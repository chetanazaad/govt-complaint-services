import re

def extract_contacts(text: str) -> dict:
    """Extract Indian phone numbers and emails using regex."""
    if not text:
        return {"phones": [], "emails": []}
        
    # Match Indian phone numbers: +91, 0, or plain 10 digits
    phone_pattern = re.compile(r'(?:(?:\+|0{0,2})91[\s-]?)?[6-9]\d{9}')
    # Match emails
    email_pattern = re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+')
    
    phones = phone_pattern.findall(text)
    emails = email_pattern.findall(text)
    
    return {
        "phones": phones,
        "emails": emails
    }
