# V2 Design: UI & Agent Transparency

**Date:** 2026-02-27
**Status:** Approved

---

## Goal

Add a React frontend and make the agent's discovery process transparent. Users interact via a web UI instead of raw API calls. During job creation, the agent's work streams live to the user, who can review, refine, and approve before the job goes live.

---

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Transparency | Live streaming + review before save | User watches agent work in real-time, then approves/refines the proposal |
| Frontend | React + TypeScript + Vite + Tailwind | Rich interactive UI, good SSE/streaming support, large ecosystem |
| Streaming | Server-Sent Events (SSE) | Real-time server→client with minimal complexity. User messages via POST. |
| UX pattern | Hybrid: search bar → live agent feed → chat refinement | Simple entry point, transparent agent work, natural language refinement |
| Session management | In-memory server-side sessions | Short-lived (< 5 min), no need for persistence |
| UI scope | Full dashboard | Job list, creation flow, job detail, run history, results viewer |

---

## Backend Changes

### New Session-Based Creation Flow

The current `POST /jobs/create` (fire-and-forget) is replaced with a session-based flow:

1. `POST /jobs/create` — accepts `{"request": "..."}`, creates session, starts agent in background, returns `{"session_id": "sess_abc"}`
2. `GET /jobs/create/{session_id}/stream` — SSE stream of agent events
3. `POST /jobs/create/{session_id}/message` — user sends refinement message
4. `POST /jobs/create/{session_id}/confirm` — user approves proposed job
5. `POST /jobs/create/{session_id}/reject` — user rejects, session ends

### Agent Event Types

Events streamed via SSE:

```
event: status
data: {"type": "status", "message": "Fetching https://..."}

event: page_fetched
data: {"type": "page_fetched", "url": "...", "title": "...", "content_length": 45000}

event: thinking
data: {"type": "thinking", "message": "Found 12 article elements..."}

event: extraction_test
data: {"type": "extraction_test", "selectors": {...}, "sample_items": [...], "count": 12}

event: proposal
data: {"type": "proposal", "job": {...}, "config": {...}, "sample_data": [...]}

event: done
data: {"type": "done", "status": "awaiting_confirmation"}

event: error
data: {"type": "error", "message": "..."}
```

### Session Lifecycle

```
User submits prompt → session "running"
    → Agent streams events via SSE
    → Agent reaches proposal → session "awaiting_confirmation"
    → User confirms → job saved → session "completed"
    → OR user sends refinement → agent resumes → session "running"
    → OR user rejects → session "cancelled"
```

Sessions stored in-memory (dict). Short-lived, not persisted.

### Agent Changes

`SetupAgent` gets a new `run_streaming()` method that yields events instead of returning a final result. It pauses after producing a proposal and waits for user input via an asyncio Queue.

The existing `run()` method is preserved for backward compatibility (API-only usage).

### CORS

FastAPI adds CORS middleware for the React dev server (localhost:5173).

---

## Frontend Design

### Pages

**1. Dashboard (`/`)**
- Grid of job cards: name, target URL, status badge, last run, items found, next run
- Quick actions: pause/resume, run now, delete
- "New monitoring job" button

**2. Job Creation (`/jobs/new`)**
- Top: large input field ("What do you want to monitor?") + submit button
- Middle: live activity feed showing agent progress (status messages, page info, extraction previews)
- When proposal arrives: sample data table + proposed schedule + confirm/reject buttons
- Bottom: chat input for natural language refinement
- On confirm: redirects to job detail page

**3. Job Detail (`/jobs/:id`)**
- Job metadata: name, URL, schedule, status, created date
- Run history table: timestamp, items found, new items, status
- Latest results: expandable list of extracted items
- Actions: edit schedule, pause/resume, run now, delete

**4. Results Viewer (`/jobs/:id/results/:runId`)**
- Full item list with is_new badges
- Run metadata: timestamp, runner type, totals

### Tech Stack

React 18, TypeScript, Vite, Tailwind CSS, React Router v6

---

## Project Structure

### Frontend (new)

```
frontend/
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.js
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── api/
│   │   ├── client.ts           # REST API client
│   │   └── sse.ts              # EventSource helper
│   ├── pages/
│   │   ├── Dashboard.tsx
│   │   ├── JobCreate.tsx
│   │   ├── JobDetail.tsx
│   │   └── ResultsViewer.tsx
│   └── components/
│       ├── Layout.tsx
│       ├── JobCard.tsx
│       ├── AgentFeed.tsx
│       ├── ExtractionPreview.tsx
│       ├── ChatInput.tsx
│       └── StatusBadge.tsx
```

### Backend (modified)

```
eip/
├── api/
│   ├── jobs.py          # Modified: session-based creation
│   └── sessions.py      # New: session management + SSE
├── agent/
│   ├── setup_agent.py   # Modified: add run_streaming()
│   └── events.py        # New: event dataclasses
└── main.py              # Modified: CORS, session routes
```

---

## Testing

- Backend: test SSE stream yields correct event sequence (mock provider), test session lifecycle (create/confirm/reject/refine), test refinement messages resume agent
- Frontend: manual testing via UI for PoC
- E2E: extend test_e2e.py to cover session-based creation flow

---

## Out of Scope

- Authentication (Entra ID SSO)
- Multi-tenancy
- Production deployment (Docker, CI/CD)
- Mobile responsiveness (desktop-first for PoC)
- Frontend unit tests
