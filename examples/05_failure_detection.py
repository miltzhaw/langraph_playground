#!/usr/bin/env python
"""Example 5: Detect failures and propagation in reconstructed traces"""

import sys
sys.path.insert(0, '/app')

import json
from src.agents.simple import (
    build_cascading_delegation, 
    build_delegation_agent,
    get_collector,
    agent_node
)
from reconstruction.dag_builder import DAGBuilder, visualize_trace
from evaluation.metrics import (
    compute_reconstruction_metrics,
    print_metrics,
    check_failure_propagation
)
from langgraph.graph import StateGraph, END


def build_scenario_with_failure():
    """
    Build a scenario where agent B fails (tool invocation fails),
    and see if we can reconstruct the failure propagation
    """
    graph = StateGraph(dict)
    
    # Agent A: Orchestrator
    graph.add_node("a_init", agent_node("agent_a", "Orchestrator: init"))
    graph.add_node("a_delegate_b", agent_node("agent_a", "Delegate to B"))
    
    # Agent B: Will fail with wrong tool params
    def b_fail_with_wrong_params(state):
        _collector = get_collector()
        _collector.emit("REASONING_STEP", "agent_b", {
            "step": "execute_search",
            "description": "Try to search with invalid params"
        })
        _collector.emit("TOOL_INVOKED", "agent_b", {
            "tool": "search",
            "params": {"query": "INVALID_SYNTAX!!!"},
            "status": "error"
        })
        _collector.emit("GOAL_FAILED", "agent_b", {
            "reason": "tool_error",
            "error_message": "Search failed with invalid query syntax"
        })
        return state
    
    graph.add_node("b_execute", b_fail_with_wrong_params)
    
    # Agent A: Detects failure
    graph.add_node("a_detect_failure", agent_node("agent_a", "Detected B failed"))
    graph.add_node("a_cleanup", agent_node("agent_a", "Cleanup"))
    
    # Connect
    graph.add_edge("a_init", "a_delegate_b")
    graph.add_edge("a_delegate_b", "b_execute")
    graph.add_edge("b_execute", "a_detect_failure")
    graph.add_edge("a_detect_failure", "a_cleanup")
    graph.add_edge("a_cleanup", END)
    
    graph.set_entry_point("a_init")
    
    return graph.compile()


def main():
    print("\n" + "="*100)
    print("EXAMPLE 5: Failure Detection and Propagation Analysis")
    print("="*100 + "\n")
    
    # Scenario 1: Normal cascading delegation
    print("\n### SCENARIO 1: Normal Cascading Delegation (No Failure) ###\n")
    
    collector = get_collector()
    collector.clear()
    collector.set_correlation("normal_cascade_001")
    
    graph = build_cascading_delegation()
    graph.invoke({})
    
    events = collector.get_events()
    builder = DAGBuilder()
    dag = builder.build(events)
    
    print(f"Events: {len(events)}")
    print(f"Reconstructed edges: {len(dag.edges)}")
    
    # Define ground truth for cascading delegation
    ground_truth_cascading = set()
    # We'll be lenient here - just check that we have edges
    
    # Scenario 2: Failure propagation
    print("\n\n### SCENARIO 2: Failure in Agent B (Tool Error) ###\n")
    
    collector.clear()
    collector.set_correlation("failure_scenario_001")
    
    graph_with_failure = build_scenario_with_failure()
    graph_with_failure.invoke({})
    
    events_with_failure = collector.get_events()
    dag_with_failure = builder.build(events_with_failure)
    
    print(f"Events: {len(events_with_failure)}")
    print(f"Reconstructed edges: {len(dag_with_failure.edges)}")
    
    # Print all events
    print("\nCollected events:")
    for i, event in enumerate(events_with_failure, 1):
        print(f"  {i}. {event['event_type']:20s} ({event['agent_id']}) - {event['payload']}")
    
    # Show DAG edges
    dag_with_failure.print_edges()
    
    # Detect failure propagation
    print("\n" + "="*100)
    print("FAILURE PROPAGATION ANALYSIS")
    print("="*100)
    
    # Find the GOAL_FAILED event
    failure_event = None
    for event in events_with_failure:
        if event['event_type'] == 'GOAL_FAILED':
            failure_event = event
            break
    
    if failure_event:
        print(f"\nFailure detected: {failure_event['event_id'][:8]}")
        print(f"Agent: {failure_event['agent_id']}")
        print(f"Reason: {failure_event['payload'].get('reason')}")
        print(f"Message: {failure_event['payload'].get('error_message')}")
        
        # Analyze propagation
        propagation = check_failure_propagation(
            dag_with_failure.edges,
            events_with_failure,
            failure_event['event_id']
        )
        
        print(f"\nPropagation:")
        print(f"  Affected events: {propagation.get('num_affected_events', 0)}")
        print(f"  Affected agents: {propagation.get('affected_agents', set())}")
        
        if propagation.get('propagation_chain'):
            print(f"\n  Propagation chain:")
            for step in propagation['propagation_chain']:
                print(f"    -> {step['event_type']:20s} ({step['agent_id']}) @ {step['timestamp']:.3f}")
    
    # Export as JSON
    print("\n" + "="*100)
    print("FAILURE SCENARIO DAG (JSON)")
    print("="*100)
    print(json.dumps(dag_with_failure.to_dict(), indent=2))


if __name__ == "__main__":
    main()
