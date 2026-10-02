import { LoaderCircle, Save, X } from "lucide-react"
import { type FormEvent, useState } from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ApiError, api } from "@/lib/api-client"
import type { Host, UpdateHostInput } from "@/lib/api-types"

export interface HostEditFormProps {
  host: Host
  onSaved: () => Promise<void> | void
  onClose: () => void
}

export function HostEditForm({ host, onSaved, onClose }: HostEditFormProps) {
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    const data = new FormData(form)
    const password = String(data.get("password") ?? "")
    const input: UpdateHostInput = {
      label: String(data.get("label") ?? "").trim() || null,
      ip: String(data.get("ip") ?? "").trim(),
    }
    if (password) input.password = password

    setIsSubmitting(true)
    setError(null)
    try {
      await api.updateHost(host.id, input)
      await onSaved()
      onClose()
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Не удалось обновить хост.")
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <form className="border-t bg-primary/[0.025] p-4 sm:p-5" onSubmit={handleSubmit}>
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h3 className="text-sm font-semibold">Редактирование хоста</h3>
          <p className="mt-1 font-mono text-xs text-muted-foreground">ID {host.id} · {host.username}</p>
        </div>
        <Button type="button" variant="ghost" size="icon" onClick={onClose} aria-label="Закрыть форму редактирования">
          <X aria-hidden="true" className="size-4" />
        </Button>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <label className="grid gap-1.5 text-xs font-medium">
          Название
          <Input name="label" maxLength={255} defaultValue={host.label ?? ""} placeholder="Production" />
        </label>
        <label className="grid gap-1.5 text-xs font-medium">
          IP-адрес
          <Input name="ip" inputMode="decimal" defaultValue={host.ip} required />
        </label>
        <label className="grid gap-1.5 text-xs font-medium">
          Новый пароль
          <Input name="password" type="password" autoComplete="new-password" placeholder="Оставьте пустым без изменений" />
        </label>
      </div>

      {error ? <p className="mt-3 text-sm text-destructive" role="alert">{error}</p> : null}

      <div className="mt-4 flex justify-end">
        <Button type="submit" size="sm" disabled={isSubmitting}>
          {isSubmitting ? <LoaderCircle aria-hidden="true" className="size-4 animate-spin" /> : <Save aria-hidden="true" className="size-4" />}
          {isSubmitting ? "Сохраняем…" : "Сохранить"}
        </Button>
      </div>
    </form>
  )
}
