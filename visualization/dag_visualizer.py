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
        """Create Graphviz DOT file for DAG visualization."""
        events_by_agent = {}
        for event in dag.events:
            agent = event['agent_id']
            events_by_agent.setdefault(agent, []).append(event)

        colors = {
            'REASONING_STEP':     '#E8F4F8',
            'GOAL_CREATED':       '#C8E6C9',
            'GOAL_DELEGATED':     '#FFE0B2',
            'TOOL_INVOKED':       '#F8BBD0',
            'GOAL_FAILED':        '#FFCDD2',
            'GOAL_COMPLETED':     '#C8E6C9',
            'INTER_AGENT_MESSAGE':'#D1C4E9',
        }

        nodes = []
        for agent in sorted(events_by_agent.keys()):
            events = sorted(events_by_agent[agent], key=lambda x: x['timestamp'])
            for event in events:
                eid   = event['event_id'][:8]
                color = colors.get(event['event_type'], '#E0E0E0')
                label = event['event_type'] + "\\n(" + eid + ")"
                nodes.append(
                    '    "' + event['event_id'] + '" [label="' + label +
                    '", fillcolor="' + color + '"];'
                )

        edge_colors = {
            'delegation':           '#FF6B6B',
            'intra_agent_sequence': '#4ECDC4',
            'inferred_by_proximity':'#95E1D3',
            'message_passing':      '#FFE66D',
        }

        edges = []
        for (from_id, to_id) in dag.edges:
            detail = dag.edge_details.get((from_id, to_id)) if hasattr(dag, 'edge_details') else None
            reason = detail.reason if detail else 'unknown'
            color  = edge_colors.get(reason, '#999999')
            edges.append(
                '    "' + from_id + '" -> "' + to_id +
                '" [label="' + reason.replace('_', ' ') +
                '", color="' + color + '", penwidth=2.0];'
            )

        graph_content = self.graph_template.format(
            nodes='\n'.join(nodes),
            edges='\n'.join(edges),
        )
        with open(output_file, 'w') as f:
            f.write(graph_content)

        print("\n✓ Created Graphviz file: " + output_file)
        print("  To render: dot -Tpng " + output_file + " -o " + output_file.replace('.dot', '.png'))
        return output_file

    def create_mermaid(self, dag, output_file="dag.md"):
        """Create separate Mermaid diagrams per agent."""
        events_by_agent = {}
        for event in dag.events:
            events_by_agent.setdefault(event["agent_id"], []).append(event)

        blocks = []
        for agent, events in sorted(events_by_agent.items()):
            lines = [f"## Agent: {agent}", "", "```mermaid", "graph TD"]
            for event in events:
                nid   = event["event_id"][:8]
                label = f"{event['event_type']} ({nid})"
                lines.append(f'    {nid}["{label}"]')
            for (from_id, to_id) in dag.edges:
                fe = next((e for e in events if e["event_id"] == from_id), None)
                te = next((e for e in events if e["event_id"] == to_id),   None)
                if fe and te:
                    lines.append(f"    {from_id[:8]} --> {to_id[:8]}")
            lines += ["```", ""]
            blocks.append("\n".join(lines))

        with open(output_file, "w") as f:
            f.write("\n\n".join(blocks))

        print(f"\n✓ Created multi-diagram Mermaid file: {output_file}")
        return output_file

    # ------------------------------------------------------------------
    # INTERACTIVE HTML  (enhanced)
    # ------------------------------------------------------------------
    def create_html_interactive(self, dag, output_file="dag_interactive.html"):
        """
        Create interactive HTML visualization using vis.js.

        Enhancements over the original:
        - Distinct node shapes per event type (ellipse / box / diamond)
        - Agent-coloured node borders for quick lane identification
        - Dashed red border on TOOL_INVOKED nodes where LLM passed
          placeholder values (reasoning-execution gap indicator)
        - 🔗 Handoffs toggle: adds dashed grey edges showing implicit
          pipeline handoffs between agents (not reconstructed by DAG rules)
        - Edge dimming: clicking a node dims unrelated edges
        - Reasoning-execution gap warning in the detail panel
        - Relative timestamps (+Xs) in the event timeline
        - Per-agent LLM latency derived from timestamps
        - Callout notes explaining key observations
        """
        # ── collect stats ────────────────────────────────────────────
        event_type_counts = {}
        for e in dag.events:
            event_type_counts[e['event_type']] = event_type_counts.get(e['event_type'], 0) + 1

        num_events  = len(dag.events)
        num_edges   = len(dag.edges)
        num_agents  = len(set(e['agent_id'] for e in dag.events))
        num_failures = event_type_counts.get('GOAL_FAILED', 0)
        num_tools    = event_type_counts.get('TOOL_INVOKED', 0)

        event_type_stats_html = "".join([
            f'<div class="stat-item"><span class="stat-label">{k}:</span>'
            f'<span class="stat-value">{v}</span></div>'
            for k, v in sorted(event_type_counts.items())
        ])

        # ── per-agent latency (GOAL_CREATED → GOAL_COMPLETED) ────────
        agent_latency = {}
        for agent in set(e['agent_id'] for e in dag.events):
            evts = sorted([e for e in dag.events if e['agent_id'] == agent],
                          key=lambda x: x['timestamp'])
            if evts:
                agent_latency[agent] = evts[-1]['timestamp'] - evts[0]['timestamp']

        latency_html = "".join([
            f'<div class="stat-item">'
            f'<span class="stat-label">{a}</span>'
            f'<span class="stat-value">~{int(v)}s</span></div>'
            for a, v in sorted(agent_latency.items())
        ])

        # ── implicit pipeline handoff edges ──────────────────────────
        # Detect GOAL_COMPLETED of agent N → GOAL_CREATED of agent N+1
        # by finding pairs where timestamps are closest across agent boundaries.
        completed = sorted(
            [e for e in dag.events if e['event_type'] == 'GOAL_COMPLETED'],
            key=lambda x: x['timestamp']
        )
        created = sorted(
            [e for e in dag.events if e['event_type'] == 'GOAL_CREATED'],
            key=lambda x: x['timestamp']
        )
        handoff_pairs = []
        for c in completed:
            # find the next GOAL_CREATED from a different agent
            for g in created:
                if g['agent_id'] != c['agent_id'] and g['timestamp'] > c['timestamp']:
                    handoff_pairs.append((c['event_id'], g['event_id']))
                    break

        handoff_edges_js = json.dumps([
            {
                'id':     f'h{i}',
                'from':   f,
                'to':     t,
                'label':  'pipeline handoff',
                'color':  '#aaa',
                'dashes': True,
                'arrows': 'to',
                'width':  1,
                'font':   {'size': 9, 'color': '#aaa',
                           'background': {'enabled': True, 'color': 'white'}},
                'smooth': {'type': 'curvedCW', 'roundness': 0.3},
            }
            for i, (f, t) in enumerate(handoff_pairs)
        ])

        # ── vis.js node / edge data ───────────────────────────────────
        AGENT_BORDER = {
            'ingestion_agent': '#1565c0',
            'analysis_agent':  '#6a1b9a',
            'citation_agent':  '#2e7d32',
            'synthesis_agent': '#e65100',
        }
        EVENT_COLOR = {
            'GOAL_CREATED':   '#C8E6C9',
            'REASONING_STEP': '#E8F4F8',
            'TOOL_INVOKED':   '#F8BBD0',
            'GOAL_COMPLETED': '#B2DFDB',
            'GOAL_FAILED':    '#FFCDD2',
            'GOAL_DELEGATED': '#FFE0B2',
        }
        EVENT_SHAPE = {
            'GOAL_CREATED':   'ellipse',
            'REASONING_STEP': 'box',
            'TOOL_INVOKED':   'diamond',
            'GOAL_COMPLETED': 'ellipse',
            'GOAL_FAILED':    'ellipse',
            'GOAL_DELEGATED': 'ellipse',
        }

        vis_nodes = []
        for e in dag.events:
            has_gap = (
                e['event_type'] == 'TOOL_INVOKED' and
                '<' in json.dumps(e.get('payload', {}).get('params', {}))
            )
            border = '#e53935' if has_gap else AGENT_BORDER.get(e['agent_id'], '#999')
            vis_nodes.append({
                'id':    e['event_id'],
                'label': e['event_type'].replace('_', '\n') + '\n' +
                         e['agent_id'].replace('_agent', '') + '\n(' +
                         e['event_id'][:6] + ')',
                'color': {
                    'background': EVENT_COLOR.get(e['event_type'], '#eee'),
                    'border':     border,
                    'highlight':  {'background': '#fff9c4', 'border': '#f9a825'},
                },
                'borderWidth':  3 if has_gap else 2,
                'borderDashes': [4, 3] if has_gap else False,
                'shape': EVENT_SHAPE.get(e['event_type'], 'box'),
                'font':  {'size': 11, 'color': '#333'},
                'title': (
                    f"<b>{e['event_type']}</b><br><small>{e['agent_id']}</small>"
                    f"<pre style='font-size:10px;max-width:280px;white-space:pre-wrap'>"
                    f"{json.dumps(e['payload'], indent=2)[:400]}</pre>"
                ),
            })

        edge_colors_map = {
            'delegation':           '#FF6B6B',
            'intra_agent_sequence': '#4ECDC4',
            'inferred_by_proximity':'#95E1D3',
            'message_passing':      '#FFE66D',
        }
        vis_edges = []
        for (from_id, to_id) in dag.edges:
            detail = dag.edge_details.get((from_id, to_id)) if hasattr(dag, 'edge_details') else None
            reason = detail.reason if detail else 'unknown'
            color  = edge_colors_map.get(reason, '#999999')
            vis_edges.append({
                'from':   from_id,
                'to':     to_id,
                'label':  reason,
                'color':  {'color': color, 'opacity': 0.8},
                'arrows': 'to',
                'width':  2,
                'font':   {'size': 9, 'color': '#888',
                           'background': {'enabled': True, 'color': 'white'}},
                'smooth': {'type': 'continuous', 'roundness': 0.4},
            })

        # ── event timeline data ───────────────────────────────────────
        t0 = dag.events[0]['timestamp'] if dag.events else 0
        timeline_data = [
            {
                'id':    e['event_id'][:8],
                'type':  e['event_type'],
                'agent': e['agent_id'],
                'rel_ts': round(e['timestamp'] - t0, 1),
            }
            for e in dag.events
        ]

        # ── full event list for detail panel ─────────────────────────
        all_events_js = json.dumps(dag.events)

        # ── assemble HTML ─────────────────────────────────────────────
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>SPECTRA - Causal DAG Visualization</title>
    <script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
