"""Convert Flowcept events to PROV-AGENT format"""

import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional

from visualization.prov_agent_models import (
    ProvAgentMetadata,
    ProvAgentEvent,
    ProvAgentHallucination
)


class FlowceptToProvAgentConverter:
    """Convert Flowcept task events to PROV-AGENT format"""
    
    def __init__(self):
        self.events: List[ProvAgentEvent] = []
        self.hallucinations: List[ProvAgentHallucination] = []
    
    def convert_flowcept_task(self, 
                             flowcept_task: Dict[str, Any],
                             agent_metadata: ProvAgentMetadata,
                             facility_metadata: Optional[Dict] = None) -> ProvAgentEvent:
        """
        Convert Flowcept task to PROV-AGENT event
        
        Args:
            flowcept_task: Task dict from Flowcept
            agent_metadata: Agent info (model, role, confidence)
            facility_metadata: Where task ran (edge/cloud/hpc)
        
        Returns:
            ProvAgentEvent with full PROV-AGENT metadata
        """
        
        event = ProvAgentEvent(
            event_id=flowcept_task.get('task_id', str(uuid.uuid4())),
            event_type=self._map_activity_to_event_type(flowcept_task),
            timestamp=flowcept_task.get('started_at', datetime.now().timestamp()),
            agent_metadata=agent_metadata,
            activity_data={
                'activity_id': flowcept_task.get('activity_id'),
                'workflow_id': flowcept_task.get('workflow_id'),
                'used': flowcept_task.get('used'),
                'generated': flowcept_task.get('generated'),
                'status': flowcept_task.get('status'),
                'duration': flowcept_task.get('ended_at', 0) - flowcept_task.get('started_at', 0)
            },
            facility_metadata=facility_metadata
        )
        
        self.events.append(event)
        return event
    
    def _map_activity_to_event_type(self, task: Dict) -> str:
        """Map Flowcept activity to PROV-AGENT event type"""
        activity_id = task.get('activity_id', '').lower()
        
        if 'search' in activity_id or 'tool' in activity_id:
            return 'TOOL_INVOCATION'
        elif 'reasoning' in activity_id or 'analyze' in activity_id:
            return 'REASONING_STEP'
        elif 'summarize' in activity_id:
            return 'REASONING_STEP'
        elif 'classify' in activity_id:
            return 'REASONING_STEP'
        else:
            return 'ACTIVITY'
    
    def add_confidence_score(self, event_id: str, confidence: float):
        """Add confidence score to event"""
        event = next((e for e in self.events if e.event_id == event_id), None)
        if event:
            event.agent_metadata.confidence = confidence
    
    def flag_potential_hallucination(self, 
                                    event_id: str,
                                    hallucination_type: str,
                                    description: str,
                                    severity: str = 'MEDIUM'):
        """Flag event as having potential hallucination"""
        event = next((e for e in self.events if e.event_id == event_id), None)
        if event:
            event.agent_metadata.add_hallucination_flag(hallucination_type)
    
    def get_events(self) -> List[ProvAgentEvent]:
        return self.events
    
    def export_to_json(self, output_file: str):
        """Export PROV-AGENT events to JSON"""
        import json
        
        events_json = [e.to_dict() for e in self.events]
        
        with open(output_file, 'w') as f:
            json.dump(events_json, f, indent=2)
        
        print(f"✅ PROV-AGENT events exported: {output_file}")
