# FitFindr

## 1. Project Overview

FitFindr is a small Gradio app that helps a user search a local mock secondhand marketplace, get outfit ideas using their wardrobe, and turn the recommendation into a short fit-card caption.

The completed project has three layers:

1. `tools.py` implements the three core tools.
2. `agent.py` coordinates those tools through a conditional planning loop and session state.
3. `app.py` provides the UI handler and Gradio interface.

The app uses a local dataset in `data/listings.json`, a wardrobe schema in `data/wardrobe_schema.json`, and Groq for the two generative steps.

## 2. Setup and Installation

Requirements:

- Python 3.13 or compatible
- A Groq API key in `.env`

Install dependencies from the project folder:

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Create a `.env` file in the project root with your key:

```env
GROQ_API_KEY=your_key_here
```

## 3. How to Run the App

Start the Gradio app from the project root:

```bash
python app.py
```

Open the local URL printed in the terminal, usually `http://localhost:7860`.

The app lets you choose either the example wardrobe or an empty wardrobe and then submit a search query such as `vintage graphic tee under $30, size M`.

## 4. How to Run Tests

Run the full pytest suite:

```bash
pytest tests -v
```

The completed project currently passes 32 pytest tests.

## 5. Tool Inventory

### `search_listings(description, size, max_price)`

