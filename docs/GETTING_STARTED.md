# AgentSwarm — Beginner's Guide

A friendly, zero-jargon walkthrough of what this project is, how it works,
and how to build/run it step by step. If you've never built an AI agent
before, start here.

---

## 1. What is this project, in one paragraph?

AgentSwarm is a tiny **AI agency** living on your computer. You give it a
goal like *"find a viral video idea about personal finance"* and a team
of AI "employees" (a boss, a few managers, and several researchers)
talks to each other, reads from a library of websites you collected,
and hands you back ideas — with sources cited so you can trust them.

Think of it as:

```
You ─► Boss AI ─► Manager AI ─► Researcher AIs ─► Library (websites + notes)
                                                ▲
                                                └── You can interrupt anytime
```

---

## 2. What you need before you start

1. **Python 3.10 or newer.** Check by opening PowerShell and running:
   ```powershell
   python --version
   ```
2. **A code editor.** VS Code is recommended.
3. **An API key for an LLM.** This project supports many; the easiest
   free option is **NVIDIA NIM** (`nvapi-...` keys). You can also use
   OpenRouter, Ollama (fully local), llama.cpp server, or OpenAI.
4. **About 1 GB of free disk** (for the Python packages + the local
   databases that get created as you scrape).

You do **not** need a GPU. You do **not** need Docker.

---

## 3. The 10-minute install

Open PowerShell in the project folder and run:

```powershell
# 1. Create an isolated Python environment (so you don't pollute your system)
python -m venv .venv
.venv\Scripts\activate

# 2. Install every library this project uses
pip install -r requirements.txt

# 3. Copy the example config and open it
copy .env.example .env
notepad .env
```

In `.env`, paste your key into `AI_API_KEY`. Everything else has a
sensible default. Save and close.

---

## 4. The mental model — what's inside?

The project is split into small folders, each with one job. Read this
table once and the rest of the guide will click:

| Folder | What it does (in plain English) |
| --- | --- |
| `data/` | The "filing cabinet". Holds the list of websites and, later, the SQLite database and vector database that get created automatically. |
| `src/config.py` | Reads your `.env` file so the rest of the code knows your API key, model, etc. |
| `src/llm/` | The "phone line" to whichever AI model you chose. One file for chat, one for embeddings. |
| `src/storage/` | Two stores: **SQLite** for plain rows (websites, scraped pages, agent chats, memories) and **Chroma** for the **vector database** (the AI-searchable library). |
| `src/scrape/` | The web-scraping team: loads the seed list, asks the AI to label each site, downloads pages, and grabs trending topics from YouTube/Twitter/Instagram-proxy/Google Trends. |
| `src/rag/` | The "smart librarian": chunks pages, retrieves relevant snippets, reranks them with the AI, and writes a cited answer with a hallucination check. |
| `src/memory/` | Short-term memory (the last few messages) and long-term memory (durable notes + semantic search). |
| `src/hitl/` | "Human in the loop." Lets an agent stop and ask **you** a question. |
| `src/agency/` | The **agents themselves**: the Boss, Managers, Workers, and the message bus they use to talk. |
| `app.py` | The Streamlit web UI you'll actually click around in. |
| `run.py` | A command-line version of the same thing, useful for scripting. |

That's it. Nine folders, all small.

---

## 5. How an "agent" works in this project (no magic)

There is no fancy framework. An agent is just a Python object with:

1. **A name and a role** (e.g. `name="dept-tech_news"`, `role="Department manager for tech"`).
2. **A `think(task)` method** that:
   - Asks the librarian (RAG) for relevant context,
   - Adds a few past messages from short-term memory,
   - Sends everything to the LLM, and
   - Gets a text reply back.
3. **A `send(receiver, topic, body)` method** that drops a message on
   the in-process message bus so another agent can read it.
4. **An `ask_human(question)` method** that pauses and asks you.
5. **A `spawn(name, role, goal)` method** that creates a brand-new agent
   on the fly. This is how the Boss creates Managers, and Managers
   create Workers.

That's the whole agent abstraction — about 60 lines of code in
`src/agency/base_agent.py`.

### The hierarchy

```
LeadManager  (the "agency owner")
   │
   ├── DepartmentManager  (one per topic: tech, marketing, news, ...)
   │       │
   │       ├── FieldWorker  (does the actual research, reads from RAG)
   │       └── FieldWorker
   │
   └── DepartmentManager
           └── FieldWorker
```

When you give a goal to `LeadManager.execute(goal)`:
1. It (optionally) asks you for any constraints.
2. It asks the AI to pick which **fields** (topics) are relevant.
3. For each field, it creates a `DepartmentManager` (or reuses one).
4. Each manager hires N `FieldWorker`s.
5. Each worker queries **only its field's slice** of the vector DB.
6. Workers report back → manager synthesises → boss writes the final answer.

