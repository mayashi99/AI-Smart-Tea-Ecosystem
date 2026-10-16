import { useCallback, useEffect, useState } from 'react'
import { get } from '../services/api.js'

export function useRemote(path) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(Boolean(path))
  const [error, setError] = useState('')
  const reload = useCallback(async () => {
    if (!path) { setData(null); setLoading(false); return }
    setLoading(true); setError('')
    try { setData(await get(path)) }
    catch (err) { setError(err.message); setData(null) }
    finally { setLoading(false) }
  }, [path])
  useEffect(() => { let mounted = true
    if (!path) return () => { mounted = false }
    setLoading(true); setError('')
    get(path).then((value) => { if (mounted) setData(value) }).catch((err) => { if (mounted) { setError(err.message); setData(null) } }).finally(() => { if (mounted) setLoading(false) })
    return () => { mounted = false }
  }, [path])
  return { data, loading, error, reload }
}
