
#!/usr/bin/env python3
"""
visualization/prov_agent_gui.py

Streamlit GUI for PROV-AGENT provenance visualization.

Provides three integrated views of the research paper analysis pipeline:

  Tab 1 — Provenance Graph
      D3-force interactive graph of the full PROV-AGENT model:
      Workflow → AgentTool nodes → AIModelInvocation nodes,
      with wasInformedBy edges colour-coded by subtype.

  Tab 2 — Hallucination Report
      Confidence scores per AgentTool, severity badges,
      and a risk-level gauge drawn from the hallucination detector.

  Tab 3 — Flowcept Agent Chat (built-in)
      The Flowcept in-memory query agent embedded as an iframe,
      or if the MCP server is not running, a lightweight pandas-based
      fallback chat that answers provenance questions directly.

Usage
─────
  # 1. Run the pipeline first so provenance records exist:
  docker exec spectra-app python examples/13_research_paper_analysis_prov_agent.py papers/paper.pdf

  # 2. Launch the GUI (inside container or port-forwarded):
  docker exec spectra-app streamlit run visualization/prov_agent_gui.py --server.port 8501

  # 3. Open http://localhost:8501 in your browser.

  # Or run both steps in one shot:
  docker exec spectra-app bash -c \
    "python examples/13_research_paper_analysis_prov_agent.py papers/paper.pdf && \
     streamlit run visualization/prov_agent_gui.py --server.port 8501"
"""
import sys
sys.path.insert(0, '/app')  

import json
import io
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

import pandas as pd
import streamlit as st

# ── Flowcept provenance reader ────────────────────────────────────────────────
from flowcept import Flowcept
from flowcept.instrumentation.flowcept_agent_task import FlowceptLLM

# ── Project visualization helpers ─────────────────────────────────────────────
from reconstruction.dag_builder import DAGBuilder
from visualization.dag_visualizer import DAGVisualizer
from visualization.prov_agent_models import ProvAgentMetadata
from visualization.prov_agent_converter import FlowceptToProvAgentConverter
from visualization.prov_agent_hallucination_detector import ProvAgentHallucinationDetector

# ─────────────────────────────────────────────────────────────────────────────
# Page config — must be the very first Streamlit call
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="PROV-AGENT Provenance Viewer",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────
DEFAULT_JSONL   = "/app/flowcept_buffer.jsonl"
DEFAULT_JSON    = "prov_agent_research_paper.json"
SUBTYPE_COLORS  = {
    "agent_task": "#2E75B6",   # blue  — AgentTool
    "llm_task":   "#70AD47",   # green — AIModelInvocation
    "task":       "#9E9E9E",   # grey  — plain Task
    "workflow":   "#1F4E79",   # dark  — Workflow
}
SEVERITY_COLORS = {
    "CRITICAL": "#C00000",
    "HIGH":     "#E74C3C",
    "MEDIUM":   "#F39C12",
    "LOW":      "#27AE60",
}
RISK_COLORS = {
    "CRITICAL": "#C00000",
    "HIGH":     "#E74C3C",
    "MEDIUM":   "#F39C12",
    "LOW":      "#27AE60",
}

# ─────────────────────────────────────────────────────────────────────────────
# Data loading helpers
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=10)
def load_flowcept_events(jsonl_path: str) -> List[Dict]:
    """Load raw Flowcept events from the JSONL buffer file."""
    path = Path(jsonl_path)
    if not path.exists():
        return []
    events = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return events


@st.cache_data(ttl=10)
def load_prov_agent_json(json_path: str) -> Optional[Dict]:
    """Load the grouped PROV-AGENT JSON produced by example 13."""
    path = Path(json_path)
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def _split_by_subtype(events: List[Dict]):
    agent_tasks = [e for e in events if e.get("subtype") == "agent_task"]
    llm_tasks   = [e for e in events if e.get("subtype") == "llm_task"]
    other       = [e for e in events if e.get("subtype") not in ("agent_task", "llm_task")]
    return agent_tasks, llm_tasks, other


