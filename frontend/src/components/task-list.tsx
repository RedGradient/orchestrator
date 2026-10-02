import { ChevronDown, CircleAlert, Server } from "lucide-react"

import { StatusBadge } from "@/components/status-badge"
import { TaskResult } from "@/components/task-result"
import { Card } from "@/components/ui/card"
import { actionTitle } from "@/lib/actions"
import type { OperationTask } from "@/lib/api-types"
import { durationMs, formatDateTime, formatDuration } from "@/lib/format"
import { hostConnectionName, hostDisplayName } from "@/lib/hosts"

export interface TaskListProps {
  tasks: OperationTask[]
}

export function TaskList({ tasks }: TaskListProps) {
  return (
    <Card className="mt-5 overflow-hidden">
      <div className="border-b p-4 sm:p-5">
        <h2 className="font-semibold">Задачи</h2>
        <p className="mt-1 text-sm text-muted-foreground">Всего задач: {tasks.length}</p>
      </div>

      <div className="divide-y">
        {tasks.map((task) => (
          <details key={task.id} className="group">
            <summary className="flex cursor-pointer list-none items-center gap-3 px-4 py-4 transition-colors hover:bg-muted/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring sm:px-5">
              <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground">
                <Server aria-hidden="true" className="size-4" />
              </span>
              <span className="min-w-0 flex-1 sm:grid sm:grid-cols-[minmax(160px,1fr)_minmax(160px,1fr)_100px] sm:items-center sm:gap-4">
                <span className="block min-w-0">
                  <span className="block truncate text-sm font-medium">
                    {hostDisplayName(task.host)}
                  </span>
                  <span className="block truncate font-mono text-xs text-muted-foreground">
                    {hostConnectionName(task.host)}
                  </span>
                </span>
                <span className="mt-1 block truncate text-sm sm:mt-0">
                  {actionTitle(task.command)}
                </span>
                <span className="mt-2 block font-mono text-xs text-muted-foreground sm:mt-0">
                  {formatDuration(durationMs(task.started_at, task.finished_at))}
                </span>
              </span>
              <StatusBadge status={task.status} className="hidden sm:inline-flex" />
              <ChevronDown
                aria-hidden="true"
                className="size-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-180"
              />
            </summary>

            <div className="border-t bg-muted/15 px-4 py-5 sm:px-5">
              <div className="mb-5 sm:hidden">
                <StatusBadge status={task.status} />
              </div>
              <dl className="grid gap-x-8 gap-y-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
                <TaskDetail label="Task ID" value={`#${task.id}`} mono />
                <TaskDetail label="Создана" value={formatDateTime(task.created_at)} />
                <TaskDetail label="Запущена" value={formatDateTime(task.started_at)} />
                <TaskDetail label="Завершена" value={formatDateTime(task.finished_at)} />
              </dl>

              {task.error ? (
                <div className="mt-5 flex items-start gap-2 rounded-md border border-destructive/25 bg-destructive/5 p-3 text-sm text-destructive" role="alert">
                  <CircleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
                  <pre className="whitespace-pre-wrap font-sans">{task.error}</pre>
                </div>
              ) : null}

              <div className="mt-5">
                <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Результат
                </h3>
                {task.result ? (
                  <TaskResult command={task.command} result={task.result} />
                ) : (
                  <p className="text-sm text-muted-foreground">Результат пока отсутствует.</p>
                )}
              </div>

              {Object.keys(task.parameters).length > 0 ? (
                <details className="mt-5 text-sm">
                  <summary className="cursor-pointer font-medium text-muted-foreground hover:text-foreground">
                    Входные параметры
                  </summary>
                  <pre className="mt-2 max-h-52 overflow-auto rounded-md border bg-background p-3 text-xs">
                    {JSON.stringify(task.parameters, null, 2)}
                  </pre>
                </details>
              ) : null}
            </div>
          </details>
        ))}
      </div>
    </Card>
  )
}

function TaskDetail({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className={mono ? "mt-0.5 font-mono text-xs" : "mt-0.5"}>{value}</dd>
    </div>
  )
}
