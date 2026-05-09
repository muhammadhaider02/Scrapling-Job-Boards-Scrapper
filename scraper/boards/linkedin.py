"""
LinkedIn job parser using Scrapling's adaptive parsing.

Handles LinkedIn's dynamic content and anti-bot protection.
"""

from typing import Optional, List, Any
from core.state import JobData
from .base import BaseJobParser


class LinkedInParser(BaseJobParser):
    """LinkedIn job board parser."""
    
    board_name = "linkedin"
    
    def parse_job(self, response: Any) -> Optional[JobData]:
        """
        Parse LinkedIn job posting page.
        
        LinkedIn structure:
        - Title: h1.top-card-layout__title or .job-details-jobs-unified-top-card__job-title
        - Company: a.topcard__org-name-link or .job-details-jobs-unified-top-card__company-name
        - Location: span.topcard__flavor--bullet or .job-details-jobs-unified-top-card__bullet
        - Description: div.description__text or .jobs-description-content__text
        
        Args:
            response: Scrapling Response object
            
        Returns:
            JobData or None
        """
        try:
            # Extract title (adaptive selector)
            title = self._css_first(response, [
                "h1.top-card-layout__title",
                ".job-details-jobs-unified-top-card__job-title",
                "h1.jobs-unified-top-card__job-title"
            ])
            
            if not title:
                print(f"LinkedIn: No title found at {response.url}")
                return None
            
            title_text = self.clean_text(self._get_text(title))
            
            # Extract company
            company = self._css_first(response, [
                "a.topcard__org-name-link",
                ".job-details-jobs-unified-top-card__company-name a",
                ".jobs-unified-top-card__company-name a"
            ])
            
            if not company:
                # Fallback: try without link
                company = self._css_first(response, [
                    ".job-details-jobs-unified-top-card__company-name",
                    ".jobs-unified-top-card__company-name"
                ])
            
            company_text = self.clean_text(self._get_text(company)) if company else "Unknown"
            
            # Extract location
            location = self._css_first(response, [
                "span.topcard__flavor--bullet",
                ".job-details-jobs-unified-top-card__bullet",
                ".jobs-unified-top-card__bullet"
            ])
            
            location_text = self.clean_text(self._get_text(location)) if location else "Pakistan"
            
            # Extract description
            description = self._css_first(response, [
                "div.description__text",
                ".jobs-description-content__text",
                ".jobs-description__content"
            ])
            
            description_text = ""
            if description:
                # Get all text including nested elements
                description_text = self.clean_text(self._get_text(description))
            
            if not description_text or len(description_text) < 50:
                print(f"LinkedIn: Description too short at {response.url}")
                return None
            
            # Extract employment type
            employment_type = None
            emp_type_elem = self._css_first(response, [
                ".job-details-jobs-unified-top-card__job-insight span",
                "li.jobs-unified-top-card__job-insight span"
            ])
            
            if emp_type_elem:
                emp_text = self._get_text(emp_type_elem).lower()
                if "full-time" in emp_text or "full time" in emp_text:
                    employment_type = "full-time"
                elif "part-time" in emp_text:
                    employment_type = "part-time"
                elif "contract" in emp_text:
                    employment_type = "contract"
                elif "internship" in emp_text:
                    employment_type = "internship"
            
            # Skills are extracted by the enricher pipeline, not the parser.
            skills: List[str] = []
            
            # Generate job ID
            job_id = self.generate_job_id(title_text, company_text, location_text)
            
            # Build job data
            job_data: JobData = {
                "job_id": job_id,
                "title": title_text,
                "company": company_text,
                "location": location_text,
                "job_url": response.url,
                "board": self.board_name,
                "description": description_text,
                "skills": skills,
                "posted_date": None,  # LinkedIn often doesn't show exact date
                "salary": None,  # Rarely shown on LinkedIn Pakistan
                "employment_type": employment_type,
                "experience_required": None,  # Could extract from description
                "raw_html": self._get_html(response)
            }
            
            if self.validate_job_data(job_data):
                return job_data
            else:
                return None
        
        except Exception as e:
            print(f"LinkedIn parse error: {e}")
            return None
    
    def parse_listing(self, response: Any) -> List[str]:
        """
        Extract job URLs from LinkedIn search results.
        
        LinkedIn structure:
        - Job cards: .job-search-card or .jobs-search__results-list li
        - Job links: a.base-card__full-link
        
        Args:
            response: Scrapling Response from search page
            
        Returns:
            List of job URLs
        """
        urls = []
        
        try:
            # Try different selectors (Scrapling css() expects single selector)
            selectors = [
                "a.base-card__full-link",
                ".job-search-card__link-wrapper",
                ".jobs-search-results__list-item a"
            ]
            
            links = []
            for selector in selectors:
                found = response.css(selector)
                if found:
                    links.extend(found)
            
            for link in links:
                url = link.attrib.get("href", "")
                
                # Clean URL (remove query params)
                if url and "/jobs/view/" in url:
                    # Extract base job URL
                    base_url = url.split("?")[0]
                    
                    # Ensure full URL
                    if not base_url.startswith("http"):
                        base_url = f"https://www.linkedin.com{base_url}"
                    
                    urls.append(base_url)
            
            print(f"LinkedIn: Found {len(urls)} job URLs")
            
        except Exception as e:
            print(f"LinkedIn listing parse error: {e}")
        
        return urls
    
    def build_search_url(self, query: str, location: str = "Pakistan", page: int = 1) -> str:
        """
        Build LinkedIn job search URL.
        
        Args:
            query: Search keywords
            location: Location filter
            page: Page number (LinkedIn uses start index)
            
        Returns:
            Search URL
        """
        # LinkedIn uses start parameter (25 jobs per page)
        start = (page - 1) * 25
        
        # URL encode query
        import urllib.parse
        query_encoded = urllib.parse.quote(query)
        location_encoded = urllib.parse.quote(location)
        
        url = (
            f"https://www.linkedin.com/jobs/search/"
            f"?keywords={query_encoded}"
            f"&location={location_encoded}"
            f"&start={start}"
        )
        
        return url


def parse_linkedin_job(response: Any) -> Optional[JobData]:
    """Convenience function for LinkedIn job parsing."""
    parser = LinkedInParser()
    return parser.parse_job(response)
