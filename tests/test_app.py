from pathlib import Path
import sys
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app
import agent
import tools


def test_empty_input_returns_validation_message(monkeypatch):
    run_agent_mock = Mock()
    monkeypatch.setattr(app, "run_agent", run_agent_mock)

    listing, outfit, fit_card = app.handle_query("   ", "Example wardrobe")

    assert "enter" in listing.lower() or "search" in listing.lower()
    assert outfit == ""
    assert fit_card == ""
    assert run_agent_mock.call_count == 0


def test_example_wardrobe_option_passes_example_wardrobe(monkeypatch):
    captured = {}

    def fake_run_agent(query, wardrobe):
        captured["query"] = query
        captured["wardrobe"] = wardrobe
        return {
            "query": query,
            "parsed": {},
            "search_results": [{"title": "Vintage Graphic Tee", "price": 18.0, "platform": "depop", "size": "M", "condition": "good"}],
            "selected_item": {"title": "Vintage Graphic Tee", "price": 18.0, "platform": "depop", "size": "M", "condition": "good"},
            "wardrobe": wardrobe,
            "outfit_suggestion": "Wear it with baggy jeans.",
            "fit_card": "Cute fit.",
            "error": None,
        }

    monkeypatch.setattr(app, "run_agent", Mock(side_effect=fake_run_agent))

    app.handle_query("vintage graphic tee under $30, size M", "Example wardrobe")

    assert captured["wardrobe"] == app.get_example_wardrobe()


def test_empty_wardrobe_option_passes_empty_wardrobe(monkeypatch):
    captured = {}

    def fake_run_agent(query, wardrobe):
        captured["wardrobe"] = wardrobe
        return {
            "query": query,
            "parsed": {},
            "search_results": [{"title": "Vintage Graphic Tee", "price": 18.0, "platform": "depop", "size": "M", "condition": "good"}],
            "selected_item": {"title": "Vintage Graphic Tee", "price": 18.0, "platform": "depop", "size": "M", "condition": "good"},
            "wardrobe": wardrobe,
            "outfit_suggestion": "Wear it with baggy jeans.",
            "fit_card": "Cute fit.",
            "error": None,
        }

    monkeypatch.setattr(app, "run_agent", Mock(side_effect=fake_run_agent))

    app.handle_query("vintage graphic tee under $30, size M", "Empty wardrobe (new user)")

    assert captured["wardrobe"] == app.get_empty_wardrobe()


def test_successful_session_produces_three_populated_panels(monkeypatch):
    def fake_run_agent(query, wardrobe):
        return {
            "query": query,
            "parsed": {},
            "search_results": [
                {
                    "title": "Vintage Graphic Tee",
                    "price": 18.0,
                    "platform": "depop",
                    "size": "M",
                    "condition": "good",
                }
            ],
            "selected_item": {
                "title": "Vintage Graphic Tee",
                "price": 18.0,
                "platform": "depop",
                "size": "M",
                "condition": "good",
            },
            "wardrobe": wardrobe,
            "outfit_suggestion": "Wear it with baggy jeans.",
            "fit_card": "Cute fit.",
            "error": None,
        }

    monkeypatch.setattr(app, "run_agent", Mock(side_effect=fake_run_agent))

    listing, outfit, fit_card = app.handle_query("vintage graphic tee under $30, size M", "Example wardrobe")

    assert listing
    assert outfit
    assert fit_card


def test_listing_panel_includes_required_fields(monkeypatch):
    def fake_run_agent(query, wardrobe):
        return {
            "query": query,
            "parsed": {},
            "search_results": [{"title": "Vintage Graphic Tee"}],
            "selected_item": {
                "title": "Vintage Graphic Tee",
                "price": 18.0,
                "platform": "depop",
                "size": "M",
                "condition": "good",
            },
            "wardrobe": wardrobe,
            "outfit_suggestion": "Wear it with baggy jeans.",
            "fit_card": "Cute fit.",
            "error": None,
        }

    monkeypatch.setattr(app, "run_agent", Mock(side_effect=fake_run_agent))

    listing, _, _ = app.handle_query("vintage graphic tee under $30, size M", "Example wardrobe")

    assert "Vintage Graphic Tee" in listing
    assert "$18.0" in listing
    assert "depop" in listing
    assert "M" in listing
    assert "good" in listing


def test_error_session_shows_error_and_clears_later_panels(monkeypatch):
    def fake_run_agent(query, wardrobe):
        return {
            "query": query,
            "parsed": {},
            "search_results": [],
            "selected_item": None,
            "wardrobe": wardrobe,
            "outfit_suggestion": None,
            "fit_card": None,
            "error": "No listings matched your search. Try loosening the description, size, or price.",
        }

    monkeypatch.setattr(app, "run_agent", Mock(side_effect=fake_run_agent))

    listing, outfit, fit_card = app.handle_query("designer ballgown size XXS under $5", "Example wardrobe")

    assert "loosen" in listing.lower()
    assert outfit == ""
    assert fit_card == ""


def test_handle_query_does_not_directly_call_tool_functions(monkeypatch):
    tool_search = Mock()
    tool_outfit = Mock()
    tool_card = Mock()
    monkeypatch.setattr(tools, "search_listings", tool_search)
    monkeypatch.setattr(tools, "suggest_outfit", tool_outfit)
    monkeypatch.setattr(tools, "create_fit_card", tool_card)
    monkeypatch.setattr(
        app,
        "run_agent",
        Mock(
            return_value={
                "query": "vintage graphic tee under $30, size M",
                "parsed": {},
                "search_results": [
                    {
                        "title": "Vintage Graphic Tee",
                        "price": 18.0,
                        "platform": "depop",
                        "size": "M",
                        "condition": "good",
                    }
                ],
                "selected_item": {
                    "title": "Vintage Graphic Tee",
                    "price": 18.0,
                    "platform": "depop",
                    "size": "M",
                    "condition": "good",
                },
                "wardrobe": {"items": []},
                "outfit_suggestion": "Wear it with baggy jeans.",
                "fit_card": "Cute fit.",
                "error": None,
            }
        ),
    )

    app.handle_query("vintage graphic tee under $30, size M", "Example wardrobe")

    assert tool_search.call_count == 0
    assert tool_outfit.call_count == 0
    assert tool_card.call_count == 0


def test_unexpected_exception_returns_readable_message(monkeypatch):
    monkeypatch.setattr(app, "run_agent", Mock(side_effect=RuntimeError("boom")))

    listing, outfit, fit_card = app.handle_query("vintage graphic tee under $30, size M", "Example wardrobe")

    assert "wrong" in listing.lower() or "try again" in listing.lower()
    assert outfit == ""
    assert fit_card == ""
