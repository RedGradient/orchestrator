const form = document.querySelector("#check-form");
const input = document.querySelector("#url");
const formError = document.querySelector("#form-error");
const results = document.querySelector("#results");
const historyList = document.querySelector("#history-list");
const button = form.querySelector("button");

let historyItems = [];
let selectedId = null;

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  formError.hidden = true;
  button.disabled = true;
  button.textContent = "Проверяю…";

  const url = normalizeUrl(input.value);

  try {
    const response = await fetch("/api/check", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
    const payload = await response.json();
    if (!response.ok) {
      formError.hidden = false;
      formError.textContent = readApiError(payload);
      return;
    }
    showResult(payload);
    await loadHistory(true);
  } catch {
    formError.hidden = false;
    formError.textContent = "Сервис проверки не ответил.";
  } finally {
    button.disabled = false;
    button.textContent = "Проверить";
  }
});

loadHistory(false);

async function loadHistory(selectNewest) {
  const response = await fetch("/api/checks");
  if (!response.ok) {
    renderHistoryMessage("Не удалось загрузить журнал.");
    return;
  }
  historyItems = await response.json();
  if (selectNewest && historyItems.length) {
    selectedId = historyItems[0].id;
  }
  renderHistory();
}

function renderHistory() {
  historyList.replaceChildren();
  if (!historyItems.length) {
    renderHistoryMessage("Пока нет проверок.");
    return;
  }
  for (const item of historyItems) {
    const entry = document.createElement("li");
    const row = document.createElement("button");
    row.type = "button";
    row.className = `history-item${item.id === selectedId ? " selected" : ""}`;
    row.addEventListener("click", () => {
      selectedId = item.id;
      showResult(item.result);
      renderHistory();
    });

    const domain = document.createElement("span");
    domain.className = "history-domain";
    domain.textContent = item.result.domain || item.result.url;

    const meta = document.createElement("span");
    meta.className = "history-meta";
    meta.textContent = `${formatDate(item.created_at)} · ${item.trigger === "automatic" ? "авто" : "вручную"}`;

    row.append(domain, meta, statusDots(item.result));
    entry.append(row);
    historyList.append(entry);
  }
}

function renderHistoryMessage(text) {
  const entry = document.createElement("li");
  entry.className = "history-empty";
  entry.textContent = text;
  historyList.replaceChildren(entry);
}

function statusDots(result) {
  const dots = document.createElement("span");
  dots.className = "dots";
  dots.append(
    dot(result.http?.ok, "HTTP"),
    dot(result.ssl ? result.ssl.ok : null, "SSL"),
    dot(result.robots ? result.robots.available && !result.robots.error : null, "robots.txt"),
    dot(result.sitemap ? result.sitemap.available && !result.sitemap.error : null, "sitemap"),
  );
  return dots;
}

function dot(ok, title) {
  const mark = document.createElement("span");
  mark.className = `dot${ok == null ? "" : ok ? " ok" : " bad"}`;
  mark.title = title;
  return mark;
}

function showResult(payload) {
  results.replaceChildren(
    renderHttp(payload.http),
    renderSsl(payload.ssl),
    renderRobots(payload.robots),
    renderSitemap(payload.sitemap),
  );
}

function normalizeUrl(value) {
  const trimmed = value.trim();
  if (/^https?:\/\//i.test(trimmed)) {
    return trimmed;
  }
  return `https://${trimmed}`;
}

function readApiError(payload) {
  const detail = payload?.detail;
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail) && detail[0]?.msg) {
    return "Нужен адрес вида https://example.com.";
  }
  return "Не удалось выполнить проверку.";
}

function renderHttp(http) {
  if (!http) {
    return skippedCard("HTTP", "Запрос к странице не выполнялся.");
  }
  const card = cardShell("HTTP", http.ok ? "Ответил" : "Недоступен", http.ok);
  const rows = [];
  if (http.status_code != null) {
    rows.push(["Код", String(http.status_code)]);
  }
  if (http.response_time_ms != null) {
    rows.push(["Время", `${http.response_time_ms} мс`]);
  }
  if (http.error) {
    rows.push(["Ошибка", http.error]);
  }
  card.append(definitionList(rows));
  return card;
}

