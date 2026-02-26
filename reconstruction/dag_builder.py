# reconstruction/dag_builder.py
"""Build causal DAG from semantic events"""

from typing import List, Dict, Set, Tuple
from dataclasses import dataclass
import json


@dataclass
class CausalEdge:
    """Represents a causal dependency between two events"""
    from_event_id: str
    to_event_id: str
    reason: str  # e.g., "delegation", "message_passing", "tool_invocation"
    from_agent: str
    to_agent: str


@dataclass
class CausalDAG:
    """Directed acyclic graph of causal dependencies"""
    events: List[Dict]  # Raw events
    edges: Set[Tuple[str, str]] = None  # Set of (from_id, to_id) tuples
    edge_details: Dict[Tuple[str, str], CausalEdge] = None
    
    def __post_init__(self):
        self.edges = set()
        self.edge_details = {}
    
    def add_edge(self, from_id: str, to_id: str, reason: str, from_agent: str, to_agent: str):
        """Add a causal edge"""
        self.edges.add((from_id, to_id))
        self.edge_details[(from_id, to_id)] = CausalEdge(
            from_event_id=from_id,
            to_event_id=to_id,
            reason=reason,
            from_agent=from_agent,
            to_agent=to_agent
        )
    
    def get_edge_reason(self, from_id: str, to_id: str) -> str:
        """Get the reason for a causal edge"""
        if (from_id, to_id) in self.edge_details:
            return self.edge_details[(from_id, to_id)].reason
        return "unknown"
    
    def print_edges(self):
        """Print all edges in readable format"""
        print("\n" + "="*100)
        print("CAUSAL EDGES (DAG)")
        print("="*100)
        
        if not self.edges:
            print("No causal edges found")
            return
        
        for from_id, to_id in sorted(self.edges):
            from_event = self._find_event(from_id)
            to_event = self._find_event(to_id)
            edge = self.edge_details.get((from_id, to_id))
            
            from_type = from_event['event_type'] if from_event else "UNKNOWN"
            to_type = to_event['event_type'] if to_event else "UNKNOWN"
            from_agent = from_event['agent_id'] if from_event else "?"
            to_agent = to_event['agent_id'] if to_event else "?"
            reason = edge.reason if edge else "unknown"
            
            print(f"{from_type:20s} ({from_agent}) -> {to_type:20s} ({to_agent}) [{reason}]")
        
        print("="*100 + "\n")
    
    def _find_event(self, event_id: str):
        """Find event by ID"""
        for event in self.events:
            if event['event_id'] == event_id:
                return event
        return None
    
    def to_dict(self):
        """Export as dictionary for JSON serialization"""
        edges_list = []
        for (from_id, to_id) in self.edges:
            edge_detail = self.edge_details.get((from_id, to_id))
            edges_list.append({
                "from_event_id": from_id,
                "to_event_id": to_id,
                "reason": edge_detail.reason if edge_detail else "unknown",
                "from_agent": edge_detail.from_agent if edge_detail else "?",
                "to_agent": edge_detail.to_agent if edge_detail else "?",
            })
        
        return {
            "num_events": len(self.events),
            "num_edges": len(self.edges),
            "edges": edges_list
        }


