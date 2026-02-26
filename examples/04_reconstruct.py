#!/usr/bin/env python
"""Example 4: Reconstruct causal DAG from events"""

import sys
sys.path.insert(0, '/app')

import json
from src.agents.simple import build_cascading_delegation, get_collector
from reconstruction.dag_builder import DAGBuilder, visualize_trace


def main():
    print("\n" + "="*100)
    print("EXAMPLE 4: Reconstructing Causal DAG from Events")
    print("="*100 + "\n")
    
    # Run the three-agent scenario
    collector = get_collector()
    collector.clear()
    collector.set_correlation("run_cascade_001")
    
    graph = build_cascading_delegation()
    graph.invoke({})
    
    # Get raw events
    events = collector.get_events()
    print(f"Collected {len(events)} events\n")
    
    # Reconstruct DAG
    builder = DAGBuilder()
    dag = builder.build(events)
    
    print(f"Reconstructed DAG with {len(dag.edges)} causal edges\n")
    
    # Print edges
    dag.print_edges()
    
    # Visualize
    visualize_trace(dag)
    
    # Export as JSON
    print("\nDAG as JSON:")
    print(json.dumps(dag.to_dict(), indent=2))


if __name__ == "__main__":
    main()
