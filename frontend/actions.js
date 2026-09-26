/** Каталог действий. Новое действие добавляется сюда и появляется в списке. */
export const ACTIONS = [
  {
    id: "docker_cleanup",
    title: "Docker Cleanup",
    description:
      "Останавливает контейнеры и удаляет volumes, networks, images и build cache. Показывает, сколько места освободилось.",
    apiCommand: "docker_cleanup",
  },
  {
    id: "postgres_backup",
    title: "Postgres Backup",
    description:
      "Создаёт dump баз из запущенных контейнеров PostgreSQL на хосте и скачивает файлы на сервер оркестратора.",
    apiCommand: "postgres_backup",
  },
  {
    id: "create_swap",
    title: "Create SWAP",
    description:
      "Подбирает размер SWAP по свободному месту на диске, удаляет старый SWAP, создаёт новый файл и включает его после перезагрузки.",
    apiCommand: "create_swap",
  },
];

const page = location.pathname;
const params = new URLSearchParams(location.search);

if (page === "/" || page.endsWith("/index.html")) {
  renderActionsCatalog();
} else if (page.endsWith("/action.html")) {
  initActionPage();
}

function renderActionsCatalog() {
  const list = document.querySelector("#actions-list");
  if (!list) {
    return;
  }

  list.replaceChildren();
  for (const action of ACTIONS) {
    const card = document.createElement("a");
    card.className = "action-card";
    card.href = `/action.html?id=${encodeURIComponent(action.id)}`;

    const title = document.createElement("h2");
    title.textContent = action.title;

    const description = document.createElement("p");
    description.textContent = action.description;

    const meta = document.createElement("span");
    meta.className = "action-card-meta";
    meta.textContent = "Открыть →";

    card.append(title, description, meta);
    list.append(card);
  }
}

