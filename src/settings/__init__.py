"""Configuration management module."""

import os

# Legacy config imports for backward compatibility
DATABASE_PATH = os.getenv('DATABASE_PATH', 'news_digest.db')

# AI Service Configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY', '')

# User interface defaults
DEFAULT_DIGEST_FREQUENCY = 'daily'
DEFAULT_OUTPUT_FORMAT = 'text'
MAX_ARTICLES_PER_DIGEST = 50

AI_CATEGORIES = [
    'Science & Discovery',
    'Technology & Gadgets', 
    'Health & Wellness',
    'Business & Finance',
    'Global Affairs',
    'Environment & Climate',
    'Good Vibes (Positive News)',
    'Pop Culture & Lifestyle',
    'For Young Minds (Youth-Focused)',
    'DIY, Skills & How-To'
]

from .email_config import (
    SMTPConfig,
    EmailServiceConfig,
    EmailConfigManager,
    get_email_config,
    validate_email_setup
)

__all__ = [
    'DATABASE_PATH',
    'OPENAI_API_KEY',
    'OPENAI_MODEL', 
    'ANTHROPIC_API_KEY',
    'GOOGLE_API_KEY',
    'DEFAULT_DIGEST_FREQUENCY',
    'DEFAULT_OUTPUT_FORMAT',
    'MAX_ARTICLES_PER_DIGEST',
    'AI_CATEGORIES',
    'SMTPConfig',
    'EmailServiceConfig', 
    'EmailConfigManager',
    'get_email_config',
    'validate_email_setup'
]