import { AlertTriangle, Check, X } from "lucide-react"

import { Card } from "@/components/ui/card"
import type {
  Overlay2AnalyzeResult,
  Overlay2CleanupResult,
  Overlay2Finding,
  Overlay2FindingState,
} from "@/lib/api-types"
import { formatBytes } from "@/lib/format"
import { cn } from "@/lib/utils"

export interface Overlay2ReportProps {
  result: Overlay2AnalyzeResult | Overlay2CleanupResult
  cleanup?: boolean
}

const statePresentation: Record<Overlay2FindingState, { label: string; className: string }> = {
  LIVE: { label: "Используется", className: "bg-success/10 text-success" },
  REFERENCED: { label: "Есть ссылка", className: "bg-success/10 text-success" },
  TEMPORARY: { label: "Защитный период", className: "bg-info/10 text-info" },
  SUSPECTED_ORPHAN: { label: "Вероятный orphan", className: "bg-warning/10 text-warning-foreground" },
  CONFIRMED_ORPHAN: { label: "Подтверждённый orphan", className: "bg-destructive/10 text-destructive" },
  UNKNOWN: { label: "Не определено", className: "bg-muted text-muted-foreground" },
}

/** Показывает отчёт анализа или очистки Docker overlay2 отдельными карточками. */
export function Overlay2Report({ result, cleanup = false }: Overlay2ReportProps) {
  const cleanupResult = cleanup ? (result as Overlay2CleanupResult) : null
  const reclaimable = cleanupResult
    ? cleanupResult.operation_plan.reduce((total, item) => total + item.size_bytes, 0)
    : result.summary.suspected_orphan_bytes

  return (
    <section aria-label="Результат анализа Docker overlay2" aria-live="polite">
      <div
        className={cn(
          "mb-4 flex items-start gap-3 rounded-md border p-3 text-sm",
          result.unsafe
            ? "border-destructive/25 bg-destructive/5 text-destructive"
            : "border-success/25 bg-success/5 text-success",
        )}
        role={result.unsafe ? "alert" : undefined}
      >
        {result.unsafe ? (
          <AlertTriangle aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
        ) : (
          <Check aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
        )}
        <div>
          <p className="font-medium">
            {result.unsafe
              ? "Неполные данные: очистка по этому отчёту запрещена."
              : "Все источники данных доступны."}
          </p>
          <p className="mt-0.5 text-xs opacity-90">
            Docker root: {result.docker_root ?? "не определён"} · Overlay2:{" "}
            {result.overlay2_root ?? "не определён"}
          </p>
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="Занято overlay2" value={formatBytes(result.disk_usage_bytes)} />
        <Metric
          label={cleanup ? "Освобождено" : "Вероятно можно освободить"}
          value={formatBytes(cleanup ? (cleanupResult?.freed_bytes ?? 0) : reclaimable)}
        />
        <Metric label="Вероятные orphan" value={formatBytes(result.summary.suspected_orphan_bytes)} />
        <Metric label="Не определено" value={formatBytes(result.summary.unknown_bytes)} />
      </div>

      {cleanupResult ? <CleanupCard result={cleanupResult} reclaimable={reclaimable} /> : null}

      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <SourcesCard sources={result.sources} />
        <FindingsCard findings={result.findings} omitted={result.omitted_findings_count} />
      </div>
    </section>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <Card className="p-4">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 text-lg font-semibold">{value}</p>
    </Card>
  )
}

function SourcesCard({ sources }: { sources: Overlay2AnalyzeResult["sources"] }) {
  return (
    <Card className="p-4 sm:p-5">
      <h4 className="font-semibold">Источники данных</h4>
      <ul className="mt-3 divide-y rounded-md border">
        {sources.map((source) => (
          <li key={source.name + ":" + source.detail} className="flex items-start gap-2 px-3 py-2 text-sm">
            {source.ok ? (
              <Check aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-success" />
            ) : (
              <X aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-destructive" />
            )}
            <span className="min-w-0">
              <span className="font-medium">{source.name}</span>
              <span className="mt-0.5 block break-words text-xs text-muted-foreground">
                {source.detail}
              </span>
            </span>
          </li>
        ))}
      </ul>
    </Card>
  )
}

function FindingsCard({ findings, omitted }: { findings: Overlay2Finding[]; omitted: number }) {
  return (
    <Card className="p-4 sm:p-5">
      <h4 className="font-semibold">Найденные объекты</h4>
      {findings.length === 0 ? (
        <p className="mt-3 text-sm text-muted-foreground">
          Объектов, требующих внимания, не найдено.
        </p>
      ) : (
        <ul className="mt-3 divide-y rounded-md border">
          {findings.map((finding) => (
            <li key={finding.path} className="px-3 py-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-mono text-xs">{finding.object_id}</span>
                <StateBadge state={finding.state} />
              </div>
              <p className="mt-2 text-sm">{finding.reason}</p>
              <p className="mt-1 break-all text-xs text-muted-foreground">
                {formatBytes(finding.size_bytes)} · возраст {formatAge(finding.age_seconds)} ·{" "}
                {finding.path}
              </p>
            </li>
          ))}
        </ul>
      )}
      {omitted > 0 ? (
        <p className="mt-3 text-xs text-muted-foreground">В отчёте не показано объектов: {omitted}.</p>
      ) : null}
    </Card>
  )
}

function CleanupCard({ result, reclaimable }: { result: Overlay2CleanupResult; reclaimable: number }) {
  return (
    <Card className="mt-4 p-4 sm:p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h4 className="font-semibold">Очистка</h4>
        <span className="text-sm text-muted-foreground">
          Подтверждено: {formatBytes(reclaimable)}
        </span>
      </div>
      {result.operation_plan.length === 0 ? (
        <p className="mt-3 text-sm text-muted-foreground">Подтверждённых объектов для удаления нет.</p>
      ) : (
        <ul className="mt-3 divide-y rounded-md border">
          {result.operations.map((operation) => {
            const failed =
              operation.result.startsWith("FAILED") || operation.result.startsWith("SKIPPED")
            return (
              <li key={operation.path} className="flex items-start gap-2 px-3 py-2 text-sm">
                {failed ? (
                  <X aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-destructive" />
                ) : (
                  <Check aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-success" />
                )}
                <span className="min-w-0">
                  <span className="font-medium">{operation.result}</span>
                  <span className="mt-0.5 block break-all text-xs text-muted-foreground">
                    {operation.path}
                  </span>
                </span>
              </li>
            )
          })}
        </ul>
      )}
    </Card>
  )
}

function StateBadge({ state }: { state: Overlay2FindingState }) {
  const presentation = statePresentation[state]
  return (
    <span className={cn("rounded-full px-2.5 py-1 text-xs font-medium", presentation.className)}>
      {presentation.label}
    </span>
  )
}

function formatAge(seconds: number): string {
  if (seconds < 60) return "меньше минуты"
  if (seconds < 3600) return Math.floor(seconds / 60) + " мин"
  if (seconds < 86400) return Math.floor(seconds / 3600) + " ч"
  return Math.floor(seconds / 86400) + " д"
}
