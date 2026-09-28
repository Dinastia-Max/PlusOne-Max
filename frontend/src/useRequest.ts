import { useCallback, useEffect, useState } from "react";
import { ApiError } from "./api";

export type RequestState<T> =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "success"; data: T };

export function useRequest<T>(
  load: (signal: AbortSignal) => Promise<T>,
  deps: readonly unknown[],
): [RequestState<T>, () => void] {
  const [state, setState] = useState<RequestState<T>>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setState({ status: "loading" });

    load(controller.signal).then(
      (data) => {
        if (!controller.signal.aborted) setState({ status: "success", data });
      },
      (error: unknown) => {
        if (controller.signal.aborted) return;
        setState({
          status: "error",
          error: error instanceof ApiError ? error : new ApiError("server", "Не удалось загрузить данные"),
        });
      },
    );

    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, attempt]);

  const retry = useCallback(() => setAttempt((value) => value + 1), []);
  return [state, retry];
}
