# Project Overview

## Purpose
This is a comprehensive news aggregation platform that fetches articles from RSS feeds, processes them with AI for categorization and summarization, and generates personalized digests. It consists of two main modules:

1. **Collector Module** - Automated RSS feed processing with AI classification and storage
2. **User Interface Module** - Personalized digest generation and delivery

## Key Features
- 📡 RSS feed collection from 50+ curated sources
- 🤖 Multi-AI processing (OpenAI, Anthropic Claude, Google AI) with automatic fallback
- 🎯 10-category classification system for articles
- 📊 Trend detection and smart deduplication
- 🌐 Modern web interface with glassmorphism design
- 📧 Email digest delivery with responsive HTML templates
- 👍 User feedback system for personalization

## Architecture
- **Database**: SQLite with comprehensive schema for articles, users, and delivery tracking
- **AI Processing**: Batch processing with multiple provider support
- **Web Interface**: Flask-based with real-time operations dashboard
- **CLI Interface**: Full command-line access for all operations
- **Email System**: SMTP integration with tracking and analytics

## Categories System
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