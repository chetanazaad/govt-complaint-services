import re

DISTRICT_MAPPING = {
    "lko": "Lucknow",
    "jpr": "Jaipur",
    "del": "Delhi"
}

def normalize_phone(phone: str) -> str:
    """Clean phone number: keep only digits, optionally prepend +91."""
    digits = re.sub(r'\D', '', phone)
    
    # If 12 digits and starts with 91
    if len(digits) == 12 and digits.startswith('91'):
        return f"+{digits}"
    # If 10 digits
    elif len(digits) == 10:
        return f"+91{digits}"
    elif len(digits) == 11 and digits.startswith('0'):
        return f"+91{digits[1:]}"
        
    return phone # fallback

def normalize_contacts(phones: list, emails: list) -> dict:
    """Clean and deduplicate phones and emails."""
    clean_phones = list(set([normalize_phone(p) for p in phones]))
    clean_emails = list(set([str(e).lower() for e in emails]))
    
    return {
        "phones": clean_phones,
        "emails": clean_emails
    }

def normalize_district(raw_district: str) -> str:
    """Map abbreviated or raw district names to standard names."""
    if not raw_district:
        return "Unknown"
    
    lower_raw = raw_district.strip().lower()
    return DISTRICT_MAPPING.get(lower_raw, raw_district.strip().title())
