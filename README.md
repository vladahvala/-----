# Система моніторингу роботи бази даних

Система збирає дані про роботу бази даних PostgreSQL, обробляє метрики через Prometheus
і відображає їх у Grafana разом із логами (Loki) і трейсами (Tempo).
Доступ до системи мають лише авторизовані користувачі.

## Архітектура

```
                         ┌──────────────────────── Docker-мережа ────────────────────────┐
 Браузер ──► nginx:8080 ─┤ auth_request ──► auth (FastAPI + SQLite, JWT у cookie)         │
                         │ /            ──► Grafana ──► Prometheus / Loki / Tempo         │
                         │ /prometheus/ ──► Prometheus                                    │
                         │                                                                │
                         │ data-generator ──► PostgreSQL ◄── postgres-exporter            │
                         │       │  метрики :8001          │ метрики :9187                │
                         │       └──────────► Prometheus ◄─┘                              │
                         │ data-generator, auth ──(OTLP)──► Tempo                         │
                         │ логи всіх контейнерів ──► Alloy ──► Loki                       │
                         └────────────────────────────────────────────────────────────────┘
```

Назовні відкритий лише порт **8080** (nginx). Усі інші сервіси доступні тільки всередині Docker-мережі.

## Відповідність вимогам

| № | Вимога | Реалізація |
|---|---|---|
| 0 | СУБД у Docker | PostgreSQL 16 (`postgres`) |
| 1 | Генерація даних у БД | `app/data_generator.py`: кожні 5 с додає подію в таблицю `monitoring_events` |
| 2 | Збір метрик | Prometheus: `postgres-exporter`, метрики генератора, власні метрики |
| 3 | Зберігання метрик | Вбудована TSDB Prometheus (volume `prometheus_data`, 15 днів) |
| 4 | Відображення | Grafana, дашборд «Моніторинг БД» (створюється автоматично) |
| 5 | Логи | Grafana Alloy збирає логи контейнерів → Grafana Loki |
| 6 | Трейси | OpenTelemetry (генератор і auth-сервер) → Grafana Tempo |
| 7 | Авторизація | `app/auth_server.py`: FastAPI + SQLite, паролі bcrypt, JWT; nginx `auth_request` + Grafana `auth.proxy` |
| 8 | Контейнеризація | Docker Compose, `Dockerfile` для Python-сервісів |
| 9 | Брокер повідомлень | Не використовується (дозволено умовою завдання) |

## Запуск

Потрібні Docker і Docker Compose.

1. Створіть файл з налаштуваннями та впишіть свої значення:
   ```bash
   cp .env.example .env
   ```
   - `POSTGRES_EXPORTER_PASSWORD` — пароль користувача БД для exporter;
   - `JWT_SECRET` — випадковий рядок, наприклад результат
     `python3 -c "import secrets; print(secrets.token_hex(32))"`;
   - `GRAFANA_ADMIN_PASSWORD` — пароль внутрішнього адміністратора Grafana.

2. Запустіть систему:
   ```bash
   docker compose up -d --build
   ```

3. Створіть користувача (пароль щонайменше 8 символів, імена `admin` і `root` заборонені):
   ```bash
   docker compose exec auth python -m app.create_user <логін>
   ```

4. Відкрийте http://localhost:8080 і увійдіть.

## Що де дивитися

| Що | Де |
|---|---|
| Дашборд | Grafana → **Dashboards** → **Monitoring** → **Моніторинг БД** |
| Логи | Grafana → **Explore** → Loki → `{service="data-generator"}` або `{service="auth"}` |
| Трейси | Grafana → **Explore** → Tempo → **Search** |
| Від логу до трейсу | у рядку логу натисніть посилання біля `trace_id` |
| Prometheus | http://localhost:8080/prometheus/ (теж потребує входу) |
| Вихід | http://localhost:8080/auth/logout або посилання **Вийти** на дашборді |

## Структура проєкту

```
├── app/
│   ├── auth_server.py      # сервер авторизації (FastAPI)
│   ├── auth_database.py    # робота з SQLite
│   ├── auth_models.py      # моделі запитів
│   ├── create_user.py      # створення користувача з консолі
│   └── data_generator.py   # генерація даних у PostgreSQL + метрики + трейси
├── config/
│   ├── alloy/              # збір логів контейнерів
│   ├── grafana/            # datasources і дашборд (provisioning)
│   ├── loki/
│   ├── nginx/              # точка входу та перевірка авторизації
│   ├── postgres/init/      # створення користувача для exporter
│   ├── prometheus/
│   └── tempo/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── .env.example
```

## Корисні команди

```bash
docker compose ps                         # стан сервісів
docker compose logs -f data-generator     # логи генератора
docker compose logs --tail 20 auth        # логи авторизації
docker compose down                       # зупинити (дані зберігаються)
docker compose down -v                    # зупинити і видалити всі дані
```

## Можливі проблеми

- **Сторінка Grafana постійно перезавантажується.** У браузері лишилися старі cookie Grafana.
  Видаліть cookie для `localhost` (F12 → Application → Cookies) або відкрийте вікно інкогніто.
- **Сторінка входу показує «Невірний логін або пароль».** Перевірте, що користувач створений (крок 3 запуску).
- **Init-скрипт PostgreSQL не виконався.** Скрипти з `config/postgres/init/` запускаються лише на порожній БД.
  Видаліть volume БД: `docker compose down`, потім `docker volume rm university-monitoring_postgres_data`.
