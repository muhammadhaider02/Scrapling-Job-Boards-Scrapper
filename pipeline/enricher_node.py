"""
Job Enricher Node: Cleans and enhances scraped job data.

Transforms raw jobs with cleaned descriptions, semantic skill extraction, and structured fields.
"""

from typing import Dict, Any
from core.state import AgentState
from pipeline.enricher import get_enricher
from langchain_core.messages import AIMessage


def job_enricher_node(state: AgentState) -> Dict[str, Any]:
    """
    Job Enricher: Clean and enhance raw job data.
    
    Responsibilities:
    1. Retrieve raw_job_list from state
    2. Clean descriptions (HTML removal, section splitting)
    3. Extract skills semantically
    4. Parse experience requirements
    5. Normalize salary data
    6. Calculate enrichment confidence
    7. Update state with enriched_job_list
    
    Args:
        state: Current agent state
        
    Returns:
        Updated state dictionary
    """
    print("\n" + "="*60)
    print("JOB ENRICHER ACTIVATED")
    print("="*60 + "\n")
    
    # Extract raw jobs from state
    raw_jobs = state.get("raw_job_list", [])
    
    if not raw_jobs:
        print("No raw jobs to enrich")
        return {
            "raw_job_list": [],
            "messages": [AIMessage(content="No jobs to enrich.")]
        }
    
    print(f"Enriching {len(raw_jobs)} raw jobs...\n")
    
    enricher = get_enricher()
    
    try:
        # Enrich all jobs
        enriched_jobs = enricher.enrich_batch(raw_jobs)
        
        # Calculate statistics
        total_confidence = sum(job.get("enrichment_confidence", 0.0) for job in enriched_jobs)
        avg_confidence = total_confidence / len(enriched_jobs) if enriched_jobs else 0
        
        # Count enrichment successes
        high_confidence = sum(1 for job in enriched_jobs if job.get("enrichment_confidence", 0) >= 0.7)
        med_confidence = sum(1 for job in enriched_jobs if 0.5 <= job.get("enrichment_confidence", 0) < 0.7)
        low_confidence = sum(1 for job in enriched_jobs if job.get("enrichment_confidence", 0) < 0.5)
        
        print(f"\nEnrichment Statistics:")
        print(f"   Total jobs: {len(enriched_jobs)}")
        print(f"   Average confidence: {avg_confidence:.2f}")
        print(f"   High confidence (≥0.7): {high_confidence}")
        print(f"   Medium confidence (0.5-0.7): {med_confidence}")
        print(f"   Low confidence (<0.5): {low_confidence}\n")
        
        # Build summary message
        summary = f"""Enriched {len(enriched_jobs)} jobs:
  • Average confidence: {avg_confidence:.2f}
  • High confidence: {high_confidence} jobs
  • Medium confidence: {med_confidence} jobs
  • Low confidence: {low_confidence} jobs

Skills extracted, experience parsed, and descriptions cleaned."""
        
        return {
            "raw_job_list": enriched_jobs,  # Replace with enriched versions
            "messages": [AIMessage(content=summary)]
        }
    
    except Exception as e:
        error_msg = f"Enrichment error: {str(e)}"
        print(f"\n{error_msg}\n")
        
        return {
            "raw_job_list": raw_jobs,  # Keep original on error
            "error": error_msg,
            "messages": [AIMessage(content=f"Enrichment failed: {error_msg}")]
        }


# Export node
__all__ = ["job_enricher_node"]
