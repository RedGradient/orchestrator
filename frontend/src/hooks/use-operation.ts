import { useCallback, useEffect, useRef, useState } from "react"

import { ApiError, api } from "@/lib/api-client"
import type { Operation, OperationStatus } from "@/lib/api-types"

const terminalStatuses = new Set<OperationStatus>([
  "succeeded",
  "failed",
  "partial_failure",
  "cancelled",
])

export type RealtimeState = "idle" | "connecting" | "connected" | "reconnecting" | "closed"

export function isTerminalOperation(status: OperationStatus): boolean {
  return terminalStatuses.has(status)
}

export function useOperation(operationId: number | null) {
  const [operation, setOperation] = useState<Operation | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [realtimeState, setRealtimeState] = useState<RealtimeState>("idle")
  const mountedRef = useRef(true)
  const refreshInFlightRef = useRef<Promise<void> | null>(null)
  const refreshQueuedRef = useRef(false)

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
    }
  }, [])

  const refresh = useCallback(async () => {
    if (operationId === null) {
      return
    }
    if (refreshInFlightRef.current) {
      refreshQueuedRef.current = true
      return refreshInFlightRef.current
    }

    const run = async () => {
      do {
        refreshQueuedRef.current = false
        const snapshot = await api.getOperation(operationId)
        if (mountedRef.current) {
          setOperation(snapshot)
          setError(null)
        }
      } while (refreshQueuedRef.current)
    }

    const promise = run()
      .catch((caught: unknown) => {
        if (mountedRef.current) {
          setError(
            caught instanceof ApiError ? caught.message : "Не удалось загрузить операцию.",
          )
        }
      })
      .finally(() => {
        refreshInFlightRef.current = null
        if (mountedRef.current) {
          setIsLoading(false)
        }
      })
    refreshInFlightRef.current = promise
    return promise
  }, [operationId])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const isTerminal = operation ? isTerminalOperation(operation.status) : false
  const hasOperation = operation !== null

  useEffect(() => {
    if (operationId === null || !hasOperation || isTerminal) {
      return
    }

    const events = new EventSource(`/api/operations/${operationId}/events`)

    events.onopen = () => {
      setRealtimeState("connected")
      void refresh()
    }
    events.onerror = () => {
      setRealtimeState("reconnecting")
    }

    const handleUpdate = () => {
      void refresh()
    }
    const handleCompleted = () => {
      void refresh().finally(() => events.close())
    }

    events.addEventListener("task.updated", handleUpdate)
    events.addEventListener("operation.updated", handleUpdate)
    events.addEventListener("operation.completed", handleCompleted)

    return () => events.close()
  }, [hasOperation, isTerminal, operationId, refresh])

  const cancel = useCallback(async () => {
    if (operationId === null) {
      return
    }
    const snapshot = await api.cancelOperation(operationId)
    setOperation(snapshot)
  }, [operationId])

  const effectiveRealtimeState = isTerminal ? "closed" : hasOperation ? realtimeState : "idle"

  return { operation, isLoading, error, realtimeState: effectiveRealtimeState, refresh, cancel }
}
