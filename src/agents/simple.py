"""Simple LangGraph agents with instrumentation hooks"""

from langgraph.graph import StateGraph, END
from typing import Any, Dict
import uuid
from datetime import datetime
import json

# In-memory event collector (later: use DB)
class TraceCollector:
    def __init__(self):
        self.events = []
        self.correlation_context = {}
    
    def set_correlation(self, cid: str):
        """Set correlation ID for current context"""
        self.correlation_context["current"] = cid
    
    def emit(self, event_type: str, agent_id: str, payload: dict) -> str:
        """Emit a semantic event"""
        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "agent_id": agent_id,
            "timestamp": datetime.now().timestamp(),
            "correlation_id": self.correlation_context.get("current", ""),
            "payload": payload
        }
        self.events.append(event)
        return event["event_id"]
    
    def get_events(self):
        return self.events
    
    def clear(self):
        self.events = []
    
    def print_trace(self):
        """Pretty-print collected events"""
        print("\n" + "="*80)
        print("COLLECTED EVENTS")
        print("="*80)
        for i, event in enumerate(self.events, 1):
            print(f"{i}. [{event['event_type']:20s}] Agent: {event['agent_id']:10s} | Payload: {event['payload']}")
        print("="*80 + "\n")

# Global collector (simple; production would use contextvars)
_collector = TraceCollector()

def get_collector():
    return _collector


# Simple agent node
def agent_node(agent_id: str, description: str):
    """Factory for creating agent nodes"""
    def node(state: Dict[str, Any]) -> Dict[str, Any]:
        _collector.emit("REASONING_STEP", agent_id, {
            "description": description,
            "state_keys": list(state.keys())
        })
        
        # Simulate some work
        state[f"{agent_id}_completed"] = True
        
        return state
    
    return node


def delegation_node(from_agent: str, to_agent: str, task: str):
    """Node that delegates work to another agent"""
    def node(state: Dict[str, Any]) -> Dict[str, Any]:
        _collector.emit("GOAL_DELEGATED", from_agent, {
            "from": from_agent,
            "to": to_agent,
            "task": task
        })
        
        state["delegated_to"] = to_agent
        state["task"] = task
        
        return state
    
    return node


# Example 1: Single agent
def build_simple_agent():
    """Single agent that reasons and completes"""
    graph = StateGraph(dict)
    
    graph.add_node("start", agent_node("agent_a", "Initialize task"))
    graph.add_node("process", agent_node("agent_a", "Process task"))
    graph.add_node("end", agent_node("agent_a", "Complete task"))
    
    graph.add_edge("start", "process")
    graph.add_edge("process", "end")
    graph.add_edge("end", END)
    
    graph.set_entry_point("start")
    
    return graph.compile()


# Example 2: Two agents with delegation
def build_delegation_agent():
    """Agent A delegates to Agent B"""
    graph = StateGraph(dict)
    
    graph.add_node("a_init", agent_node("agent_a", "Initialize"))
    graph.add_node("a_delegate", delegation_node("agent_a", "agent_b", "search"))
    graph.add_node("b_execute", agent_node("agent_b", "Execute search task"))
    graph.add_node("b_complete", agent_node("agent_b", "Send result back"))
    graph.add_node("a_receive", agent_node("agent_a", "Receive result"))
    
    graph.add_edge("a_init", "a_delegate")
    graph.add_edge("a_delegate", "b_execute")
    graph.add_edge("b_execute", "b_complete")
    graph.add_edge("b_complete", "a_receive")
    graph.add_edge("a_receive", END)
    
    graph.set_entry_point("a_init")
    
    return graph.compile()


# Example 3: Cascading delegation (A -> B -> C)
def build_cascading_delegation():
    """Three-agent cascade"""
    graph = StateGraph(dict)
    
    # Agent A: Orchestrator
    graph.add_node("a_init", agent_node("agent_a", "Orchestrator: init"))
    graph.add_node("a_delegate_b", delegation_node("agent_a", "agent_b", "retrieve_docs"))
    
    # Agent B: Intermediate
    graph.add_node("b_init", agent_node("agent_b", "Intermediate: received task"))
    graph.add_node("b_delegate_c", delegation_node("agent_b", "agent_c", "search_database"))
    
    # Agent C: Worker
    graph.add_node("c_init", agent_node("agent_c", "Worker: received task"))
    graph.add_node("c_search", agent_node("agent_c", "Search database"))
    graph.add_node("c_return", agent_node("agent_c", "Return result"))
    
    # B receives result and returns to A
    graph.add_node("b_aggregate", agent_node("agent_b", "Aggregate results"))
    graph.add_node("a_complete", agent_node("agent_a", "Final processing"))
    
    # Edges
    graph.add_edge("a_init", "a_delegate_b")
    graph.add_edge("a_delegate_b", "b_init")
    graph.add_edge("b_init", "b_delegate_c")
    graph.add_edge("b_delegate_c", "c_init")
    graph.add_edge("c_init", "c_search")
    graph.add_edge("c_search", "c_return")
    graph.add_edge("c_return", "b_aggregate")
    graph.add_edge("b_aggregate", "a_complete")
    graph.add_edge("a_complete", END)
    
    graph.set_entry_point("a_init")
    
    return graph.compile()
