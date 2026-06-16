from pathlib import Path
import sys
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import agent


def test_query_parser_extracts_description_size_and_price(monkeypatch):
    captured = {}

    def fake_search(description, size, max_price):
        captured["description"] = description
        captured["size"] = size
        captured["max_price"] = max_price
        return []

    monkeypatch.setattr(agent, "search_listings", Mock(side_effect=fake_search))
    monkeypatch.setattr(agent, "suggest_outfit", Mock())
    monkeypatch.setattr(agent, "create_fit_card", Mock())

    session = agent.run_agent(
        "I’m looking for a vintage graphic tee under $30, size M. I mostly wear baggy jeans and chunky sneakers.",
        {"items": []},
    )

    assert captured["description"] == "vintage graphic tee"
    assert captured["size"] == "M"
    assert captured["max_price"] == 30.0
    assert session["parsed"] == {
        "description": "vintage graphic tee",
        "size": "M",
        "max_price": 30.0,
    }


def test_successful_interaction_calls_all_three_tools(monkeypatch):
    search_result = {"id": "lst_006", "title": "Graphic Tee"}
    search_mock = Mock(return_value=[search_result])
    outfit_mock = Mock(return_value="Wear it with baggy jeans and chunky sneakers.")
    fit_card_mock = Mock(return_value="OOTD caption.")

    monkeypatch.setattr(agent, "search_listings", search_mock)
    monkeypatch.setattr(agent, "suggest_outfit", outfit_mock)
    monkeypatch.setattr(agent, "create_fit_card", fit_card_mock)

    session = agent.run_agent("vintage graphic tee under $30, size M", {"items": []})

    assert search_mock.called
    assert outfit_mock.called
    assert fit_card_mock.called
    assert session["error"] is None


def test_exact_top_listing_is_passed_into_suggest_outfit(monkeypatch):
    search_result = {"id": "lst_006", "title": "Graphic Tee"}
    search_mock = Mock(return_value=[search_result])
    outfit_mock = Mock(return_value="Wear it with baggy jeans and chunky sneakers.")
    fit_card_mock = Mock(return_value="OOTD caption.")

    monkeypatch.setattr(agent, "search_listings", search_mock)
    monkeypatch.setattr(agent, "suggest_outfit", outfit_mock)
    monkeypatch.setattr(agent, "create_fit_card", fit_card_mock)

    agent.run_agent("vintage graphic tee under $30, size M", {"items": []})

    outfit_mock.assert_called_once()
    passed_item, passed_wardrobe = outfit_mock.call_args.args
    assert passed_item is search_result
    assert passed_wardrobe == {"items": []}


def test_exact_outfit_and_selected_item_are_passed_into_create_fit_card(monkeypatch):
    search_result = {"id": "lst_006", "title": "Graphic Tee"}
    outfit_text = "Wear it with baggy jeans and chunky sneakers."
    search_mock = Mock(return_value=[search_result])
    outfit_mock = Mock(return_value=outfit_text)
    fit_card_mock = Mock(return_value="OOTD caption.")

    monkeypatch.setattr(agent, "search_listings", search_mock)
    monkeypatch.setattr(agent, "suggest_outfit", outfit_mock)
    monkeypatch.setattr(agent, "create_fit_card", fit_card_mock)

    agent.run_agent("vintage graphic tee under $30, size M", {"items": []})

    fit_card_mock.assert_called_once()
    passed_outfit, passed_item = fit_card_mock.call_args.args
    assert passed_outfit is outfit_text
    assert passed_item is search_result


def test_final_session_contains_expected_keys(monkeypatch):
    search_result = {"id": "lst_006", "title": "Graphic Tee"}
    monkeypatch.setattr(agent, "search_listings", Mock(return_value=[search_result]))
    monkeypatch.setattr(agent, "suggest_outfit", Mock(return_value="Wear it with baggy jeans and chunky sneakers."))
    monkeypatch.setattr(agent, "create_fit_card", Mock(return_value="OOTD caption."))

    session = agent.run_agent("vintage graphic tee under $30, size M", {"items": []})

    assert set(session.keys()) == {
        "query",
        "parsed",
        "search_results",
        "selected_item",
        "wardrobe",
        "outfit_suggestion",
        "fit_card",
        "error",
    }
    assert session["query"] == "vintage graphic tee under $30, size M"
    assert session["search_results"] == [search_result]
    assert session["selected_item"] is search_result
    assert session["wardrobe"] == {"items": []}
    assert session["outfit_suggestion"] == "Wear it with baggy jeans and chunky sneakers."
    assert session["fit_card"] == "OOTD caption."
    assert session["error"] is None


def test_empty_search_results_set_actionable_error(monkeypatch):
    search_mock = Mock(return_value=[])
    outfit_mock = Mock()
    fit_card_mock = Mock()

    monkeypatch.setattr(agent, "search_listings", search_mock)
    monkeypatch.setattr(agent, "suggest_outfit", outfit_mock)
    monkeypatch.setattr(agent, "create_fit_card", fit_card_mock)

    session = agent.run_agent("designer ballgown size XXS under $5", {"items": []})

    assert session["search_results"] == []
    assert session["error"]
    assert "loosen" in session["error"].lower()
    assert outfit_mock.call_count == 0
    assert fit_card_mock.call_count == 0


def test_empty_search_results_prevent_later_tools(monkeypatch):
    search_mock = Mock(return_value=[])
    outfit_mock = Mock()
    fit_card_mock = Mock()

    monkeypatch.setattr(agent, "search_listings", search_mock)
    monkeypatch.setattr(agent, "suggest_outfit", outfit_mock)
    monkeypatch.setattr(agent, "create_fit_card", fit_card_mock)

    agent.run_agent("designer ballgown size XXS under $5", {"items": []})

    outfit_mock.assert_not_called()
    fit_card_mock.assert_not_called()


def test_empty_wardrobe_session_can_still_complete(monkeypatch):
    search_result = {"id": "lst_006", "title": "Graphic Tee"}
    search_mock = Mock(return_value=[search_result])
    outfit_mock = Mock(return_value="Try it with relaxed denim and clean sneakers.")
    fit_card_mock = Mock(return_value="OOTD caption.")

    monkeypatch.setattr(agent, "search_listings", search_mock)
    monkeypatch.setattr(agent, "suggest_outfit", outfit_mock)
    monkeypatch.setattr(agent, "create_fit_card", fit_card_mock)

    session = agent.run_agent("vintage graphic tee under $30, size M", {"items": []})

    assert session["error"] is None
    assert session["outfit_suggestion"] == "Try it with relaxed denim and clean sneakers."
    assert session["fit_card"] == "OOTD caption."
