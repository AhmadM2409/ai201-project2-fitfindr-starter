from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tools
from tools import create_fit_card, search_listings, suggest_outfit


def _matches_size(listing_size: str, requested_size: str) -> bool:
    listing_norm = listing_size.lower()
    requested_norm = requested_size.lower()
    return requested_norm in listing_norm or listing_norm in requested_norm


def _query_score(listing: dict, description: str) -> int:
    import re

    stopwords = {
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
    tokens = {
        token
        for token in re.findall(r"[a-z0-9]+", description.lower())
        if token not in stopwords
    }
    searchable = " ".join(
        [
            str(listing.get("title", "")),
            str(listing.get("description", "")),
            str(listing.get("category", "")),
            " ".join(listing.get("style_tags", []) or []),
            " ".join(listing.get("colors", []) or []),
            str(listing.get("brand") or ""),
        ]
    ).lower()
    return sum(1 for token in tokens if token in searchable)


def test_normal_search_returns_results():
    results = search_listings("vintage graphic tee", None, 30)

    assert isinstance(results, list)
    assert results


def test_impossible_search_returns_empty_list():
    results = search_listings("designer ballgown", "XXS", 5)

    assert results == []


def test_all_results_respect_max_price():
    results = search_listings("vintage", None, 20)

    assert results
    assert all(item["price"] <= 20 for item in results)


def test_all_results_respect_size_filter():
    results = search_listings("vintage", "M", 60)

    assert results
    assert all(_matches_size(item["size"], "M") for item in results)


def test_more_relevant_results_appear_first():
    results = search_listings("bootleg graphic tee", None, 40)

    assert results
    assert results[0]["id"] == "lst_006"
    if len(results) > 1:
        assert _query_score(results[0], "bootleg graphic tee") >= _query_score(
            results[1], "bootleg graphic tee"
        )


def _make_fake_client(content=None, side_effect=None, captured_prompts=None):
    def create(**kwargs):
        if captured_prompts is not None:
            captured_prompts.append(kwargs)
        if side_effect is not None:
            raise side_effect
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=content),
                )
            ]
        )

    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))


def test_suggest_outfit_with_populated_wardrobe_returns_text(monkeypatch):
    captured = []
    fake_client = _make_fake_client(
        content="Option 1: Wear the tee with Baggy straight-leg jeans, dark wash and Chunky white sneakers.",
        captured_prompts=captured,
    )
    monkeypatch.setattr(tools, "_get_groq_client", Mock(return_value=fake_client))

    result = suggest_outfit(
        {
            "title": "Vintage Graphic Tee",
            "category": "tops",
            "size": "M",
            "colors": ["black"],
            "style_tags": ["vintage", "graphic tee"],
            "description": "soft worn-in tee",
        },
        {
            "items": [
                {
                    "id": "w_001",
                    "name": "Baggy straight-leg jeans, dark wash",
                    "category": "bottoms",
                    "colors": ["dark blue", "indigo"],
                    "style_tags": ["denim", "streetwear", "baggy"],
                    "notes": "High-waisted, sits above the hip",
                },
                {
                    "id": "w_007",
                    "name": "Chunky white sneakers",
                    "category": "shoes",
                    "colors": ["white"],
                    "style_tags": ["sneakers", "chunky", "streetwear"],
                    "notes": None,
                },
            ]
        },
    )

    assert isinstance(result, str)
    assert result.strip()
    assert captured
    assert "Baggy straight-leg jeans, dark wash" in captured[0]["messages"][1]["content"]
    assert "Chunky white sneakers" in captured[0]["messages"][1]["content"]


def test_suggest_outfit_with_empty_wardrobe_returns_advice(monkeypatch):
    fake_client = _make_fake_client(content="Try it with relaxed denim, sneakers, and light layering.")
    monkeypatch.setattr(tools, "_get_groq_client", Mock(return_value=fake_client))

    result = suggest_outfit(
        {
            "title": "Vintage Graphic Tee",
            "category": "tops",
            "size": "M",
            "colors": ["black"],
            "style_tags": ["vintage", "graphic tee"],
            "description": "soft worn-in tee",
        },
        {"items": []},
    )

    assert isinstance(result, str)
    assert result.strip()
    assert "denim" in result.lower() or "layer" in result.lower() or "sneaker" in result.lower()


def test_suggest_outfit_missing_items_key_does_not_crash(monkeypatch):
    fake_client = _make_fake_client(content="A cropped tee works well with relaxed pants and layered jewelry.")
    monkeypatch.setattr(tools, "_get_groq_client", Mock(return_value=fake_client))

    result = suggest_outfit(
        {
            "title": "Vintage Graphic Tee",
            "category": "tops",
            "size": "M",
            "colors": ["black"],
            "style_tags": ["vintage", "graphic tee"],
            "description": "soft worn-in tee",
        },
        {},
    )

    assert isinstance(result, str)
    assert result.strip()


