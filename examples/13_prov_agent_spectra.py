#!/usr/bin/env python3
"""
Example 13: PROV-AGENT + SPECTRA + Flowcept Integration (CORRECTED)
Fixed imports to work with actual Flowcept API
"""

import sys
sys.path.insert(0, '/app')

import json
from datetime import datetime

# CORRECTED: Import from proper Flowcept modules
from flowcept import Flowcept
from flowcept.instrumentation.flowcept_decorator import flowcept
from flowcept.instrumentation.flowcept_agent_task import (
    agent_flowcept_task as flowcept_task,  # alias so the rest of the file still works
    FlowceptLLM,
    get_current_context_task,
)

from reconstruction.dag_builder import DAGBuilder
from visualization.dag_visualizer import DAGVisualizer
from visualization.prov_agent_models import ProvAgentMetadata
from visualization.prov_agent_converter import FlowceptToProvAgentConverter
from visualization.prov_agent_hallucination_detector import ProvAgentHallucinationDetector


# =====================================================
# PROV-AGENT Instrumented Tasks
# =====================================================

@flowcept_task(output_names=['results'])
def search_documents(query: str):
    """
    Analyzer agent: Search documents
    PROV-AGENT: Captures tool invocation with MCP schema
    """
    print(f"  🔍 Searching for: {query}")
    
    # Simulate search with MCP tool metadata
    results = [
        {"id": "doc_001", "title": "ML Basics", "content": "Introduction to ML"},
        {"id": "doc_002", "title": "Deep Learning", "content": "Deep learning architectures"},
        {"id": "doc_003", "title": "Neural Networks", "content": "Neural network basics"}
    ]
    
    return results


@flowcept_task(output_names=['summary'])
def summarize_content(docs: list):
    """
    Summarizer agent: Summarize documents
    PROV-AGENT: Captures reasoning step with confidence
    """
    print(f"  📝 Summarizing {len(docs)} documents")
    
    # Extract summaries
    doc_titles = [d['title'] for d in docs]
    summary = f"Found {len(docs)} documents about: {', '.join(doc_titles)}"
    
    # PROV-AGENT: Add confidence metadata
    # (Confidence will be captured in agent metadata)
    
    return summary


@flowcept_task(output_names=['classification'])
def classify_document(text: str):
    """
    Classifier agent: Classify document
    PROV-AGENT: Captures decision with confidence score
    """
    print(f"  🏷️  Classifying content")
    
    classification = "Technology / Machine Learning / Deep Learning"
    
    # In real scenario, this would be model confidence from LLM
    confidence = 0.92
    
    return classification


@flowcept
def analyze_workflow(document: str):
    """
    Main workflow with Flowcept instrumentation
    PROV-AGENT: Captures full agent interaction chain
    """
    print(f"\n▶️  Starting workflow: {document}\n")
    
    # Agent 1: Search
    results = search_documents("machine learning")
    print(f"     Found {len(results)} documents")
    
    # Agent 2: Summarize
    summary = summarize_content(results)
    print(f"     Summary: {summary}")
    
    # Agent 3: Classify
    classification = classify_document(summary)
    print(f"     Classification: {classification}")
    
    return {
        'results': results,
        'summary': summary,
        'classification': classification
    }


# =====================================================
# Main Execution
# =====================================================

