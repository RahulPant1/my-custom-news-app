"""Enhanced logging utilities for the news digest application."""

import logging
import sys
import os
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path
import json
import traceback


class StructuredFormatter(logging.Formatter):
    """Custom formatter that outputs structured JSON logs."""
    
    def __init__(self, include_traceback: bool = True):
        super().__init__()
        self.include_traceback = include_traceback
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON."""
        log_entry = {
            'timestamp': datetime.utcfromtimestamp(record.created).isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Add extra fields if present
        if hasattr(record, 'user_id'):
            log_entry['user_id'] = record.user_id
        if hasattr(record, 'article_id'):
            log_entry['article_id'] = record.article_id
        if hasattr(record, 'feed_url'):
            log_entry['feed_url'] = record.feed_url
        if hasattr(record, 'category'):
            log_entry['category'] = record.category
        if hasattr(record, 'operation'):
            log_entry['operation'] = record.operation
        if hasattr(record, 'duration'):
            log_entry['duration_ms'] = record.duration
        
        # Add exception info if present
        if record.exc_info and self.include_traceback:
            log_entry['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': traceback.format_exception(*record.exc_info)
            }
        
        return json.dumps(log_entry)


class ColoredFormatter(logging.Formatter):
    """Formatter that adds colors to console output."""
    
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors."""
        color = self.COLORS.get(record.levelname, '')
        
        # Format basic message
        formatted = f"{color}[{record.levelname}]{self.RESET} "
        formatted += f"{record.name}: {record.getMessage()}"
        
        # Add context if available
        context_parts = []
        if hasattr(record, 'user_id'):
            context_parts.append(f"user={record.user_id}")
        if hasattr(record, 'operation'):
            context_parts.append(f"op={record.operation}")
        if hasattr(record, 'duration'):
            context_parts.append(f"dur={record.duration}ms")
        
        if context_parts:
            formatted += f" [{', '.join(context_parts)}]"
        
        # Add location info for errors
        if record.levelno >= logging.ERROR:
            formatted += f" ({record.module}:{record.lineno})"
        
        return formatted