Every message is saved to SQLite, so you can replay the whole
conversation later in the UI's "Browse data" tab.

---

## 6. The data pipeline (from raw web to AI-ready knowledge)

This is the part that confuses beginners the most. Here's what really
happens, in order:

```
[1] websites.json  ──►  SQLite `websites` table        (seed)
[2] AI categorizer ──►  fills the `category` column    (labels each URL)
[3] Async scraper  ──►  SQLite `pages` table           (downloads + cleans)
[4] Chunker        ──►  splits each page into pieces
[5] Embedder       ──►  turns each piece into a vector
[6] Chroma         ──►  stores vectors for semantic search
[7] RAG            ──►  given a question, finds the best pieces and
                        asks the LLM to answer with citations
```

### Why we keep HTML tags

When a page is scraped, we don't store messy HTML. We keep only the
meaningful tags (`<title>`, `<h1>`, `<h2>`, `<h3>`, `<p>`, `<li>`,
`<a>`, `<blockquote>`) and store each line as:

```html
<h1>NVIDIA announces new Llama deployment recipes</h1>
<p>The company said the recipes target enterprise inference...</p>
```

This is the **"tag as identifier"** idea: when an agent reads a snippet
later, it can immediately tell *"this came from a headline"* vs.
*"this came from a body paragraph"* vs. *"this is a link"* — without
re-parsing anything. It also keeps the corpus tiny, so we don't waste
tokens.

### Why we use two databases

- **SQLite** is great at *"give me row 42"* — perfect for storing pages,
  trends, agent messages, HITL logs. It's just a file on disk.
- **Chroma** (the vector DB) is great at *"give me text that **means**
  the same as my question"* — perfect for the RAG search.

The scraper writes to SQLite. The "Index" step copies SQLite pages into
Chroma so the RAG can search them.

---

## 7. RAG explained without the buzzwords

When you ask a question, this happens (see `src/rag/`):

1. **Vector recall** — Chroma returns ~20 snippets whose *meaning* is
   close to your question.
2. **BM25 re-rank** — A classic keyword score boosts snippets that share
   exact words (catches things embeddings miss, like product names).
3. **LLM rerank** — The AI itself scores each snippet 0–10 for "does
   this actually answer the question?" and we keep the top 5.
4. **Constrained generation** — The AI writes an answer using only
   those 5 snippets, with `[0]`, `[1]`, etc. citations.
5. **Hallucination guard** — A *second* AI call inspects the answer and
   asks: *"Is every claim supported by the cited context?"* If not, the
   answer is replaced with `"I don't know based on the indexed sources."`

That last step is what makes this "production-style" — it prevents the
LLM from confidently making things up.

---

## 8. Step-by-step: your first run

After install, do this in order. Each step takes seconds-to-minutes.

### Option A: the web UI (recommended)

```powershell
streamlit run app.py
```

A browser tab opens. On the **left sidebar**, click these buttons top
to bottom:

1. **Init DB + seed websites** — creates the SQLite file and inserts
   the curated website list.
2. **AI categorize websites** — asks the LLM to put each site into a
   category. (Token-cheap: it only sends the URL, not the page.)
3. **Field to scrape → 3. Scrape selected field** — start with
   `tech_news`. The scraper downloads each site in parallel.
4. **Index recent pages → Vector DB** — embeds the scraped pages so the
   RAG can search them.
5. **Collect trending** — pulls YouTube / X / Instagram-proxy / Google
   Trends into the `trending` table.

Now switch to the **tabs at the top**:

- **Inject knowledge** — paste any text (a transcript, a brief, notes)
  and click *Embed and store*. The agency will treat it as a real
  source from now on.
- **Ask RAG** — type a question, hit *Answer*. You'll get a cited
  answer and you'll see whether the hallucination guard flagged it.
- **Run agency** — type a goal like *"Find a viral hook for a 30-second
  Reel about saving money in your 20s"* and click *Run agency*. Watch
  the final deliverable + per-department reports appear.
- **Browse data** — see every table: websites, pages, trends, the full
  agent chat log.

### Option B: the command line

```powershell
python run.py init
python run.py categorize
python run.py scrape tech_news
python run.py index
python run.py trends
python run.py ask "what are people excited about in AI right now?"
python run.py agency "Viral video idea about personal finance for Gen-Z"
```

---

## 9. The `.env` file, demystified

