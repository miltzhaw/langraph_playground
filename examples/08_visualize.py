#!/usr/bin/env python
"""Example 8: Visualize causal DAG in multiple formats"""

import sys
sys.path.insert(0, '/app')

from src.agents.simple import build_cascading_delegation, get_collector
from reconstruction.dag_builder import DAGBuilder
from visualization.dag_visualizer import DAGVisualizer


def main():
    print("\n" + "="*100)
    print("EXAMPLE 8: Visualize Causal DAG")
    print("="*100 + "\n")
    
    # Collect and reconstruct
    collector = get_collector()
    collector.clear()
    collector.set_correlation("viz_001")
    
    graph = build_cascading_delegation()
    graph.invoke({})
    
    events = collector.get_events()
    builder = DAGBuilder()
    dag = builder.build(events)
    
    print(f"Collected {len(events)} events")
    print(f"Reconstructed {len(dag.edges)} causal edges\n")
    
    # Create visualizations
    visualizer = DAGVisualizer()
    
    print("Creating visualizations...\n")
    
    # 1. Graphviz (DOT format)
    visualizer.create_graphviz(dag, output_file="dag_visualization.dot")
    
    # 2. Mermaid (markdown-embeddable)
    visualizer.create_mermaid(dag, output_file="dag_visualization.md")
    
    # 3. Interactive HTML (vis.js)
    visualizer.create_html_interactive(dag, output_file="dag_interactive.html")
    
    # 4. Summary table
    visualizer.create_summary_table(dag, output_file="dag_summary.md")
    
    print("\n" + "="*100)
    print("VISUALIZATION FILES CREATED")
    print("="*100)
    print("""
Generated Files:

1. dag_visualization.dot
   Format: Graphviz DOT
   Use: dot -Tpng dag_visualization.dot -o dag_visualization.png
   
2. dag_visualization.md
   Format: Mermaid diagram (markdown)
   Use: View in GitHub, Notion, Confluence, etc.
   
3. dag_interactive.html ⭐
   Format: Interactive HTML (vis.js)
   Use: Open in web browser, zoom/pan/drag nodes
   
4. dag_summary.md
   Format: Markdown tables
   Use: Include in reports and documentation

Next Steps:
- View dag_interactive.html in your browser for interactive exploration
- Use dag_visualization.dot for static publication-quality images
- Share dag_visualization.md for quick documentation
- Include dag_summary.md in research papers and reports
""")
    print("="*100 + "\n")


if __name__ == "__main__":
    main()
