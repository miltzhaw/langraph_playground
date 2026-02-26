# SPECTRA: Semantic Propagated Events for Causal Trace Reconstruction in Multi-Agent Systems

A minimal implementation of causal trace reconstruction for LLM-based multi-agent systems using LangGraph.

## What This Does

1. **Collects semantic events** from multi-agent LangGraph workflows
2. **Reconstructs causal DAGs** using explicit instrumentation rules
3. **Detects failure propagation** across agent networks
4. **Measures reconstruction accuracy** against ground truth
5. **Identifies minimal telemetry** requirements via ablation study
6. **Persists traces** to PostgreSQL for analysis

## Quick Start

### Prerequisites
- Docker & Docker Compose
- ~5 minutes

### Run

```bash
# Start services (PostgreSQL + app)
docker-compose up

# In another terminal, run examples
docker exec spectra-app python examples/01_simple_agent.py
docker exec spectra-app python examples/04_reconstruct.py
docker exec spectra-app python examples/07_store_in_postgres.py
```

See `docs/QUICKSTART.md` for all 7 examples.

## Key Results

| Metric | Result | Status |
|--------|--------|--------|
| Cascading delegation (3 agents) reconstruction accuracy | 100% | ✅ |
| Essential event types | 2 (GOAL_DELEGATED, REASONING_STEP) | ✅ |
| Failure detection rate | 100% | ✅ |
| Database persistence | Working | ✅ |

## Visualization Examples

See the visualizations in action:

- **[Interactive DAG Visualization](dag_interactive.html)** - Zoom, pan, drag nodes (open in browser)
- **[Mermaid Diagram](dag_visualization.md)** - Embedded graph format for documentation
- **[Summary Table](dag_summary.md)** - Event counts and causal edges by type

## Architecture

```
spectra-playground/
├── src/
│   └── agents/              # LangGraph agent definitions
├── reconstruction/
│   ├── dag_builder.py       # Causal DAG reconstruction
│   └── correlator.py        # Event correlation
├── evaluation/
│   ├── metrics.py           # Reconstruction metrics
│   └── scenarios.py         # Test scenarios
├── storage/
│   └── postgres_backend.py  # PostgreSQL persistence
├── examples/
│   ├── 01_simple_agent.py           # Single agent
│   ├── 02_two_agents.py             # Two-agent delegation
│   ├── 03_delegation.py             # Three-agent cascade
│   ├── 04_reconstruct.py            # DAG reconstruction
│   ├── 05_failure_detection.py      # Failure propagation
│   ├── 06_ablation_study.py         # Minimal telemetry
│   └── 07_store_in_postgres.py      # Database persistence
├── docs/
│   ├── QUICKSTART.md                # Quick start guide
│   └── evaluation_results.md        # Detailed results
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── README.md
```

## Causal Reconstruction Rules

Three explicit rules reconstruct the causal DAG:

### Rule 1: Delegation
```
GOAL_DELEGATED(A → B) → next event in B
```

### Rule 2: Intra-Agent Sequence
```
REASONING_STEP(agent, t1) → REASONING_STEP(agent, t2) where t1 < t2
```

### Rule 3: Gap Completion
```
event(agent, t1) → event(agent, t2) where |t2 - t1| < threshold
```

## Examples

### Run Single Agent
```bash
docker exec spectra-app python examples/01_simple_agent.py
```
Output: 3 semantic events from single agent

### Reconstruct 3-Agent Cascade
```bash
docker exec spectra-app python examples/04_reconstruct.py
```
Output: 9 events, 8 causal edges, DAG visualization

### Visualize DAG (Interactive & Static)
```bash
docker exec spectra-app python examples/08_visualize.py
```
Output: 4 visualization formats:
- **dag_interactive.html** - Interactive visualization (zoom, pan, drag)
- **dag_visualization.dot** - Graphviz format (publication-quality PNG/PDF)
- **dag_visualization.md** - Mermaid diagram (embed in GitHub/markdown)
- **dag_summary.md** - Summary tables

Then view the interactive visualization:
```bash
docker cp spectra-app:/app/dag_interactive.html ./
open dag_interactive.html  # macOS / xdg-open for Linux / start for Windows
```

### Store in PostgreSQL
```bash
docker exec spectra-app python examples/07_store_in_postgres.py
```
Output: Events and edges persisted to database

### Run Ablation Study
```bash
docker exec spectra-app python examples/06_ablation_study.py
```
Output: Identify minimal event types (2 essential)

## Development

### Enter Container
```bash
docker exec -it spectra-app bash
```

### Run Tests
```bash
docker exec spectra-app pytest tests/
```

### View Database
```bash
# Connect to PostgreSQL
docker exec -it spectra-postgres psql -U spectra -d spectra_db

# Inside psql, verify data:
SELECT count(*) FROM semantic_events;  -- Should show 9
SELECT count(*) FROM causal_edges;     -- Should show 8
SELECT event_type, agent_id FROM semantic_events ORDER BY timestamp LIMIT 10;

# Exit
\q
```

Expected output after running example 07:
```
count 
-------
    9

count 
-------
    8

   event_type   | agent_id 
----------------+----------
 REASONING_STEP | agent_a
 GOAL_DELEGATED | agent_a
 REASONING_STEP | agent_b
 GOAL_DELEGATED | agent_b
 REASONING_STEP | agent_c
 REASONING_STEP | agent_c
 REASONING_STEP | agent_c
 REASONING_STEP | agent_b
 REASONING_STEP | agent_a
(9 rows)
```

## Database Schema

### semantic_events
```sql
event_id UUID PRIMARY KEY
event_type VARCHAR(32)
agent_id VARCHAR(64)
timestamp BIGINT
correlation_id VARCHAR(64)
payload JSONB
created_at TIMESTAMP
```

### causal_edges
```sql
from_event_id UUID (FK)
to_event_id UUID (FK)
reason VARCHAR(128)
created_at TIMESTAMP
PRIMARY KEY (from_event_id, to_event_id)
```

## Evaluation Results

See `docs/evaluation_results.md` for detailed results including:
- Reconstruction accuracy across scenarios
- Failure propagation analysis
- Ablation study findings
- Comparison metrics

## Key Findings

✅ **Formal Model Works:** T = (E, A, →, λ) is implementable and effective

✅ **Minimality Proven:** Only 2 event types needed (GOAL_DELEGATED, REASONING_STEP)

✅ **Deterministic:** No LLM-based inference required for reconstruction

✅ **Failure Detection:** Traces root-cause and propagation paths

✅ **Scalable Design:** Rules work for 2-3 agents; extendable to larger systems

## Limitations

- Single framework (LangGraph proof-of-concept)
- Synthetic scenarios only (no real LLM execution)
- 3 agents maximum (tested)
- Explicit causality only (no implicit dependency inference)

## Next Steps

- [ ] Expand to additional frameworks (AutoGen, Crew AI)
- [ ] Real LLM-based agent execution
- [ ] Privacy-preserving content filtering
- [ ] Larger-scale evaluation (5+ agents)
- [ ] Implicit causality inference
- [ ] Paper publication

## Citation

If you use SPECTRA, please cite:

```bibtex
@inproceedings{militano2026spectra,
  title={SPECTRA: Semantic Propagated Events for Causal Trace Reconstruction in Multi-Agent Systems},
  author={Militano, Leonardo},
  booktitle={Proceedings of [Conference]},
  year={2026}
}
```

## License

MIT License - see LICENSE file

## Contact

Leonardo Militano  
Distributed Systems Group, Institute of Computer Science  
Zurich University of Applied Sciences
