import { actions } from "@/lib/actions"
import type { Command } from "@/lib/api-types"

const storageKey = "orchestrator.action-selection.v1"
const knownCommands = new Set<Command>(actions.map((action) => action.command))

interface StoredSelection {
  hostIds: number[]
  commands: Command[]
}

export function loadActionSelection(): {
  hostIds: Set<number>
  commands: Set<Command>
} {
  try {
    const raw = sessionStorage.getItem(storageKey)
    if (!raw) return { hostIds: new Set(), commands: new Set() }

    const parsed = JSON.parse(raw) as Partial<StoredSelection>
    const hostIds = Array.isArray(parsed.hostIds)
      ? parsed.hostIds.filter((id) => Number.isSafeInteger(id) && id > 0)
      : []
    const commands = Array.isArray(parsed.commands)
      ? parsed.commands.filter((command): command is Command => knownCommands.has(command))
      : []

    return { hostIds: new Set(hostIds), commands: new Set(commands) }
  } catch {
    return { hostIds: new Set(), commands: new Set() }
  }
}

export function saveActionSelection(
  hostIds: ReadonlySet<number>,
  commands: ReadonlySet<Command>,
): void {
  const selection: StoredSelection = {
    hostIds: [...hostIds],
    commands: [...commands],
  }
  try {
    sessionStorage.setItem(storageKey, JSON.stringify(selection))
  } catch {
    // Storage может быть отключён политиками браузера; выбор всё равно останется в React state.
  }
}
