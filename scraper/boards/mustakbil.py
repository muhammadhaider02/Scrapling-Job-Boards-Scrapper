"""
Mustakbil.com job parser using Scrapling.

Mustakbil is a Pakistan-based job portal.
"""

from typing import Optional, List, Any
from core.state import JobData
from .base import BaseJobParser


class MustakbilParser(BaseJobParser):
    """Mustakbil.com job board parser."""
    
    board_name = "mustakbil"
    
    def parse_job(self, response: Any) -> Optional[JobData]:
        """
        Parse Mustakbil job posting page.
        
        Mustakbil structure (varies by page design):
        - Title: h1 or .job-title
        - Company: .company-name or .employer
        - Location: .job-location or .location-info
        - Description: .job-description or #description
        
        Args:
            response: Scrapling Response object
            
        Returns:
            JobData or None
        """
        try:
            # Extract title
            title = self._css_first(response, [
                "h1.job-title",
                "h1",
                ".job-detail-header h1"
            ])
            
            if not title:
                print(f"Mustakbil: No title found at {response.url}")
                return None
            
            title_text = self.clean_text(self._get_text(title))
            
            # Extract company
            company = self._css_first(response, [
                ".company-name",
                ".employer",
                ".company-info a"
            ])
            
            company_text = self.clean_text(self._get_text(company)) if company else "Unknown"
            
            # Extract location
            location = self._css_first(response, [
                ".job-location",
                ".location-info",
                "span.location"
            ])
            
            location_text = self.clean_text(self._get_text(location)) if location else "Pakistan"
            
            # Extract description
            description = self._css_first(response, [
                ".job-description",
                "#description",
                ".description-content"
            ])
            
            description_text = ""
            if description:
                description_text = self.clean_text(self._get_text(description))
            
            if not description_text or len(description_text) < 50:
                print(f"Mustakbil: Description too short at {response.url}")
                return None
            
            # Extract salary (if available)
            salary = None
            salary_elem = self._css_first(response, [
                ".salary-info",
                ".job-salary",
                "span.salary"
            ])
            
            if salary_elem:
                salary = self.clean_text(self._get_text(salary_elem))
            
            # Extract posted date
            posted_date = None
            date_elem = self._css_first(response, [
                ".posted-date",
                ".date-posted",
                "time"
            ])
            
            if date_elem:
                posted_date = self.clean_text(self._get_text(date_elem))
            
            # Extract employment type
            employment_type = None
            emp_elem = self._css_first(response, [
                ".job-type",
                ".employment-type"
            ])
            
            if emp_elem:
                emp_text = self._get_text(emp_elem).lower()
                if "full" in emp_text:
                    employment_type = "full-time"
                elif "part" in emp_text:
                    employment_type = "part-time"
                elif "contract" in emp_text:
                    employment_type = "contract"
                elif "intern" in emp_text:
                    employment_type = "internship"
            
            # Extract experience required
            experience_required = None
            exp_elem = self._css_first(response, [
                ".experience-required",
                ".required-experience"
            ])
            
            if exp_elem:
                experience_required = self.clean_text(self._get_text(exp_elem))
            
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
                "posted_date": posted_date,
                "salary": salary,
                "employment_type": employment_type,
                "experience_required": experience_required,
                "raw_html": self._get_html(response)
            }
            
            if self.validate_job_data(job_data):
                return job_data
            else:
                return None
        
        except Exception as e:
            print(f"Mustakbil parse error: {e}")
            return None
    
    def parse_listing(self, response: Any) -> List[str]:
        """
        Extract job URLs from Mustakbil search results.
        
        Args:
            response: Scrapling Response from search page
            
        Returns:
            List of job URLs
        """
        urls = []
        
        try:
            # Try different selectors (Scrapling css() expects single selector)
            selectors = [
                ".job-listing a.job-link",
                ".job-card a",
                "a[href*='/jobs/']"
            ]
            
            links = []
            for selector in selectors:
                found = response.css(selector)
                if found:
                    links.extend(found)
            
            for link in links:
                url = link.attrib.get("href", "")
                
                if url and "/jobs/" in url:
                    # Ensure full URL
                    if not url.startswith("http"):
                        url = f"https://www.mustakbil.com{url}"
                    
                    urls.append(url)
            
            print(f"Mustakbil: Found {len(urls)} job URLs")
            
        except Exception as e:
            print(f"Mustakbil listing parse error: {e}")
        
        return urls
    
    def build_search_url(self, query: str, location: str = "", page: int = 1) -> str:
        """
        Build Mustakbil job search URL.
        
        Args:
            query: Search keywords
            location: Location filter (optional)
            page: Page number
            
        Returns:
            Search URL
        """
        import urllib.parse
        query_encoded = urllib.parse.quote(query)
        
        url = f"https://www.mustakbil.com/jobs/search?q={query_encoded}"
        
        if location:
            location_encoded = urllib.parse.quote(location)
            url += f"&location={location_encoded}"
        
        if page > 1:
            url += f"&page={page}"
        
        return url


def parse_mustakbil_job(response: Any) -> Optional[JobData]:
    """Convenience function for Mustakbil job parsing."""
    parser = MustakbilParser()
    return parser.parse_job(response)
