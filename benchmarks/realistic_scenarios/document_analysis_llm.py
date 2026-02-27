
import sys
sys.path.insert(0, '/app')

from langgraph.graph import StateGraph, END
from src.agents_realistic.base import MistralAgent
from tools.document_tools import search_documents, summarize_content, classify_document
from src.agents.simple import get_collector
from reconstruction.dag_builder import DAGBuilder

def build_document_analysis_workflow():
    """
    Realistic Scenario 1: Multi-stage document analysis
    
    Flow:
    1. Coordinator receives document analysis request
    2. Delegates to Analyzer for content extraction
    3. Delegates to Summarizer for summary creation
    4. Delegates to Classifier for document categorization
    5. Returns results
    
    Demonstrates:
    - Real LLM reasoning at each stage
    - Tool invocation decisions
    - Multi-agent coordination
    - Realistic event semantics
    """
    
    # Create agents with specific roles
    coordinator = MistralAgent("coordinator", "orchestrator")
    analyzer = MistralAgent("analyzer", "content_analyzer")
    summarizer = MistralAgent("summarizer", "summarization_specialist")
    classifier = MistralAgent("classifier", "document_classifier")
    
    # Register tools for each agent
    analyzer.register_tool(search_documents)
    summarizer.register_tool(summarize_content)
    classifier.register_tool(classify_document)
    
    # Build workflow graph
    graph = StateGraph(dict)
    
    # Define nodes
    def coordinator_node(state):
        state = coordinator.reason_and_act(
            state,
            "Coordinate analysis of document about machine learning"
        )
        return state
    
    def analyzer_node(state):
        state = analyzer.reason_and_act(
            state,
            "Extract and search for information about machine learning"
        )
        return state
    
    def summarizer_node(state):
        content = state.get("tool_result", "No content")
        state = summarizer.reason_and_act(
            state,
            f"Create a concise summary of: {str(content)[:100]}"
        )
        return state
    
    def classifier_node(state):
        content = state.get("tool_result", "machine learning content")
        state = classifier.reason_and_act(
            state,
            f"Classify this content: {str(content)[:100]}"
        )
        return state
    
    # Add nodes
    graph.add_node("coordinator", coordinator_node)
    graph.add_node("analyzer", analyzer_node)
    graph.add_node("summarizer", summarizer_node)
    graph.add_node("classifier", classifier_node)
    
    # Add edges (sequential delegation)
    graph.add_edge("coordinator", "analyzer")
    graph.add_edge("analyzer", "summarizer")
    graph.add_edge("summarizer", "classifier")
    graph.add_edge("classifier", END)
    
    graph.set_entry_point("coordinator")
    
    return graph.compile()


def build_customer_service_workflow():
    """
    Realistic Scenario 2: Customer support with escalation
    
    Flow:
    1. Level 1 Bot tries to resolve simple issues
    2. If confident, completes. Otherwise, escalates to Level 2
    3. Level 2 Specialist has more tools, handles complex issues
    4. Can escalate to Level 3 Expert if needed
    
    Demonstrates:
    - Conditional escalation logic
    - Different tool access at each level
    - Realistic failure modes (unresolvable issues)
    - Decision-making based on confidence
    """
    
    # Create support agents at different levels
    level1_bot = MistralAgent("level1_bot", "frontline_support")
    level2_specialist = MistralAgent("level2_specialist", "support_specialist")
    level3_expert = MistralAgent("level3_expert", "support_expert")
    
    # Register tools (level 1 has basic tools, level 2 has more)
    level1_bot.register_tool(search_documents)
    
    level2_specialist.register_tool(search_documents)
    level2_specialist.register_tool(check_order_status)
    level2_specialist.register_tool(issue_refund)
    
    level3_expert.register_tool(search_documents)
    level3_expert.register_tool(check_order_status)
    level3_expert.register_tool(issue_refund)
    
    # Build workflow
    graph = StateGraph(dict)
    
    def level1_node(state):
        issue = state.get("customer_issue", "billing problem")
        state = level1_bot.reason_and_act(
            state,
            f"Customer support issue: {issue}"
        )
        # Set confidence based on result
        state["confidence"] = 0.6 if "error" not in state else 0.2
        return state
    
    def level2_node(state):
        issue = state.get("customer_issue", "billing problem")
        state = level2_specialist.reason_and_act(
            state,
            f"Handle escalated customer issue: {issue}"
        )
        state["confidence"] = 0.85 if "error" not in state else 0.4
        return state
    
    def level3_node(state):
        issue = state.get("customer_issue", "billing problem")
        state = level3_expert.reason_and_act(
            state,
            f"Expert handling complex issue: {issue}"
        )
        state["confidence"] = 0.95
        return state
    
    # Routing function
    def route_escalation(state):
        confidence = state.get("confidence", 0)
        if confidence > 0.7:
            return "end"
        elif state.get("escalation_level", 0) == 0:
            return "escalate_to_level2"
        elif state.get("escalation_level", 0) == 1:
            return "escalate_to_level3"
        return "end"
    
    graph.add_node("level1", level1_node)
    graph.add_node("level2", level2_node)
    graph.add_node("level3", level3_node)
    
    graph.add_conditional_edges("level1", route_escalation)
    graph.add_edge("escalate_to_level2", "level2")
    
    graph.add_conditional_edges("level2", route_escalation)
    graph.add_edge("escalate_to_level3", "level3")
    
    graph.add_edge("level3", END)
    
    graph.set_entry_point("level1")
    
    return graph.compile()


if __name__ == "__main__":
    print("\n" + "="*100)
    print("REALISTIC SCENARIO: Document Analysis with Mistral")
    print("="*100 + "\n")
    
    collector = get_collector()
    collector.clear()
    collector.set_correlation("realistic_doc_001")
    
    workflow = build_document_analysis_workflow()
    
    print("Running workflow with real LLM reasoning...\n")
    print("(This may take 30-60 seconds on first run)\n")
    
    result = workflow.invoke({})
    
    events = collector.get_events()
    collector.print_trace()
    
    # Show reconstruction
    builder = DAGBuilder()
    dag = builder.build(events)
    dag.print_edges()
    
    # Statistics
    print("\n" + "="*100)
    print("STATISTICS")
    print("="*100)
    print(f"Total events: {len(events)}")
    print(f"Causal edges: {len(dag.edges)}")
    print(f"Agents involved: {set(e['agent_id'] for e in events)}")
    print(f"Tool invocations: {len([e for e in events if e['event_type'] == 'TOOL_INVOKED'])}")
    print(f"Failures: {len([e for e in events if e['event_type'] == 'GOAL_FAILED'])}")
