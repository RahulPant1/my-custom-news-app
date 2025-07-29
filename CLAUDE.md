# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a mature CLI-based personalized news digest generator with both command-line and web interfaces. The system features two main operational modules:

1. **Collector Module** - Automated processing that fetches articles from RSS feeds, uses AI to classify into 10 predefined categories, generates summaries, and stores enriched content
2. **User Interface Module** - Retrieves from processed database and delivers personalized digests in text, Markdown, email-ready formats, or via web interface

## Architecture

The application implements a sophisticated multi-module architecture:

- **Collector Module**: RSS feeds → AI processing (classify, summarize, trend detect) → Deduplication → Database storage
- **User Interface Module**: User preferences → Article retrieval → Personalized digest generation → Multi-format output
- **Web Interface**: Flask-based admin panel with user management, pipeline monitoring, and digest preview
- **Background Jobs**: Asynchronous task processing with job queuing and status tracking
- **LLM Router**: Multi-provider AI system supporting OpenAI, Anthropic, Google, Groq, Ollama, and OpenRouter
- **Caching Layer**: Redis-based caching for performance optimization
- **Monitoring System**: Comprehensive logging, metrics collection, and health checking

## AI Categories System

Articles are classified (multi-label possible) into 10 predefined categories:
1. Science & Discovery
2. Technology & Gadgets  
3. Health & Wellness
4. Business & Finance
5. Global Affairs
6. Environment & Climate
7. Good Vibes (Positive News)
8. Pop Culture & Lifestyle
9. For Young Minds (Youth-Focused)
10. DIY, Skills & How-To

## Data Schema

**Articles Table**: id, title, author, publication_date, source_link, original_summary, rss_category, ai_categories (multi-label), ai_summary, trending_flag, date_collected

**User Preferences Table**: user_id, email, selected_categories, digest_frequency, articles_per_digest, preferred_output_format, feedback_history

**Additional Tables**: rss_feeds, feed_tracking, email_deliveries, feedback_history, engagement_metrics, email_preferences, daily_oneliners, stock_images

## Technical Implementation

### Core Components
- **Database**: SQLite with connection pooling and optimization
- **AI Processing**: Multi-provider LLM integration with usage tracking
- **Email System**: Multiple template support with SMTP configuration
- **Web Interface**: Flask application with comprehensive admin features
- **Background Processing**: Job queue system with priority handling
- **Security**: Middleware for input validation and rate limiting
- **Caching**: Redis integration for performance optimization

### Key Features Implemented
- RSS feed validation and management
- Incremental article collection
- AI-powered categorization and summarization
- Email template system with multiple layouts
- Web-based administration panel
- Pipeline monitoring and logging
- User feedback collection
- Background job processing
- Image extraction and caching
- Daily one-liner generation

## RSS Feed Integration

Each category maps to 5 curated RSS feeds managed through the web interface. RSS endpoints are validated for XML validity and accessibility with comprehensive error handling.

## Web Interface Components

### Templates (templates/)
- **Base Layout**: base.html
- **User Management**: user_management.html, create_user.html, edit_user.html, user_profile.html
- **Content Views**: digest.html, articles_dashboard.html, categories.html
- **Operations**: operations.html, rss_management.html
- **Debug Tools**: debug_user_management.html
- **Core Pages**: home.html, index.html, error.html

### Static Assets (static/)
- **Styling**: style.css
- **JavaScript**: script.js

## Testing Strategy

Comprehensive test suite implemented in tests/ directory:
- **RSS Feed Validation**: test_rss_validator.py
- **Collector Module**: test_collector.py, test_incremental_collector.py
- **Database Operations**: test_database.py
- **AI Processing**: test_ai_adapters.py, test_enhanced_ai_processor.py
- **User Interface**: test_user_interface.py, test_interactive_interface.py
- **Email System**: test_email_system.py

## Development Commands

Common development and testing commands:
- **Run Web Interface**: `python run_web_dev.py` (development) or `python run_web.py` (production)
- **Execute Pipeline**: `python main.py`
- **Run Tests**: `pytest tests/`
- **Validate RSS Feeds**: `python -m src.rss_validator`
- **Setup Cron Jobs**: `./setup_cron.sh`

## Development Status

This is a **mature, feature-complete project** with:
- ✅ Full implementation of both CLI and web interfaces
- ✅ Comprehensive test suite
- ✅ Production-ready configurations
- ✅ Multi-provider AI integration
- ✅ Background job processing
- ✅ Email delivery system
- ✅ Web-based administration
- ✅ Monitoring and logging systems
- ✅ Caching and performance optimization