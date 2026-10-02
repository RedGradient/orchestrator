import type { Command } from "@/lib/api-types"

export interface ActionDefinition {
  command: Command
  title: string
  description: string
}

export const actions: ActionDefinition[] = [
  {
    command: "docker_cleanup",
    title: "Docker Cleanup",
    description: "Удаляет неиспользуемые контейнеры, образы, сети, volumes и build cache.",
  },
  {
    command: "postgres_backup",
    title: "Postgres Backup",
    description: "Создаёт dump баз PostgreSQL из запущенных контейнеров на хосте.",
  },
  {
    command: "create_swap",
    title: "Create SWAP",
    description: "Подбирает размер, создаёт SWAP-файл и включает его после перезагрузки.",
  },
  {
    command: "logs_cleanup",
    title: "Logs Cleanup",
    description: "Настраивает ротацию системных логов и освобождает дисковое пространство.",
  },
  {
    command: "ports",
    title: "Ports Checker",
    description: "Проверяет доступные извне порты и формирует рекомендации по безопасности.",
  },
]

export function actionTitle(command: Command): string {
  return actions.find((action) => action.command === command)?.title ?? command
}
