# GDELT RAG Agent

A news analysis and retrieval system that uses [GDELT](https://www.gdeltproject.org/) (Global Database of Events, Language, and Tone) data to answer natural-language questions about world events, backed by an LLM agent.

## Architecture

- **UI** — Streamlit chat interface (`ui/app.py`)
- **API** — FastAPI backend exposing a `/chat` endpoint (`api/main.py`)
- **Agent** — Routes the user's question to a search tool, then uses an LLM to turn the raw results into a clean, factual answer (`agent/llm_agent.py`)
- **Tools** — Database queries + lightweight web scraping to pull real article text from source URLs (`agent/tools.py`)
- **Data pipeline** — Downloads and loads GDELT event data (`downloader.py`, `processor.py`)
- **Database** — SQLite (a single local file, `data/gdelt.db`, auto-created — no server to install)
- **LLM** — [Groq](https://console.groq.com/) — free, hosted, OpenAI-compatible API. No local model download needed.

## Setup

### 1. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Get a free Groq API key

Sign up at [console.groq.com/keys](https://console.groq.com/keys) and create a key (no credit card required).

### 3. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and paste in your key:

```
GROQ_API_KEY=your_groq_api_key_here
```

### 4. Load some data

```bash
python downloader.py   # downloads the latest GDELT event export
python processor.py    # loads it into data/gdelt.db (SQLite)
```

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

- "Show me the latest news from India"
- "Get political news from the US"
- "News from 2024"
- "Show me sports news from India in 2024"

## Notes on data quality

GDELT's raw event export doesn't include a real headline/description field — only actor names, an event code, and a source URL. This app:
1. Builds a plain-English fallback description from the actor names and event type (e.g. "India engaged in diplomatic cooperation with USA.")
2. Tries to scrape the real article text from the source URL at query time, and uses that instead when it succeeds.

## Project structure

```
agent/
  llm_agent.py   # query routing + LLM rephrasing (Groq)
  tools.py       # SQLite queries + article scraping
api/
  main.py        # FastAPI /chat endpoint
ui/
  app.py         # Streamlit chat UI
downloader.py    # pulls latest GDELT export
processor.py     # loads GDELT export into SQLite
data/            # local SQLite DB + downloaded files (gitignored)
```

## Troubleshooting

- **"GROQ_API_KEY is not set"** — make sure `.env` exists (copied from `.env.example`) and has your real key, and that you're running commands from the project root.
- **No results for a query** — run `downloader.py` and `processor.py` first to populate `data/gdelt.db`. GDELT only keeps a rolling ~7 day window of recent exports, so very old date ranges won't return anything unless you've archived older files yourself.
- **Groq rate limits** — the free tier is generous but not unlimited; if you hit a rate limit, wait a minute or switch `GROQ_MODEL` in `.env` to a smaller model (e.g. `llama-3.1-8b-instant`).

## Screenshot of Streamlit UI 
<img width="1918" height="971" alt="Screenshot 2026-07-31 222859" src="https://github.com/user-attachments/assets/3b298a7f-e263-4123-b293-5c598072defa" />
<img width="1918" height="997" alt="image" src="https://github.com/user-attachments/assets/89554580-d528-4ade-9f78-5823d51df170" />


## Support

For questions, contact joshilfernandes@gmail.com
