"""OpenTelemetry distributed tracing configuration."""

from __future__ import annotations

import logging
from typing import Optional

try:
    from opentelemetry import trace
    from opentelemetry.exporter.jaeger.thrift import JaegerExporter
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.neo4j import Neo4jInstrumentor
    from opentelemetry.instrumentation.requests import RequestsInstrumentor
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False

logger = logging.getLogger(__name__)


class TracingConfig:
    """OpenTelemetry tracing configuration."""
    
    def __init__(
        self,
        service_name: str = "ultimate-mcp",
        service_version: str = "0.1.2",
        jaeger_endpoint: Optional[str] = None,
        otlp_endpoint: Optional[str] = None,
        sample_rate: float = 1.0,
    ):
        self.service_name = service_name
        self.service_version = service_version
        self.jaeger_endpoint = jaeger_endpoint
        self.otlp_endpoint = otlp_endpoint
        self.sample_rate = sample_rate
        self.tracer: Optional[trace.Tracer] = None
    
    def initialize(self) -> bool:
        """Initialize OpenTelemetry tracing."""
        if not OTEL_AVAILABLE:
            logger.warning("OpenTelemetry not available, tracing disabled")
            return False
        
        try:
            # Create resource
            resource = Resource.create({
                SERVICE_NAME: self.service_name,
                SERVICE_VERSION: self.service_version,
            })
            
            # Create tracer provider
            tracer_provider = TracerProvider(resource=resource)
            
            # Add exporters
            if self.jaeger_endpoint:
                jaeger_exporter = JaegerExporter(
                    agent_host_name="localhost",
                    agent_port=14268,
                    collector_endpoint=self.jaeger_endpoint,
                )
                tracer_provider.add_span_processor(
                    BatchSpanProcessor(jaeger_exporter)
                )
                logger.info("Jaeger tracing enabled", extra={"endpoint": self.jaeger_endpoint})
            
            if self.otlp_endpoint:
                otlp_exporter = OTLPSpanExporter(endpoint=self.otlp_endpoint)
                tracer_provider.add_span_processor(
                    BatchSpanProcessor(otlp_exporter)
                )
                logger.info("OTLP tracing enabled", extra={"endpoint": self.otlp_endpoint})
            
            # Set global tracer provider
            trace.set_tracer_provider(tracer_provider)
            self.tracer = trace.get_tracer(self.service_name)
            
            # Auto-instrument libraries
            FastAPIInstrumentor.instrument()
            Neo4jInstrumentor.instrument()
            RequestsInstrumentor.instrument()
            
            logger.info("OpenTelemetry tracing initialized successfully")
            return True
            
        except Exception as e:
            logger.error("Failed to initialize tracing", extra={"error": str(e)})
            return False
    
    def get_tracer(self) -> Optional[trace.Tracer]:
        """Get the configured tracer."""
        return self.tracer


# Global tracing instance
_tracing_config: Optional[TracingConfig] = None


def init_tracing(
    service_name: str = "ultimate-mcp",
    jaeger_endpoint: Optional[str] = None,
    otlp_endpoint: Optional[str] = None,
    **kwargs
) -> TracingConfig:
    """Initialize global tracing configuration."""
    global _tracing_config
    _tracing_config = TracingConfig(
        service_name=service_name,
        jaeger_endpoint=jaeger_endpoint,
        otlp_endpoint=otlp_endpoint,
        **kwargs
    )
    _tracing_config.initialize()
    return _tracing_config


def get_tracer() -> Optional[trace.Tracer]:
    """Get global tracer instance."""
    if _tracing_config:
        return _tracing_config.get_tracer()
    return None


def trace_operation(operation_name: str):
    """Decorator to trace function calls."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            tracer = get_tracer()
            if not tracer:
                return func(*args, **kwargs)
            
            with tracer.start_as_current_span(operation_name) as span:
                try:
                    result = func(*args, **kwargs)
                    span.set_status(trace.Status(trace.StatusCode.OK))
                    return result
                except Exception as e:
                    span.set_status(trace.Status(
                        trace.StatusCode.ERROR, 
                        description=str(e)
                    ))
                    raise
        return wrapper
    return decorator


async def trace_async_operation(operation_name: str):
    """Async decorator to trace function calls."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            tracer = get_tracer()
            if not tracer:
                return await func(*args, **kwargs)
            
            with tracer.start_as_current_span(operation_name) as span:
                try:
                    result = await func(*args, **kwargs)
                    span.set_status(trace.Status(trace.StatusCode.OK))
                    return result
                except Exception as e:
                    span.set_status(trace.Status(
                        trace.StatusCode.ERROR, 
                        description=str(e)
                    ))
                    raise
        return wrapper
    return decorator
