"""Professional email template system with separation of concerns."""

from typing import Dict, List, Any, Optional
from datetime import datetime
from abc import ABC, abstractmethod
import logging
import random
# Consolidated email template system - no external dependencies needed

logger = logging.getLogger(__name__)


class EmailTemplate(ABC):
    """Abstract base class for email templates."""
    
    @abstractmethod
    def render(self, data: Dict[str, Any]) -> str:
        """Render template with provided data."""
        pass
    
    @abstractmethod
    def get_required_fields(self) -> List[str]:
        """Get list of required template fields."""
        pass
    
    def _get_category_colors(self) -> Dict[str, str]:
        """Get vibrant color scheme for categories."""
        return {
            "Science & Discovery": "#667eea",  # Purple-blue
            "Technology & Gadgets": "#f093fb",  # Pink-purple
            "Health & Wellness": "#4facfe",  # Light blue
            "Business & Finance": "#43e97b",  # Green
            "Global Affairs": "#fa709a",  # Pink-red
            "Environment & Climate": "#c471f5",  # Purple
            "Good Vibes (Positive News)": "#f6d365",  # Yellow-orange
            "Pop Culture & Lifestyle": "#fda085",  # Orange-pink
            "For Young Minds (Youth-Focused)": "#a8edea",  # Mint
            "DIY, Skills & How-To": "#ffd89b"  # Light orange
        }
    
    def _get_category_color(self, category: str) -> str:
        """Get vibrant color for specific category."""
        colors = self._get_category_colors()
        return colors.get(category, "#667eea")  # Default purple-blue
    
    def _get_category_emoji(self, category: str) -> str:
        """Get emoji for category."""
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
            "DIY, Skills & How-To": "🔧"
        }
        return emojis.get(category, "📰")
    
    def _render_article_image(self, article: Dict, base_url: str, alt_text: str = "") -> str:
        """Render article image using original RSS URL."""
        image_url = article.get('image_url')
        
        if not alt_text:
            alt_text = article.get('title', 'Article image')
        
        if image_url and image_url.startswith(('http://', 'https://')):
            return f'<div class="article-image"><img src="{image_url}" alt="{alt_text}" loading="lazy" /></div>'
        else:
            return ""
    
    def _has_article_image(self, article: Dict) -> bool:
        """Check if article has a valid image."""
        image_url = article.get('image_url')
        
        return bool(image_url and image_url.startswith(('http://', 'https://')))


