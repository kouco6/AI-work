import { useCallback, useEffect, useRef, useState } from 'react';
import { api, ApiError } from '../api/client';

export type UseApiOptions = {
  /** 轮询间隔（毫秒）。不传则只取一次。 */
  pollMs?: number;
  /** 为 false 时不发请求（依赖未就绪时用）。 */
  enabled?: boolean;
};

export type UseApiResult<T> = {
  data: T | null;
  loading: boolean;
  error: ApiError | Error | null;
  /** 手动重新拉取。 */
  refetch: () => Promise<void>;
};

/**
 * 极薄的数据请求 hook —— 复用 `api/client.ts` 的 `api.get`（自带鉴权 / 401 刷新 / SSE）。
 *
 * 与既有 hook 风格一致：返回对象、`AbortController` 取消、竞态安全。
 * 用法：`const { data, loading, error, refetch } = useApi<Usage[]>('/api/enterprise/...', [], { pollMs: 15000 })`
 */
export function useApi<T>(
  path: string,
  deps: unknown[] = [],
  options: UseApiOptions = {},
): UseApiResult<T> {
  const { pollMs, enabled = true } = options;
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(enabled);
  const [error, setError] = useState<ApiError | Error | null>(null);
  const mounted = useRef(true);

  const load = useCallback(
    async (signal?: AbortSignal) => {
      try {
        const result = await api.get<T>(path, signal ? { signal } : undefined);
        if (!mounted.current || signal?.aborted) return;
        setData(result);
        setError(null);
      } catch (err) {
        if (!mounted.current || signal?.aborted) return;
        // 主动取消不算错误
        if (err instanceof DOMException && err.name === 'AbortError') return;
        setError(err instanceof Error ? err : new Error(String(err)));
      } finally {
        if (mounted.current && !signal?.aborted) setLoading(false);
      }
    },
    [path],
  );

  useEffect(() => {
    mounted.current = true;
    if (!enabled) {
      setLoading(false);
      return;
    }
    const controller = new AbortController();
    setLoading(true);
    void load(controller.signal);
    let timer: ReturnType<typeof setInterval> | undefined;
    if (pollMs && pollMs > 0) {
      timer = setInterval(() => void load(controller.signal), pollMs);
    }
    return () => {
      mounted.current = false;
      controller.abort();
      if (timer) clearInterval(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, pollMs, load, ...deps]);

  const refetch = useCallback(() => load(), [load]);

  return { data, loading, error, refetch };
}
