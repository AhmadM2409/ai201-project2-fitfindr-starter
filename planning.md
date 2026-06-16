# FitFindr - planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation - the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed - add any additional tools below them.

### Tool 1: search_listings

**What it does:**
Searches the local mock marketplace listings dataset for items that match a user's description, optional size, and optional maximum price. It ranks results by keyword overlap with the query so the best-matching item appears first.

**Input parameters:**
- `description` (str): Keywords describing the item the user wants to find, such as `"vintage graphic tee"` or `"90s track jacket"`.
- `size` (str | None): Optional size filter. If provided, only listings whose size text reasonably matches should be considered.
- `max_price` (float | None): Optional maximum price filter, inclusive.

**What it returns:**
A `list[dict]` of matching listing objects from `data/listings.json`, sorted from best match to worst match. Each returned dict contains the original listing fields: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, and `platform`.

**What happens if it fails or returns nothing:**
If no listings match the filters or the query keywords, the function returns an empty list. The agent must stop the planning loop, set a helpful error message in session state, and not call the outfit or fit-card tools.

---

### Tool 2: suggest_outfit

**What it does:**
Uses the selected thrift listing and the user's wardrobe to generate 1 to 2 outfit ideas with the Groq LLM. If the wardrobe is empty, it should still return useful styling advice based on the new item alone instead of failing.

**Input parameters:**
- `new_item` (dict): The selected listing dict returned by `search_listings()`. This is the exact item the agent chose as the top result.
- `wardrobe` (dict): A wardrobe dict with an `items` key. Each item in `wardrobe["items"]` has `id`, `name`, `category`, `colors`, `style_tags`, and optional `notes`.

**What it returns:**
A non-empty `str` containing outfit suggestions. When the wardrobe has items, the response should name specific wardrobe pieces and show how to combine them with `new_item`. When the wardrobe is empty, the response should give general styling guidance and compatible categories, colors, and vibes.

**What happens if it fails or returns nothing:**
If `wardrobe["items"]` is empty, the tool should not error; it should switch to a general-styling prompt and still return a string. If the Groq call fails or produces no usable output, the tool should return a clear fallback message explaining that outfit suggestions could not be generated.

---

### Tool 3: create_fit_card

**What it does:**
Turns the outfit suggestion into a short shareable caption suitable for an OOTD-style social post. It should read like a casual caption, mention the item name, price, and platform naturally, and preserve the vibe of the outfit suggestion.

**Input parameters:**
- `outfit` (str): The outfit suggestion produced by `suggest_outfit()`.
- `new_item` (dict): The selected listing dict passed through from `search_listings()`.

**What it returns:**
A `str` containing a 2 to 4 sentence fit-card caption. The text should mention the item name, the price, and the platform once each, while sounding casual and specific rather than like a product listing.

**What happens if it fails or returns nothing:**
If `outfit` is empty or only whitespace, the tool should return an error string rather than calling the model. If the Groq call fails, it should return a concise fallback message saying the fit card could not be generated.

---

### Additional Tools (if any)

None. The assignment only requires the three tools above.

---

## Planning Loop

**How does your agent decide which tool to call next?**
The agent follows a conditional, state-driven workflow. It first parses the user's query into `description`, `size`, and `max_price`, then calls `search_listings()` with those parsed values. The next action depends on the current session state and the tool outputs: if `search_results` is empty, the agent writes an actionable error into session state and does not call later tools. If results exist, the agent stores the top result in `session["selected_item"]`, passes that exact dict to `suggest_outfit()`, stores the returned outfit string, then passes both the outfit string and the selected item to `create_fit_card()`. The loop is finished only after the fit card is stored and the completed session is returned.

---

## State Management

**How does information from one tool get passed to the next?**
All data flows through the session dict returned by `_new_session()`. The agent should treat that session as the single source of truth for the interaction.

Session keys and when they are written:

- `query`: written once in `_new_session()` from the incoming user query.
- `parsed`: written after query parsing in `run_agent()`. It should contain at least `description`, `size`, and `max_price`.
- `search_results`: written immediately after `search_listings()` returns.
- `selected_item`: written after search succeeds, using the first item in `search_results`.
- `wardrobe`: written once in `_new_session()` from the user-selected wardrobe.
- `outfit_suggestion`: written after `suggest_outfit()` returns.
- `fit_card`: written after `create_fit_card()` returns.
- `error`: written in `_new_session()` as `None`, then updated only when a failure stops the flow early.

The UI layer in `app.py` should only read from the final session dict. It should not recompute tool outputs.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | Stop the planning loop, set `session["error"]` to a helpful message such as "No listings matched your search. Try loosening the size, price, or description.", and return the session without calling later tools. |
| suggest_outfit | Wardrobe is empty | Keep going, but change the prompt to ask for general styling advice instead of wardrobe-specific pairings. Return a non-empty styling string so the flow can continue. |
| create_fit_card | Outfit input is missing or incomplete | Return a clear fallback error string such as "Could not generate a fit card because the outfit suggestion was empty." Do not raise an exception. |
| Groq / API failure | Model call fails, times out, or returns unusable output | Catch the failure in the tool layer, return a readable fallback string, and let the agent/UI surface that text instead of crashing. |

