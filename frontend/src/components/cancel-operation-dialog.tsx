import { LoaderCircle, TriangleAlert } from "lucide-react"

import { Button } from "@/components/ui/button"

export interface CancelOperationDialogProps {
  open: boolean
  running: number
  queued: number
  pending: number
  isCancelling: boolean
  onConfirm: () => void
  onClose: () => void
}

export function CancelOperationDialog({
  open,
  running,
  queued,
  pending,
  isCancelling,
  onConfirm,
  onClose,
}: CancelOperationDialogProps) {
  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-foreground/25 p-4 backdrop-blur-[2px]" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && !isCancelling && onClose()}>
      <section className="w-full max-w-md rounded-lg border bg-card p-5 shadow-xl" role="alertdialog" aria-modal="true" aria-labelledby="cancel-title" aria-describedby="cancel-description">
        <span className="flex size-10 items-center justify-center rounded-full bg-warning/25 text-warning-foreground">
          <TriangleAlert aria-hidden="true" className="size-5" />
        </span>
        <h2 id="cancel-title" className="mt-4 text-lg font-semibold">Отменить операцию?</h2>
        <p id="cancel-description" className="mt-2 text-sm leading-6 text-muted-foreground">
          Задачи в очереди будут отменены. Для выполняющихся задач backend запросит отмену, но удалённая команда может завершиться не сразу.
        </p>
        <dl className="mt-4 grid grid-cols-3 gap-2 text-center">
          <DialogMetric label="Выполняются" value={running} />
          <DialogMetric label="В очереди" value={queued} />
          <DialogMetric label="Ожидают" value={pending} />
        </dl>
        <div className="mt-5 flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onClose} disabled={isCancelling}>Не отменять</Button>
          <Button type="button" variant="destructive" onClick={onConfirm} disabled={isCancelling}>
            {isCancelling ? <LoaderCircle aria-hidden="true" className="size-4 animate-spin" /> : null}
            {isCancelling ? "Отменяем…" : "Отменить операцию"}
          </Button>
        </div>
      </section>
    </div>
  )
}

function DialogMetric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md bg-muted p-2.5">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-1 font-semibold">{value}</dd>
    </div>
  )
}
