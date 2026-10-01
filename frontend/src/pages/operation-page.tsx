import { useParams } from "react-router-dom"

import { PageHeader } from "@/components/page-header"
import { StatePanel } from "@/components/state-panel"

export function OperationPage() {
  const { operationId } = useParams()

  return (
    <main>
      <PageHeader
        eyebrow="Операция"
        title={operationId ? `Operation #${operationId}` : "Operation"}
        description="Прогресс и задачи операции будут подключены на этапе realtime-мониторинга."
      />
      <StatePanel
        className="mt-7"
        kind="loading"
        title="Экран операции подготовлен"
        description="REST snapshot и SSE будут подключены на следующем функциональном этапе."
      />
    </main>
  )
}
