# SPECTRA: Semantic Propagated Events for Causal Trace Reconstruction in Multi-Agent Systems

A minimal implementation of causal trace reconstruction for LLM-based multi-agent systems using LangGraph, extended with full **PROV-AGENT** provenance capture and an interactive Streamlit GUI.

---

## What This Does

1. **Collects semantic events** from multi-agent LangGraph workflows
2. **Reconstructs causal DAGs** using explicit instrumentation rules
3. **Captures agentic provenance** via PROV-AGENT (W3C PROV + MCP extension)
4. **Records LLM invocations** linking every Mistral call to the agent tool that triggered it
5. **Detects failure propagation** and hallucination risk across agent networks
6. **Visualises everything** in an interactive Streamlit GUI at `http://localhost:8501`
7. **Persists traces** to MongoDB (Flowcept) and PostgreSQL for offline analysis

---

## Quick Start

### Prerequisites

- Docker & Docker Compose
- ~5 minutes for Mistral download (first run only)

### Start services

```bash
docker-compose up -d
```

### Download Mistral (one-time)

```bash
docker exec spectra-app ollama pull mistral
docker exec spectra-app ollama list   # verify
```

### Run the full PROV-AGENT pipeline

```bash
docker exec spectra-app python examples/14_prov_research_paper_analysis.py papers/paper.pdf
```

### Launch the GUI

```bash
docker exec spectra-app bash -c \
  "cd /app && streamlit run visualization/prov_agent_gui.py \
   --server.port 8501 --server.address 0.0.0.0"
```

Open **http://localhost:8501** in your browser.

---

## Key Results

| Metric | Result | Status |
|--------|--------|--------|
| Cascading delegation (3 agents) reconstruction accuracy | 100% | ✅ |
| Real LLM multi-agent reasoning (4 agents, Example 14) | 8 records, 4 AgentTools + 4 LLM invocations | ✅ |
| PROV-AGENT wasInformedBy links captured | 4 (one per agent–LLM pair) | ✅ |
| Essential event types | 2 (GOAL_DELEGATED, REASONING_STEP) | ✅ |
| Failure detection rate | 100% | ✅ |
| Streamlit GUI | Working at localhost:8501 | ✅ |

---

## Architecture

```
spectra-playground/
├── src/
│   ├── agents/                      # LangGraph agent definitions
│   └── agents_realistic/
│       └── base.py                  # MistralAgent (wraps OllamaLLM)
├── reconstruction/
│   ├── dag_builder.py               # Causal DAG reconstruction
│   └── correlator.py                # Event correlation
├── visualization/
│   ├── prov_agent_gui.py            # Streamlit GUI (4 tabs)
│   ├── prov_agent_models.py         # ProvAgentMetadata dataclass
│   ├── prov_agent_converter.py      # Flowcept → PROV-AGENT converter
│   ├── prov_agent_hallucination_detector.py
│   └── dag_visualizer.py            # HTML/Graphviz/Mermaid export
├── examples/
│   ├── 01–10_*.py                   # Synthetic proof-of-concept examples
│   ├── 11_realistic_with_visualization.py
│   ├── 12_research_paper_analysis.py
│   ├── 13_prov_agent_spectra.py     # PROV-AGENT + synthetic agents
│   └── 14_prov_research_paper_analysis.py   # ← primary example
├── docker-compose.yml
└── requirements.txt
```

---

## PROV-AGENT Model

PROV-AGENT extends W3C PROV with Model Context Protocol (MCP) concepts to capture AI agent interactions as first-class provenance objects.

```
Workflow
  └── hadMember ──▶ AgentTool (subtype=agent_task)
                       └── wasInformedBy ──▶ AIModelInvocation (subtype=llm_task)
                                                └── used ──▶ Prompt
                                                └── generated ──▶ ResponseData
                                                └── wasAssociatedWith ──▶ AIAgent
```

### Key decorators

| Decorator / wrapper | What it captures | Flowcept subtype |
|---------------------|-----------------|-----------------|
| `@agent_flowcept_task` | One AgentTool per decorated function — inputs, outputs, duration, agent_id | `agent_task` |
| `FlowceptLLM(base_llm, ...)` | One AIModelInvocation per `.invoke()` call — prompt, response, model metadata | `llm_task` |
| `get_current_context_task()` | Retrieves the live TaskObject so FlowceptLLM can set `parent_task_id` | (links the two above) |
| `@flowcept` | Wraps the top-level function as a Workflow record | workflow |

The `parent_task_id` field on every `llm_task` record is what establishes the **wasInformedBy** relationship in the provenance graph.

---

## Provenance Files

Example 14 writes two files into `/app`:

| File | Contents | Used by |
|------|----------|---------|
| `flowcept_buffer.jsonl` | Raw Flowcept events (all subtypes) — the GUI's primary data source | GUI sidebar: *Flowcept JSONL buffer* |
| `prov_agent_research_paper.json` | Grouped PROV-AGENT export (agent_tasks / llm_tasks / other) | Reference / offline analysis |

