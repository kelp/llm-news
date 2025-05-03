"""
Scraper module for extracting articles from Anthropic's website.
"""
import json
import logging
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

class AnthropicScraper:
    """Scraper for Anthropic's news and research pages."""
    
    NEWS_URL = "https://www.anthropic.com/news"
    RESEARCH_URL = "https://www.anthropic.com/research"
    
    def __init__(self, cache_dir: str = "data"):
        """Initialize the scraper with cache directory."""
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        
    def fetch_page(self, url: str) -> Optional[str]:
        """Fetch HTML content from a URL."""
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; LLM-News/1.0; +https://github.com/kelp/llm-news)"
            }
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logger.error(f"Error fetching {url}: {e}")
            return None
    
    def parse_news_page(self, html: str) -> List[Dict]:
        """Parse the news page HTML and extract articles."""
        articles = []
        soup = BeautifulSoup(html, "lxml")
        
        # Find all news article elements
        article_elements = soup.select("a[href^='/news/']")
        
        for article in article_elements:
            # Skip duplicate articles
            if any(a.get("href") == article.get("href") for a in articles):
                continue
                
            title_element = article.select_one("h3, h2")
            date_element = article.select_one("time")
            
            if not title_element:
                continue
                
            # Extract article data
            title = title_element.get_text(strip=True)
            url = f"https://www.anthropic.com{article.get('href')}"
            date_str = date_element.get_text(strip=True) if date_element else ""
            date = self._parse_date(date_str)
            
            articles.append({
                "title": title,
                "url": url,
                "date": date,
                "source": "news"
            })
            
        return articles
    
    def parse_research_page(self, html: str) -> List[Dict]:
        """Parse the research page HTML and extract articles."""
        articles = []
        soup = BeautifulSoup(html, "lxml")
        
        # Direct approach - look for specific research publication cards
        research_cards = soup.select("div.publication-card, div.research-card, div[class*='publication'], div[class*='research']")
        
        # Also look for sections that might contain research papers
        if not research_cards:
            # Try to find any section with "publication" in its ID or class
            research_cards = soup.select("[id*='publication'], [class*='publication'], [id*='paper'], [class*='paper']")
        
        if research_cards:
            for card in research_cards:
                # Extract title, link, and date from each card
                title_element = card.select_one("h2, h3, h4, strong, b")
                link_element = card.select_one("a[href]")
                date_element = card.select_one("time, span[class*='date'], div[class*='date']")
                
                if title_element and link_element:
                    title = title_element.get_text(strip=True)
                    url = link_element.get("href")
                    
                    # Make sure it's a full URL
                    if url and url.startswith("/"):
                        url = f"https://www.anthropic.com{url}"
                    
                    # Get date if available
                    date_str = date_element.get_text(strip=True) if date_element else ""
                    if not date_str:
                        # Look for year patterns
                        text = card.get_text()
                        import re
                        year_match = re.search(r'\b20\d\d\b', text)
                        if year_match:
                            date_str = year_match.group(0)
                    
                    date = self._parse_date(date_str)
                    
                    # Only add if we don't already have this exact URL and it's a valid URL
                    if url and not any(a.get("url") == url for a in articles):
                        articles.append({
                            "title": title,
                            "url": url,
                            "date": date,
                            "source": "research"
                        })
        
        # Fallback: Since Anthropic often uses external sites for research papers,
        # look for links to arxiv.org, transformer-circuits, and other common research sites
        research_links = soup.select("a[href*='arxiv.org'], a[href*='transformer-circuits'], a[href*='.pdf'], a[href*='paper']")
        
        if research_links:
            for link in research_links:
                url = link.get("href")
                if not url:
                    continue
                
                # Skip navigation links, privacy policies, etc.
                if any(x in url.lower() for x in ["privacy", "terms", "contact", "about", "login", "sign", "home"]):
                    continue
                
                # Extract title - either from link text or from nearby heading
                title = link.get_text(strip=True)
                
                # If link text seems too short or generic, look for a better title nearby
                if not title or len(title) < 15 or title.lower() in ["read paper", "pdf", "arxiv", "link", "read more"]:
                    # Look for parent elements with better text
                    parent = link.parent
                    for _ in range(3):  # Look up to 3 levels up
                        if parent:
                            # Try to find a nearby heading first
                            nearby_heading = parent.find("h2") or parent.find("h3") or parent.find("h4")
                            if nearby_heading:
                                title = nearby_heading.get_text(strip=True)
                                break
                            
                            # Or use the parent's text if it's substantial
                            parent_text = parent.get_text(strip=True)
                            if len(parent_text) > 20 and len(parent_text) < 200:
                                title = parent_text
                                break
                                
                            parent = parent.parent
                
                # If we still don't have a good title, construct one from the URL
                if not title or len(title) < 10:
                    if "arxiv" in url:
                        # Extract arxiv ID
                        arxiv_match = re.search(r'(\d+\.\d+)', url)
                        if arxiv_match:
                            title = f"Anthropic Research Paper (arXiv:{arxiv_match.group(1)})"
                    else:
                        # Use URL path as title
                        from urllib.parse import urlparse
                        path = urlparse(url).path
                        if path:
                            title_parts = path.strip('/').split('/')[-1].replace('-', ' ').replace('_', ' ')
                            if title_parts:
                                title = f"Anthropic Research: {title_parts.title()}"
                            else:
                                title = "Anthropic Research Paper"
                
                # Try to find a date
                date_str = ""
                for nearby in [link.parent, link.parent.parent]:
                    if nearby:
                        # Look for date elements
                        date_element = nearby.select_one("time, span[class*='date'], div[class*='date']")
                        if date_element:
                            date_str = date_element.get_text(strip=True)
                            break
                
                # If no date found, try to extract from text
                if not date_str:
                    # Look for dates in the text around the link
                    context_text = link.parent.get_text() if link.parent else ""
                    import re
                    # Look for year or full date patterns
                    year_match = re.search(r'\b20\d\d\b', context_text)
                    if year_match:
                        date_str = year_match.group(0)
                    
                date = self._parse_date(date_str)
                
                # Only add if we don't already have this exact URL and the title is meaningful
                if title and url and not any(a.get("url") == url for a in articles):
                    articles.append({
                        "title": title,
                        "url": url,
                        "date": date,
                        "source": "research"
                    })
        
        # Last resort: Look for any div that mentions "research" and has links
        if not articles:
            research_sections = soup.select("div:contains('Research'), div:contains('Publications'), section:contains('Research')")
            for section in research_sections:
                links = section.select("a[href]")
                for link in links:
                    url = link.get("href")
                    if not url:
                        continue
                        
                    # Skip internal navigation links
                    if url.startswith("#") or any(x in url.lower() for x in ["privacy", "terms", "contact", "about"]):
                        continue
                        
                    # Make sure it's a full URL
                    if url.startswith("/"):
                        url = f"https://www.anthropic.com{url}"
                        
                    # Extract title
                    title = link.get_text(strip=True)
                    if not title or len(title) < 10:
                        continue
                        
                    # Try to find date
                    date = self._parse_date("")  # Default to current date
                    
                    # Only add if we don't already have this exact URL
                    if not any(a.get("url") == url for a in articles):
                        articles.append({
                            "title": title,
                            "url": url,
                            "date": date,
                            "source": "research"
                        })
        
        return articles
    
    def _parse_date(self, date_str: str) -> str:
        """Parse date from various formats to ISO format with timezone."""
        if not date_str:
            return datetime.now(timezone.utc).isoformat()
            
        try:
            # Handle various date formats
            formats = ["%B %d, %Y", "%b %d, %Y", "%Y-%m-%d"]
            
            for fmt in formats:
                try:
                    dt = datetime.strptime(date_str, fmt)
                    # Add UTC timezone
                    dt = dt.replace(tzinfo=timezone.utc)
                    return dt.isoformat()
                except ValueError:
                    continue
                    
            # If no format matches, return current time with timezone
            return datetime.now(timezone.utc).isoformat()
        except Exception as e:
            logger.error(f"Error parsing date '{date_str}': {e}")
            return datetime.now(timezone.utc).isoformat()
    
    def scrape_all(self) -> List[Dict]:
        """Scrape both news and research pages and combine results."""
        all_articles = []
        
        # Scrape news page
        news_html = self.fetch_page(self.NEWS_URL)
        if news_html:
            news_articles = self.parse_news_page(news_html)
            all_articles.extend(news_articles)
            logger.info(f"Scraped {len(news_articles)} news articles")
        
        # Scrape research page
        research_html = self.fetch_page(self.RESEARCH_URL)
        if research_html:
            research_articles = self.parse_research_page(research_html)
            all_articles.extend(research_articles)
            logger.info(f"Scraped {len(research_articles)} research articles")
        
        # Sort by date, most recent first
        all_articles.sort(key=lambda x: x.get("date", ""), reverse=True)
        
        # Save to cache
        self._save_to_cache(all_articles)
        
        return all_articles
    
    def _save_to_cache(self, articles: List[Dict]) -> None:
        """Save scraped articles to cache file."""
        cache_file = os.path.join(self.cache_dir, "anthropic_articles.json")
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(articles, f, indent=2)
            logger.info(f"Saved {len(articles)} articles to cache")
        except IOError as e:
            logger.error(f"Error saving to cache: {e}")
    
    def load_from_cache(self) -> List[Dict]:
        """Load articles from cache if available."""
        cache_file = os.path.join(self.cache_dir, "anthropic_articles.json")
        try:
            if os.path.exists(cache_file):
                with open(cache_file, "r", encoding="utf-8") as f:
                    articles = json.load(f)
                logger.info(f"Loaded {len(articles)} articles from cache")
                return articles
        except (IOError, json.JSONDecodeError) as e:
            logger.error(f"Error loading from cache: {e}")
        
        return []


if __name__ == "__main__":
    # Test the scraper
    scraper = AnthropicScraper()
    articles = scraper.scrape_all()
    print(f"Scraped {len(articles)} total articles")
    for article in articles[:5]:
        print(f"{article['title']} - {article['date']} - {article['source']}")