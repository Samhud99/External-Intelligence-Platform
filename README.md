# External Intelligence Platform

AI-powered web monitoring that discovers what to watch and then watches it automatically.

## What it does

EIP uses a two-phase model to monitor external websites for changes:

1. **Discovery (expensive, once)** — An AI agent navigates a target website, figures out its structure, picks the right CSS selectors, and saves a monitoring configuration. If the site uses JavaScript rendering, the agent escalates through a strategy ladder (CSS → Playwright → Computer Use) with user approval at each step.

2. **Automated execution (cheap, recurring)** — A lightweight runner fetches pages on a schedule, extracts data with the saved selectors, detects changes, and flags new items. If the site changes and extraction breaks, the agent re-discovers automatically.

The agent learns from experience — it remembers what worked and what failed per domain, so repeat visits start smarter.

## Features

- **Strategy ladder**: Tiered extraction — HTTP + CSS selectors, headless browser (Playwright), or Claude Computer Use — starting cheap and escalating only when needed
- **Persistent agent memory**: Per-domain knowledge that persists across sessions (site profiles, selector patterns, failure history)
- **Graceful failure**: Structured error messages with plain-English explanations, actionable next-step buttons, and expandable technical diagnostics
- **Live agent feed**: Real-time SSE streaming of agent activity during job setup — see every fetch, extraction test, and decision as it happens
- **Change detection**: Automatic diffing between runs to surface only new items
- **Health monitoring**: Tracks consecutive failures per job, auto-flags for re-discovery after 3 failures
- **Retry with backoff**: Exponential retry (1s, 4s, 16s) on transient HTTP errors

## Tech stack

| Layer | Tech |
|-------|------|
| Backend | Python, FastAPI, SSE streaming |
| AI | Claude (Anthropic API), tool-use agent loop |
| Browser automation | Playwright (headless Chromium) |
| Frontend | React 19, TypeScript, Tailwind CSS, Vite |
| Storage | File-based JSON (no database required) |
| Scheduling | APScheduler with cron expressions |

## Quick start

```bash
# Clone and set up
git clone https://github.com/Samhud99/External-Intelligence-Platform.git
cd External-Intelligence-Platform

# Backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env  # Add your ANTHROPIC_API_KEY
uvicorn eip.main:app --reload

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**.

## How it works

```
User: "Monitor homeaffairs.gov.au for new media releases"
                    │
                    ▼
         ┌─────────────────┐
         │   AI Agent       │  ← Phase 1: Discovery
         │  fetch_page()    │
         │  extract()       │
         │  remember()      │
         │  save_job()      │
         └────────┬────────┘
                  │
                  ▼
         ┌─────────────────┐
         │ Automated Runner │  ← Phase 2: Execution
         │  Fetch → Extract │
         │  Diff → Store    │
         │  (every 4 hours) │
         └─────────────────┘
```

## Project structure

```
eip/
├── agent/
│   ├── setup_agent.py      # Tool-use agent with streaming
│   ├── tools.py             # fetch_page, extract, browse_page, remember, recall
│   ├── browser.py           # Playwright headless browser
│   ├── memory.py            # Persistent per-domain memory
│   ├── events.py            # SSE event types
│   └── provider.py          # Claude API wrapper
├── runner/
│   ├── automated_runner.py  # Tier-aware runner with retry + health monitoring
│   └── change_detector.py   # Diff engine for detecting new items
├── api/
│   ├── jobs.py              # Session-based job creation + SSE endpoints
│   ├── results.py           # Run results API
│   └── sessions.py          # In-memory session manager
├── scheduler/               # APScheduler cron scheduling
├── store/                   # File-based JSON persistence
└── main.py                  # FastAPI app entry point

frontend/src/
├── pages/
│   ├── Dashboard.tsx        # Job grid with status + quick actions
│   ├── JobCreate.tsx        # Live agent feed + proposal review
│   ├── JobDetail.tsx        # Job metadata + health indicator + run history
│   └── ResultsViewer.tsx    # Extracted items table
├── components/
│   ├── AgentFeed.tsx        # Real-time SSE event renderer
│   ├── FailureCard.tsx      # Layered error display with next steps
│   ├── StatusBadge.tsx      # Color-coded status indicators
│   └── ...
└── api/
    ├── client.ts            # Typed REST client
    ├── sse.ts               # EventSource helper
    └── types.ts             # TypeScript interfaces
```

## License

Internal project.