<style>
        *{{margin:0;padding:0;box-sizing:border-box}}
        /* Fixed body to prevent double scrollbars */
        body{{font-family:'Segoe UI',sans-serif;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);height:100vh;padding:20px;overflow:hidden}}
        
        /* Container fits the viewport */
        .container{{max-width:1600px;margin:0 auto;background:white;border-radius:12px;box-shadow:0 20px 60px rgba(0,0,0,.3);overflow:hidden;height:100%;display:flex;flex-direction:column}}
        
        .header{{background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:white;padding:20px 30px;text-align:center;flex-shrink:0}}
        .header h1{{font-size:24px;margin-bottom:6px}}
        .header p{{font-size:13px;opacity:.85}}

        /* Content area takes remaining height and defines fixed columns */
        .content{{
            display:grid;
            grid-template-columns:280px 1fr 300px;
            gap:16px;
            padding:16px;
            flex-grow:1;
            overflow:hidden; /* Prevents the central area from expanding past the screen */
            height: calc(100% - 80px); /* Adjusts for header height */
        }}

        /* Sidebars have independent scrolling */
        .sidebar,.right-sidebar{{
            background:#f8f9fa;
            border-radius:8px;
            padding:16px;
            overflow-y:auto;
            border:1px solid #e0e0e0;
            font-size:12px;
            height: 100%; 
        }}

        .sidebar h3,.right-sidebar h3{{color:#444;font-size:11px;text-transform:uppercase;letter-spacing:.5px;border-bottom:2px solid #667eea;padding-bottom:8px;margin-bottom:12px}}
        .stat-item{{display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #eee}}
        .stat-label{{color:#666}}.stat-value{{color:#667eea;font-weight:bold}}
        .agent-badge{{display:inline-block;padding:2px 7px;border-radius:12px;font-size:10px;font-weight:600;margin:2px 0}}
        .ag-ingestion{{background:#e3f2fd;color:#1565c0}}.ag-analysis{{background:#f3e5f5;color:#6a1b9a}}
        .ag-citation{{background:#e8f5e9;color:#2e7d32}}.ag-synthesis{{background:#fff3e0;color:#e65100}}
        .legend-item{{display:flex;align-items:center;margin-bottom:8px;font-size:11px}}
        .lc{{width:16px;height:16px;border-radius:3px;margin-right:8px;border:1px solid #bbb;flex-shrink:0}}
        .ll{{width:26px;height:3px;margin-right:8px;flex-shrink:0;border-radius:2px}}

        /* Diagram wrapper and network - Fixed Height */
        .net-wrap{{position:relative;height:100%;min-height:0}}
        #network{{
            height:100%;
            width:100%;
            border:1px solid #ddd;
            border-radius:8px;
            background:#fafafa;
        }}

        .controls{{position:absolute;bottom:12px;left:12px;background:white;padding:10px;border-radius:6px;box-shadow:0 2px 10px rgba(0,0,0,.12);display:flex;gap:6px;z-index:100}}
        button{{padding:6px 10px;background:#667eea;color:white;border:none;border-radius:4px;cursor:pointer;font-size:11px;font-weight:500;transition:all .2s}}
        button:hover{{background:#764ba2;transform:translateY(-1px)}}
        .callout{{background:#fffde7;border-left:3px solid #f9a825;padding:8px 10px;border-radius:0 4px 4px 0;margin-bottom:10px;font-size:11px;color:#555;line-height:1.5}}
        .callout strong{{color:#e65100}}
        .event-item{{background:white;padding:8px 10px;margin-bottom:6px;border-radius:4px;border-left:3px solid #667eea;cursor:pointer;transition:all .15s}}
        .event-item:hover{{background:#f0f0f0;transform:translateX(2px)}}
        .event-item.selected{{border-left-color:#e65100;background:#fff8f5}}
        .event-type{{font-weight:bold;color:#667eea;font-size:10px}}
        .event-ts{{color:#bbb;font-size:10px;float:right}}
        .info-panel{{background:white;padding:12px;border-radius:6px;border:1px solid #ddd;margin-top:12px;font-size:11px;max-height:280px;overflow-y:auto}}
        .info-panel pre{{background:#f5f5f5;padding:8px;border-radius:4px;white-space:pre-wrap;word-break:break-all;font-size:10px;margin-top:6px}}
        .gap-warning{{background:#fce4ec;border:1px solid #f48fb1;border-radius:4px;padding:6px 8px;font-size:10px;color:#880e4f;margin:6px 0}}
        @media(max-width:1100px){{
            body{{overflow:auto;height:auto}}
            .container{{height:auto}}
            .content{{grid-template-columns:1fr;height:auto}}
            .sidebar,.right-sidebar{{display:none}}
            .net-wrap{{height:600px}}
        }}
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>🔍 SPECTRA — Semantic Causal DAG</h1>
        <p>Multi-Agent Reasoning Pipeline &nbsp;·&nbsp; {num_agents} agents &nbsp;·&nbsp; {num_events} events &nbsp;·&nbsp; {num_edges} causal edges &nbsp;·&nbsp; {num_failures} failures</p>
    </div>
    <div class="content">

        <!-- LEFT SIDEBAR -->
        <div class="sidebar">
            <h3>📊 Execution Summary</h3>
            <div class="stat-item"><span class="stat-label">Total Events</span><span class="stat-value">{num_events}</span></div>
            <div class="stat-item"><span class="stat-label">Causal Edges</span><span class="stat-value">{num_edges}</span></div>
            <div class="stat-item"><span class="stat-label">Agents</span><span class="stat-value">{num_agents}</span></div>
            <div class="stat-item"><span class="stat-label">Failures</span><span class="stat-value" style="color:{'#e53935' if num_failures else '#43a047'}">{num_failures}</span></div>
            <div class="stat-item"><span class="stat-label">Tool Invocations</span><span class="stat-value">{num_tools}</span></div>

            <h3 style="margin-top:14px">📈 Event Types</h3>
            {event_type_stats_html}

            <h3 style="margin-top:14px">🎨 Legend</h3>
            <div class="legend-item"><div class="lc" style="background:#C8E6C9"></div>GOAL_CREATED / COMPLETED</div>
            <div class="legend-item"><div class="lc" style="background:#E8F4F8"></div>REASONING_STEP</div>
            <div class="legend-item"><div class="lc" style="background:#F8BBD0"></div>TOOL_INVOKED</div>
            <div class="legend-item"><div class="lc" style="background:#FFCDD2"></div>GOAL_FAILED</div>
            <div class="legend-item"><div class="ll" style="background:#4ECDC4"></div>intra_agent_sequence</div>
            <div class="legend-item"><div class="ll" style="background:#95E1D3"></div>inferred_by_proximity</div>
            <div class="legend-item"><div style="width:26px;border-top:2px dashed #bbb;margin-right:8px"></div>pipeline handoff (implicit)</div>
            <div class="legend-item"><div class="lc" style="background:#F8BBD0;border:3px dashed #e53935"></div>reasoning-execution gap</div>

            <h3 style="margin-top:14px">⏱️ LLM Latency</h3>
            {latency_html}
        </div>

        <!-- CENTRE -->
        <div class="net-wrap">
            <div id="network"></div>
            <div class="controls">
                <button onclick="zoomIn()">🔍+</button>
                <button onclick="zoomOut()">🔍−</button>
                <button onclick="fitToScreen()">📐 Fit</button>
                <button onclick="resetPhysics()">🔄 Reset</button>
                <button onclick="toggleHandoffs()">🔗 Handoffs</button>
                <button onclick="downloadPNG()">💾 PNG</button>
            </div>
        </div>

        <!-- RIGHT SIDEBAR -->
        <div class="right-sidebar">
            <h3>📋 Event Timeline</h3>
            <div class="callout">
                <strong>Observation:</strong> {num_agents} isolated subgraphs — no cross-agent causal edges reconstructed. Toggle <b>🔗 Handoffs</b> to see implicit pipeline dependencies.
            </div>
            <div id="eventList"></div>
            <div class="info-panel">
                <div style="font-weight:bold;color:#333;border-bottom:1px solid #eee;padding-bottom:6px;margin-bottom:8px">ℹ️ Selected Event</div>
                <div id="eventInfo" style="color:#666;line-height:1.5">Click a node or event to inspect payload</div>
            </div>
        </div>

    </div>
</div>

<script>
var AGENT_CLASS = {{
    ingestion_agent:'ag-ingestion', analysis_agent:'ag-analysis',
    citation_agent:'ag-citation',   synthesis_agent:'ag-synthesis'
}};

var allEvents  = {all_events_js};
var timelineData = {json.dumps(timeline_data)};
var handoffEdges = {handoff_edges_js};

var nodes = new vis.DataSet({json.dumps(vis_nodes)});
var edges = new vis.DataSet({json.dumps(vis_edges)});

var network = new vis.Network(
    document.getElementById('network'),
    {{nodes, edges}},
    {{
        physics:{{enabled:true,stabilization:{{iterations:300,fit:true}},
                  barnesHut:{{gravitationalConstant:-28000,centralGravity:0.25,springLength:180}}}},
        nodes:{{shadow:{{enabled:true,color:'rgba(0,0,0,.15)',size:8,x:4,y:4}}}},
        edges:{{arrows:{{to:{{enabled:true,scaleFactor:1.2}}}},
               shadow:{{enabled:true,color:'rgba(0,0,0,.08)',size:4,x:2,y:2}}}},
        interaction:{{hover:true,tooltipDelay:100}},
    }}
);

// Build timeline
document.getElementById('eventList').innerHTML = timelineData.map((e,i) =>
    `<div class="event-item" id="ei-${{e.id}}" onclick="selectById('${{e.id}}')">
        <span class="event-ts">+${{e.rel_ts}}s</span>
        <div class="event-type">${{i+1}}. ${{e.type}}</div>
        <div><span class="agent-badge ${{AGENT_CLASS[e.agent]||''}}">${{e.agent}}</span></div>
    </div>`
).join('');

function selectById(shortId) {{
    var ev = allEvents.find(e => e.event_id.startsWith(shortId));
    if (!ev) return;
    document.querySelectorAll('.event-item').forEach(el => el.classList.remove('selected'));
    var el = document.getElementById('ei-' + shortId);
    if (el) {{ el.classList.add('selected'); el.scrollIntoView({{block:'nearest'}}); }}

    var hasGap = ev.event_type === 'TOOL_INVOKED' &&
        JSON.stringify(ev.payload.params||{{}}).includes('<');
    var gapHtml = hasGap
        ? `<div class="gap-warning">⚠️ <b>Reasoning-execution gap:</b> LLM passed placeholder values.
           Real objects were injected from pipeline state. The DAG records what the agent
           <i>said</i> it would do, not what was actually passed.</div>` : '';

    document.getElementById('eventInfo').innerHTML =
        `<b>${{ev.event_type}}</b> &nbsp;·&nbsp;
         <span class="agent-badge ${{AGENT_CLASS[ev.agent_id]||''}}">${{ev.agent_id}}</span><br>
         <small style="color:#aaa">t = ${{ev.timestamp.toFixed(3)}}</small>
         ${{gapHtml}}
         <pre>${{JSON.stringify(ev.payload, null, 2).substring(0, 600)}}</pre>`;

    network.selectNodes([ev.event_id]);
    network.focus(ev.event_id, {{scale:1.1, animation:true}});

    // Dim unrelated edges
    var connected = network.getConnectedEdges(ev.event_id);
    var allIds = edges.getIds();
    edges.update(allIds.map(id => ({{id, color: {{opacity: connected.includes(id) ? 1.0 : 0.15}}}})));
    network.once('blurNode', () =>
        edges.update(allIds.map(id => ({{id, color: {{opacity: 0.8}}}})))
    );
}}

network.on('click', p => {{
    if (p.nodes.length) selectById(p.nodes[0].substring(0, 8));
}});

var handoffsOn = false;
function toggleHandoffs() {{
    handoffsOn = !handoffsOn;
    if (handoffsOn) edges.add(handoffEdges);
    else            edges.remove(handoffEdges.map(e => e.id));
}}
function zoomIn()       {{ network.setOptions({{physics:false}}); network.moveTo({{scale: network.getScale()*1.2}}); }}
function zoomOut()      {{ network.setOptions({{physics:false}}); network.moveTo({{scale: network.getScale()/1.2}}); }}
function fitToScreen()  {{ network.fit({{animation:true}}); }}
function resetPhysics() {{ network.setOptions({{physics:{{enabled:true}}}}); network.stabilize(); }}
function downloadPNG()  {{
    network.once('afterDrawing', ctx => {{
        var c = ctx.canvas, ex = document.createElement('canvas');
        ex.width = c.width*2; ex.height = c.height*2;
        var x = ex.getContext('2d'); x.scale(2,2); x.drawImage(c,0,0);
        var a = document.createElement('a');
        a.href = ex.toDataURL('image/png'); a.download = 'spectra_dag.png'; a.click();
    }});
    network.redraw();
}}
</script>
</body>
</html>"""

        with open(output_file, 'w') as f:
            f.write(html)

        print(f"\n✓ Created interactive HTML: {output_file}")
        print(f"  Open in browser to interact with the DAG")
        return output_file

    def create_summary_table(self, dag, output_file="dag_summary.md"):
        """Create a markdown table summarizing the DAG."""
        lines = [
            "# Causal DAG Summary", "",
            f"**Events:** {len(dag.events)} | **Causal Edges:** {len(dag.edges)}", "",
            "## Events by Type", "",
            "| Event Type | Count | Agents |",
            "|---|---|---|",
        ]
        event_types = {}
        for e in dag.events:
            event_types.setdefault(e['event_type'], set()).add(e['agent_id'])
        for etype in sorted(event_types):
            count  = sum(1 for e in dag.events if e['event_type'] == etype)
            agents = ', '.join(sorted(event_types[etype]))
            lines.append(f"| {etype} | {count} | {agents} |")

        lines += ["", "## Causal Edges by Reason", "", "| Reason | Count |", "|---|---|"]
        reasons = {}
        for (f, t) in dag.edges:
            edge   = dag.edge_details.get((f, t)) if hasattr(dag, 'edge_details') else None
            reason = edge.reason if edge else 'unknown'
            reasons[reason] = reasons.get(reason, 0) + 1
        for reason in sorted(reasons):
            lines.append(f"| {reason} | {reasons[reason]} |")

        with open(output_file, 'w') as f:
            f.write('\n'.join(lines))

        print(f"\n✓ Created summary table: {output_file}")
        return output_file