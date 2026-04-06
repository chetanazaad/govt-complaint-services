"""Keyword-based complaint matcher using the local JSON data source."""

import json
import os
import logging
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Data Loading
# ──────────────────────────────────────────────

_complaints_data: list[dict] = []


def load_complaints_data() -> list[dict]:
    """Load complaints data from JSON file. Called once at startup."""
    global _complaints_data

    data_path = Path(__file__).parent.parent / "data" / "complaints.json"

    if not data_path.exists():
        logger.error("complaints.json not found at %s", data_path)
        raise FileNotFoundError(f"complaints.json not found at {data_path}")

    with open(data_path, "r", encoding="utf-8") as f:
        _complaints_data = json.load(f)

    logger.info("Loaded %d complaint entries from %s", len(_complaints_data), data_path)
    return _complaints_data


def get_complaints_data() -> list[dict]:
    """Return loaded complaints data."""
    if not _complaints_data:
        load_complaints_data()
    return _complaints_data


# ──────────────────────────────────────────────
# Keyword Matching (pre-LLM fallback)
# ──────────────────────────────────────────────

def keyword_match(query: str) -> Optional[dict]:
    """
    Attempt to match user query against keywords in the complaint database.
    Returns {"category", "problem", "confidence", "matched_keywords"} or None.
    """
    data = get_complaints_data()
    query_lower = query.lower().strip()
    query_words = set(query_lower.split())

    best_match = None
    best_score = 0
    best_matched_keywords = []

    for entry in data:
        keywords = [kw.lower() for kw in entry.get("keywords", [])]
        score = 0
        matched_keywords = []

        for keyword in keywords:
            keyword_parts = keyword.split()

            # Exact phrase match (highest score)
            if keyword in query_lower:
                score += len(keyword_parts) * 3
                matched_keywords.append(keyword)

            # Individual word matches
            else:
                matching_words = sum(1 for w in keyword_parts if w in query_words)
                if matching_words > 0:
                    score += matching_words
                    matched_keywords.append(keyword)

        if score > best_score:
            best_score = score
            best_match = entry
            best_matched_keywords = matched_keywords

    if best_match and best_score >= 2:
        confidence = min(round(best_score / 10, 2), 0.95)
        logger.info(
            "Keyword match found: %s / %s (score=%d, confidence=%.2f, keywords=%s)",
            best_match["category"],
            best_match["problem"],
            best_score,
            confidence,
            best_matched_keywords,
        )
        return {
            "category": best_match["category"],
            "problem": best_match["problem"],
            "confidence": confidence,
            "matched_keywords": best_matched_keywords,
        }

    logger.info("No keyword match found for query: %s", query[:80])
    return None


# ──────────────────────────────────────────────
# Complaint Resolution (exact match from JSON)
# ──────────────────────────────────────────────

def match_complaint(category: str, problem: str, district: str = None) -> Optional[dict]:
    """
    Find complaint entry by category, problem, and optional district.
    Priority: district-specific → General fallback.
    Returns full complaint data or None.
    """
    data = get_complaints_data()
    cat_lower = category.lower().strip()
    prob_lower = problem.lower().strip()
    dist_lower = district.lower().strip() if district else None

    general_match = None
    district_match = None

    for entry in data:
        entry_dist = entry.get("district", "General").lower()

        if (
            entry["category"].lower() == cat_lower
            and entry["problem"].lower() == prob_lower
        ):
            result = {
                "category": entry["category"],
                "problem": entry["problem"],
                "district": entry.get("district", "General"),
                "primary_action": entry["primary_action"],
                "escalation": entry["escalation"],
                "rti": entry["rti"],
            }

            if entry_dist == "general":
                general_match = result
            elif dist_lower and entry_dist == dist_lower:
                district_match = result

    # Prefer district-specific, fall back to general
    if district_match:
        logger.info("District match found: %s / %s / %s", category, problem, district)
        return district_match
    if general_match:
        logger.info("General match found: %s / %s (district '%s' not available)", category, problem, district or "none")
        return general_match

    # Fuzzy fallback: match category only, pick best problem
    category_entries = [e for e in data if e["category"].lower() == cat_lower]
    # Prefer district-specific fuzzy match
    for entry in category_entries:
        entry_dist = entry.get("district", "General").lower()
        if prob_lower in entry["problem"].lower() or entry["problem"].lower() in prob_lower:
            if dist_lower and entry_dist == dist_lower:
                logger.info("Fuzzy district match: %s / %s / %s", entry["category"], entry["problem"], district)
                return {
                    "category": entry["category"],
                    "problem": entry["problem"],
                    "district": entry.get("district", "General"),
                    "primary_action": entry["primary_action"],
                    "escalation": entry["escalation"],
                    "rti": entry["rti"],
                }
    # Fuzzy general fallback
    for entry in category_entries:
        entry_dist = entry.get("district", "General").lower()
        if (prob_lower in entry["problem"].lower() or entry["problem"].lower() in prob_lower) and entry_dist == "general":
            logger.info("Fuzzy general match: %s / %s", entry["category"], entry["problem"])
            return {
                "category": entry["category"],
                "problem": entry["problem"],
                "district": entry.get("district", "General"),
                "primary_action": entry["primary_action"],
                "escalation": entry["escalation"],
                "rti": entry["rti"],
            }

    logger.warning("No complaint match for: %s / %s / %s", category, problem, district)
    return None


def get_available_categories() -> list[dict]:
    """Return a summary of all available categories and problems."""
    data = get_complaints_data()
    result = []
    seen = set()

    for entry in data:
        key = (entry["category"], entry["problem"])
        if key not in seen:
            seen.add(key)
            result.append({"category": entry["category"], "problem": entry["problem"]})

    return result


def get_available_districts() -> list[str]:
    """Return a sorted list of all districts that have specific data."""
    data = get_complaints_data()
    districts = set()

    for entry in data:
        dist = entry.get("district", "General")
        if dist != "General":
            districts.add(dist)

    return sorted(districts)
