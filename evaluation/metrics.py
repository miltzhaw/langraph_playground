#!/usr/bin/env python
"""Metrics for evaluating causal trace reconstruction"""

from typing import List, Set, Tuple, Dict
from dataclasses import dataclass


@dataclass
class ReconstructionMetrics:
    """Metrics for reconstruction accuracy"""
    accuracy: float  # Fraction of ground truth edges found
    precision: float  # Fraction of reconstructed edges that are correct
    false_positives: int  # Edges reconstructed but not in ground truth
    false_negatives: int  # Edges in ground truth but not reconstructed
    trace_completeness: float  # Fraction of expected events captured
    num_events: int
    num_reconstructed_edges: int
    num_ground_truth_edges: int


def compute_reconstruction_metrics(
    reconstructed_edges: Set[Tuple[str, str]],
    ground_truth_edges: Set[Tuple[str, str]],
    num_events: int,
    expected_event_count: int
) -> ReconstructionMetrics:
    """
    Compute reconstruction accuracy metrics
    
    Args:
        reconstructed_edges: Set of (from_id, to_id) tuples from reconstruction
        ground_truth_edges: Set of (from_id, to_id) tuples from specification
        num_events: Number of events actually collected
        expected_event_count: Number of events expected per specification
    
    Returns:
        ReconstructionMetrics object
    """
    if not ground_truth_edges:
        return ReconstructionMetrics(
            accuracy=1.0 if not reconstructed_edges else 0.0,
            precision=1.0 if not reconstructed_edges else 0.0,
            false_positives=len(reconstructed_edges),
            false_negatives=0,
            trace_completeness=num_events / expected_event_count if expected_event_count > 0 else 1.0,
            num_events=num_events,
            num_reconstructed_edges=len(reconstructed_edges),
            num_ground_truth_edges=0
        )
    
    # Find true positives, false positives, false negatives
    true_positives = reconstructed_edges & ground_truth_edges
    false_positives = reconstructed_edges - ground_truth_edges
    false_negatives = ground_truth_edges - reconstructed_edges
    
    # Calculate metrics
    recall = len(true_positives) / len(ground_truth_edges) if ground_truth_edges else 0.0
    precision = len(true_positives) / len(reconstructed_edges) if reconstructed_edges else 0.0
    trace_completeness = num_events / expected_event_count if expected_event_count > 0 else 1.0
    
    return ReconstructionMetrics(
        accuracy=recall,
        precision=precision,
        false_positives=len(false_positives),
        false_negatives=len(false_negatives),
        trace_completeness=trace_completeness,
        num_events=num_events,
        num_reconstructed_edges=len(reconstructed_edges),
        num_ground_truth_edges=len(ground_truth_edges)
    )


def print_metrics(metrics: ReconstructionMetrics, scenario_name: str = ""):
    """Pretty-print reconstruction metrics"""
    print("\n" + "="*80)
    print(f"RECONSTRUCTION METRICS{' - ' + scenario_name if scenario_name else ''}")
    print("="*80)
    print(f"Accuracy (Recall):        {metrics.accuracy:.2%}  (found {metrics.num_reconstructed_edges}/{metrics.num_ground_truth_edges} edges)")
    print(f"Precision:                {metrics.precision:.2%}  (correct {metrics.num_reconstructed_edges - metrics.false_positives}/{metrics.num_reconstructed_edges} edges)")
    print(f"Trace Completeness:       {metrics.trace_completeness:.2%}  ({metrics.num_events} events)")
    print(f"False Positives:          {metrics.false_positives}")
    print(f"False Negatives:          {metrics.false_negatives}")
    print("="*80 + "\n")


def check_failure_propagation(
    dag_edges: Set[Tuple[str, str]],
    events: List[Dict],
    failure_event_id: str
) -> Dict:
    """
    Analyze if a failure propagates through the DAG
    
    Args:
        dag_edges: Causal edges in the DAG
        events: All events
        failure_event_id: Event ID of the failure
    
    Returns:
        Dict with propagation information
    """
    # Find the failure event
    failure_event = None
    for event in events:
        if event['event_id'] == failure_event_id:
            failure_event = event
            break
    
    if not failure_event:
        return {"error": "Failure event not found"}
    
    # Traverse forward from failure in DAG
    propagation_path = [failure_event_id]
    queue = [failure_event_id]
    visited = {failure_event_id}
    
    while queue:
        current_id = queue.pop(0)
        
        # Find all edges emanating from current event
        for (from_id, to_id) in dag_edges:
            if from_id == current_id and to_id not in visited:
                queue.append(to_id)
                visited.add(to_id)
                propagation_path.append(to_id)
    
    # Get details of propagation
    propagation_details = []
    for event_id in propagation_path:
        event = next((e for e in events if e['event_id'] == event_id), None)
        if event:
            propagation_details.append({
                "event_id": event_id[:8],
                "event_type": event['event_type'],
                "agent_id": event['agent_id'],
                "timestamp": event['timestamp']
            })
    
    return {
        "num_affected_events": len(propagation_path),
        "affected_agents": set(e['agent_id'] for e in propagation_details),
        "propagation_chain": propagation_details
    }


class FailureScenario:
    """Define a failure scenario with ground truth"""
    
    def __init__(self, name: str, description: str, ground_truth_edges: Set[Tuple[str, str]]):
        self.name = name
        self.description = description
        self.ground_truth_edges = ground_truth_edges
        self.expected_event_count = len(ground_truth_edges) + 1  # Rough estimate


# Predefined scenarios for testing
SCENARIOS = {
    "simple_delegation": FailureScenario(
        name="simple_delegation",
        description="Agent A delegates to B (2 agents, 1 level)",
        ground_truth_edges={
            # A: init -> delegate to B
            # B: execute
            # A: complete
            # Expected edges:
            # A reasoning -> A delegation
            # A delegation -> B reasoning
            # B reasoning -> A final
        }
    ),
    
    "cascading_delegation": FailureScenario(
        name="cascading_delegation",
        description="Agent A -> B -> C (3 agents, 2 levels)",
        ground_truth_edges={
            # A: init -> delegate to B
            # B: init -> delegate to C
            # C: execute -> return
            # B: aggregate
            # A: final
            # Expected edges:
            # A init -> A delegate_b
            # A delegate_b -> B init
            # B init -> B delegate_c
            # B delegate_c -> C init
            # C init -> C search -> C return
            # C return -> B aggregate
            # B aggregate -> A final
        }
    ),
    
    "parallel_tasks": FailureScenario(
        name="parallel_tasks",
        description="Agent A delegates to B and C in parallel",
        ground_truth_edges={
            # A: init -> delegate to B
            # A: init -> delegate to C (separate path)
            # B: execute
            # C: execute
            # A: aggregate results
        }
    ),
}


def validate_scenario(reconstructed_dag, scenario: FailureScenario, num_events: int):
    """Validate reconstruction against a scenario's ground truth"""
    metrics = compute_reconstruction_metrics(
        reconstructed_dag.edges,
        scenario.ground_truth_edges,
        num_events,
        scenario.expected_event_count
    )
    
    print(f"\nScenario: {scenario.name}")
    print(f"Description: {scenario.description}")
    print_metrics(metrics, scenario.name)
    
    return metrics
