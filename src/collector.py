"""Collector Module: Fetches, processes, and stores news articles."""

import feedparser
import requests
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Set
import logging
from urllib.parse import urljoin, urlparse
import time
import random

try:
    from .database import DatabaseManager
    from .image_extractor import ImageExtractor
except ImportError:
    from database import DatabaseManager
    from image_extractor import ImageExtractor

try:
    from .config import AI_CATEGORIES
except ImportError:
    try:
        from config import AI_CATEGORIES
    except ImportError:
        AI_CATEGORIES = ['Science & Discovery', 'Technology & Gadgets', 'Health & Wellness', 'Business & Finance', 'Global Affairs', 'Environment & Climate', 'Good Vibes (Positive News)', 'Pop Culture & Lifestyle', 'For Young Minds (Youth-Focused)', 'DIY, Skills & How-To']

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ArticleCollector:
    """Handles RSS feed collection and article processing."""
    
    def __init__(self, db_manager: DatabaseManager = None, extract_images: bool = True):
        self.db_manager = db_manager or DatabaseManager()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'NewsDigest/1.0 (Article Collector)'
        })
        self.processed_urls: Set[str] = set()
        self.collected_articles = []
        self.extract_images = extract_images
        self.image_extractor = ImageExtractor(self.db_manager) if extract_images else None
    
    def generate_content_hash(self, title: str, content: str = "") -> str:
        """Generate a hash for duplicate detection."""
        content_string = f"{title.lower().strip()}{content.lower().strip()}"
        return hashlib.md5(content_string.encode()).hexdigest()
    
    def extract_article_data(self, entry, rss_category: str) -> Dict:
        """Extract article data from RSS entry with image extraction."""
        # Get published date
        published_date = None
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            try:
                published_date = datetime(*entry.published_parsed[:6]).isoformat()
            except (ValueError, TypeError):
                published_date = None
        
        # Extract content/summary
        content = ""
        if hasattr(entry, 'content') and entry.content:
            content = entry.content[0].value if isinstance(entry.content, list) else str(entry.content)
        elif hasattr(entry, 'summary'):
            content = entry.summary
        elif hasattr(entry, 'description'):
            content = entry.description
        
        # Clean and prepare data
        title = getattr(entry, 'title', '').strip()
        author = getattr(entry, 'author', None)
        link = getattr(entry, 'link', '').strip()
        
        article_data = {
            'title': title,
            'author': author,
            'publication_date': published_date,
            'source_link': link,
            'original_summary': content[:1000] if content else None,  # Limit summary length
            'rss_category': rss_category,
            'content_hash': self.generate_content_hash(title, content)
        }
        
        # Extract image if enabled
        if self.extract_images and self.image_extractor:
            try:
                image_data = self.image_extractor.extract_image_from_entry(entry, link)
                if image_data:
                    article_data.update({
                        'image_url': image_data.get('url'),
                        'image_source': image_data.get('source'),
                        'image_cached_path': image_data.get('path'),
                        'image_size': image_data.get('size'),
                        'image_width': image_data.get('width'),
                        'image_height': image_data.get('height')
                    })
                    logger.debug(f"Extracted image for article: {title[:50]}... - Source: {image_data.get('source')}")
            except Exception as e:
                logger.debug(f"Failed to extract image for article {title[:50]}...: {e}")
        
        return article_data
    
    def download_and_cache_article_images(self, articles: List[Dict]) -> Dict:
        """Download and cache images for articles that have image URLs."""
        if not self.extract_images or not self.image_extractor:
            return {'downloaded': 0, 'cached': 0, 'errors': 0}
        
        stats = {'downloaded': 0, 'cached': 0, 'errors': 0}
        
        for article in articles:
            article_id = article.get('id')
            image_url = article.get('image_url')
            image_source = article.get('image_source')
            
            # Skip if no image URL or already cached/stock image
            if not image_url or not article_id:
                continue
            
            if image_source in ['stock', 'cached']:
                stats['cached'] += 1
                continue
            
            try:
                # Download and cache the image
                cached_info = self.image_extractor.download_and_cache_image(image_url, article_id)
                if cached_info:
                    # Update article with cached information
                    article_update = {
                        'id': article_id,
                        'image_cached_path': cached_info.get('relative_path'),
                        'image_size': cached_info.get('size'),
                        'image_width': cached_info.get('width'),
                        'image_height': cached_info.get('height')
                    }
                    
                    # Update in database
                    self.db_manager.insert_or_update_article(article_update)
                    stats['downloaded'] += 1
                    logger.debug(f"Cached image for article {article_id}: {cached_info.get('size', 0)} bytes")
                else:
                    stats['errors'] += 1
                    
            except Exception as e:
                logger.warning(f"Failed to download image for article {article_id}: {e}")
                stats['errors'] += 1
        
        if stats['downloaded'] > 0 or stats['errors'] > 0:
            logger.info(f"Image caching complete: {stats['downloaded']} downloaded, {stats['cached']} already cached, {stats['errors']} errors")
        
        return stats
    
    def fetch_from_rss_feed(self, feed_url: str, category: str, max_articles: int = 50) -> List[Dict]:
        """Fetch articles from a single RSS feed."""
        articles = []
        
        try:
            logger.info(f"Fetching from {feed_url} ({category})")
            
            # Add random delay to avoid overwhelming servers
            time.sleep(random.uniform(0.5, 2.0))
            
            response = self.session.get(feed_url, timeout=15)
            response.raise_for_status()
            
            feed = feedparser.parse(response.content)
            
            if feed.bozo:
                logger.warning(f"Feed parsing warning for {feed_url}: {feed.bozo_exception}")
            
            entries_processed = 0
            for entry in feed.entries:
                if entries_processed >= max_articles:
                    break
                
                try:
                    article_data = self.extract_article_data(entry, category)
                    
                    # Skip if we've seen this URL before
                    if article_data['source_link'] in self.processed_urls:
                        continue
                    
                    # Skip articles without title or link
                    if not article_data['title'] or not article_data['source_link']:
                        continue
                    
                    self.processed_urls.add(article_data['source_link'])
                    articles.append(article_data)
                    entries_processed += 1
                    
                except Exception as e:
                    logger.warning(f"Error processing entry from {feed_url}: {e}")
                    continue
            
            logger.info(f"Fetched {len(articles)} articles from {feed_url}")
            
        except requests.RequestException as e:
            logger.error(f"Network error fetching {feed_url}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error fetching {feed_url}: {e}")
        
        return articles
    
    def collect_from_category(self, category: str, max_per_feed: int = 20) -> List[Dict]:
        """Collect articles from all feeds in a category."""
        # Get validated feeds from database
        validated_feeds = self.db_manager.get_validated_feeds(category=category, only_ok=True)
        
        if not validated_feeds:
            logger.warning(f"No validated feeds found for category: {category}")
            return []
        
        all_articles = []
        feed_urls = [feed['feed_url'] for feed in validated_feeds]
        
        logger.info(f"Collecting from category: {category} ({len(feed_urls)} validated feeds)")
        
        for feed_url in feed_urls:
            articles = self.fetch_from_rss_feed(feed_url, category, max_per_feed)
            all_articles.extend(articles)
        
        logger.info(f"Collected {len(all_articles)} articles from {category}")
        return all_articles
    
    def collect_from_all_categories(self, max_per_feed: int = 10) -> List[Dict]:
        """Collect articles from all validated RSS feeds."""
        all_articles = []
        
        logger.info("Starting article collection from all categories")
        
        # Get all available categories from database with validated feeds
        all_feeds = self.db_manager.get_validated_feeds(only_ok=True)
        categories = list(set(feed['category'] for feed in all_feeds))
        
        for category in categories:
            category_articles = self.collect_from_category(category, max_per_feed)
            all_articles.extend(category_articles)
            
            # Add delay between categories to be respectful
            time.sleep(random.uniform(1.0, 3.0))
        
        self.collected_articles = all_articles
        logger.info(f"Total articles collected: {len(all_articles)}")
        
        return all_articles
    
    def deduplicate_articles(self, articles: List[Dict]) -> List[Dict]:
        """Remove duplicate articles based on content hash."""
        seen_hashes = set()
        unique_articles = []
        
        for article in articles:
            content_hash = article['content_hash']
            if content_hash not in seen_hashes:
                seen_hashes.add(content_hash)
                unique_articles.append(article)
        
        duplicates_removed = len(articles) - len(unique_articles)
        if duplicates_removed > 0:
            logger.info(f"Removed {duplicates_removed} duplicate articles")
        
        return unique_articles
    
    def balance_source_diversity(self, articles: List[Dict], max_per_domain: int = 5) -> List[Dict]:
        """Ensure no single domain dominates the articles."""
        domain_counts = {}
        balanced_articles = []
        
        for article in articles:
            try:
                domain = urlparse(article['source_link']).netloc.lower()
                current_count = domain_counts.get(domain, 0)
                
                if current_count < max_per_domain:
                    balanced_articles.append(article)
                    domain_counts[domain] = current_count + 1
            
            except Exception as e:
                logger.warning(f"Error processing domain for {article['source_link']}: {e}")
                balanced_articles.append(article)  # Include anyway if we can't parse domain
        
        filtered_count = len(articles) - len(balanced_articles)
        if filtered_count > 0:
            logger.info(f"Filtered {filtered_count} articles for source diversity")
        
        return balanced_articles
    
    def store_articles(self, articles: List[Dict]) -> Dict[str, int]:
        """Store articles in the database."""
        stats = {'stored': 0, 'updated': 0, 'skipped': 0, 'errors': 0}
        
        logger.info(f"Storing {len(articles)} articles in database")
        
        for article in articles:
            try:
                article_id, action = self.db_manager.insert_or_update_article(article)
                if action == 'inserted':
                    stats['stored'] += 1
                elif action == 'updated':
                    stats['updated'] += 1
                elif action == 'duplicate':
                    stats['skipped'] += 1
                else:
                    stats['errors'] += 1
            except Exception as e:
                logger.error(f"Error storing article '{article['title']}': {e}")
                stats['errors'] += 1
        
        logger.info(f"Storage complete: {stats['stored']} stored, {stats['updated']} updated, {stats['skipped']} skipped, {stats['errors']} errors")
        return stats
    
    def run_collection_cycle(self, max_per_feed: int = 10) -> Dict[str, int]:
        """Run a complete collection cycle."""
        logger.info("Starting collection cycle")
        
        # Step 1: Collect articles
        raw_articles = self.collect_from_all_categories(max_per_feed)
        
        if not raw_articles:
            logger.warning("No articles collected")
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
        
        logger.info(f"Collection cycle complete: {final_stats}")
        return final_stats


def main():
    """Run article collection."""
    collector = ArticleCollector()
    stats = collector.run_collection_cycle()
    print(f"Collection completed: {stats}")


if __name__ == "__main__":
    main()