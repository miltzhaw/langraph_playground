# Example 14: Research Paper Analysis — PROV-AGENT Edition

## Overview

Example 14 is the primary PROV-AGENT demonstration. It extends the 4-agent research paper pipeline from Example 12 with full W3C PROV-AGENT instrumentation: every agent tool execution and every Mistral LLM call is captured as a typed provenance record, linked by the `wasInformedBy` relationship defined in the PROV-AGENT model.

Running Example 14 generates the data that powers all four tabs of the Streamlit GUI at `http://localhost:8501`.

---

## What Is Captured vs Example 12

| Aspect | Example 12 | Example 14 |
|--------|-----------|-----------|
| Agent execution | ✅ Legacy collector events | ✅ Legacy collector + Flowcept |
| LLM call captured | No | ✅ FlowceptLLM wrapper |
| Provenance model | SPECTRA semantic events | ✅ W3C PROV-AGENT |
| wasInformedBy links | No | ✅ AgentTool → LLM invocation |
| GUI support | No | ✅ 4-tab Streamlit |
| Output files | HTML/Mermaid/dot/md | + JSONL buffer + PROV-AGENT JSON |

---

## Pipeline Architecture

```
Input: papers/paper.pdf
          │
          ▼
┌─────────────────────────────────────────────────────────────────┐
│  @flowcept  ←── wraps run_pipeline() as a Workflow record       │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ @agent_flowcept_task  run_ingestion                        │  │
│  │   FlowceptLLM(OllamaLLM)  ──wasInformedBy──▶ llm_task    │  │
│  │   ingest_paper(file_path=...)                              │  │
│  └───────────────────────────────────────────────────────────┘  │
│          │                                                       │
│          ▼                                                       │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ @agent_flowcept_task  run_analysis                         │  │
│  │   FlowceptLLM(OllamaLLM)  ──wasInformedBy──▶ llm_task    │  │
│  │   extract_findings(paper=<injected>)                       │  │
│  └───────────────────────────────────────────────────────────┘  │
│          │                                                       │
│          ▼                                                       │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ @agent_flowcept_task  run_citation                         │  │
│  │   FlowceptLLM(OllamaLLM)  ──wasInformedBy──▶ llm_task    │  │
│  │   validate_citations(paper=<injected>)                     │  │
│  └───────────────────────────────────────────────────────────┘  │
│          │                                                       │
│          ▼                                                       │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ @agent_flowcept_task  run_synthesis                        │  │
│  │   FlowceptLLM(OllamaLLM)  ──wasInformedBy──▶ llm_task    │  │
│  │   synthesize(findings, citations, relationships)           │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
          │
          ▼
Output: prov_agent_research_paper.json
        flowcept_buffer.jsonl
        research_paper_prov_agent_interactive.html
```

---

## PROV-AGENT Instrumentation

### The three key components

**`@agent_flowcept_task`** (from `flowcept.instrumentation.flowcept_agent_task`)

Applied to each node function. Creates one `agent_task` record per call with:
- `activity_id`: the function name (e.g. `run_ingestion`)
- `agent_id`: the standalone UUID set at startup via `BaseAgentContextManager.agent_id`
- `used`: the function's input arguments
- `generated`: the function's return value
- `status`: `FINISHED` or `FAILED`
- `started_at` / `ended_at`: Unix timestamps

**`FlowceptLLM(base_llm, agent_id=..., parent_task_id=..., workflow_id=...)`**

Wraps the `OllamaLLM` (Mistral) instance inside each node. Creates one `llm_task` record per `.invoke()` call with:
- `parent_task_id`: the `task_id` of the enclosing `agent_task` — this is the `wasInformedBy` link
- `used.prompt`: the prompt string sent to Mistral
- `generated.response`: Mistral's response text
- `custom_metadata.class_name`: the LLM class name (e.g. `OllamaLLM`)

**`get_current_context_task()`**

