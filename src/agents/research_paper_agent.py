"""
Research Paper Tools — STRICT MODE version
Pure tools (NO LLM). With robust PDF text cleaning + word boundary reconstruction.
"""

from dataclasses import dataclass
from typing import Any
import os
import re
import random

# ------------------------------------------------------------
# PDF LIBRARY
# ------------------------------------------------------------
try:
    import pdfplumber
    HAS_PDF = True
except ImportError:
    HAS_PDF = False

# ------------------------------------------------------------
# OPTIONAL: wordninja for dictionary-based word segmentation
# Falls back gracefully if not installed.
# Install: pip install wordninja
# ------------------------------------------------------------
try:
    import wordninja
    HAS_WORDNINJA = True
except ImportError:
    HAS_WORDNINJA = False


# ------------------------------------------------------------
# WORD SEGMENTATION (FIX point 1)
# ------------------------------------------------------------
def segment_merged_token(token: str) -> str:
    """
    Split a merged lowercase token into dictionary words using wordninja.
    Only applied to tokens that look like merged words (long, no spaces,
    all lowercase or mixed without uppercase transitions).
    Falls back to the midpoint heuristic if wordninja is unavailable.
    """
    # Don't touch short tokens, URLs, numbers, or tokens with existing spaces
    if len(token) < 10 or " " in token or "/" in token or token[0].isdigit():
        return token

    # Only process all-lowercase or nearly-all-lowercase tokens
    lower_ratio = sum(1 for c in token if c.islower()) / max(len(token), 1)
    if lower_ratio < 0.85:
        return token

    if HAS_WORDNINJA:
        words = wordninja.split(token)
        # Sanity check: reject if split produced too many 1-char fragments
        if sum(1 for w in words if len(w) == 1) <= 2:
            return " ".join(words)

    # Fallback: split long runs at midpoint
    if len(token) >= 14:
        mid = len(token) // 2
        return token[:mid] + " " + token[mid:]

    return token


def recover_missing_spaces(text: str) -> str:
    """
    Fix merged words in PDF-extracted text.
    Strategy:
      1. Handle camelCase / lowercase→uppercase transitions (structural)
      2. Apply dictionary segmentation to remaining long merged tokens
    """
    if not text:
        return ""

    # camelCase and lowercase→uppercase transitions
    text = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", text)
    text = re.sub(r"([a-z]{4,})([A-Z][a-z]+)", r"\1 \2", text)

    # Space after punctuation if glued
    text = re.sub(r"([.,;:!?])(?=[A-Za-z])", r"\1 ", text)

    # Parenthesis spacing
    text = re.sub(r"\(", " (", text)
    text = re.sub(r"\)", ") ", text)

    # Dictionary-based segmentation on each token
    tokens   = text.split(" ")
    repaired = [segment_merged_token(t) for t in tokens]
    text     = " ".join(repaired)

    # Collapse multiple spaces
    text = re.sub(r"\s{2,}", " ", text)

    return text


# ------------------------------------------------------------
# PDF TEXT CLEANER
# ------------------------------------------------------------
def clean_pdf_text(raw: str) -> str:
    """Clean and normalize text extracted from PDFs."""
    if not raw:
        return ""

    text = raw.replace("\r", "\n")

    ligatures = {"ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl"}
    for k, v in ligatures.items():
        text = text.replace(k, v)

    # De-hyphenate across newlines
    text = re.sub(r"(\w+)-\s*\n(\w+)", r"\1\2", text)

    # Normalize whitespace within lines
    text = re.sub(r"[ \t]+", " ", text)

    # Merge soft paragraph breaks
    text = re.sub(r"\n(?=[a-z])", " ", text)
    text = re.sub(r"(?<=[a-zA-Z]),\n", ", ", text)
    text = re.sub(r"(?<=[a-z])\n(?=[A-Z])", " ", text)

    # Collapse multiple newlines
    text = re.sub(r"\n{2,}", "\n\n", text)

    # Remove duplicate lines
    lines = text.split("\n")
    seen, cleaned = set(), []
    for ln in lines:
        stripped = ln.strip()
        if stripped not in seen:
            cleaned.append(ln)
            seen.add(stripped)
    text = "\n".join(cleaned)

    # Space recovery
    text = recover_missing_spaces(text)

    text = re.sub(r"\s{2,}", " ", text)
    text = re.sub(r"\n\s+", "\n", text)

    return text.strip()


# ------------------------------------------------------------
# PAPER METADATA
# ------------------------------------------------------------
@dataclass
class PaperMetadata:
    title: str
    authors: list[str]
    abstract: str
    year: int
    doi: str
    pages: int
    full_text: str = ""


