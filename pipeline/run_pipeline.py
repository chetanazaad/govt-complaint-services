import json
from pathlib import Path

from scrapers.html_scraper import scrape_html
from scrapers.pdf_scraper import scrape_pdf
from extractors.contact_extractor import extract_contacts
from data_transformers.normalizer import normalize_contacts, normalize_district
from mappers.complaint_mapper import map_data_to_complaint

import sys
import asyncio
import os
# Ensure we can load from backend
sys.path.append(str(Path(__file__).resolve().parent.parent))
try:
    from backend.services.llm_service import extract_complaint_semantics
except ImportError as e:
    print(f"[Error] Could not import backend.services.llm_service: {e}")
    extract_complaint_semantics = None


# Define robust absolute paths using pathlib
BASE_DIR = Path(__file__).resolve().parent
URLS_FILE = BASE_DIR / "sources" / "urls.json"
OUTPUT_FILE = BASE_DIR / "output" / "complaints.json"

def run_pipeline():
    print("[Pipeline] Starting data collection pipeline...")
    
    # 1. Setup Phase
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not URLS_FILE.exists():
        print(f"[Pipeline] Error: Source file not found at {URLS_FILE}")
        return
        
    print(f"[Pipeline] Loading source URLs from {URLS_FILE.name}...")
    with open(URLS_FILE, "r", encoding="utf-8") as f:
        urls_data = json.load(f)
        
    results = []
    
    # 2. Processing Phase
    for item in urls_data:
        url = item.get("url")
        raw_district = item.get("district", "Unknown")
        print(f"\n────────────────────────────────────────")
        print(f"[Processing] {url}")
        
        # Scrape
        if url.lower().endswith(".pdf"):
            print("[Scraper] PDF detected. Extracting text...")
            text = scrape_pdf(url)
        else:
            print("[Scraper] HTML detected. Extracting text...")
            text = scrape_html(url)
            
        if not text:
            print("[Scraper] No text recovered or request failed. Skipping.")
            continue
            
        # Extract Semantic Data via LLM
        print("[LLM] Extracting semantics...")
        semantic_data = {"confidence": 0.0}
        if extract_complaint_semantics:
            semantic_data = asyncio.run(extract_complaint_semantics(text))
            
        print(f"[LLM] Confidence: {semantic_data['confidence']}")

        # Primary Hybrid Logic Branching
        if semantic_data["confidence"] < 0.6:
            print("[Fallback] Confidence low (<0.6). Resorting to rule-based processing...")
            
            # Extract
            print("[Extractor] Hunting for phone numbers and emails...")
            raw_contacts = extract_contacts(text)
            print(f"[Extractor] Found {len(raw_contacts['phones'])} phone(s) and {len(raw_contacts['emails'])} email(s).")
            
            # Normalize
            print("[Normalizer] Cleaning and standardizing contact forms...")
            district = normalize_district(raw_district)
            contacts = normalize_contacts(raw_contacts['phones'], raw_contacts['emails'])
            print(f"[Normalizer] Mapped to standard district: {district}")
            
            # Map & Format
            print("[Mapper] Formatting and inferring category...")
            raw_data = {
                "district": district,
                "contacts": contacts,
                "source": url
            }
            mapped_complaint = map_data_to_complaint(raw_data, text)
            print(f"[Mapper] Category mapped to: {mapped_complaint.get('category')}")
            
        else:
            print(f"[LLM] High confidence! Direct map. Category: {semantic_data.get('category')} | Problem: {semantic_data.get('problem')}")
            
            # Extract contacts still (for helpline extraction)
            raw_contacts = extract_contacts(text)
            contacts = normalize_contacts(raw_contacts['phones'], raw_contacts['emails'])
            
            # Resolve district (LLM priority > fallback)
            district = semantic_data.get("district")
            if not district:
                district = normalize_district(raw_district)
                
            raw_data = {
                "district": district,
                "contacts": contacts,
                "source": url
            }
            
            # Pass LLM category into mapper so it assigns correct escalations and departments seamlessly
            mapped_complaint = map_data_to_complaint(raw_data, semantic_data.get("category", ""))
            
            # Overwrite fields strictly to LLM output
            mapped_complaint["category"] = semantic_data.get("category", "Other")
            mapped_complaint["problem"] = semantic_data.get("problem", "Unknown Issue")
            mapped_complaint["district"] = district
            mapped_complaint["urgency"] = semantic_data.get("urgency", "low")
            mapped_complaint["language"] = semantic_data.get("language", "unknown")
            mapped_complaint["confidence"] = semantic_data.get("confidence", 0.0)
            
        # Store
        results.append(mapped_complaint)
        
    # 3. Output Phase
    print(f"\n────────────────────────────────────────")
    print(f"[Pipeline] Writing output to {OUTPUT_FILE.name}...")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
        
    print("[Pipeline] ✅ Execution completed successfully.")

if __name__ == "__main__":
    run_pipeline()
