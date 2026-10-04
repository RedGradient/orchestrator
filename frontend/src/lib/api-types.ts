export type OperationStatus =
  | "pending"
  | "queued"
  | "running"
  | "succeeded"
  | "failed"
  | "partial_failure"
  | "cancelled"

export type TaskStatus =
  | "pending"
  | "queued"
  | "running"
  | "succeeded"
  | "failed"
  | "timeout"
  | "cancellation_requested"
  | "cancelled"

export type Command =
  | "site_check"
  | "overlay2_analyze"
  | "overlay2_cleanup"
  | "docker_cleanup"
  | "postgres_backup"
  | "create_swap"
  | "logs_cleanup"
  | "ports"

export interface Host {
  id: number
  label: string | null
  site_url: string | null
  ip: string
  username: string
  created_at: string
}

export interface RegisterHostInput {
  label?: string | null
  site_url?: string | null
  ip: string
  username: string
  password: string
}

export interface RegisterHostResponse {
  id: number
  label: string | null
  site_url: string | null
  ip: string
  username: string
}

export interface UpdateHostInput {
  label: string | null
  site_url: string | null
  ip: string
  password?: string
}

export interface OperationActionInput {
  command: Command
  parameters: Record<string, unknown>
}

export interface CreateOperationInput {
  host_ids: number[]
  actions: OperationActionInput[]
}

export interface OperationAccepted {
  operation_id: number
  status: OperationStatus
}

export interface OperationProgress {
  total: number
  pending: number
  queued: number
  running: number
  succeeded: number
  failed: number
  timeout: number
  cancellation_requested: number
  cancelled: number
}

export interface OperationTask {
  id: number
  host: Host
  command: Command
  parameters: Record<string, unknown>
  status: TaskStatus
  result: Record<string, unknown> | null
  error: string | null
  created_at: string
  started_at: string | null
  finished_at: string | null
}

export interface Operation {
  id: number
  status: OperationStatus
  progress: OperationProgress
  created_at: string
  started_at: string | null
  finished_at: string | null
  tasks: OperationTask[]
}

export interface OperationHistoryItem {
  id: number
  status: OperationStatus
  progress: OperationProgress
  hosts: Host[]
  actions: Command[]
  created_at: string
  started_at: string | null
  finished_at: string | null
}

export interface OperationHistoryPage {
  items: OperationHistoryItem[]
  total: number
  page: number
  page_size: number
  has_more: boolean
}

export interface OperationHistoryFilters {
  page?: number
  query?: string
  statusGroup?: "active" | "succeeded" | "failed"
  days?: 1 | 7 | 30
}

export interface ApiValidationIssue {
  loc?: Array<string | number>
  msg?: string
  type?: string
}

export interface ApiErrorPayload {
  detail?: string | ApiValidationIssue[]
}

export interface HttpCheckResult {
  ok: boolean
  status_code: number | null
  response_time_ms: number | null
  error: string | null
}

export interface SslCheckResult {
  ok: boolean
  version: string | null
  issuer: string | null
  expires_at: string | null
  days_remaining: number | null
  error: string | null
}

export interface FileCheckResult {
  available: boolean
  status_code: number | null
  valid: boolean | null
  errors: string[]
  warnings: string[]
  error: string | null
}

export interface RobotsCheckResult extends FileCheckResult {
  sitemaps: string[]
}

export interface SitemapCheckResult extends FileCheckResult {
  url_count: number | null
}

export interface CheckResult {
  url: string
  domain: string | null
  http: HttpCheckResult | null
  ssl: SslCheckResult | null
  robots: RobotsCheckResult | null
  sitemap: SitemapCheckResult | null
}
