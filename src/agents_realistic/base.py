from langchain_community.llms import Ollama
from langchain_core.tools import tool
from src.agents.simple import get_collector
from typing import Dict, List, Optional
import json
import time
import re

class MistralAgent:
    """LLM-powered agent using Mistral via Ollama"""
    
    def __init__(self, agent_id: str, role: str, ollama_host: str = "http://ollama:11434"):
        self.agent_id = agent_id
        self.role = role
        self.tools = []
        self.decision_history = []
        
        self.llm = Ollama(
            model="mistral",
            base_url=ollama_host,
            temperature=0
        )
    
    def register_tool(self, tool_func):
        """Register a tool this agent can use"""
        self.tools.append(tool_func)
    
    def _build_system_prompt(self) -> str:
        """Build system context for the agent"""
        tool_list = "\n".join([
            f"- {t.name}: {t.description}"
            for t in self.tools
        ])
        
        return f"""You are {self.agent_id}, a {self.role} agent.

Available tools:
{tool_list if tool_list else "None"}

When using a tool, format EXACTLY as:
TOOL_NAME: search_documents
PARAM_query: machine learning

OR

TOOL_NAME: summarize_content
PARAM_content: some text here

Always provide the parameter value after the colon on the same line.
Be concise."""
    
    def _parse_tool_call(self, response: str) -> tuple:
        """Parse LLM response for tool usage
        
        Returns: (tool_name, params_dict) or (None, {})
        """
        lines = response.split('\n')
        tool_name = None
        params = {}
        
        for line in lines:
            if 'TOOL_NAME:' in line:
                tool_name = line.split('TOOL_NAME:')[1].strip()
            elif 'PARAM_' in line:
                # Parse PARAM_key: value
                match = re.match(r'PARAM_(\w+):\s*(.*)', line)
                if match:
                    key, value = match.groups()
                    params[key] = value.strip()
        
        return tool_name, params
    
    def reason_and_act(self, state: Dict, goal: str) -> Dict:
        """Main agent action with LLM reasoning"""
        collector = get_collector()
        
        # 1. GOAL_CREATED event
        collector.emit("GOAL_CREATED", self.agent_id, {
            "goal": goal,
            "role": self.role,
            "tools_available": [t.name for t in self.tools],
            "timestamp": time.time()
        })
        
        # 2. REASONING_STEP: Agent thinks
        collector.emit("REASONING_STEP", self.agent_id, {
            "step": "analyze_goal",
            "goal": goal,
            "available_tools": [t.name for t in self.tools]
        })
        
        # Build prompt
        system_prompt = self._build_system_prompt()
        user_prompt = f"Task: {goal}\n\nWhat should you do?"
        
        try:
            # Call LLM
            response = self.llm.invoke(f"{system_prompt}\n\n{user_prompt}")
            reasoning = response.strip() if isinstance(response, str) else response
            
            self.decision_history.append({
                "goal": goal,
                "reasoning": reasoning[:200]
            })
            
            state["last_reasoning"] = reasoning
            
            # Parse tool call
            tool_name, params = self._parse_tool_call(reasoning)
            
            if tool_name:
                tool = next((t for t in self.tools if t.name == tool_name), None)
                
                if tool:
                    # 3. TOOL_INVOKED event
                    collector.emit("TOOL_INVOKED", self.agent_id, {
                        "tool": tool.name,
                        "params": params,
                        "reasoning_snippet": reasoning[:150]
                    })
                    
                    try:
                        # Execute tool with parsed params
                        tool_result = tool.invoke(params)
                        state["tool_result"] = tool_result
                        
                        # 4. REASONING_STEP: Process result
                        collector.emit("REASONING_STEP", self.agent_id, {
                            "step": "process_tool_result",
                            "tool": tool.name,
                            "result_length": len(str(tool_result))
                        })
                        
                        # 5. GOAL_COMPLETED event
                        collector.emit("GOAL_COMPLETED", self.agent_id, {
                            "result": str(tool_result)[:100],
                            "tool_used": tool.name,
                            "status": "success"
                        })
                        
                    except Exception as e:
                        # 5. GOAL_FAILED event
                        collector.emit("GOAL_FAILED", self.agent_id, {
                            "reason": "tool_execution_error",
                            "tool": tool.name,
                            "error": str(e),
                            "params": params,
                            "status": "failed"
                        })
                        state["error"] = str(e)
                else:
                    # Tool not found
                    collector.emit("GOAL_FAILED", self.agent_id, {
                        "reason": "tool_not_found",
                        "requested_tool": tool_name,
                        "available_tools": [t.name for t in self.tools]
                    })
            else:
                # No tool used
                collector.emit("REASONING_STEP", self.agent_id, {
                    "step": "decision_made",
                    "decision": "no_tool_needed",
                    "reasoning": reasoning[:150]
                })
                
                collector.emit("GOAL_COMPLETED", self.agent_id, {
                    "result": reasoning[:100],
                    "tool_used": None,
                    "status": "success"
                })
        
        except Exception as e:
            # LLM error
            collector.emit("GOAL_FAILED", self.agent_id, {
                "reason": "llm_error",
                "error": str(e),
                "error_type": type(e).__name__
            })
            state["error"] = str(e)
        
        return state