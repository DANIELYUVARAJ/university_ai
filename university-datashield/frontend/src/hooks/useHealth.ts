import { useState, useEffect, useCallback } from 'react'
import { HEALTH_URL } from '../config'
import type { HealthResponse, BackendStatus } from '../types'

interface UseHealthResult {
  status: BackendStatus
  data: HealthResponse | null
  error: string | null
  lastChecked: Date | null
  refresh: () => void
}

/**
 * Polls the /health endpoint and returns the live backend status.
 * The status is NOT hard-coded — it reflects a real HTTP call.
 */
export function useHealth(pollIntervalMs = 15_000): UseHealthResult {
  const [status, setStatus] = useState<BackendStatus>('checking')
  const [data, setData] = useState<HealthResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [lastChecked, setLastChecked] = useState<Date | null>(null)

  const check = useCallback(async () => {
    try {
      const controller = new AbortController()
      const timeout = setTimeout(() => controller.abort(), 5_000)
      const res = await fetch(HEALTH_URL, { signal: controller.signal })
      clearTimeout(timeout)

      if (!res.ok) {
        throw new Error(`HTTP ${res.status} ${res.statusText}`)
      }

      const json: HealthResponse = await res.json()
      setData(json)
      setStatus('online')
      setError(null)
    } catch (err) {
      setStatus('offline')
      setData(null)
      if (err instanceof Error) {
        setError(err.name === 'AbortError' ? 'Request timed out' : err.message)
      } else {
        setError('Unknown error')
      }
    } finally {
      setLastChecked(new Date())
    }
  }, [])

  useEffect(() => {
    check()
    const id = setInterval(check, pollIntervalMs)
    return () => clearInterval(id)
  }, [check, pollIntervalMs])

  return { status, data, error, lastChecked, refresh: check }
}
