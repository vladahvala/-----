
import os
import time
import random
from datetime import datetime

import psycopg
from prometheus_client import start_http_server, Counter, Gauge

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.trace import Status, StatusCode


DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "university_db",
    "user": "university_user",
    "password": os.getenv("POSTGRES_PASSWORD", "university_pass")
}

# Налаштування трасування
resource = Resource.create({
    "service.name": "university-monitoring-generator"
})

provider = TracerProvider(resource=resource)

exporter = OTLPSpanExporter(
    endpoint="http://localhost:4318/v1/traces"
)

provider.add_span_processor(BatchSpanProcessor(exporter))
trace.set_tracer_provider(provider)

tracer = trace.get_tracer("university-monitoring")


# Prometheus metrics
EVENTS_TOTAL = Counter(
    "monitoring_events_total",
    "Total number of generated events",
    ["event_type"]
)

DB_CONNECTION_STATUS = Gauge(
    "monitoring_db_connection",
    "PostgreSQL connection status"
)


def create_table(connection):
    with tracer.start_as_current_span("create_table") as span:
        try:
            span.set_attribute("db.system", "postgresql")
            span.set_attribute("db.operation", "CREATE")

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

        except Exception as error:
            span.record_exception(error)
            span.set_status(Status(StatusCode.ERROR))
            raise


def generate_event(connection):
    event_types = [
        "login",
        "logout",
        "database_query",
        "file_upload",
        "page_view"
    ]

    event_type = random.choice(event_types)

    with tracer.start_as_current_span("generate_event") as span:
        try:
            span.set_attribute("db.system", "postgresql")
            span.set_attribute("db.operation", "INSERT")
            span.set_attribute("event.type", event_type)

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

            EVENTS_TOTAL.labels(event_type=event_type).inc()

        except Exception as error:
            span.record_exception(error)
            span.set_status(Status(StatusCode.ERROR))
            raise


def main():
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

    finally:
        provider.force_flush()
        provider.shutdown()


if __name__ == "__main__":
    main()
