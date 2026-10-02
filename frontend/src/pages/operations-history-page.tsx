import { ChevronLeft, ChevronRight, MousePointerClick, Search } from "lucide-react"
import { useEffect, useMemo, useState } from "react"
import type { FormEvent } from "react"
import { Link, useSearchParams } from "react-router-dom"

import { PageHeader } from "@/components/page-header"
import { StatePanel } from "@/components/state-panel"
import { StatusBadge } from "@/components/status-badge"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { actionTitle } from "@/lib/actions"
import { ApiError, api } from "@/lib/api-client"
import type {
  OperationHistoryFilters,
  OperationHistoryItem,
  OperationHistoryPage,
} from "@/lib/api-types"
import { durationMs, formatDateTime, formatDuration } from "@/lib/format"

export function OperationsHistoryPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const filters = useMemo(() => parseFilters(searchParams), [searchParams])
  const [data, setData] = useState<OperationHistoryPage | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [reloadVersion, setReloadVersion] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    const load = (showLoader: boolean) => {
      if (showLoader) setIsLoading(true)
      setError(null)
      api
        .listOperations(filters, controller.signal)
        .then(setData)
        .catch((caught: unknown) => {
          if (caught instanceof DOMException && caught.name === "AbortError") return
          setError(caught instanceof ApiError ? caught.message : "Не удалось загрузить историю.")
        })
        .finally(() => {
          if (!controller.signal.aborted) setIsLoading(false)
        })
    }

    load(true)
    const interval = window.setInterval(() => load(false), 5000)
    return () => {
      controller.abort()
      window.clearInterval(interval)
    }
  }, [filters, reloadVersion])

  function updateFilters(updates: Record<string, string | null>) {
    const next = new URLSearchParams(searchParams)
    Object.entries(updates).forEach(([key, value]) => {
      if (value) next.set(key, value)
      else next.delete(key)
    })
    if (!("page" in updates)) next.delete("page")
    setSearchParams(next)
  }

  function submitSearch(event: FormEvent) {
    event.preventDefault()
    const form = new FormData(event.currentTarget as HTMLFormElement)
    const query = String(form.get("query") ?? "").trim()
    updateFilters({ query: query || null })
  }

  return (
    <main>
      <PageHeader
        eyebrow="Операции"
        title="История действий"
        description="Все запуски VPS-действий, их прогресс и результаты. Активные операции обновляются автоматически."
      />

      <Card className="mt-7 p-4">
        <div className="flex flex-col gap-3 lg:flex-row">
          <form onSubmit={submitSearch} className="flex min-w-0 flex-1 gap-2">
            <div className="relative flex-1">
              <Search aria-hidden="true" className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                key={filters.query ?? ""}
                name="query"
                defaultValue={filters.query ?? ""}
                placeholder="Номер операции, IP или label"
                className="pl-9"
                aria-label="Поиск операций"
              />
            </div>
            <Button type="submit" variant="outline">Найти</Button>
          </form>
          <div className="grid grid-cols-2 gap-2 sm:flex">
            <FilterSelect
              label="Статус"
              value={filters.statusGroup ?? ""}
              onChange={(value) => updateFilters({ status: value || null })}
              options={[
                ["", "Все статусы"],
                ["active", "Выполняются"],
                ["succeeded", "Успешно"],
                ["failed", "С ошибками"],
                ["cancelled", "Отменены"],
              ]}
            />
            <FilterSelect
              label="Период"
              value={filters.days ? String(filters.days) : ""}
              onChange={(value) => updateFilters({ days: value || null })}
              options={[
                ["", "За всё время"],
                ["1", "За 24 часа"],
                ["7", "За 7 дней"],
                ["30", "За 30 дней"],
              ]}
            />
          </div>
        </div>
      </Card>

      {isLoading && !data ? (
        <StatePanel className="mt-5" kind="loading" title="Загружаем историю" />
      ) : error && !data ? (
        <StatePanel className="mt-5" kind="error" title="Не удалось загрузить историю" description={error} actionLabel="Повторить" onAction={() => setReloadVersion((value) => value + 1)} />
      ) : data?.items.length === 0 ? (
        <StatePanel className="mt-5" kind="empty" title="Операции не найдены" description="Измените фильтры или запустите новое действие." />
      ) : data ? (
        <>
          {error ? <p className="mt-4 text-sm text-destructive">{error}</p> : null}
          <p className="mt-5 flex items-center gap-2 text-sm text-muted-foreground">
            <MousePointerClick aria-hidden="true" className="size-4 shrink-0" />
            Нажмите на операцию, чтобы посмотреть подробную информацию.
          </p>
          <OperationsList items={data.items} />
          <div className="mt-4 flex items-center justify-between gap-4">
            <p className="text-sm text-muted-foreground">Показано {data.items.length} из {data.total}</p>
            <div className="flex items-center gap-2">
              <Button type="button" variant="outline" size="sm" disabled={data.page <= 1} onClick={() => updateFilters({ page: String(data.page - 1) })}>
                <ChevronLeft aria-hidden="true" className="size-4" /> Назад
              </Button>
              <span className="min-w-8 text-center text-sm">{data.page}</span>
              <Button type="button" variant="outline" size="sm" disabled={!data.has_more} onClick={() => updateFilters({ page: String(data.page + 1) })}>
                Далее <ChevronRight aria-hidden="true" className="size-4" />
              </Button>
            </div>
          </div>
        </>
      ) : null}
    </main>
  )
}