function initActionPage() {
  const action = ACTIONS.find((item) => item.id === params.get("id"));
  if (!action) {
    location.replace("/");
    return;
  }

  document.title = `${action.title} — Orchestrator`;
  document.querySelector("#action-title").textContent = action.title;
  document.querySelector("#action-description").textContent = action.description;

  const hostsList = document.querySelector("#hosts-list");
  const hostsError = document.querySelector("#hosts-error");
  const runButton = document.querySelector("#run-action");
  const selectAllButton = document.querySelector("#select-all");
  const runSummary = document.querySelector("#run-summary");
  const runResults = document.querySelector("#run-results");
  const hostForm = document.querySelector("#host-form");
  const hostFormError = document.querySelector("#host-form-error");

  let hosts = [];
  const selected = new Set();
  const runState = new Map();

  selectAllButton.addEventListener("click", () => {
    const allSelected = hosts.length > 0 && hosts.every((host) => selected.has(host.id));
    selected.clear();
    if (!allSelected) {
      for (const host of hosts) {
        selected.add(host.id);
      }
    }
    renderHosts();
    syncRunButton();
  });

  runButton.addEventListener("click", async () => {
    const targets = hosts.filter((host) => selected.has(host.id));
    if (!targets.length) {
      return;
    }

    runButton.disabled = true;
    selectAllButton.disabled = true;
    hostsError.hidden = true;
    runResults.replaceChildren();
    runSummary.textContent = `Выполняется на ${targets.length} хост(ах)…`;

    for (const host of targets) {
      runState.set(host.id, { status: "running", error: null, result: null });
      renderHosts();
      appendRunCard(host, "running");

      try {
        const response = await fetch("/api/command", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            host_id: host.id,
            command: action.apiCommand,
          }),
        });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
          throw new Error(readApiError(payload, "Не удалось выполнить действие."));
        }
        runState.set(host.id, { status: "ok", error: null, result: payload });
        updateRunCard(host.id, "ok", payload);
      } catch (error) {
        const message = error instanceof Error ? error.message : "Ошибка выполнения.";
        runState.set(host.id, { status: "error", error: message, result: null });
        updateRunCard(host.id, "error", null, message);
      }
      renderHosts();
    }

    const failed = [...runState.values()].filter((item) => item.status === "error").length;
    const done = targets.length - failed;
    runSummary.textContent = failed
      ? `Готово: ${done} успешно, ${failed} с ошибкой.`
      : `Готово: все ${done} хост(а) обработаны.`;
    runButton.disabled = false;
    selectAllButton.disabled = false;
    syncRunButton();
  });

  hostForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    hostFormError.hidden = true;
    const submit = hostForm.querySelector("button[type='submit']");
    submit.disabled = true;

    try {
      const response = await fetch("/api/host", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ip: hostForm.ip.value.trim(),
          username: hostForm.username.value.trim(),
          password: hostForm.password.value,
        }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(readApiError(payload, "Не удалось сохранить хост."));
      }
      hostForm.reset();
      await loadHosts();
    } catch (error) {
      hostFormError.hidden = false;
      hostFormError.textContent =
        error instanceof Error ? error.message : "Не удалось сохранить хост.";
    } finally {
      submit.disabled = false;
    }
  });

  loadHosts();

  async function loadHosts() {
    hostsError.hidden = true;
    try {
      const response = await fetch("/api/hosts");
      if (!response.ok) {
        throw new Error("Не удалось загрузить хосты.");
      }
      hosts = await response.json();
      const known = new Set(hosts.map((host) => host.id));
      for (const id of [...selected]) {
        if (!known.has(id)) {
          selected.delete(id);
        }
      }
      renderHosts();
      syncRunButton();
    } catch (error) {
      hosts = [];
      hostsList.replaceChildren();
      hostsError.hidden = false;
      hostsError.textContent =
        error instanceof Error ? error.message : "Не удалось загрузить хосты.";
      syncRunButton();
    }
  }

  function renderHosts() {
    hostsList.replaceChildren();
    if (!hosts.length) {
      const empty = document.createElement("li");
      empty.className = "host-empty";
      empty.textContent = "Пока нет зарегистрированных хостов.";
      hostsList.append(empty);
      return;
    }

    for (const host of hosts) {
      const item = document.createElement("li");
      item.className = "host-item";

      const label = document.createElement("label");
      label.className = "host-label";

      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = selected.has(host.id);
      checkbox.addEventListener("change", () => {
        if (checkbox.checked) {
          selected.add(host.id);
        } else {
          selected.delete(host.id);
        }
        syncRunButton();
      });

      const body = document.createElement("div");
      body.className = "host-body";

      const name = document.createElement("strong");
      name.className = "host-name";
      name.textContent = host.username;

      const ip = document.createElement("span");
      ip.className = "host-ip";
      ip.textContent = host.ip;

      const meta = document.createElement("span");
      meta.className = "host-meta";
      meta.textContent = `добавлен ${formatDate(host.created_at)}`;

      body.append(name, ip, meta);

      const status = document.createElement("span");
      const state = runState.get(host.id);
      status.className = `host-status ${state?.status || "ready"}`;
      status.textContent = statusLabel(state?.status);

      label.append(checkbox, body);
      item.append(label, status);
      hostsList.append(item);
    }
  }

  function syncRunButton() {
    runButton.disabled = selected.size === 0;
  }

  function appendRunCard(host, status, payload = null, error = null) {
    const card = document.createElement("article");
    card.className = "card run-card";
    card.dataset.hostId = String(host.id);

    const head = document.createElement("div");
    head.className = "card-head";

    const heading = document.createElement("h2");
    heading.textContent = `${host.username}@${host.ip}`;

    const badge = document.createElement("span");
    badge.className = `badge ${badgeClass(status)}`;
    badge.textContent = statusLabel(status);

    head.append(heading, badge);
    card.append(head);

    const body = document.createElement("div");
    body.className = "run-card-body";
    if (status === "running") {
      body.textContent = "Команда выполняется…";
    } else if (error) {
      body.textContent = error;
    } else if (payload) {
      body.append(renderCommandResult(action.id, payload));
    }
    card.append(body);
    runResults.append(card);
  }

  function updateRunCard(hostId, status, payload = null, error = null) {
    const card = runResults.querySelector(`[data-host-id="${hostId}"]`);
    if (!card) {
      return;
    }
    const badge = card.querySelector(".badge");
    badge.className = `badge ${badgeClass(status)}`;
    badge.textContent = statusLabel(status);

    const body = card.querySelector(".run-card-body");
    body.replaceChildren();
    if (error) {
      body.textContent = error;
      return;
    }
    if (payload) {
      body.append(renderCommandResult(action.id, payload));
    }
  }
}

function renderCommandResult(actionId, payload) {
  if (actionId === "docker_cleanup") {
    return renderDockerCleanupResult(payload.result || payload);
  }
  if (actionId === "postgres_backup") {
    return renderPostgresBackupResult(payload.result || payload);
  }
  if (actionId === "create_swap") {
    return renderCreateSwapResult(payload.result || payload);
  }
  const pre = document.createElement("pre");
  pre.className = "result-json";
  pre.textContent = JSON.stringify(payload, null, 2);
  return pre;
}