class NewsDigestTemplate(EmailTemplate):
    """Professional news digest email template (Classic)."""
    
    def __init__(self):
        self.required_fields = [
            'user_id', 'categories', 'user_prefs', 'email_prefs', 
            'highlights', 'base_url', 'unsubscribe_url'
        ]
    
    def get_required_fields(self) -> List[str]:
        """Get required template fields."""
        return self.required_fields
    
    def render(self, data: Dict[str, Any]) -> str:
        """Render the news digest email template."""
        self._validate_data(data)
        
        return f"""<!DOCTYPE html>
<html lang="en">
{self._render_head()}
<body>
    <div class="container">
        {self._render_header(data)}
        {self._render_highlights(data.get('highlights', {}))}
        {self._render_categories(data)}
        {self._render_footer(data)}
    </div>
</body>
</html>"""
    
    def _validate_data(self, data: Dict[str, Any]) -> None:
        """Validate required template data."""
        missing_fields = [field for field in self.required_fields 
                         if field not in data or data[field] is None]
        if missing_fields:
            raise ValueError(f"Missing required template fields: {missing_fields}")
    
    def _render_head(self) -> str:
        """Render HTML head section."""
        return """<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Your News Digest</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 0;
            background-color: #f8f9fa;
        }
        .container {
            max-width: 600px;
            margin: 0 auto;
            background-color: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px 15px;
            text-align: center;
        }
        .header h1 {
            margin: 0;
            font-size: 20px;
            font-weight: 600;
        }
        .header p {
            margin: 8px 0 0 0;
            opacity: 0.9;
            font-size: 13px;
        }
        .highlights {
            background: #f8f9fa;
            padding: 15px;
            border-left: 3px solid #667eea;
            margin: 15px;
            border-radius: 6px;
        }
        .highlights h3 {
            margin: 0 0 10px 0;
            color: #333;
            font-size: 14px;
            font-weight: 600;
        }
        .highlight-item {
            margin: 8px 0;
            padding: 8px 10px;
            background: white;
            border-radius: 4px;
            font-size: 12px;
        }
        .category {
            margin: 30px 20px;
        }
        .category-header {
            display: flex;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #e9ecef;
        }
        .category-icon {
            font-size: 24px;
            margin-right: 10px;
        }
        .category-title {
            font-size: 22px;
            font-weight: 600;
            color: #333;
            margin: 0;
        }
        .article {
            background: white;
            border: 1px solid #e9ecef;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 25px;
            transition: box-shadow 0.2s;
            position: relative;
        }
        .article:hover {
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }
        .article::after {
            content: '';
            position: absolute;
            bottom: -12px;
            left: 20px;
            right: 20px;
            height: 1px;
            background: linear-gradient(to right, transparent, #e9ecef, transparent);
        }
        .article:last-child::after {
            display: none;
        }
        .article-title {
            font-size: 18px;
            font-weight: 600;
            margin: 0 0 10px 0;
            line-height: 1.4;
        }
        .article-title a {
            text-decoration: none;
            transition: all 0.3s ease;
        }
        .article-title a:hover {
            opacity: 0.8;
        }
        .article.with-image {
            display: flex;
            flex-direction: column;
        }
        .article-image {
            width: 100%;
            max-height: 200px;
            overflow: hidden;
            border-radius: 6px;
            margin-bottom: 15px;
        }
        .article-image img {
            width: 100%;
            height: auto;
            max-height: 200px;
            object-fit: cover;
            object-position: center;
            border-radius: 6px;
        }
        .article-meta {
            color: #6c757d;
            font-size: 13px;
            margin-bottom: 15px;
        }
        .article-summary {
            color: #495057;
            margin-bottom: 20px;
            line-height: 1.6;
        }
        .article-actions {
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 15px;
        }
        .feedback-buttons {
            display: flex;
            gap: 6px;
            flex-wrap: wrap;
            align-items: center;
        }
        .btn {
            padding: 4px 8px;
            border-radius: 12px;
            text-decoration: none;
            font-size: 10px;
            font-weight: 500;
            transition: all 0.2s;
            border: none;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            min-width: 48px;
            white-space: nowrap;
            line-height: 1.2;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        .btn:hover {
            transform: translateY(-1px);
            box-shadow: 0 2px 6px rgba(0,0,0,0.15);
        }
        .btn span {
            font-size: 10px;
            margin-right: 2px;
        }
        .btn-like {
            background: linear-gradient(135deg, #4ade80 0%, #22c55e 100%);
            color: white;
        }
        .btn-like:hover {
            background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);
        }
        .btn-dislike {
            background: linear-gradient(135deg, #f87171 0%, #ef4444 100%);
            color: white;
        }
        .btn-dislike:hover {
            background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
        }
        .btn-more {
            background: linear-gradient(135deg, #60a5fa 0%, #3b82f6 100%);
            color: white;
        }
        .btn-more:hover {
            background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
        }
        .share-buttons {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            align-items: center;
        }
        .share-btn {
            padding: 4px 8px;
            border-radius: 16px;
            text-decoration: none;
            font-size: 14px;
            border: 1px solid #ddd;
            background: #f8f9fa;
            color: #495057;
            transition: all 0.2s;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            min-width: 32px;
            height: 32px;
        }
        .share-btn:hover {
            background: #e9ecef;
            transform: translateY(-1px);
        }
        .share-twitter { 
            background: #1da1f2; 
            color: white;
        }
        .share-linkedin { 
            background: #0077b5; 
            color: white;
        }
        .share-whatsapp { 
            background: #25d366; 
            color: white;
        }
        .share-email { 
            background: #6c757d; 
            color: white;
        }
        .footer {
            background: #343a40;
            color: white;
            padding: 30px 20px;
            text-align: center;
        }
        .footer a {
            color: #adb5bd;
            text-decoration: none;
        }
        .footer a:hover {
            color: white;
        }
        @media (max-width: 600px) {
            .container {
                margin: 0;
                border-radius: 0;
            }
            .article-actions {
                flex-direction: column;
                align-items: stretch;
            }
            .feedback-buttons {
                justify-content: center;
                gap: 4px;
            }
            .btn {
                padding: 3px 6px;
                font-size: 9px;
                min-width: 42px;
            }
            .btn span {
                font-size: 9px;
                margin-right: 1px;
            }
            .share-buttons {
                justify-content: center;
                gap: 6px;
            }
            .share-btn {
                min-width: 28px;
                height: 28px;
                font-size: 12px;
            }
        }
    </style>
</head>"""
    
    def _render_header(self, data: Dict[str, Any]) -> str:
        """Render email header."""
        user_prefs = data.get('user_prefs', {})
        user_id = user_prefs.get('user_id', data.get('user_id', 'Subscriber'))
        
        return f"""<div class="header">
    <h1>📰 Your News Digest</h1>
    <p>Personalized for {user_id} • {datetime.now().strftime('%B %d, %Y')}</p>
</div>"""
    
    def _render_highlights(self, highlights: Dict[str, Any]) -> str:
        """Render highlights section."""
        if not any(highlights.values()):
            return ""
        
        html = """<div class="highlights">
    <h3>🎯 Today's Highlights</h3>"""
        
        if highlights.get('one_liner'):
            html += f"""
    <div class="highlight-item">
        <strong>💡 Key Insight:</strong> {highlights['one_liner']}
    </div>"""
        
        if highlights.get('top_stat'):
            html += f"""
    <div class="highlight-item">
        <strong>📊 Notable Stat:</strong> {highlights['top_stat']}
    </div>"""
        
        if highlights.get('top_quote'):
            html += f"""
    <div class="highlight-item">
        <strong>💬 Quote of Note:</strong> "{highlights['top_quote']}"
    </div>"""
        
        html += """
</div>"""
        return html
    
    def _render_categories(self, data: Dict[str, Any]) -> str:
        """Render categories and articles."""
        categories = data.get('categories', {})
        if not categories:
            return "<p>No articles available.</p>"
        
        category_icons = self._get_category_icons()
        html = ""
        article_counter = 0
        
        article_counter = 0
        for category, articles in categories.items():
            if not articles:
                continue
            
            icon = category_icons.get(category, '📌')
            html += f"""
        <div class="category">
            <div class="category-header">
                <span class="category-icon">{icon}</span>
                <h2 class="category-title">{category}</h2>
            </div>"""
            
            for article in articles:
                article_counter += 1
                html += self._render_article(article, data, article_counter)
            
            html += """
        </div>"""
        
        return html
    
    def _render_article(self, article: Dict[str, Any], template_data: Dict[str, Any], article_index: int = 1) -> str:
        """Render individual article with image support and vibrant colors."""
        title = article.get('title', 'No Title')
        summary = article.get('ai_summary') or article.get('original_summary', '')
        
        # Better handling for missing summaries
        if not summary or summary.strip() == '':
            summary = f"Read the full article: {title}"
        
        # Clean up summary formatting
        summary = summary.strip().strip('"').strip("'")
        summary = summary[:300] + "..." if len(summary) > 300 else summary
        
        source_link = article.get('source_link', '#')
        author = article.get('author', '')
        pub_date = article.get('publication_date', '')
        base_url = template_data.get('base_url', 'http://localhost:5000')
        
        # Format publication date
        formatted_date = self._format_date(pub_date)
        
        # Use vibrant colors from the color palette (cycle through 10 colors)
        colors = list(self._get_category_colors().values())
        title_color = colors[(article_index - 1) % len(colors)]
        
        # Check for image
        image_html = self._render_article_image(article, base_url, title)
        has_image = self._has_article_image(article)
        
        html = f"""
            <div class="article {'with-image' if has_image else ''}">
                {image_html}
                <h3 class="article-title" style="color: {title_color};">
                    <a href="{source_link}" target="_blank" style="color: {title_color};">{title}</a>
                </h3>
                <div class="article-meta">"""
        
        if author:
            html += f"By {author} • "
        if formatted_date:
            html += formatted_date
        
        html += f"""
                </div>
                <div class="article-summary">{summary}</div>"""
        
        # Add interactive elements if enabled
        email_prefs = template_data.get('email_prefs', {})
        if email_prefs.get('include_feedback_links', True):
            html += self._render_article_actions(article, template_data)
        
        html += """
            </div>"""
        
        return html
    
    def _render_article_actions(self, article: Dict[str, Any], template_data: Dict[str, Any]) -> str:
        """Render article interaction buttons."""
        article_id = article.get('id')
        user_id = template_data.get('user_id')
        base_url = template_data.get('base_url', 'http://localhost:5000')
        
        if not article_id or not user_id:
            return ""
        
        # Generate feedback URLs with delivery tracking
        delivery_id = template_data.get('delivery_id', '')
        delivery_param = f"&delivery_id={delivery_id}" if delivery_id else ""
        
        like_url = f"{base_url}/track/feedback?user_id={user_id}&article_id={article_id}&feedback=like{delivery_param}"
        dislike_url = f"{base_url}/track/feedback?user_id={user_id}&article_id={article_id}&feedback=dislike{delivery_param}"
        more_url = f"{base_url}/track/feedback?user_id={user_id}&article_id={article_id}&feedback=more_like_this{delivery_param}"
        
        html = """
                <div class="article-actions">
                    <div class="feedback-buttons">
                        <a href="{}" class="btn btn-like"><span>👍</span>Like</a>
                        <a href="{}" class="btn btn-dislike"><span>👎</span>Dislike</a>
                        <a href="{}" class="btn btn-more"><span>➕</span>More</a>
                    </div>""".format(like_url, dislike_url, more_url)
        
        # Add sharing buttons if enabled
        email_prefs = template_data.get('email_prefs', {})
        if email_prefs.get('include_social_sharing', True):
            html += self._render_share_buttons(article)
        
        html += """
                </div>"""
        
        return html
    
    def _render_share_buttons(self, article: Dict[str, Any]) -> str:
        """Render social sharing buttons."""
        title = article.get('title', '')
        link = article.get('source_link', '')
        
        # Generate share URLs (simplified)
        twitter_url = f"https://twitter.com/intent/tweet?url={link}&text={title}"
        linkedin_url = f"https://www.linkedin.com/sharing/share-offsite/?url={link}"
        whatsapp_url = f"https://wa.me/?text={title} {link}"
        email_url = f"mailto:?subject={title}&body={link}"
        
        return f"""
                    <div class="share-buttons">
                        <a href="{twitter_url}" class="share-btn share-twitter" target="_blank">🐦</a>
                        <a href="{linkedin_url}" class="share-btn share-linkedin" target="_blank">💼</a>
                        <a href="{whatsapp_url}" class="share-btn share-whatsapp" target="_blank">💬</a>
                        <a href="{email_url}" class="share-btn share-email">📧</a>
                    </div>"""
    
    def _render_footer(self, data: Dict[str, Any]) -> str:
        """Render email footer."""
        user_id = data.get('user_id', '')
        base_url = data.get('base_url', 'http://localhost:5000')
        user_prefs = data.get('user_prefs', {})
        user_email = user_prefs.get('email', 'you')
        
        return f"""<div class="footer">
            <p>Thank you for reading your personalized news digest!</p>
            <p>
                <a href="{base_url}/unsubscribe?user_id={user_id}">Unsubscribe</a> • 
                <a href="{base_url}/user_management">Account Settings</a>
            </p>
            <p style="font-size: 12px; color: #adb5bd; margin-top: 20px;">
                This email was sent to {user_email}<br>
                Generated by News Digest AI • {datetime.now().year}
            </p>
        </div>"""
    
    def _get_category_icons(self) -> Dict[str, str]:
        """Get category icon mapping."""
        return {
            'Science & Discovery': '🔬',
            'Technology & Gadgets': '💻',
            'Health & Wellness': '🏥',
            'Business & Finance': '💼',
            'Global Affairs': '🌍',
            'Environment & Climate': '🌱',
            'Good Vibes (Positive News)': '😊',
            'Pop Culture & Lifestyle': '🎭',
            'For Young Minds': '🎓',
            'For Young Minds (Youth-Focused)': '🎓',
            'DIY, Skills & How-To': '🔧'
        }
    
    def _format_date(self, date_str: str) -> str:
        """Format publication date."""
        if not date_str:
            return ''
        
        try:
            date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return date_obj.strftime('%B %d, %Y')
        except:
            return date_str[:10] if len(date_str) > 10 else date_str


