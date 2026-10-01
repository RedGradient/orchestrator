import { useCallback, useEffect, useMemo, useState } from "react"
import { useNavigate } from "react-router-dom"

import { ActionsSelector } from "@/components/actions-selector"
import { HostsSelector } from "@/components/hosts-selector"
import { OperationPreview } from "@/components/operation-preview"
import { PageHeader } from "@/components/page-header"
import { actions } from "@/lib/actions"
import { ApiError, api } from "@/lib/api-client"
import type { Command, Host } from "@/lib/api-types"

export function ActionsPage() {
  const navigate = useNavigate()
  const [hosts, setHosts] = useState<Host[]>([])
  const [selectedHostIds, setSelectedHostIds] = useState<Set<number>>(new Set())
  const [selectedActions, setSelectedActions] = useState<Set<Command>>(new Set())
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [reloadVersion, setReloadVersion] = useState(0)
  const [isCreating, setIsCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)

  const selectedHosts = useMemo(
    () => hosts.filter((host) => selectedHostIds.has(host.id)),
    [hosts, selectedHostIds],
  )
  const selectedActionDefinitions = useMemo(
    () => actions.filter((action) => selectedActions.has(action.command)),
    [selectedActions],
  )

  const reloadHosts = useCallback(() => {
    setIsLoading(true)
    setError(null)
    setReloadVersion((version) => version + 1)
  }, [])

  useEffect(() => {
    const controller = new AbortController()

    api
      .listHosts(controller.signal)
      .then((loadedHosts) => {
        setHosts(loadedHosts)
        const knownHostIds = new Set(loadedHosts.map((host) => host.id))
        setSelectedHostIds((selected) =>
          new Set([...selected].filter((hostId) => knownHostIds.has(hostId))),
        )
      })
      .catch((caught: unknown) => {
        if (caught instanceof DOMException && caught.name === "AbortError") {
          return
        }
        setError(caught instanceof ApiError ? caught.message : "Не удалось загрузить хосты.")
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsLoading(false)
        }
      })

    return () => controller.abort()
  }, [reloadVersion])

  async function createOperation() {
    if (selectedHosts.length === 0 || selectedActionDefinitions.length === 0 || isCreating) {
      return
    }

    setIsCreating(true)
    setCreateError(null)
    try {
      const accepted = await api.createOperation({
        host_ids: selectedHosts.map((host) => host.id),
        actions: selectedActionDefinitions.map((action) => ({
          command: action.command,
          parameters: {},
        })),
      })
      navigate(`/operations/${accepted.operation_id}`)
    } catch (caught) {
      setCreateError(
        caught instanceof ApiError ? caught.message : "Не удалось создать операцию.",
      )
      setIsCreating(false)
    }
  }

  return (
    <main>
      <PageHeader
        eyebrow="Операции"
        title="Действия с VPS"
        description="Выберите хосты и действия. Перед запуском вы сможете проверить полный список задач."
      />

      <div className="mt-7 grid items-start gap-5 xl:grid-cols-[minmax(0,1.08fr)_minmax(420px,0.92fr)]">
        <HostsSelector
          hosts={hosts}
          selectedHostIds={selectedHostIds}
          isLoading={isLoading}
          error={error}
          onRetry={reloadHosts}
          onSelectionChange={setSelectedHostIds}
          onHostCreated={reloadHosts}
          disabled={isCreating}
        />
        <ActionsSelector
          selectedActions={selectedActions}
          onSelectionChange={setSelectedActions}
          disabled={isCreating}
        />
      </div>

      <OperationPreview
        hosts={selectedHosts}
        actions={selectedActionDefinitions}
        isCreating={isCreating}
        error={createError}
        onCreate={createOperation}
      />
    </main>
  )
}