> **Note:** The GUI reads exclusively from the JSONL buffer. The JSON export is for offline inspection and is not consumed by any GUI tab.

---

## Examples

### Synthetic proof-of-concept (Examples 1–10)

```bash
docker exec spectra-app python examples/01_simple_agent.py     # 3 events, 1 agent
docker exec spectra-app python examples/04_reconstruct.py      # 9 events, 8 edges
docker exec spectra-app python examples/06_ablation_study.py   # minimal telemetry
docker exec spectra-app python examples/07_store_in_postgres.py
```

### Realistic LLM workflow (Examples 11–12)

```bash
docker exec spectra-app python examples/11_realistic_with_visualization.py
docker exec spectra-app python examples/12_research_paper_analysis.py papers/paper.pdf
```

### Full PROV-AGENT pipeline (Example 14 — primary)

```bash
docker exec spectra-app python examples/14_prov_research_paper_analysis.py papers/paper.pdf
```

Produces 8 provenance records:

- 4 `agent_task` records: `run_ingestion`, `run_analysis`, `run_citation`, `run_synthesis`
- 4 `llm_task` records: one OllamaLLM invocation linked to each agent tool

---

## Causal Reconstruction Rules

| Rule | Pattern | Purpose |
|------|---------|---------|
| Delegation | `GOAL_DELEGATED(A → B)` → first event in B | Cross-agent causality |
| Intra-agent sequence | `REASONING_STEP(agent, t1)` → `REASONING_STEP(agent, t2)` where t1 < t2 | Per-agent reasoning chain |
| Gap completion | event(agent, t1) → event(agent, t2) where `|t2−t1| < Δt` | Fills disconnected components |

---

## Comparing Synthetic vs Real LLM

| Aspect | Synthetic (Ex 1–10) | Realistic (Ex 11–12) | PROV-AGENT (Ex 14) |
|--------|---------------------|----------------------|-------------------|
| LLM reasoning | None (hardcoded) | ✅ Mistral | ✅ Mistral |
| Provenance model | Legacy collector | Legacy collector | ✅ W3C PROV-AGENT |
| LLM invocation captured | No | No | ✅ wasInformedBy |
| GUI support | No | No | ✅ 4-tab Streamlit |
| Hallucination analysis | No | No | ✅ confidence-based |
| Execution time | <1s | 60–90s | 60–90s |

---

## Database Schema

### semantic_events (PostgreSQL — legacy collector)

```sql
event_id        UUID PRIMARY KEY
event_type      VARCHAR(32)
agent_id        VARCHAR(64)
timestamp       BIGINT
correlation_id  VARCHAR(64)
payload         JSONB
created_at      TIMESTAMP
```

### causal_edges (PostgreSQL)

```sql
from_event_id   UUID (FK → semantic_events)
to_event_id     UUID (FK → semantic_events)
reason          VARCHAR(128)
created_at      TIMESTAMP
PRIMARY KEY (from_event_id, to_event_id)
```

Flowcept also writes to **MongoDB** (`flowcept_db`) for its own query agent and buffer reads.

---

## Known Mistral 7B Behaviours

- **Multi-step planning in one response** — Mistral often writes a chain of `TOOL_NAME:` blocks. Only the first is executed; the rest are discarded.
- **Hallucinated parameter values** — Placeholder strings like `<result of ingest_paper>` are stripped at the tool dispatch layer; real objects are always injected from pipeline state.
- **Tool selection drift** — Without explicit goal strings, agents may call a preparation tool when a downstream one is intended. Each node's goal string is written to prevent this.

---

## Limitations

- Single framework (LangGraph proof-of-concept)
- Mistral 7B tested; a larger instruction-tuned model would improve single-step tool selection
- Explicit causality only — no implicit dependency inference
- 4 agents tested in PROV-AGENT examples; synthetic examples cover up to 3

---

## Next Steps

- [x] Real LLM-based agent execution (Examples 11, 12)
- [x] Full PROV-AGENT provenance with wasInformedBy (Example 14)
- [x] Interactive Streamlit GUI with hallucination analysis
- [ ] Extend to AutoGen / CrewAI frameworks
- [ ] Privacy-preserving content filtering
- [ ] Larger-scale evaluation (5+ agents, 50+ events)
- [ ] Implicit causality inference
- [ ] Multi-tool-per-turn agent architecture

---

## Citation

```bibtex
@inproceedings{militano2026spectra,
  title={SPECTRA: Semantic Propagated Events for Causal Trace Reconstruction in Multi-Agent Systems},
  author={Militano, Leonardo},
  booktitle={Proceedings of [Conference]},
  year={2026}
}
```

## License

MIT License — see LICENSE file

## Contact

Leonardo Militano
Distributed Systems Group, Institute of Computer Science
Zurich University of Applied Sciences