function renderDockerCleanupResult(result) {
  const wrap = document.createElement("div");
  wrap.className = "cleanup-result";

  const rows = [
    ["Контейнеры", result.deleted_containers],
    ["Volumes", result.deleted_volumes],
    ["Networks", result.deleted_networks],
    ["Untagged images", result.untagged_images],
    ["Deleted images", result.deleted_images],
    ["Build cache", result.deleted_build_cache_objects],
  ];

  const list = document.createElement("dl");
  for (const [label, items] of rows) {
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.textContent = Array.isArray(items) ? String(items.length) : "0";
    list.append(dt, dd);
  }

  const space = document.createElement("p");
  space.className = "reclaimed";
  space.textContent = `Освобождено: ${result.disk_space_reclaimed || "0B"}`;

  wrap.append(list, space);
  return wrap;
}

function renderPostgresBackupResult(result) {
  const wrap = document.createElement("div");
  wrap.className = "cleanup-result";

  const dumps = Array.isArray(result)
    ? result
    : Array.isArray(result?.containers)
      ? result.containers
      : [];
  if (!dumps.length) {
    const empty = document.createElement("p");
    empty.textContent = "Контейнеры PostgreSQL не найдены, dump не создан.";
    wrap.append(empty);
    return wrap;
  }

  const list = document.createElement("dl");
  for (const item of dumps) {
    const dt = document.createElement("dt");
    dt.textContent = item.container || "container";
    const dd = document.createElement("dd");
    const size = formatByteSize(item.size_bytes);
    dd.textContent = `${item.db_name || "?"} · ${size}`;
    list.append(dt, dd);
  }

  const summary = document.createElement("p");
  summary.className = "reclaimed";
  summary.textContent = `Файлов: ${dumps.length}`;

  wrap.append(list, summary);
  return wrap;
}

function renderCreateSwapResult(result) {
  const wrap = document.createElement("div");
  wrap.className = "cleanup-result";

  if (!result?.created) {
    const empty = document.createElement("p");
    empty.textContent =
      "SWAP не создан: на диске недостаточно свободного места или заполнение ≥ 85%.";
    wrap.append(empty);
    return wrap;
  }

  const info = result.swap_info || {};
  const list = document.createElement("dl");

  const rows = [
    ["Активен", info.is_active ? "да" : "нет"],
    ["Размер SWAP", formatByteSize(info.total_swap_size_bytes)],
    ["Свободно на диске", formatByteSize(info.free_disk_space_bytes)],
  ];

  for (const [label, value] of rows) {
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.textContent = value;
    list.append(dt, dd);
  }

  wrap.append(list);

  const swaps = Array.isArray(info.swaps) ? info.swaps : [];
  if (swaps.length) {
    const devices = document.createElement("p");
    devices.className = "reclaimed";
    devices.textContent = swaps
      .map((item) => `${item.path} · ${formatByteSize(item.size_bytes)}`)
      .join("; ");
    wrap.append(devices);
  }

  return wrap;
}

function formatByteSize(value) {
  const size = Number(value);
  if (!Number.isFinite(size) || size < 0) {
    return "0B";
  }
  const units = ["B", "KB", "MB", "GB", "TB"];
  let amount = size;
  for (const unit of units) {
    if (amount < 1024 || unit === units.at(-1)) {
      return `${amount < 10 && unit !== "B" ? amount.toFixed(2) : Math.round(amount)}${unit}`;
    }
    amount /= 1024;
  }
  return `${size}B`;
}

function statusLabel(status) {
  switch (status) {
    case "running":
      return "Выполняется";
    case "ok":
      return "Готово";
    case "error":
      return "Ошибка";
    default:
      return "Готов";
  }
}

function badgeClass(status) {
  if (status === "ok") {
    return "ok";
  }
  if (status === "error") {
    return "bad";
  }
  if (status === "running") {
    return "warn";
  }
  return "skip";
}

function readApiError(payload, fallback) {
  const detail = payload?.detail;
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail) && detail[0]?.msg) {
    return detail.map((item) => item.msg).join("; ");
  }
  return fallback;
}

function formatDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("ru-RU", { dateStyle: "medium", timeStyle: "short" });
}
