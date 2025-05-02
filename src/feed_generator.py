"""
Feed generator for creating Atom feeds from scraped articles.
"""
import os
from datetime import datetime
from typing import Dict, List, Optional

from feedgen.feed import FeedGenerator


class AtomFeedGenerator:
    """Generator for Atom feeds from Anthropic articles."""
    
    def __init__(self, output_dir: str = "."):
        """Initialize with output directory."""
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def generate_feed(
        self, 
        articles: List[Dict], 
        feed_id: str = "anthropic-feed",
        title: str = "Anthropic News and Research",
        author: str = "Anthropic Feed Generator",
        feed_url: str = "https://kelp.github.io/llm-news/feed.atom"
    ) -> None:
        """Generate an Atom feed from the articles and save it to a file."""
        # Create feed generator
        fg = FeedGenerator()
        fg.id(feed_id)
        fg.title(title)
        fg.author({"name": author})
        fg.link(href=feed_url, rel="self")
        fg.language("en")
        
        # Add last updated timestamp
        now = datetime.now().isoformat()
        fg.updated(now)
        
        # Add entries
        for article in articles:
            entry = fg.add_entry()
            
            # Set required fields
            entry.id(article.get("url", f"anthropic-article-{hash(article['title'])}"))
            entry.title(article.get("title", "Untitled Article"))
            
            # Parse and set date
            pub_date = article.get("date")
            if pub_date:
                try:
                    if isinstance(pub_date, str) and "T" in pub_date:
                        # It's already in ISO format
                        entry.updated(pub_date)
                        entry.published(pub_date)
                    else:
                        # Convert to ISO format if needed
                        dt = datetime.fromisoformat(pub_date)
                        entry.updated(dt.isoformat())
                        entry.published(dt.isoformat())
                except (ValueError, TypeError):
                    # Fallback to current time
                    entry.updated(now)
                    entry.published(now)
            else:
                entry.updated(now)
                entry.published(now)
            
            # Set link
            entry.link(href=article.get("url", ""), rel="alternate")
            
            # Set content
            content = f"<p>Source: {article.get('source', 'Unknown')}</p>"
            if "summary" in article:
                content += f"<p>{article['summary']}</p>"
            entry.content(content=content, type="html")
            
            # Set source category
            source = article.get("source", "")
            if source:
                entry.category(term=source, label=source.capitalize())
        
        # Generate the feed
        atom_feed = fg.atom_str(pretty=True)
        
        # Save to file
        output_path = os.path.join(self.output_dir, "feed.atom")
        with open(output_path, "wb") as f:
            f.write(atom_feed)
        
        # Also save as XML for browsers
        output_path_xml = os.path.join(self.output_dir, "feed.xml")
        with open(output_path_xml, "wb") as f:
            f.write(atom_feed)
            
        # Generate JSON feed as well for compatibility
        json_feed = fg.json_str(pretty=True)
        output_path_json = os.path.join(self.output_dir, "feed.json")
        with open(output_path_json, "wb") as f:
            f.write(json_feed)


if __name__ == "__main__":
    # Test feed generation
    from scraper import AnthropicScraper
    
    scraper = AnthropicScraper()
    articles = scraper.load_from_cache()
    
    if not articles:
        articles = scraper.scrape_all()
    
    generator = AtomFeedGenerator()
    generator.generate_feed(articles)