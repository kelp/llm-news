# Anthropic News and Research Feed

An automated Atom feed generator for Anthropic's news and research pages.

## Features

- Scrapes [Anthropic's news](https://www.anthropic.com/news) and [research](https://www.anthropic.com/research) pages
- Generates an Atom feed updated every 4 hours via GitHub Actions
- Hosted on GitHub Pages for easy access
- Provides Atom, XML, and JSON feed formats
- Simple web interface to view recent articles

## Feed URLs

- Atom Feed: https://tcole.net/llm-news/feed.atom
- XML Feed: https://tcole.net/llm-news/feed.xml
- JSON Feed: https://tcole.net/llm-news/feed.json

## Local Development

### Prerequisites

- Python 3.8+
- pip (Python package manager)

### Setup

1. Clone the repository:
   ```
   git clone https://github.com/kelp/llm-news.git
   cd llm-news
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Run the feed generator:
   ```
   python src/main.py --output-dir ./ --cache-dir ./data
   ```

4. Open `index.html` in your browser to view the results

### Usage

```
python src/main.py [options]

Options:
  --output-dir DIR     Directory to save the generated feeds (default: .)
  --cache-dir DIR      Directory to store cached data (default: data)
  --force-refresh      Force refresh of all data (ignore HTTP caching)
  --check-updates      Use conditional HTTP requests to check for updates (default)
  --max-age SECONDS    Maximum age of cached data before forcing a check (default: 14400)
```

#### Refresh Strategies

- **Default Mode**: Uses conditional HTTP requests to check for updates if cache is older than max-age
- **Check Updates**: Always uses conditional requests regardless of cache age
- **Force Refresh**: Always performs a full scrape, ignoring all caching

## How It Works

1. The scraper uses conditional HTTP requests to check if Anthropic's pages have changed
2. If unchanged, it uses cached data; if changed, it scrapes the updated content
3. Article data (title, date, URL) is extracted and stored in a sophisticated cache
4. The feed generator creates standard Atom, XML, and JSON feeds
5. GitHub Actions runs this process hourly with smart caching and weekly full refreshes
6. The web interface displays recent articles by reading the JSON feed

### Smart Caching Mechanism

This project implements a sophisticated caching strategy to minimize bandwidth and processing:

- **HTTP Conditional Requests**: Uses If-Modified-Since and ETag headers to only download content when it's changed
- **Two-Level Cache**: Maintains both an HTTP metadata cache and a processed articles cache
- **Incremental Updates**: Only processes what's changed, preserving previously fetched data
- **Cache Age Awareness**: Automatically determines when to refresh based on cache age
- **Multiple Refresh Strategies**: Supports both lightweight checks and full refreshes

## Deployment

This project is designed to be deployed on GitHub Pages:

1. Fork this repository
2. Enable GitHub Pages in repository settings (Settings > Pages)
3. Select the `gh-pages` branch as the source
4. GitHub Actions will automatically:
   - Check for updates hourly using conditional requests (lightweight)
   - Perform a full refresh weekly to ensure complete data
   - Deploy the updated feeds to the `gh-pages` branch

## License

[MIT License](LICENSE)

## Disclaimer

This is an unofficial feed generator not affiliated with or endorsed by Anthropic. It is provided for convenience only.