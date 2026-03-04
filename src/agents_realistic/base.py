from langchain_ollama import OllamaLLM  # FIX: updated from deprecated langchain_community.llms.Ollama
from src.agents.simple import get_collector
import time
import re


class MistralAgent:
    """LLM-powered agent using Mistral via Ollama (STRICT mode: LLM only chooses tools)."""

    def __init__(self, agent_id: str, role: str, ollama_host: str = "http://ollama:11434"):
        self.agent_id = agent_id
        self.role = role
        self.tools = []
        self.decision_history = []

        # FIX: OllamaLLM replaces deprecated Ollama
        self.llm = OllamaLLM(
            model="mistral",
            base_url=ollama_host,
            temperature=0,
        )

    def register_tool(self, tool_func):
        self.tools.append(tool_func)

    def _build_system_prompt(self) -> str:
        tools_lines = []
        for t in self.tools:
            inputs = f" | inputs: {', '.join(t.inputs)}" if getattr(t, "inputs", None) else ""
            tools_lines.append(f"- {t.name}: {t.description}{inputs}")

        tool_list = "\n".join(tools_lines) if tools_lines else "None"

        return f"""You are {self.agent_id}, a {self.role} agent.

Available tools:
{tool_list}

STRICT MODE:
You ONLY decide which tool to use and with which parameters.
NEVER summarize, explain, or analyze the paper.
ONLY use the parameter names listed for each tool. Do NOT invent extra parameters.

When using a tool, format EXACTLY as:

TOOL_NAME: <tool_name>
PARAM_<input_name>: <value>

Examples:

TOOL_NAME: ingest_paper
PARAM_file_path: papers/paper.pdf

TOOL_NAME: search_content
PARAM_query: methodology

If no tool is needed, reply simply: "NO_TOOL".
"""

    def _parse_tool_call(self, response: str):
        """
        Parse the FIRST tool call block in the LLM response.

        FIX (point 3): Mistral often plans a multi-step chain and writes
        several TOOL_NAME blocks. Previously the last block was used,
        which could be an irrelevant downstream tool. We now capture only
        the first block — the tool the agent should act on immediately.
        """
        lines     = response.split("\n")
        tool_name = None
        params    = {}
        in_block  = False

        for line in lines:
            if "TOOL_NAME:" in line:
                if in_block:
                    # Second block found — stop, we only want the first
                    break
                tool_name = line.split("TOOL_NAME:")[1].strip()
                in_block  = True
            elif in_block and "PARAM_" in line:
                m = re.match(r"PARAM_(\w+):\s*(.*)", line)
                if m:
                    params[m.group(1)] = m.group(2).strip()

        return tool_name, params

    def reason_and_act(self, state: dict, goal: str) -> dict:
        collector = get_collector()

        collector.emit("GOAL_CREATED", self.agent_id, {
            "goal": goal,
            "role": self.role,
            "tools_available": [t.name for t in self.tools],
            "timestamp": time.time(),
        })

        collector.emit("REASONING_STEP", self.agent_id, {
            "step": "analyze_goal",
            "goal": goal,
            "available_tools": [t.name for t in self.tools],
        })

        system_prompt = self._build_system_prompt()
        user_prompt = f"Task: {goal}\n\nWhat should you do?"

        try:
            response = self.llm.invoke(system_prompt + "\n\n" + user_prompt)
            reasoning = response.strip() if isinstance(response, str) else str(response)
            state["last_reasoning"] = reasoning

            tool_name, params = self._parse_tool_call(reasoning)

            if tool_name and tool_name != "NO_TOOL":
                tool = next((t for t in self.tools if t.name == tool_name), None)
                if not tool:
                    collector.emit("GOAL_FAILED", self.agent_id, {
                        "reason": "tool_not_found",
                        "requested_tool": tool_name,
                        "available_tools": [t.name for t in self.tools],
                    })
                    return state

                collector.emit("TOOL_INVOKED", self.agent_id, {
                    "tool": tool.name,
                    "params": params,
                    "reasoning_snippet": reasoning[:200],
                })

                try:
                    result = tool.invoke(params, context=state)
                    state["tool_result"] = result

                    collector.emit("REASONING_STEP", self.agent_id, {
                        "step": "process_tool_result",
                        "tool": tool_name,
                        "result_length": len(str(result)),
                    })

                    collector.emit("GOAL_COMPLETED", self.agent_id, {
                        "result": str(result)[:100],
                        "tool_used": tool_name,
                        "status": "success",
                    })

                except Exception as e:
                    collector.emit("GOAL_FAILED", self.agent_id, {
                        "reason": "tool_execution_error",
                        "tool": tool_name,
                        "error": str(e),
                        "params": params,
                    })
                    state["error"] = str(e)

            else:
                collector.emit("GOAL_COMPLETED", self.agent_id, {
                    "result": "NO_TOOL",
                    "tool_used": None,
                    "status": "success",
                })

        except Exception as e:
            collector.emit("GOAL_FAILED", self.agent_id, {
                "reason": "llm_error",
                "error": str(e),
            })
            state["error"] = str(e)

        return state