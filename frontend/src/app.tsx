import { Navigate, Route, Routes } from "react-router-dom"

import { AppShell } from "@/components/app-shell"
import { ActionsPage } from "@/pages/actions-page"
import { OperationPage } from "@/pages/operation-page"
import { OperationsHistoryPage } from "@/pages/operations-history-page"

export function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<ActionsPage />} />
        <Route path="operations" element={<OperationsHistoryPage />} />
        <Route path="operations/:operationId" element={<OperationPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
