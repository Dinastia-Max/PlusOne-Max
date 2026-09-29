# PlusOne

Мини-приложение в MAX для поиска спортивных игр рядом и набора участников.

## Запуск бота

Укажите токен созданного бота в локальном `.env`:

```env
MAX_BOT_TOKEN=your_token
```

Затем запустите сервисы:

```bash
docker compose up --build
```

Сервис `bot` подключается к MAX через Long Polling. Откройте бота в MAX и
нажмите «Начать» или отправьте `/start` — бот ответит приветствием.

Если задан `MAX_MINI_APP_URL`, бот добавит к приветствию кнопку открытия
мини-приложения. Сервис `miniapp` сам собирает React-приложение из `frontend/`
и раздаёт его на `http://localhost:8080`. Запросы к API он проксирует с пути
`/api` на `backend`, поэтому наружу нужен только один адрес — порт `8080`.
Публичный HTTPS-URL этого порта (например, через `cloudflared tunnel --url
http://localhost:8080`) нужно указать и в `MAX_MINI_APP_URL`, и в настройках
мини-приложения этого бота на платформе MAX для партнёров.

Для локальной разработки фронтенда без Docker см. `frontend/.env.example`:
`VITE_API_URL` задаёт адрес API.

Токен нельзя добавлять в Git. Long Polling используется только для локальной
разработки; перед публикацией бот должен быть переведён на HTTPS Webhook.

## Уведомления

Задания создаёт API (запись, выход, отмена игры, напоминания за 24/2/1 час),
а доставляет отдельный процесс `python -m app.notification_worker`. Он не
зависит от long-polling бота: `bot` можно остановить, рассылка продолжится.
Локально worker поднимается вместе со всем стеком (`docker compose up --build`,
сервис `notification-worker`); если в базе нет таблицы `notification_jobs`,
пересоберите образы — миграции применяет `backend` при старте.

### Render

Worker разворачивается как отдельный **Background Worker** из `render.yaml`
(New → Blueprint) либо вручную с теми же параметрами:

| Параметр | Значение |
| --- | --- |
| Runtime | Docker, `backend/Dockerfile`, context `backend` |
| Docker command | `python -m app.notification_worker` |
| `DATABASE_URL`, `MAX_BOT_TOKEN` | те же значения, что у API |
| `NOTIFICATION_*` | см. `.env.example` (значения по умолчанию подходят) |

Миграции применяет только API (`alembic upgrade head` в команде запуска). Worker
сам ничего не мигрирует: при старте он ждёт, пока версия схемы в
`alembic_version` совпадёт с последней миграцией образа, и пишет в лог
`Waiting for migrations`. Так на первом деплое не возникает гонки и ошибок
`relation "notification_jobs" does not exist`. Render перезапускает упавший
worker сам; при остановке (SIGTERM) worker дорабатывает текущее сообщение,
а нетронутые задания возвращает в очередь.

### Статусы, повторы и наблюдение

| Статус | Значение |
| --- | --- |
| `pending` | ждёт `scheduled_at` или повторной попытки |
| `processing` | взято worker'ом |
| `sent` | доставлено (`sent_at`) |
| `failed` | попытки исчерпаны, причина в `last_error` |
| `canceled` | отменено (игра отменена или участник вышел) |

- Ошибка отправки: повтор через 60, 120, 240, 480 с (далее 960 с), всего
  `NOTIFICATION_MAX_ATTEMPTS` попыток; `last_error` содержит тип ошибки и тело
  ответа MAX.
- Задание, зависшее в `processing` дольше `NOTIFICATION_LOCK_TIMEOUT_SECONDS`
  (worker упал), возвращается в `pending`; потеря блокировки считается попыткой,
  поэтому «ядовитое» задание в итоге станет `failed`.
- Раз в `NOTIFICATION_STATS_INTERVAL_SECONDS` в лог пишется строка
  `Notification queue: pending=… processing=… sent=… failed=… canceled=… due=… oldest_due_lag=…`;
  если очередь отстаёт больше 5 минут, уровень — `WARNING`. Каждая неудачная
  попытка — `WARNING`, окончательный отказ — `ERROR` с id задания, типом и
  получателем.

Состояние очереди и последние ошибки можно посмотреть SQL-запросами:

```sql
SELECT status, count(*) FROM notification_jobs GROUP BY status;

SELECT id, notification_type, recipient_user_id, attempts, last_error, scheduled_at
FROM notification_jobs
WHERE status = 'failed' OR last_error IS NOT NULL
ORDER BY id DESC LIMIT 20;
```

### Smoke-тест доставки

Пользователь должен хотя бы раз открыть диалог с ботом. Скрипт создаёт по одному
заданию каждого типа (`joined`, `reminder_24h`, `reminder_2h`,
`game_status_1h`, `slot_canceled`, `participant_left`) для указанного
пользователя и ждёт, пока работающий worker их отправит:

```bash
docker compose exec backend python -m app.notification_smoke --user-id <MAX_USER_ID>
```

На Render запустите ту же команду в Shell сервиса API. Код возврата `0` —
все шесть сообщений получили статус `sent`. Сквозную проверку триггеров
выполните вручную двумя аккаунтами: запись → сразу приходит «Вы записаны»;
выход участника → организатору приходит «отказался от игры»; отмена игры →
уведомление получают все записанные; напоминания приходят за 24 ч, 2 ч и 1 ч.

## Тесты API

Интеграционные тесты используют отдельную временную PostgreSQL и не обращаются
к рабочей базе. Запуск полного набора тестов:

```bash
docker compose --profile test run --rm --build backend-test
docker compose --profile test rm -sf test-postgres
```

Первой командой применяются миграции и запускаются unit- и интеграционные
тесты. Вторая удаляет тестовый контейнер и его временные данные.

## Авторизация API

Мини-приложение передаёт строку `window.WebApp.initData` в заголовке
`X-Max-Init-Data`. Backend проверяет её подпись с помощью `MAX_BOT_TOKEN`,
срок действия и получает ID пользователя из подписанных данных. По умолчанию
данные действуют один час; срок можно изменить через
`MAX_AUTH_MAX_AGE_SECONDS`. Заголовок `X-User-Id` больше не используется.
Разрешённые адреса мини-приложения задаются через `CORS_ORIGINS`
через запятую; для локального запуска используется `http://localhost:8080`.
