import logging
import logging.config
import os
from typing import Any

from rich.console import Console
from rich.logging import RichHandler

DEFAULT_LOG_LEVEL = "INFO"

COLOR_MAPPINGS = {
    "info": "dim cyan",
    "warning": "dim yellow",
    "error": "dim red",
    "debug": "dim",
}

SUPPRESSED_LOGGERS = ["uvicorn.access", "httpx", "httpcore"]


class RichStructuredLogger:
    """A wrapper around Python's logger that provides Rich-compatible structured logging.

    This class formats kwargs as Rich markup strings for visual enhancement in
    development while falling back to plain text in CI environments.
    """

    def __init__(self, logger: logging.Logger, use_rich: bool = True) -> None:
        """Initialize the Rich structured logger.

        Args:
            logger: The underlying Python logger instance
            use_rich: Whether to use Rich markup formatting
        """

        self._logger = logger
        self._use_rich = use_rich

    def _format_message(self, msg: str, level: str, **kwargs: Any) -> str:
        """Format a log message with optional structured data.

        Args:
            msg: The main log message
            level: The log level (info, warning, error, debug)
            **kwargs: Additional structured data to include

        Returns:
            Formatted message string with Rich markup or plain text
        """

        if not kwargs:
            return msg

        extra_str = " | ".join(f"{k}={v}" for k, v in kwargs.items())

        if self._use_rich:
            color = COLOR_MAPPINGS.get(level, "dim")
            return f"{msg} [{color}]\\[{extra_str}][/{color}]"
        else:
            return f"{msg} [{extra_str}]"

    def info(self, msg: str, **kwargs: Any) -> None:
        """Log an info message with optional structured data."""

        formatted_msg = self._format_message(msg, "info", **kwargs)
        self._logger.info(formatted_msg)

    def warning(self, msg: str, **kwargs: Any) -> None:
        """Log a warning message with optional structured data."""

        formatted_msg = self._format_message(msg, "warning", **kwargs)
        self._logger.warning(formatted_msg)

    def error(self, msg: str, **kwargs: Any) -> None:
        """Log an error message with optional structured data."""

        formatted_msg = self._format_message(msg, "error", **kwargs)
        self._logger.error(formatted_msg)

    def debug(self, msg: str, **kwargs: Any) -> None:
        """Log a debug message with optional structured data."""

        formatted_msg = self._format_message(msg, "debug", **kwargs)
        self._logger.debug(formatted_msg)


def get_logger(name: str) -> RichStructuredLogger:
    """Get a logger instance with Rich-compatible structured logging methods.

    Args:
        name: The logger name, typically __name__

    Returns:
        A RichStructuredLogger instance that provides structured logging with Rich formatting
    """

    use_rich_formatting = not _is_ci_environment()
    base_logger = logging.getLogger(name)
    return RichStructuredLogger(base_logger, use_rich_formatting)


def _is_ci_environment() -> bool:
    """Check if running in a CI environment.

    Returns:
        True if CI environment variable is set, False otherwise
    """

    return bool(os.getenv("CI"))


def get_log_level() -> int:
    """Get log level from environment variable.

    Returns:
        The logging level as an integer constant
    """

    level_name = os.getenv("LOG_LEVEL", DEFAULT_LOG_LEVEL).upper()
    return getattr(logging, level_name, logging.INFO)


def _create_rich_handler(log_level: int) -> RichHandler:
    """Create and configure a Rich handler for development logging.

    Args:
        log_level: The logging level to configure debug features for

    Returns:
        Configured RichHandler instance
    """

    console = Console(stderr=True)

    rich_handler = RichHandler(
        console=console,
        rich_tracebacks=True,
        tracebacks_show_locals=log_level <= logging.DEBUG,
        show_path=log_level <= logging.DEBUG,
        show_time=True,
        omit_repeated_times=False,
        markup=True,
    )

    rich_formatter = logging.Formatter(
        fmt="%(message)s",
        datefmt="[%X]",
    )

    rich_handler.setFormatter(rich_formatter)
    return rich_handler


def _create_standard_handler() -> logging.StreamHandler:
    """Create and configure a standard stream handler for production logging.

    Returns:
        Configured StreamHandler instance
    """

    stream_handler = logging.StreamHandler()

    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stream_handler.setFormatter(formatter)
    return stream_handler


def _suppress_verbose_loggers() -> None:
    """Suppress verbose logs from common third-party libraries."""

    for logger_name in SUPPRESSED_LOGGERS:
        logging.getLogger(logger_name).setLevel(logging.WARNING)


def configure_logging(enable_rich: bool = True) -> None:
    """Configure Rich logging with FastAPI best practices.

    Args:
        enable_rich: Whether to use Rich formatting. Set to False for production
                    environments where structured logging is preferred.
    """

    log_level = get_log_level()

    if enable_rich and not _is_ci_environment():
        handlers = [_create_rich_handler(log_level)]
    else:
        handlers = [_create_standard_handler()]

    # Configure root logger
    logging.basicConfig(
        level=log_level,
        handlers=handlers,
        force=True,  # Override any existing configuration
    )

    _suppress_verbose_loggers()