class NewsDigestLogger:
    """Enhanced logger for the news digest application."""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self._setup_done = False
    
    def setup_logging(
        self,
        level: str = "INFO",
        log_file: Optional[str] = None,
        enable_console: bool = True,
        structured_format: bool = False
    ) -> None:
        """Set up logging configuration."""
        if self._setup_done:
            return
        
        # Set level
        numeric_level = getattr(logging, level.upper(), logging.INFO)
        self.logger.setLevel(numeric_level)
        
        # Clear existing handlers
        self.logger.handlers.clear()
        
        # Console handler
        if enable_console:
            console_handler = logging.StreamHandler(sys.stdout)
            if structured_format:
                console_handler.setFormatter(StructuredFormatter())
            else:
                console_handler.setFormatter(ColoredFormatter())
            self.logger.addHandler(console_handler)
        
        # File handler
        if log_file:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(StructuredFormatter())
            self.logger.addHandler(file_handler)
        
        self._setup_done = True
    
    def operation_start(self, operation: str, **context) -> Dict[str, Any]:
        """Log operation start and return context for tracking."""
        start_time = datetime.now()
        log_context = {
            'operation': operation,
            'start_time': start_time,
            **context
        }
        
        self.info(f"Starting operation: {operation}", extra=log_context)
        return log_context
    
    def operation_end(self, context: Dict[str, Any], success: bool = True, **extra) -> None:
        """Log operation end with duration."""
        if 'start_time' in context:
            duration = (datetime.now() - context['start_time']).total_seconds() * 1000
            context['duration'] = int(duration)
        
        operation = context.get('operation', 'unknown')
        status = "completed" if success else "failed"
        
        log_extra = {**context, **extra}
        if success:
            self.info(f"Operation {operation} {status}", extra=log_extra)
        else:
            self.error(f"Operation {operation} {status}", extra=log_extra)
    
    def user_action(self, user_id: str, action: str, **context) -> None:
        """Log user action."""
        self.info(f"User action: {action}", extra={'user_id': user_id, **context})
    
    def article_processed(self, article_id: int, operation: str, **context) -> None:
        """Log article processing."""
        self.info(f"Article {operation}", extra={'article_id': article_id, 'operation': operation, **context})
    
    def feed_processed(self, feed_url: str, result: str, **context) -> None:
        """Log feed processing."""
        self.info(f"Feed processing {result}", extra={'feed_url': feed_url, 'operation': 'feed_process', **context})
    
    def ai_request(self, provider: str, model: str, tokens: Optional[int] = None, cost: Optional[float] = None) -> None:
        """Log AI service request."""
        extra = {'operation': 'ai_request', 'provider': provider, 'model': model}
        if tokens:
            extra['tokens'] = tokens
        if cost:
            extra['cost'] = cost
        
        self.info(f"AI request to {provider}/{model}", extra=extra)
    
    def email_sent(self, user_id: str, email: str, subject: str, success: bool = True) -> None:
        """Log email delivery."""
        extra = {
            'user_id': user_id,
            'email': email,
            'subject': subject,
            'operation': 'email_delivery'
        }
        
        if success:
            self.info("Email sent successfully", extra=extra)
        else:
            self.error("Email delivery failed", extra=extra)
    
    def database_query(self, query_type: str, table: str, duration_ms: Optional[int] = None) -> None:
        """Log database query."""
        extra = {
            'operation': 'database_query',
            'query_type': query_type,
            'table': table
        }
        if duration_ms:
            extra['duration'] = duration_ms
        
        self.debug(f"Database {query_type} on {table}", extra=extra)
    
    def security_event(self, event_type: str, user_id: Optional[str] = None, **context) -> None:
        """Log security-related events."""
        extra = {
            'operation': 'security_event',
            'event_type': event_type,
            **context
        }
        if user_id:
            extra['user_id'] = user_id
        
        self.warning(f"Security event: {event_type}", extra=extra)
    
    def performance_metric(self, metric_name: str, value: float, unit: str = "ms") -> None:
        """Log performance metrics."""
        self.info(f"Performance: {metric_name}={value}{unit}", extra={
            'operation': 'performance_metric',
            'metric_name': metric_name,
            'value': value,
            'unit': unit
        })
    
    # Standard logging methods with context support
    def debug(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """Log debug message."""
        self.logger.debug(message, extra=extra or {})
    
    def info(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """Log info message."""
        self.logger.info(message, extra=extra or {})
    
    def warning(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """Log warning message."""
        self.logger.warning(message, extra=extra or {})
    
    def error(self, message: str, extra: Optional[Dict[str, Any]] = None, exc_info: bool = False) -> None:
        """Log error message."""
        self.logger.error(message, extra=extra or {}, exc_info=exc_info)
    
    def exception(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """Log exception with traceback."""
        self.logger.exception(message, extra=extra or {})
    
    def critical(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """Log critical message."""
        self.logger.critical(message, extra=extra or {})


def get_logger(name: str) -> NewsDigestLogger:
    """Get a logger instance for the given name."""
    return NewsDigestLogger(name)


def setup_application_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    structured_format: bool = False
) -> None:
    """Set up application-wide logging configuration."""
    # Set up root logger
    root_logger = get_logger('news_digest')
    root_logger.setup_logging(
        level=level,
        log_file=log_file,
        structured_format=structured_format
    )
    
    # Reduce noise from external libraries
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('feedparser').setLevel(logging.WARNING)


# Context manager for operation tracking
class OperationTracker:
    """Context manager for tracking operations with automatic logging."""
    
    def __init__(self, logger: NewsDigestLogger, operation: str, **context):
        self.logger = logger
        self.operation = operation
        self.context = context
        self.start_context = None
    
    def __enter__(self):
        self.start_context = self.logger.operation_start(self.operation, **self.context)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        success = exc_type is None
        self.logger.operation_end(self.start_context, success=success)
        return False  # Don't suppress exceptions