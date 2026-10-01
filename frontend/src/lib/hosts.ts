import type { Host } from "@/lib/api-types"

export function hostDisplayName(host: Host): string {
  return host.label || `${host.username}@${host.ip}`
}

export function hostConnectionName(host: Host): string {
  return `${host.username}@${host.ip}`
}
