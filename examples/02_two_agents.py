"""Example 2: Two agents with delegation"""

import sys
sys.path.insert(0, '/app')

from src.agents.simple import build_delegation_agent, get_collector

def main():
    print("\n" + "="*80)
    print("EXAMPLE 2: Two-Agent Delegation")
    print("="*80 + "\n")
    
    collector = get_collector()
    collector.clear()
    
    # Set correlation ID for this run
    collector.set_correlation("run_001")
    
    graph = build_delegation_agent()
    result = graph.invoke({})
    
    collector.print_trace()
    
    print("Events collected:", len(collector.get_events()))

if __name__ == "__main__":
    main()
