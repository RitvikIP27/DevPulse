import { useCallback, useEffect, useState } from "react";

export type AsyncState<T> =
  | { status: "loading" }
  | { status: "error"; error: Error }
  | { status: "success"; data: T };

/**
 * Every async screen must account for loading, success, empty and error
 * (rules.md 14). Emptiness depends on the shape of the data, so it is decided by
 * the screen; this hook guarantees the other three are always represented.
 */
export function useAsync<T>(load: () => Promise<T>, deps: unknown[]): {
  state: AsyncState<T>;
  reload: () => void;
} {
  const [state, setState] = useState<AsyncState<T>>({ status: "loading" });
  const [nonce, setNonce] = useState(0);

  // `load` is redefined on every render by callers, so the effect intentionally
  // keys off the caller-supplied deps rather than the function identity.
  const run = useCallback(load, deps);

  useEffect(() => {
    let cancelled = false;
    setState({ status: "loading" });
    run()
      .then((data) => {
        if (!cancelled) setState({ status: "success", data });
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setState({
            status: "error",
            error: error instanceof Error ? error : new Error("Unexpected error"),
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [run, nonce]);

  return { state, reload: () => setNonce((n) => n + 1) };
}
