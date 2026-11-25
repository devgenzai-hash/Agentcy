# AgentSwarm — AI Creative Social-Media Agency

A multi-agent system where AI "employees" (Lead Manager → Department Managers
→ Field Workers) cooperate to discover viral content ideas. Knowledge is
grounded in a curated, AI-categorized corpus of news/marketing/trend
websites plus live YouTube / Twitter / Instagram-proxy / Google Trends
signals. Everything is stored in SQLite + Chroma and exposed through a
Streamlit UI with human-in-the-loop and a production-style RAG
(hybrid retrieval + LLM rerank + hallucination guard).

## Quick start

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env       # fill in AI_API_KEY etc.
```

### CLI

```powershell
python run.py init                    # seed websites into SQLite
python run.py categorize              # AI classifies each website
python run.py scrape news_global      # async scrape one field bucket
python run.py trends                  # collect YT / X / IG / Google trends
python run.py index                   # embed scraped pages into Chroma
python run.py ask "viral hooks for AI productivity apps"
python run.py agency "Find a viral video idea in personal finance"
```

### UI

```powershell
streamlit run app.py
```

The sidebar walks through the pipeline (init → categorize → scrape → index
→ collect trends). Tabs let you paste-and-embed knowledge, ask the RAG
system, run the agency on a goal, and browse the SQLite tables.

## Architecture

```
data/websites.json        Curated seed list (news, tech, marketing, trends, etc.)
src/
  config.py               .env-backed settings
  llm/                    Unified OpenAI-compatible client
                          -> works with NVIDIA NIM, OpenRouter, Ollama, llama.cpp, OpenAI
  storage/
    sqlite_store.py       websites, pages (HTML tag preserved!), trending, memory, HITL log
    vector_store.py       Chroma persistent store with NIM embeddings
  scrape/
    seeds.py              Load curated URLs into the DB
    categorizer.py        Batched LLM classification of URLs (token-cheap)
    scraper.py            Async httpx + selectolax; stores `<tag>text</tag>` lines
    trends.py             YouTube / Twitter (trends24) / Instagram-proxy / Google Trends / Reddit
  rag/
    chunker.py            Tag-aware chunking
    retriever.py          Vector recall -> BM25 -> LLM rerank
    rag.py                Generation with citations + hallucination auditor
  memory/
    short_term.py         Per-agent rolling buffer
    long_term.py          Durable facts in SQLite + semantic recall
  hitl/
    human_loop.py         Pluggable handler (CLI default, Streamlit override)
  agency/
    message_bus.py        Pub/sub with full audit log to SQLite
    base_agent.py         RAG-grounded agent base class
    worker_agents.py      Field-specialised researchers
    department_manager.py Field managers, spawn workers
    lead_manager.py       Agency owner: plans, dispatches, synthesises
    orchestrator.py       Bootstrap + run_agency()
```

## Key design notes

- **Token-cheap scraping.** Only structural tags (`title, h1-h3, p, li, a,
  blockquote`) are kept. Scripts/styles/nav are dropped *before* anything
  reaches an LLM. Each line is stored as `<tag>text</tag>` so downstream
  prompts always know whether a fact came from a heading vs. a link.
- **Tag identifier.** `pages.body_html` is the tag-preserved corpus;
  `pages.text` is the cleaned form used for embedding fallback;
  `pages.tags_json` is a structured index per tag.
- **Production RAG.** Hybrid recall (vector + BM25) → LLM relevance
  rerank → constrained generation with `[i]` citations → independent
  hallucination auditor that can downgrade an answer to
  *"I don't know based on the indexed sources."*
- **Multi-provider LLM.** Set `AI_PROVIDER` to `nvidia-nim`,
  `openrouter`, `ollama`, `llama-cpp`, or `openai`. The same code path
  handles all of them through the OpenAI-compatible spec.
- **Human in the loop.** Any agent can call `ask_human()`. The Streamlit
  app turns this into a sidebar prompt queue; the CLI falls back to
  `input()`. Set `HUMAN_IN_THE_LOOP=false` in `.env` to auto-approve.
- **Agency hierarchy.** `LeadManager` plans which fields are needed for
  a goal, instantiates a `DepartmentManager` per field, which in turn
  spawns N `FieldWorker`s that only retrieve from their own field's
  chunks (via Chroma metadata filter). All inter-agent traffic is
  mirrored into `agent_messages` for replay.
- **Manual knowledge injection.** Paste any text in the *Inject
  knowledge* tab → it is chunked, embedded, and stored as a first-class
  RAG source the agents will consult on their next run.
