"""Configuration settings for the news digest application."""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# AI Service Configuration
# API Keys (set in .env file)
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY') 
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

# AI Model Configuration
AI_MODELS = {
    'openai': {
        'default': 'gpt-3.5-turbo',
        'alternatives': ['gpt-4', 'gpt-4-turbo', 'gpt-3.5-turbo-16k'],
        'enabled': bool(OPENAI_API_KEY)
    },
    'anthropic': {
        'default': 'claude-3-haiku-20240307',
        'alternatives': ['claude-3-sonnet-20240229', 'claude-3-opus-20240229'],
        'enabled': bool(ANTHROPIC_API_KEY)
    },
    'google': {
        'default': 'gemini-2.5-flash',
        'alternatives': ['gemini-1.5-flash', 'gemini-1.5-pro'],
        'enabled': bool(GOOGLE_API_KEY)
    }
}

# Primary AI Provider (set via environment variable or use default)
# Options: 'openai', 'anthropic', 'google', 'auto'
PRIMARY_AI_PROVIDER = os.getenv('PRIMARY_AI_PROVIDER', 'auto')

# Auto-detect primary provider if not set
# Prioritize non-Google providers to avoid quota issues
if PRIMARY_AI_PROVIDER == 'auto':
    if OPENAI_API_KEY and AI_MODELS['openai']['enabled']:
        PRIMARY_AI_PROVIDER = 'openai'  
    elif ANTHROPIC_API_KEY and AI_MODELS['anthropic']['enabled']:
        PRIMARY_AI_PROVIDER = 'anthropic'
    elif GOOGLE_API_KEY and AI_MODELS['google']['enabled']:
        PRIMARY_AI_PROVIDER = 'google'
    else:
        PRIMARY_AI_PROVIDER = None

# AI Processing Settings
AI_BATCH_SIZE = int(os.getenv('AI_BATCH_SIZE', '50'))
AI_REQUEST_TIMEOUT = int(os.getenv('AI_REQUEST_TIMEOUT', '30'))
AI_MAX_RETRIES = int(os.getenv('AI_MAX_RETRIES', '3'))

# AI Batch Summarization Settings (for cost optimization)
AI_USE_BATCH_SUMMARIES = os.getenv('AI_USE_BATCH_SUMMARIES', 'true').lower() == 'true'
AI_SUMMARY_BATCH_SIZE = int(os.getenv('AI_SUMMARY_BATCH_SIZE', '8'))  # Articles per batch API call

# Legacy OpenAI config for backward compatibility
OPENAI_MODEL = AI_MODELS['openai']['default']

# Database Configuration
DATABASE_PATH = os.getenv('DATABASE_PATH', 'news_digest.db')

# Logging Configuration
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# AI Categories
AI_CATEGORIES = [
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

# RSS Feed Configuration - Now managed in database
# Use 'python main.py feeds list' to view current feeds
# Use 'python main.py feeds add <category> <url>' to add feeds

# Application Settings
MAX_ARTICLES_PER_DIGEST = 20
DEFAULT_DIGEST_FREQUENCY = 'daily'
DEFAULT_OUTPUT_FORMAT = 'text'