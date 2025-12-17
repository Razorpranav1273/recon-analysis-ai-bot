"""
Structured Logging Setup for Recon Analysis Bot
Based on poc_risk_agent logging pattern.
"""

import os
import traceback
import logging
import logging.handlers
import structlog
from structlog.stdlib import ProcessorFormatter
from src.utils.config_reader import get_config_value
import string
import random


def generate_random_string(length: int = 10) -> str:
    """Generate random string for log file names."""
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


app_env = os.getenv("APP_ENV")


def set_app_env(_, __, event_dict):
    """Add app environment to log events."""
    event_dict["app_env"] = app_env or "unknown"
    return event_dict


def rename_event_to_msg(_, __, event_dict):
    """Rename 'event' key to 'msg' for compatibility."""
    if "event" in event_dict:
        event_dict["msg"] = event_dict["event"]
        del event_dict["event"]
    return event_dict


# Read logging configuration from TOML config
log_level_str = get_config_value("logging.level", "INFO").upper()
log_format = get_config_value("logging.format", "json").lower()
include_caller_info = get_config_value("logging.include_caller_info", True)
include_timestamps = get_config_value("logging.include_timestamps", True)

# Convert string log level to logging constant
log_level_mapping = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
    "NOTSET": logging.NOTSET,
}
log_level = log_level_mapping.get(log_level_str, logging.INFO)

# Resolve file logging destination
LOG_DIR = os.environ.get("LOG_DIR", "/var/log/fluentd")
SERVICE_NAME = os.environ.get("SERVICE_NAME", "recon-analysis-bot")
LOG_FILE_PATH = os.path.join(
    LOG_DIR, f"{SERVICE_NAME}.{generate_random_string()}.log"
)

# Pre-chain processors executed for both stdlib & structlog loggers
foreign_pre_chain = []

if include_timestamps:
    foreign_pre_chain.append(structlog.processors.TimeStamper(fmt="iso"))

foreign_pre_chain.extend(
    [
        structlog.processors.ExceptionRenderer(),
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
    ]
)

# Restore caller info fields
if include_caller_info:
    foreign_pre_chain.append(
        structlog.processors.CallsiteParameterAdder(
            {
                structlog.processors.CallsiteParameter.PATHNAME,
                structlog.processors.CallsiteParameter.MODULE,
                structlog.processors.CallsiteParameter.FUNC_NAME,
                structlog.processors.CallsiteParameter.THREAD,
                structlog.processors.CallsiteParameter.THREAD_NAME,
                structlog.processors.CallsiteParameter.PROCESS,
                structlog.processors.CallsiteParameter.PROCESS_NAME,
                structlog.processors.CallsiteParameter.LINENO,
            }
        )
    )

# Continue with remaining processors
foreign_pre_chain.extend(
    [
        structlog.stdlib.add_log_level,
        structlog.contextvars.merge_contextvars,
        set_app_env,
        rename_event_to_msg,
    ]
)

# Choose final renderer for handlers
console_renderer = (
    structlog.dev.ConsoleRenderer()
    if log_format == "console"
    else structlog.processors.JSONRenderer()
)
file_renderer = structlog.processors.JSONRenderer()

# Create formatters for handlers
console_formatter = ProcessorFormatter(
    processor=console_renderer, foreign_pre_chain=foreign_pre_chain
)
file_formatter = ProcessorFormatter(
    processor=file_renderer, foreign_pre_chain=foreign_pre_chain
)

# Build handlers: console (stdout) + file (optional)
handlers = []

console_handler = logging.StreamHandler()
console_handler.setLevel(log_level)
console_handler.setFormatter(console_formatter)
handlers.append(console_handler)

# Attempt to enable file logging; ignore failures
try:
    os.makedirs(LOG_DIR, exist_ok=True)
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE_PATH, maxBytes=10 * 1024 * 1024, backupCount=5
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(file_formatter)
    handlers.append(file_handler)
except Exception:
    print(f"Failed to write to file: {LOG_FILE_PATH} - {traceback.format_exc()}")
    pass

# Configure stdlib logging with our handlers
logging.basicConfig(level=log_level, handlers=handlers, force=True)

# Configure structlog
structlog_processors = []

if include_timestamps:
    structlog_processors.append(structlog.processors.TimeStamper(fmt="iso"))

structlog_processors.extend(
    [
        structlog.processors.ExceptionRenderer(),
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
    ]
)

if include_caller_info:
    structlog_processors.append(
        structlog.processors.CallsiteParameterAdder(
            {
                structlog.processors.CallsiteParameter.PATHNAME,
                structlog.processors.CallsiteParameter.MODULE,
                structlog.processors.CallsiteParameter.FUNC_NAME,
                structlog.processors.CallsiteParameter.THREAD,
                structlog.processors.CallsiteParameter.THREAD_NAME,
                structlog.processors.CallsiteParameter.PROCESS,
                structlog.processors.CallsiteParameter.PROCESS_NAME,
                structlog.processors.CallsiteParameter.LINENO,
            }
        )
    )

structlog_processors.extend(
    [
        structlog.processors.add_log_level,
        structlog.contextvars.merge_contextvars,
        set_app_env,
        rename_event_to_msg,
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ]
)

structlog.configure(
    processors=structlog_processors,
    wrapper_class=structlog.make_filtering_bound_logger(log_level),
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

