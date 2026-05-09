"""
Redis service for job queue management with deduplication.

Handles job enqueueing, dequeueing, and tracking processed jobs to prevent duplicates.
"""

import json
import hashlib
from typing import Dict, List, Optional
from redis import Redis
from redis.exceptions import RedisError, ConnectionError
from core.settings import get_settings


class RedisService:
    """Redis-based job queue with deduplication support."""
    
    def __init__(self):
        """Initialize Redis connection."""
        self.settings = get_settings()
        self.client: Optional[Redis] = None
        self._connect()
    
    def _connect(self) -> None:
        """Establish Redis connection with retry logic."""
        for attempt in range(self.settings.redis_max_retries):
            try:
                self.client = Redis.from_url(
                    self.settings.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_keepalive=True
                )
                # Test connection
                self.client.ping()
                print(f"Redis connected: {self.settings.redis_url}")
                return
            except (RedisError, ConnectionError) as e:
                if attempt == self.settings.redis_max_retries - 1:
                    print(f"Redis connection failed after {self.settings.redis_max_retries} attempts: {e}")
                    raise
                print(f"Redis connection attempt {attempt + 1} failed, retrying...")
    
    def _get_queue_key(self) -> str:
        """Get Redis key for job queue."""
        return f"{self.settings.redis_job_queue_prefix}:queue"
    
    def _get_processed_key(self) -> str:
        """Get Redis key for processed jobs set."""
        return f"{self.settings.redis_job_queue_prefix}:processed"
    
    def _generate_job_id(self, job_data: Dict) -> str:
        """
        Generate unique job ID from job data.
        
        Args:
            job_data: Job dictionary with title, company, location
            
        Returns:
            SHA256 hash (16 chars)
        """
        # Create deterministic string from key fields
        id_string = f"{job_data.get('title', '')}|{job_data.get('company', '')}|{job_data.get('location', '')}"
        return hashlib.sha256(id_string.encode()).hexdigest()[:16]
    
    def is_job_processed(self, job_id: str) -> bool:
        """
        Check if job has already been processed.
        
        Args:
            job_id: Unique job identifier
            
        Returns:
            True if job was previously processed
        """
        try:
            return self.client.sismember(self._get_processed_key(), job_id)
        except RedisError as e:
            print(f"Redis error checking processed job: {e}")
            return False
    
    def enqueue_job(self, job_data: Dict) -> bool:
        """
        Add job to queue if not already processed.
        
        Args:
            job_data: Job dictionary to enqueue
            
        Returns:
            True if job was enqueued, False if duplicate
        """
        try:
            job_id = job_data.get('job_id')
            if not job_id:
                job_id = self._generate_job_id(job_data)
                job_data['job_id'] = job_id
            
            # Check if already processed
            if self.is_job_processed(job_id):
                return False
            
            # Add to queue
            job_json = json.dumps(job_data)
            self.client.rpush(self._get_queue_key(), job_json)
            return True
            
        except (RedisError, json.JSONDecodeError) as e:
            print(f"Failed to enqueue job: {e}")
            return False
    
    def enqueue_jobs_batch(self, jobs: List[Dict]) -> int:
        """
        Enqueue multiple jobs in a batch.
        
        Args:
            jobs: List of job dictionaries
            
        Returns:
            Number of jobs successfully enqueued
        """
        enqueued_count = 0
        
        try:
            pipeline = self.client.pipeline()
            processed_set = self._get_processed_key()
            queue_key = self._get_queue_key()
            
            for job_data in jobs:
                job_id = job_data.get('job_id')
                if not job_id:
                    job_id = self._generate_job_id(job_data)
                    job_data['job_id'] = job_id
                
                # Check if processed (outside pipeline for efficiency)
                if not self.is_job_processed(job_id):
                    job_json = json.dumps(job_data)
                    pipeline.rpush(queue_key, job_json)
                    enqueued_count += 1
            
            pipeline.execute()
            return enqueued_count
            
        except (RedisError, json.JSONDecodeError) as e:
            print(f"Batch enqueue failed: {e}")
            return 0
    
    def dequeue_job(self, timeout: int = 0) -> Optional[Dict]:
        """
        Remove and return job from queue.
        
        Args:
            timeout: Block for N seconds if queue empty (0 = non-blocking)
            
        Returns:
            Job dictionary or None if queue empty
        """
        try:
            if timeout > 0:
                result = self.client.blpop(self._get_queue_key(), timeout=timeout)
                if result:
                    _, job_json = result
                    return json.loads(job_json)
            else:
                job_json = self.client.lpop(self._get_queue_key())
                if job_json:
                    return json.loads(job_json)
            return None
            
        except (RedisError, json.JSONDecodeError) as e:
            print(f"Failed to dequeue job: {e}")
            return None
    
    def mark_job_processed(self, job_id: str) -> bool:
        """
        Mark job as processed with TTL.
        
        Args:
            job_id: Unique job identifier
            
        Returns:
            True if marked successfully
        """
        try:
            processed_key = self._get_processed_key()
            self.client.sadd(processed_key, job_id)
            # Set TTL on the set (refresh on each add)
            self.client.expire(processed_key, self.settings.redis_processed_ttl)
            return True
        except RedisError as e:
            print(f"Failed to mark job as processed: {e}")
            return False
    
    def get_queue_length(self) -> int:
        """
        Get number of jobs in queue.
        
        Returns:
            Queue length
        """
        try:
            return self.client.llen(self._get_queue_key())
        except RedisError as e:
            print(f"Failed to get queue length: {e}")
            return 0
    
    def get_processed_count(self) -> int:
        """
        Get number of processed jobs.
        
        Returns:
            Processed job count
        """
        try:
            return self.client.scard(self._get_processed_key())
        except RedisError as e:
            print(f"Failed to get processed count: {e}")
            return 0
    
    def clear_queue(self) -> bool:
        """
        Clear all jobs from queue (use with caution).
        
        Returns:
            True if cleared successfully
        """
        try:
            self.client.delete(self._get_queue_key())
            return True
        except RedisError as e:
            print(f"Failed to clear queue: {e}")
            return False
    
    def get_stats(self) -> Dict:
        """
        Get queue statistics.
        
        Returns:
            Dictionary with queue_length and processed_count
        """
        return {
            "queue_length": self.get_queue_length(),
            "processed_count": self.get_processed_count()
        }
    
    def close(self) -> None:
        """Close Redis connection."""
        if self.client:
            self.client.close()
            print("Redis connection closed")

    # ==================== Vetting Stream Support ====================

    def _vetting_key(self, user_id: str, suffix: str) -> str:
        return f"vetting:{user_id}:{suffix}"

    def push_vetted_job(self, user_id: str, job: dict) -> bool:
        """Append a vetted job JSON to the user's Redis list."""
        try:
            key = self._vetting_key(user_id, "jobs")
            self.client.rpush(key, json.dumps(job))
            self.client.expire(key, 3600)  # 1-hour TTL on the whole list
            return True
        except (RedisError, json.JSONDecodeError) as e:
            print(f"push_vetted_job failed: {e}")
            return False

    def get_vetted_jobs(self, user_id: str, since: int = 0) -> list:
        """Return vetted jobs from index `since` onwards (inclusive)."""
        try:
            key = self._vetting_key(user_id, "jobs")
            raw = self.client.lrange(key, since, -1)
            return [json.loads(r) for r in raw]
        except (RedisError, json.JSONDecodeError) as e:
            print(f"get_vetted_jobs failed: {e}")
            return []

    def get_vetted_job_count(self, user_id: str) -> int:
        """Return total number of vetted jobs currently stored."""
        try:
            return self.client.llen(self._vetting_key(user_id, "jobs"))
        except RedisError:
            return 0

    def add_seen_job(self, user_id: str, job_id: str) -> None:
        """Mark a job as seen so it won't be processed again this session."""
        try:
            key = self._vetting_key(user_id, "seen")
            self.client.sadd(key, job_id)
            self.client.expire(key, 3600)
        except RedisError as e:
            print(f"add_seen_job failed: {e}")

    def is_job_seen(self, user_id: str, job_id: str) -> bool:
        """Check if a job was already processed in this session."""
        try:
            return bool(self.client.sismember(self._vetting_key(user_id, "seen"), job_id))
        except RedisError:
            return False

    def set_vetting_status(self, user_id: str, status: str) -> None:
        """Set the vetting pipeline status: 'processing' | 'done' | 'idle'."""
        try:
            key = self._vetting_key(user_id, "status")
            self.client.set(key, status, ex=3600)
        except RedisError as e:
            print(f"set_vetting_status failed: {e}")

    def get_vetting_status(self, user_id: str) -> str:
        """Return current vetting status string, or 'idle' if not set."""
        try:
            val = self.client.get(self._vetting_key(user_id, "status"))
            return val if val else "idle"
        except RedisError:
            return "idle"

    def update_last_poll(self, user_id: str) -> None:
        """Record the current timestamp as the last poll time (for TTL logic)."""
        try:
            import time
            key = self._vetting_key(user_id, "last_poll")
            self.client.set(key, str(time.time()), ex=120)
        except RedisError as e:
            print(f"update_last_poll failed: {e}")

    def get_last_poll(self, user_id: str) -> float:
        """Return timestamp of last poll, or 0.0 if never polled."""
        try:
            val = self.client.get(self._vetting_key(user_id, "last_poll"))
            return float(val) if val else 0.0
        except (RedisError, ValueError):
            return 0.0

    def clear_vetting_session(self, user_id: str) -> None:
        """Delete all vetting state for a user (call before starting a new session)."""
        try:
            keys = [
                self._vetting_key(user_id, "jobs"),
                self._vetting_key(user_id, "seen"),
                self._vetting_key(user_id, "status"),
                self._vetting_key(user_id, "last_poll"),
            ]
            self.client.delete(*keys)
        except RedisError as e:
            print(f"clear_vetting_session failed: {e}")


# Global service instance
_redis_service: Optional[RedisService] = None


def get_redis_service() -> RedisService:
    """
    Get or create global Redis service instance.
    
    Returns:
        RedisService instance
    """
    global _redis_service
    if _redis_service is None:
        _redis_service = RedisService()
    return _redis_service
