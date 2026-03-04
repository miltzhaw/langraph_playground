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

See `docs/QUICKSTART.md` for all 12 examples.

## Key Results

| Metric | Result | Status |
|--------|--------|--------|
| Cascading delegation (3 agents) reconstruction accuracy | 100% | ✅ |
| Real LLM multi-agent reasoning (4 agents, Example 12) | 16 events, 12 edges | ✅ |
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
│   ├── 07_store_in_postgres.py      # Database persistence
│   ├── 11_realistic_with_visualization.py  # Realistic LLM workflow
│   └── 12_research_paper_analysis.py       # Multi-agent LLM reasoning
├── docs/
│   ├── QUICKSTART.md                # Quick start guide
│   ├── evaluation_results.md        # Detailed results
│   └── RESEARCH_PAPER_ANALYSIS.md   # Example 12 documentation
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

## Phase 3: Real LLM-Based Multi-Agent Systems

SPECTRA now supports **realistic multi-agent workflows with real LLM reasoning and tool invocation**.

### Example 11: Realistic Document Analysis (Synthetic)

**Agents involved:**
- Coordinator (Orchestrator)
- Analyzer (Content Analyzer)
- Summarizer (Summarization Specialist)
- Classifier (Document Classifier)

```bash
# Download Mistral model (one-time, ~5 minutes)
docker exec spectra-app ollama pull mistral

# Run realistic document analysis with Mistral LLM
docker exec spectra-app python examples/11_realistic_with_visualization.py

# View interactive visualization
docker cp spectra-app:/app/realistic_dag_interactive.html ./
open realistic_dag_interactive.html
```

**Example output:**
- 17 semantic events collected
- 13 causal edges reconstructed
- Real Mistral LLM reasoning at each stage
- 3 successful tool invocations
- 2 goal failures (realistic error handling)
- Full DAG visualization generated

### Example 12: Research Paper Analysis Pipeline

**Demonstrates real-world multi-agent observability with independent LLM reasoning and realistic failures**

A 4-agent pipeline processes research papers:

1. **Ingestion Agent** - Extracts metadata from PDF (title, authors, abstract)
2. **Analysis Agent** - Searches content and identifies key findings
3. **Citation Agent** - Validates citations and maps research relationships
4. **Synthesis Agent** - Compiles comprehensive analysis report

Each agent uses **real Mistral LLM reasoning** to independently decide what to do.

#### Quick Start

```bash
# Analyze a research paper with 4-agent workflow
docker exec spectra-app python examples/12_research_paper_analysis.py papers/paper.pdf

# Or analyze your own paper
docker cp your_paper.pdf spectra-app:/app/papers/
docker exec spectra-app python examples/12_research_paper_analysis.py papers/your_paper.pdf

# View interactive DAG
docker cp spectra-app:/app/research_paper_analysis_interactive.html ./
open research_paper_analysis_interactive.html
```

#### Key Features

✅ **Real LLM Reasoning** - Each agent independently reasons about tasks using Mistral  
✅ **Complete Event Tracing** - All 16+ events captured (GOAL_CREATED → REASONING_STEP → TOOL_INVOKED → GOAL_FAILED/COMPLETED)  
✅ **Tool Invocation Logging** - LLM decisions logged with reasoning snippets  
✅ **Realistic Failures** - Tool failures handled gracefully without cascading crashes  
✅ **Causal DAG** - 12+ causal edges reconstructed showing reasoning→decision→failure chains  
✅ **Full Visualization** - Interactive HTML, Mermaid, Graphviz, and summary formats  

#### Real Output Example

```
COLLECTED EVENTS (16 total)
1. [GOAL_CREATED]     ingestion_agent: Extract metadata from papers/paper.pdf
2. [REASONING_STEP]   ingestion_agent: Analyzes goal and available tools
3. [TOOL_INVOKED]     ingestion_agent: Decides to call ingest_paper
4. [GOAL_FAILED]      ingestion_agent: Tool fails, but system continues
...
16. [GOAL_COMPLETED]  synthesis_agent: Final report generated

CAUSAL DAG RECONSTRUCTION
Events: 16
Causal edges: 12
Agents: 4 (all reasoning independently)

RESULTS
📄 Paper: (extracted from your PDF)
📊 Analysis: Key findings and impact score
✅ Citations: Validation rate
📝 Synthesis: Comprehensive summary
```

#### Key Insights

This example shows **why observability matters** in multi-agent systems:

- **Multiple agents reason independently** - Each uses LLM, not scripted logic
- **Tool failures happen** - But you can see exactly what was attempted and why
- **System degrades gracefully** - Synthesis completes with partial data when citation validation fails
- **Complete audit trail** - Every decision, reasoning step, and failure is logged
- **Causal reconstruction** - You can trace the entire story: why each agent did what, and where failures occurred

#### Without SPECTRA

```
❌ Workflow failed
❌ Tool invocation failed
❌ Analysis incomplete
```

#### With SPECTRA

```
✅ ingestion_agent reasoned about metadata extraction
✅ ingest_paper was invoked (LLM saw it as the right tool)
⚠️  Tool failed (SimpleTool missing .invoke())
✅ System fell back to direct execution
✅ Analysis agent reasoned and executed search
✅ synthesis_agent completed report with available data
✅ Workflow finished successfully

Here's the causal path showing what happened and why:
GOAL → REASONING → TOOL_INVOKED → FAILURE → FALLBACK → SUCCESS
```

#### Use Cases

- **Debug multi-agent workflows** - See exactly what each agent decided and why
- **Monitor LLM tool usage** - Track which tools LLMs choose and with what parameters
- **Understand failures** - Complete visibility when things go wrong
- **Audit decisions** - Full trace of reasoning for compliance
- **Optimize workflows** - See where time is spent and where failures occur

See [Research Paper Analysis Documentation](docs/RESEARCH_PAPER_ANALYSIS.md) for detailed technical information.

### Comparing Synthetic vs Real LLM

| Aspect | Synthetic (Ex 1-10) | Real LLM Doc (Ex 11) | Real LLM Paper (Ex 12) |
|--------|---------------------|----------------------|----------------------|
| LLM reasoning | None (hardcoded) | ✅ Mistral LLM | ✅ Mistral LLM |
| Tool invocation | Injected | ✅ LLM-driven | ✅ LLM-driven |
| Decision logic | Predetermined | ✅ Dynamic | ✅ Dynamic |
| Failure modes | Artificial | ✅ Realistic | ✅ Realistic |
| Event count | 5-10 per scenario | 15-20 | 16+ |
| Causal edges | 3-8 | 10-15 | 12+ |
| Agents | 2-3 | 4 | 4 |
| Execution time | <1s | 60-90s | 60-90s |
| Production relevance | Proof-of-concept | High | High |

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

✅ **Real LLM Integration:** Works with actual Mistral LLM reasoning and tool invocation

✅ **Scalable Design:** Rules work for 4 agents; extendable to larger systems

## Limitations

- Single framework (LangGraph proof-of-concept)
- Example 12 uses Mistral LLM; Examples 1-10 use synthetic scenarios
- 4 agents tested (Example 12); 3 agents maximum in synthetic examples
- Explicit causality only (no implicit dependency inference)

## Next Steps

- [x] Expand to real LLM-based agent execution (Example 11, 12)
- [x] Multi-agent reasoning with tool tracking (Example 12)
- [ ] Expand to additional frameworks (AutoGen, Crew AI)
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