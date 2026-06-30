import json
import logging
import os
import secrets

from flask import g, has_request_context, request


logger = logging.getLogger("yacht")


def assign_request_id():
    incoming = (request.headers.get("X-Request-ID") or "").strip()
    g.request_id = incoming[:64] if incoming else secrets.token_hex(12)
    return g.request_id


def get_request_id():
    if not has_request_context():
        return ""
    return getattr(g, "request_id", "")


def attach_request_id(response):
    request_id = get_request_id()
    if request_id:
        response.headers["X-Request-ID"] = request_id
    return response


def log_json(level, event, **fields):
    payload = {"event": event, **fields}
    request_id = get_request_id()
    if request_id:
        payload["request_id"] = request_id
    logger.log(level, json.dumps(payload, ensure_ascii=False, sort_keys=True))


def configure_tracing(app):
    if os.getenv("YACHT_OTEL_ENABLED", "0") != "1":
        return False

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.flask import FlaskInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except Exception as exc:
        logger.warning(json.dumps({
            "event": "otel_unavailable",
            "error": str(exc),
        }, ensure_ascii=False, sort_keys=True))
        return False

    service_name = os.getenv("OTEL_SERVICE_NAME", "yacht-multi")
    provider = TracerProvider(
        resource=Resource.create({"service.name": service_name})
    )
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)
    FlaskInstrumentor().instrument_app(app)
    logger.info(json.dumps({
        "event": "otel_enabled",
        "service_name": service_name,
    }, ensure_ascii=False, sort_keys=True))
    return True
