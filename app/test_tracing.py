from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

# Налаштовуємо провайдера трасування
provider = TracerProvider()
trace.set_tracer_provider(provider)

# Налаштовуємо відправлення traces у Tempo через OTLP HTTP
exporter = OTLPSpanExporter(
    endpoint="http://localhost:4318/v1/traces"
)

provider.add_span_processor(BatchSpanProcessor(exporter))

# Створюємо tracer
tracer = trace.get_tracer("university-monitoring")

# Створюємо тестове трасування
with tracer.start_as_current_span("test-tempo-trace") as span:
    span.set_attribute("service.name", "python-test")
    span.set_attribute("environment", "development")
    print("Test trace created and sent to Tempo")

# Примусово відправляємо дані перед завершенням програми
provider.force_flush()
provider.shutdown()