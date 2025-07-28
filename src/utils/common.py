"""Common utility functions for the news digest application."""

import hashlib
import json
import re
import time
import random
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, Callable
from urllib.parse import urlparse, urljoin
from functools import wraps
import logging

logger = logging.getLogger(__name__)


def generate_content_hash(title: str, content: str = "") -> str:
    """Generate a hash for duplicate detection."""
    content_string = f"{title.lower().strip()}{content.lower().strip()}"
    return hashlib.md5(content_string.encode()).hexdigest()


def generate_title_hash(title: str) -> str:
    """Generate a normalized hash for title-based duplicate detection."""
    # Remove common words and normalize
    normalized = re.sub(r'\b(the|a|an|and|or|but|in|on|at|to|for|of|with|by)\b', '', title.lower())
    normalized = re.sub(r'[^\w\s]', '', normalized)  # Remove punctuation
    normalized = re.sub(r'\s+', ' ', normalized).strip()  # Normalize whitespace
    return hashlib.md5(normalized.encode()).hexdigest()


def clean_text(text: str, max_length: Optional[int] = None) -> str:
    """Clean and normalize text content."""
    if not text:
        return ""
    
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Remove quotes from beginning and end
    text = re.sub(r'^["\']|["\']$', '', text.strip())
    
    if max_length and len(text) > max_length:
        text = text[:max_length-3] + "..."
    
    return text.strip()


def validate_email(email: str) -> bool:
    """Validate email format."""
    if not email:
        return False
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_url(url: str) -> bool:
    """Validate URL format."""
    if not url:
        return False
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False


def extract_domain(url: str) -> str:
    """Extract domain from URL."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        return domain.replace('www.', '')
    except Exception:
        return 'unknown'


def safe_json_loads(json_str: str, default: Any = None) -> Any:
    """Safely load JSON with fallback."""
    if not json_str:
        return default
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return default


def safe_json_dumps(obj: Any, default: str = "{}") -> str:
    """Safely dump JSON with fallback."""
    try:
        return json.dumps(obj)
    except (TypeError, ValueError):
        return default


def format_date(date_str: str, format_str: str = "%Y-%m-%d") -> str:
    """Format date string safely."""
    if not date_str:
        return ""
    try:
        if 'T' in date_str:
            date_str = date_str.replace('Z', '+00:00')
        date_obj = datetime.fromisoformat(date_str)
        return date_obj.strftime(format_str)
    except (ValueError, TypeError):
        return date_str[:10] if len(date_str) >= 10 else date_str


def get_relative_time(date_str: str) -> str:
    """Get relative time string (e.g., '2 hours ago')."""
    if not date_str:
        return "Unknown"
    
    try:
        if 'T' in date_str:
            date_str = date_str.replace('Z', '+00:00')
        date_obj = datetime.fromisoformat(date_str)
        now = datetime.now(date_obj.tzinfo) if date_obj.tzinfo else datetime.now()
        diff = now - date_obj
        
        if diff.days > 7:
            return date_obj.strftime("%b %d, %Y")
        elif diff.days > 0:
            return f"{diff.days} day{'s' if diff.days != 1 else ''} ago"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        else:
            return "Just now"
    except Exception:
        return format_date(date_str)


def chunked(lst: List[Any], chunk_size: int) -> List[List[Any]]:
    """Split a list into chunks of specified size."""
    for i in range(0, len(lst), chunk_size):
        yield lst[i:i + chunk_size]


def deduplicate_by_key(items: List[Dict], key: str) -> List[Dict]:
    """Remove duplicates from list of dictionaries based on a key."""
    seen = set()
    result = []
    for item in items:
        value = item.get(key)
        if value and value not in seen:
            seen.add(value)
            result.append(item)
    return result


def rate_limit_delay(min_delay: float = 0.5, max_delay: float = 2.0) -> None:
    """Add random delay for rate limiting."""
    delay = random.uniform(min_delay, max_delay)
    time.sleep(delay)


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exceptions: tuple = (Exception,)
) -> Callable:
    """Decorator to retry function with exponential backoff."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_retries:
                        break
                    
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay:.2f}s")
                    time.sleep(delay)
            
            raise last_exception
        return wrapper
    return decorator


