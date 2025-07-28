"""Database models and operations for the news digest application."""

import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import logging

try:
    from config import DATABASE_PATH
except ImportError:
    DATABASE_PATH = 'news_digest.db'

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages database operations for articles and user preferences."""
    
    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize database with required tables."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Articles table with enhanced duplicate detection and image support
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    author TEXT,
                    publication_date TEXT,
                    source_link TEXT UNIQUE NOT NULL,
                    original_summary TEXT,
                    rss_category TEXT,
                    ai_categories TEXT,  -- JSON string for multi-label
                    ai_summary TEXT,
                    trending_flag BOOLEAN DEFAULT FALSE,
                    date_collected TEXT DEFAULT CURRENT_TIMESTAMP,
                    date_updated TEXT DEFAULT CURRENT_TIMESTAMP,
                    content_hash TEXT UNIQUE,  -- For deduplication
                    title_hash TEXT,  -- Hash of normalized title
                    guid TEXT,  -- RSS GUID for unique identification
                    etag TEXT,  -- HTTP ETag for feed caching
                    last_modified TEXT,  -- Last-Modified header
                    image_url TEXT,  -- Primary image URL
                    image_source TEXT,  -- 'rss', 'opengraph', 'stock'
                    image_cached_path TEXT,  -- Local cached image path
                    image_size INTEGER,  -- Image file size in bytes
                    image_width INTEGER,  -- Image width in pixels
                    image_height INTEGER  -- Image height in pixels
                )
            ''')
            
            # User preferences table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_preferences (
                    user_id TEXT PRIMARY KEY,
                    email TEXT,
                    selected_categories TEXT,  -- JSON string
                    digest_frequency TEXT DEFAULT 'daily',
                    articles_per_digest INTEGER DEFAULT 10,
                    preferred_output_format TEXT DEFAULT 'text',
                    feedback_history TEXT DEFAULT '{}',  -- JSON string
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create indexes for better performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_articles_date ON articles(date_collected)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_articles_categories ON articles(ai_categories)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_articles_hash ON articles(content_hash)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_articles_title_hash ON articles(title_hash)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_articles_guid ON articles(guid)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_articles_updated ON articles(date_updated)')
            # cursor.execute('CREATE INDEX IF NOT EXISTS idx_articles_image_source ON articles(image_source)')  # Column doesn't exist in current schema
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_articles_has_image ON articles(image_url)')
            
            # RSS feeds table with validation status
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS rss_feeds (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    feed_url TEXT UNIQUE NOT NULL,
                    feed_title TEXT,
                    validation_status TEXT DEFAULT 'unknown',  -- 'ok', 'error', 'unknown'
                    validation_message TEXT,
                    last_validated TEXT,
                    is_active BOOLEAN DEFAULT TRUE,
                    date_added TEXT DEFAULT CURRENT_TIMESTAMP,
                    date_updated TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Add feed tracking table for incremental updates
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS feed_tracking (
                    feed_url TEXT PRIMARY KEY,
                    last_fetched TEXT DEFAULT CURRENT_TIMESTAMP,
                    last_modified TEXT,
                    etag TEXT,
                    last_article_count INTEGER DEFAULT 0,
                    success_count INTEGER DEFAULT 0,
                    error_count INTEGER DEFAULT 0,
                    last_error TEXT
                )
            ''')
            
            # Email delivery tracking table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS email_deliveries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    email_address TEXT NOT NULL,
                    subject_line TEXT,
                    digest_content TEXT,  -- JSON of the digest data
                    email_html TEXT,  -- Full HTML content
                    delivery_status TEXT DEFAULT 'pending',  -- 'pending', 'sent', 'failed', 'bounced'
                    delivery_method TEXT,  -- 'smtp', 'sendgrid', etc.
                    sent_at TEXT,
                    delivery_id TEXT,  -- External delivery ID from service
                    error_message TEXT,
                    open_count INTEGER DEFAULT 0,
                    click_count INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES user_preferences (user_id)
                )
            ''')
            
            # Article feedback tracking table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS feedback_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    article_id INTEGER NOT NULL,
                    email_delivery_id INTEGER,
                    feedback_type TEXT NOT NULL,  -- 'like', 'dislike', 'more_like_this', 'share'
                    feedback_source TEXT DEFAULT 'email',  -- 'email', 'web', 'cli'
                    share_platform TEXT,  -- 'twitter', 'linkedin', 'whatsapp', etc.
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES user_preferences (user_id),
                    FOREIGN KEY (article_id) REFERENCES articles (id),
                    FOREIGN KEY (email_delivery_id) REFERENCES email_deliveries (id)
                )
            ''')
            
            # Engagement metrics summary table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS engagement_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    metric_date TEXT NOT NULL,  -- YYYY-MM-DD
                    emails_sent INTEGER DEFAULT 0,
                    emails_opened INTEGER DEFAULT 0,
                    total_clicks INTEGER DEFAULT 0,
                    articles_liked INTEGER DEFAULT 0,
                    articles_disliked INTEGER DEFAULT 0,
                    shares_total INTEGER DEFAULT 0,
                    shares_twitter INTEGER DEFAULT 0,
                    shares_linkedin INTEGER DEFAULT 0,
                    shares_whatsapp INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES user_preferences (user_id),
                    UNIQUE(user_id, metric_date)
                )
            ''')
            
            # Email preferences table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS email_preferences (
                    user_id TEXT PRIMARY KEY,
                    email_enabled BOOLEAN DEFAULT TRUE,
                    delivery_frequency TEXT DEFAULT 'daily',  -- 'daily', 'weekly', 'manual'
                    delivery_time TEXT DEFAULT '08:00',  -- HH:MM format
                    delivery_timezone TEXT DEFAULT 'UTC',
                    email_format TEXT DEFAULT 'html',  -- 'html', 'text'
                    include_feedback_links BOOLEAN DEFAULT TRUE,
                    include_social_sharing BOOLEAN DEFAULT TRUE,
                    personalized_subject BOOLEAN DEFAULT TRUE,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES user_preferences (user_id)
                )
            ''')
            
            # Daily one-liners table for email highlights
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS daily_oneliners (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    oneliner TEXT NOT NULL,
                    generation_date TEXT NOT NULL,  -- YYYY-MM-DD
                    generation_model TEXT,  -- AI model used
                    usage_count INTEGER DEFAULT 0,  -- Track how often used
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(category, oneliner, generation_date)
                )
            ''')
            
            # Stock images table for fallback images
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS stock_images (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    image_path TEXT UNIQUE NOT NULL,  -- Relative path to image
                    image_name TEXT NOT NULL,  -- Human-readable name
                    category TEXT,  -- Optional category association
                    image_type TEXT DEFAULT 'general',  -- 'general', 'category-specific'
                    file_size INTEGER,  -- File size in bytes
                    width INTEGER,  -- Image width
                    height INTEGER,  -- Image height
                    usage_count INTEGER DEFAULT 0,  -- How often used
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create indexes for email tables
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_email_deliveries_user ON email_deliveries(user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_email_deliveries_status ON email_deliveries(delivery_status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_email_deliveries_sent ON email_deliveries(sent_at)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_feedback_user_article ON feedback_history(user_id, article_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_feedback_type ON feedback_history(feedback_type)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_feedback_date ON feedback_history(created_at)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_engagement_user_date ON engagement_metrics(user_id, metric_date)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_oneliners_date_category ON daily_oneliners(generation_date, category)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_oneliners_usage ON daily_oneliners(usage_count)')
            
            conn.commit()
            logger.info("Database initialized successfully")
            
            # Run migrations to add new columns to existing databases
            self._run_migrations(cursor)
    
    def _run_migrations(self, cursor):
        """Run database migrations to add new columns to existing tables."""
        try:
            # Check if image columns exist in articles table
            cursor.execute("PRAGMA table_info(articles)")
            columns = [column[1] for column in cursor.fetchall()]
            
            # Add image columns if they don't exist
            image_columns = [
                ('image_url', 'TEXT'),
                ('image_source', 'TEXT'),
                ('image_cached_path', 'TEXT'),
                ('image_size', 'INTEGER'),
                ('image_width', 'INTEGER'),
                ('image_height', 'INTEGER')
            ]
            
            for column_name, column_type in image_columns:
                if column_name not in columns:
                    try:
                        cursor.execute(f'ALTER TABLE articles ADD COLUMN {column_name} {column_type}')
                        logger.info(f"Added column {column_name} to articles table")
                    except sqlite3.Error as e:
                        logger.warning(f"Could not add column {column_name}: {e}")
            
            # Create indexes for new columns if they don't exist
            try:
                # cursor.execute('CREATE INDEX IF NOT EXISTS idx_articles_image_source ON articles(image_source)')  # Column doesn't exist in current schema
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_articles_has_image ON articles(image_url)')
            except sqlite3.Error as e:
                logger.warning(f"Could not create article image indexes: {e}")
            
            # Create stock_images indexes only if table exists
            try:
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='stock_images'")
                if cursor.fetchone():
                    cursor.execute('CREATE INDEX IF NOT EXISTS idx_stock_images_active ON stock_images(is_active)')
                    cursor.execute('CREATE INDEX IF NOT EXISTS idx_stock_images_type ON stock_images(image_type)')
            except sqlite3.Error as e:
                logger.warning(f"Could not create image indexes: {e}")
                
        except Exception as e:
            logger.error(f"Error running migrations: {e}")
    
    def insert_or_update_article(self, article_data: Dict) -> Tuple[Optional[int], str]:
        """Insert a new article or update existing one. Returns (article_id, action)."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Check if article exists by multiple criteria
                existing_id = self.find_duplicate_article(article_data, cursor)
                
                if existing_id:
                    # Update existing article with new information
                    cursor.execute('''
                        UPDATE articles 
                        SET original_summary = COALESCE(?, original_summary),
                            author = COALESCE(?, author),
                            publication_date = COALESCE(?, publication_date),
                            image_url = COALESCE(?, image_url),
                            image_source = COALESCE(?, image_source),
                            image_cached_path = COALESCE(?, image_cached_path),
                            image_size = COALESCE(?, image_size),
                            image_width = COALESCE(?, image_width),
                            image_height = COALESCE(?, image_height),
                            date_updated = CURRENT_TIMESTAMP
                        WHERE id = ?
                    ''', (
                        article_data.get('original_summary'),
                        article_data.get('author'),
                        article_data.get('publication_date'),
                        article_data.get('image_url'),
                        article_data.get('image_source'),
                        article_data.get('image_cached_path'),
                        article_data.get('image_size'),
                        article_data.get('image_width'),
                        article_data.get('image_height'),
                        existing_id
                    ))
                    return existing_id, 'updated'
                else:
                    # Insert new article
                    cursor.execute('''
                        INSERT INTO articles 
                        (title, author, publication_date, source_link, original_summary, 
                         rss_category, ai_categories, ai_summary, trending_flag, 
                         content_hash, title_hash, guid, etag, last_modified,
                         image_url, image_source, image_cached_path, image_size, 
                         image_width, image_height)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        article_data['title'],
                        article_data.get('author'),
                        article_data.get('publication_date'),
                        article_data['source_link'],
                        article_data.get('original_summary'),
                        article_data.get('rss_category'),
                        json.dumps(article_data.get('ai_categories', [])),
                        article_data.get('ai_summary'),
                        article_data.get('trending_flag', False),
                        article_data.get('content_hash'),
                        article_data.get('title_hash'),
                        article_data.get('guid'),
                        article_data.get('etag'),
                        article_data.get('last_modified'),
                        article_data.get('image_url'),
                        article_data.get('image_source'),
                        article_data.get('image_cached_path'),
                        article_data.get('image_size'),
                        article_data.get('image_width'),
                        article_data.get('image_height')
                    ))
                    return cursor.lastrowid, 'inserted'
                    
        except sqlite3.IntegrityError as e:
            logger.warning(f"Integrity constraint violation: {e}")
            return None, 'duplicate'
        except Exception as e:
            logger.error(f"Error inserting/updating article: {e}")
            return None, 'error'
    
    def insert_article(self, article_data: Dict) -> Optional[int]:
        """Insert article (legacy method for backward compatibility)."""
        article_id, action = self.insert_or_update_article(article_data)
        return article_id if action == 'inserted' else None
    
    def find_duplicate_article(self, article_data: Dict, cursor=None) -> Optional[int]:
        """Find duplicate article using multiple detection methods."""
        if cursor is None:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                return self._find_duplicate_internal(article_data, cursor)
        else:
            return self._find_duplicate_internal(article_data, cursor)
    
    def _find_duplicate_internal(self, article_data: Dict, cursor) -> Optional[int]:
        """Internal duplicate detection logic."""
        # Method 1: Exact URL match
        if article_data.get('source_link'):
            cursor.execute('SELECT id FROM articles WHERE source_link = ?', 
                         (article_data['source_link'],))
            result = cursor.fetchone()
            if result:
                return result[0]
        
        # Method 2: GUID match (RSS unique identifier)
        if article_data.get('guid'):
            cursor.execute('SELECT id FROM articles WHERE guid = ?', 
                         (article_data['guid'],))
            result = cursor.fetchone()
            if result:
                return result[0]
        
        # Method 3: Content hash match
        if article_data.get('content_hash'):
            cursor.execute('SELECT id FROM articles WHERE content_hash = ?', 
                         (article_data['content_hash'],))
            result = cursor.fetchone()
            if result:
                return result[0]
        
        # Method 4: Title hash match (for similar titles)
        if article_data.get('title_hash'):
            cursor.execute('SELECT id FROM articles WHERE title_hash = ?', 
                         (article_data['title_hash'],))
            result = cursor.fetchone()
            if result:
                return result[0]
        
        return None
    
    def get_articles_by_categories(self, categories: List[str], limit: int = 20) -> List[Dict]:
        """Retrieve articles filtered by categories."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Build query to match any of the specified categories
                category_conditions = []
                params = []
                
                for category in categories:
                    category_conditions.append("ai_categories LIKE ?")
                    params.append(f'%"{category}"%')
                
                query = f'''
                    SELECT id, title, author, publication_date, source_link, 
                           original_summary, ai_categories, ai_summary, trending_flag, date_collected,
                           image_url, image_source, image_cached_path, image_size, image_width, image_height
                    FROM articles 
                    WHERE ({" OR ".join(category_conditions)})
                    ORDER BY date_collected DESC 
                    LIMIT ?
                '''
                params.append(limit)
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                articles = []
                for row in rows:
                    articles.append({
                        'id': row[0],
                        'title': row[1],
                        'author': row[2],
                        'publication_date': row[3],
                        'source_link': row[4],
                        'original_summary': row[5],
                        'ai_categories': json.loads(row[6]) if row[6] else [],
                        'ai_summary': row[7],
                        'trending_flag': row[8],
                        'date_collected': row[9],
                        'image_url': row[10],
                        'image_source': row[11],
                        'image_cached_path': row[12],
                        'image_size': row[13],
                        'image_width': row[14],
                        'image_height': row[15]
                    })
                
                return articles
                
        except Exception as e:
            logger.error(f"Error retrieving articles: {e}")
            return []
    
    def get_recent_articles_by_categories(self, categories: List[str], days: int = 2, limit: int = 50) -> List[Dict]:
        """Retrieve recent articles filtered by categories from the past N days."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Calculate date threshold
                from datetime import datetime, timedelta
                date_threshold = (datetime.now() - timedelta(days=days)).isoformat()
                
                # Build query to match any of the specified categories
                category_conditions = []
                params = []
                
                for category in categories:
                    category_conditions.append("ai_categories LIKE ?")
                    params.append(f'%"{category}"%')
                
                # Add date threshold parameters
                params.extend([date_threshold, date_threshold, limit])
                
                query = f'''
                    SELECT id, title, author, publication_date, source_link, 
                           original_summary, ai_categories, ai_summary, trending_flag, date_collected,
                           image_url, image_source, image_cached_path, image_size, image_width, image_height
                    FROM articles 
                    WHERE ({" OR ".join(category_conditions)})
                    AND (date_collected >= ? OR publication_date >= ?)
                    ORDER BY RANDOM()
                    LIMIT ?
                '''
                # Note: Using RANDOM() for initial randomization, then we'll add more randomization in Python
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                articles = []
                for row in rows:
                    articles.append({
                        'id': row[0],
                        'title': row[1],
                        'author': row[2],
                        'publication_date': row[3],
                        'source_link': row[4],
                        'original_summary': row[5],
                        'ai_categories': json.loads(row[6]) if row[6] else [],
                        'ai_summary': row[7],
                        'trending_flag': row[8],
                        'date_collected': row[9],
                        'image_url': row[10],
                        'image_source': row[11],
                        'image_cached_path': row[12],
                        'image_size': row[13],
                        'image_width': row[14],
                        'image_height': row[15]
                    })
                
                logger.info(f"Retrieved {len(articles)} recent articles from past {days} days")
                return articles
                
        except Exception as e:
            logger.error(f"Error retrieving recent articles: {e}")
            return []
    
    def get_all_articles(self) -> List[Dict]:
        """Retrieve all articles from the database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT id, title, author, publication_date, source_link, 
                           original_summary, ai_categories, ai_summary, trending_flag, date_collected
                    FROM articles 
                    ORDER BY date_collected DESC
                ''')
                rows = cursor.fetchall()
                
                articles = []
                for row in rows:
                    articles.append({
                        'id': row[0],
                        'title': row[1],
                        'author': row[2],
                        'publication_date': row[3],
                        'source_link': row[4],
                        'original_summary': row[5],
                        'ai_categories': json.loads(row[6]) if row[6] else [],
                        'ai_summary': row[7],
                        'trending_flag': row[8],
                        'date_collected': row[9]
                    })
                
                return articles
                
        except Exception as e:
            logger.error(f"Error retrieving all articles: {e}")
            return []
    
    def insert_or_update_user_preferences(self, user_data: Dict) -> bool:
        """Insert or update user preferences."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT OR REPLACE INTO user_preferences 
                    (user_id, email, selected_categories, digest_frequency, 
                     articles_per_digest, preferred_output_format, feedback_history)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    user_data['user_id'],
                    user_data.get('email'),
                    json.dumps(user_data.get('selected_categories', [])),
                    user_data.get('digest_frequency', 'daily'),
                    user_data.get('articles_per_digest', 10),
                    user_data.get('preferred_output_format', 'text'),
                    json.dumps(user_data.get('feedback_history', {}))
                ))
                
                return cursor.rowcount > 0
                
        except Exception as e:
            logger.error(f"Error saving user preferences: {e}")
            return False
    
    def get_user_preferences(self, user_id: str) -> Optional[Dict]:
        """Retrieve user preferences by user ID."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT user_id, email, selected_categories, digest_frequency,
                           articles_per_digest, preferred_output_format, feedback_history
                    FROM user_preferences 
                    WHERE user_id = ?
                ''', (user_id,))
                
                row = cursor.fetchone()
                if row:
                    return {
                        'user_id': row[0],
                        'email': row[1],
                        'selected_categories': json.loads(row[2]) if row[2] else [],
                        'digest_frequency': row[3],
                        'articles_per_digest': row[4],
                        'preferred_output_format': row[5],
                        'feedback_history': json.loads(row[6]) if row[6] else {}
                    }
                return None
                
        except Exception as e:
            logger.error(f"Error retrieving user preferences: {e}")
            return None
    
    def delete_user_preferences(self, user_id: str) -> bool:
        """Delete user preferences from the database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Delete user preferences
                cursor.execute("DELETE FROM user_preferences WHERE user_id = ?", (user_id,))
                
                # Check if deletion was successful
                deleted_rows = cursor.rowcount
                
                if deleted_rows > 0:
                    logger.info(f"Successfully deleted user preferences for {user_id}")
                    return True
                else:
                    logger.warning(f"No user preferences found to delete for {user_id}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error deleting user preferences for {user_id}: {e}")
            return False
    
    def get_article_count(self) -> int:
        """Get total number of articles in database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM articles")
                return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"Error getting article count: {e}")
            return 0
    
    def update_feed_tracking(self, feed_url: str, success: bool, article_count: int = 0, 
                           error_msg: str = None, etag: str = None, last_modified: str = None) -> bool:
        """Update feed tracking information for incremental updates."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                if success:
                    cursor.execute('''
                        INSERT OR REPLACE INTO feed_tracking 
                        (feed_url, last_fetched, etag, last_modified, last_article_count, 
                         success_count, error_count, last_error)
                        VALUES (?, CURRENT_TIMESTAMP, ?, ?, ?, 
                                COALESCE((SELECT success_count FROM feed_tracking WHERE feed_url = ?), 0) + 1,
                                COALESCE((SELECT error_count FROM feed_tracking WHERE feed_url = ?), 0),
                                NULL)
                    ''', (feed_url, etag, last_modified, article_count, feed_url, feed_url))
                else:
                    cursor.execute('''
                        INSERT OR REPLACE INTO feed_tracking 
                        (feed_url, last_fetched, etag, last_modified, last_article_count, 
                         success_count, error_count, last_error)
                        VALUES (?, CURRENT_TIMESTAMP, 
                                COALESCE((SELECT etag FROM feed_tracking WHERE feed_url = ?), ?),
                                COALESCE((SELECT last_modified FROM feed_tracking WHERE feed_url = ?), ?),
                                COALESCE((SELECT last_article_count FROM feed_tracking WHERE feed_url = ?), 0),
                                COALESCE((SELECT success_count FROM feed_tracking WHERE feed_url = ?), 0),
                                COALESCE((SELECT error_count FROM feed_tracking WHERE feed_url = ?), 0) + 1,
                                ?)
                    ''', (feed_url, feed_url, etag, feed_url, last_modified, feed_url, feed_url, feed_url, error_msg))
                
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error updating feed tracking: {e}")
            return False
    
    def get_feed_tracking(self, feed_url: str) -> Optional[Dict]:
        """Get feed tracking information for incremental updates."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT feed_url, last_fetched, last_modified, etag, last_article_count,
                           success_count, error_count, last_error
                    FROM feed_tracking 
                    WHERE feed_url = ?
                ''', (feed_url,))
                
                row = cursor.fetchone()
                if row:
                    return {
                        'feed_url': row[0],
                        'last_fetched': row[1],
                        'last_modified': row[2],
                        'etag': row[3],
                        'last_article_count': row[4],
                        'success_count': row[5],
                        'error_count': row[6],
                        'last_error': row[7]
                    }
                return None
        except Exception as e:
            logger.error(f"Error getting feed tracking: {e}")
            return None
    
    def cleanup_old_articles(self, days_old: int = 30) -> int:
        """Remove articles older than specified days."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    DELETE FROM articles 
                    WHERE date_collected < datetime('now', '-{} days')
                '''.format(days_old))
                return cursor.rowcount
        except Exception as e:
            logger.error(f"Error cleaning up old articles: {e}")
            return 0
    
    def get_incremental_stats(self) -> Dict[str, int]:
        """Get statistics about incremental updates."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get article update stats
                cursor.execute('''
                    SELECT 
                        COUNT(*) as total_articles,
                        COUNT(CASE WHEN date_updated > date_collected THEN 1 END) as updated_articles
                    FROM articles
                ''')
                article_stats = cursor.fetchone()
                
                # Get feed tracking stats
                cursor.execute('''
                    SELECT 
                        COUNT(*) as tracked_feeds,
                        SUM(success_count) as total_successes,
                        SUM(error_count) as total_errors
                    FROM feed_tracking
                ''')
                feed_stats = cursor.fetchone()
                
                return {
                    'total_articles': article_stats[0] or 0,
                    'updated_articles': article_stats[1] or 0,
                    'tracked_feeds': feed_stats[0] or 0,
                    'total_successes': feed_stats[1] or 0,
                    'total_errors': feed_stats[2] or 0,
                    'processed_today': 0 # Placeholder
                }
        except Exception as e:
            logger.error(f"Error getting incremental stats: {e}")
            return {'error': str(e)}

    # RSS Feed Management Methods
    
    def add_rss_feed(self, category: str, feed_url: str, feed_title: str = None) -> bool:
        """Add a new RSS feed to the database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO rss_feeds 
                    (category, feed_url, feed_title, validation_status, last_validated, date_updated)
                    VALUES (?, ?, ?, 'unknown', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ''', (category, feed_url, feed_title))
                conn.commit()
                logger.info(f"Added RSS feed: {feed_url} to category: {category}")
                return True
        except Exception as e:
            logger.error(f"Error adding RSS feed: {e}")
            return False
    
    def remove_rss_feed(self, feed_url: str) -> bool:
        """Remove an RSS feed from the database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM rss_feeds WHERE feed_url = ?', (feed_url,))
                conn.commit()
                logger.info(f"Removed RSS feed: {feed_url}")
                return True
        except Exception as e:
            logger.error(f"Error removing RSS feed: {e}")
            return False
    
    def update_feed_validation(self, feed_url: str, status: str, message: str = None, 
                              feed_title: str = None) -> bool:
        """Update RSS feed validation status."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE rss_feeds 
                    SET validation_status = ?, 
                        validation_message = ?,
                        feed_title = COALESCE(?, feed_title),
                        last_validated = CURRENT_TIMESTAMP,
                        date_updated = CURRENT_TIMESTAMP
                    WHERE feed_url = ?
                ''', (status, message, feed_title, feed_url))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error updating feed validation: {e}")
            return False
    
    def get_validated_feeds(self, category: str = None, only_ok: bool = True) -> List[Dict]:
        """Get RSS feeds, optionally filtered by category and validation status."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                query = '''
                    SELECT id, category, feed_url, feed_title, validation_status, 
                           validation_message, last_validated, is_active
                    FROM rss_feeds 
                    WHERE is_active = TRUE
                '''
                params = []
                
                if category:
                    query += ' AND category = ?'
                    params.append(category)
                
                if only_ok:
                    query += " AND validation_status = 'ok'"
                
                query += ' ORDER BY category, feed_url'
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                feeds = []
                for row in rows:
                    feeds.append({
                        'id': row[0],
                        'category': row[1],
                        'feed_url': row[2],
                        'feed_title': row[3],
                        'validation_status': row[4],
                        'validation_message': row[5],
                        'last_validated': row[6],
                        'is_active': bool(row[7])
                    })
                
                return feeds
        except Exception as e:
            logger.error(f"Error getting validated feeds: {e}")
            return []
    
    def get_all_feeds(self) -> List[Dict]:
        """Get all RSS feeds regardless of validation status."""
        return self.get_validated_feeds(only_ok=False)
    
    def get_feeds_by_category(self, category: str) -> List[Dict]:
        """Get all feeds for a specific category."""
        return self.get_validated_feeds(category=category, only_ok=False)
    
    def get_feed_validation_summary(self) -> Dict[str, int]:
        """Get summary of feed validation statuses."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT validation_status, COUNT(*) 
                    FROM rss_feeds 
                    WHERE is_active = 1
                    GROUP BY validation_status
                ''')
                rows = cursor.fetchall()
                
                summary = {'total': 0}
                for status, count in rows:
                    summary[status] = count
                    summary['total'] += count
                
                return summary
        except Exception as e:
            logger.error(f"Error getting validation summary: {e}")
            logger.error(f"Exception details: {type(e).__name__}: {e}")
            return {'error': str(e)}
    
    def deactivate_feed(self, feed_url: str) -> bool:
        """Deactivate a feed instead of deleting it."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE rss_feeds 
                    SET is_active = FALSE, date_updated = CURRENT_TIMESTAMP
                    WHERE feed_url = ?
                ''', (feed_url,))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error deactivating feed: {e}")
            return False
    
    def reactivate_feed(self, feed_url: str) -> bool:
        """Reactivate a deactivated feed."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE rss_feeds 
                    SET is_active = TRUE, date_updated = CURRENT_TIMESTAMP
                    WHERE feed_url = ?
                ''', (feed_url,))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error reactivating feed: {e}")
            return False

    def update_articles_bulk(self, articles: List[Dict]) -> int:
        """Update articles in bulk."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                updates = []
                for article in articles:
                    updates.append((
                        json.dumps(article.get('ai_categories', [])),
                        article.get('ai_summary'),
                        article.get('trending_flag', False),
                        datetime.utcnow().isoformat(),
                        article.get('id')
                    ))
                
                cursor.executemany('''
                    UPDATE articles
                    SET ai_categories = ?,
                        ai_summary = ?,
                        trending_flag = ?,
                        date_updated = ?
                    WHERE id = ?
                ''', updates)
                
                return cursor.rowcount
        except Exception as e:
            logger.error(f"Error in bulk article update: {e}")
            return 0

    def get_all_users(self) -> List[Dict]:
        """Retrieve all users."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT user_id, email, selected_categories, digest_frequency,
                           articles_per_digest, preferred_output_format, feedback_history
                    FROM user_preferences
                ''')
                users = []
                for row in cursor.fetchall():
                    users.append({
                        'user_id': row[0],
                        'email': row[1],
                        'selected_categories': json.loads(row[2]) if row[2] else [],
                        'digest_frequency': row[3],
                        'articles_per_digest': row[4],
                        'preferred_output_format': row[5],
                        'feedback_history': json.loads(row[6]) if row[6] else {}
                    })
                return users
        except Exception as e:
            logger.error(f"Error getting all users: {e}")
            return []
    
    # Email delivery methods
    def record_email_delivery(self, user_id: str, email_address: str, subject_line: str, 
                            digest_content: Dict, email_html: str, delivery_method: str = 'smtp') -> Optional[int]:
        """Record an email delivery attempt."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO email_deliveries 
                    (user_id, email_address, subject_line, digest_content, email_html, 
                     delivery_method, delivery_status)
                    VALUES (?, ?, ?, ?, ?, ?, 'pending')
                ''', (user_id, email_address, subject_line, json.dumps(digest_content), 
                      email_html, delivery_method))
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Error recording email delivery: {e}")
            return None
    
    def update_email_delivery_status(self, delivery_id: int, status: str, 
                                   sent_at: str = None, external_id: str = None, 
                                   error_message: str = None) -> bool:
        """Update email delivery status."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE email_deliveries 
                    SET delivery_status = ?, sent_at = ?, delivery_id = ?, error_message = ?
                    WHERE id = ?
                ''', (status, sent_at or datetime.utcnow().isoformat(), external_id, error_message, delivery_id))
                return True
        except Exception as e:
            logger.error(f"Error updating email delivery status: {e}")
            return False
    
    def get_email_preferences(self, user_id: str) -> Optional[Dict]:
        """Get email preferences for a user."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM email_preferences WHERE user_id = ?', (user_id,))
                row = cursor.fetchone()
                if row:
                    return {
                        'user_id': row[0],
                        'email_enabled': bool(row[1]),
                        'delivery_frequency': row[2],
                        'delivery_time': row[3],
                        'delivery_timezone': row[4],
                        'email_format': row[5],
                        'include_feedback_links': bool(row[6]),
                        'include_social_sharing': bool(row[7]),
                        'personalized_subject': bool(row[8])
                    }
                return None
        except Exception as e:
            logger.error(f"Error getting email preferences: {e}")
            return None
    
    def set_email_preferences(self, user_id: str, preferences: Dict) -> bool:
        """Set email preferences for a user."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO email_preferences 
                    (user_id, email_enabled, delivery_frequency, delivery_time, delivery_timezone,
                     email_format, include_feedback_links, include_social_sharing, personalized_subject,
                     updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', (
                    user_id,
                    preferences.get('email_enabled', True),
                    preferences.get('delivery_frequency', 'daily'),
                    preferences.get('delivery_time', '08:00'),
                    preferences.get('delivery_timezone', 'UTC'),
                    preferences.get('email_format', 'html'),
                    preferences.get('include_feedback_links', True),
                    preferences.get('include_social_sharing', True),
                    preferences.get('personalized_subject', True)
                ))
                return True
        except Exception as e:
            logger.error(f"Error setting email preferences: {e}")
            return False
    
    def record_feedback(self, user_id: str, article_id: int, feedback_type: str,
                       email_delivery_id: int = None, share_platform: str = None,
                       feedback_source: str = 'email') -> bool:
        """Record user feedback on an article."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO feedback_history 
                    (user_id, article_id, email_delivery_id, feedback_type, 
                     feedback_source, share_platform)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (user_id, article_id, email_delivery_id, feedback_type, 
                      feedback_source, share_platform))
                
                # Update engagement metrics
                self._update_engagement_metrics(user_id, feedback_type, share_platform)
                return True
        except Exception as e:
            logger.error(f"Error recording feedback: {e}")
            return False
    
    def _update_engagement_metrics(self, user_id: str, feedback_type: str, share_platform: str = None):
        """Update daily engagement metrics for a user."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                today = datetime.utcnow().strftime('%Y-%m-%d')
                
                # Insert or get existing metrics for today
                cursor.execute('''
                    INSERT OR IGNORE INTO engagement_metrics (user_id, metric_date)
                    VALUES (?, ?)
                ''', (user_id, today))
                
                # Update specific metrics based on feedback type
                if feedback_type == 'like':
                    cursor.execute('''
                        UPDATE engagement_metrics 
                        SET articles_liked = articles_liked + 1, total_clicks = total_clicks + 1
                        WHERE user_id = ? AND metric_date = ?
                    ''', (user_id, today))
                elif feedback_type == 'dislike':
                    cursor.execute('''
                        UPDATE engagement_metrics 
                        SET articles_disliked = articles_disliked + 1, total_clicks = total_clicks + 1
                        WHERE user_id = ? AND metric_date = ?
                    ''', (user_id, today))
                elif feedback_type == 'share':
                    update_query = '''
                        UPDATE engagement_metrics 
                        SET shares_total = shares_total + 1, total_clicks = total_clicks + 1
                    '''
                    params = [user_id, today]
                    
                    if share_platform == 'twitter':
                        update_query += ', shares_twitter = shares_twitter + 1'
                    elif share_platform == 'linkedin':
                        update_query += ', shares_linkedin = shares_linkedin + 1'
                    elif share_platform == 'whatsapp':
                        update_query += ', shares_whatsapp = shares_whatsapp + 1'
                    
                    update_query += ' WHERE user_id = ? AND metric_date = ?'
                    cursor.execute(update_query, params)
                else:  # more_like_this, click, etc.
                    cursor.execute('''
                        UPDATE engagement_metrics 
                        SET total_clicks = total_clicks + 1
                        WHERE user_id = ? AND metric_date = ?
                    ''', (user_id, today))
                    
        except Exception as e:
            logger.error(f"Error updating engagement metrics: {e}")
    
    def get_user_engagement_summary(self, user_id: str, days: int = 30) -> Dict:
        """Get engagement summary for a user over the last N days."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT 
                        SUM(emails_sent) as total_emails,
                        SUM(emails_opened) as total_opens,
                        SUM(total_clicks) as total_clicks,
                        SUM(articles_liked) as total_likes,
                        SUM(articles_disliked) as total_dislikes,
                        SUM(shares_total) as total_shares,
                        AVG(total_clicks * 1.0 / NULLIF(emails_sent, 0)) as avg_click_rate
                    FROM engagement_metrics 
                    WHERE user_id = ? AND metric_date >= date('now', '-{} days')
                '''.format(days), (user_id,))
                
                row = cursor.fetchone()
                if row:
                    return {
                        'total_emails': row[0] or 0,
                        'total_opens': row[1] or 0,
                        'total_clicks': row[2] or 0,
                        'total_likes': row[3] or 0,
                        'total_dislikes': row[4] or 0,
                        'total_shares': row[5] or 0,
                        'avg_click_rate': round(row[6] or 0, 3)
                    }
                return {}
        except Exception as e:
            logger.error(f"Error getting engagement summary: {e}")
            return {}
    
    def get_article_feedback_summary(self, article_id: int) -> Dict:
        """Get feedback summary for a specific article."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT 
                        feedback_type,
                        COUNT(*) as count
                    FROM feedback_history 
                    WHERE article_id = ?
                    GROUP BY feedback_type
                ''', (article_id,))
                
                feedback = {}
                for row in cursor.fetchall():
                    feedback[row[0]] = row[1]
                
                return feedback
        except Exception as e:
            logger.error(f"Error getting article feedback summary: {e}")
            return {}
    
    def update_user_email(self, user_id: str, email: str) -> bool:
        """Update user's email address."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE user_preferences 
                    SET email = ?
                    WHERE user_id = ?
                ''', (email, user_id))
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error updating user email: {e}")
            return False
    
    def remove_user(self, user_id: str) -> bool:
        """Remove a user and all their associated data."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Remove from all user-related tables
                tables_to_clean = [
                    'user_preferences',
                    'email_deliveries', 
                    'email_preferences',
                    'user_feedback',
                    'user_engagement'
                ]
                
                rows_affected = 0
                for table in tables_to_clean:
                    try:
                        cursor.execute(f'DELETE FROM {table} WHERE user_id = ?', (user_id,))
                        rows_affected += cursor.rowcount
                        logger.info(f"Removed {cursor.rowcount} rows from {table} for user {user_id}")
                    except sqlite3.Error as e:
                        # Table might not exist, that's okay
                        logger.debug(f"Could not clean table {table}: {e}")
                
                conn.commit()
                logger.info(f"Successfully removed user {user_id} (total rows affected: {rows_affected})")
                return rows_affected > 0
                
        except Exception as e:
            logger.error(f"Error removing user {user_id}: {e}")
            return False
    
    def get_recent_email_deliveries(self, limit: int = 10) -> List[Dict]:
        """Get recent email deliveries for statistics."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Check if email_deliveries table exists
                cursor.execute('''
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name='email_deliveries'
                ''')
                
                if not cursor.fetchone():
                    # Table doesn't exist, return empty list
                    return []
                
                cursor.execute('''
                    SELECT user_id, email_address, subject_line, delivery_status, 
                           sent_at, error_message
                    FROM email_deliveries 
                    ORDER BY sent_at DESC 
                    LIMIT ?
                ''', (limit,))
                
                rows = cursor.fetchall()
                
                deliveries = []
                for row in rows:
                    deliveries.append({
                        'user_id': row[0],
                        'email_address': row[1],
                        'subject_line': row[2],
                        'delivery_status': row[3],
                        'delivery_timestamp': row[4],
                        'error_message': row[5]
                    })
                
                return deliveries
                
        except Exception as e:
            logger.error(f"Error getting recent email deliveries: {e}")
            return []
    
    def save_daily_oneliners(self, oneliners: List[Dict]) -> int:
        """Save daily one-liners to database. Returns count of saved items."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                saved_count = 0
                
                for oneliner_data in oneliners:
                    try:
                        cursor.execute('''
                            INSERT OR IGNORE INTO daily_oneliners 
                            (category, oneliner, generation_date, generation_model)
                            VALUES (?, ?, ?, ?)
                        ''', (
                            oneliner_data['category'],
                            oneliner_data['oneliner'],
                            oneliner_data['generation_date'],
                            oneliner_data.get('generation_model', 'unknown')
                        ))
                        if cursor.rowcount > 0:
                            saved_count += 1
                    except Exception as e:
                        logger.warning(f"Error saving oneliner: {e}")
                        continue
                
                conn.commit()
                logger.info(f"Saved {saved_count} out of {len(oneliners)} one-liners")
                return saved_count
                
        except Exception as e:
            logger.error(f"Error saving daily one-liners: {e}")
            return 0
    
    def get_random_oneliner(self, category: str = None, generation_date: str = None) -> Optional[Dict]:
        """Get a random one-liner, optionally filtered by category and date."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Build query with optional filters
                query = '''
                    SELECT id, category, oneliner, generation_date, generation_model, usage_count
                    FROM daily_oneliners
                    WHERE 1=1
                '''
                params = []
                
                if category:
                    query += ' AND category = ?'
                    params.append(category)
                
                if generation_date:
                    query += ' AND generation_date = ?'
                    params.append(generation_date)
                
                query += ' ORDER BY RANDOM() LIMIT 1'
                
                cursor.execute(query, params)
                row = cursor.fetchone()
                
                if row:
                    # Update usage count
                    cursor.execute('''
                        UPDATE daily_oneliners 
                        SET usage_count = usage_count + 1
                        WHERE id = ?
                    ''', (row[0],))
                    conn.commit()
                    
                    return {
                        'id': row[0],
                        'category': row[1],
                        'oneliner': row[2],
                        'generation_date': row[3],
                        'generation_model': row[4],
                        'usage_count': row[5] + 1
                    }
                
                return None
                
        except Exception as e:
            logger.error(f"Error getting random oneliner: {e}")
            return None
    
    def get_oneliners_by_date(self, generation_date: str) -> List[Dict]:
        """Get all one-liners for a specific date."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, category, oneliner, generation_date, generation_model, usage_count
                    FROM daily_oneliners
                    WHERE generation_date = ?
                    ORDER BY category, usage_count ASC
                ''', (generation_date,))
                
                results = []
                for row in cursor.fetchall():
                    results.append({
                        'id': row[0],
                        'category': row[1],
                        'oneliner': row[2],
                        'generation_date': row[3],
                        'generation_model': row[4],
                        'usage_count': row[5]
                    })
                return results
                
        except Exception as e:
            logger.error(f"Error getting one-liners by date: {e}")
            return []
    
    def cleanup_old_oneliners(self, days_old: int = 7) -> int:
        """Remove one-liners older than specified days. Returns count of deleted items."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    DELETE FROM daily_oneliners
                    WHERE generation_date < date('now', '-{} days')
                '''.format(days_old))
                deleted_count = cursor.rowcount
                conn.commit()
                logger.info(f"Cleaned up {deleted_count} old one-liners (older than {days_old} days)")
                return deleted_count
        except Exception as e:
            logger.error(f"Error cleaning up old one-liners: {e}")
            return 0
    
    def get_oneliner_stats(self) -> Dict:
        """Get statistics about one-liners in the database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Total count
                cursor.execute('SELECT COUNT(*) FROM daily_oneliners')
                total_count = cursor.fetchone()[0]
                
                # Count by category
                cursor.execute('''
                    SELECT category, COUNT(*) 
                    FROM daily_oneliners 
                    GROUP BY category
                    ORDER BY COUNT(*) DESC
                ''')
                by_category = dict(cursor.fetchall())
                
                # Usage statistics
                cursor.execute('''
                    SELECT 
                        AVG(usage_count) as avg_usage,
                        MAX(usage_count) as max_usage,
                        MIN(usage_count) as min_usage
                    FROM daily_oneliners
                ''')
                usage_stats = cursor.fetchone()
                
                # Date range
                cursor.execute('''
                    SELECT 
                        MIN(generation_date) as earliest_date,
                        MAX(generation_date) as latest_date
                    FROM daily_oneliners
                ''')
                date_range = cursor.fetchone()
                
                return {
                    'total_count': total_count,
                    'by_category': by_category,
                    'avg_usage': round(usage_stats[0], 2) if usage_stats[0] else 0,
                    'max_usage': usage_stats[1] or 0,
                    'min_usage': usage_stats[2] or 0,
                    'earliest_date': date_range[0],
                    'latest_date': date_range[1]
                }
                
        except Exception as e:
            logger.error(f"Error getting oneliner stats: {e}")
            return {}
    
    # Stock Image Management Methods
    
    def add_stock_image(self, image_path: str, image_name: str, category: str = None, 
                       image_type: str = 'general', file_size: int = None,
                       width: int = None, height: int = None) -> bool:
        """Add a stock image to the database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO stock_images 
                    (image_path, image_name, category, image_type, file_size, width, height)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (image_path, image_name, category, image_type, file_size, width, height))
                conn.commit()
                logger.info(f"Added stock image: {image_path}")
                return True
        except Exception as e:
            logger.error(f"Error adding stock image: {e}")
            return False
    
    def get_random_stock_image(self, category: str = None, image_type: str = None) -> Optional[Dict]:
        """Get a random stock image, optionally filtered by category or type."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                query = '''
                    SELECT id, image_path, image_name, category, image_type, 
                           file_size, width, height, usage_count
                    FROM stock_images 
                    WHERE is_active = TRUE
                '''
                params = []
                
                if category:
                    query += ' AND (category = ? OR category IS NULL)'
                    params.append(category)
                
                if image_type:
                    query += ' AND image_type = ?'
                    params.append(image_type)
                
                query += ' ORDER BY RANDOM() LIMIT 1'
                
                cursor.execute(query, params)
                row = cursor.fetchone()
                
                if row:
                    # Update usage count
                    cursor.execute('''
                        UPDATE stock_images 
                        SET usage_count = usage_count + 1, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    ''', (row[0],))
                    conn.commit()
                    
                    return {
                        'id': row[0],
                        'image_path': row[1],
                        'image_name': row[2],
                        'category': row[3],
                        'image_type': row[4],
                        'file_size': row[5],
                        'width': row[6],
                        'height': row[7],
                        'usage_count': row[8] + 1
                    }
                
                return None
        except Exception as e:
            logger.error(f"Error getting random stock image: {e}")
            return None
    
    def get_all_stock_images(self, active_only: bool = True) -> List[Dict]:
        """Get all stock images."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                query = '''
                    SELECT id, image_path, image_name, category, image_type, 
                           file_size, width, height, usage_count, is_active
                    FROM stock_images
                '''
                
                if active_only:
                    query += ' WHERE is_active = TRUE'
                
                query += ' ORDER BY usage_count ASC, image_name'
                
                cursor.execute(query)
                rows = cursor.fetchall()
                
                images = []
                for row in rows:
                    images.append({
                        'id': row[0],
                        'image_path': row[1],
                        'image_name': row[2],
                        'category': row[3],
                        'image_type': row[4],
                        'file_size': row[5],
                        'width': row[6],
                        'height': row[7],
                        'usage_count': row[8],
                        'is_active': bool(row[9])
                    })
                
                return images
        except Exception as e:
            logger.error(f"Error getting all stock images: {e}")
            return []
    
    def remove_stock_image(self, image_id: int) -> bool:
        """Remove a stock image by ID."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM stock_images WHERE id = ?', (image_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error removing stock image: {e}")
            return False
    
    def deactivate_stock_image(self, image_id: int) -> bool:
        """Deactivate a stock image instead of deleting it."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE stock_images 
                    SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (image_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error deactivating stock image: {e}")
            return False
    
    def get_stock_image_stats(self) -> Dict:
        """Get statistics about stock images."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Total counts
                cursor.execute('SELECT COUNT(*) FROM stock_images WHERE is_active = TRUE')
                active_count = cursor.fetchone()[0]
                
                cursor.execute('SELECT COUNT(*) FROM stock_images')
                total_count = cursor.fetchone()[0]
                
                # Usage statistics
                cursor.execute('''
                    SELECT 
                        AVG(usage_count) as avg_usage,
                        MAX(usage_count) as max_usage,
                        MIN(usage_count) as min_usage
                    FROM stock_images
                    WHERE is_active = TRUE
                ''')
                usage_stats = cursor.fetchone()
                
                # By category
                cursor.execute('''
                    SELECT 
                        COALESCE(category, 'General') as cat,
                        COUNT(*) as count
                    FROM stock_images 
                    WHERE is_active = TRUE
                    GROUP BY category
                    ORDER BY count DESC
                ''')
                by_category = dict(cursor.fetchall())
                
                return {
                    'active_count': active_count,
                    'total_count': total_count,
                    'inactive_count': total_count - active_count,
                    'avg_usage': round(usage_stats[0], 2) if usage_stats[0] else 0,
                    'max_usage': usage_stats[1] or 0,
                    'min_usage': usage_stats[2] or 0,
                    'by_category': by_category
                }
                
        except Exception as e:
            logger.error(f"Error getting stock image stats: {e}")
            return {}