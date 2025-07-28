"""User Interface Module: Handles user preferences and digest generation."""

import json
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging
import uuid

try:
    from .database import DatabaseManager
except ImportError:
    from database import DatabaseManager
try:
    from config import AI_CATEGORIES, MAX_ARTICLES_PER_DIGEST, DEFAULT_DIGEST_FREQUENCY, DEFAULT_OUTPUT_FORMAT
except ImportError:
    AI_CATEGORIES = ['Science & Discovery', 'Technology & Gadgets', 'Health & Wellness', 'Business & Finance', 'Global Affairs']
    MAX_ARTICLES_PER_DIGEST = 20
    DEFAULT_DIGEST_FREQUENCY = 'daily'
    DEFAULT_OUTPUT_FORMAT = 'text'

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class UserPreferencesManager:
    """Manages user preferences and settings."""
    
    def __init__(self, db_manager: DatabaseManager = None):
        self.db_manager = db_manager or DatabaseManager()
    
    def create_user(self, user_id: str = None, email: str = None, 
                   categories: List[str] = None, **kwargs) -> str:
        """Create a new user with preferences."""
        if not user_id:
            user_id = str(uuid.uuid4())[:8]  # Short UUID
        
        if categories and not all(cat in AI_CATEGORIES for cat in categories):
            invalid_cats = [cat for cat in categories if cat not in AI_CATEGORIES]
            raise ValueError(f"Invalid categories: {invalid_cats}")
        
        user_data = {
            'user_id': user_id,
            'email': email,
            'selected_categories': categories or AI_CATEGORIES[:3],  # Default to first 3
            'digest_frequency': kwargs.get('digest_frequency', DEFAULT_DIGEST_FREQUENCY),
            'articles_per_digest': kwargs.get('articles_per_digest', 10),
            'preferred_output_format': kwargs.get('preferred_output_format', DEFAULT_OUTPUT_FORMAT),
            'feedback_history': {}
        }
        
        success = self.db_manager.insert_or_update_user_preferences(user_data)
        if success:
            logger.info(f"Created user {user_id} with {len(user_data['selected_categories'])} categories")
            return user_id
        else:
            raise RuntimeError("Failed to create user preferences")
    
    def update_user_preferences(self, user_id: str, **updates) -> bool:
        """Update user preferences."""
        current_prefs = self.db_manager.get_user_preferences(user_id)
        if not current_prefs:
            raise ValueError(f"User {user_id} not found")
        
        # Validate category updates
        if 'selected_categories' in updates:
            categories = updates['selected_categories']
            if not all(cat in AI_CATEGORIES for cat in categories):
                invalid_cats = [cat for cat in categories if cat not in AI_CATEGORIES]
                raise ValueError(f"Invalid categories: {invalid_cats}")
        
        # Update preferences
        current_prefs.update(updates)
        success = self.db_manager.insert_or_update_user_preferences(current_prefs)
        
        if success:
            logger.info(f"Updated preferences for user {user_id}")
        
        return success
    
    def get_user_preferences(self, user_id: str) -> Optional[Dict]:
        """Get user preferences."""
        return self.db_manager.get_user_preferences(user_id)
    
    def add_feedback(self, user_id: str, article_id: int, feedback: str) -> bool:
        """Add user feedback for an article (like/dislike)."""
        if feedback not in ['like', 'dislike']:
            raise ValueError("Feedback must be 'like' or 'dislike'")
        
        prefs = self.get_user_preferences(user_id)
        if not prefs:
            raise ValueError(f"User {user_id} not found")
        
        feedback_history = prefs.get('feedback_history', {})
        feedback_history[str(article_id)] = {
            'feedback': feedback,
            'timestamp': datetime.now().isoformat()
        }
        
        return self.update_user_preferences(user_id, feedback_history=feedback_history)


