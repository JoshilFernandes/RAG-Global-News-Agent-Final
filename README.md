# GDELT RAG Agent

A natural-language news analysis system built on [GDELT](https://www.gdeltproject.org/) (Global Database of Events, Language, and Tone) event data. Ask a question in plain English and it routes to the right retrieval strategy — country, date, category, or semantic similarity — then uses an LLM to turn the raw results into a clean, readable answer.

## Architecture

- **UI** — Streamlit chat interface (`ui/app.py`)
- **API** — FastAPI backend exposing a `/chat` endpoint (`api/main.py`)
- **Agent** — Routes each query to the right retrieval tool, then rephrases the results into a clean answer (`agent/llm_agent.py`)
- **Retrieval** — Four strategies, chosen automatically per query (`agent/tools.py`):
  - Exact country lookup (SQL)
  - Date-range lookup (SQL)
  - Keyword match on a known category, e.g. "sports", "political" (SQL)
  - **Semantic search** for everything else — free-text/topic questions are embedded and matched against a local FAISS index, so "what's happening with tariffs?" works even without an exact keyword match
- **Data pipeline** — Downloads and loads GDELT event data (`downloader.py`, `processor.py`)
- **Database** — SQLite, a single local file (`data/gdelt.db`), auto-created — no server to install
- **Vector index** — Local FAISS + Sentence-Transformers embeddings (`vectorstore.py`, `build_vector_index.py`)
- **LLM** — [Groq](https://console.groq.com/) — free, hosted, OpenAI-compatible API. No local model download needed.

## How a query gets answered

1. **Country mentioned** (e.g. "news from Germany") → exact SQL lookup by country code. Typos are tolerated (e.g. "Germnay" still resolves correctly).
2. **"recent" / "latest"** → SQL lookup over the last 7 days
3. **Known category mentioned** (e.g. "sports", "political") → SQL keyword match
4. **Anything else** — a free-text topic like "what's happening with interest rates?" → semantic search against the FAISS index, so it matches on meaning rather than exact wording. Falls back to a plain keyword search automatically if the index has no relevant match.

## Setup

### 1. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

> **Windows note:** if `faiss-cpu` or `sentence-transformers` fail to install silently as part of the batch install, install them explicitly: `pip install faiss-cpu sentence-transformers numpy`

### 2. Get a free Groq API key

Sign up at [console.groq.com/keys](https://console.groq.com/keys) — no credit card required.

### 3. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and paste in your key:

```
GROQ_API_KEY=your_groq_api_key_here
```

### 4. Load data and build the search index

```bash
python downloader.py         # downloads the latest GDELT event export
python processor.py          # loads it into data/gdelt.db (SQLite)
python build_vector_index.py # builds the semantic (FAISS) search index
```

`build_vector_index.py` only embeds events it hasn't seen before, so it's safe to re-run after loading new data.

### 5. Run the app

In separate terminals:

```bash
# Terminal 1 — API
uvicorn api.main:app --reload --port 8000

# Terminal 2 — UI
streamlit run ui/app.py
```

Open the Streamlit URL it prints (usually http://localhost:8501) and start asking questions.

## Example queries

- "Show me the latest news from Germany"
- "Get political news from India"
- "News from 2024"
- "What's happening with interest rates?" (semantic search)
- "Any updates on climate policy?" (semantic search)

## Notes on data quality

GDELT's raw event export doesn't include a real headline/description field — only actor names, an event code, and a source URL. This app:
1. Builds a plain-English fallback description from the actor names and event type (e.g. "Germany engaged in diplomatic cooperation with France.")
2. Tries to fetch the real article text from the source URL at query time, and uses that instead when it succeeds.
3. Embeds that same text for semantic search, so retrieval quality improves as more articles get successfully scraped.

Country matching uses GDELT's own coding system (FIPS 10-4), which differs from the ISO codes you might expect for a few countries — e.g. Germany is `GM`, not `DE`; the UK is `UK`, not `GB`. This is handled internally; you can just type country names normally.

## Project structure

```
agent/
  llm_agent.py       # query routing + LLM rephrasing (Groq)
  tools.py            # SQLite queries, semantic search, article scraping
api/
  main.py              # FastAPI /chat endpoint
ui/
  app.py               # Streamlit chat UI
vectorstore.py          # FAISS + Sentence-Transformers wrapper
build_vector_index.py   # embeds stored events into the FAISS index
downloader.py            # pulls latest GDELT export
processor.py              # loads GDELT export into SQLite
data/                      # local SQLite DB + FAISS index (gitignored)
```

## Troubleshooting

- **"GROQ_API_KEY is not set"** — make sure `.env` exists (copied from `.env.example`) with your real key, and that you're running commands from the project root.
- **`ModuleNotFoundError: No module named 'faiss'`** — the batch `pip install` silently skipped it on your system; run `pip install faiss-cpu sentence-transformers numpy` directly.
- **No results for a query** — run `downloader.py` → `processor.py` → `build_vector_index.py` in order first. GDELT only keeps a rolling ~7 day window of recent exports.
- **`build_vector_index.py` seems stuck / very slow** — older versions of this script scraped article URLs one at a time with a 10-second timeout each, which can take hours on a large dataset. The current version embeds stored descriptions directly (near-instant); re-scraping real article text for better quality is an optional, separate improvement.
- **Groq rate limits** — the free tier is generous but not unlimited; if you hit a limit, wait a minute or switch to a smaller model via `GROQ_MODEL` in `.env` (e.g. `llama-3.1-8b-instant`).

## Support

For questions, contact joshilfernandes@gmail.com
