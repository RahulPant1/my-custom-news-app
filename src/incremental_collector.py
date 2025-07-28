"""Enhanced collector with incremental updates and advanced duplicate detection."""

import feedparser
import requests
import hashlib
import re
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple
import logging
from urllib.parse import urljoin, urlparse
import time
import random

try:
    from .database import DatabaseManager
except ImportError:
    from database import DatabaseManager

try:
    from .config import AI_CATEGORIES
except ImportError:
    from config import AI_CATEGORIES

try:
    from image_extractor import ImageExtractor
except ImportError:
    try:
        from .image_extractor import ImageExtractor
    except ImportError:
        ImageExtractor = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IncrementalCollector:
    """Enhanced collector with incremental updates and better duplicate detection."""
    
    def __init__(self, db_manager: DatabaseManager = None, extract_images: bool = True):
        self.db_manager = db_manager or DatabaseManager()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'NewsDigest/2.0 (Incremental Collector)'
        })
        self.processed_items = set()
        self.collection_stats = {
            'new_articles': 0,
            'updated_articles': 0,
            'duplicates_skipped': 0,
            'errors': 0
        }
        
        # Initialize image extraction
        self.extract_images = extract_images and ImageExtractor is not None
        self.image_extractor = ImageExtractor(self.db_manager) if self.extract_images else None
        if self.extract_images:
            logger.info("Image extraction enabled for incremental collector")
        else:
            logger.info("Image extraction disabled for incremental collector")
    
    def normalize_title(self, title: str) -> str:
        """Normalize title for better duplicate detection."""
        if not title:
            return ""
        
        # Convert to lowercase
        normalized = title.lower().strip()
        
        # Remove common prefixes/suffixes
        prefixes = ['breaking:', 'urgent:', 'news:', 'update:', 'exclusive:']
        for prefix in prefixes:
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix):].strip()
        
        # Remove extra whitespace and punctuation
        normalized = re.sub(r'\s+', ' ', normalized)
        normalized = re.sub(r'[^\w\s]', '', normalized)
        
        return normalized.strip()
    
    def generate_title_hash(self, title: str) -> str:
        """Generate hash for title-based duplicate detection."""
        normalized_title = self.normalize_title(title)
        return hashlib.md5(normalized_title.encode()).hexdigest()
    
    def generate_content_hash(self, title: str, content: str = "", url: str = "") -> str:
        """Generate comprehensive content hash for duplicate detection."""
        # Normalize inputs
        title_norm = self.normalize_title(title)
        content_norm = re.sub(r'\s+', ' ', content.lower().strip())[:500]  # First 500 chars
        
        # Create composite string for hashing
        composite = f"{title_norm}|{content_norm}|{urlparse(url).path}"
        return hashlib.md5(composite.encode()).hexdigest()
    
    def extract_guid(self, entry) -> Optional[str]:
        """Extract GUID from RSS entry for unique identification."""
        # Try multiple GUID fields
        guid_fields = ['id', 'guid', 'link']
        for field in guid_fields:
            if hasattr(entry, field):
                guid_value = getattr(entry, field)
                if isinstance(guid_value, str):
                    return guid_value
                elif hasattr(guid_value, 'href'):  # For link objects
                    return guid_value.href
        return None
    
    def extract_enhanced_article_data(self, entry, rss_category: str, feed_url: str) -> Dict:
        """Extract comprehensive article data with enhanced duplicate detection fields."""
        # Basic extraction
        title = getattr(entry, 'title', '').strip()
        author = getattr(entry, 'author', None)
        link = getattr(entry, 'link', '').strip()
        
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
        
        # Clean content
        if content:
            content = re.sub(r'<[^>]+>', '', content)  # Strip HTML tags
            content = re.sub(r'\s+', ' ', content).strip()
            content = content[:2000]  # Limit length
        
        # Generate hashes and identifiers
        guid = self.extract_guid(entry)
        content_hash = self.generate_content_hash(title, content, link)
        title_hash = self.generate_title_hash(title)
        
        article_data = {
            'title': title,
            'author': author,
            'publication_date': published_date,
            'source_link': link,
            'original_summary': content,
            'rss_category': rss_category,
            'content_hash': content_hash,
            'title_hash': title_hash,
            'guid': guid,
            'feed_url': feed_url
        }
        
        # Extract image if enabled
        if self.extract_images and self.image_extractor:
            try:
                image_data = self.image_extractor.extract_image_from_entry(entry, link)
                if image_data:
                    article_data.update({
                        'image_url': image_data.get('url'),
                        'image_source': image_data.get('source')
                    })
                    logger.debug(f"Extracted image for article: {title[:50]}... - Source: {image_data.get('source')}")
            except Exception as e:
                logger.debug(f"Failed to extract image for article {title[:50]}...: {e}")
        
        return article_data
    
    def should_skip_article(self, article_data: Dict) -> Tuple[bool, str]:
        """Determine if article should be skipped based on various criteria."""
        # Skip if no title or link
        if not article_data.get('title') or not article_data.get('source_link'):
            return True, 'missing_required_fields'
        
        # Skip if title is too short (likely not a real article)
        if len(article_data['title'].strip()) < 10:
            return True, 'title_too_short'
        
        # Skip if we've already processed this item in current session
        item_key = f"{article_data.get('guid', '')}:{article_data['source_link']}"
        if item_key in self.processed_items:
            return True, 'already_processed'
        
        self.processed_items.add(item_key)
        return False, 'ok'
    
    def download_and_cache_article_images(self, articles: List[Dict]) -> Dict:
        """Download and cache images for articles (DISABLED - using RSS URLs directly)."""
        logger.debug("Image caching disabled - using original RSS image URLs directly")
        return {'downloaded': 0, 'cached': 0, 'errors': 0}
    
    def fetch_feed_with_caching(self, feed_url: str, category: str) -> Tuple[Optional[feedparser.FeedParserDict], Dict]:
        """Fetch RSS feed with HTTP caching support."""
        feed_info = {
            'etag': None,
            'last_modified': None,
            'status': None,
            'cached': False
        }
        
        try:
            # Get feed tracking info for caching
            tracking = self.db_manager.get_feed_tracking(feed_url)
            
            headers = {}
            if tracking:
                if tracking.get('etag'):
                    headers['If-None-Match'] = tracking['etag']
                if tracking.get('last_modified'):
                    headers['If-Modified-Since'] = tracking['last_modified']
            
            # Add random delay to be respectful
            time.sleep(random.uniform(0.5, 2.0))
            
            response = self.session.get(feed_url, headers=headers, timeout=15)
            feed_info['status'] = response.status_code
            
            if response.status_code == 304:  # Not Modified
                logger.info(f"Feed unchanged (304): {feed_url}")
                feed_info['cached'] = True
                return None, feed_info
            
            response.raise_for_status()
            
            # Extract caching headers
            feed_info['etag'] = response.headers.get('ETag')
            feed_info['last_modified'] = response.headers.get('Last-Modified')
            
            # Parse feed
            feed = feedparser.parse(response.content)
            
            if feed.bozo:
                logger.warning(f"Feed parsing warning for {feed_url}: {feed.bozo_exception}")
            
            logger.info(f"Fetched {len(feed.entries)} entries from {feed_url}")
            return feed, feed_info
            
        except requests.RequestException as e:
            logger.error(f"Network error fetching {feed_url}: {e}")
            feed_info['error'] = str(e)
            return None, feed_info
        except Exception as e:
            logger.error(f"Unexpected error fetching {feed_url}: {e}")
            feed_info['error'] = str(e)
            return None, feed_info
    
    def process_feed_incrementally(self, feed_url: str, category: str, max_articles: int = 50) -> Dict[str, int]:
        """Process a single RSS feed with incremental updates."""
        stats = {'new': 0, 'updated': 0, 'skipped': 0, 'errors': 0}
        
        logger.info(f"Processing feed incrementally: {feed_url} ({category})")
        
        # Fetch feed with caching
        feed, feed_info = self.fetch_feed_with_caching(feed_url, category)
        
        if feed is None:
            if feed_info.get('cached'):
                # Feed unchanged, update tracking and return
                self.db_manager.update_feed_tracking(feed_url, True, 0)
                return stats
            else:
                # Error occurred
                error_msg = feed_info.get('error', 'Unknown error')
                self.db_manager.update_feed_tracking(feed_url, False, 0, error_msg)
                stats['errors'] += 1
                return stats
        
        processed_count = 0
        for entry in feed.entries:
            if processed_count >= max_articles:
                break
            
            try:
                # Extract comprehensive article data
                article_data = self.extract_enhanced_article_data(entry, category, feed_url)
                
                # Check if should skip
                should_skip, skip_reason = self.should_skip_article(article_data)
                if should_skip:
                    if skip_reason != 'already_processed':
                        logger.debug(f"Skipping article: {skip_reason} - {article_data.get('title', 'No title')}")
                    stats['skipped'] += 1
                    continue
                
                # Insert or update article
                article_id, action = self.db_manager.insert_or_update_article(article_data)
                
                if action == 'inserted':
                    stats['new'] += 1
                    logger.debug(f"New article: {article_data['title'][:50]}...")
                elif action == 'updated':
                    stats['updated'] += 1
                    logger.debug(f"Updated article: {article_data['title'][:50]}...")
                elif action == 'duplicate':
                    stats['skipped'] += 1
                else:
                    stats['errors'] += 1
                
                processed_count += 1
                
            except Exception as e:
                logger.error(f"Error processing entry from {feed_url}: {e}")
                stats['errors'] += 1
                continue
        
        # Update feed tracking
        success = stats['errors'] == 0 or (stats['new'] + stats['updated']) > 0
        self.db_manager.update_feed_tracking(
            feed_url, success, processed_count, 
            None, feed_info.get('etag'), feed_info.get('last_modified')
        )
        
        logger.info(f"Feed processed: {feed_url} - {stats}")
        return stats
    
    def collect_category_incrementally(self, category: str, max_per_feed: int = 20) -> Dict[str, int]:
        """Collect articles from all feeds in a category incrementally."""
        category_stats = {'new': 0, 'updated': 0, 'skipped': 0, 'errors': 0}
        
        # Get validated feeds from database instead of config
        validated_feeds = self.db_manager.get_validated_feeds(category=category, only_ok=True)
        
        if not validated_feeds:
            logger.warning(f"No validated feeds found for category: {category}")
            return category_stats
        
        feed_urls = [feed['feed_url'] for feed in validated_feeds]
        logger.info(f"Incrementally collecting from category: {category} ({len(feed_urls)} validated feeds)")
        
        for feed_url in feed_urls:
            feed_stats = self.process_feed_incrementally(feed_url, category, max_per_feed)
            
            # Aggregate stats
            for key in category_stats:
                category_stats[key] += feed_stats[key]
            
            # Add delay between feeds
            time.sleep(random.uniform(1.0, 3.0))
        
        logger.info(f"Category {category} complete: {category_stats}")
        return category_stats
    
    def run_incremental_collection(self, max_per_feed: int = 15, categories: List[str] = None) -> Dict[str, int]:
        """Run complete incremental collection cycle."""
        logger.info("Starting incremental collection cycle")
        
        total_stats = {'new': 0, 'updated': 0, 'skipped': 0, 'errors': 0, 'feeds_processed': 0}
        
        if categories:
            categories_to_process = categories
        else:
            # Get available categories from database with validated feeds
            all_feeds = self.db_manager.get_validated_feeds(only_ok=True)
            categories_to_process = list(set(feed['category'] for feed in all_feeds))
            logger.info(f"Found {len(categories_to_process)} categories with validated feeds")
        
        for category in categories_to_process:
            category_stats = self.collect_category_incrementally(category, max_per_feed)
            
            # Aggregate stats
            for key in ['new', 'updated', 'skipped', 'errors']:
                total_stats[key] += category_stats[key]
            
            # Count actual validated feeds processed
            validated_feeds = self.db_manager.get_validated_feeds(category=category, only_ok=True)
            total_stats['feeds_processed'] += len(validated_feeds)
            
            # Delay between categories
            time.sleep(random.uniform(2.0, 5.0))
        
        # Image caching disabled - using original RSS URLs directly
        total_stats['images_cached'] = 0
        
        # Update collection stats
        self.collection_stats = {
            'new_articles': total_stats['new'],
            'updated_articles': total_stats['updated'], 
            'duplicates_skipped': total_stats['skipped'],
            'errors': total_stats['errors'],
            'images_cached': total_stats.get('images_cached', 0)
        }
        
        logger.info(f"Incremental collection complete: {total_stats}")
        return total_stats
    
    def get_collection_summary(self) -> Dict:
        """Get comprehensive collection summary."""
        db_stats = self.db_manager.get_incremental_stats()
        
        return {
            'session_stats': self.collection_stats,
            'database_stats': db_stats,
            'processed_items': len(self.processed_items)
        }


def main():
    """Run incremental collection."""
    collector = IncrementalCollector()
    stats = collector.run_incremental_collection()
    
    print("\n" + "="*60)
    print("INCREMENTAL COLLECTION RESULTS")
    print("="*60)
    print(f"New articles: {stats['new']}")
    print(f"Updated articles: {stats['updated']}")
    print(f"Skipped (duplicates): {stats['skipped']}")
    print(f"Errors: {stats['errors']}")
    print(f"Feeds processed: {stats['feeds_processed']}")
    
    # Show summary
    summary = collector.get_collection_summary()
    db_stats = summary['database_stats']
    print(f"\nDatabase totals:")
    print(f"Total articles: {db_stats.get('total_articles', 0)}")
    print(f"Updated articles: {db_stats.get('updated_articles', 0)}")
    print(f"Tracked feeds: {db_stats.get('tracked_feeds', 0)}")
    print("="*60)


if __name__ == "__main__":
    main()