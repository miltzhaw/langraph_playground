#!/usr/bin/env python3
"""
Example 13: Research Paper Analysis with PROV-AGENT Provenance

Extends example 12 (research_paper_analysis.py) with full PROV-AGENT
instrumentation using the correct Flowcept decorators:

  - @agent_flowcept_task  →  wraps each agent node function
                             produces subtype='agent_task' records (AgentTool)
  - FlowceptLLM           →  wraps every LLM call inside a node
                             produces subtype='llm_task' records (AIModelInvocation)
  - @flowcept             →  wraps the top-level workflow
                             produces the Workflow provenance record
  - get_current_context_task() →  retrieves the TaskObject created by
                             @agent_flowcept_task so FlowceptLLM can set
                             parent_task_id, establishing wasInformedBy

Provenance records produced per workflow run
────────────────────────────────────────────
  subtype='agent_task'   AgentTool          one per graph node
  subtype='llm_task'     AIModelInvocation  one per LLM call inside a node
  subtype=None / 'task'  Task               non-agentic helper calls
  workflow record        Workflow            one for the full pipeline

Each llm_task carries parent_task_id → its enclosing agent_task,
implementing the PROV-AGENT wasInformedBy relationship.

Usage
─────
  # Inside Docker container:
  docker exec spectra-app python examples/13_research_paper_analysis_prov_agent.py papers/paper.pdf

  # With explicit agent id (standalone, no MCP server):
  python 13_research_paper_analysis_prov_agent.py papers/paper.pdf
"""

import sys
import uuid
sys.path.insert(0, '/app')

import json
from datetime import datetime

from langgraph.graph import StateGraph, END

# ── Flowcept imports ──────────────────────────────────────────────────────────
from flowcept import Flowcept
from flowcept.instrumentation.flowcept_decorator import flowcept

# CORRECT: agent_flowcept_task (not flowcept_task) creates AgentTool records
# with subtype='agent_task' and captures agent_id.
# FlowceptLLM wraps every LLM call to create AIModelInvocation records
# with subtype='llm_task' and links them via parent_task_id (wasInformedBy).
# get_current_context_task() retrieves the live TaskObject so FlowceptLLM
# can read the current task_id and agent_id without extra bookkeeping.
from flowcept.instrumentation.flowcept_agent_task import (
    agent_flowcept_task,
    FlowceptLLM,
    get_current_context_task,
)
from flowcept.flowceptor.consumers.agent.base_agent_context_manager import (
    BaseAgentContextManager,
)

# ── Project imports (unchanged from example 12) ───────────────────────────────
from src.agents_realistic.base import MistralAgent
from src.agents.simple import get_collector
from reconstruction.dag_builder import DAGBuilder
from visualization.dag_visualizer import DAGVisualizer
from src.agents.research_paper_agent import (
    ingest_paper,
    search_content,
    extract_key_findings,
    validate_citations,
    map_citation_relationships,
    synthesize_analysis,
    PaperMetadata,
    RESEARCH_TOOLS,
)


# ─────────────────────────────────────────────────────────────────────────────
# Standalone agent_id bootstrap
#
# In a full MCP deployment, BaseAgentContextManager.lifespan() assigns
# agent_id automatically when the MCP server starts.  In standalone scripts
# (no MCP server) we must set it ourselves so that every @agent_flowcept_task
# decorated function captures a meaningful agent_id instead of None.
# ─────────────────────────────────────────────────────────────────────────────
BaseAgentContextManager.agent_id = str(uuid.uuid4())
STANDALONE_AGENT_ID = BaseAgentContextManager.agent_id


# ─────────────────────────────────────────────────────────────────────────────
# Helper: build a FlowceptLLM that is linked to the calling agent_task
# ─────────────────────────────────────────────────────────────────────────────
def _make_flowcept_llm(base_llm):
    """
    Wrap base_llm with FlowceptLLM, pulling parent_task_id and agent_id
    from the thread-local TaskObject created by @agent_flowcept_task.

    This establishes the wasInformedBy relationship between the AgentTool
    (agent_task) and the AIModelInvocation (llm_task) in PROV-AGENT.
    """
    current_task = get_current_context_task()
    return FlowceptLLM(
        base_llm,
        agent_id=current_task.agent_id if current_task else STANDALONE_AGENT_ID,
        parent_task_id=current_task.task_id if current_task else None,
        workflow_id=current_task.workflow_id if current_task else Flowcept.current_workflow_id,
    )


