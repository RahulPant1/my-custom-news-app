"""RSS feed validation and testing utilities."""

import feedparser
import requests
from urllib.parse import urlparse
from typing import Dict, List, Tuple, Optional
import logging
from xml.etree import ElementTree as ET

from database import DatabaseManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RSSValidator:
    """Validates RSS feeds for accessibility and data structure."""
    
    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'NewsDigest/1.0 (RSS Feed Validator)'
        })
    
    def validate_single_feed(self, url: str) -> Dict:
        """Validate a single RSS feed URL."""
        result = {
            'url': url,
            'valid': False,
            'accessible': False,
            'has_items': False,
            'item_count': 0,
            'title': None,
            'description': None,
            'error': None,
            'sample_articles': []
        }
        
        try:
            # Check URL format
            parsed_url = urlparse(url)
            if not parsed_url.scheme or not parsed_url.netloc:
                result['error'] = "Invalid URL format"
                return result
            
            # Test accessibility
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            result['accessible'] = True
            
            # Check if it's valid XML
            try:
                ET.fromstring(response.content)
            except ET.ParseError as e:
                result['error'] = f"Invalid XML format: {e}"
                return result
            
            # Parse with feedparser
            feed = feedparser.parse(response.content)
            
            if feed.bozo:
                result['error'] = f"Feed parsing error: {feed.bozo_exception}"
                return result
            
            result['valid'] = True
            result['title'] = getattr(feed.feed, 'title', 'No title')
            result['description'] = getattr(feed.feed, 'description', 'No description')
            result['item_count'] = len(feed.entries)
            result['has_items'] = result['item_count'] > 0
            
            # Extract sample articles (first 3)
            for entry in feed.entries[:3]:
                article = {
                    'title': getattr(entry, 'title', 'No title'),
                    'link': getattr(entry, 'link', 'No link'),
                    'published': getattr(entry, 'published', 'No date'),
                    'summary': getattr(entry, 'summary', 'No summary')[:200] + '...'
                }
                result['sample_articles'].append(article)
            
            logger.info(f"✓ Feed validated: {url} ({result['item_count']} items)")
            
        except requests.RequestException as e:
            result['error'] = f"Network error: {e}"
            logger.error(f"✗ Feed inaccessible: {url} - {e}")
        except Exception as e:
            result['error'] = f"Unexpected error: {e}"
            logger.error(f"✗ Feed validation failed: {url} - {e}")
        
        return result
    
    def validate_all_feeds(self) -> Dict[str, List[Dict]]:
        """Validate all RSS feeds from database."""
        results = {}
        
        logger.info("Starting RSS feed validation for all categories...")
        
        # Get feeds from database
        db_manager = DatabaseManager()
        all_feeds = db_manager.get_all_feeds()
        
        # Group feeds by category
        feeds_by_category = {}
        for feed in all_feeds:
            category = feed['category']
            if category not in feeds_by_category:
                feeds_by_category[category] = []
            feeds_by_category[category].append(feed['feed_url'])
        
        for category, feed_urls in feeds_by_category.items():
            logger.info(f"Validating feeds for category: {category}")
            category_results = []
            
            for feed_url in feed_urls:
                result = self.validate_single_feed(feed_url)
                category_results.append(result)
            
            results[category] = category_results
            
            # Log category summary
            valid_count = sum(1 for r in category_results if r['valid'])
            logger.info(f"Category {category}: {valid_count}/{len(feed_urls)} feeds valid")
        
        return results
    
    def get_validation_summary(self, results: Dict[str, List[Dict]]) -> Dict:
        """Generate a summary of validation results."""
        total_feeds = 0
        valid_feeds = 0
        accessible_feeds = 0
        feeds_with_items = 0
        total_articles = 0
        
        category_stats = {}
        problematic_feeds = []
        
        for category, feed_results in results.items():
            category_valid = 0
            category_total = len(feed_results)
            category_articles = 0
            
            for result in feed_results:
                total_feeds += 1
                if result['accessible']:
                    accessible_feeds += 1
                if result['valid']:
                    valid_feeds += 1
                    category_valid += 1
                if result['has_items']:
                    feeds_with_items += 1
                    total_articles += result['item_count']
                    category_articles += result['item_count']
                
                if not result['valid']:
                    problematic_feeds.append({
                        'category': category,
                        'url': result['url'],
                        'error': result['error']
                    })
            
            category_stats[category] = {
                'valid': category_valid,
                'total': category_total,
                'articles': category_articles
            }
        
        return {
            'total_feeds': total_feeds,
            'valid_feeds': valid_feeds,
            'accessible_feeds': accessible_feeds,
            'feeds_with_items': feeds_with_items,
            'total_articles': total_articles,
            'category_stats': category_stats,
            'problematic_feeds': problematic_feeds
        }
    
    def print_validation_report(self, results: Dict[str, List[Dict]]):
        """Print a formatted validation report."""
        summary = self.get_validation_summary(results)
        
        print("\n" + "="*60)
        print("RSS FEED VALIDATION REPORT")
        print("="*60)
        
        print(f"Total feeds checked: {summary['total_feeds']}")
        print(f"Accessible feeds: {summary['accessible_feeds']}")
        print(f"Valid RSS feeds: {summary['valid_feeds']}")
        print(f"Feeds with content: {summary['feeds_with_items']}")
        print(f"Total articles found: {summary['total_articles']}")
        
        print("\nCATEGORY BREAKDOWN:")
        print("-" * 40)
        for category, stats in summary['category_stats'].items():
            print(f"{category}: {stats['valid']}/{stats['total']} valid ({stats['articles']} articles)")
        
        if summary['problematic_feeds']:
            print(f"\nPROBLEMATIC FEEDS ({len(summary['problematic_feeds'])}):")
            print("-" * 40)
            for feed in summary['problematic_feeds']:
                print(f"• {feed['category']}: {feed['url']}")
                print(f"  Error: {feed['error']}")
        
        print("\n" + "="*60)


def run_feed_validation():
    """Run RSS feed validation and display results."""
    validator = RSSValidator()
    results = validator.validate_all_feeds()
    validator.print_validation_report(results)
    return results


if __name__ == "__main__":
    run_feed_validation()