"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os
import re

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


_SEARCH_STOPWORDS = {
    "a",
    "an",
    "and",
    "at",
    "for",
    "from",
    "i",
    "in",
    "is",
    "it",
    "looking",
    "mostly",
    "of",
    "on",
    "or",
    "out",
    "size",
    "the",
    "this",
    "to",
    "under",
    "want",
    "wear",
    "what",
    "with",
    "would",
    "you",
}


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform

    TODO:
        1. Load all listings with load_listings().
        2. Filter by max_price and size (if provided).
        3. Score each remaining listing by keyword overlap with `description`.
        4. Drop any listings with a score of 0 (no relevant matches).
        5. Sort by score, highest first, and return the listing dicts.

    Before writing code, fill in the Tool 1 section of planning.md.
    """
    listings = load_listings()
    query_tokens = [
        token
        for token in _tokenize(description or "")
        if token not in _SEARCH_STOPWORDS
    ]

    if not query_tokens:
        return []

    filtered_results: list[tuple[int, dict]] = []
    requested_size = size.lower() if size is not None else None

    for listing in listings:
        listing_price = listing.get("price")
        if max_price is not None and listing_price is not None and listing_price > max_price:
            continue

        if requested_size is not None:
            listing_size = str(listing.get("size", "")).lower()
            if requested_size not in listing_size and listing_size not in requested_size:
                continue

        searchable_parts = [
            str(listing.get("title", "")),
            str(listing.get("description", "")),
            str(listing.get("category", "")),
            " ".join(listing.get("style_tags", []) or []),
            " ".join(listing.get("colors", []) or []),
            str(listing.get("brand") or ""),
        ]
        searchable_tokens = set(_tokenize(" ".join(searchable_parts)))
        score = sum(1 for token in set(query_tokens) if token in searchable_tokens)

        if score == 0:
            continue

        filtered_results.append((score, listing))

    filtered_results.sort(key=lambda item: item[0], reverse=True)
    return [listing for score, listing in filtered_results]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If empty: call the LLM with a prompt for general styling ideas
           (what kinds of items pair well, what vibe it suits, etc.).
        3. If not empty: format the wardrobe items into a prompt and ask
           the LLM to suggest specific outfit combinations using the new item
           and named pieces from the wardrobe.
        4. Return the LLM's response as a string.

    Before writing code, fill in the Tool 2 section of planning.md.
    """
    items = wardrobe.get("items") if isinstance(wardrobe, dict) else None
    if not items:
        prompt = (
            "You are a styling assistant for a thrift shopping app.\n"
            "Give 1-2 concise styling ideas for this secondhand item when the user does not have a wardrobe on file.\n"
            "Focus on the item's vibe, what categories pair well with it, and a few practical styling details.\n\n"
            f"Item:\n"
            f"- Title: {new_item.get('title', '')}\n"
            f"- Category: {new_item.get('category', '')}\n"
            f"- Size: {new_item.get('size', '')}\n"
            f"- Colors: {', '.join(new_item.get('colors', []) or [])}\n"
            f"- Style tags: {', '.join(new_item.get('style_tags', []) or [])}\n"
            f"- Description: {new_item.get('description', '')}\n"
        )
    else:
        wardrobe_lines = []
        for item in items:
            wardrobe_lines.append(
                "- {name} ({category}) | colors: {colors} | tags: {tags} | notes: {notes}".format(
                    name=item.get("name", ""),
                    category=item.get("category", ""),
                    colors=", ".join(item.get("colors", []) or []),
                    tags=", ".join(item.get("style_tags", []) or []),
                    notes=item.get("notes") or "none",
                )
            )

        prompt = (
            "You are a styling assistant for a thrift shopping app.\n"
            "Suggest 1-2 complete outfit combinations using the new item and specific wardrobe pieces by name.\n"
            "Include useful styling details like silhouette, layering, color balance, and footwear.\n\n"
            f"New item:\n"
            f"- Title: {new_item.get('title', '')}\n"
            f"- Category: {new_item.get('category', '')}\n"
            f"- Size: {new_item.get('size', '')}\n"
            f"- Colors: {', '.join(new_item.get('colors', []) or [])}\n"
            f"- Style tags: {', '.join(new_item.get('style_tags', []) or [])}\n"
            f"- Description: {new_item.get('description', '')}\n\n"
            "Wardrobe items:\n"
            + "\n".join(wardrobe_lines)
        )

    try:
        client = _get_groq_client()
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You write short, practical outfit advice for a thrift styling assistant. "
                        "Be specific, useful, and concise."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
        )
        content = response.choices[0].message.content if response.choices else ""
        if content and str(content).strip():
            return str(content).strip()
    except Exception:
        pass

    if not items:
        return (
            "I could not generate styling ideas right now, but this item should still work best with "
            "simple basics, a balanced silhouette, and accessories that match its vibe."
        )
    return (
        "I could not generate wardrobe-based outfit ideas right now, but this item should pair well "
        "with complementary basics, clean layering, and shoes that match its silhouette."
    )


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)

    TODO:
        1. Guard against an empty or whitespace-only outfit string.
        2. Build a prompt that gives the LLM the item details and the outfit,
           and asks for a caption matching the style guidelines above.
        3. Call the LLM and return the response.

    Before writing code, fill in the Tool 3 section of planning.md.
    """
    if not outfit or not outfit.strip():
        return "Could not generate a fit card because the outfit suggestion was empty."

    prompt = (
        "You are writing a short, casual OOTD-style caption for a thrift shopping app.\n"
        "Make it 2-4 sentences, natural and specific, and avoid sounding like a product description.\n"
        "Mention the item title, price, and platform naturally exactly once each.\n"
        "Use a little variety and keep the vibe stylish and authentic.\n\n"
        f"Item title: {new_item.get('title', '')}\n"
        f"Price: {new_item.get('price', '')}\n"
        f"Platform: {new_item.get('platform', '')}\n"
        f"Outfit idea: {outfit}\n"
    )

    try:
        client = _get_groq_client()
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You write concise, casual captions for thrifted outfit posts. "
                        "Sound human and specific."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=1.0,
        )
        content = response.choices[0].message.content if response.choices else ""
        if content and str(content).strip():
            return str(content).strip()
    except Exception:
        pass

    return "Could not generate a fit card right now."