| Setting | What to put | Why |
| --- | --- | --- |
| `AI_PROVIDER` | `nvidia-nim` / `openrouter` / `ollama` / `llama-cpp` / `openai` | Picks which API the LLM client talks to. |
| `AI_API_KEY` | Your `nvapi-...` (or other) key | Authenticates to the provider. |
| `AI_MODEL` | e.g. `meta/llama-3.1-8b-instruct` | The chat model name. Must exist on your chosen provider. |
| `EMBEDDING_MODEL` | e.g. `nvidia/nv-embedqa-e5-v5` | Turns text into vectors for Chroma. |
| `EMBEDDING_DIMENSIONS` | `1024` for NIM's `nv-embedqa-e5-v5` | Must match the model. |
| `HUMAN_IN_THE_LOOP` | `true` or `false` | If true, agents will ask you for input before key actions. |
| `SCRAPE_CONCURRENCY` | `8` | How many websites to download in parallel. Lower if your network is slow. |

### Want a fully local setup? Use Ollama.

1. Install Ollama from <https://ollama.com>.
2. Run `ollama pull llama3.1:8b` and `ollama pull nomic-embed-text`.
3. In `.env`:
   ```
   AI_PROVIDER=ollama
   AI_MODEL=llama3.1:8b
   EMBEDDING_PROVIDER=ollama
   EMBEDDING_MODEL=nomic-embed-text
   EMBEDDING_DIMENSIONS=768
   AI_API_KEY=ollama
   ```
4. Done. No internet needed after that.

---

## 10. How to extend it (the fun part)

### Add a new field of websites
Edit `data/websites.json`, add a new key like `"finance_news"` with a
list of URLs, then re-run **Init DB + seed websites**.

### Add a new trending source
Open `src/scrape/trends.py` and copy one of the existing functions
(e.g. `youtube_trending`). Add it to the dict returned by
`collect_all_trends()`.

### Give a worker a different specialty
In `src/agency/worker_agents.py`, subclass `FieldWorker` and override
`investigate()`. For example, a `HookWriterWorker` could prompt the
LLM specifically for short-form video hooks.

### Plug in a new LLM provider
If it speaks the OpenAI HTTP spec, just add its base URL to
`PROVIDER_BASE_URLS` in `src/config.py`. Done. No client code changes.

### Change how pages are chunked
Edit `chunk_tagged()` in `src/rag/chunker.py`. Smaller chunks =
sharper recall but more vectors; larger chunks = more context per hit.

---

## 11. Troubleshooting

| Symptom | Likely cause / fix |
| --- | --- |
| `openai.AuthenticationError` | `AI_API_KEY` is empty or wrong. |
| Scraper returns 0 pages | Some sites block default user agents. Change `USER_AGENT` in `.env`. |
| RAG says *"I don't know"* every time | You haven't run **Index recent pages** yet, or the question isn't covered by your sources. Paste extra context in the *Inject knowledge* tab. |
| `chromadb` install fails on Windows | You need the latest pip: `python -m pip install --upgrade pip` and Microsoft C++ Build Tools. |
| Streamlit doesn't open the browser | Visit the URL it prints, usually `http://localhost:8501`. |
| Agent runs are slow | Lower `workers_per_dept` in the UI, or switch to a faster/smaller model. |

---

## 12. Glossary (one-line definitions)

- **LLM** — Large Language Model, the thing that writes text (e.g. Llama 3.1).
- **Embedding** — A list of numbers representing the *meaning* of some text. Similar meaning → similar numbers.
- **Vector database** — A store optimized for finding the most similar embedding to a query embedding. We use Chroma.
- **RAG** — Retrieval-Augmented Generation. Look up relevant text first, then ask the LLM to answer using only that text.
- **Chunk** — A small slice of a long document (e.g. ~1200 characters). We embed chunks, not whole pages.
- **Rerank** — A second-pass scoring of search results to push the truly relevant ones to the top.
- **Hallucination guard** — A separate LLM call that verifies the answer is actually supported by the cited context.
- **HITL** — Human In The Loop. The system pauses for your input.
- **Agent** — A Python object with a role, a memory, and the ability to talk to an LLM and to other agents.
- **Message bus** — A simple pub/sub channel agents use to send each other messages.
- **Short-term memory** — The last few messages in the current task.
- **Long-term memory** — Durable notes saved to SQLite + searchable via Chroma.

---

## 13. What to read next, in order

1. [src/config.py](../src/config.py) — see how settings are loaded.
2. [src/llm/provider.py](../src/llm/provider.py) — see one LLM call end-to-end.
3. [src/storage/sqlite_store.py](../src/storage/sqlite_store.py) — see every table the project uses.
4. [src/scrape/scraper.py](../src/scrape/scraper.py) — see the tag-preserving HTML parser.
5. [src/rag/rag.py](../src/rag/rag.py) — see the full RAG pipeline including the hallucination guard.
6. [src/agency/base_agent.py](../src/agency/base_agent.py) — see the entire `Agent` class.
7. [src/agency/lead_manager.py](../src/agency/lead_manager.py) — see how the boss plans and delegates.
8. [app.py](../app.py) — see how the UI wires it all together.

You can read the whole codebase in an afternoon. Have fun.
