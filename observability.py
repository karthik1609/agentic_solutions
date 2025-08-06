#!/usr/bin/env python3
"""
ServiceNow MCP System - Observability Stack
Structured logging, distributed tracing, metrics, and continuous profiling
"""

import os
import sys
import socket
import platform
import atexit
from typing import Optional, Dict, Any
from contextlib import contextmanager

import structlog
import pyroscope
from prometheus_client import start_http_server, Counter, Histogram, Gauge, Info

from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor

from dotenv import load_dotenv
load_dotenv()

# Global observability state
_observability_initialized = False
_tracer_provider: Optional[TracerProvider] = None
_meter_provider: Optional[MeterProvider] = None
_logger = None

# Global metrics
REQUEST_COUNT = None
REQUEST_DURATION = None
SUBPROCESS_COUNT = None
SUBPROCESS_DURATION = None
SYSTEM_INFO = None

def get_service_info() -> Dict[str, str]:
    """Get service information for resource labeling"""
    return {
        SERVICE_NAME: os.getenv("OTEL_SERVICE_NAME", "servicenow-mcp-system"),
        SERVICE_VERSION: os.getenv("OTEL_SERVICE_VERSION", "1.0.0"),
        "service.instance.id": f"{socket.gethostname()}-{os.getpid()}",
        "environment": os.getenv("ENVIRONMENT", "development"),
        "host.name": socket.gethostname(),
        "os.type": platform.system(),
        "python.version": platform.python_version(),
    }

def configure_structured_logging(
    log_level: str = "DEBUG",
    log_to_file: bool = True,
    service_name: str = "servicenow-mcp-system"
) -> structlog.stdlib.BoundLogger:
    """Configure comprehensive structured logging with file output and centralized collection"""
    import logging
    from logging.handlers import RotatingFileHandler
    
    # Create logs directory
    logs_dir = os.path.join(os.getcwd(), "logs")
    os.makedirs(logs_dir, exist_ok=True)
    
    # Configure structlog processors
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.CallsiteParameterAdder(
            parameters=[structlog.processors.CallsiteParameter.FUNC_NAME]
        ),
        # OpenTelemetry will inject trace/span IDs automatically
        structlog.processors.JSONRenderer()
    ]
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Set up comprehensive logging with multiple handlers
    log_level_obj = getattr(logging, log_level.upper(), logging.DEBUG)
    
    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level_obj)
    
    # Clear existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Console handler (structured JSON for Loki ingestion)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level_obj)
    console_handler.setFormatter(logging.Formatter('%(message)s'))
    root_logger.addHandler(console_handler)
    
    if log_to_file:
        # Main application log file (rotating)
        main_log_file = os.path.join(logs_dir, f"{service_name}.log")
        file_handler = RotatingFileHandler(
            main_log_file, 
            maxBytes=50*1024*1024,  # 50MB
            backupCount=5
        )
        file_handler.setLevel(log_level_obj)
        file_handler.setFormatter(logging.Formatter('%(message)s'))
        root_logger.addHandler(file_handler)
        
        # Error-only log file
        error_log_file = os.path.join(logs_dir, f"{service_name}-errors.log")
        error_handler = RotatingFileHandler(
            error_log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=3
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(logging.Formatter('%(message)s'))
        root_logger.addHandler(error_handler)
    
    # Set all component loggers to capture everything
    component_loggers = [
        "fastapi", "uvicorn", "uvicorn.access", "uvicorn.error",
        "httpx", "opentelemetry", "magentic_ui", "mcp", "fastmcp",
        "autogen", "openai", "requests", "urllib3", "asyncio",
        "structlog", "prometheus_client", "pyroscope"
    ]
    
    for logger_name in component_loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(log_level_obj)
        logger.propagate = True  # Ensure logs propagate to root logger
    
    # Special handling for noisy loggers - set to INFO minimum
    noisy_loggers = ["urllib3.connectionpool", "asyncio"]
    for logger_name in noisy_loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(max(log_level_obj, logging.INFO))
    
    return structlog.get_logger()

def configure_tracing() -> TracerProvider:
    """Configure OpenTelemetry tracing"""
    global _tracer_provider
    
    # Create resource with service information
    resource = Resource.create(get_service_info())
    
    # Create tracer provider
    _tracer_provider = TracerProvider(resource=resource)
    
    # Configure OTLP exporter
    otlp_exporter = OTLPSpanExporter(
        endpoint=os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "http://localhost:4317"),
        insecure=True,
    )
    
    # Add span processor
    span_processor = BatchSpanProcessor(otlp_exporter)
    _tracer_provider.add_span_processor(span_processor)
    
    # Set global tracer provider
    trace.set_tracer_provider(_tracer_provider)
    
    return _tracer_provider