Called inside each node to retrieve the live `TaskObject` created by `@agent_flowcept_task`. This is how `FlowceptLLM` reads the correct `task_id` and `agent_id` without manual bookkeeping.

### Wiring pattern

```python
from flowcept.instrumentation.flowcept_agent_task import (
    agent_flowcept_task,
    FlowceptLLM,
    get_current_context_task,
)

def _make_flowcept_llm(base_llm):
    current_task = get_current_context_task()
    return FlowceptLLM(
        base_llm,
        agent_id=current_task.agent_id if current_task else STANDALONE_AGENT_ID,
        parent_task_id=current_task.task_id if current_task else None,
        workflow_id=current_task.workflow_id if current_task else Flowcept.current_workflow_id,
    )

@agent_flowcept_task
def run_ingestion(state: dict, agent: MistralAgent) -> dict:
    if hasattr(agent, 'llm'):
        agent.llm = _make_flowcept_llm(agent.llm)   # ← wrap before reasoning
    state = agent.reason_and_act(state, "Extract metadata from the PDF")
    paper = ingest_paper(file_path=state.get("paper_path"))
    ...
```

The same pattern repeats for `run_analysis`, `run_citation`, and `run_synthesis`.

---

## Running Example 14

```bash
# Standard run with the bundled paper
docker exec spectra-app python examples/14_prov_research_paper_analysis.py papers/paper.pdf

# Analyse your own PDF
docker cp your_paper.pdf spectra-app:/app/papers/
docker exec spectra-app python examples/14_prov_research_paper_analysis.py papers/your_paper.pdf
```

### Expected console output

```
====================================================================================================
EXAMPLE 13: Research Paper Analysis — PROV-AGENT Edition
====================================================================================================

Standalone agent_id : fd693d95-4127-4159-9c0f-f80671340a7e
Paper               : papers/paper.pdf

Building workflow...
  ✅ agent_flowcept_task available
  ✅ FlowceptLLM available

Running analysis...
  ✅ Workflow completed

────────────────────────────────────────────────────────────────
PROV-AGENT PROVENANCE SUMMARY
────────────────────────────────────────────────────────────────
  Total records     : 8
  AgentTool records : 4  (subtype='agent_task')
  LLM invocations   : 4  (subtype='llm_task')
  Other tasks       : 0

  AgentTool records:
    [run_ingestion]  agent_id=fd693d95...  status=FINISHED  duration=1.879s
    [run_analysis]   agent_id=fd693d95...  status=FINISHED  duration=0.026s
    [run_citation]   agent_id=fd693d95...  status=FINISHED  duration=0.018s
    [run_synthesis]  agent_id=fd693d95...  status=FINISHED  duration=0.015s

  AIModelInvocation records (linked via parent_task_id → wasInformedBy):
    [llm_interaction]  parent=...  model=OllamaLLM  prompt="You are ingestion_agent..."
    [llm_interaction]  parent=...  model=OllamaLLM  prompt="You are analysis_agent..."
    [llm_interaction]  parent=...  model=OllamaLLM  prompt="You are citation_agent..."
    [llm_interaction]  parent=...  model=OllamaLLM  prompt="You are synthesis_agent..."
────────────────────────────────────────────────────────────────
```

---

## Output Files

| File | Location | Description |
|------|----------|-------------|
| `flowcept_buffer.jsonl` | `/app/` | Raw Flowcept events, one JSON object per line. Primary GUI data source. |
| `prov_agent_research_paper.json` | `/app/` | Grouped PROV-AGENT export: `agent_tasks`, `llm_tasks`, `other_tasks` arrays plus a metadata header. |
| `research_paper_prov_agent_interactive.html` | `/app/` | Standalone interactive DAG (legacy SPECTRA visualiser). |
| `research_paper_prov_agent.dot` | `/app/` | Graphviz source. Render: `dot -Tpng file.dot -o file.png` |
| `research_paper_prov_agent_visualization.md` | `/app/` | Mermaid diagram source. |
| `research_paper_prov_agent_summary.md` | `/app/` | Tabular summary of events and edges. |

