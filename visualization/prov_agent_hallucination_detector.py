"""Detect hallucinations using PROV-AGENT metadata"""

import uuid
from datetime import datetime
from typing import Dict, List, Optional

from visualization.prov_agent_models import (
    ProvAgentEvent,
    ProvAgentHallucination
)


class ProvAgentHallucinationDetector:
    """Detect hallucinations using PROV-AGENT metadata"""
    
    def __init__(self):
        self.hallucinations: List[ProvAgentHallucination] = []
        self.mcp_tools: Dict[str, Dict] = {}  # Cache of valid MCP tools
    
    def register_mcp_tool(self, tool_name: str, tool_schema: Dict):
        """Register a valid MCP tool"""
        self.mcp_tools[tool_name] = tool_schema
    
    def analyze_events(self, events: List[ProvAgentEvent]) -> List[ProvAgentHallucination]:
        """Analyze all events for hallucinations"""
        self.hallucinations = []
        
        for event in events:
            # Check 1: Confidence-based hallucination
            self._check_confidence(event)
            
            # Check 2: Tool invocation hallucinations
            if event.event_type == 'TOOL_INVOCATION':
                self._check_tool_hallucination(event)
            
            # Check 3: Schema validation hallucinations
            if event.agent_metadata.tool_inputs:
                self._check_schema_hallucination(event)
        
        return self.hallucinations
    
    def _check_confidence(self, event: ProvAgentEvent):
        """Detect low-confidence decisions"""
        confidence = event.agent_metadata.confidence
        
        if confidence < 0.7:
            hallucination = ProvAgentHallucination(
                hallucination_id=str(uuid.uuid4()),
                hallucination_type='CONFIDENCE',
                severity='HIGH' if confidence < 0.5 else 'MEDIUM',
                agent_id=event.agent_metadata.agent_name,
                confidence_score=confidence,
                description=f"Agent made decision with low confidence ({confidence:.2f})",
                evidence={
                    'decision': event.agent_metadata.response,
                    'confidence_score': confidence,
                    'threshold': 0.7
                },
                timestamp=event.timestamp,
                facility_context=event.agent_metadata.facility_type
            )
            self.hallucinations.append(hallucination)
    
    def _check_tool_hallucination(self, event: ProvAgentEvent):
        """Detect if agent used non-existent tool"""
        tool_name = event.agent_metadata.tool_name
        
        if tool_name and tool_name not in self.mcp_tools:
            hallucination = ProvAgentHallucination(
                hallucination_id=str(uuid.uuid4()),
                hallucination_type='TOOL',
                severity='CRITICAL',
                agent_id=event.agent_metadata.agent_name,
                confidence_score=1.0,
                description=f"Agent invoked non-existent tool: {tool_name}",
                evidence={
                    'claimed_tool': tool_name,
                    'available_tools': list(self.mcp_tools.keys()),
                    'activity': event.activity_data
                },
                timestamp=event.timestamp,
                facility_context=event.agent_metadata.facility_type
            )
            self.hallucinations.append(hallucination)
    
    def _check_schema_hallucination(self, event: ProvAgentEvent):
        """Detect if tool was invoked with wrong parameters"""
        tool_name = event.agent_metadata.tool_name
        inputs = event.agent_metadata.tool_inputs
        
        if tool_name in self.mcp_tools:
            schema = self.mcp_tools[tool_name]
            
            # Simple schema validation
            expected_params = schema.get('parameters', {}).get('properties', {})
            actual_params = inputs.keys() if inputs else []
            
            missing_params = set(expected_params.keys()) - set(actual_params)
            extra_params = set(actual_params) - set(expected_params.keys())
            
            if missing_params or extra_params:
                hallucination = ProvAgentHallucination(
                    hallucination_id=str(uuid.uuid4()),
                    hallucination_type='SCHEMA',
                    severity='HIGH',
                    agent_id=event.agent_metadata.agent_name,
                    confidence_score=0.85,
                    description=f"Tool invoked with incorrect parameters",
                    evidence={
                        'tool': tool_name,
                        'expected_params': list(expected_params.keys()),
                        'actual_params': list(actual_params),
                        'missing': list(missing_params),
                        'extra': list(extra_params)
                    },
                    timestamp=event.timestamp,
                    facility_context=event.agent_metadata.facility_type
                )
                self.hallucinations.append(hallucination)
    
    def get_hallucinations(self) -> List[ProvAgentHallucination]:
        return self.hallucinations
    
    def generate_report(self, output_file: str):
        """Generate hallucination report"""
        import json
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'total_hallucinations': len(self.hallucinations),
            'by_type': self._count_by_type(),
            'by_severity': self._count_by_severity(),
            'hallucinations': [h.to_dict() for h in self.hallucinations],
            'risk_level': self._calculate_risk_level()
        }
        
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"✅ Hallucination report generated: {output_file}")
        return report
    
    def _count_by_type(self) -> Dict[str, int]:
        counts = {}
        for h in self.hallucinations:
            counts[h.hallucination_type] = counts.get(h.hallucination_type, 0) + 1
        return counts
    
    def _count_by_severity(self) -> Dict[str, int]:
        counts = {}
        for h in self.hallucinations:
            counts[h.severity] = counts.get(h.severity, 0) + 1
        return counts
    
    def _calculate_risk_level(self) -> str:
        """Calculate overall risk level"""
        if not self.hallucinations:
            return 'LOW'
        
        critical = sum(1 for h in self.hallucinations if h.severity == 'CRITICAL')
        high = sum(1 for h in self.hallucinations if h.severity == 'HIGH')
        
        if critical > 0:
            return 'CRITICAL'
        elif high >= 3:
            return 'HIGH'
        elif high > 0:
            return 'MEDIUM'
        else:
            return 'LOW'
