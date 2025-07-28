# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a CLI-based personalized news digest generator with two main modules:

1. **Collector Module** - Automated processing that fetches articles from RSS feeds, uses AI to classify into 10 predefined categories, generates summaries, and stores enriched content
2. **User Interface Module** - Retrieves from processed database and delivers personalized digests in text, Markdown, or email-ready formats

## Architecture

The application is designed around a two-module architecture for scalability:

- **Collector Module**: Fetches → AI processes (classify, summarize, trend detect) → Deduplicates → Stores in central database
- **User Interface Module**: User preferences → Fetch relevant articles → Generate personalized digest → Output in chosen format

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

**Article Table**: id, title, author, publication_date, source_link, original_summary, rss_category, ai_categories (multi-label), ai_summary, trending_flag, date_collected

**User Preferences Table**: user_id, email, selected_categories, digest_frequency, articles_per_digest, preferred_output_format, feedback_history

## RSS Feed Integration

Each category maps to 5 curated RSS feeds. All RSS endpoints must be validated for XML validity and accessibility before implementation.

## Key Implementation Notes

- Batch AI processing only - all classification, summarization, and trend detection done in bulk
- Centralized content pool serves all users  
- Deduplication and diversity balancing to prevent single source dominance
- Email-ready output generation even in CLI phase for future integration
- User feedback loop for personalization (likes/dislikes tracking)

## Testing Strategy

Each module and feature must be thoroughly tested upon creation to avoid multiple issues:

- **RSS Feed Validation**: Test each RSS endpoint for XML validity, accessibility, and data structure before integration
- **Collector Module Testing**: Unit tests for feed parsing, AI processing pipeline, deduplication logic, and database storage
- **User Interface Module Testing**: Test user preference handling, digest generation, output formatting, and error handling
- **Integration Testing**: End-to-end testing of the complete pipeline from RSS feeds to final digest output
- **AI Processing Testing**: Validate category classification accuracy, summary quality, and trend detection
- **Database Testing**: Test data integrity, query performance, and storage/retrieval operations
- **CLI Interface Testing**: Test all command-line arguments, error messages, and user interaction flows

## Development Status

This appears to be a greenfield project - no existing code files found, only product requirements documentation.