function renderSsl(ssl) {
  if (!ssl) {
    return skippedCard("SSL", "Проверка пропущена: хост не ответил.");
  }
  const card = cardShell("SSL", ssl.ok ? "Сертификат принят" : "Ошибка", ssl.ok);
  const rows = [];
  if (ssl.version) {
    rows.push(["Версия", ssl.version]);
  }
  if (ssl.issuer) {
    rows.push(["Издатель", ssl.issuer]);
  }
  if (ssl.expires_at) {
    rows.push(["Истекает", formatDate(ssl.expires_at)]);
  }
  if (ssl.days_remaining != null) {
    rows.push(["Осталось дней", String(ssl.days_remaining)]);
  }
  if (ssl.error) {
    rows.push(["Ошибка", ssl.error]);
  }
  card.append(definitionList(rows));
  return card;
}

function renderRobots(robots) {
  if (!robots) {
    return skippedCard("robots.txt", "Проверка пропущена: хост не ответил.");
  }
  const ok = robots.available && robots.valid !== false && !robots.error;
  const label = robots.error ? "Ошибка" : robots.available ? "Найден" : "Нет файла";
  const card = cardShell("robots.txt", label, ok);
  const rows = [];
  if (robots.status_code != null) {
    rows.push(["Код", String(robots.status_code)]);
  }
  if (robots.valid != null) {
    rows.push(["Синтаксис", robots.valid ? "корректный" : "с ошибками"]);
  }
  if (robots.error) {
    rows.push(["Ошибка", robots.error]);
  }
  card.append(definitionList(rows));
  appendNotes(card, "Ошибки", robots.errors, "errors");
  appendNotes(card, "Предупреждения", robots.warnings, "warnings");
  appendNotes(card, "Sitemap", robots.sitemaps, "sitemaps");
  return card;
}

function renderSitemap(sitemap) {
  if (!sitemap) {
    return skippedCard("sitemap", "Проверка пропущена: хост не ответил.");
  }
  const ok = sitemap.available && sitemap.valid !== false && !sitemap.error;
  const label = sitemap.error ? "Ошибка" : sitemap.available ? "Найден" : "Нет файла";
  const card = cardShell("sitemap", label, ok);
  const rows = [];
  if (sitemap.status_code != null) {
    rows.push(["Код", String(sitemap.status_code)]);
  }
  if (sitemap.valid != null) {
    rows.push(["Синтаксис", sitemap.valid ? "корректный" : "с ошибками"]);
  }
  if (sitemap.url_count != null) {
    rows.push(["Адресов", String(sitemap.url_count)]);
  }
  if (sitemap.error) {
    rows.push(["Ошибка", sitemap.error]);
  }
  card.append(definitionList(rows));
  appendNotes(card, "Ошибки", sitemap.errors, "errors");
  appendNotes(card, "Предупреждения", sitemap.warnings, "warnings");
  return card;
}

function skippedCard(title, note) {
  const card = cardShell(title, "Не проверялось", null);
  const paragraph = document.createElement("p");
  paragraph.className = "skip-note";
  paragraph.textContent = note;
  card.append(paragraph);
  return card;
}

function cardShell(title, badgeText, ok) {
  const card = document.createElement("article");
  card.className = "card";
  const head = document.createElement("div");
  head.className = "card-head";
  const heading = document.createElement("h2");
  heading.textContent = title;
  const badge = document.createElement("span");
  badge.className = `badge ${ok == null ? "skip" : ok ? "ok" : "bad"}`;
  badge.textContent = badgeText;
  head.append(heading, badge);
  card.append(head);
  return card;
}

function definitionList(rows) {
  const list = document.createElement("dl");
  for (const [term, value] of rows) {
    const dt = document.createElement("dt");
    dt.textContent = term;
    const dd = document.createElement("dd");
    dd.textContent = value;
    list.append(dt, dd);
  }
  return list;
}

function appendNotes(card, title, items, className) {
  if (!items?.length) {
    return;
  }
  const heading = document.createElement("p");
  heading.className = "skip-note";
  heading.textContent = title;
  const list = document.createElement("ul");
  list.className = `notes ${className}`;
  for (const item of items) {
    const li = document.createElement("li");
    li.textContent = String(item);
    list.append(li);
  }
  card.append(heading, list);
}

function formatDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("ru-RU", { dateStyle: "medium", timeStyle: "short" });
}
