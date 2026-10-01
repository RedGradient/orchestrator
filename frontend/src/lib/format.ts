export function formatDateTime(value: string | null): string {
  if (!value) {
    return "—"
  }

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }

  return new Intl.DateTimeFormat("ru-RU", {
    dateStyle: "medium",
    timeStyle: "medium",
  }).format(date)
}

export function durationMs(startedAt: string | null, finishedAt: string | null): number | null {
  if (!startedAt) {
    return null
  }

  const start = new Date(startedAt).getTime()
  const finish = finishedAt ? new Date(finishedAt).getTime() : Date.now()
  if (!Number.isFinite(start) || !Number.isFinite(finish) || finish < start) {
    return null
  }
  return finish - start
}

export function formatDuration(milliseconds: number | null): string {
  if (milliseconds === null) {
    return "—"
  }
  if (milliseconds < 1000) {
    return `${milliseconds} мс`
  }

  const seconds = Math.floor(milliseconds / 1000)
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const remainder = seconds % 60
  if (hours > 0) {
    return `${hours} ч ${minutes} мин ${remainder} с`
  }
  if (minutes > 0) {
    return `${minutes} мин ${remainder} с`
  }
  return `${remainder} с`
}

export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) {
    return "—"
  }
  const units = ["Б", "КБ", "МБ", "ГБ", "ТБ"]
  let value = bytes
  let unitIndex = 0
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024
    unitIndex += 1
  }
  return `${new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 1 }).format(value)} ${units[unitIndex]}`
}
