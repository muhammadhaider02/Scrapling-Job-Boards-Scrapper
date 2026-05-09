"""
Supabase service for database operations.

Handles CRUD operations for jobs, user profiles, applications, and other database entities.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import json
from supabase import create_client, Client
from postgrest.exceptions import APIError
from core.settings import get_settings
from core.role_filters import filter_allowed_roles


class SupabaseService:
    """Supabase database operations wrapper."""
    
    def __init__(self):
        """Initialize Supabase client."""
        self.settings = get_settings()
        self.client: Optional[Client] = None
        self._connect()
    
    def _connect(self) -> None:
        """Establish Supabase connection."""
        try:
            self.client = create_client(
                self.settings.supabase_url,
                self.settings.supabase_service_role_key
            )
            print(f"Supabase connected: {self.settings.supabase_url}")
        except Exception as e:
            print(f"Supabase connection failed: {e}")
            raise

    def reconnect(self) -> None:
        """Force a fresh Supabase connection. Call after long-running operations
        (e.g. LLM calls) to avoid stale HTTP/2 connection errors."""
        print("Reconnecting Supabase client...")
        # Explicitly close the old httpx session so the stale HTTP/2 transport
        # is torn down before we create a fresh client.
        try:
            if self.client and hasattr(self.client, 'postgrest') and hasattr(self.client.postgrest, 'session'):
                self.client.postgrest.session.close()
        except Exception:
            pass  # Best-effort close — don't let cleanup errors block reconnect
        self._connect()
    
    # ==================== User Profile Operations ====================
    
    def get_user_profile(self, user_id: str) -> Optional[Dict]:
        """
        Get user profile with skills and quiz scores.
        
        Args:
            user_id: UUID of user
            
        Returns:
            User profile dictionary or None
        """
        try:
            response = self.client.table("user_profiles").select("*").eq("user_id", user_id).execute()
            
            if response.data:
                profile = response.data[0]
                
                # Fetch quiz scores
                quiz_response = self.client.table("user_quiz_scores").select("*").eq("user_id", user_id).execute()
                profile['quiz_scores'] = quiz_response.data if quiz_response.data else []
                
                return profile
            return None
            
        except APIError as e:
            print(f"Failed to get user profile: {e}")
            return None
    
    def upsert_user_profile(self, user_id: str, profile_data: Dict) -> bool:
        """
        Insert or update user profile.
        
        Args:
            user_id: UUID of user
            profile_data: Dictionary containing profile fields
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Prepare profile record
            profile_record = {
                'user_id': user_id,
                'name': profile_data.get('name'),
                'email': profile_data.get('email'),
                'phone': profile_data.get('phone'),
                'location': profile_data.get('location'),
                'summary': profile_data.get('summary'),
                'github': profile_data.get('github'),
                'linkedin': profile_data.get('linkedin'),
                'portfolio': profile_data.get('portfolio'),
                'profile_picture_url': profile_data.get('profile_picture_url'),
                'skills': profile_data.get('skills', []),
                'previous_roles': profile_data.get('previous_roles', []),
                'years_of_experience': profile_data.get('years_of_experience', 0),
                'projects': profile_data.get('projects', []),
                'certificates': profile_data.get('certificates', []),
                'education': profile_data.get('education', []),
                'experience': profile_data.get('experience', []),
                'recommended_roles': profile_data.get('recommended_roles', []),
                'updated_at': datetime.utcnow().isoformat()
            }
            
            # Upsert (insert or update on conflict with user_id)
            response = self.client.table("user_profiles").upsert(
                profile_record,
                on_conflict='user_id'
            ).execute()
            
            print(f"Saved user profile for user_id: {user_id}")
            return True
            
        except APIError as e:
            print(f"Failed to upsert user profile: {e}")
            return False
    
    # ==================== Job Operations ====================
    
    def bulk_insert_jobs(self, jobs: List[Dict]) -> int:
        """
        Insert multiple jobs with upsert on conflict.
        
        Args:
            jobs: List of job dictionaries
            
        Returns:
            Number of jobs inserted/updated
        """
        if not jobs:
            return 0
        
        try:
            # Prepare jobs for insertion (map from JobData to database schema)
            job_records = []
            for job in jobs:
                # Extract experience as integer (min_years from parsed data or fallback)
                experience_int = None
                if job.get('experience_parsed') and job['experience_parsed'].get('min_years'):
                    experience_int = job['experience_parsed']['min_years']
                elif job.get('experience_required'):
                    # Try to extract number from text
                    import re
                    match = re.search(r'(\d+)', str(job.get('experience_required', '')))
                    if match:
                        experience_int = int(match.group(1))
                
                date_scrapped = job.get('date_scrapped') or datetime.utcnow().isoformat()

                record = {
                    'job_id': job['job_id'],
                    'job_title': job.get('title', ''),
                    'job_description': job.get('description', ''),
                    'skills_required': job.get('skills', []),
                    'experience_required': experience_int,  # INTEGER
                    'education_required': job.get('education_required'),
                    'job_type': job.get('employment_type', ''),
                    'location': job.get('location', ''),
                    'industry': job.get('industry'),
                    'company': job.get('company', ''),
                    'url': job.get('job_url', ''),
                    'job_source': job.get('job_source') or job.get('board', ''),
                    'date_scrapped': date_scrapped,
                }
                job_records.append(record)
            
            # Upsert (insert or update on conflict)
            response = self.client.table("jobs").upsert(
                job_records,
                on_conflict='job_id',
                returning='minimal'
            ).execute()
            
            print(f"Inserted/updated {len(job_records)} jobs to Supabase")
            return len(job_records)
            
        except APIError as e:
            print(f"Failed to bulk insert jobs: {e}")
            return 0

    def delete_stale_jobs(self, days: int = 7) -> int:
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        try:
            response = (
                self.client.table("jobs")
                .delete()
                .lt("date_scrapped", cutoff)
                .execute()
            )
            deleted = len(response.data) if response.data else 0
            print(f"Deleted {deleted} stale jobs older than {days} days")
            return deleted
        except APIError as e:
            print(f"Failed to delete stale jobs: {e}")
            return 0

    def get_job_by_id(self, job_id: str) -> Optional[Dict]:
        """
        Get job by ID.
        
        Args:
            job_id: Unique job identifier
            
        Returns:
            Job dictionary or None
        """
        try:
            response = self.client.table("jobs").select("*").eq("job_id", job_id).execute()
            return response.data[0] if response.data else None
        except APIError as e:
            print(f"Failed to get job: {e}")
            return None

    def save_resume_version(
        self,
        user_id: str,
        original_json: Dict[str, Any],
        optimized_json: Dict[str, Any],
        job_id: Optional[str] = None,
        job_title: Optional[str] = None,
        optimization_metadata: Optional[Dict[str, Any]] = None,
        is_base_version: bool = False,
        sections_optimized: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Persist one resume version to public.resumes."""
        try:
            existing = (
                self.client.table("resumes")
                .select("version")
                .eq("user_id", user_id)
                .order("version", desc=True)
                .limit(1)
                .execute()
            )

            next_version = 1
            if existing.data:
                next_version = int(existing.data[0].get("version", 0)) + 1

            resume_record = {
                "user_id": user_id,
                "original_json": original_json,
                "optimized_json": optimized_json,
                "job_id": job_id,
                "job_title": job_title,
                "optimization_metadata": optimization_metadata or {},
                "version": next_version,
                "is_base_version": is_base_version,
                "sections_optimized": sections_optimized or [],
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            }

            insert_result = self.client.table("resumes").insert(resume_record).execute()
            if not insert_result.data:
                return None

            created = insert_result.data[0]
            return {
                "id": created.get("id"),
                "version": created.get("version", next_version),
            }
        except APIError as e:
            print(f"Failed to save resume version for user {user_id}: {e}")
            return None
    
    def search_jobs(
        self, 
        skills: Optional[List[str]] = None,
        location: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """
        Search jobs by criteria.
        
        Args:
            skills: List of required skills
            location: Job location
            limit: Maximum results
            
        Returns:
            List of matching jobs
        """
        try:
            query = self.client.table("jobs").select("*")
            
            if skills:
                # Use Postgres array contains operator
                query = query.contains("skills_required", skills)
            
            if location:
                query = query.ilike("location", f"%{location}%")
            
            response = query.limit(limit).order("scraped_at", desc=True).execute()
            return response.data if response.data else []
            
        except APIError as e:
            print(f"Failed to search jobs: {e}")
            return []

    def get_jobs_for_roles(
        self,
        roles: List[str],
        offset: int = 0,
        limit: int = 50,
    ) -> List[Dict]:
        """
        Fetch a paginated batch of jobs whose title matches any of the given roles.

        Uses ILIKE pattern matching on job_title for each role (OR-combined).
        Results are ordered by job_id for stable cursor-based pagination.

        Args:
            roles: List of role names, e.g. ["Backend Developer", "Python Engineer"]
            offset: Number of rows to skip (pagination cursor)
            limit: Maximum rows to return

        Returns:
            List of job dicts from the DB
        """
        if not roles:
            return []

        allowed_roles = filter_allowed_roles(roles, self.settings.permitted_roles)
        if not allowed_roles:
            print("Requested roles are outside configured allowlist")
            return []

        try:
            query = self.client.table("jobs").select("*")

            # Build OR filter: job_title ILIKE '%Role1%' OR job_title ILIKE '%Role2%' ...
            ilike_clauses = ",".join(
                f"job_title.ilike.%{role.strip()}%" for role in allowed_roles
            )
            query = query.or_(ilike_clauses)

            response = (
                query
                .order("job_id")
                .range(offset, offset + limit - 1)
                .execute()
            )
            return response.data if response.data else []

        except APIError as e:
            print(f"Failed to get_jobs_for_roles: {e}")
            return []

    
    # ==================== Application Operations ====================
    
    def create_application(
        self,
        user_id: str,
        job_id: str,
        reasoning_note: str,
        optimized_resume_url: Optional[str] = None,
        optimized_cover_letter: Optional[str] = None
    ) -> Optional[int]:
        """
        Create job application record.
        
        Args:
            user_id: User UUID
            job_id: Job identifier
            reasoning_note: Vetting officer's reasoning
            optimized_resume_url: Path to tailored resume
            optimized_cover_letter: Cover letter text
            
        Returns:
            Application ID or None
        """
        try:
            application = {
                'user_id': user_id,
                'job_id': job_id,
                'status': 'pending',
                'reasoning_note': reasoning_note,
                'optimized_resume_url': optimized_resume_url,
                'optimized_cover_letter': optimized_cover_letter,
                'created_at': datetime.utcnow().isoformat()
            }
            
            response = self.client.table("job_applications").insert(application).execute()
            
            if response.data:
                app_id = response.data[0]['id']
                print(f"Created application #{app_id} for job {job_id}")
                return app_id
            return None
            
        except APIError as e:
            print(f"Failed to create application: {e}")
            return None
    
    def update_application_status(
        self,
        application_id: int,
        status: str,
        applied_at: Optional[datetime] = None
    ) -> bool:
        """
        Update application status.
        
        Args:
            application_id: Application record ID
            status: New status ('pending', 'approved', 'applied', 'rejected', 'error')
            applied_at: Timestamp when applied
            
        Returns:
            True if updated successfully
        """
        try:
            update_data = {
                'status': status,
                'updated_at': datetime.utcnow().isoformat()
            }
            
            if applied_at:
                update_data['applied_at'] = applied_at.isoformat()
            
            self.client.table("job_applications").update(update_data).eq("id", application_id).execute()
            print(f"Updated application #{application_id} status to '{status}'")
            return True
            
        except APIError as e:
            print(f"Failed to update application status: {e}")
            return False
    
    def get_user_applications(self, user_id: str, limit: int = 50) -> List[Dict]:
        """
        Get user's job applications.
        
        Args:
            user_id: User UUID
            limit: Maximum results
            
        Returns:
            List of applications with job details
        """
        try:
            response = (
                self.client.table("job_applications")
                .select("*, jobs(*)")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            return response.data if response.data else []
        except APIError as e:
            print(f"Failed to get user applications: {e}")
            return []

    def get_application_by_id(self, application_id: int) -> Optional[Dict]:
        """Get one application by primary key."""
        try:
            response = (
                self.client.table("job_applications")
                .select("*")
                .eq("id", application_id)
                .limit(1)
                .execute()
            )
            return response.data[0] if response.data else None
        except APIError as e:
            print(f"Failed to get application #{application_id}: {e}")
            return None

    def save_application_materials_draft(
        self,
        application_id: int,
        optimized_resume: Optional[Dict[str, Any]],
        optimized_cover_letter: Optional[str],
        template_name: Optional[str] = None,
    ) -> bool:
        """
        Persist edited application materials as a draft.

        The current schema stores a resume URL field. For draft support without
        schema changes, we serialize the edited resume JSON into that field.
        """
        try:
            update_data: Dict[str, Any] = {
                "status": "draft",
                "updated_at": datetime.utcnow().isoformat(),
            }

            if optimized_resume is not None:
                update_data["optimized_resume_url"] = json.dumps(optimized_resume)

            if optimized_cover_letter is not None:
                update_data["optimized_cover_letter"] = optimized_cover_letter

            if template_name:
                existing = self.get_application_by_id(application_id)
                existing_note = (existing or {}).get("reasoning_note") or ""
                template_note = f"Template: {template_name}"
                if template_note not in existing_note:
                    merged_note = f"{existing_note}\n{template_note}".strip()
                    update_data["reasoning_note"] = merged_note

            self.client.table("job_applications").update(update_data).eq("id", application_id).execute()
            print(f"Saved draft materials for application #{application_id}")
            return True

        except APIError as e:
            print(f"Failed to save draft materials for application #{application_id}: {e}")
            return False
    
    # ==================== Error Logging ====================
    
    def log_scraping_error(self, url: str, error: str, retries: int = 0) -> bool:
        """
        Log scraping error for debugging.
        
        Args:
            url: URL that failed
            error: Error message
            retries: Number of retry attempts
            
        Returns:
            True if logged successfully
        """
        try:
            # This assumes you have a scraping_errors table (optional)
            error_record = {
                'url': url,
                'error_message': error,
                'retries': retries,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # Try to insert, but don't fail if table doesn't exist
            try:
                self.client.table("scraping_errors").insert(error_record).execute()
            except Exception:
                pass
            
            print(f"Logged scraping error: {url[:50]}...")
            return True
            
        except Exception as e:
            print(f"Failed to log scraping error: {e}")
            return False


# Global service instance
_supabase_service: Optional[SupabaseService] = None


def get_supabase_service() -> SupabaseService:
    """
    Get or create global Supabase service instance.
    
    Returns:
        SupabaseService instance
    """
    global _supabase_service
    if _supabase_service is None:
        _supabase_service = SupabaseService()
    return _supabase_service
