"""Email template system."""

from .email_templates import (
    EmailTemplate,
    NewsDigestTemplate,
    EmailTemplateManager,
    render_email_template,
    MobileCardTemplate
)

__all__ = [
    'EmailTemplate',
    'NewsDigestTemplate', 
    'EmailTemplateManager',
    'render_email_template',
    'MobileCardTemplate'
]