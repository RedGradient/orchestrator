import { LoaderCircle, Plus, X } from "lucide-react"
import { type FormEvent, useState } from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ApiError, api } from "@/lib/api-client"

export interface HostRegistrationFormProps {
  onCreated: () => Promise<void> | void
  onClose: () => void
}

export function HostRegistrationForm({ onCreated, onClose }: HostRegistrationFormProps) {
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    const data = new FormData(form)
    const label = String(data.get("label") ?? "").trim()

    setIsSubmitting(true)
    setError(null)
    try {
      await api.registerHost({
        label: label || null,
        site_url: String(data.get("site_url") ?? "").trim() || null,
        ip: String(data.get("ip") ?? "").trim(),
        username: String(data.get("username") ?? "").trim(),
        password: String(data.get("password") ?? ""),
      })
      form.reset()
      await onCreated()
      onClose()
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Не удалось добавить хост.")
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <form className="border-b bg-muted/30 p-4 sm:p-5" onSubmit={handleSubmit}>
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h3 className="text-sm font-semibold">Новый хост</h3>
          <p className="mt-1 text-xs text-muted-foreground">
            Название необязательно. Данные подключения сохраняются на backend.
          </p>
        </div>
        <Button type="button" variant="ghost" size="icon" onClick={onClose} aria-label="Закрыть форму">
          <X aria-hidden="true" className="size-4" />
        </Button>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <label className="grid gap-1.5 text-xs font-medium">
          Название
          <Input name="label" maxLength={255} placeholder="Production" autoComplete="off" />
        </label>
        <label className="grid gap-1.5 text-xs font-medium">
          IP-адрес
          <Input name="ip" inputMode="decimal" placeholder="192.0.2.10" required />
        </label>
        <label className="grid gap-1.5 text-xs font-medium">
          Адрес сайта
          <Input name="site_url" inputMode="url" placeholder="example.com" autoComplete="url" />
        </label>
        <label className="grid gap-1.5 text-xs font-medium">
          Пользователь
          <Input name="username" placeholder="root" autoComplete="username" required />
        </label>
        <label className="grid gap-1.5 text-xs font-medium">
          Пароль
          <Input name="password" type="password" autoComplete="current-password" required />
        </label>
      </div>

      {error ? (
        <p className="mt-3 text-sm text-destructive" role="alert">
          {error}
        </p>
      ) : null}

      <div className="mt-4 flex justify-end">
        <Button type="submit" size="sm" disabled={isSubmitting}>
          {isSubmitting ? (
            <LoaderCircle aria-hidden="true" className="size-4 animate-spin" />
          ) : (
            <Plus aria-hidden="true" className="size-4" />
          )}
          {isSubmitting ? "Добавляем…" : "Добавить хост"}
        </Button>
      </div>
    </form>
  )
}