def timeout_handler(timeout_seconds: int):
    """Decorator to add timeout to function execution."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            import signal
            
            def timeout_signal_handler(signum, frame):
                raise TimeoutError(f"Function {func.__name__} timed out after {timeout_seconds} seconds")
            
            # Set up signal handler
            old_handler = signal.signal(signal.SIGALRM, timeout_signal_handler)
            signal.alarm(timeout_seconds)
            
            try:
                result = func(*args, **kwargs)
                signal.alarm(0)  # Cancel alarm
                return result
            finally:
                signal.signal(signal.SIGALRM, old_handler)
        
        return wrapper
    return decorator


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """Truncate text to maximum length with suffix."""
    if not text or len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def extract_keywords(text: str, min_length: int = 3) -> List[str]:
    """Extract keywords from text."""
    if not text:
        return []
    
    # Remove HTML tags and normalize
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'[^\w\s]', ' ', text)
    
    # Split into words and filter
    words = text.lower().split()
    keywords = []
    
    stop_words = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have',
        'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
        'this', 'that', 'these', 'those', 'can', 'may', 'might', 'must'
    }
    
    for word in words:
        if len(word) >= min_length and word not in stop_words:
            keywords.append(word)
    
    return list(set(keywords))  # Remove duplicates


def calculate_similarity(text1: str, text2: str) -> float:
    """Calculate simple text similarity score (0-1)."""
    if not text1 or not text2:
        return 0.0
    
    keywords1 = set(extract_keywords(text1))
    keywords2 = set(extract_keywords(text2))
    
    if not keywords1 or not keywords2:
        return 0.0
    
    intersection = keywords1.intersection(keywords2)
    union = keywords1.union(keywords2)
    
    return len(intersection) / len(union) if union else 0.0


def format_file_size(size_bytes: int) -> str:
    """Format file size in human readable format."""
    if size_bytes == 0:
        return "0B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    import math
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    
    return f"{s} {size_names[i]}"


class CircuitBreaker:
    """Simple circuit breaker implementation."""
    
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
    
    def call(self, func: Callable, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        if self.state == 'OPEN':
            if time.time() - self.last_failure_time > self.timeout:
                self.state = 'HALF_OPEN'
            else:
                raise Exception("Circuit breaker is OPEN")
        
        try:
            result = func(*args, **kwargs)
            if self.state == 'HALF_OPEN':
                self.state = 'CLOSED'
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.failure_count >= self.failure_threshold:
                self.state = 'OPEN'
            
            raise e


def validate_categories(categories: List[str], valid_categories: List[str]) -> Dict[str, Any]:
    """Validate category list against valid categories."""
    if not categories:
        return {
            'valid': False,
            'errors': ['At least one category must be provided'],
            'invalid_categories': [],
            'valid_categories': []
        }
    
    invalid = [cat for cat in categories if cat not in valid_categories]
    valid = [cat for cat in categories if cat in valid_categories]
    
    return {
        'valid': len(invalid) == 0,
        'errors': [f"Invalid categories: {', '.join(invalid)}"] if invalid else [],
        'invalid_categories': invalid,
        'valid_categories': valid
    }


def generate_tracking_url(base_url: str, user_id: str, article_id: int, 
                         feedback_type: str, delivery_id: int = None, 
                         share_platform: str = None) -> str:
    """Generate tracking URL for feedback/engagement with consistent parameters."""
    import urllib.parse
    
    params = {
        'user_id': user_id,
        'article_id': article_id,
        'feedback': feedback_type,
        'source': 'email'
    }
    
    if delivery_id:
        params['delivery_id'] = delivery_id
    if share_platform:
        params['platform'] = share_platform
        
    query_string = urllib.parse.urlencode(params)
    return f"{base_url}/track/feedback?{query_string}"


def generate_share_url(article_url: str, article_title: str, platform: str,
                      user_id: str = None, article_id: int = None, 
                      email_delivery_id: int = None) -> str:
    """Generate social sharing URL with optional tracking."""
    import urllib.parse
    
    encoded_url = urllib.parse.quote(article_url)
    encoded_title = urllib.parse.quote(article_title)
    
    share_urls = {
        'twitter': f"https://twitter.com/intent/tweet?url={encoded_url}&text={encoded_title}",
        'linkedin': f"https://www.linkedin.com/sharing/share-offsite/?url={encoded_url}",
        'whatsapp': f"https://wa.me/?text={encoded_title}%20{encoded_url}",
        'email': f"mailto:?subject={encoded_title}&body={encoded_url}"
    }
    
    return share_urls.get(platform, article_url)


def get_category_emoji(category: str) -> str:
    """Get emoji for news category - centralized mapping."""
    emojis = {
        "Science & Discovery": "🔬",
        "Technology & Gadgets": "💻", 
        "Health & Wellness": "🏥",
        "Business & Finance": "💼",
        "Global Affairs": "🌍",
        "Environment & Climate": "🌱",
        "Good Vibes (Positive News)": "😊",
        "Pop Culture & Lifestyle": "🎭",
        "For Young Minds (Youth-Focused)": "🎓",
        "For Young Minds": "🎓",
        "DIY, Skills & How-To": "🔧"
    }
    return emojis.get(category, "📰")


def normalize_category_name(category: str) -> str:
    """Normalize category names for consistency."""
    if not category:
        return ""
    
    # Basic normalization
    normalized = category.strip()
    
    # Handle common variations
    category_mappings = {
        "tech": "Technology & Gadgets",
        "technology": "Technology & Gadgets",
        "science": "Science & Discovery",
        "health": "Health & Wellness",
        "business": "Business & Finance",
        "finance": "Business & Finance",
        "world": "Global Affairs",
        "international": "Global Affairs",
        "environment": "Environment & Climate",
        "climate": "Environment & Climate",
        "lifestyle": "Pop Culture & Lifestyle",
        "culture": "Pop Culture & Lifestyle",
        "youth": "For Young Minds (Youth-Focused)",
        "diy": "DIY, Skills & How-To",
        "positive": "Good Vibes (Positive News)"
    }
    
    return category_mappings.get(normalized.lower(), normalized)


def ensure_list(value: Any) -> List:
    """Ensure value is a list, converting if necessary."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, (tuple, set)):
        return list(value)
    if isinstance(value, str):
        # Try to parse as JSON array first
        try:
            parsed = safe_json_loads(value)
            if isinstance(parsed, list):
                return parsed
        except:
            pass
        # Otherwise, treat as single item
        return [value]
    return [value]


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe file system usage."""
    if not filename:
        return "unnamed"
    
    # Remove or replace problematic characters
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
    sanitized = re.sub(r'\s+', '_', sanitized)
    sanitized = sanitized.strip('._')
    
    # Ensure reasonable length
    if len(sanitized) > 100:
        sanitized = sanitized[:100]
    
    return sanitized or "unnamed"


def merge_dicts(dict1: Dict, dict2: Dict, prefer_second: bool = True) -> Dict:
    """Merge two dictionaries with conflict resolution."""
    result = dict1.copy()
    
    for key, value in dict2.items():
        if key in result:
            if prefer_second:
                result[key] = value
            # If prefer_second is False, keep existing value
        else:
            result[key] = value
    
    return result