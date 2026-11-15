import { useCallback, useEffect, useState } from 'react'

/** Load something and keep the three states every screen shows: loading, failed with a retry, and loaded. */
export function useResource<T>(load: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T>()
  const [error, setError] = useState<string>()
  const [loading, setLoading] = useState(true)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const run = useCallback(async () => {
    setLoading(true)
    setError(undefined)
    try {
      setData(await load())
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, deps)
  useEffect(() => {
    void run()
  }, [run])
  return { data, setData, error, loading, retry: run }
}
