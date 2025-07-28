# News Digest Generator - Architecture & Technical Documentation

## Table of Contents
1. [System Overview](#system-overview)
2. [Architecture Design](#architecture-design)
3. [Core Components](#core-components)
4. [Data Flow](#data-flow)
5. [Database Schema](#database-schema)
6. [AI Integration](#ai-integration)
7. [API Endpoints](#api-endpoints)
8. [Deployment & Setup](#deployment--setup)
9. [Configuration](#configuration)
10. [Error Handling & Monitoring](#error-handling--monitoring)

---

## System Overview

The News Digest Generator is a comprehensive CLI and web-based application that automates the collection, AI-powered processing, and personalized delivery of news articles. The system is built around a two-module architecture optimized for scalability and maintainability.

### Key Features
- **Automated RSS Feed Collection**: Fetches from multiple news sources
- **AI-Powered Processing**: Multi-provider LLM routing for categorization and summarization
- **Personalized Digests**: User preference-based content curation
- **Multiple Output Formats**: Text, Markdown, and HTML email formats
- **Web Interface**: Mobile-responsive dashboard for management
- **Batch Processing**: Cost-optimized AI operations
- **Duplicate Detection**: Content deduplication across sources

---

## Architecture Design

### High-Level Architecture

```
┌─────────────────────┐    ┌──────────────────────┐    ┌─────────────────────┐
│   Collector Module  │    │   AI Processing      │    │  User Interface     │
│                     │    │                      │    │                     │
│ ┌─────────────────┐ │    │ ┌──────────────────┐ │    │ ┌─────────────────┐ │
│ │ RSS Feeds       │ │───▶│ │ LLM Router       │ │───▶│ │ CLI Interface   │ │
│ │ - Feed Parser   │ │    │ │ - Multi-provider │ │    │ │ - Click CLI     │ │
│ │ - Deduplication │ │    │ │ - Fallback Logic │ │    │ │ - Commands      │ │
│ │ - Image Extract │ │    │ │ - Usage Tracking │ │    │ │                 │ │
│ └─────────────────┘ │    │ └──────────────────┘ │    │ └─────────────────┘ │
│                     │    │                      │    │                     │
│ ┌─────────────────┐ │    │ ┌──────────────────┐ │    │ ┌─────────────────┐ │
│ │ Incremental     │ │    │ │ Enhanced AI      │ │    │ │ Web Interface   │ │
│ │ Collection      │ │    │ │ Processor        │ │    │ │ - Flask App     │ │
│ │                 │ │    │ │ - Categorization │ │    │ │ - Dashboard     │ │
│ └─────────────────┘ │    │ │ - Summarization  │ │    │ │ - User Mgmt     │ │
└─────────────────────┘    │ │ - Trend Detection│ │    │ └─────────────────┘ │
                           │ └──────────────────┘ │    └─────────────────────┘
                           └──────────────────────┘
                                     │
                           ┌──────────────────────┐
                           │   Central Database   │
                           │                      │
                           │ ┌──────────────────┐ │
                           │ │ Articles Table   │ │
                           │ │ Users Table      │ │
                           │ │ Feeds Table      │ │
                           │ │ Email Queue      │ │
                           │ └──────────────────┘ │
                           └──────────────────────┘
```

### Module Responsibilities

#### 1. Collector Module
- **RSS Feed Management**: Fetches and validates RSS feeds
- **Content Processing**: Extracts article metadata and content
- **Deduplication**: Prevents duplicate articles using content hashing
- **Image Extraction**: Downloads and caches article images
- **Incremental Updates**: Efficient updates without full re-processing

#### 2. AI Processing Layer
- **Multi-Provider LLM Routing**: Supports OpenAI, Anthropic, Google, Groq, OpenRouter, Ollama
- **Intelligent Fallback**: Automatic provider switching on failures
- **Batch Processing**: Cost-optimized batch operations
- **Category Classification**: Multi-label categorization into 10 predefined categories
- **Summarization**: Generates concise AI summaries
- **Trend Detection**: Identifies trending topics

#### 3. User Interface Module
- **Preference Management**: User category preferences and settings management
- **Digest Generation**: Personalized content curation
- **Multiple Output Formats**: Text, Markdown, HTML email
- **CLI Interface**: Comprehensive command-line tools
- **Web Dashboard**: Mobile-responsive management interface

---

## Core Components

### 1. DatabaseManager (`src/database.py`)
**Purpose**: Centralized database operations for articles, users, and system data

**Key Methods**:
- `init_database()`: Creates database schema
- `store_article()`: Stores/updates articles with deduplication
- `get_user_preferences()`: Retrieves user settings
- `get_personalized_articles()`: Fetches articles based on user preferences

**Database Tables**:
- `articles`: Core article storage with AI categories and summaries
- `user_preferences`: User settings and category preferences
- `rss_feeds`: RSS feed configurations by category
- `email_queue`: Pending email deliveries
- `user_engagement`: User feedback and interaction tracking

### 2. ArticleCollector (`src/collector.py`)
**Purpose**: RSS feed collection and article processing

**Key Features**:
- HTTP session management with proper user agents
- Content hash generation for deduplication
- Image extraction and caching
- Error handling with retry logic
- Feed validation and metadata extraction

### 3. IncrementalCollector (`src/incremental_collector.py`)
**Purpose**: Efficient incremental article collection

**Key Features**:
- ETag and Last-Modified header support
- Differential updates to avoid re-processing
- Batch processing for performance
- Comprehensive error reporting

### 4. LLMRouter (`src/llm_router/llm_router.py`)
**Purpose**: Multi-provider AI service management

**Supported Providers**:
- OpenAI (GPT-3.5, GPT-4 variants)
- Anthropic (Claude models)
- Google (Gemini models)
- Groq (Fast inference)
- OpenRouter (Multiple model access)
- Ollama (Local models)

**Key Features**:
- Automatic failover between providers
- Usage tracking and cost monitoring
- Circuit breaker pattern for provider failures
- Rate limit handling with exponential backoff

### 5. EnhancedAIProcessor (`src/enhanced_ai_processor.py`)
**Purpose**: AI-powered content processing

**Processing Pipeline**:
1. **Classification**: Multi-label categorization into 10 categories
2. **Summarization**: Batch processing for cost efficiency
3. **Trend Detection**: Identifies emerging topics
4. **Quality Scoring**: Content relevance assessment

### 6. UserPreferencesManager (`src/user_interface.py`)
**Purpose**: User management and preference handling

**Features**:
- User creation with customizable preferences
- Category selection from 10 predefined categories
- Digest frequency and format preferences
- Engagement tracking and feedback processing

### 7. Web Interface (`src/web_interface.py`)
**Purpose**: Flask-based web dashboard

**Key Routes**:
- `/`: Dashboard home with system overview
- `/users`: User management interface
- `/articles`: Article browser with filtering
- `/categories`: Category management
- `/operations`: System operations (collect, process, send)

---

## Data Flow

### 1. Article Collection Flow
```
RSS Feeds → Feed Parser → Content Extraction → Deduplication → Database Storage
    ↓
Image URLs → Image Extractor → Image Cache → Database Update
```

### 2. AI Processing Flow
```
Unprocessed Articles → Batch Formation → LLM Router → Provider Selection → AI Processing
    ↓
Classification Results → Summarization → Trend Detection → Database Update
```

### 3. Digest Generation Flow
```
User Preferences → Article Filter → Category Grouping → Format Selection → Output Generation
    ↓
Email Template → SMTP Delivery → Engagement Tracking
```

---

## Database Schema

### Articles Table
```sql
CREATE TABLE articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    author TEXT,
    publication_date TEXT,
    source_link TEXT UNIQUE NOT NULL,
    original_summary TEXT,
    rss_category TEXT,
    ai_categories TEXT,  -- JSON array of categories
    ai_summary TEXT,
    trending_flag BOOLEAN DEFAULT FALSE,
    date_collected TEXT DEFAULT CURRENT_TIMESTAMP,
    content_hash TEXT UNIQUE,
    image_url TEXT,
    engagement_score REAL DEFAULT 0.0
);
```

### User Preferences Table
```sql
CREATE TABLE user_preferences (
    user_id TEXT PRIMARY KEY,
    email TEXT UNIQUE,
    selected_categories TEXT,  -- JSON array
    digest_frequency TEXT DEFAULT 'daily',
    articles_per_digest INTEGER DEFAULT 10,
    preferred_output_format TEXT DEFAULT 'text',
    feedback_history TEXT DEFAULT '{}',
    date_created TEXT DEFAULT CURRENT_TIMESTAMP
);
```

### RSS Feeds Table
```sql
CREATE TABLE rss_feeds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    url TEXT UNIQUE NOT NULL,
    title TEXT,
    last_fetched TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    error_count INTEGER DEFAULT 0
);
```

---

## AI Integration

### Category System
The system uses 10 predefined categories for article classification:

1. **Science & Discovery**: Research, scientific breakthroughs, space
2. **Technology & Gadgets**: Tech news, products, innovations
3. **Health & Wellness**: Medical news, fitness, mental health
4. **Business & Finance**: Markets, economics, corporate news
5. **Global Affairs**: International news, politics, diplomacy
6. **Environment & Climate**: Climate change, sustainability, nature
7. **Good Vibes (Positive News)**: Uplifting stories, achievements
8. **Pop Culture & Lifestyle**: Entertainment, trends, culture
9. **For Young Minds (Youth-Focused)**: Education, youth interests
10. **DIY, Skills & How-To**: Tutorials, learning, crafts

### AI Processing Pipeline

1. **Batch Formation**: Articles grouped for efficient processing
2. **Provider Selection**: LLM Router selects optimal provider
3. **Classification Request**: Multi-label categorization prompt
4. **Summarization Request**: Batch summarization for cost efficiency
5. **Result Processing**: Parse and store AI responses
6. **Error Handling**: Retry logic with exponential backoff

### Cost Optimization Strategies

- **Batch Processing**: Multiple articles per API call
- **Provider Fallback**: Switch to cheaper providers when possible
- **Usage Tracking**: Monitor costs across providers
- **Smart Caching**: Avoid re-processing unchanged content

---

## API Endpoints

### CLI Commands
```bash
# Setup and configuration
news setup                          # Initial system setup
news web                           # Start web interface

# Article collection
news collect                       # Collect new articles
news collect -n 20                # Collect 20 articles per feed
news process                       # AI process articles

# User management
news user add email@domain.com     # Create new user
news user list                     # List all users
news user show user_id            # Show user details
news user edit user_id --count 15 # Edit user preferences

# Digest operations
news send user_id                  # Send digest to user
news run user_id                   # Full pipeline (collect + process + send)
news preview user_id               # Preview digest without sending

# Development commands
news dev db-stats                  # Database statistics
news dev test-email user_id        # Test email configuration
```

### Web Interface Routes
```python
# Main interface
GET  /                            # Dashboard home
GET  /articles                    # Article browser
GET  /categories                  # Category management

# User management
GET  /users                       # User list
GET  /users/create               # Create user form
POST /users/create               # Create user action
GET  /users/<user_id>/edit       # Edit user form
POST /users/<user_id>/edit       # Update user action

# Operations
POST /operations/collect          # Trigger collection
POST /operations/process          # Trigger AI processing
POST /operations/send_digest      # Send digest to user

# API endpoints
GET  /api/articles                # Get articles (JSON)
GET  /api/users                   # Get users (JSON)
POST /api/users/<user_id>/feedback # Submit user feedback
```

---

## Deployment & Setup

### Prerequisites
- Python 3.8+
- SQLite3
- Internet connection for RSS feeds and AI services

### Installation Steps

1. **Clone Repository**
```bash
git clone <repository-url>
cd my_custom_news_app
```

2. **Install Dependencies**
```bash
pip install -r requirements.txt
```

3. **Environment Configuration**
```bash
# Create .env file with API keys
echo "OPENAI_API_KEY=your_key_here" > .env
echo "ANTHROPIC_API_KEY=your_key_here" >> .env
echo "GOOGLE_API_KEY=your_key_here" >> .env
```

4. **Initial Setup**
```bash
python main.py setup
```

5. **Create User**
```bash
python main.py user add your@email.com
```

6. **Start Web Interface**
```bash
python main.py web
```

### Production Deployment

#### Using systemd (Linux)
```ini
[Unit]
Description=News Digest Generator
After=network.target

[Service]
Type=simple
User=news
WorkingDirectory=/opt/news-digest
ExecStart=/opt/news-digest/venv/bin/python main.py web
Restart=always

[Install]
WantedBy=multi-user.target
```

#### Cron Jobs for Automation
```bash
# Collect articles every hour
0 * * * * /opt/news-digest/venv/bin/python /opt/news-digest/main.py collect

# Process with AI every 4 hours
0 */4 * * * /opt/news-digest/venv/bin/python /opt/news-digest/main.py process

# Send daily digests at 8 AM
0 8 * * * /opt/news-digest/venv/bin/python /opt/news-digest/scripts/send_all_digests.py
```

---

## Configuration

### AI Configuration (`ai_config.yaml`)
```yaml
providers:
  openai:
    enabled: true
    api_key: "${OPENAI_API_KEY}"
    default_model: "gpt-3.5-turbo"
    max_requests_per_minute: 60
    
  anthropic:
    enabled: true
    api_key: "${ANTHROPIC_API_KEY}"
    default_model: "claude-3-haiku-20240307"
    max_requests_per_minute: 50
    
  google:
    enabled: true
    api_key: "${GOOGLE_API_KEY}"
    default_model: "gemini-2.5-flash"
    max_requests_per_minute: 15

routing:
  primary_provider: "openai"
  fallback_order: ["anthropic", "google"]
  max_retries: 3
  circuit_breaker_threshold: 5
```

### Application Configuration (`config.py`)
```python
# Database
DATABASE_PATH = 'news_digest.db'

# AI Processing
AI_BATCH_SIZE = 50
AI_REQUEST_TIMEOUT = 30
AI_USE_BATCH_SUMMARIES = True
AI_SUMMARY_BATCH_SIZE = 8

# Application Settings
MAX_ARTICLES_PER_DIGEST = 20
DEFAULT_DIGEST_FREQUENCY = 'daily'
DEFAULT_OUTPUT_FORMAT = 'text'
```

### Email Configuration
```python
# SMTP Settings (in .env file)
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
SMTP_USERNAME = 'your_email@gmail.com'
SMTP_PASSWORD = 'your_app_password'
SMTP_FROM_EMAIL = 'news@yourdomain.com'
SMTP_FROM_NAME = 'News Digest Generator'
```

---

## Error Handling & Monitoring

### Logging System
The application uses Python's logging framework with multiple levels:

- **DEBUG**: Detailed debugging information
- **INFO**: General system operations
- **WARNING**: Potential issues that don't stop execution
- **ERROR**: Error conditions that affect functionality
- **CRITICAL**: Serious errors that may cause system failure

### Error Recovery Strategies

1. **Network Failures**: Automatic retry with exponential backoff
2. **AI Provider Failures**: Fallback to alternative providers
3. **Database Errors**: Transaction rollback and retry logic
4. **Email Delivery Failures**: Queue system with retry attempts

### Monitoring & Metrics

#### System Health Checks
- Database connectivity
- RSS feed accessibility
- AI provider availability
- Email server connectivity

#### Performance Metrics
- Article collection rate
- AI processing time
- Email delivery success rate
- User engagement metrics

#### Cost Monitoring
- AI API usage per provider
- Cost per article processed
- Monthly spending trends
- Usage optimization recommendations

### Troubleshooting Common Issues

#### RSS Feed Issues
```bash
# Test specific feed
python main.py dev test-feed <feed_url>

# Validate all feeds
python main.py dev validate-feeds
```

#### AI Processing Issues
```bash
# Check AI provider status
python main.py dev test-ai

# Reprocess failed articles
python main.py process --retry-failed
```

#### Email Delivery Issues
```bash
# Test email configuration
python main.py dev test-email <user_id>

# Check email queue
python main.py dev email-queue-status
```

---

## Performance Considerations

### Database Optimization
- Indexed columns for fast queries
- Connection pooling for web interface
- Batch operations for bulk updates
- Regular VACUUM operations for SQLite

### Memory Management
- Streaming RSS feed processing
- Limited batch sizes for AI processing
- Image caching with size limits
- Garbage collection optimization

### Scalability Features
- Modular architecture for component scaling
- Database-agnostic design (SQLite for development, PostgreSQL for production)
- Microservice-ready component separation
- Horizontal scaling capability through load balancing

---

This documentation provides a comprehensive overview of the News Digest Generator architecture, enabling developers to understand, maintain, and extend the system effectively.