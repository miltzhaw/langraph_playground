#!/usr/bin/env python
"""Example 7: Store traces in PostgreSQL"""

import sys
sys.path.insert(0, '/app')

from src.agents.simple import build_cascading_delegation, get_collector
from reconstruction.dag_builder import DAGBuilder
from storage.postgres_backend import PostgresBackend


def main():
    print("\n" + "="*100)
    print("EXAMPLE 7: Store Traces in PostgreSQL")
    print("="*100 + "\n")
    
    # Collect events
    collector = get_collector()
    collector.clear()
    collector.set_correlation("postgres_test_001")
    
    graph = build_cascading_delegation()
    graph.invoke({})
    
    events = collector.get_events()
    print(f"Collected {len(events)} events\n")
    
    # Reconstruct DAG
    builder = DAGBuilder()
    dag = builder.build(events)
    
    print(f"Reconstructed {len(dag.edges)} causal edges\n")
    
    # Store in PostgreSQL
    try:
        backend = PostgresBackend()
        
        # Store events
        print("Storing events in PostgreSQL...")
        backend.store_events_batch(events)
        
        # Store causal edges
        print("Storing causal edges in PostgreSQL...")
        for (from_id, to_id) in dag.edges:
            reason = dag.get_edge_reason(from_id, to_id)
            backend.store_causal_edge(from_id, to_id, reason)
        
        # Retrieve and display
        print("\nRetrieving from database...")
        stored_events = backend.get_events()
        stored_edges = backend.get_causal_edges()
        
        print(f"✓ Stored and retrieved {len(stored_events)} events from DB")
        print(f"✓ Stored and retrieved {len(stored_edges)} edges from DB")
        
        backend.close()
        
    except Exception as e:
        print(f"✗ Database operation failed: {e}")


if __name__ == "__main__":
    main()
