# Техническая оценка: асинхронные операции над VPS

## Область работ и решение

Этот документ фиксирует исходное состояние и целевой контракт переноса VPS-действий
из жизненного цикла HTTP-запроса в фоновые задачи. Он не меняет поведение
приложения. Предлагаемая реализация сохраняет FastAPI в качестве API-слоя,
PostgreSQL как авторитетное хранилище состояния, AsyncSSH как слой выполнения
действий и добавляет Celery с Redis для фоновой доставки задач.

Ниже используется доменное имя **OperationTask** (таблица БД
`operation_tasks`). Оно намеренно не совпадает с `celery.Task`.

## Текущий поток запроса

`POST /api/command` в `src/main.py` принимает один `host_id` и один `Command`.
Он загружает `Host` через привязанный к запросу `AsyncSession`, открывает
AsyncSSH-соединение, выбирает действие цепочкой `if`/`elif` и ожидает его
завершения перед возвратом `201 Created`.

```text
браузер -> POST /api/command -> FastAPI endpoint -> AsyncSession.get(Host)
        -> asyncssh.connect -> action(conn) -> response
```

В результате браузерное соединение остаётся открытым на всё время SSH-операции.
Текущий frontend последовательно выполняет один запрос для каждого выбранного
хоста.

## Существующее хранение данных и соглашения для сессий

`src/models.py` сейчас содержит:

- `Site` и `Check` для истории проверок сайтов;
- `Host` для SSH-учётных данных и адреса целевого сервера.

Первичные ключи — целые числа. JSON-полезная нагрузка хранится PostgreSQL в
`JSONB`. Миграции Alembic линейны; текущая ревизия — `ac78f4283d89`.

`src/session.py` владеет одним асинхронным SQLAlchemy engine и
`async_sessionmaker`. FastAPI dependency выдаёт сессию и откатывает её, если
исключение выходит наружу. Сервисы, например `create_host()` и `_save_check()`,
сами коммитят успешно выполненные записи. Новый сервис операций должен сохранить
этот явный паттерн транзакций; Celery worker обязан создавать собственную сессию
и никогда не получать ORM-объект из FastAPI.

## Существующие schemas и результаты действий

В `src/schemas.py` уже есть `Command`, `CommandRequest`, `CommandResponse` и
модели результатов для большинства действий:

- `DockerPruneResult` для `docker_cleanup`;
- `CreateSwapResult` для `create_swap`;
- `LogsCleanupResult` для `logs_cleanup`;
- `PortsCheckResult` для `ports`.

Сейчас `postgres_dump` возвращает `dict[str, Any]`; отдельной Pydantic-модели
результата нет. В рамках асинхронных операций нужно либо ввести небольшую
типизированную схему результата бэкапа, либо явно валидировать и сохранять его
текущий сериализуемый словарь. Нельзя заменять результаты actions универсальной
моделью stdout/stderr.

## Существующие действия и необходимые адаптеры

Все VPS-действия являются обычными async-функциями и не должны содержать код
Celery:

- `docker_cleanup` вызывает `docker_cleanup(conn)` и не требует адаптера.
- `create_swap` вызывает `try_create_swap(conn)`; имя в registry отличается от
  имени Python-функции.
- `logs_cleanup` вызывает `logs_cleanup(conn)` и не требует адаптера.
- `ports` вызывает `check_ports(conn)`; имя в registry отличается от имени
  Python-функции.
- `postgres_backup` вызывает `postgres_dump(conn, host, local_dump_dir)` и
  требует адаптера, который передаст IP хоста и доступный worker’у каталог
  бэкапов.

Действия вызывают `run_command(conn, ...)` и могут выполнять несколько удалённых
команд. Поэтому один `OperationTask` представляет одно полное действие на одном
хосте, а не отдельный вызов `conn.run()`.

Существующие интеграционные тесты в `tests/integration/test_ports.py` и
`tests/integration/test_logs.py` напрямую проверяют эти actions через SSH
тестового контейнера. Они должны остаться независимыми от Celery и Redis.

## Целевая доменная модель и правила состояний

Добавить `Operation` и `OperationTask` с целочисленными ID и временными метками,
согласованными с существующими моделями.

`Operation` минимально хранит `id`, `status`, `created_at`, `started_at` и
`finished_at`. `OperationTask` хранит `id`, `operation_id`, `host_id`,
`command`, `parameters` (JSONB), `status`, `result` (JSONB), `error` и такие же
временные метки. `created_by` не входит в scope, поскольку в проекте нет
пользовательского контекста.

Переходы состояний задачи:

```text
PENDING -> QUEUED -> RUNNING -> SUCCEEDED
                             -> FAILED | TIMEOUT | CANCELLATION_REQUESTED
PENDING | QUEUED -> CANCELLED
```

`SUCCEEDED`, `FAILED`, `TIMEOUT` и `CANCELLED` — terminal-состояния. Worker
должен атомарно захватывать только задачу в `QUEUED` и при повторной доставке
оставлять любую terminal-задачу без изменений.

