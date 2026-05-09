"""
Indeed Pakistan job parser using Scrapling.

Indeed is a global job search engine with Pakistan listings.
"""

from typing import Optional, List, Any
from core.state import JobData
from .base import BaseJobParser


class IndeedParser(BaseJobParser):
    """Indeed job board parser."""
    
    board_name = "indeed"
    
    def parse_job(self, response: Any) -> Optional[JobData]:
        """
        Parse Indeed job posting page.
        
        Indeed structure:
        - Title: h1.jobsearch-JobInfoHeader-title or .jobsearch-JobInfoHeader-title-container h1
        - Company: div.jobsearch-InlineCompanyRating > div
        - Location: div.jobsearch-JobInfoHeader-subtitle > div
        - Description: div#jobDescriptionText or .jobsearch-jobDescriptionText
        
        Args:
            response: Scrapling Response object
            
        Returns:
            JobData or None
        """
        try:
            # Extract title
            title = self._css_first(response, [
                "h1.jobsearch-JobInfoHeader-title",
                ".jobsearch-JobInfoHeader-title-container h1",
                "h1[data-testid='jobsearch-JobInfoHeader-title']"
            ])
            
            if not title:
                print(f"Indeed: No title found at {response.url}")
                return None
            
            title_text = self.clean_text(self._get_text(title))
            
            # Extract company
            company = self._css_first(response, [
                "div.jobsearch-InlineCompanyRating > div",
                "div[data-company-name='true']",
                ".jobsearch-CompanyInfoContainer a"
            ])
            
            company_text = self.clean_text(self._get_text(company)) if company else "Unknown"
            
            # Extract location
            location = self._css_first(response, [
                "div.jobsearch-JobInfoHeader-subtitle > div:last-child",
                "div[data-testid='job-location']",
                ".jobsearch-JobInfoHeader-subtitle .jobsearch-JobInfoHeader-subtitle-link"
            ])
            
            location_text = self.clean_text(self._get_text(location)) if location else "Pakistan"
            
            # Extract description
            description = self._css_first(response, [
                "div#jobDescriptionText",
                ".jobsearch-jobDescriptionText",
                "div[id='jobDescriptionText']"
            ])
            
            description_text = ""
            if description:
                description_text = self.clean_text(self._get_text(description))
            
            if not description_text or len(description_text) < 50:
                print(f"Indeed: Description too short at {response.url}")
                return None
            
            # Extract salary (if available)
            salary = None
            salary_elem = self._css_first(response, [
                ".jobsearch-JobMetadataHeader-item",
                "div[data-testid='jobsearch-JobMetadataHeader-salary']",
                ".salary-snippet"
            ])
            
            if salary_elem and ("PKR" in self._get_text(salary_elem) or "Rs" in self._get_text(salary_elem)):
                salary = self.clean_text(self._get_text(salary_elem))
            
            # Extract employment type
            employment_type = None
            job_type_elem = self._css_first(response, [
                "div[data-testid='job-type-text']",
                ".jobsearch-JobMetadataHeader-item"
            ])
            
            if job_type_elem:
                job_type_text = self._get_text(job_type_elem).lower()
                if "full-time" in job_type_text or "full time" in job_type_text:
                    employment_type = "full-time"
                elif "part-time" in job_type_text:
                    employment_type = "part-time"
                elif "contract" in job_type_text:
                    employment_type = "contract"
                elif "internship" in job_type_text or "intern" in job_type_text:
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
                "posted_date": None,  # Indeed shows relative dates ("Posted 2 days ago")
                "salary": salary,
                "employment_type": employment_type,
                "experience_required": None,
                "raw_html": self._get_html(response)
            }
            
            if self.validate_job_data(job_data):
                return job_data
            else:
                return None
        
        except Exception as e:
            print(f"Indeed parse error: {e}")
            return None
    
    def parse_listing(self, response: Any) -> List[str]:
        """
        Extract job URLs from Indeed search results.
        
        Args:
            response: Scrapling Response from search page
            
        Returns:
            List of job URLs
        """
        urls = []
        
        try:
            # Try different selectors (Scrapling css() expects single selector)
            selectors = [
                "a.jcs-JobTitle",
                "a[data-testid='job-title']",
                ".jobsearch-ResultsList a[id^='job_']"
            ]
            
            links = []
            for selector in selectors:
                found = response.css(selector)
                if found:
                    links.extend(found)
            
            for link in links:
                url = link.attrib.get("href", "")
                
                if url and "/rc/clk" in url:
                    # Indeed uses redirect URLs - extract job ID
                    job_id = None
                    if "jk=" in url:
                        job_id = url.split("jk=")[1].split("&")[0]
                    
                    if job_id:
                        # Build direct job URL
                        direct_url = f"https://pk.indeed.com/viewjob?jk={job_id}"
                        urls.append(direct_url)
                elif url and "/viewjob" in url:
                    # Direct job URL
                    if not url.startswith("http"):
                        url = f"https://pk.indeed.com{url}"
                    urls.append(url)
            
            print(f"Indeed: Found {len(urls)} job URLs")
            
        except Exception as e:
            print(f"Indeed listing parse error: {e}")
        
        return urls
    
    def build_search_url(self, query: str, location: str = "Pakistan", page: int = 1) -> str:
        """
        Build Indeed job search URL for Pakistan.
        
        Args:
            query: Search keywords
            location: Location filter
            page: Page number (Indeed uses start index, 10 jobs per page)
            
        Returns:
            Search URL
        """
        import urllib.parse
        query_encoded = urllib.parse.quote(query)
        location_encoded = urllib.parse.quote(location)
        
        # Indeed uses start parameter (10 jobs per page)
        start = (page - 1) * 10
        
        url = (
            f"https://pk.indeed.com/jobs"
            f"?q={query_encoded}"
            f"&l={location_encoded}"
        )
        
        if start > 0:
            url += f"&start={start}"
        
        return url


def parse_indeed_job(response: Any) -> Optional[JobData]:
    """Convenience function for Indeed job parsing."""
    parser = IndeedParser()
    return parser.parse_job(response)