# ─────────────────────────────────────────────────────────────────────────────
# SimpleTool wrapper (unchanged from example 12)
# ─────────────────────────────────────────────────────────────────────────────
class SimpleTool:
    """Thin wrapper that normalises parameter names before calling a tool func."""

    PARAM_MAPPINGS = {
        'ingest_paper':    {'file': 'file_path', 'filepath': 'file_path', 'path': 'file_path'},
        'search_content':  {'query': 'search_query', 'search_term': 'search_query'},
        'extract_findings':{'content': 'paper', 'text': 'paper'},
        'validate_citations':   {'paper': 'paper'},
        'map_relationships':    {'paper': 'paper'},
    }

    def __init__(self, name, description, func):
        self.name = name
        self.description = description
        self.func = func

    def invoke(self, *args, **kwargs):
        if self.name in self.PARAM_MAPPINGS:
            for alias, canonical in self.PARAM_MAPPINGS[self.name].items():
                if alias in kwargs:
                    kwargs[canonical] = kwargs.pop(alias)
                    break
        try:
            return self.func(*args, **kwargs) if args else self.func(**kwargs)
        except TypeError as e:
            err = str(e)
            if 'missing' in err and 'required positional argument' in err:
                try:
                    if len(kwargs) == 1:
                        return self.func(next(iter(kwargs.values())))
                    return self.func()
                except Exception:
                    pass
            return f"Tool execution failed: {err}"
        except Exception as e:
            return f"Tool execution failed: {str(e)}"


# ─────────────────────────────────────────────────────────────────────────────
# Graph node functions — instrumented with @agent_flowcept_task
#
# IMPORTANT: the decorator is applied to the *inner* node functions, not to
# the LangGraph node names.  Each decorated call produces one AgentTool record.
# The MistralAgent.reason_and_act() call inside each node uses _make_flowcept_llm
# to wrap the underlying LLM, so every model invocation is also captured.
#
# For MCP-based deployment the decorator order would be:
#   @mcp.tool()
#   @agent_flowcept_task
#   def my_tool(...): ...
#
# Here (standalone / LangGraph), we use @agent_flowcept_task alone.
# ─────────────────────────────────────────────────────────────────────────────

@agent_flowcept_task
def run_ingestion(state: dict, agent: MistralAgent) -> dict:
    """
    AgentTool: ingest_paper
    Extracts metadata from the PDF at state['paper_path'].
    Produces: subtype='agent_task', activity_id='run_ingestion'
    """
    paper_path = state.get("paper_path", "papers/paper.pdf")

    # Wrap the agent's underlying LLM so the reasoning step is captured
    # as a linked llm_task (AIModelInvocation → wasInformedBy run_ingestion)
    if hasattr(agent, 'llm'):
        agent.llm = _make_flowcept_llm(agent.llm)

    state = agent.reason_and_act(state, f"Extract metadata from {paper_path}")

    paper = ingest_paper(file_path=paper_path)
    state["paper"] = {
        "title":   paper.title,
        "authors": paper.authors,
        "year":    paper.year,
        "abstract":paper.abstract,
        "doi":     paper.doi,
        "pages":   paper.pages,
    }
    return state


@agent_flowcept_task
def run_analysis(state: dict, agent: MistralAgent) -> dict:
    """
    AgentTool: analyse content
    Searches content and extracts key findings.
    Produces: subtype='agent_task', activity_id='run_analysis'
    """
    if not state.get("paper"):
        return state

    if hasattr(agent, 'llm'):
        agent.llm = _make_flowcept_llm(agent.llm)

    state = agent.reason_and_act(state, "Analyze paper content and findings")

    paper = PaperMetadata(
        title=state["paper"]["title"],
        authors=state["paper"]["authors"],
        abstract=state["paper"]["abstract"],
        year=state["paper"]["year"],
        doi=state["paper"]["doi"],
        pages=state["paper"]["pages"],
    )
    search_results = search_content(paper, "methodology")
    findings       = extract_key_findings(paper)

    state["analysis"] = {
        "search_count":     len(search_results),
        "key_contribution": findings["main_contribution"],
        "key_results":      findings["key_results"],
        "impact_score":     findings["impact_score"],
        "citations":        findings["citations_estimated"],
    }
    return state