- Function name: `search_listings`
- Signature: `search_listings(description: str, size: str | None = None, max_price: float | None = None) -> list[dict]`
- Purpose: Search the local listings dataset for items that match the query description, optional size, and optional maximum price.
- Return type: `list[dict]`
- Return contents: Original listing dictionaries from `data/listings.json`, sorted from highest relevance to lowest. Each listing contains `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, and `platform`.
- Failure behavior: Returns `[]` when nothing matches. It does not raise for a normal no-results search.

### `suggest_outfit(new_item, wardrobe)`

- Function name: `suggest_outfit`
- Signature: `suggest_outfit(new_item: dict, wardrobe: dict) -> str`
- Purpose: Use Groq model `llama-3.3-70b-versatile` to suggest 1 to 2 outfits or general styling advice based on the selected item and wardrobe.
- Return type: `str`
- Return contents: A non-empty outfit suggestion string. When the wardrobe has items, it references specific wardrobe item names and styling details. When the wardrobe is empty or missing items, it returns general styling advice.
- Failure behavior: If the wardrobe is empty or missing `items`, it still returns styling advice. If the Groq/API call fails or returns empty content, it returns a readable fallback string instead of raising.

### `create_fit_card(outfit, new_item)`

- Function name: `create_fit_card`
- Signature: `create_fit_card(outfit: str, new_item: dict) -> str`
- Purpose: Use Groq model `llama-3.3-70b-versatile` to turn the outfit suggestion into a short OOTD-style caption.
- Return type: `str`
- Return contents: A 2 to 4 sentence caption that mentions the item title, price, and platform naturally.
- Failure behavior: If `outfit` is empty or whitespace, it returns a clear error string and does not call Groq. If the Groq/API call fails or returns empty content, it returns a readable fallback string.

## 6. Planning Loop

The agent in `agent.py` uses a conditional, state-driven workflow:

1. Parse the query into `description`, `size`, and `max_price`.
2. Call `search_listings(description, size, max_price)`.
3. Store the results in `session["search_results"]`.
4. If the search results are empty, stop immediately, set `session["error"]` to an actionable message, and do not call later tools.
5. If results exist, store `search_results[0]` in `session["selected_item"]`.
6. Pass that exact listing dict and `session["wardrobe"]` into `suggest_outfit()`.
7. Store the returned string in `session["outfit_suggestion"]`.
8. Pass the exact outfit string and selected item dict into `create_fit_card()`.
9. Store the returned caption in `session["fit_card"]`.
10. Return the completed session dictionary.

This is not a fixed linear success path. The empty-search branch exits early and the returned session carries the error message.

## 7. State Management

The agent uses the session dictionary from `_new_session()` as the single source of truth.

Session keys:

- `query`: The original user query string. Written in `_new_session()`.
- `parsed`: Parsed query values. Written in `run_agent()` after parsing. Contains `description`, `size`, and `max_price`.
- `search_results`: The list returned by `search_listings()`. Written in `run_agent()` after search completes.
- `selected_item`: The top search result. Written in `run_agent()` when search succeeds.
- `wardrobe`: The wardrobe selected by the UI. Written in `_new_session()` and passed into `run_agent()`.
- `outfit_suggestion`: The string returned by `suggest_outfit()`. Written in `run_agent()` after the outfit tool returns.
- `fit_card`: The string returned by `create_fit_card()`. Written in `run_agent()` after the fit card tool returns.
- `error`: A readable failure message or `None`. Written in `_new_session()` and updated in `run_agent()` when the flow stops early or something unexpected fails.

How values move:

- `app.py` chooses the wardrobe and passes it to `run_agent()`.
- `run_agent()` writes the query parse into `session["parsed"]`.
- `search_listings()` receives the parsed values and returns listings.
- The top listing becomes `session["selected_item"]`.
- That exact item and the wardrobe become inputs to `suggest_outfit()`.
- The returned outfit string and the selected item become inputs to `create_fit_card()`.
- `app.py` reads only the final session dictionary and formats the panel strings.

## 8. Error Handling

### No search results

If `search_listings()` returns `[]`, the agent sets:

```text
No listings matched your search. Try loosening the description, size, or price.
```

The agent returns immediately and does not call `suggest_outfit()` or `create_fit_card()`.

### Empty wardrobe

If `wardrobe["items"]` is empty or missing, `suggest_outfit()` switches to a general styling prompt. It still returns a useful string instead of failing.

### Empty outfit input

If `create_fit_card()` receives an empty or whitespace-only outfit string, it returns:

```text
Could not generate a fit card because the outfit suggestion was empty.
```

It does not call Groq in that case.

### Groq/API failure

Both Groq-backed tools catch API/model failures and return readable fallback strings. The tests mock those failures and verify the fallback text instead of allowing crashes.

### Unexpected UI errors

`handle_query()` in `app.py` catches unexpected exceptions and returns a readable UI message in the listing panel with empty outfit and fit-card panels. The UI stays up rather than crashing.

Concrete examples from testing:

- The agent tests confirm that empty search results stop the loop early.
- The tool tests confirm that empty wardrobes still produce outfit advice.
- The tool tests confirm that empty outfit input returns an error string and skips Groq.
- The app tests confirm that a mocked exception returns a readable UI error message.

## 9. Testing

The repository currently passes 32 pytest tests.

Test coverage includes:

- Tool tests for `search_listings()`
- Tool tests for `suggest_outfit()`
- Tool tests for `create_fit_card()`
- Planning-loop and state-passing tests for `agent.py`
- UI-handler tests for `app.py`

Manual checks were also performed for:

- a happy path search and outfit flow
- the no-results path
- the empty wardrobe path
- the empty outfit input path

## 10. Specification Reflection

### One way `planning.md` helped implementation

`planning.md` made the state flow explicit before coding, especially the rule that the top search result must be passed unchanged into `suggest_outfit()` and then into `create_fit_card()`. That kept the implementation honest about session data and made the tests straightforward to write.

### One divergence from the original plan

The parser in `agent.py` became slightly more precise than the first draft of the plan. In practice it had to trim leading articles and handle a curly apostrophe query form so the parsed description matched the rubric example exactly. That change made the implementation more robust without changing the intended behavior.

## 11. AI Usage

Codex was used in a staged way rather than as a one-shot code generator.

1. Codex received the tool specification and implemented one tool at a time. Each tool was then verified with isolated pytest tests before moving on.
2. Codex received the planning-loop diagram and session-state specification, implemented `agent.py`, and the resulting behavior was verified with mocked state-passing and early-return tests.
3. Generated code was not accepted automatically. It was reviewed and corrected through tests, including fixes for parser details and prompt/fallback behavior.

## 12. Demo Instructions

The demo shows three things:

1. The complete three-tool workflow from search to outfit to fit card.
2. Session state passing between the agent and the tools.
3. The no-results failure path, where the agent stops early and returns a readable error.

To demo it, run `python app.py`, submit a query such as `vintage graphic tee under $30, size M`, and then try a no-results query such as `designer ballgown size XXS under $5`.
