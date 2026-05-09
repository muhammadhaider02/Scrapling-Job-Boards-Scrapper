"""Job board parsers for LinkedIn, Rozee, Indeed, Mustakbil."""

from .base import BaseJobParser
from .linkedin import LinkedInParser, parse_linkedin_job
from .rozee import RozeeParser, parse_rozee_job
from .indeed import IndeedParser, parse_indeed_job
from .mustakbil import MustakbilParser, parse_mustakbil_job

__all__ = [
    "BaseJobParser",
    "LinkedInParser",
    "RozeeParser",
    "IndeedParser",
    "MustakbilParser",
    "parse_linkedin_job",
    "parse_rozee_job",
    "parse_indeed_job",
    "parse_mustakbil_job",
]
