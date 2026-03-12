"""Email template system."""

from .email_templates import (
    EmailTemplate,
    NewspaperTemplate,
    EmailTemplateManager,
    render_email_template,
    MobileCardTemplate
)

__all__ = [
    'EmailTemplate',
    'NewspaperTemplate', 
    'EmailTemplateManager',
    'render_email_template',
    'MobileCardTemplate'
]