def configure_metrics() -> MeterProvider:
    """Configure OpenTelemetry metrics"""
    global _meter_provider, REQUEST_COUNT, REQUEST_DURATION, SUBPROCESS_COUNT, SUBPROCESS_DURATION, SYSTEM_INFO
    
    # Create resource with service information
    resource = Resource.create(get_service_info())
    
    # Configure OTLP metric exporter
    otlp_metric_exporter = OTLPMetricExporter(
        endpoint=os.getenv("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT", "http://localhost:4317"),
        insecure=True,
    )
    
    # Create metric reader
    metric_reader = PeriodicExportingMetricReader(
        exporter=otlp_metric_exporter,
        export_interval_millis=30000,  # 30 seconds
    )
    
    # Create meter provider
    _meter_provider = MeterProvider(
        resource=resource,
        metric_readers=[metric_reader],
    )
    
    # Set global meter provider
    metrics.set_meter_provider(_meter_provider)
    
    # Create meter
    meter = metrics.get_meter("servicenow.mcp.system")
    
    # Create custom metrics
    REQUEST_COUNT = meter.create_counter(
        name="http_requests_total",
        description="Total number of HTTP requests",
        unit="1",
    )
    
    REQUEST_DURATION = meter.create_histogram(
        name="http_request_duration_seconds",
        description="HTTP request duration in seconds",
        unit="s",
    )
    
    SUBPROCESS_COUNT = meter.create_counter(
        name="subprocess_started_total",
        description="Total number of subprocesses started",
        unit="1",
    )
    
    SUBPROCESS_DURATION = meter.create_histogram(
        name="subprocess_duration_seconds",
        description="Subprocess execution duration in seconds", 
        unit="s",
    )
    
    # Prometheus metrics for local scraping
    from prometheus_client import Counter, Histogram, Info
    
    # Service info
    SYSTEM_INFO = Info("servicenow_mcp_system_info", "ServiceNow MCP System Information")
    SYSTEM_INFO.info(get_service_info())
    
    return _meter_provider

def configure_profiling():
    """Configure continuous profiling with Pyroscope"""
    try:
        pyroscope.configure(
            application_name=os.getenv("OTEL_SERVICE_NAME", "servicenow-mcp-system"),
            server_address=os.getenv("PYROSCOPE_SERVER_ADDRESS", "http://localhost:4040"),
            tags={
                "service.instance.id": f"{socket.gethostname()}-{os.getpid()}",
                "environment": os.getenv("ENVIRONMENT", "development"),
                "version": os.getenv("OTEL_SERVICE_VERSION", "1.0.0"),
            },
            sample_rate=100,  # Sample every request in development
            detect_subprocesses=True,  # Profile child processes too
            oncpu=os.getenv("PYROSCOPE_ONCPU_PROFILING", "true").lower() == "true",
            gil_only=True,  # Python-specific: only profile when GIL is held
        )
    except Exception as e:
        _logger.warning("pyroscope_config_failed", error=str(e))

def configure_auto_instrumentation():
    """Configure automatic instrumentation for common libraries"""
    
    # FastAPI instrumentation
    FastAPIInstrumentor().instrument()
    
    # HTTP client instrumentation
    HTTPXClientInstrumentor().instrument()
    RequestsInstrumentor().instrument()
    
    # Logging instrumentation (injects trace context)
    LoggingInstrumentor().instrument(set_logging_format=True)

def start_prometheus_server():
    """Start Prometheus metrics server for local scraping, using a free port if needed"""
    desired = os.getenv("PROMETHEUS_METRICS_PORT")
    # Determine initial port
    if desired:
        port = int(desired)
        try:
            start_http_server(port)
            _logger.info("prometheus_server_started", port=port)
            return
        except OSError as e:
            _logger.warning("prometheus_server_start_failed", port=port, error=str(e))
    # Fallback: find a free OS-assigned port
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("", 0))
    free_port = sock.getsockname()[1]
    sock.close()
    try:
        start_http_server(free_port)
        _logger.info("prometheus_server_started", port=free_port, fallback=True)
    except OSError as e:
        _logger.error("prometheus_server_fallback_failed", port=free_port, error=str(e))