@agent_flowcept_task
def run_citation(state: dict, agent: MistralAgent) -> dict:
    """
    AgentTool: validate citations and map relationships.
    Produces: subtype='agent_task', activity_id='run_citation'
    """
    if not state.get("paper"):
        return state

    if hasattr(agent, 'llm'):
        agent.llm = _make_flowcept_llm(agent.llm)

    state = agent.reason_and_act(state, "Validate citations and map relationships")

    paper = PaperMetadata(
        title=state["paper"]["title"],
        authors=state["paper"]["authors"],
        abstract=state["paper"]["abstract"],
        year=state["paper"]["year"],
        doi=state["paper"]["doi"],
        pages=state["paper"]["pages"],
    )
    citations     = validate_citations(paper, sample_size=10)
    relationships = map_citation_relationships(paper)

    if citations.get("validation_failed"):
        state["citation_failed"] = True
        state["citation_error"]  = citations.get("error")
    else:
        state["citations"] = {
            "validated":       citations.get("validated", 0),
            "total":           citations.get("total_citations", 0),
            "validation_rate": citations.get("validation_rate", 0.0),
        }
        state["citation_clusters"] = {
            "clusters": relationships.get("clusters", []),
            "total":    relationships.get("total_relationships", 0),
        }
    return state


@agent_flowcept_task
def run_synthesis(state: dict, agent: MistralAgent) -> dict:
    """
    AgentTool: synthesise comprehensive analysis.
    Produces: subtype='agent_task', activity_id='run_synthesis'
    """
    if hasattr(agent, 'llm'):
        agent.llm = _make_flowcept_llm(agent.llm)

    state = agent.reason_and_act(state, "Synthesize comprehensive analysis")

    synthesis     = synthesize_analysis(
        state.get("analysis", {}),
        state.get("citations", {}),
        state.get("citation_clusters", {}),
    )
    state["synthesis"] = synthesis
    return state


# ─────────────────────────────────────────────────────────────────────────────
# Workflow builder
# ─────────────────────────────────────────────────────────────────────────────

def build_research_paper_workflow():
    """
    Build the 4-agent LangGraph workflow.

    Each LangGraph node is a thin lambda that calls the corresponding
    @agent_flowcept_task decorated function, passing the pre-built agent.
    This keeps LangGraph's node signature (state → state) while still
    letting Flowcept capture each node as a separate AgentTool.
    """
    ingestion_agent = MistralAgent("ingestion_agent", "PDF ingestion specialist")
    analysis_agent  = MistralAgent("analysis_agent",  "research content analyzer")
    citation_agent  = MistralAgent("citation_agent",  "citation validator")
    synthesis_agent = MistralAgent("synthesis_agent", "synthesis specialist")

    tools_list = [
        SimpleTool(name=n, description=d["description"], func=d["func"])
        for n, d in RESEARCH_TOOLS.items()
    ]
    for ag in (ingestion_agent, analysis_agent, citation_agent, synthesis_agent):
        ag.tools = tools_list

    graph = StateGraph(dict)

    # LangGraph nodes — thin lambdas so Flowcept sees the decorated functions
    graph.add_node("ingestion", lambda s: run_ingestion(s, ingestion_agent))
    graph.add_node("analysis",  lambda s: run_analysis(s,  analysis_agent))
    graph.add_node("citation",  lambda s: run_citation(s,  citation_agent))
    graph.add_node("synthesis", lambda s: run_synthesis(s, synthesis_agent))

    graph.add_edge("ingestion", "analysis")
    graph.add_edge("analysis",  "citation")
    graph.add_edge("citation",  "synthesis")
    graph.add_edge("synthesis", END)
    graph.set_entry_point("ingestion")

    return graph.compile()


# ─────────────────────────────────────────────────────────────────────────────
# PROV-AGENT post-processing helpers
# ─────────────────────────────────────────────────────────────────────────────

def _print_prov_agent_summary(events: list):
    """Print a structured summary of PROV-AGENT provenance records."""
    agent_tasks = [e for e in events if e.get("subtype") == "agent_task"]
    llm_tasks   = [e for e in events if e.get("subtype") == "llm_task"]
    other_tasks = [e for e in events if e.get("subtype") not in ("agent_task", "llm_task")]

    print(f"\n{'─'*80}")
    print("PROV-AGENT PROVENANCE SUMMARY")
    print(f"{'─'*80}")
    print(f"  Total records     : {len(events)}")
    print(f"  AgentTool records : {len(agent_tasks)}  (subtype='agent_task')")
    print(f"  LLM invocations   : {len(llm_tasks)}   (subtype='llm_task')")
    print(f"  Other tasks       : {len(other_tasks)}")

    if agent_tasks:
        print(f"\n  AgentTool records:")
        for t in agent_tasks:
            duration = (t.get("ended_at", 0) - t.get("started_at", 0))
            print(f"    [{t.get('activity_id', '?')}]  agent_id={t.get('agent_id', '?')[:8]}...  "
                  f"status={t.get('status', '?')}  duration={duration:.3f}s")

    if llm_tasks:
        print(f"\n  AIModelInvocation records (linked via parent_task_id → wasInformedBy):")
        for t in llm_tasks:
            pid = (t.get("parent_task_id") or "none")[:12]
            model = (t.get("custom_metadata") or {}).get("class_name", "?")
            prompt_preview = ""
            used = t.get("used") or {}
            if isinstance(used, dict) and "prompt" in used:
                prompt_preview = str(used["prompt"])[:60].replace("\n", " ")
            print(f"    [llm_interaction]  parent={pid}...  model={model}  "
                  f'prompt="{prompt_preview}..."')

    print(f"{'─'*80}")


