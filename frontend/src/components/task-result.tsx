import { Check, X } from "lucide-react"
import type { ReactNode } from "react"

import type { Command } from "@/lib/api-types"
import { formatBytes } from "@/lib/format"

interface TaskResultProps {
  command: Command
  result: Record<string, unknown>
}

function record(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null
}

function records(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value) ? value.map(record).filter((item) => item !== null) : []
}

function StatusValue({ value }: { value: unknown }) {
  const success = value === true
  return (
    <span className={success ? "inline-flex items-center gap-1 text-success" : "inline-flex items-center gap-1 text-destructive"}>
      {success ? <Check aria-hidden="true" className="size-3.5" /> : <X aria-hidden="true" className="size-3.5" />}
      {success ? "Готово" : "Ошибка"}
    </span>
  )
}

function PortsResult({ result }: { result: Record<string, unknown> }) {
  const ports = records(result.ports)
  if (ports.length === 0) {
    return <p className="text-sm text-muted-foreground">Доступных извне портов не найдено.</p>
  }
  return (
    <div className="overflow-x-auto rounded-md border">
      <table className="w-full min-w-[620px] text-left text-sm">
        <thead className="bg-muted/70 text-xs text-muted-foreground">
          <tr>
            <th className="px-3 py-2 font-medium">Порт</th>
            <th className="px-3 py-2 font-medium">Сервис</th>
            <th className="px-3 py-2 font-medium">Docker</th>
            <th className="px-3 py-2 font-medium">Рекомендация</th>
          </tr>
        </thead>
        <tbody className="divide-y">
          {ports.map((port, index) => (
            <tr key={`${String(port.port)}:${String(port.service)}:${index}`}>
              <td className="px-3 py-2 font-mono">{String(port.port ?? "—")}</td>
              <td className="px-3 py-2">{String(port.service ?? "—")}</td>
              <td className="px-3 py-2">{port.is_docker ? "Да" : "Нет"}</td>
              <td className="px-3 py-2">
                <span className="font-medium">{String(port.should_close ?? "unknown")}</span>
                {port.reason ? <span className="mt-0.5 block text-xs text-muted-foreground">{String(port.reason)}</span> : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function DockerResult({ result }: { result: Record<string, unknown> }) {
  const rows = [
    ["Контейнеры", result.deleted_containers],
    ["Volumes", result.deleted_volumes],
    ["Сети", result.deleted_networks],
    ["Образы", result.deleted_images],
    ["Build cache", result.deleted_build_cache_objects],
  ] as const
  return (
    <div>
      <p className="mb-3 text-sm">
        Освобождено: <strong>{String(result.disk_space_reclaimed ?? "0B")}</strong>
      </p>
      <dl className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
        {rows.map(([label, value]) => (
          <div key={label} className="rounded-md border bg-muted/20 p-3">
            <dt className="text-xs text-muted-foreground">{label}</dt>
            <dd className="mt-1 text-lg font-semibold">{Array.isArray(value) ? value.length : 0}</dd>
          </div>
        ))}
      </dl>
    </div>
  )
}

function BackupResult({ result }: { result: Record<string, unknown> }) {
  const containers = records(result.containers)
  return (
    <div>
      <p className="mb-3 text-sm text-muted-foreground">
        Создано dump-файлов: <strong className="text-foreground">{containers.length}</strong>
      </p>
      {containers.length > 0 ? (
        <ul className="divide-y rounded-md border">
          {containers.map((item, index) => (
            <li key={`${String(item.container)}:${index}`} className="flex flex-wrap justify-between gap-2 px-3 py-2 text-sm">
              <span><strong>{String(item.container ?? "—")}</strong> / {String(item.db_name ?? "—")}</span>
              <span className="text-muted-foreground">{formatBytes(Number(item.size_bytes))}</span>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  )
}

function SwapResult({ result }: { result: Record<string, unknown> }) {
  const info = record(result.swap_info)
  return (
    <dl className="grid gap-3 sm:grid-cols-3">
      <Metric label="Создан" value={result.created ? "Да" : "Нет"} />
      <Metric label="Активен" value={info?.is_active ? "Да" : "Нет"} />
      <Metric label="Размер" value={info ? formatBytes(Number(info.total_swap_size_bytes)) : "—"} />
    </dl>
  )
}

function LogsResult({ result }: { result: Record<string, unknown> }) {
  const items: Array<[string, Record<string, unknown> | null]> = [
    ["Logrotate", record(result.logrotate)],
    ["Fail2ban", record(result.fail2ban)],
    ["Journald", record(result.journald)],
    ["Fail2ban config", record(result.fail2ban_config)],
    ["Docker daemon", record(result.dockerd)],
  ]
  return (
    <div>
      <p className="mb-3 text-sm">
        Освобождено: <strong>{formatBytes(Number(result.freed_bytes ?? 0))}</strong>
      </p>
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {items.map(([label, item]) => (
          <div key={label} className="rounded-md border bg-muted/20 p-3 text-sm">
            <p className="mb-1 text-xs text-muted-foreground">{label}</p>
            {item ? <StatusValue value={item.success} /> : <span>Нет данных</span>}
            {item?.error ? <p className="mt-1 text-xs text-destructive">{String(item.error)}</p> : null}
          </div>
        ))}
      </div>
    </div>
  )
}

function Metric({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="rounded-md border bg-muted/20 p-3">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-1 font-medium">{value}</dd>
    </div>
  )
}

export function TaskResult({ command, result }: TaskResultProps) {
  if (command === "ports") return <PortsResult result={result} />
  if (command === "docker_cleanup") return <DockerResult result={result} />
  if (command === "postgres_backup") return <BackupResult result={result} />
  if (command === "create_swap") return <SwapResult result={result} />
  if (command === "logs_cleanup") return <LogsResult result={result} />

  return (
    <pre className="max-h-80 overflow-auto rounded-md border bg-muted/40 p-3 text-xs">
      {JSON.stringify(result, null, 2)}
    </pre>
  )
}
