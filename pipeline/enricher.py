"""
Job data enrichment utility.

Cleans descriptions, extracts skills semantically, parses experience, and normalizes salary.
"""

import re
import html
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import pandas as pd
from pathlib import Path


class JobEnricher:
    """
    Enriches raw job data with cleaned descriptions, semantic skills, and structured fields.
    """
    
    def __init__(self, skill_list_path: Optional[str] = None):
        """
        Initialize enricher.
        
        Args:
            skill_list_path: Path to master skill list Excel file
        """
        self.skill_list = self._load_skill_list(skill_list_path)
        print(f"JobEnricher initialized with {len(self.skill_list)} skills")
    
    def _load_skill_list(self, skill_list_path: str) -> List[str]:
        """
        Load master skill list from Excel.

        Args:
            skill_list_path: Path to skills_master.xlsx

        Returns:
            List of skill keywords

        Raises:
            FileNotFoundError: If the Excel file does not exist at the given path.
            RuntimeError: If the Excel file exists but cannot be read.
        """
        if not skill_list_path or not Path(skill_list_path).exists():
            raise FileNotFoundError(
                f"[JobEnricher] Skill list Excel not found at: '{skill_list_path}'\n"
                f"Set EXCEL_SKILL_GAP in your .env to point to data/skills_master.xlsx."
            )

        try:
            df = pd.read_excel(skill_list_path)
            skills = df.iloc[:, 0].dropna().tolist()
            print(f"   Loaded {len(skills)} skills from {skill_list_path}")
            return skills
        except Exception as e:
            raise RuntimeError(
                f"[JobEnricher] Failed to read skill list from '{skill_list_path}': {e}"
            ) from e
    
    def clean_description(self, description: str, raw_html: str = "") -> Dict[str, Any]:
        """
        Clean and structure job description.
        
        Args:
            description: Extracted description text
            raw_html: Raw HTML for fallback parsing
            
        Returns:
            Dictionary with cleaned text and sections
        """
        if not description:
            return {
                "full_text": "",
                "sections": {},
                "word_count": 0
            }
        
        # Step 1: Decode HTML entities
        cleaned = html.unescape(description)
        
        # Step 2: Remove extra whitespace and normalize
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        # Step 3: Split into sections (heuristic-based)
        sections = self._split_into_sections(cleaned)
        
        # Step 4: Deduplicate repeated phrases
        cleaned = self._deduplicate_text(cleaned)
        
        return {
            "full_text": cleaned,
            "sections": sections,
            "word_count": len(cleaned.split())
        }
    
    def _split_into_sections(self, text: str) -> Dict[str, str]:
        """
        Split description into sections using keyword detection.
        
        Args:
            text: Cleaned description text
            
        Returns:
            Dictionary of section names to content
        """
        sections = {}
        
        # Section keywords (case-insensitive)
        section_patterns = {
            "responsibilities": r"(?:responsibilities|duties|role|what you['\u2019]ll do|key tasks)",
            "requirements": r"(?:requirements|qualifications|what we['\u2019]re looking for|must have|required skills)",
            "preferred": r"(?:preferred|nice to have|bonus|plus|good to have)",
            "benefits": r"(?:benefits|perks|what we offer|why join|compensation)",
            "about_company": r"(?:about us|about the company|who we are|company overview)"
        }
        
        # Find section boundaries
        matches = []
        for section_name, pattern in section_patterns.items():
            for match in re.finditer(pattern, text, re.IGNORECASE):
                matches.append((match.start(), section_name))
        
        # Sort by position
        matches.sort()
        
        # Extract sections
        for i, (start, section_name) in enumerate(matches):
            # Find end (next section or end of text)
            end = matches[i + 1][0] if i + 1 < len(matches) else len(text)
            
            # Extract section content
            section_text = text[start:end].strip()
            
            # Remove section header
            section_text = re.sub(section_patterns[section_name], '', section_text, count=1, flags=re.IGNORECASE).strip()
            
            # Clean up formatting
            section_text = re.sub(r'^[:•\-\s]+', '', section_text).strip()
            
            if section_text:
                sections[section_name] = section_text
        
        return sections
    
    def _deduplicate_text(self, text: str) -> str:
        """
        Remove duplicate sentences (common in auto-generated postings).
        
        Args:
            text: Input text
            
        Returns:
            Deduplicated text
        """
        sentences = re.split(r'[.!?]\s+', text)
        seen = set()
        unique = []
        
        for sentence in sentences:
            # Normalize for comparison
            normalized = sentence.lower().strip()
            if normalized and normalized not in seen and len(normalized) > 10:
                seen.add(normalized)
                unique.append(sentence)
        
        return '. '.join(unique) + '.' if unique else text
    
    def _categorize_skill(self, skill: str) -> str:
        """
        Categorize a skill into technical/soft/tools.
        
        Args:
            skill: Skill name
            
        Returns:
            Category name
        """
        skill_lower = skill.lower()
        
        # Soft skills keywords
        soft_keywords = ["communication", "leadership", "team", "problem", "collaboration", 
                        "analytical", "creative", "critical thinking", "management"]
        if any(keyword in skill_lower for keyword in soft_keywords):
            return "soft"
        
        # Tool keywords
        tool_keywords = ["git", "jira", "jenkins", "docker", "kubernetes", "hadoop"]
        if any(keyword in skill_lower for keyword in tool_keywords):
            return "tools"
        
        # Default: technical
        return "technical"
    
    def extract_skills(self, description: str, title: str, existing_skills: List[str] = None) -> Dict[str, List[str]]:
        """
        Extract and categorize skills from description and existing skills list.
        
        Args:
            description: Job description text
            title: Job title (for relevance filtering)
            existing_skills: Pre-extracted skills from job board parser
            
        Returns:
            Categorized skills dictionary
        """
        desc_lower = description.lower()
        all_skills = set()
        
        # Start with existing skills (from job board parser)
        if existing_skills:
            all_skills.update(existing_skills)
        
        # Search description for skills from master list
        for skill in self.skill_list:
            skill_lower = skill.lower()
            
            # Word boundary matching to avoid false positives
            pattern = r'\b' + re.escape(skill_lower) + r'\b'
            
            if re.search(pattern, desc_lower):
                all_skills.add(skill)
        
        # Categorize all found skills
        categorized = {
            "technical": [],
            "soft": [],
            "tools": []
        }
        
        for skill in all_skills:
            category = self._categorize_skill(skill)
            categorized[category].append(skill)
        
        # Deduplicate within each category
        for category in categorized:
            categorized[category] = list(dict.fromkeys(categorized[category]))
        
        return categorized
    
    def parse_experience(self, description: str, experience_field: Optional[str]) -> Dict[str, Any]:
        """
        Parse experience requirements from text.
        
        Args:
            description: Job description
            experience_field: Dedicated experience field (if exists)
            
        Returns:
            Structured experience data
        """
        # Combine sources
        text = f"{experience_field or ''} {description}".lower()
        
        # Level keywords
        level_patterns = {
            "entry": r"\b(?:entry level|fresher|fresh graduate|0-1 years?|no experience)\b",
            "junior": r"\b(?:junior|1-2 years?|1-3 years?)\b",
            "mid": r"\b(?:mid[-\s]level|3-5 years?|4-6 years?|intermediate)\b",
            "senior": r"\b(?:senior|5\+ years?|6\+ years?|7\+ years?|experienced)\b",
            "lead": r"\b(?:lead|principal|architect|10\+ years?|expert)\b"
        }
        
        detected_level = "unknown"
        for level, pattern in level_patterns.items():
            if re.search(pattern, text):
                detected_level = level
                break
        
        # Parse year ranges
        min_years = 0
        max_years = None
        raw_text = None
        
        # Patterns for years
        year_patterns = [
            r"(\d+)\s*-\s*(\d+)\s*years?",  # "3-5 years"
            r"(\d+)\s+to\s+(\d+)\s*years?",  # "3 to 5 years"
            r"(\d+)\+\s*years?",  # "5+ years"
            r"minimum\s+(\d+)\s*years?",  # "minimum 5 years"
            r"at least\s+(\d+)\s*years?",  # "at least 3 years"
        ]
        
        for pattern in year_patterns:
            match = re.search(pattern, text)
            if match:
                raw_text = match.group(0)
                groups = match.groups()
                
                if len(groups) == 2:  # Range
                    min_years = int(groups[0])
                    max_years = int(groups[1])
                elif len(groups) == 1:  # Single or minimum
                    min_years = int(groups[0])
                    max_years = None  # Open-ended
                
                break
        
        return {
            "min_years": min_years,
            "max_years": max_years,
            "level": detected_level,
            "raw_text": raw_text
        }
    
    def normalize_salary(self, salary: Optional[str], location: str) -> Optional[Dict[str, Any]]:
        """
        Normalize salary to structured format.
        
        Args:
            salary: Raw salary string
            location: Job location (for currency detection)
            
        Returns:
            Normalized salary data or None
        """
        if not salary or salary.lower() in ["competitive", "negotiable", "not specified"]:
            return None
        
        # Detect currency
        currency = "PKR"  # Default for Pakistan
        if "$" in salary or "usd" in salary.lower():
            currency = "USD"
        elif "£" in salary or "gbp" in salary.lower():
            currency = "GBP"
        elif "€" in salary or "eur" in salary.lower():
            currency = "EUR"
        elif "rs" in salary.lower() or "pkr" in salary.lower():
            currency = "PKR"
        
        # Extract numbers
        # Handle formats: "80,000 - 120,000", "80k - 120k", "$1500-2000"
        numbers = re.findall(r'[\d,]+(?:\.\d+)?', salary)
        
        if not numbers:
            return None
        
        # Parse amounts
        amounts = []
        for num_str in numbers:
            # Remove commas
            num_str = num_str.replace(',', '')
            try:
                amount = float(num_str)
                
                # Handle k (thousands)
                if 'k' in salary.lower():
                    amount *= 1000
                
                amounts.append(int(amount))
            except ValueError:
                continue
        
        if not amounts:
            return None
        
        # Determine min/max
        min_amount = min(amounts)
        max_amount = max(amounts) if len(amounts) > 1 else None
        
        # Detect period
        period = "month"  # Default
        if any(keyword in salary.lower() for keyword in ["annual", "yearly", "per year", "p.a."]):
            period = "year"
        elif any(keyword in salary.lower() for keyword in ["monthly", "per month", "/month"]):
            period = "month"
        
        return {
            "currency": currency,
            "min": min_amount,
            "max": max_amount,
            "period": period,
            "raw": salary
        }
    
    def extract_education(self, description: str, education_field: Optional[str]) -> Optional[str]:
        """
        Extract education requirements from description.
        
        Args:
            description: Job description
            education_field: Dedicated education field (if exists)
            
        Returns:
            Education requirement string or None
        """
        # Combine sources
        text = f"{education_field or ''} {description}".lower()
        
        # Education patterns (ordered by priority)
        education_patterns = {
            "PhD": r"\b(?:ph\.?d\.?|doctorate|doctoral degree)\b",
            "Master's": r"\b(?:master'?s?|m\.?s\.?|msc|mba|graduate degree)\b",
            "Bachelor's": r"\b(?:bachelor'?s?|b\.?s\.?|b\.?sc\.?|b\.?eng\.?|undergraduate degree|4-year degree)\b",
            "Associate": r"\b(?:associate'?s? degree|2-year degree)\b",
            "High School": r"\b(?:high school|secondary school|diploma)\b"
        }
        
        for education, pattern in education_patterns.items():
            if re.search(pattern, text):
                return education
        
        return None
    
    def extract_job_type(self, description: str, employment_type: Optional[str]) -> Optional[str]:
        """
        Extract job type from description.
        
        Args:
            description: Job description
            employment_type: Dedicated employment_type field (if exists)
            
        Returns:
            Job type string or None
        """
        # Combine sources
        text = f"{employment_type or ''} {description}".lower()
        
        # Job type patterns (ordered by priority)
        job_type_patterns = {
            "Internship": r"\b(?:intern|internship|intern position)\b",
            "Contract": r"\b(?:contract|contractor|contractual|temporary|temp)\b",
            "Part-time": r"\b(?:part-time|part time|parttime)\b",
            "Full-time": r"\b(?:full-time|full time|fulltime|permanent)\b"
        }
        
        for job_type, pattern in job_type_patterns.items():
            if re.search(pattern, text):
                return job_type
        
        # Default to Full-time if no match found (most common)
        return "Full-time"
    
    def enrich_job(self, job: Dict[str, Any]) -> Tuple[Dict[str, Any], float]:
        """
        Enrich single job with all transformations.
        
        Args:
            job: Raw JobData dictionary
            
        Returns:
            Tuple of (enriched job, confidence score)
        """
        enriched = job.copy()
        confidence = 0.5  # Base score
        
        try:
            # Clean description
            description_result = self.clean_description(
                job.get("description", ""),
                job.get("raw_html", "")
            )
            enriched["description_sections"] = description_result["sections"]
            enriched["description"] = description_result["full_text"]  # Update with cleaned version
            
            if description_result["word_count"] > 100:
                confidence += 0.1
            if len(description_result["sections"]) > 1:
                confidence += 0.2
            
            # Extract skills (preserve existing + search for more)
            skills_result = self.extract_skills(
                description_result["full_text"],
                job.get("title", ""),
                existing_skills=job.get("skills", [])  # Pass existing skills from parser
            )
            enriched["skills_categorized"] = skills_result
            
            # Flatten for backward compatibility
            all_skills = []
            for category in skills_result.values():
                all_skills.extend(category)
            enriched["skills"] = list(dict.fromkeys(all_skills))  # Deduplicate
            
            if len(enriched["skills"]) >= 3:
                confidence += 0.1
            if len(enriched["skills"]) >= 7:
                confidence += 0.1
            
            # Parse experience
            experience_result = self.parse_experience(
                description_result["full_text"],
                job.get("experience_required")
            )
            enriched["experience_parsed"] = experience_result
            
            if experience_result["min_years"] > 0 or experience_result["level"] != "unknown":
                confidence += 0.1
            
            # Normalize salary
            salary_result = self.normalize_salary(
                job.get("salary"),
                job.get("location", "")
            )
            enriched["salary_normalized"] = salary_result
            
            if salary_result:
                confidence += 0.1
            
            # Extract education requirement
            education = self.extract_education(
                description_result["full_text"],
                job.get("education_required")
            )
            if education:
                enriched["education_required"] = education
                confidence += 0.05
            
            # Extract job type
            job_type = self.extract_job_type(
                description_result["full_text"],
                job.get("employment_type")
            )
            if job_type:
                enriched["employment_type"] = job_type
                confidence += 0.05
            
            # Add metadata
            enriched["enrichment_confidence"] = min(confidence, 1.0)
            enriched["enrichment_timestamp"] = datetime.utcnow().isoformat()
            
        except Exception as e:
            print(f"Enrichment error for job {job.get('job_id', 'unknown')}: {e}")
            enriched["enrichment_confidence"] = 0.3
            enriched["enrichment_timestamp"] = datetime.utcnow().isoformat()
        
        return enriched, enriched["enrichment_confidence"]
    
    def enrich_batch(self, jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Enrich multiple jobs.
        
        Args:
            jobs: List of raw JobData dictionaries
            
        Returns:
            List of enriched jobs
        """
        enriched_jobs = []
        total_confidence = 0.0
        
        print(f"\nEnriching {len(jobs)} jobs...")
        
        for i, job in enumerate(jobs, 1):
            enriched, confidence = self.enrich_job(job)
            enriched_jobs.append(enriched)
            total_confidence += confidence
            
            print(f"   Job {i}/{len(jobs)}: {job.get('title', 'Unknown')} (confidence: {confidence:.2f})")
        
        avg_confidence = total_confidence / len(jobs) if jobs else 0
        print(f"\nEnrichment complete. Average confidence: {avg_confidence:.2f}\n")
        
        return enriched_jobs


# Global enricher instance
_enricher: Optional[JobEnricher] = None


def get_enricher() -> JobEnricher:
    """
    Get or create global enricher instance.

    Returns:
        JobEnricher instance

    Raises:
        FileNotFoundError: If EXCEL_SKILL_GAP path does not exist.
    """
    global _enricher
    if _enricher is None:
        from core.settings import get_settings

        settings = get_settings()
        configured = settings.excel_skill_gap
        configured_path = Path(configured)
        if configured_path.is_absolute():
            skill_path = configured_path
        else:
            skill_path = Path(__file__).resolve().parent.parent / configured_path

        _enricher = JobEnricher(skill_list_path=str(skill_path))
    return _enricher