def _export_prov_agent_records(events: list, output_path: str):
    """Export PROV-AGENT records to JSON, grouped by subtype."""
    grouped = {
        "workflow_metadata": {
            "workflow_id":   Flowcept.current_workflow_id,
            "campaign_id":   Flowcept.campaign_id,
            "agent_id":      STANDALONE_AGENT_ID,
            "captured_at":   datetime.now().isoformat(),
            "total_records": len(events),
        },
        "agent_tasks":  [e for e in events if e.get("subtype") == "agent_task"],
        "llm_tasks":    [e for e in events if e.get("subtype") == "llm_task"],
        "other_tasks":  [e for e in events if e.get("subtype") not in ("agent_task", "llm_task")],
    }
    with open(output_path, "w") as f:
        json.dump(grouped, f, indent=2, default=str)
    print(f"  ✅ PROV-AGENT records saved: {output_path}")


def _build_provenance_graph_text(events: list) -> str:
    """
    Build a simple text representation of the PROV-AGENT graph showing:
      AgentTool ──wasInformedBy──> AIModelInvocation
    """
    agent_tasks = {e["task_id"]: e for e in events if e.get("subtype") == "agent_task"}
    llm_tasks   = [e for e in events if e.get("subtype") == "llm_task"]

    lines = ["PROV-AGENT Graph (wasInformedBy relationships):", ""]
    for at_id, at in agent_tasks.items():
        lines.append(f"  AgentTool: {at.get('activity_id')} [agent_id={str(at.get('agent_id','?'))[:8]}...]")
        linked = [lt for lt in llm_tasks if lt.get("parent_task_id") == at_id]
        if linked:
            for lt in linked:
                model = (lt.get("custom_metadata") or {}).get("class_name", "LLM")
                lines.append(f"    └─wasInformedBy──> AIModelInvocation [{model}]")
        else:
            lines.append("    └─ (no LLM invocations recorded)")
        lines.append("")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

