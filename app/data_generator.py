import os
import time
import random
from datetime import datetime

import psycopg
from prometheus_client import start_http_server, Counter, Gauge


DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "university_db",
    "user": "university_user",
    "password": os.getenv("POSTGRES_PASSWORD", "university_pass")
}

# Загальна кількість згенерованих подій
EVENTS_TOTAL = Counter(
    "monitoring_events_total",
    "Total number of generated events",
    ["event_type"]
)

# Кількість активних підключень генератора до БД
DB_CONNECTION_STATUS = Gauge(
    "monitoring_db_connection",
    "PostgreSQL connection status"
)


def create_table(connection):
    with connection.cursor() as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS monitoring_events (
                id SERIAL PRIMARY KEY,
                event_type VARCHAR(50) NOT NULL,
                description TEXT,
                value INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
    connection.commit()


def generate_event(connection):
    event_types = [
        "login",
        "logout",
        "database_query",
        "file_upload",
        "page_view"
    ]

    event_type = random.choice(event_types)

    with connection.cursor() as cursor:
        cursor.execute("""
            INSERT INTO monitoring_events
                (event_type, description, value)
            VALUES (%s, %s, %s);
        """, (
            event_type,
            "Generated test event",
            random.randint(1, 100)
        ))

    connection.commit()

    # Збільшуємо лічильник відповідного типу події
    EVENTS_TOTAL.labels(event_type=event_type).inc()


def main():
    # Запускаємо HTTP-сервер метрик на порту 8000
    start_http_server(8001)

    print("Prometheus metrics available on port 8001")
    print("Connecting to PostgreSQL...")

    try:
        with psycopg.connect(**DB_CONFIG) as connection:
            DB_CONNECTION_STATUS.set(1)

            print("Connected successfully!")
            create_table(connection)

            print("Table monitoring_events is ready.")

            while True:
                generate_event(connection)
                print(f"Event generated at {datetime.now()}")
                time.sleep(5)

    except Exception:
        DB_CONNECTION_STATUS.set(0)
        raise


if __name__ == "__main__":
    main()