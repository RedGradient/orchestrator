# Orchestrator

Сервис для проверки сайтов и обслуживания удалённых серверов по SSH.

Проверка сайта смотрит, отвечает ли адрес по HTTP(S), действителен ли TLS-сертификат
и доверен ли он (в том числе сертификаты Минцифры), есть ли `robots.txt` и
`sitemap.xml` и корректно ли они составлены. Результат каждой проверки сохраняется
в PostgreSQL; история запусков доступна в журнале на странице.

Для операций с VPS хост регистрируется по SSH. На странице действий выбирается
операция, отмечаются хосты и запускается выполнение. Сейчас доступны:

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
- Redis и Celery: SSH-действия запускаются в фоновом worker-процессе;
  состояние операции и отдельных задач хранится в PostgreSQL, а изменения
  передаются клиенту через Server-Sent Events (SSE)
- Страница на HTML, CSS и JavaScript
- Docker Compose; в проде перед приложением стоит Caddy и Let's Encrypt

## Интерфейс

- `/` — каталог действий
- `/action.html?id=…` — хосты и запуск выбранного действия
- `/check.html` — проверка сайта и журнал

## Запуск для разработки

```bash
cp .env.example .env
docker compose -f docker-compose.dev.yml up --build
```

Compose запускает `db`, `redis`, `app` и `worker`. Приложение применяет миграции
Alembic при старте, а `worker` получает фоновые SSH-задачи через Redis.

Страница: http://localhost:8000. Postgres опубликован на `localhost:5432`, Redis —
на `localhost:6379`.

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

- `POST /api/check` — проверить сайт и сохранить результат  
  Тело: `{ "url": "https://example.com" }`
- `GET /api/checks` — последние проверки из журнала
- `GET /api/hosts` — список зарегистрированных хостов
- `POST /api/host` — зарегистрировать SSH-хост  
  Тело: `{ "ip": "1.2.3.4", "username": "root", "password": "..." }`  
  Ответ: `{ "id", "ip", "username" }`
- `POST /api/command` — выполнить действие на хосте  
  Тело: `{ "host_id": 1, "command": "docker_cleanup" }`  
  Команды: `docker_cleanup`, `postgres_backup`, `create_swap`, `logs_cleanup`, `ports`

### Фоновые операции с VPS

`Operation` объединяет действия, запускаемые на выбранных хостах. Для каждой пары
«хост — действие» создаётся отдельная задача, которую выполняет Celery worker.

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
