"""Email configuration management with validation and type safety."""

import os
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass
from urllib.parse import urlparse

# Load environment variables directly
from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)


@dataclass
class SMTPConfig:
    """SMTP server configuration with validation."""
    
    server: str
    port: int
    username: str
    password: str
    from_email: str
    from_name: str
    use_tls: bool = True
    timeout: int = 30
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        self.validate()
    
    def validate(self) -> None:
        """Validate SMTP configuration."""
        if not self.server:
            raise ValueError("SMTP server is required")
        
        if not (1 <= self.port <= 65535):
            raise ValueError(f"Invalid SMTP port: {self.port}")
        
        if not self.username:
            raise ValueError("SMTP username is required")
        
        if not self.password:
            raise ValueError("SMTP password is required")
        
        if not self._is_valid_email(self.from_email):
            raise ValueError(f"Invalid from_email format: {self.from_email}")
        
        if not self.from_name.strip():
            raise ValueError("from_name cannot be empty")
    
    @staticmethod
    def _is_valid_email(email: str) -> bool:
        """Basic email validation."""
        return "@" in email and "." in email.split("@")[1]


@dataclass
class EmailServiceConfig:
    """Email service configuration."""
    
    smtp: SMTPConfig
    base_url: str
    template_dir: str = "templates/email"
    max_subject_length: int = 78
    max_content_length: int = 102400  # 100KB
    rate_limit_per_hour: int = 100
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        self.validate()
    
    def validate(self) -> None:
        """Validate email service configuration."""
        if not self.base_url:
            raise ValueError("base_url is required")
        
        # Validate base_url format
        try:
            parsed = urlparse(self.base_url)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError("Invalid base_url format")
        except Exception as e:
            raise ValueError(f"Invalid base_url: {e}")
        
        if self.max_subject_length < 10:
            raise ValueError("max_subject_length must be at least 10")
        
        if self.max_content_length < 1024:
            raise ValueError("max_content_length must be at least 1KB")
        
        if self.rate_limit_per_hour < 1:
            raise ValueError("rate_limit_per_hour must be positive")


class EmailConfigManager:
    """Manages email configuration with environment variable loading."""
    
    def __init__(self):
        self._config: Optional[EmailServiceConfig] = None
    
    def get_config(self) -> EmailServiceConfig:
        """Get email configuration, loading from environment if needed."""
        if self._config is None:
            self._config = self._load_from_environment()
        return self._config
    
    def _load_from_environment(self) -> EmailServiceConfig:
        """Load configuration from environment variables."""
        try:
            smtp_config = SMTPConfig(
                server=self._get_env_var("SMTP_SERVER", "smtp.gmail.com"),
                port=int(self._get_env_var("SMTP_PORT", "587")),
                username=self._get_env_var("SMTP_USERNAME", required=True),
                password=self._get_env_var("SMTP_PASSWORD", required=True),
                from_email=self._get_env_var("FROM_EMAIL", 
                                           fallback=self._get_env_var("SMTP_USERNAME", required=True)),
                from_name=self._get_env_var("FROM_NAME", "News Digest"),
                use_tls=self._get_env_bool("SMTP_USE_TLS", True),
                timeout=int(self._get_env_var("SMTP_TIMEOUT", "30"))
            )
            
            return EmailServiceConfig(
                smtp=smtp_config,
                base_url=self._get_env_var("BASE_URL", "http://localhost:5000"),
                template_dir=self._get_env_var("EMAIL_TEMPLATE_DIR", "templates/email"),
                max_subject_length=int(self._get_env_var("EMAIL_MAX_SUBJECT_LENGTH", "78")),
                max_content_length=int(self._get_env_var("EMAIL_MAX_CONTENT_LENGTH", "102400")),
                rate_limit_per_hour=int(self._get_env_var("EMAIL_RATE_LIMIT_PER_HOUR", "100"))
            )
            
        except Exception as e:
            logger.error(f"Failed to load email configuration: {e}")
            raise ValueError(f"Invalid email configuration: {e}")
    
    def _get_env_var(self, key: str, default: str = None, required: bool = False, fallback: str = None) -> str:
        """Get environment variable with validation."""
        value = os.getenv(key, default)
        
        if value is None and fallback:
            value = fallback
        
        if required and not value:
            raise ValueError(f"Required environment variable {key} is not set")
        
        return value or ""
    
    def _get_env_bool(self, key: str, default: bool = False) -> bool:
        """Get boolean environment variable."""
        value = os.getenv(key, str(default)).lower()
        return value in ("true", "1", "yes", "on")
    
    def validate_config(self) -> Dict[str, Any]:
        """Validate current configuration and return status."""
        try:
            config = self.get_config()
            return {
                "valid": True,
                "smtp_server": config.smtp.server,
                "smtp_port": config.smtp.port,
                "from_email": config.smtp.from_email,
                "base_url": config.base_url,
                "errors": []
            }
        except Exception as e:
            return {
                "valid": False,
                "errors": [str(e)]
            }


# Global configuration manager instance
email_config_manager = EmailConfigManager()


def get_email_config() -> EmailServiceConfig:
    """Get the global email configuration."""
    return email_config_manager.get_config()


def validate_email_setup() -> Dict[str, Any]:
    """Validate email setup and return detailed status."""
    return email_config_manager.validate_config()