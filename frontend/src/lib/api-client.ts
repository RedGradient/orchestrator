import type {
  ApiErrorPayload,
  CheckHistoryItem,
  CheckResult,
  CreateOperationInput,
  Host,
  Operation,
  OperationAccepted,
  RegisterHostInput,
  RegisterHostResponse,
  UpdateHostInput,
} from "@/lib/api-types"

export class ApiError extends Error {
  readonly status: number
  readonly payload: unknown

  constructor(message: string, status: number, payload: unknown) {
    super(message)
    this.name = "ApiError"
    this.status = status
    this.payload = payload
  }
}

function errorMessage(payload: ApiErrorPayload | null, fallback: string): string {
  if (typeof payload?.detail === "string") {
    return payload.detail
  }

  if (Array.isArray(payload?.detail)) {
    const messages = payload.detail.flatMap((issue) => (issue.msg ? [issue.msg] : []))
    if (messages.length > 0) {
      return messages.join(". ")
    }
  }

  return fallback
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      Accept: "application/json",
      ...init?.headers,
    },
  })

  const payload = (await response.json().catch(() => null)) as T | ApiErrorPayload | null
  if (!response.ok) {
    throw new ApiError(
      errorMessage(payload as ApiErrorPayload | null, `Запрос завершился с кодом ${response.status}.`),
      response.status,
      payload,
    )
  }

  return payload as T
}

function jsonRequest(method: "POST", body?: unknown): RequestInit {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  }
}

export const api = {
  runSiteCheck: (url: string) =>
    request<CheckResult>("/api/check", jsonRequest("POST", { url })),
  listSiteChecks: (signal?: AbortSignal) =>
    request<CheckHistoryItem[]>("/api/checks", { signal }),
  listHosts: (signal?: AbortSignal) => request<Host[]>("/api/hosts", { signal }),
  registerHost: (input: RegisterHostInput) =>
    request<RegisterHostResponse>("/api/host", jsonRequest("POST", input)),
  updateHost: (hostId: number, input: UpdateHostInput) =>
    request<Host>(`/api/hosts/${hostId}`, {
      ...jsonRequest("POST", input),
      method: "PATCH",
    }),
  deleteHost: (hostId: number) =>
    request<void>(`/api/hosts/${hostId}`, { method: "DELETE" }),
  createOperation: (input: CreateOperationInput) =>
    request<OperationAccepted>("/api/operations", jsonRequest("POST", input)),
  getOperation: (operationId: number) =>
    request<Operation>(`/api/operations/${operationId}`),
  cancelOperation: (operationId: number) =>
    request<Operation>(`/api/operations/${operationId}/cancel`, jsonRequest("POST")),
}
