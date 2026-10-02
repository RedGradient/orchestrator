import { CheckCircle2, CircleDashed, Clock3, ListChecks, XCircle } from "lucide-react"

import { StatusBadge } from "@/components/status-badge"
import { Card } from "@/components/ui/card"
import type { Operation } from "@/lib/api-types"
import { durationMs, formatDateTime, formatDuration } from "@/lib/format"

export interface OperationSummaryProps {
  operation: Operation
}

export function OperationSummary({ operation }: OperationSummaryProps) {
  const { progress } = operation
  const completed = progress.succeeded + progress.failed + progress.timeout + progress.cancelled
  const percent = progress.total === 0 ? 0 : Math.round((completed / progress.total) * 100)
  const counters = [
    { label: "Успешно", value: progress.succeeded, icon: CheckCircle2, className: "text-success" },
    { label: "Выполняется", value: progress.running, icon: CircleDashed, className: "text-info" },
    { label: "В очереди", value: progress.pending + progress.queued, icon: Clock3, className: "text-muted-foreground" },
    { label: "Ошибки", value: progress.failed + progress.timeout, icon: XCircle, className: "text-destructive" },
  ]

  return (
    <div className="mt-6 grid gap-4 xl:grid-cols-[minmax(0,1.4fr)_minmax(320px,0.6fr)]">
      <Card className="p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-sm text-muted-foreground">Общий прогресс</p>
            <p className="mt-1 text-2xl font-semibold tracking-tight">
              {completed} / {progress.total} завершено
            </p>
          </div>
          <StatusBadge status={operation.status} />
        </div>

        <div className="mt-5 h-2 overflow-hidden rounded-full bg-muted" aria-label={`Выполнено ${percent}%`}>
          <div
            className="h-full rounded-full bg-primary transition-[width] duration-300"
            style={{ width: `${percent}%` }}
          />
        </div>
        <p className="mt-2 text-right font-mono text-xs text-muted-foreground">{percent}%</p>

        <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {counters.map(({ label, value, icon: Icon, className }) => (
            <div key={label} className="rounded-md border bg-muted/20 p-3">
              <Icon aria-hidden="true" className={`size-4 ${className}`} />
              <p className="mt-2 text-xl font-semibold">{value}</p>
              <p className="text-xs text-muted-foreground">{label}</p>
            </div>
          ))}
        </div>

        <dl className="mt-4 flex flex-wrap gap-x-4 gap-y-2 border-t pt-4 text-xs">
          <ProgressCount label="Pending" value={progress.pending} />
          <ProgressCount label="Queued" value={progress.queued} />
          <ProgressCount label="Running" value={progress.running} />
          <ProgressCount label="Succeeded" value={progress.succeeded} />
          <ProgressCount label="Failed" value={progress.failed} />
          <ProgressCount label="Timeout" value={progress.timeout} />
        </dl>
      </Card>

      <Card className="p-5">
        <div className="flex items-center gap-2">
          <ListChecks aria-hidden="true" className="size-4 text-muted-foreground" />
          <h2 className="font-semibold">Время</h2>
        </div>
        <dl className="mt-4 grid gap-3 text-sm">
          <div className="flex justify-between gap-4">
            <dt className="text-muted-foreground">Создана</dt>
            <dd className="text-right">{formatDateTime(operation.created_at)}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-muted-foreground">Запущена</dt>
            <dd className="text-right">{formatDateTime(operation.started_at)}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-muted-foreground">Завершена</dt>
            <dd className="text-right">{formatDateTime(operation.finished_at)}</dd>
          </div>
          <div className="flex justify-between gap-4 border-t pt-3">
            <dt className="font-medium">Длительность</dt>
            <dd className="font-mono text-xs">
              {formatDuration(durationMs(operation.started_at, operation.finished_at))}
            </dd>
          </div>
        </dl>
      </Card>
    </div>
  )
}

function ProgressCount({ label, value }: { label: string; value: number }) {
  return (
    <div className="inline-flex gap-1.5">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="font-mono font-medium">{value}</dd>
    </div>
  )
}
