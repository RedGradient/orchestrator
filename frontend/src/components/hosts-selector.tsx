import { Plus, Search, Server } from "lucide-react"
import { useMemo, useState } from "react"

import { HostRegistrationForm } from "@/components/host-registration-form"
import { StatePanel } from "@/components/state-panel"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import type { Host } from "@/lib/api-types"

export interface HostsSelectorProps {
  hosts: Host[]
  selectedHostIds: ReadonlySet<number>
  isLoading: boolean
  error: string | null
  onRetry: () => void
  onSelectionChange: (selected: Set<number>) => void
  onHostCreated: () => Promise<void> | void
}

function hostName(host: Host): string {
  return host.label || `${host.username}@${host.ip}`
}

export function HostsSelector({
  hosts,
  selectedHostIds,
  isLoading,
  error,
  onRetry,
  onSelectionChange,
  onHostCreated,
}: HostsSelectorProps) {
  const [query, setQuery] = useState("")
  const [isFormOpen, setIsFormOpen] = useState(false)
  const normalizedQuery = query.trim().toLocaleLowerCase("ru")
  const filteredHosts = useMemo(
    () =>
      hosts.filter((host) =>
        [host.label, host.username, host.ip]
          .filter(Boolean)
          .some((value) => value?.toLocaleLowerCase("ru").includes(normalizedQuery)),
      ),
    [hosts, normalizedQuery],
  )

  const allVisibleSelected =
    filteredHosts.length > 0 && filteredHosts.every((host) => selectedHostIds.has(host.id))

  function toggleHost(hostId: number) {
    const next = new Set(selectedHostIds)
    if (next.has(hostId)) {
      next.delete(hostId)
    } else {
      next.add(hostId)
    }
    onSelectionChange(next)
  }

  function toggleVisibleHosts() {
    const next = new Set(selectedHostIds)
    for (const host of filteredHosts) {
      if (allVisibleSelected) {
        next.delete(host.id)
      } else {
        next.add(host.id)
      }
    }
    onSelectionChange(next)
  }

  return (
    <Card className="overflow-hidden">
      <div className="flex flex-col gap-4 border-b p-4 sm:p-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="font-semibold">Хосты</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Выбрано {selectedHostIds.size} из {hosts.length}
            </p>
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setIsFormOpen((open) => !open)}
            aria-expanded={isFormOpen}
          >
            <Plus aria-hidden="true" className="size-4" />
            Добавить
          </Button>
        </div>

        <div className="flex flex-col gap-2 sm:flex-row">
          <label className="relative flex-1">
            <span className="sr-only">Поиск хостов</span>
            <Search
              aria-hidden="true"
              className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
            />
            <Input
              className="pl-9"
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Поиск по названию, пользователю или IP"
            />
          </label>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            disabled={filteredHosts.length === 0}
            onClick={toggleVisibleHosts}
          >
            {allVisibleSelected ? "Снять видимые" : "Выбрать видимые"}
          </Button>
        </div>
      </div>

      {isFormOpen ? (
        <HostRegistrationForm onCreated={onHostCreated} onClose={() => setIsFormOpen(false)} />
      ) : null}

      {isLoading ? (
        <StatePanel
          kind="loading"
          title="Загружаем хосты"
          description="Получаем актуальный список с сервера."
          className="m-4 min-h-72 border-0"
        />
      ) : error ? (
        <StatePanel
          kind="error"
          title="Не удалось загрузить хосты"
          description={error}
          actionLabel="Повторить"
          onAction={onRetry}
          className="m-4 min-h-72"
        />
      ) : hosts.length === 0 ? (
        <StatePanel
          kind="empty"
          title="Хостов пока нет"
          description="Добавьте первый VPS, чтобы запускать на нём действия."
          actionLabel="Добавить хост"
          onAction={() => setIsFormOpen(true)}
          className="m-4 min-h-72"
        />
      ) : filteredHosts.length === 0 ? (
        <StatePanel
          kind="empty"
          title="Ничего не найдено"
          description="Измените поисковый запрос и попробуйте снова."
          className="m-4 min-h-72"
        />
      ) : (
        <ul className="max-h-[480px] divide-y overflow-y-auto" aria-label="Список хостов">
          {filteredHosts.map((host) => (
            <li key={host.id}>
              <label className="flex cursor-pointer items-center gap-3 px-4 py-3.5 transition-colors hover:bg-muted/50 sm:px-5">
                <Checkbox
                  checked={selectedHostIds.has(host.id)}
                  onChange={() => toggleHost(host.id)}
                  aria-label={`Выбрать ${hostName(host)}`}
                />
                <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground">
                  <Server aria-hidden="true" className="size-4" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium">{hostName(host)}</span>
                  {host.label ? (
                    <span className="block truncate font-mono text-xs text-muted-foreground">
                      {host.username}@{host.ip}
                    </span>
                  ) : (
                    <span className="block truncate font-mono text-xs text-muted-foreground">
                      ID {host.id}
                    </span>
                  )}
                </span>
              </label>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}
