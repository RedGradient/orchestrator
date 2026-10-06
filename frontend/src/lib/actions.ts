import type { Command } from "@/lib/api-types"

export interface ActionDefinition {
  command: Command
  title: string
  description: string
  experimental?: boolean
}

export const actions: ActionDefinition[] = [
  {
    command: "site_check",
    title: "Site Check",
    description: "Проверяет доступность сайта, HTTPS-сертификат, robots.txt и sitemap.xml.",
  },
  {
    command: "overlay2_analyze",
    title: "Overlay2 Analyze",
    description: "Анализирует физические висячие слои Docker overlay2 без изменений на хосте.",
    experimental: true,
  },
  {
    command: "overlay2_cleanup",
    title: "Overlay2 Cleanup",
    description: "Удаляет подтверждённые висячие слои Docker overlay2 после повторной проверки.",
    experimental: true,
  },
  {
    command: "docker_cleanup",
    title: "Docker Cleanup",
    description: "Останавливает и удаляет все Docker-контейнеры, затем очищает volumes, сети, образы и build cache.",
  },
  {
    command: "postgres_backup",
    title: "Postgres Backup",
    description: "Находит PostgreSQL-контейнеры, создаёт дампы их баз и скачивает их на сервер Orchestrator.",
  },
  {
    command: "create_swap",
    title: "Create SWAP",
    description: "Проверяет текущую SWAP и при необходимости создаёт и подключает swap-файл.",
  },
  {
    command: "logs_cleanup",
    title: "Logs Cleanup",
    description: "Устанавливает и настраивает logrotate и Fail2ban, ограничивает журналы systemd и Docker, очищает системные логи.",
  },
  {
    command: "ports",
    title: "Ports Checker",
    description: "Находит открытые TCP-порты, включая порты Docker, и формирует рекомендации по ограничению доступа.",
  },
]

export function actionTitle(command: Command): string {
  return actions.find((action) => action.command === command)?.title ?? command
}
