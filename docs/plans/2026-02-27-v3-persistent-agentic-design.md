# V3 Design: Persistent Agentic Extraction with Fallbacks

**Date:** 2026-02-27
**Status:** Approved

---

## Goal

Make the agent persistent (learns from experience), add a tiered extraction strategy ladder (CSS → Playwright → Computer Use), and ensure every failure is graceful with specific, actionable next steps for the user.

---

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Architecture | Strategy Ladder + Agent Memory | Extends existing tool-use agent naturally; each tier is a new tool |
| Extraction tiers | CSS → Playwright → Computer Use | Start cheap, escalate on failure; each tier handles what the previous can't |
| Escalation control | User approves each step | User stays in control; maps to existing confirm/refine/reject flow |
| Agent memory | Persistent structured JSON per domain | Lightweight, no new infrastructure; agent learns over time |
| Failure UX | Layered — plain English + expandable technical details | Non-technical users get actionable buttons; operators can dig into diagnostics |
| Runner changes | Tier-aware + retry + auto-health monitoring | Scheduled runs use the right tier; transient failures get retried; degradation is detected |

---

## Strategy Ladder

### Tier 1 — HTTP + CSS Selectors (existing)

- Tools: `fetch_page` + `extract_with_selectors`
- Cost: ~$0.01/run. Fast.
- Works for: Static HTML pages.
- Fails when: JS-rendered content, login walls, dynamic pagination.

### Tier 2 — Playwright Browser (new)

- New tool: `browse_page(url, actions?)`
- Launches headless Chromium, renders JS, executes actions (click, scroll, wait, fill, paginate), returns rendered HTML + screenshot.
- Cost: ~$0.05/run.
- Works for: JS-heavy sites, SPAs, paginated content.
- Fails when: CAPTCHAs, complex multi-step flows, visual-only content.

### Tier 3 — Computer Use (new)

- New tool: `computer_use(url, instruction)`
- Uses Claude's computer use capability to visually interact with the page — sees screenshots, reasons about UI, clicks/types/scrolls.
- Cost: ~$0.50+/run.
- Works for: Almost anything a human can do.
- Fails when: Login required (credentials needed), rate limits, blocked IP.

### Escalation Flow

```
Agent starts at Tier 1
    → Extraction succeeds → save config with tier: "css"
    → Extraction fails → emit escalation_proposal event
        → User approves → try Tier 2
            → Extraction succeeds → save config with tier: "playwright"
            → Extraction fails → emit escalation_proposal event
                → User approves → try Tier 3
                    → Extraction succeeds → save config with tier: "computer_use"
                    → Extraction fails → emit failure event with next steps
                → User rejects → emit failure event with next steps
        → User rejects → emit failure event with next steps
```

The successful tier is saved in the extraction config. Future scheduled runs use it directly.

---

## Agent Memory

### What's Remembered

| Memory Type | Example | Used For |
|-------------|---------|----------|
| Site profile | "example.com uses React, needs JS rendering" | Skip Tier 1 on known JS sites |
| Strategy outcomes | "CSS selectors failed on day.gov.au, Playwright worked" | Start at the right tier on re-agenting |
| Selector patterns | "Government .gov.au sites typically use .media-release-list" | Suggest selectors faster for similar sites |
| Failure patterns | "This site returns 403 after 10 requests/min" | Rate limit awareness |

### Storage

- New collection: `data/memory/` with files like `site_example.com.json`
- Memory loaded into agent system prompt when working on a related domain
- Append-only with timestamps — agent adds entries, never deletes

### New Agent Tools

- `remember(domain, key, value)` — store a learning about a domain
- `recall(domain)` — load all memories for a domain

Memory is scoped per domain. When the agent works on `homeaffairs.gov.au`, it loads memories for that domain only.

---

## Graceful Failure + Next Steps

Every failure produces: (1) a plain-English user message with action buttons, and (2) expandable technical details.

### Failure Taxonomy

| Failure | User Message | Next Steps | Technical Detail |
|---------|-------------|------------|-----------------|
| Site unreachable | "This site is currently down or blocking requests" | Retry later button, change URL option | HTTP status, headers, timeout info |
| No items found (all tiers) | "We couldn't find extractable content on this page" | Try different page, describe content more | Tier-by-tier failure reasons, screenshots |
| JS-rendered (Tier 1 fail) | "This page loads content with JavaScript" | Approve browser rendering (escalation) | Raw HTML vs rendered diff |
| Login required | "This page requires authentication" | Provide credentials input, try public page | Response code, redirect URL, login form detected |
| Rate limited | "This site is limiting our requests" | Auto-retry scheduled in X minutes | Rate limit headers, retry-after |
| CAPTCHA detected | "This site has bot protection" | Try different approach, manual instructions | CAPTCHA type detected |
| Partial extraction | "Found items but some fields are missing" | Approve partial results or refine selectors | Field-by-field success/failure breakdown |

