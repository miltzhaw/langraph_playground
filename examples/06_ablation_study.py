#!/usr/bin/env python
"""Example 6: Ablation study - remove event types, measure reconstruction accuracy"""

import sys
sys.path.insert(0, '/app')

from src.agents.simple import build_cascading_delegation, get_collector
from reconstruction.dag_builder import DAGBuilder
from evaluation.metrics import compute_reconstruction_metrics
import json


def run_ablation_study():
    """
    Run ablation study: remove each event type, measure reconstruction accuracy
    
    This answers: "Which event types are essential?"
    """
    print("\n" + "="*100)
    print("ABLATION STUDY: Minimal Telemetry Requirements")
    print("="*100 + "\n")
    
    # Collect baseline (all events)
    collector = get_collector()
    collector.clear()
    collector.set_correlation("ablation_baseline")
    
    graph = build_cascading_delegation()
    graph.invoke({})
    
    all_events = collector.get_events()
    print(f"Baseline: {len(all_events)} events\n")
    
    # Get baseline reconstruction
    builder = DAGBuilder()
    baseline_dag = builder.build(all_events)
    baseline_edges_set = baseline_dag.edges
    baseline_num_edges = len(baseline_edges_set)
    
    print(f"Baseline edges: {baseline_num_edges}\n")
    
    # Define ground truth (expected edges for cascading delegation)
    # Based on the structure: A->B->C with A,B,C executing
    ground_truth_edges = {
        # We'll use baseline as ground truth for this study
        # In real scenario, would define from specification
    }
    
    # Get event types present
    event_types = set(e['event_type'] for e in all_events)
    print(f"Event types in trace: {sorted(event_types)}\n")
    
    # Ablation: remove each event type
    results = []
    
    # Baseline
    results.append({
        "config": "BASELINE (all events)",
        "removed_type": None,
        "num_events": len(all_events),
        "num_edges": baseline_num_edges,
        "accuracy": 1.0  # Baseline is 100% by definition
    })
    
    # Remove each event type
    for remove_type in sorted(event_types):
        filtered_events = [e for e in all_events if e['event_type'] != remove_type]
        
        if not filtered_events:
            continue  # Skip if removing this type leaves no events
        
        # Reconstruct with filtered events
        dag = builder.build(filtered_events)
        num_edges = len(dag.edges)
        
        # Measure accuracy (fraction of baseline edges recovered)
        recovered = len(dag.edges & baseline_edges_set)
        accuracy = recovered / baseline_num_edges if baseline_num_edges else 1.0
        
        results.append({
            "config": f"WITHOUT {remove_type}",
            "removed_type": remove_type,
            "num_events": len(filtered_events),
            "num_edges": num_edges,
            "accuracy": accuracy
        })
    
    # Print results as table
    print("="*100)
    print("ABLATION RESULTS")
    print("="*100)
    print(f"{'Configuration':<40} | {'Events':<8} | {'Edges':<8} | {'Accuracy':<10}")
    print("-"*100)
    
    for result in results:
        config = result['config']
        events = result['num_events']
        edges = result['num_edges']
        accuracy = result['accuracy']
        
        print(f"{config:<40} | {events:<8} | {edges:<8} | {accuracy:>8.2%}")
    
    print("="*100 + "\n")
    
    # Analysis
    print("INTERPRETATION:")
    print("-" * 100)
    
    # Find which event types are essential (removing them drops accuracy significantly)
    essential = []
    optional = []
    
    baseline_accuracy = results[0]['accuracy']
    baseline_edges_count = results[0]['num_edges']
    
    for result in results[1:]:  # Skip baseline
        if result['accuracy'] < 0.8:  # Drops below 80% threshold
            essential.append({
                "type": result['removed_type'],
                "accuracy_drop": baseline_accuracy - result['accuracy']
            })
        else:
            optional.append({
                "type": result['removed_type'],
                "accuracy": result['accuracy']
            })
    
    print(f"\n✓ ESSENTIAL event types (removing drops accuracy below 80%):")
    for item in essential:
        print(f"  - {item['type']:<30} (drops {item['accuracy_drop']:.1%})")
    
    if optional:
        print(f"\n◆ OPTIONAL event types (can be removed without major accuracy loss):")
        for item in optional:
            print(f"  - {item['type']:<30} (maintains {item['accuracy']:.1%} accuracy)")
    else:
        print(f"\n◆ OPTIONAL event types: None (all are essential)")
    
    print("\n" + "="*100)
    print(f"MINIMAL TELEMETRY SET: {len(essential)} essential event types")
    print("="*100 + "\n")
    
    # Export as JSON
    export = {
        "study": "ablation_study",
        "baseline_edges": baseline_edges_count,
        "results": results,
        "essential_types": [e['type'] for e in essential],
        "optional_types": [o['type'] for o in optional]
    }
    
    print("Ablation results (JSON):")
    print(json.dumps(export, indent=2))
    
    return results


if __name__ == "__main__":
    run_ablation_study()
