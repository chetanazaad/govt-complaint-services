"""Utility helpers for input sanitization and validation."""

import re
import html
import logging

logger = logging.getLogger(__name__)

# Characters allowed in user queries
ALLOWED_PATTERN = re.compile(r"[^a-zA-Z0-9\s\.\,\!\?\-\'\"\/\(\)]")


def sanitize_input(text: str) -> str:
    """
    Sanitize user input to prevent injection attacks.
    - Strips HTML entities
    - Removes suspicious characters
    - Truncates to safe length
    """
    # Decode HTML entities
    text = html.unescape(text)

    # Remove HTML tags
    text = re.sub(r"<[^>]+>", "", text)

    # Remove control characters
    text = "".join(ch for ch in text if ord(ch) >= 32 or ch in "\n\t")

    # Remove potentially dangerous characters
    text = ALLOWED_PATTERN.sub("", text)

    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()

    # Truncate
    if len(text) > 500:
        text = text[:500]
        logger.warning("Input truncated to 500 characters")

    return text


def normalize_category(category: str) -> str:
    """Normalize category string to title case."""
    category = category.strip()
    mapping = {
        "electricity": "Electricity",
        "police": "Police",
        "land": "Land",
        "transport": "Transport",
        "water": "Water",
    }
    return mapping.get(category.lower(), category.title())


def normalize_problem(problem: str) -> str:
    """Normalize problem string to title case."""
    return problem.strip().title()