### Implementation

- New event type: `failure` with structured fields:
  - `failure_code` — machine-readable code (e.g., `site_unreachable`, `no_items`, `login_required`)
  - `user_message` — plain English explanation
  - `next_steps[]` — array of actionable options, each with `type` and `label`
  - `technical_details` — structured diagnostics
- Each next step maps to a UI action (button, input, text)
- Failures are stored in agent memory to avoid repeating the same approach

---

## Automated Runner Changes

### Tier-Aware Execution

Extraction config includes `tier: "css" | "playwright" | "computer_use"`. The runner picks the right execution path.

### Retry with Backoff

On transient failures (HTTP 5xx, timeout), retry up to 3 times with exponential backoff (1s, 4s, 16s).

### Auto Health Monitoring

If a job returns 0 items for 3 consecutive runs:
- Flag job for re-agenting
- Emit `job_health` notification
- Record site change in agent memory

### Partial Success

If extraction gets some fields but not others, save what we got and flag missing fields. Don't treat partial results as total failure.

### New Runner Paths

**Playwright runner:**
- Launch headless Chromium via Playwright
- Execute configured actions (scroll, click, wait for selector)
- Run CSS selectors on rendered DOM
- Return extracted items

**Computer Use runner:**
- Invoke Claude computer use with stored instruction
- Agent visually navigates page, extracts data
- Return structured results

---

## Frontend Changes

### Job Creation Page

- New event renderer for `escalation_proposal` — shows why current tier failed, proposes next tier with approve/reject buttons
- New event renderer for `failure` — card with user message, action buttons, expandable technical details
- When escalation is approved, feed continues from where it left off

### Job Detail Page

- Health indicator: green (last 3 runs OK), yellow (partial), red (failing)
- "Re-discover" button when health is red — launches agent session with loaded memory
- Run history shows which tier was used per run

### Failure Next-Steps Rendering

| Next Step Type | UI Rendering |
|---------------|-------------|
| `retry` | "Try Again" button |
| `escalate` | "Approve [Tier Name]" button |
| `provide_credentials` | Credentials input form |
| `change_url` | URL input field |
| `manual_instructions` | Text block with what to do |

---

## Data Model Changes

### Extraction Config (updated)

```json
{
  "job_id": "job_abc",
  "strategy": "css_selector",
  "tier": "playwright",
  "selectors": { ... },
  "base_url": "https://example.com",
  "playwright_actions": [
    {"action": "wait_for_selector", "selector": ".content"},
    {"action": "scroll", "direction": "bottom"}
  ],
  "computer_use_instruction": null
}
```

### Agent Memory Entry

```json
{
  "domain": "example.com",
  "entries": [
    {
      "key": "site_profile",
      "value": "React SPA, requires JS rendering",
      "created_at": "2026-02-27T10:00:00Z"
    },
    {
      "key": "tier_1_failure",
      "value": "CSS selectors returned 0 items — content loaded via JavaScript",
      "created_at": "2026-02-27T10:01:00Z"
    },
    {
      "key": "tier_2_success",
      "value": "Playwright with scroll + wait worked, found 15 items",
      "created_at": "2026-02-27T10:02:00Z"
    }
  ]
}
```

### Failure Event

```json
{
  "type": "failure",
  "failure_code": "login_required",
  "user_message": "This page requires authentication to access.",
  "next_steps": [
    {"type": "provide_credentials", "label": "Provide login credentials"},
    {"type": "change_url", "label": "Try a different page"}
  ],
  "technical_details": {
    "http_status": 302,
    "redirect_url": "https://example.com/login",
    "login_form_detected": true
  }
}
```

---

## New Dependencies

| Dependency | Purpose |
|------------|---------|
| `playwright` | Headless browser for Tier 2 extraction |
| `anthropic` (computer use) | Claude computer use API for Tier 3 |

---

## Testing

- **Agent memory:** test remember/recall, test domain scoping, test memory loaded into prompts
- **Playwright tool:** test browse_page with mock browser, test action execution
- **Computer use tool:** test with mocked Claude API responses
- **Escalation flow:** test tier 1 fail → proposal → tier 2 → success
- **Failure events:** test each failure type produces correct structured output
- **Runner tiers:** test CSS runner, Playwright runner, Computer Use runner
- **Retry logic:** test exponential backoff on transient failures
- **Health monitoring:** test 3 consecutive failures → re-agent flag
- **Frontend:** manual testing of escalation UI, failure cards, health indicators

---

## Out of Scope

- Credential storage/vault (users provide credentials per-session)
- Proxy/VPN rotation for blocked IPs
- Real database migration (keep file-based JSON)
- Multi-agent orchestration (single agent with multiple tools)
- Authentication (Entra ID SSO — separate work)
