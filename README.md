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

## Стек

- Python 3.14, FastAPI и Uvicorn
- HTTP-проверки через httpx, разбор DNS через dnspython, TLS через стандартную библиотеку
- Асинхронный SQLAlchemy и psycopg, миграции Alembic, PostgreSQL 17
- SSH к хостам через asyncssh
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

Страница: http://localhost:8000. Postgres опубликован на `localhost:5432`. При старте контейнер применяет миграции Alembic.

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
  Команды: `docker_cleanup`, `postgres_backup`, `create_swap`
