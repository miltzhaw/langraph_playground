#!/usr/bin/env python
"""Example 12: Research Paper Analysis with Real LLM - FIXED"""

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
    PaperMetadata, RESEARCH_TOOLS
)


def build_research_paper_workflow():
    """Build 4-agent research paper analysis workflow."""
    
    ingestion_agent = MistralAgent("ingestion_agent", "PDF ingestion specialist")
    analysis_agent = MistralAgent("analysis_agent", "research content analyzer")
    citation_agent = MistralAgent("citation_agent", "citation validator")
    synthesis_agent = MistralAgent("synthesis_agent", "synthesis specialist")
    
    # Minimal wrapper class for tools with invoke method
    class SimpleTool:
        def __init__(self, name, description, func):
            self.name = name
            self.description = description
            self.func = func
        
        def invoke(self, *args, **kwargs):
            """Execute the tool with provided parameters"""
            # Parameter name mappings - map what agents send to what functions expect
            param_mappings = {
                'ingest_paper': {
                    'file': 'file_path',
                    'filepath': 'file_path',
                    'path': 'file_path',
                },
                'search_content': {
                    'query': 'search_query',
                    'search_term': 'search_query',
                },
                'extract_findings': {
                    'content': 'paper',
                    'text': 'paper',
                },
                'validate_citations': {
                    'paper': 'paper',
                },
                'map_relationships': {
                    'paper': 'paper',
                },
            }
            
            # Apply parameter mappings
            if self.name in param_mappings:
                mappings = param_mappings[self.name]
                for provided_name, expected_name in mappings.items():
                    if provided_name in kwargs:
                        kwargs[expected_name] = kwargs.pop(provided_name)
                        break  # Only map first matching alias
            
            try:
                # Try calling with the parameters
                if args:
                    return self.func(*args, **kwargs)
                else:
                    return self.func(**kwargs)
            except TypeError as e:
                error_str = str(e)
                # If missing arguments, try to be smart about it
                if 'missing' in error_str and 'required positional argument' in error_str:
                    try:
                        # Extract first value from kwargs if only one param
                        if len(kwargs) == 1:
                            return self.func(next(iter(kwargs.values())))
                        # Try no args for no-param functions
                        return self.func()
                    except:
                        pass
                
                # Return original error
                return f"Tool execution failed: {error_str}"
            except Exception as e:
                return f"Tool execution failed: {str(e)}"
    
    # Create tool objects from RESEARCH_TOOLS
    tools_list = [
        SimpleTool(
            name=tool_name,
            description=tool_def["description"],
            func=tool_def["func"]
        )
        for tool_name, tool_def in RESEARCH_TOOLS.items()
    ]
    
    # Attach tools to agents
    ingestion_agent.tools = tools_list
    analysis_agent.tools = tools_list
    citation_agent.tools = tools_list
    synthesis_agent.tools = tools_list
    
    graph = StateGraph(dict)
    
    def ingestion_node(state):
        paper_path = state.get("paper_path", "papers/paper.pdf")
        state = ingestion_agent.reason_and_act(state, f"Extract metadata from {paper_path}")
        
        # Call ingest_paper directly, bypassing agent tool system
        paper = ingest_paper(file_path=paper_path)
        state["paper"] = {
            "title": paper.title,
            "authors": paper.authors,
            "year": paper.year,
            "abstract": paper.abstract,
            "doi": paper.doi,
            "pages": paper.pages
        }
        return state
    
    def analysis_node(state):
        if not state.get("paper"):
            return state
        
        state = analysis_agent.reason_and_act(state, "Analyze paper content and findings")
        
        paper = PaperMetadata(
            title=state["paper"]["title"],
            authors=state["paper"]["authors"],
            abstract=state["paper"]["abstract"],
            year=state["paper"]["year"],
            doi=state["paper"]["doi"],
            pages=state["paper"]["pages"]
        )
        
        search_results = search_content(paper, "methodology")
        findings = extract_key_findings(paper)
        
        state["analysis"] = {
            "search_count": len(search_results),
            "key_contribution": findings["main_contribution"],
            "key_results": findings["key_results"],
            "impact_score": findings["impact_score"],
            "citations": findings["citations_estimated"]
        }
        return state
    
    def citation_node(state):
        if not state.get("paper"):
            return state
        
        state = citation_agent.reason_and_act(state, "Validate citations and map relationships")
        
        paper = PaperMetadata(
            title=state["paper"]["title"],
            authors=state["paper"]["authors"],
            abstract=state["paper"]["abstract"],
            year=state["paper"]["year"],
            doi=state["paper"]["doi"],
            pages=state["paper"]["pages"]
        )
        
        # These return dicts, not JSON strings
        citations = validate_citations(paper, sample_size=10)
        relationships = map_citation_relationships(paper)
        
        if citations.get("validation_failed"):
            state["citation_failed"] = True
            state["citation_error"] = citations.get("error")
        else:
            state["citations"] = {
                "validated": citations.get("validated", 0),
                "total": citations.get("total_citations", 0),
                "validation_rate": citations.get("validation_rate", 0.0)  # FIX: Use correct key
            }
            state["citation_clusters"] = {
                "clusters": relationships.get("clusters", []),
                "total": relationships.get("total_relationships", 0)
            }
        
        return state
    
    def synthesis_node(state):
        state = synthesis_agent.reason_and_act(state, "Synthesize comprehensive analysis")
        
        synthesis = synthesize_analysis(
            state.get("analysis", {}),
            state.get("citations", {}),
            state.get("citation_clusters", {})
        )
        state["synthesis"] = synthesis
        return state
    
    graph.add_node("ingestion", ingestion_node)
    graph.add_node("analysis", analysis_node)
    graph.add_node("citation", citation_node)
    graph.add_node("synthesis", synthesis_node)
    
    graph.add_edge("ingestion", "analysis")
    graph.add_edge("analysis", "citation")
    graph.add_edge("citation", "synthesis")
    graph.add_edge("synthesis", END)
    
    graph.set_entry_point("ingestion")
    return graph.compile()