function OperationsList({ items }: { items: OperationHistoryItem[] }) {
  return (
    <Card className="mt-5 overflow-hidden p-0">
      <div className="hidden grid-cols-[80px_140px_160px_1fr_1fr_100px_110px] gap-4 border-b bg-muted/35 px-5 py-3 text-xs font-medium text-muted-foreground lg:grid">
        <span>Операция</span><span>Статус</span><span>Создана</span><span>Хосты</span><span>Действия</span><span>Прогресс</span><span>Длительность</span>
      </div>
      <div className="divide-y">
        {items.map((operation) => <OperationRow key={operation.id} operation={operation} />)}
      </div>
    </Card>
  )
}

function OperationRow({ operation }: { operation: OperationHistoryItem }) {
  const completed = operation.progress.succeeded + operation.progress.failed + operation.progress.timeout + operation.progress.cancelled
  const hosts = operation.hosts.map((host) => host.label || host.ip)
  const hostSummary = hosts.length <= 2 ? hosts.join(", ") : `${hosts.slice(0, 2).join(", ")} +${hosts.length - 2}`
  const actions = operation.actions.map(actionTitle)
  const actionSummary = actions.length <= 2 ? actions.join(", ") : `${actions.slice(0, 2).join(", ")} +${actions.length - 2}`

  return (
    <Link to={`/operations/${operation.id}`} className="block px-5 py-4 transition-colors hover:bg-muted/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring">
      <div className="grid gap-3 lg:grid-cols-[80px_140px_160px_1fr_1fr_100px_110px] lg:items-center lg:gap-4">
        <span className="font-semibold">#{operation.id}</span>
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground lg:hidden">Статус</span>
          <StatusBadge status={operation.status} className="shrink-0" />
        </div>
        <p className="text-sm text-muted-foreground">{formatDateTime(operation.created_at)}</p>
        <HistoryValue label="Хосты" value={hostSummary || "—"} />
        <HistoryValue label="Действия" value={actionSummary || "—"} />
        <HistoryValue label="Прогресс" value={`${completed} из ${operation.progress.total}`} mono />
        <HistoryValue label="Длительность" value={formatDuration(durationMs(operation.started_at, operation.finished_at))} mono />
      </div>
    </Link>
  )
}

function HistoryValue({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return <p className={`min-w-0 truncate text-sm ${mono ? "font-mono text-xs" : ""}`} title={value}><span className="mr-2 text-xs text-muted-foreground lg:hidden">{label}</span>{value}</p>
}

function FilterSelect({ label, value, options, onChange }: { label: string; value: string; options: [string, string][]; onChange: (value: string) => void }) {
  return (
    <select aria-label={label} value={value} onChange={(event) => onChange(event.target.value)} className="h-9 rounded-md border border-input bg-background px-3 text-sm shadow-sm outline-none focus:ring-2 focus:ring-ring">
      {options.map(([optionValue, optionLabel]) => <option key={optionValue} value={optionValue}>{optionLabel}</option>)}
    </select>
  )
}

function parseFilters(params: URLSearchParams): OperationHistoryFilters {
  const page = Number(params.get("page"))
  const status = params.get("status")
  const days = Number(params.get("days"))
  return {
    page: Number.isSafeInteger(page) && page > 0 ? page : 1,
    query: params.get("query")?.trim() || undefined,
    statusGroup: ["active", "succeeded", "failed", "cancelled"].includes(status ?? "") ? status as OperationHistoryFilters["statusGroup"] : undefined,
    days: [1, 7, 30].includes(days) ? days as 1 | 7 | 30 : undefined,
  }
}
