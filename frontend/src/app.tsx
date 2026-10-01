import { ServerCog } from "lucide-react"
import { Link, Navigate, Route, Routes } from "react-router-dom"

import { Button } from "@/components/ui/button"

function FoundationPage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-5xl items-center px-6 py-16">
      <section className="w-full rounded-xl border bg-card p-8 shadow-sm">
        <div className="mb-6 flex size-11 items-center justify-center rounded-lg bg-primary text-primary-foreground">
          <ServerCog aria-hidden="true" className="size-5" />
        </div>
        <p className="mb-2 text-sm font-medium text-primary">Orchestrator</p>
        <h1 className="text-3xl font-semibold tracking-tight">Управление VPS-операциями</h1>
        <p className="mt-3 max-w-2xl text-muted-foreground">
          Основа нового интерфейса готова. Выбор хостов, действий и мониторинг операций будут
          добавлены на следующих этапах.
        </p>
        <Button asChild className="mt-7">
          <Link to="/">Открыть действия</Link>
        </Button>
      </section>
    </main>
  )
}

export function App() {
  return (
    <Routes>
      <Route path="/" element={<FoundationPage />} />
      <Route path="/operations/:operationId" element={<FoundationPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
