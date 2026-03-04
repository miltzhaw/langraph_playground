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
| Real LLM multi-agent reasoning (4 agents, Example 12) | 20 events, 15 edges | ✅ |
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

**Demonstrates real-world multi-agent observability with independent LLM reasoning and robust tool dispatch.**

A 4-agent pipeline processes research papers:

1. **Ingestion Agent** - Extracts metadata from PDF (title, authors, abstract)
2. **Analysis Agent** - Searches content and identifies key findings
3. **Citation Agent** - Validates citations and maps research relationships
4. **Synthesis Agent** - Compiles comprehensive analysis report

Each agent uses **real Mistral LLM reasoning** to independently decide what to do.

#### Quick Start

```bash
# Install wordninja for PDF text cleaning (one-time)
docker exec spectra-app pip install wordninja

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
✅ **Complete Event Tracing** - 20 events captured per run (GOAL_CREATED → REASONING_STEP → TOOL_INVOKED → GOAL_COMPLETED)  
✅ **Tool Invocation Logging** - LLM decisions logged with reasoning snippets  
✅ **Robust Tool Dispatch** - Param whitelisting and context injection prevent LLM hallucinated arguments from causing failures  
✅ **Explicit Agent Goals** - Each agent receives a precise goal string to prevent multi-step chain planning drift  
✅ **Causal DAG** - 15 causal edges reconstructed showing reasoning→decision→outcome chains  
✅ **Full Visualization** - Interactive HTML, Mermaid, Graphviz, and summary formats  

#### Known LLM Behaviour (Mistral 7B)

When using Mistral, the following behaviours are observed and handled:

- **Multi-step planning in a single response** — Mistral often writes a chain of `TOOL_NAME:` blocks in one response. Only the first block is parsed and executed; subsequent blocks are discarded.
- **Hallucinated param values** — The LLM may pass placeholder strings like `<result of ingest_paper>` or fabricated object literals. These are stripped by the param whitelist; real objects are always injected from pipeline state.
- **Tool selection drift** — Without explicit goal strings, agents may select preparation tools (e.g. `validate_citations`) when the goal calls for a downstream tool (e.g. `synthesize`). Each node's goal string is written to prevent this.

#### Real Output Example

```
COLLECTED EVENTS (20 total)
1.  [GOAL_CREATED]     ingestion_agent: Extract metadata from papers/paper.pdf
2.  [REASONING_STEP]   ingestion_agent: Analyzes goal and available tools
3.  [TOOL_INVOKED]     ingestion_agent: ingest_paper(file_path=papers/paper.pdf)
4.  [REASONING_STEP]   ingestion_agent: Processes tool result
5.  [GOAL_COMPLETED]   ingestion_agent: Metadata extracted
6.  [GOAL_CREATED]     analysis_agent:  The paper has already been ingested. Call extract_findings...
7.  [REASONING_STEP]   analysis_agent:  Analyzes goal
8.  [TOOL_INVOKED]     analysis_agent:  extract_findings(paper=<injected>)
9.  [REASONING_STEP]   analysis_agent:  Processes tool result
10. [GOAL_COMPLETED]   analysis_agent:  Findings extracted
...
20. [GOAL_COMPLETED]   synthesis_agent: Final report generated

CAUSAL DAG RECONSTRUCTION
Events: 20
Causal edges: 15
Agents: 4 (all reasoning independently)
Failures: 0

RESULTS
📄 Paper: future internet Article The Cloud-to-Edge-to-IoT Continuum... (2023)
📊 Analysis: When a natural or human disaster occurs time is critical...
✅ Citations: 95.2% validated
🔗 Citation Clusters: Cluster A (5 papers), Cluster B (4 papers)
📝 Synthesis: Contribution: When a natural or human disaster occurs...
```

#### Key Insights

This example shows **why observability matters** in multi-agent systems:

- **Multiple agents reason independently** - Each uses the LLM, not scripted logic
- **LLM hallucinations are contained** - Hallucinated parameters are intercepted at the tool dispatch layer before reaching functions
- **System is robust** - Pipeline nodes have direct fallbacks independent of agent tool events
- **Complete audit trail** - Every decision, reasoning step, and tool invocation is logged
- **Causal reconstruction** - You can trace the entire story: why each agent did what it did

#### Without SPECTRA

```
❌ Workflow failed
❌ Tool invocation failed with unexpected keyword argument
❌ Analysis incomplete
```

#### With SPECTRA

```
✅ ingestion_agent extracted paper metadata with correct file path
✅ analysis_agent called extract_findings directly (not ingest_paper)
✅ citation_agent called validate_citations first (not map_relationships)
✅ synthesis_agent called synthesize with injected state (not placeholder strings)
✅ 0 failures — full pipeline completed

Causal path (per agent):
GOAL_CREATED → REASONING_STEP → TOOL_INVOKED → REASONING_STEP → GOAL_COMPLETED
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
| Event count | 5-10 per scenario | 15-20 | 20 |
| Causal edges | 3-8 | 10-15 | 15 |
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

✅ **LLM Hallucination Contained:** Param whitelisting and context injection prevent hallucinated arguments from causing runtime failures

✅ **Scalable Design:** Rules work for 4 agents; extendable to larger systems

## Limitations

- Single framework (LangGraph proof-of-concept)
- Example 12 uses Mistral LLM; Examples 1-10 use synthetic scenarios
- 4 agents tested (Example 12); 3 agents maximum in synthetic examples
- Explicit causality only (no implicit dependency inference)
- Mistral 7B plans multi-step tool chains but the architecture executes one tool per agent turn; a larger or instruction-tuned model would improve single-step tool selection accuracy
- PDF text quality depends on source encoding; multi-column or scanned PDFs may produce merged words requiring `wordninja` for correction

## Next Steps

- [x] Expand to real LLM-based agent execution (Example 11, 12)
- [x] Multi-agent reasoning with tool tracking (Example 12)
- [x] LLM hallucination containment at tool dispatch layer
- [x] Explicit agent goal strings to prevent tool selection drift
- [ ] Expand to additional frameworks (AutoGen, Crew AI)
- [ ] Privacy-preserving content filtering
- [ ] Larger-scale evaluation (5+ agents)
- [ ] Implicit causality inference
- [ ] Multi-tool-per-turn agent architecture
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