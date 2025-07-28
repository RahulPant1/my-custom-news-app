"""Custom exception hierarchy for the news digest application."""

from typing import Optional, Dict, Any


class NewsDigestError(Exception):
    """Base exception class for all news digest related errors."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}
    
    def __str__(self) -> str:
        if self.details:
            return f"{self.message} - Details: {self.details}"
        return self.message


class ConfigurationError(NewsDigestError):
    """Raised when there are configuration-related issues."""
    pass


class DatabaseError(NewsDigestError):
    """Base class for database-related errors."""
    pass


class DatabaseConnectionError(DatabaseError):
    """Raised when database connection fails."""
    pass


class DatabaseTimeoutError(DatabaseError):
    """Raised when database operations timeout."""
    pass


class DataValidationError(DatabaseError):
    """Raised when data validation fails during database operations."""
    pass


class UserNotFoundError(DatabaseError):
    """Raised when a requested user is not found."""
    
    def __init__(self, user_id: str):
        super().__init__(f"User '{user_id}' not found")
        self.user_id = user_id


class ArticleError(NewsDigestError):
    """Base class for article-related errors."""
    pass


class ArticleNotFoundError(ArticleError):
    """Raised when a requested article is not found."""
    
    def __init__(self, article_id: int):
        super().__init__(f"Article with ID {article_id} not found")
        self.article_id = article_id


class DuplicateArticleError(ArticleError):
    """Raised when attempting to insert a duplicate article."""
    pass


class RSSError(NewsDigestError):
    """Base class for RSS feed-related errors."""
    pass


class RSSFeedError(RSSError):
    """Raised when RSS feed processing fails."""
    
    def __init__(self, feed_url: str, message: str):
        super().__init__(f"RSS feed error for {feed_url}: {message}")
        self.feed_url = feed_url


class RSSValidationError(RSSError):
    """Raised when RSS feed validation fails."""
    pass


class RSSTimeoutError(RSSError):
    """Raised when RSS feed request times out."""
    pass


class AIServiceError(NewsDigestError):
    """Base class for AI service-related errors."""
    pass


class AIProviderError(AIServiceError):
    """Raised when AI provider is not available or configured."""
    
    def __init__(self, provider: str, message: str = None):
        msg = message or f"AI provider '{provider}' is not available or configured"
        super().__init__(msg)
        self.provider = provider


class AIQuotaExceededError(AIServiceError):
    """Raised when AI service quota is exceeded."""
    pass


class AITimeoutError(AIServiceError):
    """Raised when AI service request times out."""
    pass


class AIResponseError(AIServiceError):
    """Raised when AI service returns invalid response."""
    pass


class EmailError(NewsDigestError):
    """Base class for email-related errors."""
    pass


class EmailConfigurationError(EmailError):
    """Raised when email configuration is invalid."""
    pass


class EmailDeliveryError(EmailError):
    """Raised when email delivery fails."""
    
    def __init__(self, recipient: str, message: str):
        super().__init__(f"Email delivery failed to {recipient}: {message}")
        self.recipient = recipient


class EmailTemplateError(EmailError):
    """Raised when email template processing fails."""
    pass


class EmailAuthenticationError(EmailError):
    """Raised when email authentication fails."""
    pass


class ValidationError(NewsDigestError):
    """Raised when input validation fails."""
    
    def __init__(self, field: str, value: Any, message: str):
        super().__init__(f"Validation error for {field}: {message}")
        self.field = field
        self.value = value


class CategoryError(NewsDigestError):
    """Raised when category-related operations fail."""
    
    def __init__(self, category: str, message: str):
        super().__init__(f"Category error for '{category}': {message}")
        self.category = category


class DigestGenerationError(NewsDigestError):
    """Raised when digest generation fails."""
    pass


class UserPreferencesError(NewsDigestError):
    """Raised when user preferences operations fail."""
    pass


class RateLimitError(NewsDigestError):
    """Raised when rate limits are exceeded."""
    
    def __init__(self, service: str, retry_after: Optional[int] = None):
        message = f"Rate limit exceeded for {service}"
        if retry_after:
            message += f". Retry after {retry_after} seconds"
        super().__init__(message)
        self.service = service
        self.retry_after = retry_after


class SecurityError(NewsDigestError):
    """Raised when security violations occur."""
    pass


class AuthenticationError(SecurityError):
    """Raised when authentication fails."""
    pass


class AuthorizationError(SecurityError):
    """Raised when authorization fails."""
    pass


# Utility functions for exception handling

def handle_database_errors(func):
    """Decorator to handle common database errors."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ConnectionError as e:
            raise DatabaseConnectionError(f"Database connection failed: {e}")
        except TimeoutError as e:
            raise DatabaseTimeoutError(f"Database operation timed out: {e}")
        except ValueError as e:
            raise DataValidationError(f"Data validation failed: {e}")
        except Exception as e:
            raise DatabaseError(f"Unexpected database error: {e}")
    return wrapper


def handle_ai_errors(func):
    """Decorator to handle common AI service errors."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ConnectionError as e:
            raise AIServiceError(f"AI service connection failed: {e}")
        except TimeoutError as e:
            raise AITimeoutError(f"AI service request timed out: {e}")
        except Exception as e:
            if "quota" in str(e).lower() or "rate limit" in str(e).lower():
                raise AIQuotaExceededError(f"AI service quota exceeded: {e}")
            elif "authentication" in str(e).lower():
                raise AIProviderError("unknown", f"AI authentication failed: {e}")
            else:
                raise AIServiceError(f"Unexpected AI service error: {e}")
    return wrapper


def handle_email_errors(func):
    """Decorator to handle common email errors."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ConnectionError as e:
            raise EmailDeliveryError("unknown", f"Email server connection failed: {e}")
        except TimeoutError as e:
            raise EmailDeliveryError("unknown", f"Email delivery timed out: {e}")
        except Exception as e:
            if "authentication" in str(e).lower():
                raise EmailAuthenticationError(f"Email authentication failed: {e}")
            else:
                raise EmailError(f"Unexpected email error: {e}")
    return wrapper