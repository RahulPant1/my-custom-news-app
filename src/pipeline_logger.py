"""Shared pipeline logging utility for CLI and web interface."""

import os
import json
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class PipelineLogger:
    """Shared logging utility for pipeline execution."""
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.logs_dir = os.path.join(os.path.dirname(__file__), '..', 'logs')
        self.log_file = os.path.join(self.logs_dir, f'pipeline_{user_id}.json')
        os.makedirs(self.logs_dir, exist_ok=True)
    
    def log(self, message: str, status: str = 'info', step: Optional[str] = None):
        """Add a log entry to the pipeline log file."""
        timestamp = datetime.now()
        log_entry = {
            'timestamp': timestamp.isoformat(),
            'message': message,
            'status': status,
            'step': step,
            'formatted': f'[{timestamp.strftime("%H:%M:%S")}] {message}'
        }
        
        try:
            # Read existing logs
            existing_logs = []
            if os.path.exists(self.log_file):
                try:
                    with open(self.log_file, 'r') as f:
                        existing_logs = json.load(f)
                except (json.JSONDecodeError, FileNotFoundError):
                    existing_logs = []
            
            # Add new log
            existing_logs.append(log_entry)
            
            # Keep only last 100 logs
            if len(existing_logs) > 100:
                existing_logs = existing_logs[-100:]
            
            # Write back to file
            with open(self.log_file, 'w') as f:
                json.dump(existing_logs, f, indent=2)
                
            # Also log to standard logger
            logger.info(f"Pipeline log for {self.user_id}: {message}")
            
        except Exception as e:
            logger.error(f"Failed to write pipeline log: {e}")
    
    def clear(self):
        """Clear all logs for this user."""
        try:
            if os.path.exists(self.log_file):
                os.remove(self.log_file)
        except Exception as e:
            logger.error(f"Failed to clear pipeline logs: {e}")
    
    def info(self, message: str, step: Optional[str] = None):
        """Log an info message."""
        self.log(message, 'info', step)
    
    def success(self, message: str, step: Optional[str] = None):
        """Log a success message."""
        self.log(message, 'success', step)
    
    def warning(self, message: str, step: Optional[str] = None):
        """Log a warning message."""
        self.log(message, 'warning', step)
    
    def error(self, message: str, step: Optional[str] = None):
        """Log an error message."""
        self.log(message, 'error', step)
    
    def running(self, message: str, step: Optional[str] = None):
        """Log a running status message."""
        self.log(message, 'running', step)