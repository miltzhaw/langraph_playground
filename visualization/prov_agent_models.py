"""PROV-AGENT data models for agent-aware provenance"""

from dataclasses import dataclass, asdict, field
from typing import Dict, List, Any, Optional
from datetime import datetime
import json


@dataclass
class ProvAgentMetadata:
    """Agent metadata for PROV-AGENT model"""
    agent_name: str
    agent_role: str
    model_name: str
    model_version: str = "1.0"
    confidence: float = 0.5
    prompt: Optional[str] = None
    response: Optional[str] = None
    tool_name: Optional[str] = None
    tool_schema: Optional[Dict] = None
    tool_inputs: Optional[Dict] = None
    tool_outputs: Optional[Dict] = None
    facility_type: Optional[str] = None  # edge, cloud, hpc
    facility_location: Optional[str] = None
    hallucination_flags: List[str] = field(default_factory=list)
    
    def to_dict(self):
        return asdict(self)
    
    def add_hallucination_flag(self, flag: str):
        """Flag potential hallucination"""
        self.hallucination_flags.append(flag)


@dataclass
class ProvAgentEvent:
    """PROV-AGENT event from workflow execution"""
    event_id: str
    event_type: str  # TOOL_INVOCATION, REASONING_STEP, etc.
    timestamp: float
    agent_metadata: ProvAgentMetadata
    activity_data: Dict[str, Any]
    facility_metadata: Optional[Dict] = None
    
    def to_dict(self):
        return {
            'event_id': self.event_id,
            'event_type': self.event_type,
            'timestamp': datetime.fromtimestamp(self.timestamp).isoformat(),
            'agent': self.agent_metadata.to_dict(),
            'activity': self.activity_data,
            'facility': self.facility_metadata
        }


@dataclass
class ProvAgentHallucination:
    """Detected hallucination with PROV-AGENT metadata"""
    hallucination_id: str
    hallucination_type: str  # TOOL, SCHEMA, INTERPRETATION, CONFIDENCE
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    agent_id: str
    confidence_score: float
    description: str
    evidence: Dict[str, Any]
    timestamp: float
    facility_context: Optional[str] = None
    
    def to_dict(self):
        return {
            'hallucination_id': self.hallucination_id,
            'type': self.hallucination_type,
            'severity': self.severity,
            'agent': self.agent_id,
            'confidence': self.confidence_score,
            'description': self.description,
            'evidence': self.evidence,
            'timestamp': datetime.fromtimestamp(self.timestamp).isoformat(),
            'facility': self.facility_context
        }