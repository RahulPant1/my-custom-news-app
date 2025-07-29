# News Digest Generator 📰

A comprehensive news aggregation platform that fetches articles from RSS feeds, processes them with AI, and generates personalized digests via CLI and modern web interface.

## 🚀 Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env and add your AI service API keys

# 3. Setup database
python main.py setup

# 4. Add a user
python main.py user add your-email@example.com

# 5. Launch web interface
python main.py web
# Open http://localhost:5000
```

## 🌟 Features

- **📡 RSS Feed Collection**: Aggregates from 50+ curated sources across 10 categories
- **🤖 Multi-AI Processing**: OpenAI, Anthropic Claude, Google AI with automatic fallback
- **🎯 Smart Personalization**: User preferences with AI-driven article selection
- **📊 Trend Detection**: Identifies trending topics across articles
- **🌐 Modern Web Interface**: Professional glassmorphism design with real-time operations
- **📧 Rich Email Templates**: Mobile-responsive HTML emails with feedback system
- **🔄 Background Processing**: Asynchronous task handling with progress tracking

## 🗂️ Categories System

Articles are classified into 10 AI-powered categories:

1. 🔬 **Science & Discovery** - Research, breakthroughs, innovations
2. 💻 **Technology & Gadgets** - Tech news, products, software updates  
3. 🏥 **Health & Wellness** - Medical research, health tips, wellness
4. 💼 **Business & Finance** - Markets, business, economic trends
5. 🌍 **Global Affairs** - International news, politics, diplomacy
6. 🌱 **Environment & Climate** - Climate change, sustainability
7. 😊 **Good Vibes** - Positive news, uplifting stories
8. 🎭 **Pop Culture & Lifestyle** - Entertainment, culture, lifestyle
9. 🎓 **For Young Minds** - Educational content, youth-focused
10. 🔧 **DIY & How-To** - Tutorials, skills, guides

## 💻 CLI Commands

### Core Operations
```bash
# Complete pipeline (collect + process + send)
python main.py run USER_ID [--articles 15] [--skip-ai]

# Send digest using existing articles
python main.py send USER_ID [--categories "Technology & Gadgets"]

# Preview digest
python main.py preview USER_ID [--format html] [--save output.html]

# Launch web interface
python main.py web
```

### User Management
```bash
# Add user with preferences
python main.py user add EMAIL [--id USER_ID] [--count 10]

# Edit user preferences
python main.py user edit USER_ID [--email NEW_EMAIL] [--count 15]

# List all users
python main.py user list

# Remove user
python main.py user remove USER_ID [--yes]
```

### Development
```bash
# Test email configuration
python main.py dev test-email USER_ID

# Database statistics
python main.py dev db-stats
```

## 🌐 Web Interface

The modern web interface provides comprehensive management through three main sections:

### 🏠 Dashboard (`/`)
- User overview with preference cards
- Quick actions: create users, send emails, view digests
- Real-time statistics and system health

### ⚙️ Operations Dashboard (`/operations`)
- **Pipeline Execution**: Run complete news processing with options:
  - Daily/Weekly digest modes
  - Enhanced AI processing
  - Dry run preview
  - Skip AI on rate limits
  - Custom article limits
- **Real-time Monitoring**: Live logs, progress tracking, auto-refresh
- **Email Delivery**: Instant digest sending to users

### 👥 User Management (`/user-management`)
- Interactive user directory with search and filtering
- Bulk operations: CSV export, mass emails
- Visual category selection with touch-friendly UI
- Create, edit, delete users with confirmation dialogs

## ⚙️ Configuration

### Environment Variables (.env)
```bash
# AI Services (at least one required)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=AI...

# Email Configuration
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# Application Settings
DATABASE_PATH=news_digest.db
LOG_LEVEL=INFO
MAX_ARTICLES_PER_DIGEST=20
AI_USE_BATCH_SUMMARIES=true
```

### AI Model Configuration (config.py)
```python
AI_MODELS = {
    'openai': {
        'default': 'gpt-3.5-turbo',
        'alternatives': ['gpt-4', 'gpt-4-turbo']
    },
    'anthropic': {
        'default': 'claude-3-haiku-20240307',
        'alternatives': ['claude-3-sonnet-20240229']
    }
}
```

## 🏗️ Architecture

### Two-Module Design
- **Collector Module**: RSS → AI Processing → Deduplication → Database
- **User Interface Module**: Preferences → Personalization → Multi-format Output

### Database Schema
```sql
-- Core Tables
articles: id, title, author, publication_date, source_link, ai_summary, ai_categories, trending_flag
user_preferences: user_id, email, selected_categories, digest_frequency, articles_per_digest
email_deliveries: id, user_id, template_used, delivery_status, sent_at
daily_oneliners: id, category, generation_date, one_liners
```

### Project Structure
```
my_custom_news_app/
├── src/                    # Core application code
│   ├── web_interface.py   # Flask web application
│   ├── collector.py       # RSS feed processing
│   ├── ai_processor.py    # AI categorization & summarization
│   ├── user_interface.py  # CLI user management
│   └── email_delivery.py  # Email system with templates
├── templates/             # Web interface templates
├── tests/                 # Comprehensive test suite
├── main.py               # CLI entry point
└── config.py             # Configuration settings
```

## 🚨 Troubleshooting

### Common Issues

**Web Interface Not Loading**
```bash
cd my_custom_news_app
python main.py web
# Verify templates/ directory exists
```

**Email Delivery Failures**
```bash
python main.py dev test-email USER_ID
# Check SMTP settings in .env file
```

**AI Processing Errors**
```bash
python main.py dev db-stats
# Verify API keys and rate limits
```

**Pipeline Timeouts**
```bash
# Use fewer articles for testing
python main.py run USER_ID --articles 3 --skip-ai
```

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Test specific components
pytest tests/test_web_interface.py -v
pytest tests/test_enhanced_ai_processor.py -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

## 📈 Performance & Monitoring

- **API Cost Optimization**: 10× reduction through batch processing
- **Built-in Monitoring**: Real-time web dashboard with system health
- **Email Analytics**: Delivery rates, engagement tracking
- **Incremental Updates**: Smart caching with HTTP ETags

## 🔐 Security

- Store API keys securely in `.env` (never commit)
- Use HTTPS in production
- Implement data retention policies
- Regular database backups

## 📝 License

Educational and personal use. Respect AI provider API limits and terms of service.

---

**Ready to start?** `python main.py setup` → `python main.py user add your@email.com` → `python main.py web`