> **Note on the JSON export:** `prov_agent_research_paper.json` is written for offline inspection and is not read by any GUI tab. All four GUI tabs source their data exclusively from `flowcept_buffer.jsonl`.

---

## Understanding the GUI

### Tab 1 — Provenance Graph

This is the main PROV-AGENT view. After a successful Example 14 run you should see:

- One large dark-blue **Workflow** node at the centre
- Four medium blue **AgentTool** nodes (run_ingestion, run_analysis, run_citation, run_synthesis), connected to the Workflow by grey `hadMember` edges
- Four small green **AIModelInvocation** nodes (one per OllamaLLM call), each connected to its parent AgentTool by a green `wasInformedBy` edge
- Sequential green `wasInformedBy` edges chaining the AgentTool nodes in execution order

Hover any node to see its full metadata in the tooltip. The tooltip for an AgentTool shows `Agent ID`, `Status`, `Duration`, `Inputs`, and `Outputs`. The tooltip for an AIModelInvocation shows `Model`, `Duration`, `Prompt` (truncated to 80 chars), and `Response` (truncated to 80 chars).

**What a healthy graph looks like:**

```
Workflow ──hadMember──▶ run_ingestion ──wasInformedBy──▶ LLM [OllamaLLM]
                               │
                        wasInformedBy
                               │
                               ▼
                         run_analysis ──wasInformedBy──▶ LLM [OllamaLLM]
                               │
                        wasInformedBy
                               │
                               ▼
                         run_citation ──wasInformedBy──▶ LLM [OllamaLLM]
                               │
                        wasInformedBy
                               │
                               ▼
                        run_synthesis ──wasInformedBy──▶ LLM [OllamaLLM]
```

**Diagnosing a disconnected LLM node:**

If a green node appears floating with no edge, `parent_task_id` was not set. This means `_make_flowcept_llm()` was called outside an active `@agent_flowcept_task` context (i.e. `get_current_context_task()` returned `None`). Check that the LLM wrapper is created *inside* the decorated function, not before the decorator fires.

### Tab 2 — Causal DAG

Shows the legacy SPECTRA causal DAG reconstructed from the event collector. This view is complementary to Tab 1: Tab 1 shows the PROV-AGENT provenance graph (what Flowcept captured), while Tab 2 shows the SPECTRA causal reconstruction (what the semantic event collector captured).

You will see `GOAL_FAILED` nodes in the DAG even when all four `agent_task` records show `FINISHED` in Tab 1. This is expected: the legacy collector fires a `GOAL_FAILED` event when any intermediate LLM reasoning step does not produce a clean tool invocation, while the Flowcept `@agent_flowcept_task` decorator records the overall function outcome, which succeeds via a direct fallback path.

### Tab 3 — Hallucination Report

Confidence scores for all four agent tools are displayed. With Mistral via OllamaLLM, confidence is not directly exposed by the model API, so the default value of 0.8 is used unless your `MistralAgent` sets it explicitly in `custom_metadata`. To get real confidence values you would need a model endpoint that returns logprobs and propagate them through the agent's return value into the Flowcept record.

The hallucination detector flags events with confidence below configured thresholds. At the default 0.8, you may see MEDIUM or LOW risk flags depending on the detector's threshold configuration.

### Tab 4 — Provenance Chat

The DataFrame shown at the top of this tab contains all 8 records from `flowcept_buffer.jsonl` in a flat tabular format. Useful columns to examine:

| Column | What it tells you |
|--------|------------------|
| `subtype` | `agent_task` or `llm_task` |
| `activity_id` | Function name (`run_ingestion`, `llm_interaction`, etc.) |
| `agent_id` | The standalone UUID set at startup |
| `parent_task_id` | For `llm_task` records: the `task_id` of the enclosing `agent_task` — the wasInformedBy link |
| `duration_s` | Elapsed seconds |
| `used` | JSON of inputs |
| `generated` | JSON of outputs |
| `custom_metadata` | LLM class name and other metadata |