Статус Operation выводится из входящих задач. Пока хотя бы одна задача не
terminal, Operation имеет `PENDING`, `QUEUED` или `RUNNING`; после завершения
всех задач — `SUCCEEDED`, `FAILED`, `CANCELLED` или `PARTIAL_FAILURE` по
ситуации. Ошибка одной задачи не завершает ошибкой ещё выполняющуюся Operation.

## Целевой API-контракт

Новый API ориентирован на batch-выполнение:

```text
POST /api/operations                         -> 202, operation_id and status
GET  /api/operations/{operation_id}          -> operation snapshot and tasks
GET  /api/operations/{operation_id}/events   -> SSE stream
POST /api/operations/{operation_id}/cancel   -> updated snapshot/status
```

`POST /api/operations` принимает `host_ids` и описания actions. Если будущий
запрос явно не передаёт пары, создаётся декартово произведение хостов и actions.
Ответ и frontend идентифицируют работу с помощью доменных `operation_id` и
`task_id`; идентификатор Celery-сообщения остаётся внутренней деталью.

`GET` — авторитетный snapshot после обновления страницы или переподключения SSE.
На первом этапе `/api/command` нужно сохранить для совместимости, пока текущий
frontend переходит на новый endpoint; его удаление — отдельное осознанное
изменение API.

## Границы выполнения и доставки уведомлений

Целевая граница компонентов:

```text
HTTP -> operation service -> Celery message(task id) -> task executor
     -> AsyncSSH connection -> existing action -> typed result
```

`src/services/operations.py` должен отвечать за создание Operation, snapshots,
агрегацию и отмену. Registry/executor actions должен быть отдельным модулем
(например, `src/services/task_executor.py`) и адаптировать единственную особую
сигнатуру бэкапа, не меняя action-функции. Конфигурация Celery и синхронная
входная Celery-задача должны быть вне FastAPI (например, `src/celery_app.py` и
`src/worker_tasks.py`). Входная Celery-задача получает только
`operation_task_id`, открывает собственную БД-сессию, захватывает задачу и
запускает для async executor изолированный asyncio event loop.

После коммита изменения состояния в PostgreSQL worker публикует небольшое
JSON-событие в Redis Pub/Sub-канал, относящийся к Operation. SSE endpoint
FastAPI подписывается на него и отправляет события `task.updated`,
`operation.updated` и финальное `operation.completed`. Потеря Pub/Sub-события
допустима, так как это не source of truth: им остаётся endpoint со snapshot.

## Необходимые изменения миграций и инфраструктуры

Одна миграция Alembic должна создать две таблицы, enum’ы статусов, внешние ключи,
столбцы JSONB и индексы, нужные для поиска операций/задач и захвата задач
worker’ом. В runtime-зависимости нужно добавить Celery, Redis client и Redis в
Compose-файлы для разработки и production. Worker нужны те же настройки БД, код
приложения, CA-сертификаты и общий volume `/app/backup`, поскольку
`postgres_dump` записывает файлы локально.

## Сбои и намеренная семантика первой версии

- **Повторная доставка / гонка workers:** захватывать queued-задачу атомарным
  условным update или row lock; не выполнять задачу, если захват не удался.
- **Публикация в broker после DB commit не удалась:** записи в `QUEUED` могут
  остаться без сообщения. Первой реализации нужен явный recovery-путь для
  повторной постановки; transactional outbox остаётся техническим долгом.
- **Ошибки SSH, аутентификации, action или сериализации результата:** сохранять
  `FAILED` с диагностикой и всегда закрывать соединение.
- **Timeout:** конфигурация содержит отдельные connection и action timeouts;
  action timeout сохраняет `TIMEOUT`.
- **Cancellation:** queued-работа становится `CANCELLED`. Выполняющаяся работа
  становится `CANCELLATION_REQUESTED`; закрытие SSH-соединения не означает
  гарантию остановки удалённого процесса.
- **Повторные попытки:** не использовать глобальный Celery autoretry.
  Деструктивные административные actions не считаются идемпотентными.
- **Конкурентность:** сначала полагаться на concurrency Celery worker. Модель
  данных не должна мешать будущим лимитам общего, per-operation или per-host
  уровня.

Запланированные задания не входят в эту миграцию. Будущий планировщик должен создавать те
же записи `Operation` и `OperationTask` и использовать тот же executor.

## Минимальная последовательность реализации

1. Добавить конфигурацию, сервисы Celery/Redis в Compose, модели БД и миграцию.
2. Добавить schemas операций и безопасный с точки зрения транзакций сервис
   операций.
3. Реализовать registry/executor actions и lifecycle Celery worker.
4. Добавить REST endpoints и перевести frontend, временно сохранив совместимость
   с `/api/command`.
5. Добавить SSE через Redis и семантику отмены.
6. Добавить unit/API/SSE-тесты, сохранить SSH integration tests и задокументировать
   ограничения recovery и процесс развёртывания.
