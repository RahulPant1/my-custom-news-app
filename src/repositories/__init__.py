"""Repository layer for database access."""

from .email_repository import (
    EmailRepository,
    EmailDelivery,
    EmailPreferences,
    FeedbackRecord
)

__all__ = [
    'EmailRepository',
    'EmailDelivery',
    'EmailPreferences', 
    'FeedbackRecord'
]