# ─────────────────────────────────────────────────────────────────────────────
# PROV-AGENT graph builder — produces a D3 JSON payload
# ─────────────────────────────────────────────────────────────────────────────

def build_prov_graph_json(events: List[Dict]) -> Dict:
    """
    Convert Flowcept events into a D3-force graph JSON (nodes + links).

    Node types map to PROV-AGENT classes:
      workflow   → Workflow
      agent_task → AgentTool
      llm_task   → AIModelInvocation
      task       → Task
    """
    nodes: List[Dict] = []
    links: List[Dict] = []
    node_ids: set = set()

    def add_node(nid, label, subtype, metadata=None):
        if nid not in node_ids:
            node_ids.add(nid)
            nodes.append({
                "id":       nid,
                "label":    label,
                "subtype":  subtype,
                "color":    SUBTYPE_COLORS.get(subtype, "#BBBBBB"),
                "metadata": metadata or {},
            })

    def add_link(source, target, label):
        links.append({"source": source, "target": target, "label": label})

    # Workflow node
    workflow_ids = set(e.get("workflow_id") for e in events if e.get("workflow_id"))
    for wid in workflow_ids:
        add_node(wid, f"Workflow\n{wid[:8]}...", "workflow")

    # Task nodes and edges
    for e in events:
        eid      = e.get("task_id") or str(uuid.uuid4())
        subtype  = e.get("subtype") or "task"
        act_id   = e.get("activity_id", "unknown")
        wid      = e.get("workflow_id")
        agent_id = e.get("agent_id")
        pid      = e.get("parent_task_id")

        duration = round((e.get("ended_at", 0) - e.get("started_at", 0)), 3)
        status   = e.get("status", "?")

        # Build metadata panel content
        used      = e.get("used") or {}
        generated = e.get("generated") or {}
        meta      = e.get("custom_metadata") or {}

        if subtype == "agent_task":
            label = f"AgentTool\n{act_id}"
            tooltip_meta = {
                "Agent ID":  str(agent_id or "")[:16] + "...",
                "Status":    status,
                "Duration":  f"{duration}s",
                "Inputs":    str(used)[:120],
                "Outputs":   str(generated)[:120],
            }
        elif subtype == "llm_task":
            model   = meta.get("class_name", "LLM")
            prompt  = (used.get("prompt") or "")[:80]
            response= (generated.get("response") or "")[:80]
            label   = f"LLM\n{model}"
            tooltip_meta = {
                "Model":    model,
                "Duration": f"{duration}s",
                "Prompt":   prompt + "...",
                "Response": response + "...",
            }
        else:
            label = f"Task\n{act_id}"
            tooltip_meta = {"Status": status, "Duration": f"{duration}s"}

        add_node(eid, label, subtype, tooltip_meta)

        # Workflow → AgentTool (wasAssociatedWith / hadMember)
        if wid and wid in node_ids and subtype == "agent_task":
            add_link(wid, eid, "hadMember")

        # AgentTool ←wasInformedBy— LLM (parent_task_id)
        if subtype == "llm_task" and pid and pid in node_ids:
            add_link(pid, eid, "wasInformedBy")

        # AgentTool chain (sequential: find predecessor by activity order)
        # (built below after all nodes are registered)

    # Sequential wasInformedBy between AgentTool nodes (execution order)
    agent_task_events = sorted(
        [e for e in events if e.get("subtype") == "agent_task"],
        key=lambda e: e.get("started_at", 0),
    )
    for i in range(1, len(agent_task_events)):
        src = agent_task_events[i - 1].get("task_id")
        dst = agent_task_events[i].get("task_id")
        if src and dst:
            add_link(src, dst, "wasInformedBy")

    return {"nodes": nodes, "links": links}


# ─────────────────────────────────────────────────────────────────────────────
# D3 interactive graph HTML
# ─────────────────────────────────────────────────────────────────────────────

