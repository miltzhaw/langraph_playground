"""Visualize causal DAGs as images and interactive graphs"""

import json
from typing import Dict, List, Set, Tuple
import os


class DAGVisualizer:
    """Visualize causal DAGs using Graphviz"""
    
    def __init__(self):
        self.graph_template = """
digraph CausalDAG {{
    rankdir=TB;
    bgcolor=white;
    node [shape=box, style=filled, fontname="Arial", fontsize=10];
    edge [fontname="Arial", fontsize=9];
    
    {nodes}
    
    {edges}
}}
"""
    
    def create_graphviz(self, dag, output_file="dag.dot"):
        """
        Create Graphviz DOT file for DAG visualization
        
        Args:
            dag: CausalDAG object
            output_file: Output .dot filename
        """
        # Group events by agent
        events_by_agent = {}
        for event in dag.events:
            agent = event['agent_id']
            if agent not in events_by_agent:
                events_by_agent[agent] = []
            events_by_agent[agent].append(event)
        
        # Define colors for event types
        colors = {
            'REASONING_STEP': '#E8F4F8',
            'GOAL_CREATED': '#C8E6C9',
            'GOAL_DELEGATED': '#FFE0B2',
            'TOOL_INVOKED': '#F8BBD0',
            'GOAL_FAILED': '#FFCDD2',
            'GOAL_COMPLETED': '#C8E6C9',
            'INTER_AGENT_MESSAGE': '#D1C4E9',
        }
        
        # Define colors for agents
        agent_colors = {
            'agent_a': '#BBDEFB',
            'agent_b': '#C8E6C9',
            'agent_c': '#FFE0B2',
            'agent_d': '#F8BBD0',
        }
        
        # Create nodes
        nodes = []
        for agent in sorted(events_by_agent.keys()):
            # Agent cluster/subgraph
            events = sorted(events_by_agent[agent], key=lambda x: x['timestamp'])
            
            node_lines = []
            for i, event in enumerate(events):
                event_id = event['event_id'][:8]  # Short ID
                event_type = event['event_type']
                color = colors.get(event_type, '#E0E0E0')
                
                label = event_type + "\\n(" + event_id + ")"
                node_line = '    "' + event['event_id'] + '" [label="' + label + '", fillcolor="' + color + '"];'
                node_lines.append(node_line)
            
            nodes.extend(node_lines)
        
        # Create edges with labels
        edges = []
        edge_colors = {
            'delegation': '#FF6B6B',
            'intra_agent_sequence': '#4ECDC4',
            'inferred_by_proximity': '#95E1D3',
            'message_passing': '#FFE66D',
        }
        
        for (from_id, to_id) in dag.edges:
            edge_detail = dag.edge_details.get((from_id, to_id))
            reason = edge_detail.reason if edge_detail else 'unknown'
            color = edge_colors.get(reason, '#999999')
            
            edge_label = reason.replace('_', ' ')
            edge_line = '    "' + from_id + '" -> "' + to_id + '" [label="' + edge_label + '", color="' + color + '", penwidth=2.0];'
            edges.append(edge_line)
        
        # Create graph
        graph_content = self.graph_template.format(
            nodes='\n'.join(nodes),
            edges='\n'.join(edges)
        )
        
        # Write to file
        with open(output_file, 'w') as f:
            f.write(graph_content)
        
        msg1 = "\n✓ Created Graphviz file: " + output_file
        msg2 = "  To render: dot -Tpng " + output_file + " -o " + output_file.replace('.dot', '.png')
        print(msg1)
        print(msg2)
        
        return output_file
    
    def create_mermaid(self, dag, output_file="dag.md"):
        """
        Create Mermaid diagram (markdown-embeddable)
        
        Args:
            dag: CausalDAG object
            output_file: Output .md filename with mermaid syntax
        """
        lines = ["```mermaid", "graph TD"]
        
        # Add nodes with styling
        event_style = {
            'REASONING_STEP': 'style REASONING_STEP fill:#E8F4F8',
            'GOAL_CREATED': 'style GOAL_CREATED fill:#C8E6C9',
            'GOAL_DELEGATED': 'style GOAL_DELEGATED fill:#FFE0B2',
            'TOOL_INVOKED': 'style TOOL_INVOKED fill:#F8BBD0',
            'GOAL_FAILED': 'style GOAL_FAILED fill:#FFCDD2',
        }
        
        for (from_id, to_id) in dag.edges:
            from_event = next((e for e in dag.events if e['event_id'] == from_id), None)
            to_event = next((e for e in dag.events if e['event_id'] == to_id), None)
            
            if from_event and to_event:
                from_type = from_event['event_type']
                to_type = to_event['event_type']
                from_agent = from_event['agent_id']
                to_agent = to_event['agent_id']
                
                from_label = from_type + " (" + from_agent + ")"
                to_label = to_type + " (" + to_agent + ")"
                
                from_key = from_id[:8]
                to_key = to_id[:8]
                
                edge_detail = dag.edge_details.get((from_id, to_id))
                reason = edge_detail.reason if edge_detail else 'unknown'
                
                lines.append('    ' + from_key + '["' + from_label + '"]')
                lines.append('    ' + to_key + '["' + to_label + '"]')
                lines.append('    ' + from_key + ' -->|' + reason + '| ' + to_key)
        
        lines.append("```")
        
        content = '\n'.join(lines)
        
        with open(output_file, 'w') as f:
            f.write(content)
        
        print("\n✓ Created Mermaid diagram: " + output_file)
        print("  View in: GitHub markdown, Notion, Confluence, etc.")
        
        return output_file
    
    def create_html_interactive(self, dag, output_file="dag_interactive.html"):
        """
        Create interactive HTML visualization using vis.js
        
        Args:
            dag: CausalDAG object
            output_file: Output .html filename
        """
        # Prepare nodes and edges for vis.js
        nodes = []
        edges = []
        
        event_colors = {
            'REASONING_STEP': '#E8F4F8',
            'GOAL_CREATED': '#C8E6C9',
            'GOAL_DELEGATED': '#FFE0B2',
            'TOOL_INVOKED': '#F8BBD0',
            'GOAL_FAILED': '#FFCDD2',
            'GOAL_COMPLETED': '#C8E6C9',
        }
        
        # Create nodes
        for event in dag.events:
            event_id = event['event_id']
            event_type = event['event_type']
            agent_id = event['agent_id']
            color = event_colors.get(event_type, '#E0E0E0')
            
            short_id = event_id[:6]
            label = f"{event_type}\n{agent_id}\n({short_id})"
            
            nodes.append({
                'id': event_id,
                'label': label,
                'color': color,
                'title': json.dumps(event['payload'], indent=2),
                'font': {'size': 12},
            })
        
        # Create edges
        edge_colors = {
            'delegation': '#FF6B6B',
            'intra_agent_sequence': '#4ECDC4',
            'inferred_by_proximity': '#95E1D3',
            'message_passing': '#FFE66D',
        }
        
        for (from_id, to_id) in dag.edges:
            edge_detail = dag.edge_details.get((from_id, to_id))
            reason = edge_detail.reason if edge_detail else 'unknown'
            color = edge_colors.get(reason, '#999999')
            
            edges.append({
                'from': from_id,
                'to': to_id,
                'label': reason,
                'color': color,
                'arrows': 'to',
                'font': {'size': 10},
            })
        
        # Create HTML
        nodes_json = json.dumps(nodes)
        edges_json = json.dumps(edges)
        num_events = len(dag.events)
        num_edges = len(dag.edges)
        agents = ', '.join(sorted(set(e['agent_id'] for e in dag.events)))
        
        html_content = """<!DOCTYPE html>
<html>
<head>
    <title>SPECTRA - Causal DAG Visualization</title>
    <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <style type="text/css">
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        #network {
            width: 100%;
            height: 800px;
            border: 1px solid #ddd;
            background-color: white;
            border-radius: 5px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        h1 {
            color: #333;
            margin-bottom: 10px;
        }
        .info {
            background-color: #e3f2fd;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
            border-left: 4px solid #2196F3;
        }
        .legend {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }
        .legend-item {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .legend-color {
            width: 30px;
            height: 30px;
            border-radius: 3px;
            border: 1px solid #ddd;
        }
        .controls {
            margin-bottom: 20px;
        }
        button {
            padding: 10px 20px;
            margin-right: 10px;
            background-color: #2196F3;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
        }
        button:hover {
            background-color: #1976D2;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔍 SPECTRA - Causal DAG Visualization</h1>
        
        <div class="info">
            <strong>Events:</strong> """ + str(num_events) + """ | 
            <strong>Causal Edges:</strong> """ + str(num_edges) + """ |
            <strong>Agents:</strong> """ + agents + """
        </div>
        
        <div class="legend">
            <div class="legend-item">
                <div class="legend-color" style="background-color: #E8F4F8;"></div>
                <span>Reasoning Step</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background-color: #FFE0B2;"></div>
                <span>Goal Delegated</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background-color: #F8BBD0;"></div>
                <span>Tool Invoked</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background-color: #FFCDD2;"></div>
                <span>Goal Failed</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background-color: #C8E6C9;"></div>
                <span>Goal Completed</span>
            </div>
        </div>
        
        <div class="controls">
            <button onclick="zoomIn()">🔍 Zoom In</button>
            <button onclick="zoomOut()">🔍 Zoom Out</button>
            <button onclick="fitToScreen()">📐 Fit Screen</button>
            <button onclick="downloadPNG()">💾 Download PNG</button>
        </div>
        
        <div id="network"></div>
    </div>

    <script type="text/javascript">
        var nodes = new vis.DataSet(""" + nodes_json + """);
        var edges = new vis.DataSet(""" + edges_json + """);

        var container = document.getElementById('network');
        var data = {
            nodes: nodes,
            edges: edges
        };

        var options = {
            physics: {
                enabled: true,
                stabilization: {
                    iterations: 200
                }
            },
            nodes: {
                font: {
                    size: 14,
                    color: '#333'
                },
                borderWidth: 2,
                borderWidthSelected: 3
            },
            edges: {
                smooth: {
                    type: 'continuous'
                },
                arrows: {
                    to: {
                        enabled: true,
                        scaleFactor: 1.2
                    }
                }
            }
        };

        var network = new vis.Network(container, data, options);

        function zoomIn() {
            var scale = network.getScale();
            network.setOptions({ physics: false });
            network.moveTo({ scale: scale * 1.2 });
        }

        function zoomOut() {
            var scale = network.getScale();
            network.setOptions({ physics: false });
            network.moveTo({ scale: scale / 1.2 });
        }

        function fitToScreen() {
            network.fit({ animation: true });
        }

        function downloadPNG() {
            var canvas = network.canvas.canvas;
            var link = document.createElement('a');
            link.href = canvas.toDataURL();
            link.download = 'dag_visualization.png';
            link.click();
        }
    </script>
</body>
</html>
"""
        
        with open(output_file, 'w') as f:
            f.write(html_content)
        
        print(f"\n✓ Created interactive HTML: {output_file}")
        print(f"  Open in browser to interact with the DAG")
        
        return output_file
    
    def create_summary_table(self, dag, output_file="dag_summary.md"):
        """
        Create a markdown table summarizing the DAG
        
        Args:
            dag: CausalDAG object
            output_file: Output .md filename
        """
        lines = [
            "# Causal DAG Summary",
            "",
            "**Events:** " + str(len(dag.events)) + " | **Causal Edges:** " + str(len(dag.edges)),
            ""
        ]
        
        # Event types table
        lines.append("## Events by Type")
        lines.append("")
        lines.append("| Event Type | Count | Agents |")
        lines.append("|---|---|---|")
        
        event_types = {}
        for event in dag.events:
            etype = event['event_type']
            if etype not in event_types:
                event_types[etype] = set()
            event_types[etype].add(event['agent_id'])
        
        for etype in sorted(event_types.keys()):
            agents = ', '.join(sorted(event_types[etype]))
            count = len([e for e in dag.events if e['event_type'] == etype])
            lines.append("| " + etype + " | " + str(count) + " | " + agents + " |")
        
        # Edges by reason
        lines.append("")
        lines.append("## Causal Edges by Reason")
        lines.append("")
        lines.append("| Reason | Count |")
        lines.append("|---|---|")
        
        reasons = {}
        for (from_id, to_id) in dag.edges:
            edge = dag.edge_details.get((from_id, to_id))
            reason = edge.reason if edge else 'unknown'
            reasons[reason] = reasons.get(reason, 0) + 1
        
        for reason in sorted(reasons.keys()):
            lines.append("| " + reason + " | " + str(reasons[reason]) + " |")
        
        content = '\n'.join(lines)
        
        with open(output_file, 'w') as f:
            f.write(content)
        
        print("\n✓ Created summary table: " + output_file)
        
        return output_file
