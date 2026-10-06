# Orchestrator

Сервис для обслуживания удалённых серверов и проверки сайтов, привязанных к хостам.

Проверка сайта — действие `site_check` для выбранного хоста с указанным `site_url`.
Она смотрит, отвечает ли адрес по HTTP(S), действителен ли TLS-сертификат, есть ли
`robots.txt` и `sitemap.xml` и корректно ли они составлены. Результат сохраняется
в задаче операции и отображается в общей истории действий.

Для SSH-действий хост регистрируется с данными подключения. На странице действий
выбираются хосты и действия, после чего запускается операция. Сейчас доступны:

- **Site Check** — проверяет сайт, указанный в `site_url` хоста: HTTP, TLS,
  `robots.txt` и `sitemap.xml`; SSH-подключение для этого действия не требуется;
- **Overlay2 Analyze** *(экспериментальное)* — анализирует
  физические директории Docker `overlay2`, показывает используемые, временные и
  потенциально висячие слои;
- **Overlay2 Cleanup** *(экспериментальное)* — повторно анализирует `overlay2` и
  удаляет выявленные висячие слои;
- **Docker Cleanup** — остановка и удаление контейнеров, prune volumes, networks,
  images и build cache; в отчёте — списки удалённых объектов и освобождённое место;
- **Postgres Backup** — dump баз из запущенных контейнеров PostgreSQL на хосте;
  файлы скачиваются в каталог `backup/` на сервере оркестратора;
- **Create SWAP** — подбор размера по свободному месту, удаление старого SWAP,
  создание файла `/swapfile` и запись в fstab.
- **Logs Rotation** — настройка и выполнение ротации логов с ограничением их размера. 
  Избыточные данные в ротированных лог-файлах удаляются с сохранением последних записей, 
  что позволяет освободить занятое дисковое пространство.
- **Port Checker** — проверяет открытые порты хоста, определяет связанные с ними сервисы и формирует 
  рекомендации по ограничению внешнего доступа.



## Стек

- Python 3.14, FastAPI и Uvicorn
- HTTP-проверки через httpx, разбор DNS через dnspython, TLS через стандартную библиотеку
- Асинхронный SQLAlchemy и psycopg, миграции Alembic, PostgreSQL 17
- SSH к хостам через asyncssh
- Redis и Celery: действия операций запускаются в фоновом worker-процессе;
  состояние операции и отдельных задач хранится в PostgreSQL, а изменения
  передаются клиенту через Server-Sent Events (SSE)
- React, TypeScript, Vite, Tailwind CSS и shadcn/ui
- Docker Compose; в проде перед приложением стоит Caddy и Let's Encrypt

## Интерфейс

Frontend находится в `frontend/`. Vite обрабатывает клиентские маршруты и
проксирует `/api` в FastAPI во время разработки. Production-сборку из
`frontend/dist` раздаёт FastAPI.

- `/` — основной экран действий
- `/operations` — история запусков с поиском, фильтрами и пагинацией
- `/operations/:operationId` — прогресс и результаты отдельного запуска

## Запуск для разработки

```bash
cp .env.example .env
docker compose -f docker-compose.dev.yml up --build
```

Compose запускает `db`, `redis`, `app`, `frontend` и `worker`. Приложение применяет
миграции Alembic при старте, `worker` получает фоновые задачи через Redis, а
Vite автоматически обновляет frontend при изменениях.

Frontend для разработки: http://localhost:5173. Собранная версия через FastAPI:
http://localhost:8000. Postgres опубликован на `localhost:5432`, Redis — на
`localhost:6379`.

Frontend также можно запустить отдельно:

```bash
cd frontend
npm install
npm run dev
```

Проверка production-сборки:

```bash
cd frontend
npm run build
```

Для запуска вне Compose укажите `DATABASE_URL`, `CELERY_BROKER_URL` и `REDIS_URL`.
По умолчанию две последние переменные указывают на `redis://localhost:6379/0`.
Таймауты SSH настраиваются переменными `SSH_CONNECTION_TIMEOUT_SECONDS` (15 секунд)
и `SSH_ACTION_TIMEOUT_SECONDS` (900 секунд).

## Запуск в проде

В `.env` задайте `SITE_ADDRESS` (домен без схемы). Пароли замените на свои.

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Caddy слушает 80 и 443 и получает сертификат Let's Encrypt.

## API

- `GET /api/hosts` — список зарегистрированных хостов
- `POST /api/host` — зарегистрировать SSH-хост.
  Поле `site_url` необязательно; адрес без схемы будет дополнен `https://`.
  Тело: `{ "label": "Production", "site_url": "example.com", "ip": "1.2.3.4", "username": "root", "password": "..." }`.
  Ответ: `{ "id", "label", "site_url", "ip", "username" }`
- `PATCH /api/hosts/{host_id}` — изменить `label`, `site_url`, IP и/или пароль активного хоста.
- `DELETE /api/hosts/{host_id}` — скрыть хост из рабочих списков, сохранив историю Tasks.
- `POST /api/command` — выполнить SSH-действие на хосте
  Тело: `{ "host_id": 1, "command": "docker_cleanup" }`
  Команды: `overlay2_analyze`, `overlay2_cleanup`, `docker_cleanup`,
  `postgres_backup`, `create_swap`, `logs_cleanup`, `ports`

### Фоновые операции

`Operation` объединяет действия, запускаемые на выбранных хостах. Для каждой пары
«хост — действие» создаётся отдельная задача, которую выполняет Celery worker.
SSH открывается только для действий, которым он нужен.

- `POST /api/operations` — создать операцию и поставить её задачи в очередь. Возвращает
  `202 Accepted` и идентификатор операции:

  ```json
  {
    "host_ids": [1, 2],
    "actions": [
      { "command": "ports", "parameters": {} },
      { "command": "logs_cleanup", "parameters": {} }
    ]
  }
  ```

  Ответ: `{ "operation_id": 42, "status": "queued" }`.

  Действие `site_check` требует непустой `site_url` у каждого выбранного хоста.
  Иначе API вернёт `422 Unprocessable Entity` с именем и IP каждого хоста без адреса сайта.

- `GET /api/operations` — получить страницу истории операций; поддерживает `page`,
  `page_size`, `query`, `status_group` и `days`
- `GET /api/operations/{operation_id}` — актуальный снимок операции: её статус,
  счётчики прогресса, а также статус, результат или ошибку каждой дочерней задачи.
- `GET /api/operations/{operation_id}/events` — SSE-поток событий
  `task.updated`, `operation.updated` и `operation.completed`. После события
  клиенту следует запрашивать актуальный снимок операции через `GET`.
- `POST /api/operations/{operation_id}/cancel` — отменить ещё не начатые задачи и
  запросить отмену выполняемых; возвращает обновлённый снимок операции.

Статусы операции: `pending`, `queued`, `running`, `succeeded`, `failed`,
`partial_failure`, `cancelled`. Статусы задач дополнительно включают `timeout` и
`cancellation_requested`.
