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
        
        # Find all research article elements
        article_elements = soup.select("a[href^='/research/']")
        
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