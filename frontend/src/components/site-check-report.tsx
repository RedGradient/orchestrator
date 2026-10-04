import type { ReactNode } from "react"

import { Card } from "@/components/ui/card"
import type {
  CheckResult,
  FileCheckResult,
  HttpCheckResult,
  RobotsCheckResult,
  SitemapCheckResult,
  SslCheckResult,
} from "@/lib/api-types"
import { formatDateTime } from "@/lib/format"
import { cn } from "@/lib/utils"

export interface SiteCheckReportProps {
  result: CheckResult
}

/** Показывает подробный результат проверки сайта отдельными карточками. */
export function SiteCheckReport({ result }: SiteCheckReportProps) {
  return (
    <section aria-label="Результат проверки сайта" aria-live="polite">
      <div className="mb-4">
        <h4 className="text-lg font-semibold">{result.domain || result.url}</h4>
        <p className="truncate text-sm text-muted-foreground">{result.url}</p>
      </div>
      <div className="grid gap-4 xl:grid-cols-2">
        <HttpCard result={result.http} />
        <SslCard result={result.ssl} />
        <FileCard title="robots.txt" result={result.robots} extra={result.robots?.sitemaps} />
        <FileCard title="sitemap" result={result.sitemap} urlCount={result.sitemap?.url_count} />
      </div>
    </section>
  )
}

function ResultCard({
  title,
  ok,
  status,
  children,
}: {
  title: string
  ok: boolean | null
  status: string
  children: ReactNode
}) {
  return (
    <Card className="p-4 sm:p-5">
      <div className="flex items-center justify-between gap-3">
        <h5 className="font-semibold">{title}</h5>
        <span
          className={cn(
            "rounded-full bg-muted px-2.5 py-1 text-xs font-medium text-muted-foreground",
            ok === true && "bg-success/10 text-success",
            ok === false && "bg-destructive/10 text-destructive",
          )}
        >
          {status}
        </span>
      </div>
      {children}
    </Card>
  )
}

function HttpCard({ result }: { result: HttpCheckResult | null }) {
  if (!result) return <SkippedCard title="HTTP" />
  return (
    <ResultCard title="HTTP" ok={result.ok} status={result.ok ? "Ответил" : "Недоступен"}>
      <ResultRows
        rows={[
          ["Код", result.status_code],
          ["Время", result.response_time_ms === null ? null : `${result.response_time_ms} мс`],
          ["Ошибка", result.error],
        ]}
      />
    </ResultCard>
  )
}

function SslCard({ result }: { result: SslCheckResult | null }) {
  if (!result) return <SkippedCard title="SSL" />
  return (
    <ResultCard title="SSL" ok={result.ok} status={result.ok ? "Сертификат принят" : "Ошибка"}>
      <ResultRows
        rows={[
          ["Версия", result.version],
          ["Издатель", result.issuer],
          ["Истекает", result.expires_at ? formatDateTime(result.expires_at) : null],
          ["Осталось дней", result.days_remaining],
          ["Ошибка", result.error],
        ]}
      />
    </ResultCard>
  )
}

function FileCard({
  title,
  result,
  extra,
  urlCount,
}: {
  title: string
  result: FileCheckResult | RobotsCheckResult | SitemapCheckResult | null
  extra?: string[]
  urlCount?: number | null
}) {
  if (!result) return <SkippedCard title={title} />
  const ok = result.available && result.valid !== false && !result.error
  return (
    <ResultCard
      title={title}
      ok={ok}
      status={result.error ? "Ошибка" : result.available ? "Найден" : "Нет файла"}
    >
      <ResultRows
        rows={[
          ["Код", result.status_code],
          ["Синтаксис", result.valid === null ? null : result.valid ? "корректный" : "с ошибками"],
          ["Адресов", urlCount ?? null],
          ["Ошибка", result.error],
        ]}
      />
      <Notes title="Ошибки" items={result.errors} destructive />
      <Notes title="Предупреждения" items={result.warnings} />
      <Notes title="Sitemap" items={extra ?? []} />
    </ResultCard>
  )
}

function SkippedCard({ title }: { title: string }) {
  return (
    <ResultCard title={title} ok={null} status="Не проверялось">
      <p className="mt-4 text-sm text-muted-foreground">Проверка была пропущена.</p>
    </ResultCard>
  )
}

function ResultRows({ rows }: { rows: Array<[string, string | number | null]> }) {
  const visible = rows.filter(([, value]) => value !== null)
  return (
    <dl className="mt-4 grid grid-cols-[110px_minmax(0,1fr)] gap-x-3 gap-y-2 text-sm">
      {visible.map(([label, value]) => (
        <div key={label} className="contents">
          <dt className="text-muted-foreground">{label}</dt>
          <dd className="break-words">{value}</dd>
        </div>
      ))}
    </dl>
  )
}

function Notes({
  title,
  items,
  destructive = false,
}: {
  title: string
  items: string[]
  destructive?: boolean
}) {
  if (items.length === 0) return null
  return (
    <div className="mt-4">
      <p className="text-xs font-semibold text-muted-foreground">{title}</p>
      <ul className={cn("mt-1 list-disc space-y-1 pl-5 text-sm", destructive && "text-destructive")}>
        {items.map((item, index) => (
          <li key={`${item}:${index}`} className="break-words">
            {item}
          </li>
        ))}
      </ul>
    </div>
  )
}
