import type {
  ApiErrorPayload,
  ApiValidationIssue,
  CheckHistoryItem,
  CheckResult,
  CreateOperationInput,
  Host,
  Operation,
  OperationAccepted,
  OperationHistoryFilters,
  OperationHistoryPage,
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

const fieldLabels: Record<string, string> = {
  actions: "Действия",
  days: "Период",
  host_ids: "Хосты",
  ip: "IP-адрес",
  label: "Название",
  page: "Страница",
  page_size: "Размер страницы",
  password: "Пароль",
  query: "Поисковый запрос",
  status_group: "Статус",
  url: "Адрес сайта",
  username: "Пользователь",
}

function validationMessage(issue: ApiValidationIssue): string {
  const fieldKey = [...(issue.loc ?? [])].reverse().find((part) => typeof part === "string")
  const field = fieldKey ? fieldLabels[fieldKey] ?? fieldKey : "Значение"

  switch (issue.type) {
    case "missing":
      return `Заполните поле «${field}»`
    case "string_too_short":
      return `Поле «${field}» не должно быть пустым`
    case "string_too_long":
      return `Поле «${field}» содержит слишком много символов`
    case "ip_v4_address":
      return "Укажите корректный IPv4-адрес"
    case "url_parsing":
    case "url_syntax_violation":
      return "Укажите корректный адрес сайта"
    case "greater_than_equal":
    case "less_than_equal":
    case "int_parsing":
      return `Укажите корректное значение поля «${field}»`
    case "too_short":
      return `Выберите хотя бы одно значение в поле «${field}»`
    default:
      return issue.msg && /[А-Яа-яЁё]/.test(issue.msg)
        ? issue.msg
        : `Проверьте значение поля «${field}»`
  }
}

function statusErrorMessage(status: number): string {
  switch (status) {
    case 400:
      return "Сервер не смог обработать запрос."
    case 401:
      return "Для выполнения запроса требуется авторизация."
    case 403:
      return "Недостаточно прав для выполнения запроса."
    case 404:
      return "Запрашиваемые данные не найдены."
    case 409:
      return "Запрос конфликтует с текущим состоянием данных."
    case 422:
      return "Проверьте введённые данные."
    default:
      return status >= 500
        ? "На сервере произошла ошибка. Повторите попытку позже."
        : `Запрос завершился с кодом ${status}.`
  }
}

function errorMessage(payload: ApiErrorPayload | null, status: number): string {
  if (typeof payload?.detail === "string") {
    return /[А-Яа-яЁё]/.test(payload.detail) ? payload.detail : statusErrorMessage(status)
  }

  if (Array.isArray(payload?.detail)) {
    const messages = payload.detail.map(validationMessage)
    if (messages.length > 0) {
      return messages.join(". ")
    }
  }

  return statusErrorMessage(status)
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
      errorMessage(payload as ApiErrorPayload | null, response.status),
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
  listOperations: (filters: OperationHistoryFilters, signal?: AbortSignal) => {
    const params = new URLSearchParams({ page: String(filters.page ?? 1) })
    if (filters.query) params.set("query", filters.query)
    if (filters.statusGroup) params.set("status_group", filters.statusGroup)
    if (filters.days) params.set("days", String(filters.days))
    return request<OperationHistoryPage>(`/api/operations?${params}`, { signal })
  },
  getOperation: (operationId: number) =>
    request<Operation>(`/api/operations/${operationId}`),
  cancelOperation: (operationId: number) =>
    request<Operation>(`/api/operations/${operationId}/cancel`, jsonRequest("POST")),
}
