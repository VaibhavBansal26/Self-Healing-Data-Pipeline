from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator


@contextmanager
def trace_span(name: str, **attributes: object) -> Iterator[None]:
    """No-op compatible tracing span.

    If OpenTelemetry is installed and OTEL_ENABLED=true, this uses the current
    tracer. Otherwise it remains a zero dependency no-op so local demos never
    break.
    """
    if os.getenv("OTEL_ENABLED", "false").lower() != "true":
        yield
        return
    try:
        from opentelemetry import trace
        tracer = trace.get_tracer("self_healing_pipeline")
        with tracer.start_as_current_span(name) as span:
            for key, value in attributes.items():
                span.set_attribute(key, str(value))
            yield
    except Exception:
        yield


def setup_fastapi_tracing(app: object) -> None:
    if os.getenv("OTEL_ENABLED", "false").lower() != "true":
        return
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)  # type: ignore[arg-type]
    except Exception:
        return
