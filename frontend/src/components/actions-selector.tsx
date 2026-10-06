import { Box, DatabaseBackup, Globe2, HardDrive, ListRestart, ScanSearch, ShieldCheck, Trash2 } from "lucide-react"

import { Card } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { actions } from "@/lib/actions"
import type { Command } from "@/lib/api-types"
import { cn } from "@/lib/utils"

const actionIcons = {
  site_check: Globe2,
  overlay2_analyze: ScanSearch,
  overlay2_cleanup: Trash2,
  docker_cleanup: Box,
  postgres_backup: DatabaseBackup,
  create_swap: HardDrive,
  logs_cleanup: ListRestart,
  ports: ShieldCheck,
} satisfies Record<Command, typeof Box>

export interface ActionsSelectorProps {
  selectedActions: ReadonlySet<Command>
  onSelectionChange: (selected: Set<Command>) => void
  disabled?: boolean
}

export function ActionsSelector({
  selectedActions,
  onSelectionChange,
  disabled = false,
}: ActionsSelectorProps) {
  function toggleAction(command: Command) {
    const next = new Set(selectedActions)
    if (next.has(command)) {
      next.delete(command)
    } else {
      next.add(command)
    }
    onSelectionChange(next)
  }

  function toggleAll() {
    onSelectionChange(selectedActions.size === actions.length ? new Set() : new Set(actions.map((action) => action.command)))
  }

  return (
    <Card className="overflow-hidden">
      <div className="flex items-start justify-between gap-4 border-b p-4 sm:p-5">
        <div>
          <h2 className="font-semibold">Действия</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Выбрано {selectedActions.size} из {actions.length}
          </p>
        </div>
        <button
          type="button"
          className="text-sm font-medium text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          onClick={toggleAll}
          disabled={disabled}
        >
          {selectedActions.size === actions.length ? "Снять все" : "Выбрать все"}
        </button>
      </div>

      <ul className="divide-y" aria-label="Доступные действия">
        {actions.map((action) => {
          const Icon = actionIcons[action.command]
          const isSelected = selectedActions.has(action.command)
          return (
            <li key={action.command}>
              <label
                className={cn(
                  "flex cursor-pointer items-start gap-3 px-4 py-4 transition-colors hover:bg-muted/50 sm:px-5",
                  isSelected && "bg-primary/[0.045]",
                )}
              >
                <Checkbox
                  checked={isSelected}
                  onChange={() => toggleAction(action.command)}
                  aria-label={`Выбрать действие ${action.title}`}
                  className="mt-1"
                  disabled={disabled}
                />
                <span
                  className={cn(
                    "flex size-9 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground",
                    isSelected && "bg-primary/10 text-primary",
                  )}
                >
                  <Icon aria-hidden="true" className="size-4.5" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="text-sm font-medium">
                    {action.title}
                    {action.experimental ? (
                      <span className="ml-1.5 font-normal text-muted-foreground">(экспериментальное)</span>
                    ) : null}
                  </span>
                  <span className="mt-1 block text-sm leading-5 text-muted-foreground">
                    {action.description}
                  </span>
                  <code className="mt-2 block text-xs text-muted-foreground">{action.command}</code>
                </span>
              </label>
            </li>
          )
        })}
      </ul>
    </Card>
  )
}
