import { useState, useEffect, useCallback } from 'react'

export function useApi(apiFn, deps = []) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetch = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await apiFn()
      setData(res.data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, deps) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    fetch()
  }, [fetch])

  return { data, loading, error, refetch: fetch }
}