def render_d3_provenance_graph(graph_json: Dict, height: int = 620):
    """Render an interactive D3-force PROV-AGENT graph inside Streamlit."""
    graph_str = json.dumps(graph_json)
    html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ margin: 0; background: #0f1117; font-family: Arial, sans-serif; }}
  svg  {{ width: 100%; height: {height}px; }}

  .link {{ stroke-opacity: 0.6; stroke-width: 1.5px; marker-end: url(#arrow); }}
  .link-label {{ fill: #aaa; font-size: 10px; pointer-events: none; }}

  .node circle {{ stroke: #fff; stroke-width: 1.5px; cursor: grab; }}
  .node text   {{ fill: #eee; font-size: 10px; pointer-events: none; text-anchor: middle; }}

  #tooltip {{
    position: absolute; background: #1e2130; color: #eee;
    border: 1px solid #444; border-radius: 6px;
    padding: 10px 14px; font-size: 12px; pointer-events: none;
    display: none; max-width: 280px; line-height: 1.6;
    box-shadow: 0 4px 12px rgba(0,0,0,0.5);
  }}

  .legend {{ position: absolute; bottom: 12px; left: 12px; }}
  .legend-item {{ display: flex; align-items: center; margin-bottom: 4px; color: #ccc; font-size: 11px; }}
  .legend-dot {{ width: 12px; height: 12px; border-radius: 50%; margin-right: 6px; flex-shrink: 0; }}
</style>
</head>
<body>
<div id="tooltip"></div>
<svg id="graph">
  <defs>
    <marker id="arrow" viewBox="0 -5 10 10" refX="22" refY="0"
            markerWidth="6" markerHeight="6" orient="auto">
      <path d="M0,-5L10,0L0,5" fill="#666"/>
    </marker>
  </defs>
  <g id="zoom-layer"></g>
</svg>
<div class="legend">
  <div class="legend-item"><div class="legend-dot" style="background:#1F4E79"></div>Workflow</div>
  <div class="legend-item"><div class="legend-dot" style="background:#2E75B6"></div>AgentTool (agent_task)</div>
  <div class="legend-item"><div class="legend-dot" style="background:#70AD47"></div>AIModelInvocation (llm_task)</div>
  <div class="legend-item"><div class="legend-dot" style="background:#9E9E9E"></div>Task</div>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.8.5/d3.min.js"></script>
<script>
const graphData = {graph_str};
const W = document.getElementById("graph").clientWidth || 900;
const H = {height};

const svg = d3.select("#graph");
const g   = svg.select("#zoom-layer");

svg.call(d3.zoom().scaleExtent([0.3, 3]).on("zoom", e => g.attr("transform", e.transform)));

const sim = d3.forceSimulation(graphData.nodes)
  .force("link",   d3.forceLink(graphData.links).id(d => d.id).distance(160))
  .force("charge", d3.forceManyBody().strength(-400))
  .force("center", d3.forceCenter(W / 2, H / 2))
  .force("x",      d3.forceX(W / 2).strength(0.04))
  .force("y",      d3.forceY(H / 2).strength(0.04));

// Links
const link = g.append("g").selectAll("line")
  .data(graphData.links).enter().append("line")
  .attr("class", "link")
  .attr("stroke", d => d.label === "wasInformedBy" ? "#70AD47" : "#555");

const linkLabel = g.append("g").selectAll("text")
  .data(graphData.links).enter().append("text")
  .attr("class", "link-label")
  .text(d => d.label);

// Node radius by subtype
function nodeRadius(d) {{
  if (d.subtype === "workflow")   return 22;
  if (d.subtype === "agent_task") return 18;
  if (d.subtype === "llm_task")   return 14;
  return 12;
}}

// Nodes
const node = g.append("g").selectAll("g")
  .data(graphData.nodes).enter().append("g")
  .attr("class", "node")
  .call(d3.drag()
    .on("start", (e, d) => {{ if (!e.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; }})
    .on("drag",  (e, d) => {{ d.fx = e.x; d.fy = e.y; }})
    .on("end",   (e, d) => {{ if (!e.active) sim.alphaTarget(0); d.fx = null; d.fy = null; }}));

node.append("circle")
  .attr("r",    d => nodeRadius(d))
  .attr("fill", d => d.color);

node.each(function(d) {{
  const lines = d.label.split("\\n");
  lines.forEach((line, i) => {{
    d3.select(this).append("text")
      .attr("dy", `${{(i - (lines.length - 1) / 2) * 13}}px`)
      .text(line);
  }});
}});

// Tooltip
const tooltip = document.getElementById("tooltip");
node.on("mouseover", (e, d) => {{
  let html = `<strong>${{d.label.replace("\\n", " ")}}</strong><br>`;
  html += `<em style="color:#aaa">${{d.subtype}}</em><br><br>`;
  for (const [k, v] of Object.entries(d.metadata || {{}})) {{
    html += `<b>${{k}}:</b> ${{v}}<br>`;
  }}
  tooltip.innerHTML = html;
  tooltip.style.display = "block";
  tooltip.style.left = (e.pageX + 14) + "px";
  tooltip.style.top  = (e.pageY - 28) + "px";
}})
.on("mousemove", e => {{
  tooltip.style.left = (e.pageX + 14) + "px";
  tooltip.style.top  = (e.pageY - 28) + "px";
}})
.on("mouseout", () => {{ tooltip.style.display = "none"; }});

// Tick
sim.on("tick", () => {{
  link
    .attr("x1", d => d.source.x).attr("y1", d => d.source.y)
    .attr("x2", d => d.target.x).attr("y2", d => d.target.y);
  linkLabel
    .attr("x", d => (d.source.x + d.target.x) / 2)
    .attr("y", d => (d.source.y + d.target.y) / 2);
  node.attr("transform", d => `translate(${{d.x}},${{d.y}})`);
}});
</script>
</body>
</html>
"""
    st.components.v1.html(html, height=height + 10, scrolling=False)


# ─────────────────────────────────────────────────────────────────────────────
# Hallucination tab
# ─────────────────────────────────────────────────────────────────────────────

def run_hallucination_analysis(agent_tasks: List[Dict]) -> Dict:
    """Run the hallucination detector over agent_task records and return report."""
    converter = FlowceptToProvAgentConverter()
    for task in agent_tasks:
        metadata = ProvAgentMetadata(
            agent_name=task.get("activity_id", "unknown"),
            agent_role="agent_tool",
            model_name=(task.get("custom_metadata") or {}).get("class_name", "unknown"),
            confidence=float((task.get("custom_metadata") or {}).get("confidence", 0.8)),
            facility_type="cloud",
        )
        converter.convert_flowcept_task(task, metadata)

    detector = ProvAgentHallucinationDetector()
    hallucinations = detector.analyze_events(converter.get_events())
    report = detector.generate_report("prov_agent_hallucination_report.json")
    return report, hallucinations


def render_hallucination_tab(agent_tasks: List[Dict]):
    """Render the hallucination analysis tab."""
    if not agent_tasks:
        st.info("No agent_task records found. Run example 13 first.")
        return

    report, hallucinations = run_hallucination_analysis(agent_tasks)

    # Risk gauge
    risk   = report.get("risk_level", "LOW")
    rcolor = RISK_COLORS.get(risk, "#888")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Overall Risk",         risk,  delta=None)
    col2.metric("Total Hallucinations", report.get("total_hallucinations", 0))
    col3.metric("Agent Tools Analyzed", len(agent_tasks))
    col4.metric("By Severity",
                ", ".join(f"{k}:{v}" for k, v in report.get("by_severity", {}).items()) or "—")

    st.markdown(
        f"<div style='background:{rcolor};color:white;padding:10px 18px;"
        f"border-radius:6px;font-size:18px;font-weight:bold;display:inline-block;"
        f"margin-bottom:16px'>Risk Level: {risk}</div>",
        unsafe_allow_html=True,
    )

    # Confidence scores per agent tool
    st.subheader("Confidence scores per AgentTool")
    conf_rows = []
    for t in agent_tasks:
        conf = float((t.get("custom_metadata") or {}).get("confidence", 0.8))
        conf_rows.append({
            "AgentTool":   t.get("activity_id", "?"),
            "Confidence":  conf,
            "Status":      t.get("status", "?"),
            "Duration (s)":round((t.get("ended_at", 0) - t.get("started_at", 0)), 3),
        })
    conf_df = pd.DataFrame(conf_rows)
    st.dataframe(
        conf_df.style
               .background_gradient(subset=["Confidence"], cmap="RdYlGn", vmin=0, vmax=1)
               .format({"Confidence": "{:.2f}", "Duration (s)": "{:.3f}"}),
        use_container_width=True,
        hide_index=True,
    )

    # Hallucination table
    if hallucinations:
        st.subheader("Detected hallucinations")
        hall_rows = []
        for h in hallucinations:
            d = h.to_dict()
            hall_rows.append({
                "Type":       d.get("type", "?"),
                "Severity":   d.get("severity", "?"),
                "Agent":      d.get("agent", "?"),
                "Confidence": d.get("confidence", "?"),
                "Description":d.get("description", "?")[:120],
            })
        hall_df = pd.DataFrame(hall_rows)

        def color_severity(val):
            return f"color: {SEVERITY_COLORS.get(val, '#888')}; font-weight: bold"

        st.dataframe(
            hall_df.style.applymap(color_severity, subset=["Severity"]),
            use_container_width=True,
            hide_index=True,
        )

        with st.expander("Full hallucination evidence (JSON)"):
            st.json([h.to_dict() for h in hallucinations])
    else:
        st.success("✅ No hallucinations detected in this run.")


# ─────────────────────────────────────────────────────────────────────────────
# Flowcept Agent Chat tab
# ─────────────────────────────────────────────────────────────────────────────

def render_chat_tab(events: List[Dict]):
    """
    Lightweight provenance chat backed by a pandas DataFrame of Flowcept events.

    Answers natural-language questions about the captured provenance without
    requiring the MCP server to be running. Uses the Anthropic API directly
    so this works in any environment where ANTHROPIC_API_KEY is set.

    For the full Flowcept Agent GUI (with Streamlit MCP chat), start the
    MCP server separately:
        flowcept --start-agent
    and open http://localhost:8000 in your browser.
    """
    st.markdown(
        "Ask questions about the provenance captured in this run. "
        "This chat queries the in-memory DataFrame of Flowcept events."
    )

    # Build flat DataFrame from events for the LLM context
    rows = []
    for e in events:
        rows.append({
            "task_id":       e.get("task_id", ""),
            "subtype":       e.get("subtype", "task"),
            "activity_id":   e.get("activity_id", ""),
            "agent_id":      str(e.get("agent_id") or "")[:12],
            "parent_task_id":str(e.get("parent_task_id") or "")[:12],
            "status":        e.get("status", ""),
            "started_at":    e.get("started_at", 0),
            "ended_at":      e.get("ended_at", 0),
            "duration_s":    round((e.get("ended_at", 0) - e.get("started_at", 0)), 3),
            "workflow_id":   str(e.get("workflow_id") or "")[:12],
            "used":          json.dumps(e.get("used") or {}),
            "generated":     json.dumps(e.get("generated") or {}),
            "custom_metadata": json.dumps(e.get("custom_metadata") or {}),
        })
    df = pd.DataFrame(rows)

    st.dataframe(df, use_container_width=True, hide_index=True)

    # ── Chat interface ────────────────────────────────────────────────────────
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # Render previous messages
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_input = st.chat_input(
        "Ask about the provenance: e.g. 'Which agent took longest?' or "
        "'What LLM models were called?'"
    )

    if user_input:
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            with st.spinner("Querying provenance..."):
                answer = _answer_provenance_question(user_input, df, events)
            st.markdown(answer)

        st.session_state.chat_history.append({"role": "assistant", "content": answer})

    # Quick-action buttons
    st.markdown("**Quick queries:**")
    qcols = st.columns(4)
    quick_queries = [
        "Which AgentTool took the longest?",
        "List all LLM model invocations",
        "Show the wasInformedBy relationships",
        "What was the overall workflow status?",
    ]
    for col, q in zip(qcols, quick_queries):
        if col.button(q, use_container_width=True):
            st.session_state.chat_history.append({"role": "user", "content": q})
            answer = _answer_provenance_question(q, df, events)
            st.session_state.chat_history.append({"role": "assistant", "content": answer})
            st.rerun()

    # Flowcept Agent link
    st.divider()
    st.markdown(
        "**Full Flowcept Agent** (requires `flowcept --start-agent` and MongoDB running):  \n"
        "Start the MCP agent server, then open "
        "[http://localhost:8000](http://localhost:8000) for the full Streamlit GUI "
        "with natural-language pandas queries, plot generation, and provenance card exports."
    )


def _answer_provenance_question(question: str, df: pd.DataFrame, events: List[Dict]) -> str:
    """
    Answer a natural-language question about provenance by calling the
    Anthropic API with the DataFrame schema + sample rows as context.

    Falls back to a rule-based answerer if the API key is not set.
    """
    import os
    api_key = os.environ.get("ANTHROPIC_API_KEY")

    if not api_key:
        return _rule_based_answer(question, df, events)

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        schema_summary = df.dtypes.to_string()
        sample_rows    = df.head(10).to_markdown(index=False)
        context = (
            f"You are a provenance analyst. The user is asking about a PROV-AGENT "
            f"workflow provenance DataFrame with {len(df)} records.\n\n"
            f"Schema:\n{schema_summary}\n\n"
            f"Sample rows (up to 10):\n{sample_rows}\n\n"
            f"Key fields:\n"
            f"- subtype: 'agent_task' = AgentTool, 'llm_task' = AIModelInvocation\n"
            f"- parent_task_id: links llm_task to its enclosing agent_task (wasInformedBy)\n"
            f"- duration_s: elapsed seconds for that record\n\n"
            f"Answer concisely in Markdown. If you need to show data, use a small table."
        )
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            messages=[
                {"role": "user", "content": f"{context}\n\nQuestion: {question}"}
            ],
        )
        return response.content[0].text
    except Exception as e:
        return _rule_based_answer(question, df, events) + f"\n\n*(API error: {e})*"


def _rule_based_answer(question: str, df: pd.DataFrame, events: List[Dict]) -> str:
    """Simple keyword-based fallback answerer when no API key is available."""
    q = question.lower()

    if "longest" in q or "slowest" in q or "duration" in q:
        if df.empty:
            return "No records found."
        longest = df.loc[df["duration_s"].idxmax()]
        return (
            f"**Longest AgentTool:** `{longest['activity_id']}` "
            f"({longest['duration_s']:.3f}s) — subtype: `{longest['subtype']}`"
        )

    if "llm" in q or "model" in q or "invocation" in q:
        llm_rows = df[df["subtype"] == "llm_task"]
        if llm_rows.empty:
            return "No LLM invocations found in this run."
        lines = ["**LLM invocations:**\n"]
        for _, r in llm_rows.iterrows():
            meta = {}
            try:
                meta = json.loads(r.get("custom_metadata") or "{}")
            except Exception:
                pass
            lines.append(
                f"- `{r['activity_id']}` — model: `{meta.get('class_name','?')}` "
                f"— duration: {r['duration_s']:.3f}s "
                f"— parent: `{r['parent_task_id'] or 'none'}`"
            )
        return "\n".join(lines)

    if "wasinformedby" in q or "relationship" in q or "link" in q:
        llm_rows = df[df["subtype"] == "llm_task"]
        agent_rows = df[df["subtype"] == "agent_task"]
        if llm_rows.empty:
            return "No wasInformedBy relationships found (no LLM invocations captured)."
        lines = ["**wasInformedBy relationships (AgentTool → AIModelInvocation):**\n"]
        for _, l in llm_rows.iterrows():
            parent = agent_rows[agent_rows["task_id"] == l["parent_task_id"]]
            parent_name = parent.iloc[0]["activity_id"] if not parent.empty else l["parent_task_id"]
            lines.append(f"- `{parent_name}` ──wasInformedBy──▶ `{l['activity_id']}`")
        return "\n".join(lines)

    if "status" in q or "workflow" in q:
        statuses = df["status"].value_counts().to_dict()
        wids = df["workflow_id"].dropna().unique()
        return (
            f"**Workflow IDs:** {', '.join(wids[:3])}\n\n"
            f"**Status breakdown:**\n"
            + "\n".join(f"- `{k}`: {v}" for k, v in statuses.items())
        )

    if "agent" in q or "tool" in q:
        at = df[df["subtype"] == "agent_task"]
        if at.empty:
            return "No AgentTool records found."
        return (
            f"**AgentTool records ({len(at)}):**\n"
            + "\n".join(f"- `{r['activity_id']}` — {r['duration_s']:.3f}s — {r['status']}"
                        for _, r in at.iterrows())
        )

    # Fallback: summarize everything
    at_count  = len(df[df["subtype"] == "agent_task"])
    llm_count = len(df[df["subtype"] == "llm_task"])
    return (
        f"This provenance run captured **{len(df)}** total records: "
        f"**{at_count}** AgentTool (agent_task) and "
        f"**{llm_count}** AIModelInvocation (llm_task).\n\n"
        f"Try asking: *Which agent took longest?*, "
        f"*List all LLM invocations*, or *Show the wasInformedBy relationships*."
    )


# ─────────────────────────────────────────────────────────────────────────────
# DAG tab (existing DAGVisualizer output embedded)
# ─────────────────────────────────────────────────────────────────────────────

def render_dag_tab(events: List[Dict]):
    """Embed the existing DAGVisualizer HTML output or rebuild it on the fly."""
    # Try loading the pre-generated file from example 13
    html_path = Path("research_paper_prov_agent_interactive.html")
    if html_path.exists():
        html_content = html_path.read_text()
        st.components.v1.html(html_content, height=700, scrolling=True)
        st.caption(f"Source: `{html_path}` — regenerate by re-running example 13.")
    else:
        # Rebuild from legacy collector events if available
        legacy_collector_events = [e for e in events if "event_type" in e]
        if legacy_collector_events:
            try:
                builder    = DAGBuilder()
                dag        = builder.build(legacy_collector_events)
                visualizer = DAGVisualizer()
                out_file   = "/tmp/prov_agent_dag_gui.html"
                visualizer.create_html_interactive(dag, output_file=out_file)
                html_content = Path(out_file).read_text()
                st.components.v1.html(html_content, height=700, scrolling=True)
            except Exception as e:
                st.warning(f"Could not build DAG: {e}")
        else:
            st.info(
                "No pre-generated DAG file found.  \n"
                "Run example 13 first:  \n"
                "`docker exec spectra-app python examples/13_research_paper_analysis_prov_agent.py papers/paper.pdf`"
            )


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────────────────────

def render_sidebar() -> tuple:
    """Render sidebar controls and return (jsonl_path, json_path, auto_refresh)."""
    st.sidebar.title("🔍 PROV-AGENT Viewer")
    st.sidebar.markdown(
        "Visualises provenance captured by `@agent_flowcept_task` "
        "and `FlowceptLLM` from example 13."
    )
    st.sidebar.divider()

    jsonl_path = st.sidebar.text_input(
        "Flowcept JSONL buffer", value=DEFAULT_JSONL,
        help="Path to flowcept_messages.jsonl produced during the pipeline run."
    )
    json_path = st.sidebar.text_input(
        "PROV-AGENT JSON export", value=DEFAULT_JSON,
        help="Path to prov_agent_research_paper.json produced by example 13."
    )
    auto_refresh = st.sidebar.toggle("Auto-refresh (10s)", value=False)

    st.sidebar.divider()
    st.sidebar.markdown("**PROV-AGENT record subtypes**")
    for subtype, color in SUBTYPE_COLORS.items():
        st.sidebar.markdown(
            f"<span style='background:{color};color:white;padding:2px 8px;"
            f"border-radius:4px;font-size:12px'>{subtype}</span>",
            unsafe_allow_html=True,
        )

    st.sidebar.divider()
    st.sidebar.markdown(
        "**Run pipeline:**  \n"
        "```\ndocker exec spectra-app python \\\n"
        "  examples/13_research_paper_analysis_prov_agent.py \\\n"
        "  papers/paper.pdf\n```"
        "\n\n**Start Flowcept Agent:**  \n"
        "```\nflowcept --start-agent\n```"
    )

    return jsonl_path, json_path, auto_refresh


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    jsonl_path, json_path, auto_refresh = render_sidebar()

    events = load_flowcept_events(jsonl_path)
    prov_json = load_prov_agent_json(json_path)   # ← actually call it

    # Show metadata from the JSON export in the sidebar
    if prov_json:
        if isinstance(prov_json, list):
            meta = {}   # flat list export — no metadata header
            st.sidebar.divider()
            st.sidebar.markdown("**PROV-AGENT export**")
            st.sidebar.caption(f"{len(prov_json)} records in export file")
        else:
            meta = prov_json.get("metadata", {})
            st.sidebar.divider()
            st.sidebar.markdown("**PROV-AGENT export metadata**")
            st.sidebar.caption(f"Workflow: `{str(meta.get('workflow_id','?'))[:16]}...`")
            st.sidebar.caption(f"Agent: `{str(meta.get('agent_id','?'))[:16]}...`")
            st.sidebar.caption(f"Captured: {meta.get('captured_at','?')}")
            st.sidebar.caption(f"Records: {meta.get('total_records','?')}")
    else:
        st.sidebar.caption(f"⚠️ JSON export not found at `{json_path}`")

    if auto_refresh:
        import time
        st.empty()
        time.sleep(10)
        st.rerun()

    # Load data
    events = load_flowcept_events(jsonl_path)

    if not events:
        st.warning(
            f"No provenance records found at `{jsonl_path}`.  \n"
            "Run example 13 first to generate provenance data."
        )
        return

    agent_tasks, llm_tasks, other = _split_by_subtype(events)

    # Header metrics
    st.title("PROV-AGENT Provenance Viewer")
    st.caption(f"Loaded {len(events)} records from `{jsonl_path}` "
               f"at {datetime.now().strftime('%H:%M:%S')}")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total records",          len(events))
    m2.metric("AgentTool records",      len(agent_tasks),
              help="subtype='agent_task' — maps to AgentTool in PROV-AGENT")
    m3.metric("AIModelInvocation",      len(llm_tasks),
              help="subtype='llm_task' — maps to AIModelInvocation in PROV-AGENT")
    m4.metric("wasInformedBy links",
              len([lt for lt in llm_tasks if lt.get("parent_task_id")]),
              help="llm_task records with a parent_task_id → AgentTool")

    st.divider()

    # Tabs
    tab_graph, tab_dag, tab_halluc, tab_chat = st.tabs([
        "🕸️  Provenance Graph",
        "📊  Causal DAG",
        "⚠️  Hallucination Report",
        "💬  Provenance Chat",
    ])

    with tab_graph:
        st.subheader("PROV-AGENT Interactive Provenance Graph")
        st.caption(
            "Nodes: **dark blue** = Workflow, **blue** = AgentTool, "
            "**green** = AIModelInvocation. "
            "Edges: **wasInformedBy** (green) and **hadMember** (grey). "
            "Drag nodes to rearrange. Hover for details."
        )
        graph_json = build_prov_graph_json(events)
        render_d3_provenance_graph(graph_json, height=620)

        with st.expander("Raw graph JSON"):
            st.json(graph_json)

    with tab_dag:
        st.subheader("Causal DAG (DAGVisualizer output)")
        render_dag_tab(events)

    with tab_halluc:
        st.subheader("Hallucination Analysis")
        render_hallucination_tab(agent_tasks)

    with tab_chat:
        st.subheader("Provenance Chat")
        render_chat_tab(events)


if __name__ == "__main__":
    main()