class DAGBuilder:
    """Reconstructs causal DAG from semantic events"""
    
    def build(self, events: List[Dict]) -> CausalDAG:
        """
        Build causal DAG using three explicit rules:
        1. GOAL_DELEGATED -> next event in target agent
        2. REASONING_STEP -> next event in same agent
        3. Timestamp proximity (intra-agent only)
        """
        dag = CausalDAG(events=events)
        
        # Rule 1: Delegation edges
        self._apply_delegation_rule(dag)
        
        # Rule 2: Intra-agent reasoning edges
        self._apply_intra_agent_rule(dag)
        
        # Rule 3: Gap completion (proximity)
        self._apply_gap_completion(dag)
        
        return dag
    
    def _apply_delegation_rule(self, dag: CausalDAG):
        """
        Rule 1: GOAL_DELEGATED (from agent A to agent B) 
        -> next REASONING_STEP in agent B
        """
        delegations = [e for e in dag.events if e['event_type'] == 'GOAL_DELEGATED']
        
        for delegation in delegations:
            from_agent = delegation['agent_id']
            to_agent = delegation['payload'].get('to')
            delegation_id = delegation['event_id']
            delegation_time = delegation['timestamp']
            
            # Find next event in target agent after delegation
            target_events = [
                e for e in dag.events 
                if e['agent_id'] == to_agent and e['timestamp'] > delegation_time
            ]
            
            if target_events:
                next_event = min(target_events, key=lambda x: x['timestamp'])
                dag.add_edge(
                    delegation_id,
                    next_event['event_id'],
                    "delegation",
                    from_agent,
                    to_agent
                )
    
    def _apply_intra_agent_rule(self, dag: CausalDAG):
        """
        Rule 2: Within same agent, connect events by timestamp:
        - REASONING_STEP -> next REASONING_STEP
        - REASONING_STEP -> TOOL_INVOKED
        """
        events_by_agent = {}
        for event in dag.events:
            agent = event['agent_id']
            if agent not in events_by_agent:
                events_by_agent[agent] = []
            events_by_agent[agent].append(event)
        
        # For each agent, connect consecutive events
        for agent, agent_events in events_by_agent.items():
            sorted_events = sorted(agent_events, key=lambda x: x['timestamp'])
            
            for i in range(len(sorted_events) - 1):
                current = sorted_events[i]
                next_event = sorted_events[i + 1]
                
                # Skip if already connected by delegation
                if (current['event_id'], next_event['event_id']) in dag.edges:
                    continue
                
                # Connect reasoning steps within same agent
                if current['event_type'] == 'REASONING_STEP':
                    dag.add_edge(
                        current['event_id'],
                        next_event['event_id'],
                        "intra_agent_sequence",
                        agent,
                        agent
                    )
    
    def _apply_gap_completion(self, dag: CausalDAG):
        """
        Rule 3: Fill gaps in same agent if events are close in time
        (helps with missing instrumentation)
        """
        # Find connected components
        components = self._find_components(dag)
        
        if len(components) <= 1:
            return  # Already connected
        
        # Within each agent, connect closest events across components
        events_by_agent = {}
        for event in dag.events:
            agent = event['agent_id']
            if agent not in events_by_agent:
                events_by_agent[agent] = []
            events_by_agent[agent].append(event)
        
        for agent, agent_events in events_by_agent.items():
            sorted_events = sorted(agent_events, key=lambda x: x['timestamp'])
            
            # Find gaps: events not connected to previous
            for i in range(len(sorted_events) - 1):
                current = sorted_events[i]
                next_event = sorted_events[i + 1]
                
                # If not already connected, check time gap
                if (current['event_id'], next_event['event_id']) not in dag.edges:
                    time_gap = next_event['timestamp'] - current['timestamp']
                    
                    if time_gap < 0.01:  # Less than 10ms, likely causally related
                        dag.add_edge(
                            current['event_id'],
                            next_event['event_id'],
                            "inferred_by_proximity",
                            agent,
                            agent
                        )
    
    def _find_components(self, dag: CausalDAG):
        """Find connected components in the DAG"""
        # Simple DFS-based component finding
        visited = set()
        components = []
        
        def dfs(event_id, component):
            if event_id in visited:
                return
            visited.add(event_id)
            component.add(event_id)
            
            # Follow edges forward
            for (from_id, to_id) in dag.edges:
                if from_id == event_id:
                    dfs(to_id, component)
                elif to_id == event_id:
                    dfs(from_id, component)
        
        for event in dag.events:
            if event['event_id'] not in visited:
                component = set()
                dfs(event['event_id'], component)
                components.append(component)
        
        return components


def visualize_trace(dag: CausalDAG):
    """Create a simple text visualization of the causal trace"""
    print("\n" + "="*100)
    print("CAUSAL TRACE VISUALIZATION")
    print("="*100)
    
    # Group by agent
    events_by_agent = {}
    for event in dag.events:
        agent = event['agent_id']
        if agent not in events_by_agent:
            events_by_agent[agent] = []
        events_by_agent[agent].append(event)
    
    # Sort agents
    for agent in sorted(events_by_agent.keys()):
        events = sorted(events_by_agent[agent], key=lambda x: x['timestamp'])
        print(f"\n{agent}:")
        
        for i, event in enumerate(events):
            event_type = event['event_type']
            event_id = event['event_id'][:8]  # Short ID
            
            # Check if this event has incoming edges
            incoming = [e for (f, e) in dag.edges if e == event['event_id']]
            incoming_str = " <--" if incoming else ""
            
            # Check if this event has outgoing edges
            outgoing = [e for (f, e) in dag.edges if f == event['event_id']]
            outgoing_str = " -->" if outgoing else ""
            
            print(f"  [{i}] {event_type:20s} {incoming_str}{outgoing_str} ({event_id})")
    
    print("="*100 + "\n")
