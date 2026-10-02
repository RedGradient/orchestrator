import { LoaderCircle, Trash2 } from "lucide-react"
import { useEffect, useRef } from "react"

import { Button } from "@/components/ui/button"
import type { Host } from "@/lib/api-types"
import { hostDisplayName } from "@/lib/hosts"

export interface DeleteHostDialogProps {
  host: Host | null
  isDeleting: boolean
  error: string | null
  onConfirm: () => void
  onClose: () => void
}

export function DeleteHostDialog({ host, isDeleting, error, onConfirm, onClose }: DeleteHostDialogProps) {
  const cancelButtonRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (host) cancelButtonRef.current?.focus()
  }, [host])

  if (!host) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-foreground/25 p-4 backdrop-blur-[2px]" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && !isDeleting && onClose()} onKeyDown={(event) => event.key === "Escape" && !isDeleting && onClose()}>
      <section className="w-full max-w-md rounded-lg border bg-card p-5 shadow-xl" role="alertdialog" aria-modal="true" aria-labelledby="delete-host-title" aria-describedby="delete-host-description">
        <span className="flex size-10 items-center justify-center rounded-full bg-destructive/10 text-destructive">
          <Trash2 aria-hidden="true" className="size-5" />
        </span>
        <h2 id="delete-host-title" className="mt-4 text-lg font-semibold">Удалить {hostDisplayName(host)}?</h2>
        <p id="delete-host-description" className="mt-2 text-sm leading-6 text-muted-foreground">
          Хост исчезнет из списка и больше не будет доступен для новых операций. История уже выполненных задач сохранится.
        </p>
        {error ? <p className="mt-3 text-sm text-destructive" role="alert">{error}</p> : null}
        <div className="mt-5 flex justify-end gap-2">
          <Button ref={cancelButtonRef} type="button" variant="outline" onClick={onClose} disabled={isDeleting}>Не удалять</Button>
          <Button type="button" variant="destructive" onClick={onConfirm} disabled={isDeleting}>
            {isDeleting ? <LoaderCircle aria-hidden="true" className="size-4 animate-spin" /> : <Trash2 aria-hidden="true" className="size-4" />}
            {isDeleting ? "Удаляем…" : "Удалить хост"}
          </Button>
        </div>
      </section>
    </div>
  )
}
