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
            edge_detail = dag.edge_details.get((from_id, to_id)) if hasattr(dag, 'edge_details') else None
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
                
                edge_detail = dag.edge_details.get((from_id, to_id)) if hasattr(dag, 'edge_details') else None
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
        edge_colors_map = {
            'delegation': '#FF6B6B',
            'intra_agent_sequence': '#4ECDC4',
            'inferred_by_proximity': '#95E1D3',
            'message_passing': '#FFE66D',
        }
        
        for (from_id, to_id) in dag.edges:
            edge_detail = dag.edge_details.get((from_id, to_id)) if hasattr(dag, 'edge_details') else None
            reason = edge_detail.reason if edge_detail else 'unknown'
            color = edge_colors_map.get(reason, '#999999')
            
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
        
        # Count event types
        event_type_counts = {}
        for event in dag.events:
            etype = event['event_type']
            event_type_counts[etype] = event_type_counts.get(etype, 0) + 1
        
        event_stats = '<br>'.join([f"{k}: {v}" for k, v in sorted(event_type_counts.items())])
        
        # Extract event list for timeline
        event_list_data = [{"id": e["event_id"][:8], "type": e["event_type"], "agent": e["agent_id"]} for e in dag.events]
        event_list_json = json.dumps(event_list_data)
        
        html_content = """<!DOCTYPE html>
<html>
<head>
    <title>SPECTRA - Causal DAG Visualization</title>
    <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <style type="text/css">
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1600px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        
        .header h1 {
            font-size: 28px;
            margin-bottom: 10px;
        }
        
        .header p {
            font-size: 14px;
            opacity: 0.9;
        }
        
        .content {
            display: grid;
            grid-template-columns: 300px 1fr 300px;
            gap: 20px;
            padding: 20px;
            height: calc(100vh - 200px);
        }
        
        .sidebar {
            background: #f8f9fa;
            border-radius: 8px;
            padding: 20px;
            overflow-y: auto;
            border: 1px solid #e0e0e0;
        }
        
        .sidebar h3 {
            color: #333;
            margin-bottom: 15px;
            font-size: 14px;
            text-transform: uppercase;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
        }
        
        .stat-group {
            margin-bottom: 20px;
        }
        
        .stat-item {
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            font-size: 13px;
            border-bottom: 1px solid #ddd;
        }
        
        .stat-label {
            color: #666;
            font-weight: 500;
        }
        
        .stat-value {
            color: #667eea;
            font-weight: bold;
        }
        
        .legend {
            background: white;
            padding: 15px;
            border-radius: 6px;
            margin-top: 20px;
            border: 1px solid #ddd;
        }
        
        .legend-item {
            display: flex;
            align-items: center;
            margin-bottom: 10px;
            font-size: 12px;
        }
        
        .legend-color {
            width: 20px;
            height: 20px;
            border-radius: 3px;
            margin-right: 8px;
            border: 1px solid #999;
        }
        
        #network {
            height: 75vh;
            border: 1px solid #ddd;
            border-radius: 8px;
            background: white;
            position: relative;
        }
        
        .controls {
            position: absolute;
            bottom: 20px;
            left: 20px;
            background: white;
            padding: 12px;
            border-radius: 6px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            display: flex;
            gap: 8px;
            z-index: 100;
        }
        
        button {
            padding: 8px 12px;
            background-color: #667eea;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
            font-weight: 500;
            transition: all 0.3s;
        }
        
        button:hover {
            background-color: #764ba2;
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        }
        
        .right-sidebar {
            background: #f8f9fa;
            border-radius: 8px;
            padding: 20px;
            overflow-y: auto;
            border: 1px solid #e0e0e0;
        }
        
        .event-list {
            font-size: 12px;
        }
        
        .event-item {
            background: white;
            padding: 10px;
            margin-bottom: 8px;
            border-radius: 4px;
            border-left: 3px solid #667eea;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .event-item:hover {
            background: #f0f0f0;
            transform: translateX(3px);
        }
        
        .event-type {
            font-weight: bold;
            color: #667eea;
            font-size: 11px;
        }
        
        .event-agent {
            color: #666;
            font-size: 11px;
            margin-top: 3px;
        }
        
        .info-panel {
            background: white;
            padding: 15px;
            border-radius: 6px;
            border: 1px solid #ddd;
            margin-top: 20px;
            max-height: 300px;
            overflow-y: auto;
            font-size: 12px;
        }
        
        .info-title {
            font-weight: bold;
            color: #333;
            margin-bottom: 10px;
            border-bottom: 1px solid #ddd;
            padding-bottom: 8px;
        }
        
        .info-detail {
            color: #666;
            line-height: 1.5;
            word-break: break-word;
        }
        
        @media (max-width: 1200px) {
            .content {
                grid-template-columns: 1fr;
                height: auto;
            }
            
            .sidebar, .right-sidebar {
                display: none;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 SPECTRA - Semantic Causal DAG Visualization</h1>
            <p>Interactive exploration of multi-agent reasoning and coordination</p>
        </div>
        
        <div class="content">
            <!-- Left Sidebar: Statistics -->
            <div class="sidebar">
                <h3>📊 Execution Summary</h3>
                <div class="stat-group">
                    <div class="stat-item">
                        <span class="stat-label">Total Events:</span>
                        <span class="stat-value">""" + str(num_events) + """</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label">Causal Edges:</span>
                        <span class="stat-value">""" + str(num_edges) + """</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label">Agents:</span>
                        <span class="stat-value">""" + str(len(set(e['agent_id'] for e in dag.events))) + """</span>
                    </div>
                </div>
                
                <h3>📈 Event Types</h3>
                <div class="stat-group">
                    """ + "".join([f'<div class="stat-item"><span class="stat-label">{k}:</span><span class="stat-value">{v}</span></div>' for k, v in sorted(event_type_counts.items())]) + """
                </div>
                
                <div class="legend">
                    <strong style="font-size: 12px;">Event Type Colors</strong>
                    <div class="legend-item">
                        <div class="legend-color" style="background-color: #E8F4F8;"></div>
                        <span>Reasoning Step</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-color" style="background-color: #C8E6C9;"></div>
                        <span>Goal Created</span>
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
                        <div class="legend-color" style="background-color: #B2DFDB;"></div>
                        <span>Goal Completed</span>
                    </div>
                </div>
            </div>
            
            <!-- Center: Network Visualization -->
            <div style="position: relative;">
                <div id="network"></div>
                <div class="controls">
                    <button onclick="zoomIn()">🔍+ Zoom In</button>
                    <button onclick="zoomOut()">🔍- Zoom Out</button>
                    <button onclick="fitToScreen()">📐 Fit</button>
                    <button onclick="resetPhysics()">🔄 Reset</button>
                    <button onclick="downloadPNG()">💾 PNG</button>
                </div>
            </div>
            
            <!-- Right Sidebar: Events and Details -->
            <div class="right-sidebar">
                <h3>📋 Event Timeline</h3>
                <div class="event-list" id="eventList"></div>
                
                <div class="info-panel">
                    <div class="info-title">ℹ️ Selected Event Details</div>
                    <div class="info-detail" id="eventInfo">
                        Click an event node to see details
                    </div>
                </div>
            </div>
        </div>
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
                    iterations: 200,
                    fit: true
                },
                barnesHut: {
                    gravitationalConstant: -26000,
                    centralGravity: 0.3,
                    springLength: 200
                }
            },
            nodes: {
                font: {
                    size: 13,
                    color: '#333',
                    face: 'Segoe UI'
                },
                borderWidth: 2,
                borderWidthSelected: 4,
                shadow: {
                    enabled: true,
                    color: 'rgba(0,0,0,0.2)',
                    size: 10,
                    x: 5,
                    y: 5
                }
            },
            edges: {
                smooth: {
                    type: 'continuous',
                    roundness: 0.5
                },
                arrows: {
                    to: {
                        enabled: true,
                        scaleFactor: 1.3,
                        type: 'arrow'
                    }
                },
                color: {
                    color: '#aaa',
                    highlight: '#667eea',
                    opacity: 0.6
                },
                width: 2,
                font: {
                    size: 11,
                    color: '#666',
                    background: {
                        enabled: true,
                        color: 'white'
                    }
                },
                shadow: {
                    enabled: true,
                    color: 'rgba(0,0,0,0.1)',
                    size: 5,
                    x: 3,
                    y: 3
                }
            }
        };

        var network = new vis.Network(container, data, options);

        // Event list
        var events = """ + event_list_json + """;
        var eventListHtml = events.map((e, i) => 
            `<div class="event-item" onclick="selectEvent('${e.id}')">
                <div class="event-type">${i+1}. ${e.type}</div>
                <div class="event-agent">${e.agent}</div>
            </div>`
        ).join('');
        document.getElementById('eventList').innerHTML = eventListHtml;

        function selectEvent(eventId) {
            var allEvents = """ + json.dumps(dag.events) + """;
            var event = allEvents.find(e => e.event_id.startsWith(eventId));
            if (event) {
                var html = `
                    <strong>${event.event_type}</strong><br>
                    Agent: <strong>${event.agent_id}</strong><br>
                    Time: ${event.timestamp.toFixed(3)}<br>
                    <hr>
                    <strong>Payload:</strong><br>
                    <pre>${JSON.stringify(event.payload, null, 2).substring(0, 500)}</pre>
                `;
                document.getElementById('eventInfo').innerHTML = html;
                nodes.update({id: event.event_id, borderWidth: 4});
            }
        }

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

        function resetPhysics() {
            network.setOptions({ physics: { enabled: true } });
            network.stabilize();
        }

        function downloadPNG() {
            network.once("afterDrawing", function(ctx) {
                var scaleFactor = 2; // higher resolution
                var canvas = ctx.canvas;

                var exportCanvas = document.createElement("canvas");
                exportCanvas.width = canvas.width * scaleFactor;
                exportCanvas.height = canvas.height * scaleFactor;

                var exportCtx = exportCanvas.getContext("2d");
                exportCtx.scale(scaleFactor, scaleFactor);
                exportCtx.drawImage(canvas, 0, 0);

                var link = document.createElement("a");
                link.href = exportCanvas.toDataURL("image/png");
                link.download = "causal_dag_highres.png";

                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
            });

            network.redraw();
        }

        // Click on node to show details
        network.on('click', function(params) {
            if (params.nodes.length > 0) {
                var nodeId = params.nodes[0];
                selectEvent(nodeId.substring(0, 8));
            }
        });
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
            edge = dag.edge_details.get((from_id, to_id)) if hasattr(dag, 'edge_details') else None
            reason = edge.reason if edge else 'unknown'
            reasons[reason] = reasons.get(reason, 0) + 1
        
        for reason in sorted(reasons.keys()):
            lines.append("| " + reason + " | " + str(reasons[reason]) + " |")
        
        content = '\n'.join(lines)
        
        with open(output_file, 'w') as f:
            f.write(content)
        
        print("\n✓ Created summary table: " + output_file)
        
        return output_file