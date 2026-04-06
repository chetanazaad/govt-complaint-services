import pdfplumber
import requests
import io

def scrape_pdf(url: str) -> str:
    """Download and extract text from a PDF."""
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        
        text = ""
        with pdfplumber.open(io.BytesIO(response.content)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + " "
        return text.strip()
    except Exception as e:
        print(f"[PDF Scraper] Error scraping {url}: {e}")
        return ""
