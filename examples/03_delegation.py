"""Example 3: Cascading three-agent delegation"""

import sys
sys.path.insert(0, '/app')

from src.agents.simple import build_cascading_delegation, get_collector

def main():
    print("\n" + "="*80)
    print("EXAMPLE 3: Cascading Three-Agent Delegation (A → B → C)")
    print("="*80 + "\n")
    
    collector = get_collector()
    collector.clear()
    
    collector.set_correlation("run_cascade_001")
    
    graph = build_cascading_delegation()
    result = graph.invoke({})
    
    collector.print_trace()
    
    # Print as JSON for later processing
    print("\nEvents as JSON:")
    import json
    print(json.dumps(collector.get_events(), indent=2))
    
    print(f"\nTotal events: {len(collector.get_events())}")

if __name__ == "__main__":
    main()
