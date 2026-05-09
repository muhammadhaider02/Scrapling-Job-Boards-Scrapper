"""
Shared state and job data types for standalone scraper flows.
"""

from typing import Any, List, Optional, TypedDict


class JobData(TypedDict, total=False):
    job_id: str
    title: str
    company: str
    location: str
    job_url: str
    board: str
    description: str
    skills: List[str]
    posted_date: Optional[str]
    salary: Optional[str]
    employment_type: Optional[str]
    experience_required: Optional[str]
    education_required: Optional[str]
    industry: Optional[str]
    raw_html: str
    date_scrapped: Optional[str]
    job_source: Optional[str]


class AgentState(TypedDict, total=False):
    messages: List[Any]
    user_id: str
    search_query: str
    raw_job_list: List[JobData]
    scraping_status: str
    current_page: int
    error: Optional[str]
    retry_count: int
