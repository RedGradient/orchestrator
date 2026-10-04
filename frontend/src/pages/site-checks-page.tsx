import { Check, Globe2, History, LoaderCircle, Search, X } from "lucide-react"
import { type FormEvent, useCallback, useEffect, useState } from "react"

import { PageHeader } from "@/components/page-header"
import { SiteCheckReport } from "@/components/site-check-report"
import { StatePanel } from "@/components/state-panel"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { ApiError, api } from "@/lib/api-client"
import type {
  CheckHistoryItem,
  CheckResult,
} from "@/lib/api-types"
import { formatDateTime } from "@/lib/format"
import { cn } from "@/lib/utils"

export function SiteChecksPage() {
  const [history, setHistory] = useState<CheckHistoryItem[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [result, setResult] = useState<CheckResult | null>(null)
  const [isHistoryLoading, setIsHistoryLoading] = useState(true)
  const [historyError, setHistoryError] = useState<string | null>(null)
  const [isChecking, setIsChecking] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  const loadHistory = useCallback(async (selectNewest = false, signal?: AbortSignal) => {
    try {
      const items = await api.listSiteChecks(signal)
      setHistory(items)
      setHistoryError(null)
      if (selectNewest && items[0]) {
        setSelectedId(items[0].id)
        setResult(items[0].result)
      }
    } catch (caught) {
      if (caught instanceof DOMException && caught.name === "AbortError") return
      setHistoryError(
        caught instanceof ApiError ? caught.message : "Не удалось загрузить журнал.",
      )
    } finally {
      if (!signal?.aborted) setIsHistoryLoading(false)
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    api
      .listSiteChecks(controller.signal)
      .then((items) => {
        setHistory(items)
        setHistoryError(null)
      })
      .catch((caught: unknown) => {
        if (caught instanceof DOMException && caught.name === "AbortError") return
        setHistoryError(
          caught instanceof ApiError ? caught.message : "Не удалось загрузить журнал.",
        )
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsHistoryLoading(false)
      })
    return () => controller.abort()
  }, [])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    const data = new FormData(form)
    const rawUrl = String(data.get("url") ?? "").trim()
    const url = /^https?:\/\//i.test(rawUrl) ? rawUrl : `https://${rawUrl}`

    setIsChecking(true)
    setFormError(null)
    try {
      const checked = await api.runSiteCheck(url)
      setResult(checked)
      await loadHistory(true)
    } catch (caught) {
      setFormError(caught instanceof ApiError ? caught.message : "Сервис проверки не ответил.")
    } finally {
      setIsChecking(false)
    }
  }

  function selectHistoryItem(item: CheckHistoryItem) {
    setSelectedId(item.id)
    setResult(item.result)
  }

  return (
    <main>
      <PageHeader
        eyebrow="Мониторинг"
        title="Проверка сайта"
        description="HTTP, TLS-сертификат, robots.txt и sitemap. Результаты сохраняются в журнале."
      />

      <form className="mt-6" onSubmit={handleSubmit}>
        <label htmlFor="site-url" className="mb-2 block text-sm font-medium">
          Адрес сайта
        </label>
        <div className="flex flex-col gap-2 sm:flex-row">
          <div className="relative flex-1">
            <Globe2
              aria-hidden="true"
              className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
            />
            <Input
              id="site-url"
              name="url"
              type="text"
              inputMode="url"
              autoComplete="url"
              placeholder="https://example.com"
              className="pl-9"
              required
              disabled={isChecking}
            />
          </div>
          <Button type="submit" disabled={isChecking} className="sm:min-w-32">
            {isChecking ? (
              <LoaderCircle aria-hidden="true" className="size-4 animate-spin" />
            ) : (
              <Search aria-hidden="true" className="size-4" />
            )}
            {isChecking ? "Проверяем…" : "Проверить"}
          </Button>
        </div>
        {formError ? (
          <p className="mt-2 text-sm text-destructive" role="alert">
            {formError}
          </p>
        ) : null}
      </form>

      <div className="mt-7 grid items-start gap-5 lg:grid-cols-[300px_minmax(0,1fr)]">
        <CheckHistory
          items={history}
          selectedId={selectedId}
          isLoading={isHistoryLoading}
          error={historyError}
          onSelect={selectHistoryItem}
          onRetry={() => {
            setIsHistoryLoading(true)
            void loadHistory()
          }}
        />
        <CheckReport result={result} isChecking={isChecking} />
      </div>
    </main>
  )
}

function CheckHistory({
  items,
  selectedId,
  isLoading,
  error,
  onSelect,
  onRetry,
}: {
  items: CheckHistoryItem[]
  selectedId: number | null
  isLoading: boolean
  error: string | null
  onSelect: (item: CheckHistoryItem) => void
  onRetry: () => void
}) {
  return (
    <Card className="overflow-hidden">
      <div className="flex items-center gap-2 border-b p-4">
        <History aria-hidden="true" className="size-4 text-muted-foreground" />
        <h2 className="font-semibold">Журнал</h2>
      </div>
      {isLoading ? (
        <StatePanel kind="loading" title="Загружаем" className="m-3 min-h-48 border-0" />
      ) : error ? (
        <StatePanel
          kind="error"
          title="Журнал недоступен"
          description={error}
          actionLabel="Повторить"
          onAction={onRetry}
          className="m-3 min-h-48"
        />
      ) : items.length === 0 ? (
        <StatePanel
          kind="empty"
          title="Пока нет проверок"
          description="Запустите первую проверку сайта."
          className="m-3 min-h-48"
        />
      ) : (
        <ul className="max-h-[620px] divide-y overflow-y-auto" aria-label="История проверок">
          {items.map((item) => (
            <li key={item.id}>
              <button
                type="button"
                onClick={() => onSelect(item)}
                className={cn(
                  "w-full px-4 py-3 text-left transition-colors hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring",
                  selectedId === item.id && "bg-primary/[0.06]",
                )}
              >
                <span className="block truncate text-sm font-medium">
                  {item.result.domain || item.result.url}
                </span>
                <span className="mt-1 block text-xs text-muted-foreground">
                  {formatDateTime(item.created_at)} · {item.trigger === "automatic" ? "авто" : "вручную"}
                </span>
                <CheckMarks result={item.result} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

function CheckMarks({ result }: { result: CheckResult }) {
  const marks = [
    ["HTTP", result.http?.ok],
    ["SSL", result.ssl?.ok],
    ["robots.txt", result.robots ? result.robots.available && !result.robots.error : undefined],
    ["sitemap", result.sitemap ? result.sitemap.available && !result.sitemap.error : undefined],
  ] as const
  return (
    <span className="mt-2 flex flex-wrap gap-1.5">
      {marks.map(([label, ok]) => (
        <span
          key={label}
          className={cn(
            "inline-flex items-center gap-1 rounded-full bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground",
            ok === true && "bg-success/10 text-success",
            ok === false && "bg-destructive/10 text-destructive",
          )}
        >
          {ok === true ? <Check aria-hidden="true" className="size-2.5" /> : ok === false ? <X aria-hidden="true" className="size-2.5" /> : null}
          {label}
        </span>
      ))}
    </span>
  )
}

function CheckReport({ result, isChecking }: { result: CheckResult | null; isChecking: boolean }) {
  if (isChecking) {
    return <StatePanel kind="loading" title="Проверяем сайт" description="Это может занять несколько секунд." />
  }
  if (!result) {
    return <StatePanel kind="empty" title="Результатов пока нет" description="Запустите проверку или выберите запись в журнале." />
  }
  return <SiteCheckReport result={result} />
}