class ModernNewsTemplate(EmailTemplate):
    """Modern minimalist news digest template."""
    
    def __init__(self):
        self.required_fields = [
            'user_id', 'categories', 'user_prefs', 'email_prefs', 
            'highlights', 'base_url', 'unsubscribe_url'
        ]
    
    def get_required_fields(self) -> List[str]:
        return self.required_fields
    
    def render(self, data: Dict[str, Any]) -> str:
        self._validate_data(data)
        
        return f"""<!DOCTYPE html>
<html lang="en">
{self._render_head()}
<body>
    <div class="container">
        {self._render_header(data)}
        {self._render_highlights(data.get('highlights', {}))}
        {self._render_categories(data)}
        {self._render_footer(data)}
    </div>
</body>
</html>"""
    
    def _validate_data(self, data: Dict[str, Any]) -> None:
        missing_fields = [field for field in self.required_fields 
                         if field not in data or data[field] is None]
        if missing_fields:
            raise ValueError(f"Missing required template fields: {missing_fields}")
    
    def _render_head(self) -> str:
        return """<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>News Brief</title>
    <style>
        body {
            font-family: 'SF Pro Display', -apple-system, BlinkMacSystemFont, sans-serif;
            line-height: 1.5;
            margin: 0;
            padding: 0;
            background: #fafafa;
            color: #1a1a1a;
        }
        .container {
            max-width: 580px;
            margin: 20px auto;
            background: white;
            border-radius: 16px;
            overflow: hidden;
            box-shadow: 0 8px 32px rgba(0,0,0,0.08);
        }
        .header {
            background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
            color: white;
            padding: 25px 20px;
            text-align: center;
        }
        .header h1 {
            margin: 0;
            font-size: 18px;
            font-weight: 700;
            letter-spacing: -0.3px;
        }
        .header p {
            margin: 8px 0 0 0;
            opacity: 0.9;
            font-size: 12px;
            font-weight: 500;
        }
        .highlights {
            background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
            padding: 15px 20px;
            border-left: 3px solid #0ea5e9;
        }
        .highlights h3 {
            margin: 0 0 10px 0;
            color: #0f172a;
            font-size: 14px;
            font-weight: 600;
        }
        .highlight-item {
            margin: 8px 0;
            padding: 8px 12px;
            background: white;
            border-radius: 6px;
            font-size: 12px;
            color: #334155;
        }
        .category {
            margin: 0;
            border-bottom: 1px solid #f1f5f9;
        }
        .category:last-child {
            border-bottom: none;
        }
        .category-header {
            padding: 24px 32px 16px;
            background: #f8fafc;
        }
        .category-title {
            font-size: 18px;
            font-weight: 700;
            color: #0f172a;
            margin: 0;
            display: flex;
            align-items: center;
        }
        .category-icon {
            margin-right: 8px;
            font-size: 18px;
        }
        .article {
            padding: 20px 32px;
            border-bottom: 1px solid #f1f5f9;
        }
        .article:last-child {
            border-bottom: none;
        }
        .article-title {
            font-size: 15px;
            font-weight: 600;
            margin: 0 0 8px 0;
            line-height: 1.4;
        }
        .article-title a {
            text-decoration: none;
            transition: all 0.3s ease;
        }
        .article-title a:hover {
            opacity: 0.8;
        }
        .article.with-image {
            display: flex;
            flex-direction: column;
        }
        .article-image {
            width: 100%;
            max-height: 180px;
            overflow: hidden;
            border-radius: 8px;
            margin-bottom: 12px;
        }
        .article-image img {
            width: 100%;
            height: auto;
            max-height: 180px;
            object-fit: cover;
            object-position: center;
            border-radius: 8px;
        }
        .article-meta {
            color: #64748b;
            font-size: 12px;
            margin-bottom: 12px;
            font-weight: 500;
        }
        .article-summary {
            color: #475569;
            margin-bottom: 16px;
            line-height: 1.5;
            font-size: 14px;
        }
        .article-actions {
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 12px;
        }
        .feedback-buttons {
            display: flex;
            gap: 4px;
            align-items: center;
        }
        .btn {
            padding: 3px 8px;
            border-radius: 20px;
            text-decoration: none;
            font-size: 9px;
            font-weight: 600;
            transition: all 0.2s;
            border: none;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            min-width: 44px;
            white-space: nowrap;
            line-height: 1.2;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .btn:hover {
            transform: translateY(-1px);
        }
        .btn span {
            font-size: 9px;
            margin-right: 1px;
        }
        .btn-like {
            background: #10b981;
            color: white;
        }
        .btn-like:hover {
            background: #059669;
        }
        .btn-dislike {
            background: #f59e0b;
            color: white;
        }
        .btn-dislike:hover {
            background: #d97706;
        }
        .btn-more {
            background: #8b5cf6;
            color: white;
        }
        .btn-more:hover {
            background: #7c3aed;
        }
        .share-buttons {
            display: flex;
            gap: 6px;
            align-items: center;
        }
        .share-btn {
            padding: 6px;
            border-radius: 50%;
            text-decoration: none;
            font-size: 12px;
            border: 1px solid #e2e8f0;
            background: #f8fafc;
            color: #64748b;
            transition: all 0.2s;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 32px;
            height: 32px;
        }
        .share-btn:hover {
            background: #e2e8f0;
            transform: scale(1.1);
        }
        .footer {
            background: #1e293b;
            color: #94a3b8;
            padding: 32px;
            text-align: center;
        }
        .footer a {
            color: #cbd5e1;
            text-decoration: none;
        }
        .footer a:hover {
            color: white;
        }
        @media (max-width: 600px) {
            .container {
                margin: 0;
                border-radius: 0;
            }
            .article {
                padding: 16px 20px;
            }
            .category-header {
                padding: 20px;
            }
        }
    </style>
</head>"""
    
    def _render_header(self, data: Dict[str, Any]) -> str:
        user_prefs = data.get('user_prefs', {})
        user_id = user_prefs.get('user_id', data.get('user_id', 'Reader'))
        
        return f"""<div class="header">
    <h1>✨ Daily Brief</h1>
    <p>Curated for {user_id} • {datetime.now().strftime('%B %d')}</p>
</div>"""
    
    def _render_highlights(self, highlights: Dict[str, Any]) -> str:
        if not any(highlights.values()):
            return ""
        
        html = """<div class="highlights">
    <h3>🎯 Today's Focus</h3>"""
        
        if highlights.get('one_liner'):
            html += f"""
    <div class="highlight-item">
        <strong>Key Insight:</strong> {highlights['one_liner']}
    </div>"""
        
        html += "</div>"
        return html
    
    def _render_categories(self, data: Dict[str, Any]) -> str:
        categories = data.get('categories', {})
        if not categories:
            return "<p>No articles available.</p>"
        
        category_icons = self._get_category_icons()
        html = ""
        article_counter = 0
        
        for category, articles in categories.items():
            if not articles:
                continue
            
            icon = category_icons.get(category, '📌')
            html += f"""
        <div class="category">
            <div class="category-header">
                <h2 class="category-title">
                    <span class="category-icon">{icon}</span>
                    {category}
                </h2>
            </div>"""
            
            for article in articles:
                article_counter += 1
                html += self._render_article(article, data, article_counter)
            
            html += "</div>"
        
        return html
    
    def _render_article(self, article: Dict[str, Any], template_data: Dict[str, Any], article_index: int = 1) -> str:
        title = article.get('title', 'No Title')
        summary = article.get('ai_summary') or article.get('original_summary', '')
        
        # Better handling for missing summaries
        if not summary or summary.strip() == '':
            summary = f"Read the full article: {title}"
        
        # Clean up summary formatting
        summary = summary.strip().strip('"').strip("'")
        summary = summary[:250] + "..." if len(summary) > 250 else summary
        
        source_link = article.get('source_link', '#')
        author = article.get('author', '')
        base_url = template_data.get('base_url', 'http://localhost:5000')
        
        # Use vibrant colors from the color palette
        colors = list(self._get_category_colors().values())
        title_color = colors[(article_index - 1) % len(colors)]
        
        # Check for image
        image_html = self._render_article_image(article, base_url, title)
        has_image = self._has_article_image(article)
        
        html = f"""
            <div class="article {'with-image' if has_image else ''}">
                {image_html}
                <h3 class="article-title" style="color: {title_color};">
                    <a href="{source_link}" target="_blank" style="color: {title_color};">{title}</a>
                </h3>"""
        
        if author:
            html += f'<div class="article-meta">By {author}</div>'
        
        html += f'<div class="article-summary">{summary}</div>'
        
        email_prefs = template_data.get('email_prefs', {})
        if email_prefs.get('include_feedback_links', True):
            html += self._render_article_actions(article, template_data)
        
        html += "</div>"
        return html
    
    def _render_article_actions(self, article: Dict[str, Any], template_data: Dict[str, Any]) -> str:
        article_id = article.get('id')
        user_id = template_data.get('user_id')
        base_url = template_data.get('base_url', 'http://localhost:5000')
        
        if not article_id or not user_id:
            return ""
        
        delivery_id = template_data.get('delivery_id', '')
        delivery_param = f"&delivery_id={delivery_id}" if delivery_id else ""
        
        like_url = f"{base_url}/track/feedback?user_id={user_id}&article_id={article_id}&feedback=like{delivery_param}"
        dislike_url = f"{base_url}/track/feedback?user_id={user_id}&article_id={article_id}&feedback=dislike{delivery_param}"
        more_url = f"{base_url}/track/feedback?user_id={user_id}&article_id={article_id}&feedback=more_like_this{delivery_param}"
        
        html = f"""
                <div class="article-actions">
                    <div class="feedback-buttons">
                        <a href="{like_url}" class="btn btn-like"><span>👍</span>Like</a>
                        <a href="{dislike_url}" class="btn btn-dislike"><span>👎</span>Skip</a>
                        <a href="{more_url}" class="btn btn-more"><span>➕</span>More</a>
                    </div>"""
        
        email_prefs = template_data.get('email_prefs', {})
        if email_prefs.get('include_social_sharing', True):
            html += self._render_share_buttons(article)
        
        html += "</div>"
        return html
    
    def _render_share_buttons(self, article: Dict[str, Any]) -> str:
        title = article.get('title', '')
        link = article.get('source_link', '')
        
        twitter_url = f"https://twitter.com/intent/tweet?url={link}&text={title}"
        linkedin_url = f"https://www.linkedin.com/sharing/share-offsite/?url={link}"
        
        return f"""
                    <div class="share-buttons">
                        <a href="{twitter_url}" class="share-btn" target="_blank">🐦</a>
                        <a href="{linkedin_url}" class="share-btn" target="_blank">💼</a>
                    </div>"""
    
    def _render_footer(self, data: Dict[str, Any]) -> str:
        user_id = data.get('user_id', '')
        base_url = data.get('base_url', 'http://localhost:5000')
        
        return f"""<div class="footer">
            <p>Thank you for reading your daily brief!</p>
            <p>
                <a href="{base_url}/preferences?user_id={user_id}">Preferences</a> • 
                <a href="{base_url}/unsubscribe?user_id={user_id}">Unsubscribe</a>
            </p>
        </div>"""
    
    def _get_category_icons(self) -> Dict[str, str]:
        return {
            'Science & Discovery': '🔬',
            'Technology & Gadgets': '💻',
            'Health & Wellness': '🏥',
            'Business & Finance': '💼',
            'Global Affairs': '🌍',
            'Environment & Climate': '🌱',
            'Good Vibes (Positive News)': '😊',
            'Pop Culture & Lifestyle': '🎭',
            'For Young Minds': '🎓',
            'For Young Minds (Youth-Focused)': '🎓',
            'DIY, Skills & How-To': '🔧'
        }


