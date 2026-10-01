import type { OperationStatus, TaskStatus } from "@/lib/api-types"
import { cn } from "@/lib/utils"

type Status = OperationStatus | TaskStatus

const statusPresentation: Record<Status, { label: string; className: string }> = {
  pending: { label: "Ожидает", className: "bg-muted text-muted-foreground" },
  queued: { label: "В очереди", className: "bg-muted text-muted-foreground" },
  running: { label: "Выполняется", className: "bg-info/10 text-info" },
  succeeded: { label: "Успешно", className: "bg-success/10 text-success" },
  failed: { label: "Ошибка", className: "bg-destructive/10 text-destructive" },
  partial_failure: {
    label: "Частичная ошибка",
    className: "bg-warning/10 text-warning-foreground",
  },
  timeout: { label: "Тайм-аут", className: "bg-warning/10 text-warning-foreground" },
  cancellation_requested: {
    label: "Отмена запрошена",
    className: "bg-warning/10 text-warning-foreground",
  },
  cancelled: { label: "Отменено", className: "bg-muted text-muted-foreground" },
}

export interface StatusBadgeProps {
  status: Status
  className?: string
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const presentation = statusPresentation[status]

  return (
    <span
      className={cn(
        "inline-flex h-6 items-center rounded-full px-2.5 text-xs font-semibold whitespace-nowrap",
        presentation.className,
        className,
      )}
    >
      {presentation.label}
    </span>
  )
}