def test_suggest_outfit_api_failure_returns_fallback(monkeypatch):
    fake_client = _make_fake_client(side_effect=RuntimeError("boom"))
    monkeypatch.setattr(tools, "_get_groq_client", Mock(return_value=fake_client))

    result = suggest_outfit(
        {
            "title": "Vintage Graphic Tee",
            "category": "tops",
            "size": "M",
            "colors": ["black"],
            "style_tags": ["vintage", "graphic tee"],
            "description": "soft worn-in tee",
        },
        {"items": []},
    )

    assert isinstance(result, str)
    assert result.strip()
    assert "could not generate" in result.lower() or "right now" in result.lower()


def test_suggest_outfit_empty_model_response_returns_fallback(monkeypatch):
    fake_client = _make_fake_client(content="   ")
    monkeypatch.setattr(tools, "_get_groq_client", Mock(return_value=fake_client))

    result = suggest_outfit(
        {
            "title": "Vintage Graphic Tee",
            "category": "tops",
            "size": "M",
            "colors": ["black"],
            "style_tags": ["vintage", "graphic tee"],
            "description": "soft worn-in tee",
        },
        {"items": []},
    )

    assert isinstance(result, str)
    assert result.strip()
    assert "could not generate" in result.lower() or "right now" in result.lower()


def test_create_fit_card_with_valid_outfit_returns_caption(monkeypatch):
    fake_client = _make_fake_client(content="Vintage tee energy with baggy denim and chunky shoes.")
    monkeypatch.setattr(tools, "_get_groq_client", Mock(return_value=fake_client))

    result = create_fit_card(
        "Pair the tee with baggy jeans and chunky sneakers for a relaxed streetwear look.",
        {
            "title": "Vintage Graphic Tee",
            "price": 18.0,
            "platform": "depop",
        },
    )

    assert isinstance(result, str)
    assert result.strip()


def test_create_fit_card_prompt_includes_item_details_and_outfit(monkeypatch):
    captured = []
    fake_client = _make_fake_client(
        content="Vintage tee energy with baggy denim and chunky shoes.",
        captured_prompts=captured,
    )
    monkeypatch.setattr(tools, "_get_groq_client", Mock(return_value=fake_client))

    outfit = "Pair the tee with baggy jeans and chunky sneakers for a relaxed streetwear look."
    create_fit_card(
        outfit,
        {
            "title": "Vintage Graphic Tee",
            "price": 18.0,
            "platform": "depop",
        },
    )

    assert captured
    prompt = captured[0]["messages"][1]["content"]
    assert "Vintage Graphic Tee" in prompt
    assert "18.0" in prompt or "$18" in prompt
    assert "depop" in prompt
    assert outfit in prompt


def test_create_fit_card_empty_outfit_returns_error_without_calling_groq(monkeypatch):
    fake_client = Mock()
    monkeypatch.setattr(tools, "_get_groq_client", Mock(return_value=fake_client))

    result = create_fit_card(
        "   ",
        {
            "title": "Vintage Graphic Tee",
            "price": 18.0,
            "platform": "depop",
        },
    )

    assert isinstance(result, str)
    assert result.strip()
    assert "empty" in result.lower()
    assert not fake_client.chat.completions.create.called


def test_create_fit_card_api_failure_returns_fallback(monkeypatch):
    fake_client = _make_fake_client(side_effect=RuntimeError("boom"))
    monkeypatch.setattr(tools, "_get_groq_client", Mock(return_value=fake_client))

    result = create_fit_card(
        "Pair the tee with baggy jeans and chunky sneakers for a relaxed streetwear look.",
        {
            "title": "Vintage Graphic Tee",
            "price": 18.0,
            "platform": "depop",
        },
    )

    assert isinstance(result, str)
    assert result.strip()
    assert "could not generate" in result.lower() or "right now" in result.lower()


def test_create_fit_card_empty_model_response_returns_fallback(monkeypatch):
    fake_client = _make_fake_client(content="   ")
    monkeypatch.setattr(tools, "_get_groq_client", Mock(return_value=fake_client))

    result = create_fit_card(
        "Pair the tee with baggy jeans and chunky sneakers for a relaxed streetwear look.",
        {
            "title": "Vintage Graphic Tee",
            "price": 18.0,
            "platform": "depop",
        },
    )

    assert isinstance(result, str)
    assert result.strip()
    assert "could not generate" in result.lower() or "right now" in result.lower()


def test_create_fit_card_returns_distinct_outputs_for_distinct_inputs(monkeypatch):
    first_client = _make_fake_client(content="First caption with a mellow vibe.")
    second_client = _make_fake_client(content="Second caption with a bolder vibe.")
    clients = [first_client, second_client]

    def _client_factory():
        return clients.pop(0)

    monkeypatch.setattr(tools, "_get_groq_client", Mock(side_effect=_client_factory))

    first = create_fit_card(
        "Outfit one.",
        {"title": "Vintage Graphic Tee", "price": 18.0, "platform": "depop"},
    )
    second = create_fit_card(
        "Outfit two.",
        {"title": "Vintage Graphic Tee", "price": 18.0, "platform": "depop"},
    )

    assert first == "First caption with a mellow vibe."
    assert second == "Second caption with a bolder vibe."
    assert first != second