def init_observability(
    service_name: Optional[str] = None,
    service_version: Optional[str] = None,
    enable_profiling: bool = True,
    enable_prometheus: bool = True,
) -> structlog.stdlib.BoundLogger:
    """
    Initialize the complete observability stack
    
    Args:
        service_name: Override service name
        service_version: Override service version  
        enable_profiling: Enable continuous profiling
        enable_prometheus: Enable Prometheus metrics server
        
    Returns:
        Configured structured logger
    """
    global _observability_initialized, _logger
    
    if _observability_initialized:
        return _logger
    
    # Override service info if provided
    if service_name:
        os.environ["OTEL_SERVICE_NAME"] = service_name
    if service_version:
        os.environ["OTEL_SERVICE_VERSION"] = service_version
    
    # Initialize components in order
    service_info = get_service_info()
    _logger = configure_structured_logging(
        log_level="DEBUG",
        log_to_file=True,
        service_name=service_info.get(SERVICE_NAME, "servicenow-mcp-system")
    )
    _logger.info("observability_init_starting", service=service_info)
    
    try:
        # Configure OpenTelemetry
        configure_tracing()
        configure_metrics()
        configure_auto_instrumentation()
        
        # Configure profiling if enabled
        if enable_profiling:
            configure_profiling()
            _logger.info("profiling_enabled")
        
        # Start Prometheus server if enabled
        if enable_prometheus:
            start_prometheus_server()
        
        _observability_initialized = True
        _logger.info("observability_init_complete", 
                    tracing=True, 
                    metrics=True, 
                    profiling=enable_profiling,
                    prometheus=enable_prometheus)
        
        # Register cleanup handler
        atexit.register(shutdown_observability)
        
        return _logger
        
    except Exception as e:
        _logger.error("observability_init_failed", error=str(e), exc_info=True)
        raise

def shutdown_observability():
    """Shutdown observability components gracefully"""
    global _tracer_provider, _meter_provider, _logger
    
    if _logger:
        _logger.info("observability_shutdown_starting")
    
    try:
        # Shutdown tracing
        if _tracer_provider:
            _tracer_provider.shutdown()
            
        # Shutdown metrics  
        if _meter_provider:
            _meter_provider.shutdown()
            
        if _logger:
            _logger.info("observability_shutdown_complete")
            
    except Exception as e:
        if _logger:
            _logger.error("observability_shutdown_failed", error=str(e))

@contextmanager
def trace_subprocess(command: str, **extra_tags):
    """Context manager to trace subprocess execution"""
    if not _observability_initialized:
        yield
        return
        
    tracer = trace.get_tracer(__name__)
    start_time = time.time()
    
    with tracer.start_as_current_span("subprocess.execute") as span:
        span.set_attribute("subprocess.command", command)
        span.set_attribute("subprocess.pid", os.getpid())
        
        # Add extra tags
        for key, value in extra_tags.items():
            span.set_attribute(f"subprocess.{key}", str(value))
        
        # Increment subprocess counter
        if SUBPROCESS_COUNT:
            SUBPROCESS_COUNT.add(1, {"command": command})
            
        try:
            yield span
            span.set_status(trace.Status(trace.StatusCode.OK))
        except Exception as e:
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise
        finally:
            # Record duration
            duration = time.time() - start_time
            if SUBPROCESS_DURATION:
                SUBPROCESS_DURATION.record(duration, {"command": command})
            span.set_attribute("subprocess.duration_seconds", duration)

def get_logger(name: str = None) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance"""
    if not _observability_initialized:
        # Fallback to basic structlog if not initialized
        return structlog.get_logger(name)
    return structlog.get_logger(name)

def get_tracer(name: str = __name__):
    """Get an OpenTelemetry tracer instance"""
    return trace.get_tracer(name)

def get_meter(name: str = __name__):
    """Get an OpenTelemetry meter instance"""
    return metrics.get_meter(name)

# Import time for subprocess tracing
import time