---

## Architecture

```mermaid
flowchart TD
    U[User query] --> P[Planning loop in run_agent()]
    P --> S[Parse query into description, size, max_price]
    S --> L[search_listings(description, size, max_price)]
    L -->|no matches| E[session.error = helpful no-results message]
    E --> R[Return session early]
    L -->|matches found| T[Store top result in session.selected_item]
    T --> O[suggest_outfit(new_item, wardrobe)]
    O -->|empty wardrobe| O2[General styling prompt]
    O -->|LLM success| C[Store session.outfit_suggestion]
    O2 --> C
    C --> F[create_fit_card(outfit, new_item)]
    F --> G[Store session.fit_card]
    G --> X[Return completed session]

    subgraph State[Session state]
        Q[query]
        P1[parsed]
        SR[search_results]
        SI[selected_item]
        W[wardrobe]
        OS[outfit_suggestion]
        FC[fit_card]
        ER[error]
    end

    U -. writes .-> Q
    S -. writes .-> P1
    L -. writes .-> SR
    T -. writes .-> SI
    P -. reads .-> W
    O -. writes .-> OS
    F -. writes .-> FC
    E -. writes .-> ER
```

---

## AI Tool Plan

For each milestone below, I will provide Codex with the relevant sections of this plan, the starter code, and the exact data shapes from `data/listings.json` and `data/wardrobe_schema.json`. I will verify each result by running the smallest practical check before moving to the next milestone.

**Milestone 1 - Repository and data inspection:**
I will give Codex the repository file list plus `data/listings.json`, `data/wardrobe_schema.json`, and the relevant starter files. It should produce a concise implementation map that identifies the important files, the data shapes, and the incomplete functions. I will review the output by checking that it matches the actual file structure and the real field names in the data.

**Milestone 2 - Planning document specification:**
I will give Codex the starter `planning.md` template and the starter code context. It should produce a fully specified planning document that defines the tools, the state flow, the error handling, and the example interaction. I will review the result by confirming that every required section is filled in and that the plan matches the existing codebase.

**Milestone 3 - Individual tool implementations:**
I will give Codex the Tool 1, Tool 2, and Tool 3 specs plus the listing and wardrobe data shapes. It should produce the implementations for `search_listings()`, `suggest_outfit()`, and `create_fit_card()` in `tools.py`. I will verify `search_listings()` with a few keyword, size, and price queries; verify `suggest_outfit()` with both a populated wardrobe and an empty wardrobe; and verify `create_fit_card()` with a valid outfit string and an empty-outfit failure case.

**Milestone 4 - Planning loop and state management:**
I will give Codex the Planning Loop, State Management, Error Handling, and Architecture sections, plus the tool implementations from Milestone 3. It should produce `run_agent()` in `agent.py` and the `handle_query()` wiring in `app.py`. I will verify the happy path, the no-results path, and the empty-wardrobe path by checking the returned session dict and the three Gradio output strings.

**Milestone 5 - Environment and dependency verification:**
I will give Codex the requirements file and the setup notes from the repo inspection. It should confirm that the Python environment can import the required packages and that the project can start cleanly. I will review this by running the import check and, if needed, the application entry point to ensure the environment is ready for implementation work.

**Milestone 6 - End-to-end review and handoff:**
I will give Codex the completed code and the planning document. It should produce a final review of the interaction flow, the error paths, and the user-facing outputs. I will review the output by confirming that the final behavior matches the plan, that the implementation milestones were completed in order, and that the app handles both successful searches and failure cases cleanly.

---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish - tool call by tool call. Use a specific example query.

**Example user query:** "I'm looking for a vintage graphic tee under $30, size M. I mostly wear baggy jeans and chunky sneakers."

**Step 1:**
The user submits the query. `run_agent()` creates a new session and parses it into `description="vintage graphic tee"`, `size="M"`, and `max_price=30.0`.

**Step 2:**
The agent calls `search_listings(description="vintage graphic tee", size=None, max_price=30)`. The tool returns a list of matching listings from the local dataset, sorted by relevance.

**Step 3:**
The agent stores the search results in `session["search_results"]`, takes the first listing as `session["selected_item"]`, and passes that exact listing dict plus the wardrobe into `suggest_outfit()`. If the wardrobe is the example wardrobe, the model should generate outfit ideas using named pieces such as the baggy jeans, white tank, chunky sneakers, or black denim jacket.

**Step 4:**
`suggest_outfit()` returns a string with 1 to 2 outfit ideas. The agent stores that string in `session["outfit_suggestion"]` and then calls `create_fit_card(outfit, new_item)` with the outfit string and the same listing dict selected earlier.

**Step 5:**
`create_fit_card()` returns a short caption that mentions the item name, price, and platform naturally. The agent stores it in `session["fit_card"]` and returns the completed session.

**Final output to user:**
The user sees the top listing, the outfit suggestion, and the fit card. If no listings matched, the user instead sees a single helpful error message in the listing panel and empty outfit and fit-card panels.
