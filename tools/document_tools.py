from langchain_core.tools import tool
import json

@tool
def search_documents(query: str) -> str:
    """Search knowledge base for documents matching query"""
    documents = {
        "machine learning": [
            {"id": "doc_001", "title": "ML Basics", "summary": "Introduction to machine learning concepts"},
            {"id": "doc_002", "title": "Neural Networks", "summary": "Deep learning with neural networks"},
        ],
        "ai": [
            {"id": "doc_007", "title": "AI Overview", "summary": "Artificial intelligence fundamentals"},
        ]
    }
    
    matches = []
    for key, docs in documents.items():
        if query.lower() in key.lower():
            matches.extend(docs)
    
    if not matches:
        matches = documents.get("ai", [])
    
    return json.dumps(matches[:3])

@tool
def summarize_content(content: str) -> str:
    """Summarize provided content"""
    words = content.split()
    summary = " ".join(words[:min(30, len(words))]) + "..."
    
    return json.dumps({
        "original_length": len(content),
        "summary": summary,
        "summary_length": len(summary)
    })

@tool
def classify_document(text: str) -> str:
    """Classify document into categories"""
    categories = {
        "machine learning": 0.85,
        "technical": 0.15
    }
    
    if "machine" in text.lower() or "learning" in text.lower():
        categories = {"machine learning": 0.95, "technical": 0.05}
    
    top_category = max(categories, key=categories.get)
    
    return json.dumps({
        "primary_category": top_category,
        "confidence": categories[top_category],
        "all_categories": categories
    })