class NewspaperTemplate(EmailTemplate):
    """Classic newspaper-style digest template."""
    
    def __init__(self):
        self.required_fields = [
            'user_id', 'categories', 'user_prefs', 'email_prefs', 
            'highlights', 'base_url', 'unsubscribe_url'
        ]
    
    def get_required_fields(self) -> List[str]:
        return self.required_fields
    
    def render(self, data: Dict[str, Any]) -> str:
        self._validate_data(data)
        
        return f"""<!DOCTYPE html>
<html lang="en">
{self._render_head()}
<body>
    <div class="container">
        {self._render_header(data)}
        {self._render_highlights(data.get('highlights', {}))}
        {self._render_categories(data)}
        {self._render_footer(data)}
    </div>
</body>
</html>"""
    
    def _validate_data(self, data: Dict[str, Any]) -> None:
        missing_fields = [field for field in self.required_fields 
                         if field not in data or data[field] is None]
        if missing_fields:
            raise ValueError(f"Missing required template fields: {missing_fields}")
    
    def _render_head(self) -> str:
        return """<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>The Daily Report</title>
    <style>
        body {
            font-family: 'Times New Roman', Times, serif;
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            background: #f5f5f0;
            color: #2c2c2c;
        }
        .container {
            max-width: 700px;
            margin: 0 auto;
            background: white;
            border: 2px solid #2c2c2c;
        }
        .header {
            background: #2c2c2c;
            color: white;
            padding: 15px;
            text-align: center;
            border-bottom: 3px double #666;
        }
        .header h1 {
            margin: 0;
            font-size: 22px;
            font-weight: bold;
            font-family: 'Times New Roman', serif;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .header .date {
            margin: 8px 0 0 0;
            font-size: 12px;
            font-weight: normal;
            letter-spacing: 0.5px;
        }
        .highlights {
            background: #f9f9f9;
            padding: 15px;
            border-bottom: 2px solid #ddd;
            border-top: 1px solid #ddd;
        }
        .highlights h3 {
            margin: 0 0 10px 0;
            color: #2c2c2c;
            font-size: 14px;
            font-weight: bold;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            border-bottom: 2px solid #2c2c2c;
            padding-bottom: 3px;
        }
        .highlight-item {
            margin: 8px 0;
            padding: 8px;
            background: white;
            border-left: 3px solid #2c2c2c;
            font-size: 12px;
            font-style: italic;
        }
        .category {
            border-bottom: 2px solid #ddd;
        }
        .category:last-child {
            border-bottom: none;
        }
        .category-header {
            background: #2c2c2c;
            color: white;
            padding: 15px 20px;
        }
        .category-title {
            font-size: 24px;
            font-weight: bold;
            margin: 0;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .article {
            padding: 20px;
            border-bottom: 1px solid #eee;
        }
        .article:last-child {
            border-bottom: none;
        }
        .article-title {
            font-size: 20px;
            font-weight: bold;
            margin: 0 0 10px 0;
            line-height: 1.3;
        }
        .article-title a {
            text-decoration: none;
            transition: all 0.3s ease;
        }
        .article-title a:hover {
            text-decoration: underline;
            opacity: 0.8;
        }
        .article.with-image {
            display: flex;
            flex-direction: column;
        }
        .article-image {
            width: 100%;
            max-height: 200px;
            overflow: hidden;
            border: 2px solid #2c2c2c;
            margin-bottom: 15px;
        }
        .article-image img {
            width: 100%;
            height: auto;
            max-height: 200px;
            object-fit: cover;
            object-position: center;
        }
        .article-meta {
            color: #666;
            font-size: 12px;
            margin-bottom: 15px;
            font-style: italic;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .article-summary {
            color: #444;
            margin-bottom: 15px;
            line-height: 1.7;
            font-size: 15px;
            text-align: justify;
        }
        .article-actions {
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 15px;
            padding-top: 15px;
            border-top: 1px solid #eee;
        }
        .feedback-buttons {
            display: flex;
            gap: 8px;
            align-items: center;
        }
        .btn {
            padding: 5px 12px;
            border: 2px solid #2c2c2c;
            background: white;
            color: #2c2c2c;
            text-decoration: none;
            font-size: 10px;
            font-weight: bold;
            transition: all 0.2s;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            min-width: 50px;
            white-space: nowrap;
            line-height: 1.2;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .btn:hover {
            background: #2c2c2c;
            color: white;
        }
        .btn span {
            font-size: 10px;
            margin-right: 3px;
        }
        .share-buttons {
            display: flex;
            gap: 8px;
            align-items: center;
        }
        .share-btn {
            padding: 5px 8px;
            border: 1px solid #666;
            background: #f9f9f9;
            color: #666;
            text-decoration: none;
            font-size: 11px;
            transition: all 0.2s;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            min-width: 30px;
            height: 30px;
        }
        .share-btn:hover {
            background: #666;
            color: white;
        }
        .footer {
            background: #2c2c2c;
            color: #ccc;
            padding: 20px;
            text-align: center;
            font-size: 12px;
        }
        .footer a {
            color: #fff;
            text-decoration: none;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .footer a:hover {
            text-decoration: underline;
        }
        @media (max-width: 600px) {
            body {
                padding: 10px;
            }
            .header h1 {
                font-size: 18px;
            }
            .article {
                padding: 15px;
            }
        }
    </style>
</head>"""
    
    def _render_header(self, data: Dict[str, Any]) -> str:
        user_prefs = data.get('user_prefs', {})
        user_id = user_prefs.get('user_id', data.get('user_id', 'Subscriber'))
        
        return f"""<div class="header">
    <h1>The Daily Report</h1>
    <div class="date">Personal Edition for {user_id} • {datetime.now().strftime('%A, %B %d, %Y')}</div>
</div>"""
    
    def _render_highlights(self, highlights: Dict[str, Any]) -> str:
        if not any(highlights.values()):
            return ""
        
        html = """<div class="highlights">
    <h3>Editor's Note</h3>"""
        
        if highlights.get('one_liner'):
            html += f"""
    <div class="highlight-item">
        {highlights['one_liner']}
    </div>"""
        
        html += "</div>"
        return html
    
    def _render_categories(self, data: Dict[str, Any]) -> str:
        categories = data.get('categories', {})
        if not categories:
            return "<p>No articles available.</p>"
        
        html = ""
        article_counter = 0
        for category, articles in categories.items():
            if not articles:
                continue
            
            html += f"""
        <div class="category">
            <div class="category-header">
                <h2 class="category-title">{category}</h2>
            </div>"""
            
            for article in articles:
                article_counter += 1
                html += self._render_article(article, data, article_counter)
            
            html += "</div>"
        
        return html
    
    def _render_article(self, article: Dict[str, Any], template_data: Dict[str, Any], article_index: int = 1) -> str:
        title = article.get('title', 'No Title')
        summary = article.get('ai_summary') or article.get('original_summary', '')
        
        # Better handling for missing summaries
        if not summary or summary.strip() == '':
            summary = f"Read the full article: {title}"
        
        # Clean up summary formatting
        summary = summary.strip().strip('"').strip("'")
        summary = summary[:400] + "..." if len(summary) > 400 else summary
        
        source_link = article.get('source_link', '#')
        author = article.get('author', '')
        base_url = template_data.get('base_url', 'http://localhost:5000')
        
        # Use vibrant colors from the color palette
        colors = list(self._get_category_colors().values())
        title_color = colors[(article_index - 1) % len(colors)]
        
        # Check for image
        image_html = self._render_article_image(article, base_url, title)
        has_image = self._has_article_image(article)
        
        html = f"""
            <div class="article {'with-image' if has_image else ''}">
                {image_html}
                <h3 class="article-title" style="color: {title_color};">
                    <a href="{source_link}" target="_blank" style="color: {title_color};">{title}</a>
                </h3>"""
        
        if author:
            html += f'<div class="article-meta">By {author}</div>'
        
        html += f'<div class="article-summary">{summary}</div>'
        
        email_prefs = template_data.get('email_prefs', {})
        if email_prefs.get('include_feedback_links', True):
            html += self._render_article_actions(article, template_data)
        
        html += "</div>"
        return html
    
    def _render_article_actions(self, article: Dict[str, Any], template_data: Dict[str, Any]) -> str:
        article_id = article.get('id')
        user_id = template_data.get('user_id')
        base_url = template_data.get('base_url', 'http://localhost:5000')
        
        if not article_id or not user_id:
            return ""
        
        delivery_id = template_data.get('delivery_id', '')
        delivery_param = f"&delivery_id={delivery_id}" if delivery_id else ""
        
        like_url = f"{base_url}/track/feedback?user_id={user_id}&article_id={article_id}&feedback=like{delivery_param}"
        dislike_url = f"{base_url}/track/feedback?user_id={user_id}&article_id={article_id}&feedback=dislike{delivery_param}"
        more_url = f"{base_url}/track/feedback?user_id={user_id}&article_id={article_id}&feedback=more_like_this{delivery_param}"
        
        html = f"""
                <div class="article-actions">
                    <div class="feedback-buttons">
                        <a href="{like_url}" class="btn"><span>👍</span>Good</a>
                        <a href="{dislike_url}" class="btn"><span>👎</span>Skip</a>
                        <a href="{more_url}" class="btn"><span>➕</span>More</a>
                    </div>"""
        
        email_prefs = template_data.get('email_prefs', {})
        if email_prefs.get('include_social_sharing', True):
            html += self._render_share_buttons(article)
        
        html += "</div>"
        return html
    
    def _render_share_buttons(self, article: Dict[str, Any]) -> str:
        title = article.get('title', '')
        link = article.get('source_link', '')
        
        twitter_url = f"https://twitter.com/intent/tweet?url={link}&text={title}"
        
        return f"""
                    <div class="share-buttons">
                        <a href="{twitter_url}" class="share-btn" target="_blank">Share</a>
                    </div>"""
    
    def _render_footer(self, data: Dict[str, Any]) -> str:
        user_id = data.get('user_id', '')
        base_url = data.get('base_url', 'http://localhost:5000')
        
        return f"""<div class="footer">
            <p>THE DAILY REPORT • PERSONAL EDITION</p>
            <p>
                <a href="{base_url}/user_management">Account Settings</a> | 
                <a href="{base_url}/unsubscribe?user_id={user_id}">Unsubscribe</a>
            </p>
        </div>"""
    
    def _get_category_icons(self) -> Dict[str, str]:
        return {}


