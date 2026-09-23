# Orchestrator

Сервис проверяет доступность и корректность работы сайта: отвечает ли HTTP(S), 
действителен ли TLS-сертификат и доверен ли он, включая сертификаты Минцифры, 
присутствуют ли `robots.txt` и `sitemap.xml` и корректно ли они составлены. 
Результаты каждой проверки сохраняются в PostgreSQL; история предыдущих запусков 
доступна в журнале на странице сайта.


## Стек

- Python 3.14, FastAPI и Uvicorn
- HTTP-проверки через httpx, разбор DNS через dnspython, TLS через стандартную библиотеку
- SQLAlchemy и psycopg, миграции Alembic, PostgreSQL 17
- Страница на HTML, CSS и JavaScript
- Docker Compose; в проде перед приложением стоит Caddy (вместо nginx) и Let's Encrypt

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

- `POST /api/check` — проверить адрес и сохранить результат
- `GET /api/checks` — последние проверки
