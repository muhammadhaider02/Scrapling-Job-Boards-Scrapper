"""
Base parser interface for job board scrapers.

All board-specific parsers inherit from this ABC to ensure consistent API.
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from core.state import JobData
import hashlib


class BaseJobParser(ABC):
    """
    Abstract base class for job board parsers.
    
    Each parser implements board-specific extraction logic using Scrapling's
    adaptive parsing capabilities.
    """
    
    board_name: str = "unknown"
    
    @abstractmethod
    def parse_job(self, response: Any) -> Optional[JobData]:
        """
        Parse single job page into structured data.
        
        Args:
            response: Scrapling Selector object (returned by fetch())
            
        Returns:
            JobData dictionary or None on failure
        """
        pass
    
    @abstractmethod
    def parse_listing(self, response: Any) -> List[str]:
        """
        Extract job URLs from listing page.
        
        Args:
            response: Scrapling Selector from search results page
            
        Returns:
            List of job URLs to scrape
        """
        pass
    
    @abstractmethod
    def build_search_url(self, query: str, location: str = "", page: int = 1) -> str:
        """
        Build search URL for job query.
        
        Args:
            query: Search keywords (e.g., "python developer")
            location: Location filter (e.g., "lahore")
            page: Page number for pagination
            
        Returns:
            Full search URL
        """
        pass
    
    def generate_job_id(self, title: str, company: str, location: str) -> str:
        """
        Generate deterministic job ID from key fields.
        
        Args:
            title: Job title
            company: Company name
            location: Job location
            
        Returns:
            SHA256 hash (first 16 chars)
        """
        unique_string = f"{title.lower()}|{company.lower()}|{location.lower()}"
        return hashlib.sha256(unique_string.encode()).hexdigest()[:16]
    
    def clean_text(self, text: Optional[str]) -> str:
        """
        Clean extracted text (remove extra whitespace, newlines).
        
        Args:
            text: Raw text
            
        Returns:
            Cleaned text
        """
        if not text:
            return ""
        
        text = " ".join(text.split())
        return text.strip()
    
    def validate_job_data(self, data: Dict[str, Any]) -> bool:
        """
        Validate required fields are present.
        
        Args:
            data: Job data dictionary
            
        Returns:
            True if valid
        """
        required_fields = ["title", "company", "location", "job_url", "description"]
        
        for field in required_fields:
            if not data.get(field):
                print(f"Missing required field: {field}")
                return False
        
        return True
    
    def _css_first(self, response: Any, selectors: List[str]) -> Optional[Any]:
        """
        Try multiple CSS selectors and return first match.
        
        Args:
            response: Scrapling Response object
            selectors: List of CSS selectors to try
            
        Returns:
            First matched element or None
        """
        for selector in selectors:
            try:
                elements = response.css(selector)
                if elements and len(elements) > 0:
                    return elements[0]
            except Exception:
                continue
        return None
    
    def _get_text(self, element: Any, get_all: bool = True) -> str:
        """
        Extract text from a Scrapling element using ::text pseudo-element.
        
        Args:
            element: Scrapling element
            get_all: If True, gets all text nodes and joins them (for nested HTML).
                     If False, gets only first text node.
            
        Returns:
            Text content or empty string
        """
        if element is None:
            return ""
        
        try:
            if get_all:
                # Use ::text pseudo-element to extract all text nodes (for nested HTML)
                text_results = element.css('::text').getall()
                return ' '.join(text_results) if text_results else ""
            else:
                # Get only first text node
                text_result = element.css('::text').get()
                return text_result if text_result else ""
        except Exception:
            # Fallback to .text attribute if it exists
            try:
                return str(element.text) if hasattr(element, 'text') else ""
            except Exception:
                return ""
    
    def _get_html(self, response: Any) -> str:
        """
        Extract raw HTML from a Scrapling response.
        
        Args:
            response: Scrapling Response object
            
        Returns:
            Raw HTML string or empty string
        """
        if response is None:
            return ""
        
        try:
            # Try .get() method (Parsel-like API)
            if hasattr(response, 'get'):
                html = response.get()
                return html if html else ""
        except Exception:
            pass
        
        try:
            # Try direct HTML attribute
            if hasattr(response, 'html'):
                return str(response.html)
        except Exception:
            pass
        
        try:
            # Try body attribute
            if hasattr(response, 'body'):
                return str(response.body)
        except Exception:
            pass
        
        return ""
