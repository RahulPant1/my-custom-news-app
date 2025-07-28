"""Centralized configuration management for the news digest application."""

import os
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


@dataclass
class DatabaseConfig:
    """Database configuration settings."""
    path: str
    timeout: int = 30
    enable_wal_mode: bool = True
    connection_pool_size: int = 5
    
    @classmethod
    def from_env(cls) -> 'DatabaseConfig':
        """Create configuration from environment variables."""
        return cls(
            path=os.getenv('DATABASE_PATH', 'news_digest.db'),
            timeout=int(os.getenv('DB_TIMEOUT', '30')),
            enable_wal_mode=os.getenv('DB_WAL_MODE', 'true').lower() == 'true',
            connection_pool_size=int(os.getenv('DB_POOL_SIZE', '5'))
        )


@dataclass
class AIConfig:
    """AI service configuration settings."""
    primary_provider: str
    openai_api_key: Optional[str]
    anthropic_api_key: Optional[str]
    google_api_key: Optional[str]
    batch_size: int
    request_timeout: int
    max_retries: int
    use_batch_summaries: bool
    summary_batch_size: int
    
    @classmethod
    def from_env(cls) -> 'AIConfig':
        """Create configuration from environment variables."""
        # Auto-detect primary provider
        openai_key = os.getenv('OPENAI_API_KEY')
        anthropic_key = os.getenv('ANTHROPIC_API_KEY')
        google_key = os.getenv('GOOGLE_API_KEY')
        
        primary = os.getenv('PRIMARY_AI_PROVIDER', 'auto')
        if primary == 'auto':
            if google_key:
                primary = 'google'
            elif openai_key:
                primary = 'openai'
            elif anthropic_key:
                primary = 'anthropic'
            else:
                primary = None
        
        return cls(
            primary_provider=primary,
            openai_api_key=openai_key,
            anthropic_api_key=anthropic_key,
            google_api_key=google_key,
            batch_size=int(os.getenv('AI_BATCH_SIZE', '50')),
            request_timeout=int(os.getenv('AI_REQUEST_TIMEOUT', '30')),
            max_retries=int(os.getenv('AI_MAX_RETRIES', '3')),
            use_batch_summaries=os.getenv('AI_USE_BATCH_SUMMARIES', 'true').lower() == 'true',
            summary_batch_size=int(os.getenv('AI_SUMMARY_BATCH_SIZE', '8'))
        )
    
    def get_available_providers(self) -> List[str]:
        """Get list of available AI providers based on API keys."""
        providers = []
        if self.openai_api_key:
            providers.append('openai')
        if self.anthropic_api_key:
            providers.append('anthropic')
        if self.google_api_key:
            providers.append('google')
        return providers
    
    def is_provider_available(self, provider: str) -> bool:
        """Check if a specific provider is available."""
        return provider in self.get_available_providers()


@dataclass
class EmailConfig:
    """Email service configuration settings."""
    smtp_server: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    from_email: str
    from_name: str
    base_url: str
    use_tls: bool = True
    timeout: int = 30
    
    @classmethod
    def from_env(cls) -> 'EmailConfig':
        """Create configuration from environment variables."""
        return cls(
            smtp_server=os.getenv('SMTP_SERVER', 'smtp.gmail.com'),
            smtp_port=int(os.getenv('SMTP_PORT', '587')),
            smtp_username=os.getenv('SMTP_USERNAME', ''),
            smtp_password=os.getenv('SMTP_PASSWORD', ''),
            from_email=os.getenv('FROM_EMAIL', os.getenv('SMTP_USERNAME', '')),
            from_name=os.getenv('FROM_NAME', 'News Digest'),
            base_url=os.getenv('BASE_URL', 'http://localhost:5000'),
            use_tls=os.getenv('SMTP_USE_TLS', 'true').lower() == 'true',
            timeout=int(os.getenv('SMTP_TIMEOUT', '30'))
        )
    
    def is_configured(self) -> bool:
        """Check if email is properly configured."""
        return bool(
            self.smtp_username and 
            self.smtp_password and 
            self.from_email
        )
    
    def validate(self) -> Dict[str, Any]:
        """Validate email configuration."""
        errors = []
        
        if not self.smtp_username:
            errors.append("SMTP username is required")
        if not self.smtp_password:
            errors.append("SMTP password is required")
        if not self.from_email:
            errors.append("From email is required")
        if self.smtp_port < 1 or self.smtp_port > 65535:
            errors.append("SMTP port must be between 1 and 65535")
        
        # Basic email validation
        if self.from_email and '@' not in self.from_email:
            errors.append("From email format is invalid")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'smtp_server': self.smtp_server,
            'smtp_port': self.smtp_port,
            'from_email': self.from_email
        }


