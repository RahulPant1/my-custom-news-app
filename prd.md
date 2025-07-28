Product Requirements: CLI-Based Personalized News Digest Generator 
1. Overview
A CLI-based application that:
    • Aggregates news from a predefined set of RSS feeds.
    • Uses AI to reclassify articles into 10 predefined categories (multi-label possible).
    • Generates human-friendly summaries and trend insights.
    • Stores enriched articles with metadata (author, date, source link, etc.).
    • Outputs personalized digests in text, Markdown, or email-ready formats based on user preferences.
    • **Multi-Provider LLM Support**: Utilizes a robust multi-provider LLM router with automatic fallback for reliability and cost optimization.
    • Designed for scalability with two separate modules:
        1. Collector Module – fetches, processes, and stores news.
        2. User Interface Module – retrieves from the processed database and delivers user-specific digests.

2. Predefined AI Categories
Articles will be classified (multi-label possible) into:
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

3. RSS Feed Mapping (Phase 1 Starter Set)
Each category pulls from 5 curated RSS feeds:
Category	RSS Feeds (Sample Sources)
Science & Discovery	ScienceDaily (https://www.sciencedaily.com/rss) 
    New Scientist (https://www.newscientist.com/feed/home) 
    Scientific American (https://www.scientificamerican.com/rss) 
    Phys.org (https://phys.org/rss-feed.xml) 
    Popular Science Science (https://www.popsci.com/category/science/feed)
Technology & Gadgets	TechCrunch (https://techcrunch.com/feed) 
    WIRED (https://www.wired.com/feed/rss) 
    The Verge (https://www.theverge.com/rss/index.xml) 
    Engadget (https://www.engadget.com/rss.xml) 
    CNET News (https://www.cnet.com/rss/news)
Health & Wellness	ScienceDaily Health (https://www.sciencedaily.com/rss/health_medicine.xml) 
    Scientific American Health (https://www.scientificamerican.com/rss/health.xml) 
    LiveScience (https://www.livescience.com/feeds/latest) 
    Medscape News (https://www.medscape.com/rss/news.xml) 
    Nature Medicine (https://www.nature.com/subjects/medicine.rss)
Business & Finance	Financial Times World (https://www.ft.com/rss/world) 
    WSJ Business (https://www.wsj.com/xml/rss/3_7014.xml) 
    The Economist Business (https://www.economist.com/business/rss.xml) 
    TechCrunch Startups (https://techcrunch.com/startups/feed) 
    VentureBeat (https://venturebeat.com/feed)
Global Affairs	BBC World (https://www.bbc.co.uk/news/world/rss.xml) 
    Reuters World (https://www.reuters.com/rss/worldNews) 
    Al Jazeera All News (https://www.aljazeera.com/xml/rss/all.xml) 
    The Economist International (https://www.economist.com/international/rss.xml) 
    Foreign Affairs (https://www.foreignaffairs.com/rss)
Environment & Climate	ScienceDaily Environment (https://www.sciencedaily.com/rss/environment.xml) 
    PopSci Environment (https://www.popsci.com/category/environment/feed) 
    Nature Environmental (https://www.nature.com/subjects/environment.rss) 
    LiveScience Environment (https://www.livescience.com/rss.xml) 
    Wired Environment (https://www.wired.com/feed/category/environment/rss)
Good Vibes (Positive News)	Positive News (https://www.positive.news/feed) 
    Good News Network (https://www.goodnewsnetwork.org/feed) 
    Upworthy (https://www.upworthy.com/feeds/all) 
    HuffPost Good News (https://www.huffpost.com/section/good-news/feed) 
    Today I Found Out (https://tifo.co/feed)
Pop Culture & Lifestyle	New Yorker Culture (https://www.newyorker.com/feed/cultural-comment.rss) 
    WIRED Culture (https://www.wired.com/feed/category/culture/rss) 
    PopSci Life Skills (https://www.popsci.com/category/life-skills/feed) 
    Atlas Obscura (https://www.atlasobscura.com/feeds/stories.xml) 
    Brain Pickings (https://www.brainpickings.org/feed)
For Young Minds	Science News for Students (https://www.snexplores.org/feed) 
    Science Sparks (https://www.science-sparks.com/feed) 
    Science Buddies (https://www.sciencebuddies.org/blog/rss.xml) 
    Tumble (Kids Science) (https://www.sciencepodcastforkids.com/blog/feed) 
    The Kid Should See This (https://www.thekidshouldseethis.com/feed)
DIY, Skills & How-To	Popular Science DIY (https://www.popsci.com/category/diy/feed) 
    Lifehacker (https://www.lifehacker.com/rss) 
    Instructables (https://www.instructables.com/rss/category/all.xml) 
    Make Magazine (https://www.makezine.com/feed) 
    DIY Network (https://www.diynetwork.com/rss/all.xml)

## Multi-Provider LLM Request Router Module

### Overview
The application utilizes a sophisticated multi-provider LLM routing system that ensures reliable AI processing with automatic fallback capabilities. This module addresses key challenges with single-provider dependencies.

### Key Features

#### 1. **Multi-Provider Support**
- **Supported Providers**: OpenAI, Anthropic (Claude), Google (Gemini), Groq, OpenRouter
- **Configurable Priority**: Providers and models are tried in configured order
- **Automatic Fallback**: If one provider fails or is rate-limited, automatically tries the next
- **Model Selection**: Each provider can have multiple models with different capabilities and limits

#### 2. **Advanced Rate Limiting**
- **RPM (Requests Per Minute)**: Tracks and enforces per-model rate limits
- **RPD (Requests Per Day)**: Daily usage tracking with automatic reset at midnight UTC
- **Persistent Storage**: Usage counters persist across application restarts
- **Flexible Backends**: JSON file (default) or SQLite for concurrent access

#### 3. **Configuration-Driven**
```yaml
providers:
  - name: google
    models:
      - model: gemini-2.5-pro
        rpm: 5       # max 5 requests/minute
        rpd: 500     # max 500 requests/day
      - model: gemini-2.0-flash
        rpm: 10
        rpd: 1000

  - name: anthropic
    models:
      - model: claude-3-5-sonnet-20241022
        rpm: 5
        rpd: 300
```

#### 4. **Error Handling & Resilience**
- **Graceful Degradation**: Continues operation even if some providers are unavailable
- **Comprehensive Logging**: Tracks provider selection, rate limits, and errors
- **Error Classification**: Distinguishes between rate limits, API errors, and other failures
- **Usage Statistics**: Real-time monitoring of provider usage and success rates

#### 5. **Integration Points**
- **Drop-in Replacement**: Existing AI calls can use the router without code changes
- **Enhanced Features**: 
  - Article classification with multi-provider fallback
  - AI summarization with reliability guarantees
  - Email subject generation
  - Digest personalization
- **Backward Compatibility**: Maintains compatibility with existing AI adapter interfaces

### Technical Implementation

#### Usage Example
```python
from llm_router import LLMRouter

router = LLMRouter(config_path="ai_config.yaml")
response = router.query("Summarize today's top news")
```

#### Integration with News Digest
- **Article Processing**: Classification and summarization use the router
- **Email Generation**: Subject lines and content personalization
- **Content Enhancement**: AI insights and digest introductions
- **Monitoring**: Usage tracking and provider health monitoring

### Benefits
1. **Reliability**: No single point of failure for AI processing
2. **Cost Optimization**: Automatic routing to most cost-effective available provider
3. **Rate Limit Compliance**: Prevents API violations with persistent tracking
4. **Scalability**: Easy addition of new providers and models
5. **Observability**: Comprehensive monitoring and usage statistics

Immediate Step to be done for any new rss feed added (and also validate above ones)
Validate each RSS endpoint (ensure XML validity, active feeds, and accessibility) before building the Collector logic.


4.  Modules
Module 1: Collector (Automated Processing)
    • Fetch articles from predefined RSS feeds.
    • Extract full metadata (title, author, date, source link, RSS category, summary).
    • Use AI (in bulk) to:
        ○ Assign application-defined categories (multi-label).
        ○ Generate AI-enhanced summaries (Markdown-friendly).
        ○ Create trend highlights and quick context (e.g., “3 AI breakthroughs this week” or “Why This Matters” sections).
    • Deduplicate stories and balance diversity (no one source dominating).
    • Store all enriched content in the central database.
Module 2: User Interface (Digest Output)
    • Users configure via CLI:
        ○ Categories (from the 10 AI-driven ones).
        ○ Articles per digest, output format (plain text, Markdown, email-ready text).
        ○ Digest frequency (daily, weekly).
    • Generates personalized digests:
        ○ Includes AI summaries, title, author, date, source link.
        ○ Adds optional engagement hooks:
            § “Top Tweet/Stat of the Day.”
            § “One-Line Explainer” for a trending story.
            § Sharing links (social, WhatsApp).
        ○ Applies fallback logic (older content or original summaries if fresh ones or AI outputs are missing).

5. Core Features (Summary)
    1. Collector Module – Fetch feeds, extract metadata, AI reclassify, summarize, trend detect, deduplicate, store.
    2. User Interface Module – Read preferences, fetch top N articles per user, generate digest with summaries, metadata, and optional engagement hooks (Top Fact, Quick Explainer, sharing links).
    3. User Feedback Loop – Track likes/dislikes for personalization in future phases.
    4. Output Options – Plain text, Markdown, or email-ready text.

4. User Experience & Personalization
    • Modes → Personalization Levels:
Users select categories but the system evolves:
        ○ Feedback collected via thumbs up/down or “more like this/less like this” links in digests.
        ○ Profiles adapt over time (even in CLI phase, feedback can be stored for future weighting).
    • Engagement Hooks:
        ○ Small, high-engagement sections (Top Fact, Quick Explainer).
        ○ One-click sharing buttons to increase reach organically.

5. Content Quality & Discovery
    • De-Duplication & Cross-Source Check:
Prevent duplicates from dominating the digest.
    • Diversity Balancing:
Automatically mix sources to ensure no single publication exceeds a set share of top stories.
    • AI Beyond Summaries:
        ○ Highlight trending topics (“3 stories trending in AI today”).
        ○ Provide context blocks (“Why this matters” or timeline for an ongoing issue).

6. Email Strategy (Even in CLI Phase)
    • Although Phase 1 is CLI-driven, the system should generate email-ready digest text for future sending.
    • Personalized Subject Lines:
AI can craft catchy, category-specific subjects (e.g., “Your Daily Tech & Good Vibes Brief”).
    • Configurable Output:
        ○ Local text file
        ○ Markdown file
        ○ Email-ready text (with subject line, ready for integration later)

7. Data Storage (with Metadata)
Article Table Fields:
    • id
    • title
    • author (if available)
    • publication_date
    • source_link
    • original_summary
    • rss_category (from feed)
    • ai_categories (multi-label; from 10 categories)
    • ai_summary
    • trending_flag (if part of a trend cluster)
    • date_collected
User Preferences Table:
    • user_id
    • email (optional for export)
    • selected_categories (from AI-driven list)
    • digest_frequency
    • articles_per_digest
    • preferred_output_format
    • feedback_history (likes/dislikes, for future personalization)

8. Operational Efficiency
    • Batch AI Processing Only:
All classification, summarization, and trend detection done in bulk, not per user.
    • Centralized Content Pool:
Single processed dataset serves all users.
    • Logging & Reporting:
        ○ Number of articles fetched, summarized, and stored.
Engagement stats (clicks, likes, etc.) for future personalization.