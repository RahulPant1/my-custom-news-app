# Codebase Structure

## Root Directory
```
my_custom_news_app/
├── main.py                    # CLI entry point with Click commands
├── config.py                  # Application configuration and constants
├── requirements.txt           # Python dependencies
├── README.md                  # Comprehensive project documentation
├── CLAUDE.md                  # AI assistant instructions and guidelines
├── .env.example              # Environment variable template
└── setup_cron.sh             # Cron job setup script
```

## Source Code (src/)
```
src/
├── core/                     # Core functionality and exceptions
│   ├── exceptions.py         # Custom exception classes
│   └── config_manager.py     # Configuration management
├── utils/                    # Utility functions and helpers
│   ├── common.py            # Common utility functions
│   └── logging.py           # Logging configuration
├── collectors/              # RSS feed collection
│   └── article_collector_refactored.py
├── services/                # Service layer classes
│   ├── email_service.py     # Email delivery services
│   ├── email_manager.py     # Email management
│   └── unified_email_service.py
├── templates/               # Email template management
│   └── email_templates.py   # HTML email templates
├── settings/                # Configuration modules
│   ├── email_config.py      # Email configuration
│   └── __init__.py          # Settings constants
├── llm_router/              # AI service routing and management
│   ├── llm_router.py        # Main router logic
│   ├── usage_tracker.py     # API usage tracking
│   └── providers/           # AI provider adapters
├── repositories/            # Data access layer
│   └── email_repository.py  # Email-related database operations
```

## Key Source Files
- **database.py** - Core database operations and schema management
- **collector.py** - RSS feed collection and processing
- **enhanced_ai_processor.py** - AI processing with multi-provider support
- **user_interface.py** - User management and digest generation
- **web_interface.py** - Flask web application with modern UI
- **ai_adapters.py** - AI service adapters and response handling

## Web Interface (templates/ & static/)
```
templates/
├── base.html                # Base template with modern design
├── home.html               # Dashboard interface
├── operations.html         # Operations dashboard
├── user_management.html    # User management interface
├── create_user.html        # User creation form
└── digest.html             # Digest viewing template

static/                     # CSS, JS, and static assets
```

## Testing Structure
```
tests/
├── test_database.py         # Database operations testing
├── test_collector.py        # RSS collection testing  
├── test_enhanced_ai_processor.py # AI processing testing
├── test_user_interface.py   # User management testing
├── test_web_interface.py    # Web interface testing
├── test_email_system.py     # Email delivery testing
└── test_ai_adapters.py      # AI adapter testing
```

## Data and Logs
```
data/                       # Data storage directory
logs/                       # Application logs
news_digest.db             # SQLite database file
usage_counters.json        # AI API usage tracking
```

## Configuration Files
- **.env** - Environment variables (API keys, SMTP settings)
- **ai_config.yaml** - AI model configuration
- **prd.md** - Product requirements documentation
- **ARCHITECTURE.md** - System architecture documentation