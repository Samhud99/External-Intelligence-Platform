# Product Requirements Document: RACV External Intelligence Platform

**Document Status:** Draft v0.1
**Author:** AI & Transformation Division
**Date:** 27 February 2026
**Classification:** Internal — RACV Confidential

---

## 1. Executive Summary

Microsoft 365 Copilot and Copilot Studio are powerful tools for internal knowledge work, but they have a fundamental limitation: they cannot reliably scrape, monitor, or ingest external web-based information. This creates a gap for RACV teams who need to continuously monitor the outside world — regulatory changes, travel incidents, brand mentions, market signals, and industry research — and act on that information internally.

The **External Intelligence Platform (EIP)** closes this gap. It provides RACV users with a self-service interface to define external search queries and scheduled monitoring jobs. AI agents execute these queries, gather structured results, and deliver them into the Microsoft Copilot ecosystem where RACV's existing internal AI capabilities can analyse, summarise, and action the information.

The core architectural principle is simple: **data in, never data out.** No sensitive RACV data or internal context leaves the organisation. The platform only retrieves publicly available external information and pipes it inward.

---

## 2. Problem Statement

RACV teams across the organisation currently rely on manual processes to monitor external information sources. Policy analysts periodically check government websites. The travel team manually scans news and advisory sites. Marketing teams have limited visibility into brand mentions. These manual processes are slow, inconsistent, and don't scale.

Copilot Studio can orchestrate internal workflows and analyse documents, but it cannot perform reliable external web scraping, monitor websites for changes, or execute recurring search jobs against public internet sources. This means RACV staff spend significant time on low-value information gathering that should be automated, and they often miss time-sensitive signals entirely.

---

## 3. Proposed Solution

### 3.1 Platform Overview

The External Intelligence Platform is a web application that allows authenticated RACV users to:

1. **Define search queries** — specify what external information they want to monitor, including target sources, keywords, and relevance criteria.
2. **Configure scheduled jobs** — set frequency and timing for recurring searches (cron-style scheduling), from real-time monitoring to daily or weekly digests.
3. **Receive structured results** — retrieved information is normalised into a consistent structured format and delivered into the Microsoft 365 ecosystem (Copilot, Teams, SharePoint) for internal analysis.

### 3.2 Architectural Principle: Data In, Never Data Out

This is the non-negotiable design constraint for the platform.

- **Outbound:** Only search queries and publicly available URLs leave the RACV environment. No internal data, customer information, proprietary analysis, or sensitive context is ever sent externally.
- **Inbound:** External information is gathered, structured, and delivered into RACV's internal environment where Copilot and other internal tools perform all analysis, classification, and decision-support.
- **Separation of concerns:** The external layer gathers. The internal layer thinks.

This architecture is designed to satisfy RACV's cyber security, data governance, and privacy requirements by ensuring the platform functions exclusively as an ingestion mechanism.

### 3.3 AI Agent Strategy: Build Once, Automate Cheaply

The platform uses a two-phase execution model that optimises for both intelligence and cost:

**Phase 1 — Agent-Led Discovery:** When a user creates a new monitoring job, an AI agent (powered by a capable model such as Claude or equivalent) executes the initial query agenically. The agent navigates sources, identifies the right data extraction patterns, determines optimal selectors and parsing strategies, and validates that the results meet the user's intent. This is the expensive, high-intelligence phase.

**Phase 2 — Automated Execution:** Once the agent has successfully completed the initial run and the user has confirmed the results are correct, the platform codifies the agent's approach into a lightweight, deterministic automation — scheduled HTTP requests, DOM selectors, RSS parsing, API calls, or similar low-cost mechanisms. Subsequent runs execute this automation at a fraction of the cost of a full agentic workflow.

**Re-agenting:** If the automation detects that a source has changed structure (e.g. a website redesign), the job is flagged and an agent is re-invoked to re-discover the extraction pattern. The user is notified and the automation is updated.

This approach means RACV pays for AI intelligence once per job setup (and occasionally for maintenance), while ongoing monitoring runs at commodity compute costs.

---

## 4. Use Cases

### 4.1 Regulatory & Government Monitoring

**Persona:** Policy Analyst, Government Relations, Compliance

**Scenario:** A user in RACV's policy team wants to monitor the Australian Department of Home Affairs website for new announcements, policy changes, consultations, and regulatory updates that could impact RACV's operations (insurance regulation, travel policy, immigration changes affecting travel insurance products, etc.).

**Workflow:**

1. User creates a monitoring job targeting homeaffairs.gov.au — specifically the media releases, consultations, and legislation pages.
2. The AI agent performs initial discovery: identifies page structures, announcement patterns, date formats, and content areas.
3. The platform creates a scheduled job (e.g. every 4 hours during business days).
4. When new content is detected, the platform extracts the announcement title, date, summary text, category, and source URL.
5. This structured payload is delivered to a designated Teams channel and/or SharePoint list.
6. A Copilot agent within RACV's environment picks up the new item and performs impact analysis: *"How might this announcement affect RACV's insurance products, member services, or compliance obligations?"*

**Value:** Policy team moves from reactive periodic checking to proactive, near-real-time awareness with AI-assisted impact assessment.

---

### 4.2 Travel Safety & Incident Intelligence

**Persona:** Travel Operations, RACV Travel Consultants, Emergency Response

**Scenario:** RACV sells travel insurance and operates travel booking services. The team needs to be aware of travel safety events globally — not just official government advisories (which are often slow to update), but also emerging incidents reported in news media that may affect RACV customers. The 2024 Laos methanol poisoning is a prime example: it was widely reported in news before Smartraveller issued formal warnings.

**Workflow:**

1. User defines monitoring jobs across multiple source types:
   - **Official:** Smartraveller.gov.au advisories and updates.
   - **News:** Major news outlets and wire services for travel-related incident keywords (poisoning, natural disaster, civil unrest, airline disruption, health outbreak) filtered by geographic regions where RACV customers commonly travel.
   - **Social/forum signals:** Travel forums and social media for early-warning signals.
2. The AI agent establishes extraction patterns for each source type.
3. Scheduled jobs run at appropriate frequencies (official sources daily, news sources every 2 hours, social signals every 30 minutes).
4. Results are structured with location, severity assessment, event type, source credibility indicator, and timestamp.
5. A Copilot agent in RACV's environment receives the feed and:
   - Cross-references against RACV customer booking data to identify potentially affected travellers.
   - Drafts preliminary customer communications for review.
   - Flags items for the travel operations team with recommended response actions.

**Value:** RACV moves from reactive advisory monitoring to proactive multi-source travel intelligence, potentially identifying customer-affecting incidents hours or days before formal government advisories.

---

### 4.3 Brand & Reputation Monitoring

**Persona:** Marketing, Communications, Member Experience

**Scenario:** RACV wants to track every public mention of the RACV brand across social media platforms, news outlets, review sites, and forums to understand brand sentiment, identify emerging issues, and respond to member concerns.

**Workflow:**

1. User configures monitoring for "RACV" across target platforms: X/Twitter, Facebook (public posts/pages), Reddit, Google News, Trustpilot, ProductReview.com.au, Whirlpool forums, and major Australian news outlets.
2. The AI agent maps the search and extraction approach for each platform (API where available, web scraping where necessary).
3. Scheduled jobs run continuously during business hours and at reduced frequency outside hours.
4. Each mention is captured with: platform, author (where public), content text, timestamp, URL, and an initial sentiment tag (positive / neutral / negative / requires review).
5. Results feed into a SharePoint list or Teams channel.
6. A Copilot agent analyses the feed: identifies trending themes, flags urgent negative mentions for the comms team, and produces a daily brand health digest.

**Value:** Replaces expensive third-party social listening tools or supplements them with a customisable, AI-enhanced monitoring capability integrated directly into RACV's Microsoft ecosystem.

---

### 4.4 Market Signal & Price Triggers

**Persona:** Investment Team, Commercial Strategy, Procurement

**Scenario:** A user in RACV's investment or commercial team wants to set up conditional triggers based on external market data — for example, receiving an alert when the price of gold crosses a specific threshold, when fuel prices hit a certain level, or when exchange rates move beyond a defined band.

**Workflow:**

1. User defines a trigger condition: *"Alert me when the spot price of gold exceeds USD $5,000 per ounce."*
2. The AI agent identifies the most reliable free or public data sources for the target metric (e.g. financial data APIs, commodity exchange websites, Reserve Bank feeds).
3. A lightweight polling job is created at the appropriate frequency (e.g. every 15 minutes for market data).
4. The platform evaluates the trigger condition on each poll.
5. When the condition is met, a structured alert is sent to the user via Teams notification and/or email, including the current value, the threshold, the timestamp, and source.
6. Optionally, a Copilot agent can be configured to run a pre-defined analysis: *"Gold has crossed $5,000. Summarise the potential implications for RACV's investment portfolio and insurance reserves."*

**Value:** Eliminates the need for staff to manually monitor market data or set up fragile custom alert scripts. Enables non-technical users to create sophisticated conditional monitoring with natural language.

---

### 4.5 Industry Research & Analyst Report Discovery

**Persona:** Strategy, Innovation, any knowledge worker

**Scenario:** A user wants to stay across the latest research and reports published by consulting firms, analysts, and industry bodies that are relevant to their role — but doesn't have time to check dozens of websites. For example, a strategist wants to know the moment McKinsey, Deloitte, BCG, Gartner, or the Insurance Council of Australia publish new research on topics like mobility, insurance trends, AI adoption, or member experience.

**Workflow:**

1. User defines a set of target sources (consulting firm blogs, research portals, industry body publications) and topic keywords relevant to their role.
2. The AI agent crawls each source, identifies the publication feed structure, and sets up extraction patterns.
3. Scheduled jobs check for new publications daily.
4. When new research is detected, the platform captures: title, publisher, publication date, abstract/summary (where publicly available), topic tags, and URL.
5. The structured result is delivered to the user's Teams or a shared channel.
6. A Copilot agent analyses each new item against the user's role context: *"New Gartner report on insurance technology trends published. Based on your role in AI transformation, here's why this may be relevant and three key takeaways from the available summary."*

**Value:** Turns passive, hit-or-miss research consumption into an active, personalised intelligence feed. Users discover relevant research on the day it's published rather than weeks later (or never).

---

## 5. Functional Requirements

### 5.1 Job Configuration

| Requirement | Description |
|---|---|
| **Source definition** | Users can specify target URLs, domains, or describe sources in natural language. The AI agent resolves these to specific monitorable endpoints. |
| **Query definition** | Users define what information to look for using natural language descriptions, keywords, or structured filters. |
| **Scheduling** | Users select monitoring frequency from presets (real-time, every 15 mins, hourly, every 4 hours, daily, weekly) or define custom cron expressions. |
| **Trigger conditions** | Users can define conditional logic for alerts (threshold-based, change-detected, keyword-matched). |
| **Output destination** | Users select where results are delivered: Teams channel, Teams chat, SharePoint list, email, or Power Automate trigger. |
| **Job management** | Users can pause, resume, edit, duplicate, and delete monitoring jobs. |

### 5.2 AI Agent Capabilities

| Requirement | Description |
|---|---|
| **Source discovery** | Agent can navigate websites, identify content structures, and determine optimal extraction strategies. |
| **Content extraction** | Agent extracts relevant text, metadata, dates, and categorisation from web pages. |
| **Change detection** | Agent can identify what is new or changed since the last check. |
| **Relevance filtering** | Agent applies user-defined relevance criteria to filter noise from signal. |
| **Automation generation** | Agent codifies its discovery into a repeatable, low-cost automation. |
| **Self-healing** | Platform detects extraction failures and re-invokes the agent to update the automation. |

### 5.3 Output & Integration

| Requirement | Description |
|---|---|
| **Structured output** | All results conform to a consistent schema: source, timestamp, title, content summary, URL, category/tags, confidence score. |
| **Microsoft 365 delivery** | Native integration with Teams (adaptive cards), SharePoint (list items), and Power Automate (trigger webhooks). |
| **Copilot handoff** | Results are formatted for consumption by Copilot Studio agents for downstream analysis. |
| **Audit trail** | All job executions, results, and delivery events are logged for governance and troubleshooting. |

---

## 6. Non-Functional Requirements

| Category | Requirement |
|---|---|
| **Security** | No RACV internal data transmitted externally. All external requests contain only search queries and public URLs. Platform operates within RACV's Azure tenant. |
| **Authentication** | Entra ID SSO. Role-based access control for job creation, administration, and viewing. |
| **Data retention** | Retrieved external data retained for a configurable period (default 90 days) within RACV's environment. |
| **Scalability** | Platform should support 500+ concurrent monitoring jobs across the organisation. |
| **Reliability** | Job execution SLA of 99.5% uptime. Failed jobs retry with exponential backoff and alert the user after repeated failures. |
| **Cost management** | Dashboard showing per-job execution costs. Agentic runs vs. automated runs clearly differentiated. Org-wide budget controls. |
| **Compliance** | Platform must comply with RACV's AI governance framework, including model usage policies, data handling standards, and the AI acceptable use policy. |

---

## 7. Technical Architecture (High-Level)

```
┌─────────────────────────────────────────────────────────┐
│                    RACV INTERNAL ENVIRONMENT             │
│                                                         │
│  ┌──────────┐    ┌──────────────┐    ┌───────────────┐  │
│  │  Users    │───▶│  EIP Web App │───▶│  Job Scheduler│  │
│  │          │    │  (Config UI) │    │  & Orchestrator│  │
│  └──────────┘    └──────────────┘    └───────┬───────┘  │
│                                              │          │
│                                    ┌─────────┴────────┐ │
│                                    │                   │ │
│                              ┌─────▼─────┐  ┌─────────▼┐│
│                              │ AI Agent   │  │Automated ││
│                              │ (Phase 1)  │  │Runner    ││
│                              │ Discovery  │  │(Phase 2) ││
│                              └─────┬──────┘  └────┬─────┘│
│                                    │              │      │
│                              ┌─────▼──────────────▼────┐ │
│                              │   Results Store         │ │
│                              │   (Structured Output)   │ │
│                              └─────────┬───────────────┘ │
│                                        │                 │
│            ┌───────────────┬───────────┼────────────┐    │
│            ▼               ▼           ▼            ▼    │
│     ┌──────────┐   ┌────────────┐ ┌────────┐ ┌────────┐ │
│     │  Teams   │   │ SharePoint │ │Power   │ │Copilot │ │
│     │ Channels │   │ Lists      │ │Automate│ │Studio  │ │
│     └──────────┘   └────────────┘ └────────┘ │Agents  │ │
│                                               └────────┘ │
└─────────────────────────────────────────────────────────┘
                         │
                    Only outbound:
                  search queries &
                    public URLs
                         │
                         ▼
              ┌─────────────────────┐
              │   PUBLIC INTERNET   │
              │                     │
              │  Gov websites       │
              │  News outlets       │
              │  Social media       │
              │  Market data feeds  │
              │  Research portals   │
              └─────────────────────┘
```

---

## 8. Cost Model

| Phase | Cost Driver | Frequency | Relative Cost |
|---|---|---|---|
| **Agent discovery** | LLM tokens + compute for agentic web navigation | Once per job setup + on source changes | High ($$) |
| **Automated execution** | HTTP requests, HTML parsing, simple logic | Per schedule (could be hundreds/day) | Very low ($) |
| **Re-agenting** | LLM tokens for re-discovery when sources change | Occasional, event-driven | Medium ($$) |
| **Results delivery** | Microsoft Graph API calls, Teams/SharePoint writes | Per result delivered | Negligible |

The two-phase model means the platform's steady-state operating cost is dominated by cheap automated polling, with occasional spikes for agent-led work. This is significantly more cost-effective than running a full agentic workflow on every scheduled check.

---

## 9. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **Website structure changes break automations** | High | Medium | Self-healing re-agenting mechanism. Automated failure detection with user notification. |
| **Rate limiting or blocking by target sites** | Medium | Medium | Respect robots.txt. Implement polite crawling (rate limiting, appropriate user-agent). Use APIs where available. |
| **Information accuracy/reliability** | Medium | High | Platform delivers raw information with source attribution. All analysis and decision-making happens internally via Copilot. Source credibility indicators in output schema. |
| **Scope creep — users request data-out capabilities** | Medium | High | Hard architectural constraint: no data-out pathway exists. Governance policy enforces this at platform level. |
| **Cost overrun from excessive agentic re-runs** | Low | Medium | Budget controls per job and per user. Alerting on abnormal re-agenting frequency. |
| **Legal/ToS compliance for web scraping** | Medium | Medium | Legal review of target site terms of service. Preference for official APIs and RSS feeds. Configurable source allow-list managed by platform admins. |

---

## 10. Success Metrics

| Metric | Target | Measurement |
|---|---|---|
| **Time to awareness** | Reduce time from external event to internal awareness by 80% | Compare current manual monitoring lag vs. platform-detected timestamps |
| **Active monitoring jobs** | 50+ jobs within 3 months of launch | Platform analytics |
| **Automation conversion rate** | 90%+ of agent-discovered jobs successfully converted to low-cost automations | Phase 1 to Phase 2 conversion tracking |
| **User satisfaction** | Net Promoter Score > 40 from platform users | Quarterly survey |
| **Cost per insight** | < $0.10 per automated check; < $5.00 per agent discovery run | Platform cost dashboard |
| **Copilot integration utilisation** | 70%+ of delivered results are consumed by a downstream Copilot agent | Delivery and consumption logging |

---

## 11. Phased Delivery

### Phase 1 — Foundation (Weeks 1–6)

- Platform infrastructure and authentication.
- Job configuration UI (basic).
- AI agent discovery for static web pages.
- Change detection for single-page sources.
- Teams channel delivery.
- Use Case 4.1 (Government monitoring) as pilot.

### Phase 2 — Expansion (Weeks 7–12)

- Multi-source job support.
- Conditional trigger engine.
- SharePoint and Power Automate delivery.
- Automation generation (Phase 2 runner).
- Use Cases 4.2 (Travel intelligence) and 4.4 (Market triggers).

### Phase 3 — Scale (Weeks 13–18)

- Social media monitoring capabilities.
- Research/publication discovery.
- Copilot Studio agent templates for common analysis patterns.
- Cost management dashboard.
- Self-service job templates and sharing.
- Use Cases 4.3 (Brand monitoring) and 4.5 (Research discovery).

---

## 12. Open Questions

1. **Model selection:** Should the AI agent layer use Claude (via the forthcoming Anthropic enterprise agreement), Azure OpenAI, or a multi-model approach? Cost, capability, and governance implications differ.
2. **Hosting:** Azure Functions + Container Apps within RACV's tenant, or explore a managed platform?
3. **Admin controls:** What level of source allow-listing is required? Should platform admins approve new target domains?
4. **Existing tooling overlap:** Does RACV currently have any social listening or media monitoring contracts that this platform would supplement or replace?
5. **Copilot Studio templates:** Should the platform ship with pre-built Copilot Studio agents for each use case, or provide structured output and let teams build their own analysis agents?

---

*This document is a living draft. Feedback and iteration welcomed from AI Governance Council, Cyber Architecture, and business stakeholders.*
