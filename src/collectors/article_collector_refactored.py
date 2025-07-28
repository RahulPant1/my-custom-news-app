"""Refactored Article Collector with improved architecture and error handling."""

import feedparser
import requests
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from urllib.parse import urlparse

from core.config_manager import config
from core.exceptions import (
    RSSFeedError, RSSTimeoutError, RSSValidationError,
    DatabaseError, handle_database_errors
)
from utils.common import (
    generate_content_hash, generate_title_hash, extract_domain,
    rate_limit_delay, retry_with_backoff, clean_text, deduplicate_by_key
)
from utils.logging import get_logger, OperationTracker


@dataclass
class ArticleData:
    """Structured representation of article data."""
    title: str
    author: Optional[str]
    publication_date: Optional[str]
    source_link: str
    original_summary: Optional[str]
    rss_category: str
    content_hash: str
    title_hash: str
    guid: Optional[str] = None
    
    @classmethod
    def from_rss_entry(cls, entry, rss_category: str) -> 'ArticleData':
        """Create ArticleData from RSS entry."""
        # Extract published date
        published_date = None
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            try:
                published_date = datetime(*entry.published_parsed[:6]).isoformat()
            except (ValueError, TypeError):
                pass
        
        # Extract content/summary
        content = ""
        if hasattr(entry, 'content') and entry.content:
            content = entry.content[0].value if isinstance(entry.content, list) else str(entry.content)
        elif hasattr(entry, 'summary'):
            content = entry.summary
        elif hasattr(entry, 'description'):
            content = entry.description
        
        # Clean and prepare data
        title = clean_text(getattr(entry, 'title', ''))
        author = getattr(entry, 'author', None)
        link = getattr(entry, 'link', '').strip()
        guid = getattr(entry, 'id', None) or getattr(entry, 'guid', None)
        
        # Clean content
        cleaned_content = clean_text(content, max_length=1000)
        
        return cls(
            title=title,
            author=author,
            publication_date=published_date,
            source_link=link,
            original_summary=cleaned_content,
            rss_category=rss_category,
            content_hash=generate_content_hash(title, content),
            title_hash=generate_title_hash(title),
            guid=guid
        )
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for database storage."""
        return {
            'title': self.title,
            'author': self.author,
            'publication_date': self.publication_date,
            'source_link': self.source_link,
            'original_summary': self.original_summary,
            'rss_category': self.rss_category,
            'content_hash': self.content_hash,
            'title_hash': self.title_hash,
            'guid': self.guid
        }
    
    def is_valid(self) -> bool:
        """Check if article data is valid."""
        return bool(self.title and self.source_link)


class FeedProcessor:
    """Handles individual RSS feed processing."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'NewsDigest/2.0 (Article Collector)'
        })
    
    @retry_with_backoff(max_retries=3, base_delay=1.0)
    def fetch_feed(self, feed_url: str, timeout: int = 15) -> feedparser.FeedParserDict:
        """Fetch RSS feed with retries and error handling."""
        try:
            self.logger.debug(f"Fetching RSS feed: {feed_url}")
            
            response = self.session.get(feed_url, timeout=timeout)
            response.raise_for_status()
            
            feed = feedparser.parse(response.content)
            
            if feed.bozo:
                self.logger.warning(f"Feed parsing warning for {feed_url}: {feed.bozo_exception}")
                # Still continue if we got some data
                if not feed.entries:
                    raise RSSValidationError(f"No entries found in RSS feed: {feed_url}")
            
            return feed
            
        except requests.Timeout:
            raise RSSTimeoutError(f"Timeout fetching RSS feed: {feed_url}")
        except requests.RequestException as e:
            raise RSSFeedError(feed_url, f"Network error: {e}")
        except Exception as e:
            raise RSSFeedError(feed_url, f"Unexpected error: {e}")
    
    def extract_articles(self, feed: feedparser.FeedParserDict, category: str, max_articles: int) -> List[ArticleData]:
        """Extract articles from parsed feed."""
        articles = []
        processed_urls = set()
        
        for entry in feed.entries[:max_articles]:
            try:
                article_data = ArticleData.from_rss_entry(entry, category)
                
                # Skip invalid articles
                if not article_data.is_valid():
                    self.logger.debug(f"Skipping invalid article: {article_data.title}")
                    continue
                
                # Skip duplicates by URL
                if article_data.source_link in processed_urls:
                    continue
                
                processed_urls.add(article_data.source_link)
                articles.append(article_data)
                
            except Exception as e:
                self.logger.warning(f"Error processing RSS entry: {e}")
                continue
        
        return articles
    
    def process_feed(self, feed_url: str, category: str, max_articles: int = 20) -> List[ArticleData]:
        """Process a single RSS feed and return articles."""
        with OperationTracker(self.logger, "process_feed", feed_url=feed_url, category=category):
            # Add rate limiting
            rate_limit_delay()
            
            # Fetch feed
            feed = self.fetch_feed(feed_url)
            
            # Extract articles
            articles = self.extract_articles(feed, category, max_articles)
            
            self.logger.feed_processed(
                feed_url, 
                "success", 
                articles_extracted=len(articles),
                category=category
            )
            
            return articles