# ------------------------------------------------------------
# INGESTION TOOL
# ------------------------------------------------------------
def ingest_paper(file_path: str) -> PaperMetadata:
    """
    Extract metadata + cleaned text from PDF.

    Dual extraction strategy:
      - Page 1 uses extract_text() to preserve line structure for title extraction.
      - All pages use extract_words(use_text_flow=True) for body text to handle
        multi-column layouts. Falls back to extract_text() per page on failure.
    """
    if HAS_PDF and os.path.exists(file_path):
        try:
            with pdfplumber.open(file_path) as pdf:
                # --- Page 1: line-structured for title ---
                first_page_raw   = pdf.pages[0].extract_text() or "" if pdf.pages else ""
                first_page_clean = clean_pdf_text(first_page_raw)

                # --- All pages: word-flow for body text ---
                pages_text = []
                for page in pdf.pages:
                    try:
                        words = page.extract_words(
                            x_tolerance=3,
                            y_tolerance=3,
                            keep_blank_chars=False,
                            use_text_flow=True,
                        )
                        if words:
                            pages_text.append(" ".join(w["text"] for w in words))
                        else:
                            pages_text.append(page.extract_text() or "")
                    except Exception:
                        pages_text.append(page.extract_text() or "")

                raw_full  = "\n\n".join(pages_text)
                full_text = clean_pdf_text(raw_full)

                # --- Title from line-structured page 1 ---
                title = "Unknown Title"
                for line in first_page_clean.splitlines():
                    stripped = line.strip()
                    if stripped and len(stripped) > 5 and len(stripped) < 200:
                        title = stripped
                        break

                # --- Abstract from body text ---
                abstract = "No abstract found."
                m = re.search(
                    r"Abstract[:\s]+(.+?)(?:\n\n|Introduction|1\.)",
                    full_text,
                    flags=re.I | re.S,
                )
                if m:
                    abstract = m.group(1).strip()

                # --- Year ---
                meta  = pdf.metadata or {}
                year  = 0
                cdate = meta.get("CreationDate") or meta.get("ModDate")
                if isinstance(cdate, str) and cdate.startswith("D:"):
                    try:
                        year = int(cdate[2:6])
                    except Exception:
                        year = 0

                return PaperMetadata(
                    title=title[:200],
                    authors=[],
                    abstract=abstract[:2000],
                    year=year,
                    doi="",
                    pages=len(pdf.pages),
                    full_text=full_text,
                )

        except Exception:
            return _neutral_fallback()

    return _neutral_fallback()


def _neutral_fallback() -> PaperMetadata:
    return PaperMetadata(
        title="Unknown Title",
        authors=[],
        abstract="No abstract extracted.",
        year=0,
        doi="",
        pages=0,
        full_text="",
    )


# ------------------------------------------------------------
# SEARCH TOOL
# ------------------------------------------------------------
def search_content(paper: PaperMetadata, query: str) -> list[dict]:
    text  = paper.full_text.lower()
    query = query.lower()
    results = []
    if query in text:
        idx     = text.find(query)
        snippet = paper.full_text[max(0, idx - 150): idx + 150]
        results.append({"section": "Context", "content": snippet, "relevance": 0.95})
    return results


# ------------------------------------------------------------
# FINDINGS TOOL
# ------------------------------------------------------------
def extract_key_findings(paper: PaperMetadata) -> dict[str, Any]:
    text      = (paper.abstract or "") + "\n" + (paper.full_text or "")
    sentences = re.split(r"(?<=[.!?])\s+", text)
    interesting = [
        s for s in sentences
        if any(k in s.lower() for k in ["improve", "achieve", "accuracy", "%", "throughput"])
    ]
    return {
        "main_contribution": (paper.abstract or paper.title)[:500],
        "key_results":       interesting[:3],
        "impact_score":      6.5 if interesting else 5.0,
        "citations_estimated": 0,
    }


# ------------------------------------------------------------
# CITATION VALIDATION (SIMULATED)
# ------------------------------------------------------------
def validate_citations(paper: PaperMetadata, sample_size: int = 5) -> dict[str, Any]:
    if random.random() < 0.05:
        raise TimeoutError("Citation DB timeout")
    return {
        "total_citations": 42,
        "validated":       40,
        "validation_rate": 40 / 42,
        "issues":          [],
    }


# ------------------------------------------------------------
# RELATIONSHIP MAP
# ------------------------------------------------------------
def map_citation_relationships(paper: PaperMetadata) -> dict[str, Any]:
    return {
        "total_relationships": 12,
        "clusters": [
            {"name": "Cluster A", "papers": 5},
            {"name": "Cluster B", "papers": 4},
        ],
    }


# ------------------------------------------------------------
# SYNTHESIS TOOL
# ------------------------------------------------------------
def synthesize_analysis(findings: dict, citations: dict, relationships: dict) -> str:
    return (
        f"Contribution: {findings.get('main_contribution')}. "
        f"Impact score: {findings.get('impact_score')}. "
        f"Citation validation: {citations.get('validation_rate', 'N/A')}. "
        f"Clusters: {len(relationships.get('clusters', []))}."
    )


# ------------------------------------------------------------
# TOOL REGISTRATION
# ------------------------------------------------------------
RESEARCH_TOOLS = {
    "ingest_paper": {
        "func":        ingest_paper,
        "description": "Extract and clean text from a PDF file. ONLY param: file_path (str).",
        "inputs":      ["file_path"],
    },
    "search_content": {
        "func":        search_content,
        "description": "Search cleaned paper text. ONLY params: paper (PaperMetadata), query (str).",
        "inputs":      ["paper", "query"],
    },
    "extract_findings": {
        "func":        extract_key_findings,
        "description": (
            "Extract key findings from an already-ingested paper. "
            "ONLY param: paper (PaperMetadata). "
            "Do NOT pass file_path. The paper object is injected automatically."
        ),
        "inputs":      ["paper"],
    },
    "validate_citations": {
        "func":        validate_citations,
        "description": (
            "Validate citations in a paper. "
            "ONLY params: paper (PaperMetadata), sample_size (int, optional). "
            "Use this tool FIRST when the goal involves citation validation."
        ),
        "inputs":      ["paper", "sample_size"],
    },
    "map_relationships": {
        "func":        map_citation_relationships,
        "description": (
            "Map citation relationships in a paper. "
            "ONLY param: paper (PaperMetadata). "
            "Use this tool AFTER validate_citations, not instead of it."
        ),
        "inputs":      ["paper"],
    },
    "synthesize": {
        "func":        synthesize_analysis,
        "description": (
            "Produce final synthesis text. "
            "ONLY params: findings (dict), citations (dict), relationships (dict). "
            "Do NOT pass paper, file_path, or sample_size. "
            "All params are injected automatically from pipeline state."
        ),
        "inputs":      ["findings", "citations", "relationships"],
    },
}