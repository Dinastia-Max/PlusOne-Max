"""Seed SVAO football fields."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260928_0002"
down_revision: str | None = "20260923_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


fields_table = sa.table(
    "fields",
    sa.column("name", sa.String),
    sa.column("address", sa.String),
    sa.column("district", sa.String),
    sa.column("is_active", sa.Boolean),
)


FIELDS = [
    {
        "name": "Медведково Арена",
        "address": (
            "Москва, Северо-Восточный административный округ, "
            "район Северное Медведково «Медведково Арена»"
        ),
        "district": "SVAO",
        "is_active": True,
    },
    {
        "name": "Стадион «Юность», школа №1506, корпус 3",
        "address": (
            "Москва, Северо-Восточный административный округ, "
            "район Северное Медведково школа N1506 корпус N3 "
            "стадион «Юность»"
        ),
        "district": "SVAO",
        "is_active": True,
    },
    {
        "name": "Коробка, Стартовая улица, 35",
        "address": (
            "Москва, Северо-Восточный административный округ, "
            "Лосиноостровский район Москва Стартовая улица 35 коробка"
        ),
        "district": "SVAO",
        "is_active": True,
    },
    {
        "name": "Футбольное поле Devon Medical",
        "address": (
            "Москва, Таёжная улица, 1, "
            "стадион «Футбольное поле Devon Medical»"
        ),
        "district": "SVAO",
        "is_active": True,
    },
    {
        "name": "Коробка, Магаданская улица, 8А",
        "address": (
            "Москва, Северо-Восточный административный округ, "
            "Лосиноостровский район Магаданская улица, 8А"
        ),
        "district": "SVAO",
        "is_active": True,
    },
    {
        "name": "Коробка, Джамгаровский парк",
        "address": "Москва, Джамгаровский парк коробка",
        "district": "SVAO",
        "is_active": True,
    },
    {
        "name": "«Прайд»",
        "address": (
            "Москва, Северо-Восточный административный округ, "
            "Лосиноостровский район улица Коминтерна, 15 «Прайд»"
        ),
        "district": "SVAO",
        "is_active": True,
    },
    {
        "name": "Медицинский колледж",
        "address": "Москва, Таймырская улица, 4, Медицинский Колледж",
        "district": "SVAO",
        "is_active": True,
    },
    {
        "name": "Школа №1381, отделение 2",
        "address": (
            "Москва, Северо-Восточный административный округ, "
            "Лосиноостровский район Школа № 1381, "
            "школьное отделение № 2"
        ),
        "district": "SVAO",
        "is_active": True,
    },
    {
        "name": "Школа №763, корпус 3",
        "address": (
            "Москва, Анадырский проезд, 51, "
            "Школа № 763, учебный корпус № 3"
        ),
        "district": "SVAO",
        "is_active": True,
    },
    {
        "name": "Коробка, улица Коминтерна, 4к1",
        "address": "Москва, улица Коминтерна, 4к1, коробка",
        "district": "SVAO",
        "is_active": True,
    },
    {
        "name": "Поле, проспект Мира, 185",
        "address": (
            "Москва, Северо-Восточный административный округ, "
            "район Ростокино, проспект Мира, 185"
        ),
        "district": "SVAO",
        "is_active": True,
    },
    {
        "name": "Парк спорта Яуза",
        "address": "Москва, парк спорта Яуза",
        "district": "SVAO",
        "is_active": True,
    },
    {
        "name": "Поле, Сельскохозяйственная улица, 26с6",
        "address": (
            "Москва, Северо-Восточный административный округ, "
            "район Ростокино, Сельскохозяйственная улица, 26с6"
        ),
        "district": "SVAO",
        "is_active": True,
    },
    {
        "name": "СШОР «Юность Москвы» по футболу, Буревестник",
        "address": "СШОР Юность Москвы по футболу Буревестник",
        "district": "SVAO",
        "is_active": True,
    },
    {
        "name": "Поле, Тайнинская улица, 18",
        "address": (
            "Москва, Северо-Восточный административный округ, "
            "Лосиноостровский район, Тайнинская улица, 18"
        ),
        "district": "SVAO",
        "is_active": True,
    },
    {
        "name": "Школа №283, корпус 10",
        "address": (
            "Москва, Осташковская улица, 30, корп. 2, "
            "Школа № 283, корпус № 10"
        ),
        "district": "SVAO",
        "is_active": True,
    },
    {
        "name": "Школа №1095",
        "address": (
            "Москва, улица Менжинского, 30, "
            "Школа № 1095, учебный корпус"
        ),
        "district": "SVAO",
        "is_active": True,
    },
    {
        "name": "Школа №283, корпус 1",
        "address": (
            "Москва, Широкая улица, 21А, "
            "Школа № 283, корпус № 1"
        ),
        "district": "SVAO",
        "is_active": True,
    },
    {
        "name": "Школа №283, корпус 2",
        "address": (
            "Москва, улица Грекова, 20, "
            "Школа № 283, корпус № 2"
        ),
        "district": "SVAO",
        "is_active": True,
    },
    {
        "name": "Коробка, проезд Шокальского, 28с2",
        "address": (
            "Москва, Северо-Восточный административный округ, "
            "район Северное Медведково, Москва, "
            "проезд Шокальского, 28с2, коробка"
        ),
        "district": "SVAO",
        "is_active": True,
    },
]


def upgrade() -> None:
    connection = op.get_bind()

    for field in FIELDS:
        existing = connection.execute(
            sa.select(fields_table.c.name).where(
                fields_table.c.name == field["name"],
                fields_table.c.address == field["address"],
            )
        ).first()

        if existing is None:
            op.bulk_insert(fields_table, [field])


def downgrade() -> None:
    field_names = [field["name"] for field in FIELDS]

    op.execute(
        fields_table.delete().where(
            fields_table.c.name.in_(field_names)
        )
    )