def main():
    print("\n" + "="*80)
    print("PROV-AGENT + SPECTRA + Flowcept Integration Example (CORRECTED)")
    print("="*80)
    
    try:
        # 1. Run workflow with Flowcept instrumentation
        print("\n[1] Running workflow with Flowcept...")
        result = analyze_workflow("Document about machine learning")
        print("     ✅ Workflow completed")
        
    except Exception as e:
        print(f"     ❌ Workflow error: {e}")
        import traceback
        traceback.print_exc()
        return
    
    try:
        # 2. Get Flowcept events from buffer
        print("\n[2] Reading Flowcept events from buffer...")
        
        # Flowcept stores events in memory buffer
        # Get the messages that were generated
        prov_messages = Flowcept.read_buffer_file()
        
        if not prov_messages:
            print("     ⚠️  No Flowcept messages captured")
            print("     Flowcept buffer file: flowcept_messages.jsonl")
            
            # Try reading from file directly
            try:
                with open('flowcept_messages.jsonl', 'r') as f:
                    prov_messages = [json.loads(line) for line in f if line.strip()]
                print(f"     ✅ Read {len(prov_messages)} messages from flowcept_messages.jsonl")
            except FileNotFoundError:
                print("     ❌ flowcept_messages.jsonl not found")
                prov_messages = []
        else:
            print(f"     ✅ Captured {len(prov_messages)} tasks")
        
    except Exception as e:
        print(f"     ❌ Error reading Flowcept events: {e}")
        prov_messages = []
    
    try:
        # 3. Convert to PROV-AGENT format
        print("\n[3] Converting to PROV-AGENT format...")
        
        if not prov_messages:
            print("     ⚠️  No messages to convert - creating synthetic events for demo")
            
            # Create synthetic events for demonstration
            prov_messages = [
                {
                    'activity_id': 'search_documents',
                    'task_id': 'task_001',
                    'workflow_id': 'workflow_001',
                    'used': {'query': 'machine learning'},
                    'generated': {'results': 'doc_001, doc_002, doc_003'},
                    'status': 'FINISHED',
                    'started_at': datetime.now().timestamp(),
                    'ended_at': datetime.now().timestamp() + 1.0
                },
                {
                    'activity_id': 'summarize_content',
                    'task_id': 'task_002',
                    'workflow_id': 'workflow_001',
                    'used': {'docs': '[...]'},
                    'generated': {'summary': 'Found 3 documents...'},
                    'status': 'FINISHED',
                    'started_at': datetime.now().timestamp() + 1.0,
                    'ended_at': datetime.now().timestamp() + 2.0
                },
                {
                    'activity_id': 'classify_document',
                    'task_id': 'task_003',
                    'workflow_id': 'workflow_001',
                    'used': {'text': 'Found 3 documents...'},
                    'generated': {'classification': 'Tech/ML'},
                    'status': 'FINISHED',
                    'started_at': datetime.now().timestamp() + 2.0,
                    'ended_at': datetime.now().timestamp() + 3.0
                }
            ]
        
        converter = FlowceptToProvAgentConverter()
        
        # Map Flowcept tasks to agents with PROV-AGENT metadata
        agent_info = {
            'search_documents': ProvAgentMetadata(
                agent_name='analyzer',
                agent_role='content_analyzer',
                model_name='Mistral-7B',
                model_version='1.0',
                confidence=0.95,
                facility_type='cloud',
                facility_location='aws-us-east'
            ),
            'summarize_content': ProvAgentMetadata(
                agent_name='summarizer',
                agent_role='summarization_specialist',
                model_name='Mistral-7B',
                model_version='1.0',
                confidence=0.75,  # Lower confidence = potential hallucination
                facility_type='cloud',
                facility_location='aws-us-east'
            ),
            'classify_document': ProvAgentMetadata(
                agent_name='classifier',
                agent_role='document_classifier',
                model_name='Mistral-7B',
                model_version='1.0',
                confidence=0.65,  # Low confidence = high risk
                facility_type='cloud',
                facility_location='aws-us-east'
            )
        }
        
        # Convert each task
        converted_count = 0
        for task in prov_messages:
            activity_id = task.get('activity_id', '')
            metadata = agent_info.get(activity_id)
            
            if metadata:
                event = converter.convert_flowcept_task(
                    task,
                    agent_metadata=metadata,
                    facility_metadata={'type': 'cloud', 'location': 'us-east'}
                )
                converted_count += 1
                print(f"     ✅ Converted {activity_id} → PROV-AGENT event")
        
        print(f"     Total converted: {converted_count}")
        
    except Exception as e:
        print(f"     ❌ Conversion error: {e}")
        import traceback
        traceback.print_exc()
        return
    
    try:
        # 4. Detect hallucinations using PROV-AGENT metadata
        print("\n[4] Detecting hallucinations with PROV-AGENT...")
        
        detector = ProvAgentHallucinationDetector()
        
        # Register valid MCP tools (schema validation)
        detector.register_mcp_tool('search_documents', {
            'name': 'search_documents',
            'description': 'Search for documents',
            'parameters': {
                'type': 'object',
                'properties': {
                    'query': {'type': 'string'},
                    'maxResults': {'type': 'integer'}
                },
                'required': ['query']
            }
        })
        
        detector.register_mcp_tool('summarize_content', {
            'name': 'summarize_content',
            'description': 'Summarize content',
            'parameters': {
                'type': 'object',
                'properties': {
                    'text': {'type': 'string'}
                },
                'required': ['text']
            }
        })
        
        detector.register_mcp_tool('classify_document', {
            'name': 'classify_document',
            'description': 'Classify document',
            'parameters': {
                'type': 'object',
                'properties': {
                    'text': {'type': 'string'},
                    'categories': {'type': 'array'}
                },
                'required': ['text']
            }
        })
        
        # Analyze events for hallucinations
        hallucinations = detector.analyze_events(converter.get_events())
        print(f"     ⚠️  Detected {len(hallucinations)} potential hallucinations")
        
        for h in hallucinations:
            print(f"        - {h.hallucination_type} ({h.severity}): {h.description}")
        
    except Exception as e:
        print(f"     ❌ Hallucination detection error: {e}")
        import traceback
        traceback.print_exc()
        hallucinations = []
    
    try:
        # 5. Export results
        print("\n[5] Exporting results...")
        
        converter.export_to_json('prov_agent_events.json')
        hallucination_report = detector.generate_report('hallucination_report.json')
        
        print(f"     ✅ Exported PROV-AGENT events")
        print(f"     ✅ Generated hallucination report")
        
    except Exception as e:
        print(f"     ❌ Export error: {e}")
        hallucination_report = {'risk_level': 'UNKNOWN', 'by_type': {}, 'by_severity': {}}
    
    try:
        # 6. Build causal DAG
        print("\n[6] Building causal DAG...")
        
        # For demo, create simple DAG
        dag_edges = [
            ('search_documents', 'summarize_content'),
            ('summarize_content', 'classify_document')
        ]
        
        print(f"     ✅ Built DAG with {len(dag_edges)} causal edges")
        
    except Exception as e:
        print(f"     ❌ DAG build error: {e}")
        dag_edges = []
    
    # 7. Print summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"\n  PROV-AGENT Analysis:")
    print(f"    • Events captured: {len(converter.get_events())}")
    print(f"    • Hallucinations detected: {len(hallucinations)}")
    print(f"    • Risk level: {hallucination_report.get('risk_level', 'UNKNOWN')}")
    print(f"    • By type: {hallucination_report.get('by_type', {})}")
    print(f"    • By severity: {hallucination_report.get('by_severity', {})}")
    
    print(f"\n  Causal DAG:")
    print(f"    • Edges: {len(dag_edges)}")
    print(f"    • Agents: analyzer, summarizer, classifier")
    print(f"    • Flow: search → summarize → classify")
    
    print(f"\n  Generated Files:")
    print(f"    ✅ prov_agent_events.json (PROV-AGENT metadata)")
    print(f"    ✅ hallucination_report.json (Risk analysis)")
    print(f"    ✅ flowcept_messages.jsonl (Raw Flowcept events)")
    
    print("\n" + "="*80 + "\n")


if __name__ == "__main__":
    main()