class MobileCardTemplate(EmailTemplate):
    """Mobile-first card layout email template with image support (consolidated from enhanced_email_templates.py)."""
    
    def __init__(self):
        self.required_fields = [
            'user_id', 'categories', 'user_prefs', 'email_prefs', 
            'highlights', 'base_url', 'unsubscribe_url'
        ]
    
    def get_required_fields(self) -> List[str]:
        return self.required_fields
    
    def render(self, data: Dict[str, Any]) -> str:
        """Render the mobile card email template."""
        self._validate_data(data)
        
        user_id = data.get('user_id')
        delivery_id = data.get('delivery_id')
        base_url = data.get('base_url', 'http://localhost:5000')
        
        return self.render_mobile_card_template(data, user_id, delivery_id, base_url)
    
    def _validate_data(self, data: Dict[str, Any]) -> None:
        missing_fields = [field for field in self.required_fields 
                         if field not in data or data[field] is None]
        if missing_fields:
            raise ValueError(f"Missing required template fields: {missing_fields}")
    
    def render_mobile_card_template(self, digest_data: Dict, user_id: str = None, delivery_id: int = None, 
                                  base_url: str = "http://localhost:5000") -> str:
        """Render a mobile-first card layout email template with images."""
        
        # Extract data
        categories = digest_data.get('categories', {})
        generated_at = digest_data.get('generated_at', datetime.now().isoformat())
        
        # Format dates
        try:
            generated_dt = datetime.fromisoformat(generated_at.replace('Z', '+00:00'))
            current_date = generated_dt.strftime('%B %d, %Y')
            current_time = generated_dt.strftime('%I:%M %p')
        except:
            current_date = datetime.now().strftime('%B %d, %Y')
            current_time = datetime.now().strftime('%I:%M %p')
        
        # Count total articles
        total_articles = sum(len(articles) for articles in categories.values())
        
        # Generate categories HTML
        categories_html = ""
        
        for category, articles in categories.items():
            if not articles:
                continue
            
            # Category header
            categories_html += f"""
            <div class="category-header">
                <h2 class="category-title">
                    {self._get_category_emoji(category)} {category}
                    <span class="category-count">{len(articles)}</span>
                </h2>
            </div>
            """
            
            # Article cards
            for article in articles:
                categories_html += self._render_mobile_article_card(article, category, user_id, delivery_id, base_url)
        
        # Generate unsubscribe URL
        unsubscribe_url = f"{base_url}/unsubscribe?user_id={user_id}&delivery_id={delivery_id}"
        
        return f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <meta http-equiv="X-UA-Compatible" content="IE=edge">
            <title>Your News Digest - {current_date}</title>
            {self._get_mobile_styles()}
        </head>
        <body>
            <div class="email-container">
                <div class="header">
                    <h1>📰 Your News Digest</h1>
                    <p>Personalized for {user_id}</p>
                    <p>{current_date} at {current_time}</p>
                    <p>{total_articles} articles across {len(categories)} categories</p>
                </div>
                
                <div class="content">
                    {categories_html}
                </div>
                
                <div class="footer">
                    <h3>📬 How was today's digest?</h3>
                    
                    <div class="feedback-section">
                        <a href="{base_url}/feedback?user_id={user_id}&type=excellent&delivery_id={delivery_id}" class="feedback-btn">⭐ Excellent</a>
                        <a href="{base_url}/feedback?user_id={user_id}&type=good&delivery_id={delivery_id}" class="feedback-btn">👍 Good</a>
                        <a href="{base_url}/feedback?user_id={user_id}&type=needs_improvement&delivery_id={delivery_id}" class="feedback-btn">📝 Improve</a>
                    </div>
                    
                    <div class="footer-links">
                        <strong>News Digest</strong> • Powered by AI<br>
                        <a href="{base_url}/preferences?user_id={user_id}">⚙️ Preferences</a>
                        <a href="{base_url}/digest/{user_id}">🌐 View Online</a>
                    </div>
                    
                    <p>
                        <a href="{unsubscribe_url}" class="unsubscribe-link">
                            Unsubscribe from these emails
                        </a>
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
    
    def _render_mobile_article_card(self, article: Dict, category: str, user_id: str, delivery_id: int, base_url: str) -> str:
        """Render individual article card for mobile layout."""
        import urllib.parse
        
        article_id = article.get('id', 0)
        title = article.get('title', 'Untitled Article')
        
        # Get the best available summary
        ai_summary = article.get('ai_summary', '').strip()
        original_summary = article.get('original_summary', '').strip()
        
        if ai_summary:
            summary = ai_summary[:300] + '...' if len(ai_summary) > 300 else ai_summary
        elif original_summary:
            summary = original_summary[:300] + '...' if len(original_summary) > 300 else original_summary
        else:
            summary = f"Discover the latest insights in {category.lower()}. Click to read the full story."
        
        source_link = article.get('source_link', '#')
        author = article.get('author', 'Unknown Author')
        pub_date = article.get('publication_date', '')
        image_url = article.get('image_url')
        
        # Format publication date
        try:
            if pub_date:
                pub_dt = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
                formatted_date = pub_dt.strftime('%b %d, %Y')
            else:
                formatted_date = 'Recent'
        except:
            formatted_date = 'Recent'
        
        # Determine image to use
        image_html = ""
        has_image = False
        
        if image_url and image_url.startswith(('http://', 'https://')):
            image_html = f'<div class="card-image"><img src="{image_url}" alt="{title}" loading="lazy" /></div>'
            has_image = True
        
        # Generate action URLs
        like_url = f"{base_url}/feedback?user_id={user_id}&article_id={article_id}&type=like&delivery_id={delivery_id}"
        dislike_url = f"{base_url}/feedback?user_id={user_id}&article_id={article_id}&type=dislike&delivery_id={delivery_id}"
        more_url = f"{base_url}/feedback?user_id={user_id}&article_id={article_id}&type=more_like_this&delivery_id={delivery_id}"
        
        # Generate share URLs
        encoded_title = urllib.parse.quote(title)
        encoded_url = urllib.parse.quote(source_link)
        
        twitter_url = f"https://twitter.com/intent/tweet?text={encoded_title}&url={encoded_url}"
        linkedin_url = f"https://www.linkedin.com/sharing/share-offsite/?url={encoded_url}"
        whatsapp_url = f"https://wa.me/?text={encoded_title}%20{encoded_url}"
        
        # Create article card
        card_class = "news-card" + ("" if has_image else " no-image")
        
        # Get vibrant color for this category
        category_color = self._get_category_color(category)
        
        return f"""
        <div class="{card_class}">
            {image_html}
            
            <div class="card-content">
                <div class="card-category" style="background: {category_color};">{category}</div>
                
                <h3 class="card-title" style="color: {category_color};">
                    <a href="{source_link}" target="_blank" style="color: {category_color};">{title}</a>
                </h3>
                
                <p class="card-summary">{summary}</p>
                
                <div class="card-footer">
                    <div class="card-meta">
                        <span class="card-author">{author}</span>
                        <span>•</span>
                        <span>{formatted_date}</span>
                    </div>
                    
                    <div class="card-actions">
                        <a href="{like_url}" class="action-btn like-btn" title="Like this article">👍</a>
                        <a href="{dislike_url}" class="action-btn dislike-btn" title="Dislike this article">👎</a>
                        <a href="{more_url}" class="action-btn share-btn" title="More like this">⭐</a>
                    </div>
                </div>
                
                <div class="social-share">
                    <a href="{twitter_url}" class="social-btn twitter-btn" target="_blank">🐦 Twitter</a>
                    <a href="{linkedin_url}" class="social-btn linkedin-btn" target="_blank">💼 LinkedIn</a>
                    <a href="{whatsapp_url}" class="social-btn whatsapp-btn" target="_blank">💬 WhatsApp</a>
                </div>
            </div>
        </div>
        """
    
    def _get_mobile_styles(self) -> str:
        """Get comprehensive mobile-optimized CSS styles."""
        return """
        <style>
            /* Reset and base styles */
            body, table, td, p, a, li, blockquote {
                -webkit-text-size-adjust: 100%;
                -ms-text-size-adjust: 100%;
                margin: 0;
                padding: 0;
            }
            
            img {
                -ms-interpolation-mode: bicubic;
                border: 0;
                outline: none;
                text-decoration: none;
                max-width: 100%;
                height: auto;
                display: block;
            }
            
            body {
                width: 100% !important;
                min-width: 100%;
                margin: 0;
                padding: 0;
                background: #f8fafc;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                line-height: 1.6;
            }
            
            .email-container {
                max-width: 600px;
                margin: 0 auto;
                background: #ffffff;
                border-radius: 0;
                overflow: hidden;
            }
            
            .header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 24px 20px;
                text-align: center;
                color: white;
            }
            
            .header h1 {
                margin: 0 0 8px 0;
                font-size: 28px;
                font-weight: 700;
                color: white;
                line-height: 1.2;
            }
            
            .header p {
                margin: 4px 0;
                font-size: 16px;
                opacity: 0.9;
                color: white;
            }
            
            .content {
                padding: 20px;
                background: #f8fafc;
            }
            
            .news-card {
                background: white;
                border-radius: 16px;
                margin-bottom: 20px;
                overflow: hidden;
                box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
                border: 1px solid #e2e8f0;
                transition: all 0.3s ease;
            }
            
            .news-card:hover {
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.12);
                transform: translateY(-2px);
            }
            
            .news-card.no-image {
                border-left: 5px solid #667eea;
                background: linear-gradient(135deg, #ffffff 0%, #f9fafb 100%);
            }
            
            .card-image {
                width: 100%;
                max-height: 220px;
                overflow: hidden;
                position: relative;
            }
            
            .card-image img {
                width: 100%;
                height: auto;
                max-height: 220px;
                object-fit: cover;
                object-position: center;
                transition: transform 0.3s ease;
            }
            
            .card-content {
                padding: 20px;
            }
            
            .card-category {
                display: inline-block;
                background: #667eea;
                color: white;
                font-size: 12px;
                font-weight: 600;
                padding: 4px 12px;
                border-radius: 12px;
                margin-bottom: 12px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            
            .card-title {
                margin: 0 0 12px 0;
                font-size: 20px;
                font-weight: 700;
                line-height: 1.3;
                color: #1a202c;
            }
            
            .card-title a {
                color: #1a202c;
                text-decoration: none;
                display: block;
            }
            
            .card-title a:hover {
                color: #667eea;
            }
            
            .card-summary {
                color: #4a5568;
                font-size: 15px;
                line-height: 1.6;
                margin: 0 0 16px 0;
            }
            
            .card-footer {
                padding-top: 16px;
                border-top: 1px solid #e2e8f0;
                display: flex;
                justify-content: space-between;
                align-items: center;
                flex-wrap: wrap;
                gap: 12px;
            }
            
            .card-meta {
                font-size: 13px;
                color: #718096;
                display: flex;
                align-items: center;
                gap: 8px;
            }
            
            .card-author {
                font-weight: 500;
                color: #4a5568;
            }
            
            .card-actions {
                display: flex;
                gap: 8px;
                align-items: center;
            }
            
            .action-btn {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                width: 32px;
                height: 32px;
                border-radius: 50%;
                text-decoration: none;
                font-size: 14px;
                transition: all 0.2s ease;
                border: 1px solid #e2e8f0;
                background: white;
            }
            
            .action-btn:hover {
                transform: scale(1.1);
                box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
            }
            
            .like-btn {
                color: #48bb78;
                border-color: #48bb78;
            }
            
            .like-btn:hover {
                background: #48bb78;
                color: white;
            }
            
            .dislike-btn {
                color: #f56565;
                border-color: #f56565;
            }
            
            .dislike-btn:hover {
                background: #f56565;
                color: white;
            }
            
            .share-btn {
                color: #4299e1;
                border-color: #4299e1;
            }
            
            .share-btn:hover {
                background: #4299e1;
                color: white;
            }
            
            .social-share {
                display: flex;
                gap: 8px;
                margin-top: 12px;
                padding-top: 12px;
                border-top: 1px solid #f7fafc;
            }
            
            .social-btn {
                display: inline-flex;
                align-items: center;
                gap: 6px;
                padding: 6px 12px;
                border-radius: 20px;
                text-decoration: none;
                font-size: 12px;
                font-weight: 500;
                transition: all 0.2s ease;
                border: 1px solid #e2e8f0;
                background: #f8fafc;
                color: #4a5568;
            }
            
            .social-btn:hover {
                transform: translateY(-1px);
                box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
            }
            
            .twitter-btn:hover {
                background: #1da1f2;
                color: white;
                border-color: #1da1f2;
            }
            
            .linkedin-btn:hover {
                background: #0077b5;
                color: white;
                border-color: #0077b5;
            }
            
            .whatsapp-btn:hover {
                background: #25d366;
                color: white;
                border-color: #25d366;
            }
            
            .category-header {
                background: white;
                border-radius: 12px;
                padding: 16px 20px;
                margin: 24px 0 16px 0;
                border-left: 4px solid #667eea;
                box-shadow: 0 1px 6px rgba(0, 0, 0, 0.05);
            }
            
            .category-title {
                margin: 0;
                font-size: 22px;
                font-weight: 700;
                color: #667eea;
                display: flex;
                align-items: center;
                gap: 8px;
            }
            
            .category-count {
                background: #667eea;
                color: white;
                font-size: 12px;
                font-weight: 600;
                padding: 4px 8px;
                border-radius: 12px;
                margin-left: auto;
            }
            
            .footer {
                background: #2d3748;
                color: white;
                padding: 32px 20px;
                text-align: center;
            }
            
            .footer h3 {
                margin: 0 0 16px 0;
                font-size: 20px;
                font-weight: 600;
                color: white;
            }
            
            .feedback-section {
                margin: 20px 0;
            }
            
            .feedback-btn {
                display: inline-block;
                margin: 4px 8px;
                padding: 8px 16px;
                background: #667eea;
                color: white;
                text-decoration: none;
                border-radius: 20px;
                font-size: 14px;
                font-weight: 500;
                transition: all 0.2s ease;
            }
            
            .feedback-btn:hover {
                background: #5a67d8;
                transform: translateY(-1px);
            }
            
            .footer-links {
                margin: 20px 0;
                font-size: 14px;
            }
            
            .footer-links a {
                color: #a0aec0;
                text-decoration: none;
                margin: 0 8px;
            }
            
            .footer-links a:hover {
                color: white;
            }
            
            .unsubscribe-link {
                color: #a0aec0;
                font-size: 12px;
                text-decoration: none;
            }
            
            .unsubscribe-link:hover {
                color: white;
            }
            
            @media only screen and (max-width: 600px) {
                .email-container {
                    border-radius: 0;
                    margin: 0;
                }
                
                .header {
                    padding: 20px 16px;
                }
                
                .header h1 {
                    font-size: 24px;
                }
                
                .content {
                    padding: 16px;
                }
                
                .news-card {
                    margin-bottom: 16px;
                    border-radius: 12px;
                }
                
                .card-content {
                    padding: 16px;
                }
                
                .card-title {
                    font-size: 18px;
                }
                
                .card-footer {
                    flex-direction: column;
                    align-items: flex-start;
                    gap: 8px;
                }
                
                .footer {
                    padding: 24px 16px;
                }
            }
        </style>
        """
    