---

## Agents

### run_ingestion

Extracts paper metadata from the PDF. Uses `ingest_paper(file_path)` after Mistral reasons about the goal. This is typically the slowest step (~1–2 seconds) because `ingest_paper` reads and parses the PDF.

### run_analysis

Identifies key findings. Uses `extract_findings(paper)` with the paper object injected from pipeline state. Mistral reasons about what analysis to perform.

### run_citation

Validates citations and maps citation relationships. Uses `validate_citations(paper)`. Note that in the current implementation, citation validation produces results even when the legacy collector records a `GOAL_FAILED`, because the tool has a direct return path in the pipeline state.

### run_synthesis

Compiles the final report. Uses `synthesize(findings, citations, relationships)` with all upstream results injected from state. Produces the synthesis string shown in the RESULTS section of the console output.

---

## Extending Example 14

### Add a new agent stage

1. Write a new node function decorated with `@agent_flowcept_task`
2. Inside it, call `_make_flowcept_llm(agent.llm)` before `agent.reason_and_act()`
3. Add the node to the LangGraph `StateGraph` with `.add_node()` and `.add_edge()`

```python
@agent_flowcept_task
def run_impact(state: dict, agent: MistralAgent) -> dict:
    if hasattr(agent, 'llm'):
        agent.llm = _make_flowcept_llm(agent.llm)
    state = agent.reason_and_act(state, "Assess the paper's research impact")
    state["impact"] = assess_impact(state.get("paper"))
    return state
```

### Expose real LLM confidence

If your Ollama setup supports logprobs, extract them from the LLM response and set them on the Flowcept task:

```python
@agent_flowcept_task
def run_analysis(state: dict, agent: MistralAgent) -> dict:
    current_task = get_current_context_task()
    ...
    response = llm.invoke(prompt)
    if current_task and hasattr(response, 'response_metadata'):
        current_task.custom_metadata = current_task.custom_metadata or {}
        current_task.custom_metadata['confidence'] = response.response_metadata.get('logprob_score', 0.8)
    ...
```

This value will then appear in the Tab 3 confidence gradient table.

### Use a different model

Change `OLLAMA_MODEL` in `docker-compose.yml` and pull the new model:

```bash
# Edit docker-compose.yml: OLLAMA_MODEL: llama3
docker exec spectra-app ollama pull llama3
docker-compose restart app
```

---

## Troubleshooting

### "No provenance records found" in the GUI

The GUI is looking for `flowcept_buffer.jsonl` relative to its working directory. Always launch Streamlit with `cd /app` first:

```bash
docker exec spectra-app bash -c \
  "cd /app && streamlit run visualization/prov_agent_gui.py --server.port 8501 --server.address 0.0.0.0"
```

Or update the **Flowcept JSONL buffer** path in the sidebar to the full absolute path `/app/flowcept_buffer.jsonl`.

### "ModuleNotFoundError: No module named 'reconstruction'"

Add `sys.path.insert(0, '/app')` at the top of `prov_agent_gui.py`, immediately after the docstring and before any project imports.

### LLM nodes appear disconnected in Tab 1

`parent_task_id` was not set on the `llm_task` record. Confirm that `_make_flowcept_llm()` is called *inside* the `@agent_flowcept_task`-decorated function body, and that `get_current_context_task()` returns a non-None value at that point.

### All agent durations are near zero except run_ingestion

This is normal. `run_ingestion` is slow because it reads the PDF. The analysis, citation, and synthesis nodes complete quickly because their tools operate on in-memory Python objects (the paper dict) rather than I/O.

### GOAL_FAILED events appear in Tab 2 but Tab 1 shows all FINISHED

This is expected. The legacy SPECTRA event collector and the Flowcept `@agent_flowcept_task` decorator observe the workflow at different levels. The decorator wraps the entire node function (which has a direct fallback path), while the legacy collector fires events based on LLM reasoning steps that may not cleanly resolve to a single tool call.