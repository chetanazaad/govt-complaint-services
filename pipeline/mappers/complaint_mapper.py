def map_data_to_complaint(extracted_data: dict, raw_text: str) -> dict:
    """Map extracted contacts and raw text into complaint-ready format."""
    text_lower = raw_text.lower() if raw_text else ""
    
    # Default values
    category = "Unknown"
    problem = "General Issue"
    department = "General Administration"
    escalation = ["Level 1 Officer", "Level 2 Officer"]
    
    # 1 & 2 & 4: Infer category, department, problem, and escalation using keywords
    if any(kw in text_lower for kw in ["electric", "power", "uppcl", "lesa", "substation"]):
        category = "Electricity"
        problem = "Power Issue"
        department = "UPPCL / Electricity Department"
        escalation = ["Junior Engineer", "SDO", "Executive Engineer"]
        
    elif any(kw in text_lower for kw in ["police", "sp", "station", "thana", "fir", "circle officer"]):
        category = "Police"
        problem = "Complaint Not Registered"
        department = "District Police"
        escalation = ["Station Officer", "Circle Officer", "SP"]
        
    elif any(kw in text_lower for kw in ["water", "jal", "nagar nigam", "jal nigam", "supply"]):
        category = "Water"
        problem = "Water Supply Issue"
        department = "Jal Nigam / Nagar Nigam"
        escalation = ["Junior Engineer", "Executive Engineer", "Municipal Commissioner"]
        
    elif any(kw in text_lower for kw in ["rto", "transport", "vehicle", "license"]):
        category = "Transport"
        problem = "Transport Issue"
        department = "RTO / Transport Department"
        escalation = ["ARTO", "RTO", "Transport Commissioner"]
        
    elif any(kw in text_lower for kw in ["tehsil", "revenue", "land", "registry", "lekhpal"]):
        category = "Land"
        problem = "Land Dispute"
        department = "Revenue Department"
        escalation = ["Tehsildar", "SDM", "District Magistrate"]
        
    # 3: Improve Primary Action
    phones = extracted_data.get("contacts", {}).get("phones", [])
    helpline = phones[0] if phones else ""
    
    primary_action = {
        "department": department,
        "helpline": helpline,
        "source": extracted_data.get("source", "")
    }
    
    # Store all numbers if multiple exist
    if len(phones) > 1:
        primary_action["all_helplines"] = phones
    
    # 5: Ensure Output Quality
    return {
        "category": category,
        "problem": problem,
        "district": extracted_data.get("district", "Unknown"),
        "primary_action": primary_action,
        "escalation": escalation,
        "rti": {
            "note": "File RTI if unresolved"
        }
    }