class MagazineTemplate(EmailTemplate):
    """Magazine-style colorful digest template."""
    
    def __init__(self):
        self.required_fields = [
            'user_id', 'categories', 'user_prefs', 'email_prefs', 
            'highlights', 'base_url', 'unsubscribe_url'
        ]
    
    def get_required_fields(self) -> List[str]:
        return self.required_fields
    
    def render(self, data: Dict[str, Any]) -> str:
        self._validate_data(data)
        
        return f"""<!DOCTYPE html>
<html lang="en">
{self._render_head()}
<body>
    <div class="container">
        {self._render_header(data)}
        {self._render_highlights(data.get('highlights', {}))}
        {self._render_categories(data)}
        {self._render_footer(data)}
    </div>
</body>
</html>"""
    
    def _validate_data(self, data: Dict[str, Any]) -> None:
        missing_fields = [field for field in self.required_fields 
                         if field not in data or data[field] is None]
        if missing_fields:
            raise ValueError(f"Missing required template fields: {missing_fields}")
    
    def _render_head(self) -> str:
        return """<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NewsScope Magazine</title>
    <style>
        body {
            font-family: 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 0;
            background: linear-gradient(135deg, #ff9a9e 0%, #fecfef 50%, #fecfef 100%);
            color: #2d3748;
        }
        .container {
            max-width: 600px;
            margin: 20px auto;
            background: white;
            border-radius: 20px;
            overflow: hidden;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 25px 20px;
            text-align: center;
            position: relative;
            overflow: hidden;
        }
        .header::before {
            content: '';
            position: absolute;
            top: -50%;
            right: -50%;
            width: 200%;
            height: 200%;
            background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%);
            animation: pulse 4s ease-in-out infinite;
        }
        @keyframes pulse {
            0%, 100% { transform: scale(1); opacity: 0.3; }
            50% { transform: scale(1.1); opacity: 0.1; }
        }
        .header h1 {
            margin: 0;
            font-size: 20px;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            position: relative;
            z-index: 1;
        }
        .header p {
            margin: 10px 0 0 0;
            font-size: 13px;
            font-weight: 300;
            position: relative;
            z-index: 1;
        }
        .highlights {
            background: linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%);
            padding: 15px 20px;
            position: relative;
        }
        .highlights h3 {
            margin: 0 0 12px 0;
            color: #2d3748;
            font-size: 15px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.3px;
        }
        .highlight-item {
            margin: 10px 0;
            padding: 10px 15px;
            background: rgba(255,255,255,0.9);
            border-radius: 10px;
            font-size: 12px;
            color: #4a5568;
            border-left: 3px solid #667eea;
        }
        .category {
            margin: 0;
        }
        .category-header {
            background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%);
            padding: 25px 30px;
            position: relative;
        }
        .category-title {
            font-size: 22px;
            font-weight: 700;
            color: #2d3748;
            margin: 0;
            display: flex;
            align-items: center;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .category-icon {
            margin-right: 12px;
            font-size: 24px;
            background: white;
            width: 40px;
            height: 40px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        }
        .article {
            padding: 25px 30px;
            background: white;
            position: relative;
        }
        .article::before {
            content: '';
            position: absolute;
            left: 0;
            top: 0;
            bottom: 0;
            width: 4px;
            background: linear-gradient(to bottom, #667eea, #764ba2);
        }
        .article-title {
            font-size: 18px;
            font-weight: 700;
            margin: 0 0 12px 0;
            line-height: 1.4;
        }
        .article-title a {
            text-decoration: none;
            background: linear-gradient(to right, currentColor, currentColor);
            background-size: 0% 2px;
            background-repeat: no-repeat;
            background-position: 0% 100%;
            transition: background-size 0.3s;
        }
        .article-title a:hover {
            background-size: 100% 2px;
        }
        .article.with-image {
            display: flex;
            flex-direction: column;
        }
        .article-image {
            width: 100%;
            max-height: 220px;
            overflow: hidden;
            border-radius: 12px;
            margin-bottom: 15px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }
        .article-image img {
            width: 100%;
            height: auto;
            max-height: 220px;
            object-fit: cover;
            object-position: center;
            border-radius: 12px;
        }
        .article-meta {
            color: #718096;
            font-size: 12px;
            margin-bottom: 15px;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .article-summary {
            color: #4a5568;
            margin-bottom: 20px;
            line-height: 1.7;
            font-size: 15px;
        }
        .article-actions {
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 15px;
            padding-top: 20px;
            border-top: 1px solid #e2e8f0;
        }
        .feedback-buttons {
            display: flex;
            gap: 6px;
            align-items: center;
        }
        .btn {
            padding: 4px 10px;
            border-radius: 25px;
            text-decoration: none;
            font-size: 10px;
            font-weight: 700;
            transition: all 0.3s;
            border: none;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            min-width: 50px;
            white-space: nowrap;
            line-height: 1.2;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        }
        .btn span {
            font-size: 10px;
            margin-right: 2px;
        }
        .btn-like {
            background: linear-gradient(135deg, #48bb78 0%, #38a169 100%);
            color: white;
        }
        .btn-dislike {
            background: linear-gradient(135deg, #ed8936 0%, #dd6b20 100%);
            color: white;
        }
        .btn-more {
            background: linear-gradient(135deg, #4299e1 0%, #3182ce 100%);
            color: white;
        }
        .share-buttons {
            display: flex;
            gap: 6px;
            align-items: center;
        }
        .share-btn {
            padding: 6px;
            border-radius: 50%;
            text-decoration: none;
            font-size: 14px;
            background: linear-gradient(135deg, #edf2f7 0%, #e2e8f0 100%);
            color: #4a5568;
            transition: all 0.3s;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 36px;
            height: 36px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .share-btn:hover {
            transform: scale(1.1);
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        }
        .footer {
            background: linear-gradient(135deg, #2d3748 0%, #4a5568 100%);
            color: #e2e8f0;
            padding: 30px;
            text-align: center;
        }
        .footer a {
            color: white;
            text-decoration: none;
            font-weight: 500;
        }
        .footer a:hover {
            text-decoration: underline;
        }
        @media (max-width: 600px) {
            .container {
                margin: 10px;
                border-radius: 15px;
            }
            .article {
                padding: 20px 25px;
            }
        }
    </style>
</head>"""
    
    def _render_header(self, data: Dict[str, Any]) -> str:
        user_prefs = data.get('user_prefs', {})
        user_id = user_prefs.get('user_id', data.get('user_id', 'Reader'))
        
        return f"""<div class="header">
    <h1>🌟 NewsScope</h1>
    <p>Your Personal Magazine • {user_id} • {datetime.now().strftime('%B %d')}</p>
</div>"""
    
    def _render_highlights(self, highlights: Dict[str, Any]) -> str:
        if not any(highlights.values()):
            return ""
        
        html = """<div class="highlights">
    <h3>✨ Spotlight</h3>"""
        
        if highlights.get('one_liner'):
            html += f"""
    <div class="highlight-item">
        {highlights['one_liner']}
    </div>"""
        
        html += "</div>"
        return html
    
    def _render_categories(self, data: Dict[str, Any]) -> str:
        categories = data.get('categories', {})
        if not categories:
            return "<p>No articles available.</p>"
        
        category_icons = self._get_category_icons()
        html = ""
        article_counter = 0
        
        for category, articles in categories.items():
            if not articles:
                continue
            
            icon = category_icons.get(category, '📌')
            html += f"""
        <div class="category">
            <div class="category-header">
                <h2 class="category-title">
                    <span class="category-icon">{icon}</span>
                    {category}
                </h2>
            </div>"""
            
            for article in articles:
                article_counter += 1
                html += self._render_article(article, data, article_counter)
            
            html += "</div>"
        
        return html
    
    def _render_article(self, article: Dict[str, Any], template_data: Dict[str, Any], article_index: int = 1) -> str:
        title = article.get('title', 'No Title')
        summary = article.get('ai_summary') or article.get('original_summary', '')
        
        # Better handling for missing summaries
        if not summary or summary.strip() == '':
            summary = f"Read the full article: {title}"
        
        # Clean up summary formatting
        summary = summary.strip().strip('"').strip("'")
        summary = summary[:300] + "..." if len(summary) > 300 else summary
        
        source_link = article.get('source_link', '#')
        author = article.get('author', '')
        base_url = template_data.get('base_url', 'http://localhost:5000')
        
        # Use vibrant colors from the color palette
        colors = list(self._get_category_colors().values())
        title_color = colors[(article_index - 1) % len(colors)]
        
        # Check for image
        image_html = self._render_article_image(article, base_url, title)
        has_image = self._has_article_image(article)
        
        html = f"""
            <div class="article {'with-image' if has_image else ''}">
                {image_html}
                <h3 class="article-title" style="color: {title_color};">
                    <a href="{source_link}" target="_blank" style="color: {title_color};">{title}</a>
                </h3>"""
        
        if author:
            html += f'<div class="article-meta">By {author}</div>'
        
        html += f'<div class="article-summary">{summary}</div>'
        
        email_prefs = template_data.get('email_prefs', {})
        if email_prefs.get('include_feedback_links', True):
            html += self._render_article_actions(article, template_data)
        
        html += "</div>"
        return html
    
    def _render_article_actions(self, article: Dict[str, Any], template_data: Dict[str, Any]) -> str:
        article_id = article.get('id')
        user_id = template_data.get('user_id')
        base_url = template_data.get('base_url', 'http://localhost:5000')
        
        if not article_id or not user_id:
            return ""
        
        delivery_id = template_data.get('delivery_id', '')
        delivery_param = f"&delivery_id={delivery_id}" if delivery_id else ""
        
        like_url = f"{base_url}/track/feedback?user_id={user_id}&article_id={article_id}&feedback=like{delivery_param}"
        dislike_url = f"{base_url}/track/feedback?user_id={user_id}&article_id={article_id}&feedback=dislike{delivery_param}"
        more_url = f"{base_url}/track/feedback?user_id={user_id}&article_id={article_id}&feedback=more_like_this{delivery_param}"
        
        html = f"""
                <div class="article-actions">
                    <div class="feedback-buttons">
                        <a href="{like_url}" class="btn btn-like"><span>💚</span>Love</a>
                        <a href="{dislike_url}" class="btn btn-dislike"><span>⏭️</span>Skip</a>
                        <a href="{more_url}" class="btn btn-more"><span>🔥</span>More</a>
                    </div>"""
        
        email_prefs = template_data.get('email_prefs', {})
        if email_prefs.get('include_social_sharing', True):
            html += self._render_share_buttons(article)
        
        html += "</div>"
        return html
    
    def _render_share_buttons(self, article: Dict[str, Any]) -> str:
        title = article.get('title', '')
        link = article.get('source_link', '')
        
        twitter_url = f"https://twitter.com/intent/tweet?url={link}&text={title}"
        linkedin_url = f"https://www.linkedin.com/sharing/share-offsite/?url={link}"
        
        return f"""
                    <div class="share-buttons">
                        <a href="{twitter_url}" class="share-btn" target="_blank">🐦</a>
                        <a href="{linkedin_url}" class="share-btn" target="_blank">💼</a>
                    </div>"""
    
    def _render_footer(self, data: Dict[str, Any]) -> str:
        user_id = data.get('user_id', '')
        base_url = data.get('base_url', 'http://localhost:5000')
        
        return f"""<div class="footer">
            <p>🌟 NewsScope Magazine • Personal Edition</p>
            <p>
                <a href="{base_url}/preferences?user_id={user_id}">✏️ Preferences</a> • 
                <a href="{base_url}/unsubscribe?user_id={user_id}">🚪 Unsubscribe</a>
            </p>
        </div>"""
    
    def _get_category_icons(self) -> Dict[str, str]:
        return {
            'Science & Discovery': '🔬',
            'Technology & Gadgets': '💻',
            'Health & Wellness': '🏥',
            'Business & Finance': '💼',
            'Global Affairs': '🌍',
            'Environment & Climate': '🌱',
            'Good Vibes (Positive News)': '😊',
            'Pop Culture & Lifestyle': '🎭',
            'For Young Minds': '🎓',
            'For Young Minds (Youth-Focused)': '🎓',
            'DIY, Skills & How-To': '🔧'
        }


