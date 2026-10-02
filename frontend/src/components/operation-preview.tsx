import { AlertCircle, ArrowRight, LoaderCircle, Play, Rows3 } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import type { ActionDefinition } from "@/lib/actions"
import type { Host } from "@/lib/api-types"
import { hostConnectionName, hostDisplayName } from "@/lib/hosts"

export interface OperationPreviewProps {
  hosts: Host[]
  actions: ActionDefinition[]
  isCreating: boolean
  error: string | null
  onCreate: () => void
}

export function OperationPreview({ hosts, actions, isCreating, error, onCreate }: OperationPreviewProps) {
  const taskCount = hosts.length * actions.length
  const canCreate = hosts.length > 0 && actions.length > 0 && !isCreating

  return (
    <Card className="mt-5 overflow-hidden">
      <div className="flex flex-col justify-between gap-5 border-b p-4 sm:flex-row sm:items-center sm:p-5">
        <div>
          <div className="flex items-center gap-2">
            <Rows3 aria-hidden="true" className="size-4 text-muted-foreground" />
            <h2 className="font-semibold">Preview операции</h2>
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
            <strong className="font-medium text-foreground">{hosts.length} хостов</strong>
            <span aria-hidden="true">·</span>
            <strong className="font-medium text-foreground">{actions.length} действий</strong>
            <ArrowRight aria-hidden="true" className="size-3.5" />
            <strong className="font-semibold text-primary">{taskCount} задач</strong>
          </div>
        </div>

        <Button type="button" size="lg" disabled={!canCreate} onClick={onCreate}>
          {isCreating ? (
            <LoaderCircle aria-hidden="true" className="size-4 animate-spin" />
          ) : (
            <Play aria-hidden="true" className="size-4" />
          )}
          {isCreating ? "Создаём операцию…" : "Запустить операцию"}
        </Button>
      </div>

      {error ? (
        <div className="flex items-start gap-2 border-b bg-destructive/5 px-4 py-3 text-sm text-destructive sm:px-5" role="alert">
          <AlertCircle aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          <span>{error}</span>
        </div>
      ) : null}

      {hosts.length === 0 || actions.length === 0 ? (
        <div className="px-4 py-10 text-center sm:px-5">
          <p className="text-sm font-medium">
            {hosts.length === 0 && actions.length === 0
              ? "Выберите хосты и действия"
              : hosts.length === 0
                ? "Выберите хотя бы один хост"
                : "Выберите хотя бы одно действие"}
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            Здесь появится точный список задач до запуска.
          </p>
        </div>
      ) : (
        <div className="max-h-[420px] overflow-auto">
          <table className="w-full min-w-[520px] border-collapse text-left text-sm">
            <thead className="sticky top-0 z-10 bg-muted/95 text-xs text-muted-foreground backdrop-blur">
              <tr>
                <th className="w-16 px-4 py-2.5 font-medium sm:px-5">№</th>
                <th className="px-4 py-2.5 font-medium sm:px-5">Хост</th>
                <th className="px-4 py-2.5 font-medium sm:px-5">Действие</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {hosts.flatMap((host, hostIndex) =>
                actions.map((action, actionIndex) => (
                  <tr key={`${host.id}:${action.command}`} className="hover:bg-muted/30">
                    <td className="px-4 py-3 font-mono text-xs text-muted-foreground sm:px-5">
                      {hostIndex * actions.length + actionIndex + 1}
                    </td>
                    <td className="px-4 py-3 sm:px-5">
                      <span className="block font-medium">{hostDisplayName(host)}</span>
                      {host.label ? (
                        <span className="mt-0.5 block font-mono text-xs text-muted-foreground">
                          {hostConnectionName(host)}
                        </span>
                      ) : null}
                    </td>
                    <td className="px-4 py-3 sm:px-5">
                      <span className="block font-medium">{action.title}</span>
                      <code className="mt-0.5 block text-xs text-muted-foreground">
                        {action.command}
                      </code>
                    </td>
                  </tr>
                )),
              )}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}
