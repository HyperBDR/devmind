"""
Common content filtering utilities.

This module provides shared content filtering functions used across
different content collection systems (Google News, GitHub Trending, etc.).
"""

import logging
import re
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def contains_filter_words(
    text: str,
    filter_words: List[str]
) -> Tuple[bool, Optional[str]]:
    """
    Check if text contains any filtered words.

    This function uses improved word boundary matching to avoid false
    positives from hyphenated technical terms (e.g., "naked-POC" should
    not match "naked").

    Args:
        text: Text content to check
        filter_words: List of words/phrases to filter out

    Returns:
        tuple: (contains_filter_word, matched_word)
            - contains_filter_word: True if text contains a filtered word
            - matched_word: The matched filter word, or None if no match
    """
    if not filter_words or not text:
        return False, None

    text_lower = text.lower()

    for word in filter_words:
        if not word:
            continue

        word_lower = word.lower()

        # Use word boundary matching for better accuracy
        # For multi-word phrases, use simple substring match
        if " " in word:
            # Multi-word phrase: use substring match
            pattern = re.escape(word_lower)
        else:
            # Single word: use word boundary with improved logic
            # This ensures we don't match words that are part of hyphenated
            # technical terms (e.g., "naked-POC" should not match "naked")
            # The pattern matches the word only if:
            # 1. It's at word boundary
            # 2. It's NOT followed by hyphen and then a letter
            #    (technical terms)
            escaped_word = re.escape(word_lower)
            # Negative lookahead: exclude hyphen followed by letter
            # (case-insensitive)
            # This prevents matching "naked" in "naked-POC" but still
            # matches "naked" as standalone word
            # Pattern explanation:
            # - \b: word boundary before the word
            # - (?!-[a-zA-Z]): negative lookahead - not followed by
            #   hyphen+letter
            # - (?=\W|$): must be followed by non-word char or end of string
            pattern = r'\b' + escaped_word + r'(?!-[a-zA-Z])' + r'(?=\W|$)'

        if re.search(pattern, text_lower, re.IGNORECASE):
            return True, word

    return False, None


def check_fields(
    fields: Dict[str, str],
    filter_words: List[str],
    item_name: str = ""
) -> Tuple[bool, str]:
    """
    Check if any of the provided fields contains filtered words.

    This function checks multiple text fields and returns detailed information
    about which fields contain filtered words.

    Args:
        fields: Dictionary mapping field names to their text content
        filter_words: List of words/phrases to filter out
        item_name: Optional name of the item being checked (for logging)

    Returns:
        tuple: (passes_filter, failure_reason)
            - passes_filter: True if all fields pass the filter
            - failure_reason: Detailed reason if filter fails,
              empty string if passes
    """
    if not filter_words:
        return True, ""

    if item_name:
        logger.debug(
            f"[Content Filter] Checking '{item_name}' with "
            f"{len(filter_words)} filter words"
        )

    # Check each field separately to identify where keyword appears
    found_fields = []
    matched_word = None

    for field_name, field_text in fields.items():
        if not field_text:
            continue

        contains_word, matched = contains_filter_words(
            field_text, filter_words
        )
        if contains_word:
            found_fields.append(field_name)
            if not matched_word:
                matched_word = matched

    if found_fields:
        location_str = ", ".join(found_fields)
        reason = (
            f"Contains filtered word: '{matched_word}' "
            f"(found in: {location_str})"
        )
        if item_name:
            logger.info(
                f"[Content Filter] '{item_name}' filtered: {reason}"
            )
        return False, reason

    if item_name:
        logger.debug(
            f"[Content Filter] '{item_name}' passed content filter"
        )
    return True, ""
