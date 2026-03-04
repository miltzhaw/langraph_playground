#!/usr/bin/env python
"""
Example 12: Research Paper Analysis Pipeline (STRICT MODE, FIXED)
"""

import sys
sys.path.insert(0, '/app')

from langgraph.graph import StateGraph, END
from src.agents_realistic.base import MistralAgent
from src.agents.simple import get_collector

from reconstruction.dag_builder import DAGBuilder
from visualization.dag_visualizer import DAGVisualizer

from src.agents.research_paper_agent import (
    ingest_paper, search_content, extract_key_findings,
    validate_citations, map_citation_relationships, synthesize_analysis,
    PaperMetadata, RESEARCH_TOOLS,
)


def build_research_paper_workflow():
    """Build 4-agent STRICT MODE research paper analysis workflow."""

    ingestion_agent = MistralAgent("ingestion_agent", "PDF ingestion specialist")
    analysis_agent  = MistralAgent("analysis_agent",  "research content analyzer")
    citation_agent  = MistralAgent("citation_agent",  "citation validator")
    synthesis_agent = MistralAgent("synthesis_agent", "synthesis specialist")

    class SimpleTool:
        """
        Deterministic tool wrapper.

        Key design principle: any parameter whose value must be a live Python
        object (PaperMetadata, result dicts) is ALWAYS injected from the
        execution context, never trusted from the LLM response.  The LLM is
        only allowed to supply primitive scalars (file_path, sample_size, query).
        """

        # Parameters that must come from context, not from the LLM.
        # Maps tool_name -> {param_name: context_key}
        CONTEXT_PARAMS = {
            "search_content":    {"paper": "paper_obj"},
            "extract_findings":  {"paper": "paper_obj"},
            "validate_citations": {"paper": "paper_obj"},
            "map_relationships": {"paper": "paper_obj"},
            "synthesize": {
                "findings":      "analysis",
                "citations":     "citations",
                "relationships": "citation_clusters",
            },
        }

        # Only these primitive params are accepted from the LLM per tool.
        LLM_ALLOWED = {
            "ingest_paper":       {"file_path"},
            "search_content":     {"query"},
            "extract_findings":   set(),           # no LLM params needed
            "validate_citations": {"sample_size"},
            "map_relationships":  set(),
            "synthesize":         set(),
        }

        def __init__(self, name, description, func, inputs):
            self.name        = name
            self.description = description
            self.func        = func
            self.inputs      = inputs

        def invoke(self, params: dict, *, context=None):
            params  = dict(params or {})
            name    = self.name
            context = context or {}

            # --- Alias mapping for file_path variations ---
            if name == "ingest_paper":
                for alias in ("file", "filepath", "path"):
                    if alias in params and "file_path" not in params:
                        params["file_path"] = params.pop(alias)

            # --- Keep only LLM-safe primitive params ---
            allowed_from_llm = self.LLM_ALLOWED.get(name, set())
            params = {k: v for k, v in params.items() if k in allowed_from_llm}

            # --- Type coercion for primitives ---
            if name == "validate_citations" and "sample_size" in params:
                try:
                    params["sample_size"] = int(params["sample_size"])
                except Exception:
                    params["sample_size"] = 5

            # --- Inject context-sourced params (always override LLM) ---
            for param_name, ctx_key in self.CONTEXT_PARAMS.get(name, {}).items():
                value = context.get(ctx_key)
                if value is not None:
                    params[param_name] = value

            return self.func(**params)

    # Build tools from registry
    tools = [
        SimpleTool(n, d["description"], d["func"], d["inputs"])
        for n, d in RESEARCH_TOOLS.items()
    ]

    for agent in (ingestion_agent, analysis_agent, citation_agent, synthesis_agent):
        agent.tools = tools

    graph = StateGraph(dict)

    # ------------------------------------------------------------------
    # Nodes
    # ------------------------------------------------------------------

    def ingestion_node(state):
        path  = state.get("paper_path", "papers/paper.pdf")
        state = ingestion_agent.reason_and_act(state, f"Extract metadata from {path}")

        paper = ingest_paper(file_path=path)
        state["paper_obj"] = paper
        state["paper"] = {
            "title":    paper.title,
            "authors":  paper.authors,
            "year":     paper.year,
            "abstract": paper.abstract,
            "doi":      paper.doi,
            "pages":    paper.pages,
        }
        return state

    def analysis_node(state):
        if not state.get("paper_obj"):
            return state

        # FIX point 5: explicit goal tells the agent the paper is already
        # ingested so it does not attempt to call ingest_paper again.
        state  = analysis_agent.reason_and_act(
            state,
            "The paper has already been ingested. "
            "Call extract_findings to extract key findings from the ingested paper. "
            "Do NOT call ingest_paper."
        )
        paper  = state["paper_obj"]

        findings   = extract_key_findings(paper)
        search_res = search_content(paper, "methodology")

        state["analysis"] = {
            "main_contribution": findings["main_contribution"],
            "key_results":       findings["key_results"],
            "impact_score":      findings["impact_score"],
            "citations":         findings["citations_estimated"],
            "search_count":      len(search_res),
        }
        return state

    def citation_node(state):
        if not state.get("paper_obj"):
            return state

        state = citation_agent.reason_and_act(state, "Validate citations and map relationships")
        paper = state["paper_obj"]

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

    def synthesis_node(state):
        # FIX: explicit goal prevents the LLM from planning a multi-step
        # chain starting with validate_citations or map_relationships.
        # All inputs are already in state and will be injected automatically.
        state = synthesis_agent.reason_and_act(
            state,
            "All findings, citations, and relationships are already available. "
            "Call synthesize NOW with findings, citations, and relationships. "
            "Do NOT call validate_citations, map_relationships, or extract_findings."
        )

        # Always call synthesize_analysis directly with state data —
        # the agent's tool invocation above may have failed if the LLM
        # hallucinated bad params, but the node never relies on it.
        syn = synthesize_analysis(
            state.get("analysis",          {}),
            state.get("citations",         {}),
            state.get("citation_clusters", {}),
        )
        state["synthesis"] = syn
        return state

    # ------------------------------------------------------------------
    # Graph wiring
    # ------------------------------------------------------------------
    graph.add_node("ingestion", ingestion_node)
    graph.add_node("analysis",  analysis_node)
    graph.add_node("citation",  citation_node)
    graph.add_node("synthesis", synthesis_node)

    graph.add_edge("ingestion", "analysis")
    graph.add_edge("analysis",  "citation")
    graph.add_edge("citation",  "synthesis")
    graph.add_edge("synthesis", END)

    graph.set_entry_point("ingestion")
    return graph.compile()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Analyze research papers with LLM")
    parser.add_argument("paper", nargs="?", default="papers/paper.pdf",
                        help="Path to PDF paper")
    args = parser.parse_args()

    print("\n" + "=" * 100)
    print("EXAMPLE 12: Research Paper Analysis Pipeline")
    print("=" * 100 + "\n")

    collector = get_collector()
    collector.clear()
    collector.set_correlation("research_paper_001")

    print("Building workflow...")
    try:
        workflow = build_research_paper_workflow()
        print("✅ Workflow built\n")
    except Exception as e:
        print(f"❌ Failed to build workflow: {e}")
        sys.exit(1)

    print("Running analysis...")
    try:
        result = workflow.invoke({"paper_path": args.paper})
        print("✅ Workflow completed\n")
    except Exception as e:
        print(f"❌ Workflow failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    events = collector.get_events()
    collector.print_trace()

    # ------------------------------------------------------------------
    # Results
    # ------------------------------------------------------------------
    print("\n" + "=" * 100)
    print("RESULTS")
    print("=" * 100)

    if result.get("paper"):
        authors = ", ".join(result["paper"]["authors"][:2]) if result["paper"]["authors"] else ""
        print(f"\n📄 Paper: {result['paper']['title']} ({result['paper']['year']})")
        print(f"   Authors: {authors}")

    if result.get("analysis"):
        contrib = result["analysis"].get("main_contribution", "")[:80]
        print(f"\n📊 Analysis:")
        print(f"   Key Contribution: {contrib}...")
        print(f"   Impact Score: {result['analysis']['impact_score']}/10")

    if result.get("citations"):
        rate = result["citations"].get("validation_rate", 0)
        print(f"\n✅ Citations: {rate:.1%} validated")
    elif result.get("citation_failed"):
        print(f"\n⚠️  Citation validation failed: {result.get('citation_error')}")

    if result.get("citation_clusters"):
        print(f"\n🔗 Citation Clusters:")
        for cluster in result["citation_clusters"].get("clusters", [])[:3]:
            print(f"   - {cluster.get('name', 'Unknown')}: {cluster.get('papers', 0)} papers")

    if result.get("synthesis"):
        print(f"\n📝 Synthesis: {result['synthesis'][:200]}...")

    # ------------------------------------------------------------------
    # Execution statistics
    # ------------------------------------------------------------------
    print("\n" + "=" * 100)
    print("EXECUTION STATISTICS")
    print("=" * 100)
    print(f"Total events:      {len(events)}")
    print(f"Event types:       {sorted(set(e['event_type'] for e in events))}")
    print(f"Agents:            {sorted(set(e['agent_id'] for e in events))}")
    print(f"Reasoning steps:   {len([e for e in events if e['event_type'] == 'REASONING_STEP'])}")
    print(f"Tool invocations:  {len([e for e in events if e['event_type'] == 'TOOL_INVOKED'])}")
    print(f"Failures:          {len([e for e in events if e['event_type'] == 'GOAL_FAILED'])}")

    # ------------------------------------------------------------------
    # DAG Reconstruction
    # ------------------------------------------------------------------
    print("\n" + "=" * 100)
    print("CAUSAL DAG RECONSTRUCTION")
    print("=" * 100)

    builder = DAGBuilder()
    dag     = builder.build(events)

    print(f"\n✅ DAG reconstructed:")
    print(f"   Events: {len(events)}")
    print(f"   Edges:  {len(dag.edges)}")
    dag.print_edges()

    # ------------------------------------------------------------------
    # Visualizations
    # ------------------------------------------------------------------
    print("\n" + "=" * 100)
    print("GENERATING VISUALIZATIONS")
    print("=" * 100)

    try:
        visualizer = DAGVisualizer()
        visualizer.create_html_interactive(dag, output_file="research_paper_analysis_interactive.html")
        visualizer.create_graphviz(dag,        output_file="research_paper_analysis.dot")
        visualizer.create_mermaid(dag,         output_file="research_paper_analysis_visualization.md")
        visualizer.create_summary_table(dag,   output_file="research_paper_analysis_summary.md")

        print("\n✅ Visualizations created:")
        print("   - research_paper_analysis_interactive.html")
        print("   - research_paper_analysis.dot")
        print("   - research_paper_analysis_visualization.md")
        print("   - research_paper_analysis_summary.md")
        print("\nTo view: docker cp spectra-app:/app/research_paper_analysis_interactive.html ./")
    except Exception as e:
        print(f"⚠️  Visualization failed: {e}")

    print("\n✅ Example completed!")


if __name__ == "__main__":
    main()