import requests
from bs4 import BeautifulSoup

def scrape_html(url: str) -> str:
    """Scrape text content from an HTML page."""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")
        return soup.get_text(separator=" ", strip=True)
    except Exception as e:
        print(f"[HTML Scraper] Error scraping {url}: {e}")
        return ""