class ArticleCollectorRefactored:
    """Refactored Article Collector with improved architecture."""
    
    def __init__(self, db_manager=None):
        from database import DatabaseManager  # Lazy import to avoid circular dependency
        
        self.db_manager = db_manager or DatabaseManager()
        self.feed_processor = FeedProcessor()
        self.logger = get_logger(__name__)
        self.processed_urls: Set[str] = set()
        self.collected_articles: List[ArticleData] = []
    
    def get_validated_feeds(self, category: Optional[str] = None) -> List[Dict]:
        """Get validated RSS feeds from database."""
        try:
            return self.db_manager.get_validated_feeds(category=category, only_ok=True)
        except Exception as e:
            raise DatabaseError(f"Failed to get validated feeds: {e}")
    
    def collect_from_category(self, category: str, max_per_feed: int = 20) -> List[ArticleData]:
        """Collect articles from all feeds in a category."""
        validated_feeds = self.get_validated_feeds(category=category)
        
        if not validated_feeds:
            self.logger.warning(f"No validated feeds found for category: {category}")
            return []
        
        all_articles = []
        
        with OperationTracker(self.logger, "collect_category", category=category, feeds_count=len(validated_feeds)):
            for feed_info in validated_feeds:
                try:
                    feed_url = feed_info['feed_url']
                    articles = self.feed_processor.process_feed(feed_url, category, max_per_feed)
                    all_articles.extend(articles)
                    
                except (RSSFeedError, RSSTimeoutError, RSSValidationError) as e:
                    self.logger.error(f"RSS feed error: {e}", extra={'feed_url': feed_info.get('feed_url')})
                    continue
                except Exception as e:
                    self.logger.exception(f"Unexpected error processing feed: {e}")
                    continue
        
        self.logger.info(f"Collected {len(all_articles)} articles from {category}")
        return all_articles
    
    def collect_from_all_categories(self, max_per_feed: int = 10, categories: Optional[List[str]] = None) -> List[ArticleData]:
        """Collect articles from all or specified categories."""
        all_articles = []
        
        # Get available categories
        if categories:
            target_categories = categories
        else:
            all_feeds = self.get_validated_feeds()
            target_categories = list(set(feed['category'] for feed in all_feeds))
        
        with OperationTracker(self.logger, "collect_all_categories", categories_count=len(target_categories)):
            for category in target_categories:
                try:
                    category_articles = self.collect_from_category(category, max_per_feed)
                    all_articles.extend(category_articles)
                    
                except Exception as e:
                    self.logger.exception(f"Error collecting from category {category}: {e}")
                    continue
        
        self.collected_articles = all_articles
        self.logger.info(f"Total articles collected: {len(all_articles)}")
        
        return all_articles
    
    def deduplicate_articles(self, articles: List[ArticleData]) -> List[ArticleData]:
        """Remove duplicate articles using multiple strategies."""
        if not articles:
            return articles
        
        with OperationTracker(self.logger, "deduplicate_articles", input_count=len(articles)):
            # Convert to dicts for processing
            article_dicts = [article.to_dict() for article in articles]
            
            # Strategy 1: Remove exact URL duplicates
            unique_by_url = deduplicate_by_key(article_dicts, 'source_link')
            
            # Strategy 2: Remove content hash duplicates
            unique_by_content = deduplicate_by_key(unique_by_url, 'content_hash')
            
            # Convert back to ArticleData objects
            unique_articles = []
            for article_dict in unique_by_content:
                # Reconstruct ArticleData
                article = ArticleData(
                    title=article_dict['title'],
                    author=article_dict['author'],
                    publication_date=article_dict['publication_date'],
                    source_link=article_dict['source_link'],
                    original_summary=article_dict['original_summary'],
                    rss_category=article_dict['rss_category'],
                    content_hash=article_dict['content_hash'],
                    title_hash=article_dict['title_hash'],
                    guid=article_dict['guid']
                )
                unique_articles.append(article)
            
            duplicates_removed = len(articles) - len(unique_articles)
            if duplicates_removed > 0:
                self.logger.info(f"Removed {duplicates_removed} duplicate articles")
            
            return unique_articles
    
    def balance_source_diversity(self, articles: List[ArticleData], max_per_domain: int = 5) -> List[ArticleData]:
        """Ensure no single domain dominates the articles."""
        if not articles:
            return articles
        
        with OperationTracker(self.logger, "balance_diversity", input_count=len(articles)):
            domain_counts = {}
            balanced_articles = []
            
            for article in articles:
                try:
                    domain = extract_domain(article.source_link)
                    current_count = domain_counts.get(domain, 0)
                    
                    if current_count < max_per_domain:
                        balanced_articles.append(article)
                        domain_counts[domain] = current_count + 1
                
                except Exception as e:
                    self.logger.warning(f"Error processing domain for {article.source_link}: {e}")
                    balanced_articles.append(article)  # Include anyway
            
            filtered_count = len(articles) - len(balanced_articles)
            if filtered_count > 0:
                self.logger.info(f"Filtered {filtered_count} articles for source diversity")
            
            return balanced_articles
    
    @handle_database_errors
    def store_articles(self, articles: List[ArticleData]) -> Dict[str, int]:
        """Store articles in the database with comprehensive error handling."""
        if not articles:
            return {'stored': 0, 'updated': 0, 'skipped': 0, 'errors': 0}
        
        stats = {'stored': 0, 'updated': 0, 'skipped': 0, 'errors': 0}
        
        with OperationTracker(self.logger, "store_articles", articles_count=len(articles)):
            for article in articles:
                try:
                    article_id, action = self.db_manager.insert_or_update_article(article.to_dict())
                    
                    if action == 'inserted':
                        stats['stored'] += 1
                        self.logger.article_processed(article_id, 'stored', title=article.title)
                    elif action == 'updated':
                        stats['updated'] += 1
                        self.logger.article_processed(article_id, 'updated', title=article.title)
                    elif action == 'duplicate':
                        stats['skipped'] += 1
                    else:
                        stats['errors'] += 1
                        
                except Exception as e:
                    self.logger.error(f"Error storing article '{article.title}': {e}")
                    stats['errors'] += 1
        
        self.logger.info(
            f"Storage complete: {stats['stored']} stored, {stats['updated']} updated, "
            f"{stats['skipped']} skipped, {stats['errors']} errors"
        )
        return stats
    
    def run_collection_cycle(self, max_per_feed: int = 10, categories: Optional[List[str]] = None) -> Dict[str, int]:
        """Run a complete collection cycle with enhanced error handling and logging."""
        with OperationTracker(self.logger, "collection_cycle", max_per_feed=max_per_feed):
            try:
                # Step 1: Collect articles
                raw_articles = self.collect_from_all_categories(max_per_feed, categories)
                
                if not raw_articles:
                    self.logger.warning("No articles collected")
                    return {'collected': 0, 'stored': 0, 'skipped': 0, 'errors': 0}
                
                # Step 2: Deduplicate
                unique_articles = self.deduplicate_articles(raw_articles)
                
                # Step 3: Balance diversity
                balanced_articles = self.balance_source_diversity(unique_articles)
                
                # Step 4: Store in database
                storage_stats = self.store_articles(balanced_articles)
                
                final_stats = {
                    'collected': len(raw_articles),
                    'unique': len(unique_articles),
                    'balanced': len(balanced_articles),
                    **storage_stats
                }
                
                self.logger.info(f"Collection cycle complete: {final_stats}")
                return final_stats
                
            except Exception as e:
                self.logger.exception("Collection cycle failed")
                raise


def main():
    """Test the refactored collector."""
    collector = ArticleCollectorRefactored()
    stats = collector.run_collection_cycle()
    print(f"Collection completed: {stats}")


if __name__ == "__main__":
    main()