class EmailTemplateManager:
    """Manages email templates with caching and validation."""
    
    def __init__(self):
        self._templates = {
            'news_digest': NewsDigestTemplate(),      # Classic professional
            'modern_news': ModernNewsTemplate(),      # Modern minimalist  
            'newspaper': NewspaperTemplate(),         # Classic newspaper
            'magazine': MagazineTemplate(),           # Colorful magazine
            'mobile_card': MobileCardTemplate()     # Mobile-first card layout with images
        }
    
    def render_template(self, template_name: str, data: Dict[str, Any]) -> str:
        """Render email template with data."""
        if template_name not in self._templates:
            raise ValueError(f"Unknown template: {template_name}")
        
        template = self._templates[template_name]
        
        try:
            return template.render(data)
        except Exception as e:
            logger.error(f"Template rendering failed for {template_name}: {e}")
            raise ValueError(f"Template rendering failed: {e}")
    
    def render_random_template(self, data: Dict[str, Any]) -> str:
        """Render email template with a randomly selected template."""
        template_names = list(self._templates.keys())
        
        # Check if any articles have images - prioritize mobile_card template
        has_images = False
        categories = data.get('categories', {})
        for category_articles in categories.values():
            for article in category_articles:
                image_url = article.get('image_url')
                if image_url and image_url.startswith(('http://', 'https://')):
                    has_images = True
                    break
            if has_images:
                break
        
        # If we have images, prefer the mobile_card template (80% chance)
        if has_images and 'mobile_card' in template_names and random.random() < 0.8:
            selected_template = 'mobile_card'
        else:
            selected_template = random.choice(template_names)
        
        logger.info(f"Randomly selected template: {selected_template} (has_images: {has_images})")
        return self.render_template(selected_template, data)
    
    def get_random_template_name(self) -> str:
        """Get a random template name."""
        return random.choice(list(self._templates.keys()))
    
    def get_available_templates(self) -> List[str]:
        """Get list of available template names."""
        return list(self._templates.keys())
    
    def validate_template_data(self, template_name: str, data: Dict[str, Any]) -> List[str]:
        """Validate template data and return list of missing fields."""
        if template_name not in self._templates:
            raise ValueError(f"Unknown template: {template_name}")
        
        template = self._templates[template_name]
        required_fields = template.get_required_fields()
        
        return [field for field in required_fields 
                if field not in data or data[field] is None]


# Global template manager instance
template_manager = EmailTemplateManager()


def render_email_template(template_name: str, data: Dict[str, Any]) -> str:
    """Render email template with provided data."""
    if template_name == 'random' or template_name == 'news_digest':
        # Use random template selection for default or explicit random request
        return template_manager.render_random_template(data)
    else:
        return template_manager.render_template(template_name, data)