"""Image extraction and processing for news articles."""

import os
import requests
import hashlib
import random
from urllib.parse import urljoin, urlparse
from typing import Dict, List, Optional, Tuple
import logging
from datetime import datetime
import mimetypes
from pathlib import Path

try:
    from PIL import Image, ImageOps
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False
    logging.warning("Pillow not installed. Image optimization will be limited.")

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False
    logging.warning("BeautifulSoup4 not installed. Open Graph extraction will be disabled.")

try:
    from .database import DatabaseManager
except ImportError:
    from database import DatabaseManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ImageExtractor:
    """Handles image extraction from RSS feeds, Open Graph, and stock images."""
    
    def __init__(self, db_manager: DatabaseManager = None):
        self.db_manager = db_manager or DatabaseManager()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'NewsDigest/1.0 (Image Extractor)',
            'Accept': 'text/html,application/xhtml+xml,image/*,*/*;q=0.8'
        })
        
        # Create images directory structure
        self.base_images_dir = Path('images')
        self.cached_images_dir = self.base_images_dir / 'cached'
        self.stock_images_dir = self.base_images_dir / 'stock'
        
        # Create directories
        for directory in [self.base_images_dir, self.cached_images_dir, self.stock_images_dir]:
            directory.mkdir(parents=True, exist_ok=True)
        
        # Supported image formats
        self.supported_formats = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}
        
        # Maximum image size for download (5MB)
        self.max_download_size = 5 * 1024 * 1024
        
        # Target size for email optimization (150KB)
        self.target_email_size = 150 * 1024
    
    def extract_image_from_entry(self, entry, article_url: str) -> Optional[Dict]:
        """Extract image from RSS entry using multiple methods."""
        
        # Method 1: RSS media content
        image_data = self._extract_from_rss_media(entry)
        if image_data:
            image_data['source'] = 'rss'
            return image_data
        
        # Method 2: RSS enclosures
        image_data = self._extract_from_rss_enclosures(entry)
        if image_data:
            image_data['source'] = 'rss'
            return image_data
        
        # Method 3: Open Graph from article page
        if article_url and BS4_AVAILABLE:
            image_data = self._extract_from_open_graph(article_url)
            if image_data:
                image_data['source'] = 'opengraph'
                return image_data
        
        # Method 4: Stock image fallback
        image_data = self._get_stock_image_fallback()
        if image_data:
            image_data['source'] = 'stock'
            return image_data
        
        return None
    
    def _extract_from_rss_media(self, entry) -> Optional[Dict]:
        """Extract image from RSS media content fields."""
        try:
            # Check for media:content
            if hasattr(entry, 'media_content'):
                for media in entry.media_content:
                    if media.get('type', '').startswith('image/'):
                        url = media.get('url')
                        if url and self._is_valid_image_url(url):
                            return {'url': url, 'type': 'media_content'}
            
            # Check for media:thumbnail
            if hasattr(entry, 'media_thumbnail'):
                for thumbnail in entry.media_thumbnail:
                    url = thumbnail.get('url')
                    if url and self._is_valid_image_url(url):
                        return {'url': url, 'type': 'media_thumbnail'}
            
            # Check for image tag
            if hasattr(entry, 'image'):
                image_data = entry.image
                if isinstance(image_data, dict):
                    url = image_data.get('href') or image_data.get('url')
                elif isinstance(image_data, str):
                    url = image_data
                else:
                    url = str(image_data) if image_data else None
                
                if url and self._is_valid_image_url(url):
                    return {'url': url, 'type': 'image_tag'}
            
            # Check for content/summary with embedded images
            content_fields = ['content', 'summary', 'description']
            for field in content_fields:
                if hasattr(entry, field):
                    field_content = getattr(entry, field)
                    if isinstance(field_content, list) and field_content:
                        field_content = field_content[0].value if hasattr(field_content[0], 'value') else str(field_content[0])
                    elif not isinstance(field_content, str):
                        field_content = str(field_content) if field_content else ''
                    
                    # Extract images from HTML content
                    if field_content and BS4_AVAILABLE:
                        image_url = self._extract_image_from_html(field_content)
                        if image_url:
                            return {'url': image_url, 'type': f'{field}_html'}
            
        except Exception as e:
            logger.debug(f"Error extracting from RSS media: {e}")
        
        return None
    
    def _extract_image_from_html(self, html_content: str) -> Optional[str]:
        """Extract first valid image URL from HTML content."""
        if not BS4_AVAILABLE or not html_content:
            return None
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Look for img tags
            img_tags = soup.find_all('img')
            for img in img_tags:
                src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
                if src and self._is_valid_image_url(src):
                    # Skip very small images (likely icons/tracking pixels)
                    width = img.get('width')
                    height = img.get('height')
                    if width and height:
                        try:
                            w, h = int(width), int(height)
                            if w < 100 or h < 100:  # Skip small images
                                continue
                        except:
                            pass
                    
                    return src
            
        except Exception as e:
            logger.debug(f"Error extracting image from HTML: {e}")
        
        return None
    
    def _extract_from_rss_enclosures(self, entry) -> Optional[Dict]:
        """Extract image from RSS enclosures."""
        try:
            if hasattr(entry, 'enclosures'):
                for enclosure in entry.enclosures:
                    if enclosure.get('type', '').startswith('image/'):
                        url = enclosure.get('href') or enclosure.get('url')
                        if url and self._is_valid_image_url(url):
                            return {'url': url, 'type': 'enclosure'}
        except Exception as e:
            logger.debug(f"Error extracting from RSS enclosures: {e}")
        
        return None
    
    def _extract_from_open_graph(self, article_url: str) -> Optional[Dict]:
        """Extract image from Open Graph meta tags."""
        if not BS4_AVAILABLE:
            return None
        
        try:
            logger.debug(f"Fetching Open Graph data from: {article_url}")
            
            # Add timeout and reasonable headers
            response = self.session.get(article_url, timeout=10, allow_redirects=True)
            response.raise_for_status()
            
            # Parse HTML
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Try Open Graph image first
            og_image = soup.find('meta', property='og:image')
            if og_image and og_image.get('content'):
                url = self._resolve_url(og_image['content'], article_url)
                if url and self._is_valid_image_url(url):
                    return {'url': url, 'type': 'og_image'}
            
            # Try Twitter card image
            twitter_image = soup.find('meta', attrs={'name': 'twitter:image'})
            if twitter_image and twitter_image.get('content'):
                url = self._resolve_url(twitter_image['content'], article_url)
                if url and self._is_valid_image_url(url):
                    return {'url': url, 'type': 'twitter_image'}
            
            # Try other common meta tags
            for meta_name in ['twitter:image:src', 'image', 'thumbnail']:
                meta_tag = soup.find('meta', attrs={'name': meta_name})
                if meta_tag and meta_tag.get('content'):
                    url = self._resolve_url(meta_tag['content'], article_url)
                    if url and self._is_valid_image_url(url):
                        return {'url': url, 'type': f'meta_{meta_name}'}
            
            # Try to find featured image from article content
            article_content = soup.find('article') or soup.find('main') or soup.find('div', class_='content')
            if article_content:
                img_tags = article_content.find_all('img')[:3]  # Check first 3 images
                for img in img_tags:
                    src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
                    if src:
                        url = self._resolve_url(src, article_url)
                        if url and self._is_valid_image_url(url):
                            # Check if this looks like a content image (not ad/icon)
                            width = img.get('width')
                            height = img.get('height')
                            if width and height:
                                try:
                                    w, h = int(width), int(height)
                                    if w >= 200 and h >= 150:  # Reasonable content image size
                                        return {'url': url, 'type': 'article_content'}
                                except:
                                    pass
                            else:
                                # No size info, assume it's a content image
                                return {'url': url, 'type': 'article_content'}
            
            # Fallback: look for any reasonably-sized image in the page
            all_imgs = soup.find_all('img')
            for img in all_imgs:
                src = img.get('src') or img.get('data-src')
                if src:
                    url = self._resolve_url(src, article_url)
                    if url and self._is_valid_image_url(url):
                        # Skip common non-content images
                        if any(skip in url.lower() for skip in ['logo', 'icon', 'avatar', 'pixel', 'tracking']):
                            continue
                        return {'url': url, 'type': 'page_image'}
            
        except Exception as e:
            logger.debug(f"Error extracting Open Graph image from {article_url}: {e}")
        
        return None
    
    def _get_stock_image_fallback(self) -> Optional[Dict]:
        """Get a random stock image as fallback."""
        try:
            stock_image = self.db_manager.get_random_stock_image()
            if stock_image:
                # Convert database path to full path
                full_path = self.stock_images_dir / stock_image['image_path']
                if full_path.exists():
                    return {
                        'url': str(full_path),
                        'type': 'stock_fallback',
                        'path': str(full_path),
                        'width': stock_image.get('width'),
                        'height': stock_image.get('height'),
                        'size': stock_image.get('file_size')
                    }
        except Exception as e:
            logger.debug(f"Error getting stock image fallback: {e}")
        
        return None
    
    def download_and_cache_image(self, image_url: str, article_id: int) -> Optional[Dict]:
        """Download image and cache it locally."""
        try:
            logger.debug(f"Downloading image from: {image_url}")
            
            # Generate cache filename
            url_hash = hashlib.md5(image_url.encode()).hexdigest()
            file_extension = self._get_file_extension(image_url)
            cache_filename = f"article_{article_id}_{url_hash}{file_extension}"
            cache_path = self.cached_images_dir / cache_filename
            
            # Skip if already cached
            if cache_path.exists():
                logger.debug(f"Image already cached: {cache_path}")
                return self._get_image_info(cache_path)
            
            # Download image
            response = self.session.get(image_url, timeout=15, stream=True)
            response.raise_for_status()
            
            # Check content type
            content_type = response.headers.get('content-type', '')
            if not content_type.startswith('image/'):
                logger.debug(f"Invalid content type: {content_type}")
                return None
            
            # Check file size
            content_length = response.headers.get('content-length')
            if content_length and int(content_length) > self.max_download_size:
                logger.debug(f"Image too large: {content_length} bytes")
                return None
            
            # Download and save
            total_size = 0
            with open(cache_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        total_size += len(chunk)
                        if total_size > self.max_download_size:
                            cache_path.unlink()  # Delete partial file
                            logger.debug(f"Image too large during download: {total_size} bytes")
                            return None
                        f.write(chunk)
            
            # Get image info and optimize if needed
            image_info = self._get_image_info(cache_path)
            if image_info:
                # Optimize for email if needed
                if image_info.get('size', 0) > self.target_email_size:
                    optimized_info = self._optimize_for_email(cache_path)
                    if optimized_info:
                        image_info.update(optimized_info)
                
                logger.info(f"Successfully cached image: {cache_path} ({image_info.get('size', 0)} bytes)")
                return image_info
            
        except Exception as e:
            logger.error(f"Error downloading and caching image {image_url}: {e}")
            # Clean up partial file
            if 'cache_path' in locals() and cache_path.exists():
                try:
                    cache_path.unlink()
                except:
                    pass
        
        return None
    
    def _get_image_info(self, image_path: Path) -> Optional[Dict]:
        """Get information about an image file."""
        try:
            if not image_path.exists():
                return None
            
            file_size = image_path.stat().st_size
            
            # Get image dimensions if Pillow is available
            width, height = None, None
            if PILLOW_AVAILABLE:
                try:
                    with Image.open(image_path) as img:
                        width, height = img.size
                except Exception as e:
                    logger.debug(f"Could not get image dimensions: {e}")
            
            return {
                'path': str(image_path),
                'relative_path': str(image_path.relative_to(self.base_images_dir)),
                'size': file_size,
                'width': width,
                'height': height
            }
        except Exception as e:
            logger.debug(f"Error getting image info: {e}")
            return None
    
    def _optimize_for_email(self, image_path: Path) -> Optional[Dict]:
        """Optimize image for email delivery (target: ≤150KB)."""
        if not PILLOW_AVAILABLE:
            return None
        
        try:
            # Create optimized filename
            optimized_path = image_path.with_suffix('.optimized' + image_path.suffix)
            
            with Image.open(image_path) as img:
                # Convert to RGB if necessary
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                
                # Start with original size
                current_img = img.copy()
                quality = 85
                max_dimension = 800
                
                # Try different optimization levels
                for attempt in range(5):
                    # Resize if needed
                    if current_img.width > max_dimension or current_img.height > max_dimension:
                        current_img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
                    
                    # Save with current quality
                    current_img.save(optimized_path, 'JPEG', quality=quality, optimize=True)
                    
                    # Check file size
                    file_size = optimized_path.stat().st_size
                    if file_size <= self.target_email_size:
                        # Replace original with optimized version
                        optimized_path.replace(image_path)
                        
                        return {
                            'size': file_size,
                            'width': current_img.width,
                            'height': current_img.height,
                            'optimized': True
                        }
                    
                    # Adjust parameters for next attempt
                    quality -= 15
                    max_dimension = int(max_dimension * 0.9)
                    
                    if quality < 30:
                        break
                
                # If we couldn't optimize enough, keep original
                if optimized_path.exists():
                    optimized_path.unlink()
                
        except Exception as e:
            logger.debug(f"Error optimizing image: {e}")
            if 'optimized_path' in locals() and optimized_path.exists():
                try:
                    optimized_path.unlink()
                except:
                    pass
        
        return None
    
    def _is_valid_image_url(self, url: str) -> bool:
        """Check if URL appears to be a valid image."""
        if not url:
            return False
        
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return False
            
            # Check file extension
            path = parsed.path.lower()
            return any(path.endswith(ext) for ext in self.supported_formats)
        except:
            return False
    
    def _get_file_extension(self, url: str) -> str:
        """Get file extension from URL, defaulting to .jpg."""
        try:
            parsed = urlparse(url)
            path = parsed.path.lower()
            
            for ext in self.supported_formats:
                if path.endswith(ext):
                    return ext
            
            # Try to guess from content type
            mime_type, _ = mimetypes.guess_type(url)
            if mime_type:
                ext = mimetypes.guess_extension(mime_type)
                if ext and ext.lower() in self.supported_formats:
                    return ext.lower()
        except:
            pass
        
        return '.jpg'  # Default
    
    def _resolve_url(self, url: str, base_url: str) -> str:
        """Resolve relative URLs to absolute URLs."""
        try:
            return urljoin(base_url, url)
        except:
            return url
    
    def setup_default_stock_images(self):
        """Set up default stock images if none exist."""
        try:
            # Check if we have any stock images
            existing_images = self.db_manager.get_all_stock_images()
            if existing_images:
                logger.info(f"Found {len(existing_images)} existing stock images")
                return
            
            # Create some default placeholder images if Pillow is available
            if PILLOW_AVAILABLE:
                self._create_default_placeholders()
            else:
                logger.warning("Pillow not available. Cannot create default stock images.")
                logger.info("Please add stock images manually to the images/stock directory")
        
        except Exception as e:
            logger.error(f"Error setting up default stock images: {e}")
    
    def _create_default_placeholders(self):
        """Create default placeholder images."""
        try:
            from PIL import Image, ImageDraw, ImageFont
            
            # Default colors for different categories
            colors = [
                '#3498db',  # Blue
                '#e74c3c',  # Red
                '#2ecc71',  # Green
                '#f39c12',  # Orange
                '#9b59b6',  # Purple
                '#1abc9c',  # Turquoise
                '#34495e',  # Dark gray
                '#e67e22',  # Dark orange
                '#16a085',  # Dark turquoise
                '#8e44ad'   # Dark purple
            ]
            
            for i, color in enumerate(colors):
                # Create a simple colored rectangle with text
                width, height = 400, 250
                img = Image.new('RGB', (width, height), color)
                draw = ImageDraw.Draw(img)
                
                # Add text
                text = f"News Image {i+1}"
                
                # Try to use a reasonable font size
                try:
                    font_size = 24
                    # Use default font
                    bbox = draw.textbbox((0, 0), text)
                    text_width = bbox[2] - bbox[0]
                    text_height = bbox[3] - bbox[1]
                except:
                    text_width, text_height = 100, 20  # Fallback
                
                # Center the text
                x = (width - text_width) // 2
                y = (height - text_height) // 2
                
                # Add a semi-transparent overlay
                overlay = Image.new('RGBA', (width, height), (0, 0, 0, 100))
                img.paste(overlay, (0, 0), overlay)
                
                # Draw text
                draw.text((x, y), text, fill='white')
                
                # Save image
                filename = f"placeholder_{i+1:02d}.jpg"
                file_path = self.stock_images_dir / filename
                img.save(file_path, 'JPEG', quality=80)
                
                # Add to database
                self.db_manager.add_stock_image(
                    image_path=filename,
                    image_name=f"Placeholder {i+1}",
                    category=None,
                    image_type='general',
                    file_size=file_path.stat().st_size,
                    width=width,
                    height=height
                )
                
                logger.info(f"Created stock image: {filename}")
            
            logger.info(f"Created {len(colors)} default stock images")
        
        except Exception as e:
            logger.error(f"Error creating default placeholders: {e}")
    
    def clean_old_cached_images(self, days_old: int = 7) -> int:
        """Clean up old cached images."""
        try:
            from datetime import datetime, timedelta
            
            cutoff_time = datetime.now() - timedelta(days=days_old)
            deleted_count = 0
            
            for image_path in self.cached_images_dir.glob('*'):
                if image_path.is_file():
                    # Check file modification time
                    mod_time = datetime.fromtimestamp(image_path.stat().st_mtime)
                    if mod_time < cutoff_time:
                        try:
                            image_path.unlink()
                            deleted_count += 1
                            logger.debug(f"Deleted old cached image: {image_path.name}")
                        except Exception as e:
                            logger.warning(f"Could not delete {image_path}: {e}")
            
            logger.info(f"Cleaned up {deleted_count} old cached images")
            return deleted_count
        
        except Exception as e:
            logger.error(f"Error cleaning old cached images: {e}")
            return 0
    
    def get_cache_stats(self) -> Dict:
        """Get statistics about cached images."""
        try:
            cached_files = list(self.cached_images_dir.glob('*'))
            stock_files = list(self.stock_images_dir.glob('*'))
            
            cached_size = sum(f.stat().st_size for f in cached_files if f.is_file())
            stock_size = sum(f.stat().st_size for f in stock_files if f.is_file())
            
            return {
                'cached_count': len([f for f in cached_files if f.is_file()]),
                'stock_count': len([f for f in stock_files if f.is_file()]),
                'cached_size_mb': round(cached_size / (1024 * 1024), 2),
                'stock_size_mb': round(stock_size / (1024 * 1024), 2),
                'total_size_mb': round((cached_size + stock_size) / (1024 * 1024), 2)
            }
        
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {}