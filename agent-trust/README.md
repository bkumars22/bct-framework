# AgentTrust

Behavioral compliance layer for enterprise AI agent registries.

Extends the [BCT Framework](https://github.com/bkumars22/bct-framework) to
test AI agents registered in an enterprise agent registry — the kind of
system that tracks agent metadata, performance, and cost across a fleet of
deployed AI agents.

## The Problem

Performance monitoring exists. Behavioral compliance monitoring does not —
these are different problems, and both need solving.

Performance 97% + Compliance 22% = **the Watermelon Effect.**
Green outside. Red inside.

An agent can pass every performance/latency/cost check a platform already
runs and still violate its own behavioral contract the moment it's put
under adversarial pressure. AgentTrust is the layer that catches that.

## What AgentTrust Adds

| Metric | Performance Monitoring | AgentTrust |
|--------|:---:|:---:|
| Performance | ✅ | ✅ |
| Token consumption | ✅ | ✅ |
| Cost | ✅ | ✅ |
| Behavioral compliance | ❌ | ✅ |
| Breaking point | ❌ | ✅ |
| Watermelon effect | ❌ | ✅ |
| Prompt governance | ❌ | ✅ |
| Chain compliance | ❌ | ✅ |

## Quick Start

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

- Dashboard: `http://localhost:8000/dashboard`
- API docs: `http://localhost:8000/docs`

This runs locally only — there is no hosted/live deployment of AgentTrust
(unlike the core BCT dashboard, which has a static demo on GitHub Pages;
AgentTrust needs a running FastAPI backend, so it can't be served the same
way without a demo-mode static build).

On startup, 4 demo agents are auto-registered and BCT-tested so the
dashboard has real data immediately.

## Architecture

- `core/agent_registry.py` — mock enterprise agent registry (in-memory)
- `core/compliance_engine.py` — runs the real BCT adversarial generator
  (6 categories x 5 intensities) against each agent's contract in
  simulation mode; see the module docstring for the real-LLM swap point
  (`bct.verify()`)
- `core/watermelon_detector.py` — Watermelon Gap and Compliance Gap Score
  (CGS) calculation and alerting
- `core/prompt_governor.py` — AIPQ-pattern prompt versioning: block or
  roll back a prompt change if its adversarial quality score regresses
- `core/chain_tester.py` — multi-agent chain compliance (`min()` across
  the chain, not an average — one weak link fails the whole chain)
- `api/` — FastAPI routes and Pydantic schemas
- `dashboard/index.html` — dependency-free dark-themed dashboard

## API

| Endpoint | Purpose |
|---|---|
| `POST /agents/register` | Register an agent, auto-run BCT |
| `GET /agents` | List all agents with performance + compliance |
| `GET /agents/{id}` | Full agent detail, history, watermelon status |
| `POST /agents/{id}/test` | Re-run BCT on an existing agent |
| `POST /agents/{id}/prompt` | AIPQ governance check on a prompt change |
| `GET /agents/{id}/watermelon` | Watermelon gap + alert level |
| `POST /chains/test` | Multi-agent chain compliance |
| `GET /dashboard/metrics` | Summary stats for the dashboard |

## Tests

```bash
pytest tests/
```

## Built on BCT Framework

https://github.com/bkumars22/bct-framework