@flowcept  # marks the whole pipeline as a Workflow in PROV-AGENT
def run_pipeline(paper_path: str) -> dict:
    """Full research paper analysis pipeline with PROV-AGENT provenance."""
    workflow = build_research_paper_workflow()
    return workflow.invoke({"paper_path": paper_path})


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Research Paper Analysis with PROV-AGENT provenance"
    )
    parser.add_argument("paper", nargs="?", default="papers/paper.pdf",
                        help="Path to PDF paper")
    args = parser.parse_args()

    print("\n" + "=" * 100)
    print("EXAMPLE 13: Research Paper Analysis — PROV-AGENT Edition")
    print("=" * 100)
    print(f"\nStandalone agent_id : {STANDALONE_AGENT_ID}")
    print(f"Paper               : {args.paper}\n")

    # ── Legacy event collector (unchanged from example 12) ────────────────
    collector = get_collector()
    collector.clear()
    collector.set_correlation("research_paper_prov_agent_001")

    # ── Build workflow ─────────────────────────────────────────────────────
    print("Building workflow...")
    try:
        # Pre-flight: confirm Flowcept decorators are importable
        from flowcept.instrumentation.flowcept_agent_task import agent_flowcept_task
        print("  ✅ agent_flowcept_task available")
        print("  ✅ FlowceptLLM available")
    except ImportError as e:
        print(f"  ❌ Import failed: {e}")
        print("     Make sure flowcept[llm_agent] is installed.")
        sys.exit(1)

    # ── Run pipeline ───────────────────────────────────────────────────────
    print("\nRunning analysis...")
    try:
        result = run_pipeline(args.paper)
        print("  ✅ Workflow completed\n")
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # ── Read Flowcept events ───────────────────────────────────────────────
    # read_buffer_file() returns all records written to flowcept_messages.jsonl
    # during this run, including agent_task and llm_task subtypes.
    flowcept_events = Flowcept.read_buffer_file()

    # ── PROV-AGENT summary ─────────────────────────────────────────────────
    _print_prov_agent_summary(flowcept_events)

    # ── Provenance graph (text) ────────────────────────────────────────────
    print("\n" + _build_provenance_graph_text(flowcept_events))

    # ── Export PROV-AGENT records ──────────────────────────────────────────
    print("Exporting PROV-AGENT records...")
    _export_prov_agent_records(flowcept_events, "prov_agent_research_paper.json")

    # ── Domain results (unchanged from example 12) ─────────────────────────
    print("\n" + "=" * 100)
    print("RESULTS")
    print("=" * 100)

    if result.get("paper"):
        print(f"\n  📄 Paper  : {result['paper']['title']} ({result['paper']['year']})")
        print(f"     Authors: {', '.join(result['paper']['authors'][:2])}")

    if result.get("analysis"):
        print(f"\n  📊 Analysis:")
        print(f"     Key Contribution : {result['analysis']['key_contribution'][:80]}...")
        print(f"     Impact Score     : {result['analysis']['impact_score']}/10")

    if result.get("citations"):
        vr = result['citations'].get('validation_rate', 0)
        print(f"\n  ✅ Citations: {vr:.1%} validated")
    elif result.get("citation_failed"):
        print(f"\n  ⚠️  Citation validation failed: {result.get('citation_error')}")

    if result.get("citation_clusters"):
        print(f"\n  🔗 Citation Clusters:")
        for cluster in result['citation_clusters'].get('clusters', [])[:3]:
            print(f"     - {cluster.get('name', 'Unknown')}: {cluster.get('papers', 0)} papers")

    if result.get("synthesis"):
        print(f"\n  📝 Synthesis: {result['synthesis'][:200]}...")

    # ── Legacy collector statistics (unchanged from example 12) ───────────
    events = collector.get_events()
    print("\n" + "=" * 100)
    print("LEGACY COLLECTOR STATISTICS (example 12 compatibility)")
    print("=" * 100)
    print(f"  Total events    : {len(events)}")
    if events:
        print(f"  Event types     : {sorted(set(e['event_type'] for e in events))}")
        print(f"  Agents          : {sorted(set(e['agent_id'] for e in events))}")
        print(f"  Reasoning steps : {len([e for e in events if e['event_type'] == 'REASONING_STEP'])}")
        print(f"  Tool invocations: {len([e for e in events if e['event_type'] == 'TOOL_INVOKED'])}")
        print(f"  Failures        : {len([e for e in events if e['event_type'] == 'GOAL_FAILED'])}")

    # ── Causal DAG reconstruction (unchanged from example 12) ─────────────
    print("\n" + "=" * 100)
    print("CAUSAL DAG RECONSTRUCTION")
    print("=" * 100)
    builder = DAGBuilder()
    dag = builder.build(events)
    print(f"\n  ✅ DAG reconstructed:")
    print(f"     Events : {len(events)}")
    print(f"     Edges  : {len(dag.edges)}")
    dag.print_edges()

    # ── Visualisations ─────────────────────────────────────────────────────
    print("\n" + "=" * 100)
    print("GENERATING VISUALISATIONS")
    print("=" * 100)
    try:
        visualizer = DAGVisualizer()
        visualizer.create_html_interactive(
            dag, output_file="research_paper_prov_agent_interactive.html")
        visualizer.create_graphviz(
            dag, output_file="research_paper_prov_agent.dot")
        visualizer.create_mermaid(
            dag, output_file="research_paper_prov_agent_visualization.md")
        visualizer.create_summary_table(
            dag, output_file="research_paper_prov_agent_summary.md")
        print("\n  ✅ Visualisations created:")
        print("     - research_paper_prov_agent_interactive.html")
        print("     - research_paper_prov_agent.dot")
        print("     - research_paper_prov_agent_visualization.md")
        print("     - research_paper_prov_agent_summary.md")
        print("     - prov_agent_research_paper.json")
        print("\n  To copy out of Docker:")
        print("  docker cp spectra-app:/app/research_paper_prov_agent_interactive.html ./")
        print("  docker cp spectra-app:/app/prov_agent_research_paper.json ./")
    except Exception as e:
        print(f"  ⚠️  Visualisation failed: {e}")

    print("\n  ✅ Example 13 completed!")
    print("=" * 100 + "\n")


if __name__ == "__main__":
    main()