@dataclass
class AppConfig:
    """Application-wide configuration settings."""
    debug: bool
    log_level: str
    max_articles_per_digest: int
    default_digest_frequency: str
    default_output_format: str
    ai_categories: List[str]
    
    @classmethod
    def from_env(cls) -> 'AppConfig':
        """Create configuration from environment variables."""
        return cls(
            debug=os.getenv('DEBUG', 'false').lower() == 'true',
            log_level=os.getenv('LOG_LEVEL', 'INFO'),
            max_articles_per_digest=int(os.getenv('MAX_ARTICLES_PER_DIGEST', '20')),
            default_digest_frequency=os.getenv('DEFAULT_DIGEST_FREQUENCY', 'daily'),
            default_output_format=os.getenv('DEFAULT_OUTPUT_FORMAT', 'text'),
            ai_categories=[
                "Science & Discovery",
                "Technology & Gadgets", 
                "Health & Wellness",
                "Business & Finance",
                "Global Affairs",
                "Environment & Climate",
                "Good Vibes (Positive News)",
                "Pop Culture & Lifestyle",
                "For Young Minds (Youth-Focused)",
                "DIY, Skills & How-To"
            ]
        )


class ConfigManager:
    """Centralized configuration manager."""
    
    def __init__(self):
        """Initialize configuration manager."""
        self._database = None
        self._ai = None
        self._email = None
        self._app = None
    
    @property
    def database(self) -> DatabaseConfig:
        """Get database configuration."""
        if self._database is None:
            self._database = DatabaseConfig.from_env()
        return self._database
    
    @property
    def ai(self) -> AIConfig:
        """Get AI configuration."""
        if self._ai is None:
            self._ai = AIConfig.from_env()
        return self._ai
    
    @property
    def email(self) -> EmailConfig:
        """Get email configuration."""
        if self._email is None:
            self._email = EmailConfig.from_env()
        return self._email
    
    @property
    def app(self) -> AppConfig:
        """Get application configuration."""
        if self._app is None:
            self._app = AppConfig.from_env()
        return self._app
    
    def reload(self) -> None:
        """Reload all configurations from environment."""
        self._database = None
        self._ai = None
        self._email = None
        self._app = None
    
    def get_config_summary(self) -> Dict[str, Any]:
        """Get a summary of all configurations."""
        return {
            'database': {
                'path': self.database.path,
                'timeout': self.database.timeout,
                'pool_size': self.database.connection_pool_size
            },
            'ai': {
                'primary_provider': self.ai.primary_provider,
                'available_providers': self.ai.get_available_providers(),
                'batch_size': self.ai.batch_size,
                'use_batch_summaries': self.ai.use_batch_summaries
            },
            'email': {
                'configured': self.email.is_configured(),
                'server': self.email.smtp_server,
                'port': self.email.smtp_port,
                'from_email': self.email.from_email
            },
            'app': {
                'debug': self.app.debug,
                'log_level': self.app.log_level,
                'max_articles': self.app.max_articles_per_digest,
                'categories_count': len(self.app.ai_categories)
            }
        }


# Global configuration instance
config = ConfigManager()