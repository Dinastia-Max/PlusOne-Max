import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "./api";

export type RequestState<T> =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "success"; data: T };

export function useRequest<T>(
  load: (signal: AbortSignal) => Promise<T>,
  deps: readonly unknown[],
): [RequestState<T>, (silent?: boolean) => void] {
  const [state, setState] = useState<RequestState<T>>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);
  const silentRef = useRef(false);

  useEffect(() => {
    const controller = new AbortController();
    if (!silentRef.current) setState({ status: "loading" });
    silentRef.current = false;

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

  const reload = useCallback((silent = false) => {
    silentRef.current = silent === true;
    setAttempt((value) => value + 1);
  }, []);

  return [state, reload];
}
