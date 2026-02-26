"""Example 1: Run a simple single-agent workflow"""

import sys
sys.path.insert(0, '/app')

from src.agents.simple import build_simple_agent, get_collector

def main():
    print("\n" + "="*80)
    print("EXAMPLE 1: Simple Single-Agent Workflow")
    print("="*80 + "\n")
    
    # Create and run agent
    graph = build_simple_agent()
    result = graph.invoke({})
    
    # Print trace
    collector = get_collector()
    collector.print_trace()
    
    print("Final state:", result)

if __name__ == "__main__":
    main()