class DigestGenerator:
    """Generates personalized news digests."""
    
    def __init__(self, db_manager: DatabaseManager = None):
        self.db_manager = db_manager or DatabaseManager()
    
    def _deduplicate_articles_by_category(self, articles: List[Dict], user_categories: List[str]) -> Dict[str, List[Dict]]:
        """Group articles by category ensuring NO duplicates across categories.
        Each article appears only ONCE under its most relevant category.
        """
        by_category = {cat: [] for cat in user_categories}
        processed_articles = set()  # Track by article ID to prevent duplicates
        
        # Sort articles by date to prioritize newer ones
        sorted_articles = sorted(articles, key=lambda x: x.get('date_collected', ''), reverse=True)
        
        for article in sorted_articles:
            article_id = article.get('id')
            
            # STRICT deduplication - skip if already processed
            if article_id in processed_articles:
                logger.debug(f"Skipping duplicate article ID {article_id}: {article.get('title', 'No title')}")
                continue
                
            # Get article categories
            article_categories = article.get('ai_categories', [])
            if isinstance(article_categories, str):
                import json
                try:
                    article_categories = json.loads(article_categories)
                except:
                    article_categories = ['Uncategorized']
            
            # Find the FIRST matching category for this article from user's preferences
            # This ensures each article goes to exactly one category
            best_category = None
            for user_cat in user_categories:
                if user_cat in article_categories:
                    best_category = user_cat
                    break
            
            # If matched, add to that category and mark as processed
            if best_category:
                by_category[best_category].append(article)
                processed_articles.add(article_id)
                logger.debug(f"Added article ID {article_id} to category '{best_category}': {article.get('title', 'No title')[:50]}")
            else:
                logger.debug(f"No category match for article ID {article_id}: {article.get('title', 'No title')[:50]}")
        
        # Remove empty categories
        return {cat: articles for cat, articles in by_category.items() if articles}
    
    def get_personalized_articles(self, user_id: str, article_count_override: int = None) -> List[Dict]:
        """Get articles personalized for the user based on their preferences.
        
        Args:
            user_id: User identifier
            article_count_override: Optional override for article count (CLI/web can override user's default)
        """
        prefs = self.db_manager.get_user_preferences(user_id)
        if not prefs:
            raise ValueError(f"User {user_id} not found")
        
        categories = prefs['selected_categories']
        
        # Use override if provided, otherwise use user's preference, capped by MAX_ARTICLES_PER_DIGEST
        if article_count_override is not None:
            article_count = min(article_count_override, MAX_ARTICLES_PER_DIGEST)
            logger.info(f"Using article count override: {article_count} (requested: {article_count_override})")
        else:
            article_count = min(prefs['articles_per_digest'], MAX_ARTICLES_PER_DIGEST)
        
        # Get more articles to allow for randomization and variety
        # Fetch from past 2 days to ensure fresh content variety
        articles = self.db_manager.get_recent_articles_by_categories(categories, days=2, limit=article_count * 5)
        
        # If we don't have enough recent articles, fall back to all articles
        if len(articles) < article_count * 2:
            logger.info(f"Only found {len(articles)} recent articles, fetching more from database")
            articles = self.db_manager.get_articles_by_categories(categories, article_count * 4)
        
        # CRITICAL: Deduplicate articles by ID first to prevent duplicate articles in digest
        seen_article_ids = set()
        deduplicated_articles = []
        for article in articles:
            article_id = article.get('id')
            if article_id and article_id not in seen_article_ids:
                deduplicated_articles.append(article)
                seen_article_ids.add(article_id)
            else:
                logger.debug(f"Removing duplicate article ID {article_id}: {article.get('title', 'No title')[:50]}")
        
        logger.info(f"Deduplicated {len(articles)} articles down to {len(deduplicated_articles)} unique articles")
        articles = deduplicated_articles
        
        # Apply variety limits: max 2 per source, max 1 per author
        articles = self._apply_variety_limits(articles)
        
        # Add randomization: shuffle the articles before final selection
        import random
        random.shuffle(articles)
        
        # Limit to requested count after variety filtering and randomization
        articles = articles[:article_count]
        
        # Apply user feedback preferences with enhanced randomization
        feedback_history = prefs.get('feedback_history', {})
        scored_articles = []
        
        import random
        
        for article in articles:
            score = 0
            article_id = str(article['id'])
            
            # Base randomization factor to ensure variety (±5 points randomly)
            score += random.randint(-5, 5)
            
            # Boost trending articles (but not too much to allow variety)
            if article.get('trending_flag'):
                score += 8
            
            # Apply feedback scoring
            if article_id in feedback_history:
                feedback = feedback_history[article_id]['feedback']
                if feedback == 'like':
                    score += 7  # Increased to prefer liked articles
                elif feedback == 'dislike':
                    score -= 15  # Strong penalty for disliked content
            
            # Strongly prefer articles with valid images (boost by 12 points)
            if self._has_valid_image(article):
                score += 12
                
            # Prefer articles with AI summaries
            if article.get('ai_summary'):
                score += 3
            
            # Add variety bonus for recent articles (past 24 hours)
            try:
                article_date = article.get('date_collected') or article.get('publication_date')
                if article_date:
                    from datetime import datetime, timedelta
                    if isinstance(article_date, str):
                        try:
                            article_datetime = datetime.fromisoformat(article_date.replace('Z', '+00:00'))
                            if article_datetime > datetime.now() - timedelta(hours=24):
                                score += 4  # Bonus for very recent articles
                        except:
                            pass
            except:
                pass
            
            # Add slight randomization to prevent deterministic ordering
            score += random.uniform(-2, 2)
            
            scored_articles.append((score, article))
        
        # Sort by score and return articles
        scored_articles.sort(key=lambda x: x[0], reverse=True)
        final_articles = [article for score, article in scored_articles]
        
        # Log variety information
        if final_articles:
            sources = set()
            categories_found = set()
            for article in final_articles:
                # Extract source
                source_link = article.get('source_link', '')
                if source_link:
                    try:
                        from urllib.parse import urlparse
                        parsed = urlparse(source_link)
                        sources.add(parsed.netloc.lower().replace('www.', ''))
                    except:
                        pass
                # Extract categories
                ai_categories = article.get('ai_categories', [])
                if isinstance(ai_categories, list):
                    categories_found.update(ai_categories)
            
            logger.info(f"Selected {len(final_articles)} articles from {len(sources)} sources across {len(categories_found)} categories")
        
        return final_articles
    
    def _has_valid_image(self, article: Dict) -> bool:
        """Check if an article has a valid, displayable image from RSS URL."""
        image_url = article.get('image_url', '')
        
        # Check for valid RSS image URL (filter out placeholders and invalid URLs)
        if image_url and image_url.startswith(('http://', 'https://')):
            # Filter out known placeholder patterns
            placeholder_patterns = [
                'placeholder.png',
                'placeholder.jpg',
                'placeholder.gif',
                'default.png',
                'default.jpg',
                'logo.png',
                'logo.jpg',
                'favicon',
                'icon.png',
                'icon.jpg'
            ]
            
            # Convert to lowercase for case-insensitive matching
            url_lower = image_url.lower()
            
            # Check if it's a placeholder
            for pattern in placeholder_patterns:
                if pattern in url_lower:
                    return False
            
            # Check for valid image extensions
            valid_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
            has_valid_extension = any(url_lower.endswith(ext) for ext in valid_extensions)
            
            # Must have valid extension and be a reasonable length (likely valid)
            if has_valid_extension and len(image_url) > 30:
                return True
        
        return False
    
    def _apply_variety_limits(self, articles: List[Dict]) -> List[Dict]:
        """Apply variety limits: max 2 per source, max 1 per author."""
        # Shuffle articles first to ensure randomness in which articles pass the limits
        import random
        shuffled_articles = articles.copy()
        random.shuffle(shuffled_articles)
        
        source_count = {}
        author_count = {}
        filtered_articles = []
        
        for article in shuffled_articles:
            # Extract source from source_link (domain name)
            source_link = article.get('source_link', '')
            if source_link:
                try:
                    from urllib.parse import urlparse
                    parsed = urlparse(source_link)
                    source = parsed.netloc.lower().replace('www.', '')
                except:
                    source = 'unknown'
            else:
                source = 'unknown'
            
            # Get author (handle None values)
            author_raw = article.get('author')
            if author_raw and isinstance(author_raw, str):
                author = author_raw.strip().lower()
            else:
                author = ''
            
            if not author or author in ['unknown', '', 'admin', 'editor']:
                author = 'unknown'
            
            # Check limits
            source_current = source_count.get(source, 0)
            author_current = author_count.get(author, 0)
            
            # Apply limits: max 2 per source, max 1 per author (unless unknown author)
            if source_current < 2 and (author == 'unknown' or author_current < 1):
                filtered_articles.append(article)
                source_count[source] = source_current + 1
                author_count[author] = author_current + 1
            
            # Stop if we have enough variety
            if len(filtered_articles) >= 50:  # Reasonable limit
                break
        
        return filtered_articles
    
    def format_text_digest(self, articles: List[Dict], user_prefs: Dict) -> str:
        """Format articles as plain text digest."""
        if not articles:
            return "No articles found for your selected categories."
        
        digest_lines = []
        digest_lines.append("=" * 60)
        digest_lines.append(f"PERSONALIZED NEWS DIGEST - {datetime.now().strftime('%Y-%m-%d')}")
        digest_lines.append(f"Categories: {', '.join(user_prefs['selected_categories'])}")
        digest_lines.append("=" * 60)
        digest_lines.append("")
        
        # Group by category ensuring no duplicates
        by_category = self._deduplicate_articles_by_category(articles, user_prefs['selected_categories'])
        
        for category, category_articles in by_category.items():
            digest_lines.append(f"## {category.upper()}")
            digest_lines.append("-" * 40)
            
            for i, article in enumerate(category_articles[:5], 1):  # Limit per category
                trending_marker = " 🔥" if article.get('trending_flag') else ""
                digest_lines.append(f"{i}. {article['title']}{trending_marker}")
                
                # Use AI summary if available, otherwise original
                summary = article.get('ai_summary') or article.get('original_summary', '')
                if summary:
                    digest_lines.append(f"   {summary}")
                
                if article.get('author'):
                    digest_lines.append(f"   Author: {article['author']}")
                
                digest_lines.append(f"   Link: {article['source_link']}")
                digest_lines.append("")
            
            digest_lines.append("")
        
        # Add footer
        digest_lines.append("=" * 60)
        digest_lines.append(f"Generated {len(articles)} articles from your selected categories")
        digest_lines.append("Use feedback commands to improve future digests")
        digest_lines.append("=" * 60)
        
        return "\n".join(digest_lines)
    
    def format_markdown_digest(self, articles: List[Dict], user_prefs: Dict) -> str:
        """Format articles as Markdown digest."""
        if not articles:
            return "# No Articles Found\n\nNo articles found for your selected categories."
        
        digest_lines = []
        digest_lines.append(f"# Personalized News Digest - {datetime.now().strftime('%Y-%m-%d')}")
        digest_lines.append(f"**Categories:** {', '.join(user_prefs['selected_categories'])}")
        digest_lines.append("")
        
        # Group by category ensuring no duplicates
        by_category = self._deduplicate_articles_by_category(articles, user_prefs['selected_categories'])
        
        for category, category_articles in by_category.items():
            digest_lines.append(f"## {category}")
            digest_lines.append("")
            
            for article in category_articles[:5]:  # Limit per category
                trending_marker = " 🔥" if article.get('trending_flag') else ""
                digest_lines.append(f"### [{article['title']}]({article['source_link']}){trending_marker}")
                
                # Use AI summary if available
                summary = article.get('ai_summary') or article.get('original_summary', '')
                if summary:
                    digest_lines.append(summary)
                
                metadata_parts = []
                if article.get('author'):
                    metadata_parts.append(f"**Author:** {article['author']}")
                if article.get('publication_date'):
                    metadata_parts.append(f"**Date:** {article['publication_date'][:10]}")
                
                if metadata_parts:
                    digest_lines.append(f"*{' | '.join(metadata_parts)}*")
                
                digest_lines.append("")
        
        # Add footer
        digest_lines.append("---")
        digest_lines.append(f"*Generated {len(articles)} articles from your selected categories*")
        digest_lines.append("*Use feedback commands to improve future digests*")
        
        return "\n".join(digest_lines)
    
    def format_email_ready_digest(self, articles: List[Dict], user_prefs: Dict) -> Dict[str, str]:
        """Format articles as email-ready content with subject line."""
        if not articles:
            return {
                'subject': f"📰 News Update - We're Refreshing Your Sources",
                'body': "No new articles found for your selected categories today."
            }
        
        # Generate subject line
        trending_count = sum(1 for article in articles if article.get('trending_flag'))
        category_names = user_prefs['selected_categories']
        
        if trending_count > 0:
            subject = f"📈 {trending_count} Trending + {len(articles)} Articles - {category_names[0]} & More"
        else:
            subject = f"📰 {len(articles)} Articles - {', '.join(category_names[:2])}"
        
        if len(category_names) > 2:
            subject += f" + {len(category_names) - 2} More"
        
        subject += f" | {datetime.now().strftime('%m/%d')}"
        
        # Generate body (HTML-like formatting for email)
        body_lines = []
        body_lines.append(f"Your personalized news digest for {datetime.now().strftime('%B %d, %Y')}")
        body_lines.append("")
        body_lines.append("=" * 50)
        
        # Group and format articles ensuring no duplicates
        by_category = self._deduplicate_articles_by_category(articles, user_prefs['selected_categories'])
        
        for category, category_articles in by_category.items():
            body_lines.append(f"\n{category.upper()}")
            body_lines.append("-" * 20)
            
            for i, article in enumerate(category_articles[:3], 1):  # Fewer per category for email
                trending_marker = " [TRENDING]" if article.get('trending_flag') else ""
                body_lines.append(f"\n{i}. {article['title']}{trending_marker}")
                
                summary = article.get('ai_summary') or article.get('original_summary', '')
                if summary:
                    # Limit summary length for email
                    body_lines.append(f"   {summary[:150]}...")
                
                body_lines.append(f"   Read more: {article['source_link']}")
        
        body_lines.append("\n" + "=" * 50)
        body_lines.append(f"Total articles: {len(articles)}")
        body_lines.append("Reply with feedback to improve future digests!")
        
        return {
            'subject': subject,
            'body': "\n".join(body_lines)
        }
    
    def generate_digest(self, user_id: str, article_count_override: int = None) -> Dict[str, str]:
        """Generate a complete digest for the user.
        
        Args:
            user_id: User identifier
            article_count_override: Optional override for article count (CLI/web can override user's default)
        """
        # Get user preferences
        user_prefs = self.db_manager.get_user_preferences(user_id)
        if not user_prefs:
            raise ValueError(f"User {user_id} not found")
        
        # Get personalized articles
        articles = self.get_personalized_articles(user_id, article_count_override)
        
        # Format according to preference
        output_format = user_prefs.get('preferred_output_format', 'text')
        
        if output_format == 'markdown':
            content = self.format_markdown_digest(articles, user_prefs)
            return {'format': 'markdown', 'content': content}
        
        elif output_format == 'email':
            email_data = self.format_email_ready_digest(articles, user_prefs)
            return {
                'format': 'email',
                'subject': email_data['subject'],
                'content': email_data['body']
            }
        
        else:  # Default to text
            content = self.format_text_digest(articles, user_prefs)
            return {'format': 'text', 'content': content}


def main():
    """Test the user interface module."""
    # Create a test user
    prefs_manager = UserPreferencesManager()
    user_id = prefs_manager.create_user(
        categories=['Technology & Gadgets', 'Science & Discovery'],
        articles_per_digest=5
    )
    
    print(f"Created test user: {user_id}")
    
    # Generate a digest
    digest_gen = DigestGenerator()
    digest = digest_gen.generate_digest(user_id)
    
    print(f"\nGenerated digest ({digest['format']} format):")
    print("=" * 60)
    if digest['format'] == 'email':
        print(f"Subject: {digest['subject']}")
        print("-" * 40)
    print(digest['content'])


if __name__ == "__main__":
    main()