def main():
    import argparse
    
    # Parse arguments BEFORE anything else
    parser = argparse.ArgumentParser(description="Analyze research papers with LLM")
    parser.add_argument("paper", nargs="?", default="papers/paper.pdf",
                        help="Path to PDF paper")
    args = parser.parse_args()
    paper_path = args.paper
    
    print("\n" + "="*100)
    print("EXAMPLE 12: Research Paper Analysis Pipeline")
    print("="*100 + "\n")
    
    print("Building workflow...")
    
    collector = get_collector()
    collector.clear()
    collector.set_correlation("research_paper_001")
    
    try:
        workflow = build_research_paper_workflow()
        print("✅ Workflow built\n")
    except Exception as e:
        print(f"❌ Failed: {e}")
        exit(1)
    
    print("Running analysis...")
    
    try:
        result = workflow.invoke({"paper_path": paper_path})
        print("✅ Workflow completed\n")
    except Exception as e:
        print(f"❌ Failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
    
    events = collector.get_events()
    collector.print_trace()
    
    # Print results
    print("\n" + "="*100)
    print("RESULTS")
    print("="*100)
    
    if result.get("paper"):
        print(f"\n📄 Paper: {result['paper']['title']} ({result['paper']['year']})")
        print(f"   Authors: {', '.join(result['paper']['authors'][:2])}")
    
    if result.get("analysis"):
        print(f"\n📊 Analysis:")
        print(f"   Key Contribution: {result['analysis']['key_contribution'][:80]}...")
        print(f"   Impact Score: {result['analysis']['impact_score']}/10")
    
    # FIX: Use correct key name and safe access
    if result.get("citations"):
        validation_rate = result['citations'].get('validation_rate', 0)
        print(f"\n✅ Citations: {validation_rate:.1%} validated")
    elif result.get("citation_failed"):
        print(f"\n⚠️  Citation validation failed: {result.get('citation_error')}")
    
    # FIX: Use correct key for citation clusters
    if result.get("citation_clusters"):
        print(f"\n🔗 Citation Clusters:")
        for cluster in result['citation_clusters'].get('clusters', [])[:3]:
            print(f"   - {cluster.get('name', 'Unknown')}: {cluster.get('papers', 0)} papers")
    
    if result.get("synthesis"):
        print(f"\n📝 Synthesis: {result['synthesis'][:200]}...")
    
    # Statistics
    print("\n" + "="*100)
    print("EXECUTION STATISTICS")
    print("="*100)
    print(f"Total events: {len(events)}")
    print(f"Event types: {sorted(set(e['event_type'] for e in events))}")
    print(f"Agents: {sorted(set(e['agent_id'] for e in events))}")
    print(f"Reasoning steps: {len([e for e in events if e['event_type'] == 'REASONING_STEP'])}")
    print(f"Tool invocations: {len([e for e in events if e['event_type'] == 'TOOL_INVOKED'])}")
    print(f"Failures: {len([e for e in events if e['event_type'] == 'GOAL_FAILED'])}")
    
    # Reconstruct DAG
    print("\n" + "="*100)
    print("CAUSAL DAG RECONSTRUCTION")
    print("="*100)
    
    builder = DAGBuilder()
    dag = builder.build(events)
    
    print(f"\n✅ DAG reconstructed:")
    print(f"   Events: {len(events)}")
    print(f"   Edges: {len(dag.edges)}")
    
    dag.print_edges()
    
    # Visualizations
    print("\n" + "="*100)
    print("GENERATING VISUALIZATIONS")
    print("="*100)
    
    try:
        visualizer = DAGVisualizer()
        visualizer.create_html_interactive(dag, output_file="research_paper_analysis_interactive.html")
        visualizer.create_graphviz(dag, output_file="research_paper_analysis.dot")
        visualizer.create_mermaid(dag, output_file="research_paper_analysis_visualization.md")
        visualizer.create_summary_table(dag, output_file="research_paper_analysis_summary.md")
        
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