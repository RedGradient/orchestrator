import { ArrowLeft, Radio, RefreshCw, WifiOff } from "lucide-react"
import { Link, useNavigate, useParams } from "react-router-dom"

import { OperationSummary } from "@/components/operation-summary"
import { PageHeader } from "@/components/page-header"
import { StatePanel } from "@/components/state-panel"
import { TaskList } from "@/components/task-list"
import { Button } from "@/components/ui/button"
import { isTerminalOperation, useOperation } from "@/hooks/use-operation"

export function OperationPage() {
  const params = useParams()
  const navigate = useNavigate()
  const parsedId = Number(params.operationId)
  const operationId = Number.isSafeInteger(parsedId) && parsedId > 0 ? parsedId : null
  const { operation, isLoading, error, realtimeState, refresh } = useOperation(operationId)

  if (operationId === null) {
    return (
      <main>
        <PageHeader eyebrow="Операция" title="Некорректный идентификатор" />
        <StatePanel
          className="mt-7"
          kind="error"
          title="Идентификатор операции должен быть положительным числом"
          description="Вернитесь в историю и выберите существующую операцию."
        >
          <Button asChild variant="outline" size="sm" className="mt-5">
            <Link to="/operations">Вернуться к истории</Link>
          </Button>
        </StatePanel>
      </main>
    )
  }

  if (isLoading && !operation) {
    return (
      <main>
        <PageHeader eyebrow="Операция" title={`Operation #${operationId}`} />
        <StatePanel
          className="mt-7"
          kind="loading"
          title="Загружаем операцию"
          description="Получаем актуальное состояние и список задач."
        />
      </main>
    )
  }

  if (!operation) {
    return (
      <main>
        <PageHeader eyebrow="Операция" title={`Operation #${operationId}`} />
        <StatePanel
          className="mt-7"
          kind="error"
          title="Не удалось открыть операцию"
          description={error ?? "Операция не найдена или временно недоступна."}
          actionLabel="Повторить"
          onAction={() => void refresh()}
        />
      </main>
    )
  }

  const terminal = isTerminalOperation(operation.status)

  function goBack() {
    if (window.history.length > 1) {
      navigate(-1)
      return
    }
    navigate("/operations")
  }

  return (
    <main>
      <button
        type="button"
        onClick={goBack}
        className="mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <ArrowLeft aria-hidden="true" className="size-4" />
        Назад
      </button>
      <PageHeader
        eyebrow="Операция"
        title={`Operation #${operation.id}`}
        description="REST snapshot — актуальное состояние операции. Изменения поступают через один realtime-канал."
        actions={
          <>
            <Button asChild variant="outline">
              <Link to="/">Новое действие</Link>
            </Button>
            <RealtimeIndicator state={realtimeState} terminal={terminal} />
          </>
        }
      />

      {error ? (
        <div className="mt-5 flex flex-wrap items-center justify-between gap-3 rounded-md border border-warning/40 bg-warning/10 px-4 py-3 text-sm text-warning-foreground" role="status">
          <span>{error} Показано последнее полученное состояние.</span>
          <Button type="button" size="sm" variant="outline" onClick={() => void refresh()}>
            <RefreshCw aria-hidden="true" className="size-4" />
            Обновить
          </Button>
        </div>
      ) : null}

      <OperationSummary operation={operation} />
      <TaskList tasks={operation.tasks} />
    </main>
  )
}

function RealtimeIndicator({ state, terminal }: { state: string; terminal: boolean }) {
  if (terminal) {
    return <span className="text-xs font-medium text-muted-foreground">Операция завершена</span>
  }
  const disconnected = state === "reconnecting"
  return (
    <span className={disconnected ? "inline-flex items-center gap-1.5 text-xs font-medium text-warning-foreground" : "inline-flex items-center gap-1.5 text-xs font-medium text-success"}>
      {disconnected ? <WifiOff aria-hidden="true" className="size-3.5" /> : <Radio aria-hidden="true" className="size-3.5" />}
      {disconnected ? "Переподключаемся…" : state === "connected" ? "Realtime подключён" : "Подключаем realtime…"}
    </span>
  )
}
