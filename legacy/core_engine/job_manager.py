#!/usr/bin/env python3
"""
Job Manager for EUCLID-CORE / PYTHIA
Handles job lifecycle: creation, search, submission, sharing, and acceptance.
Persists to SQLite for durability across restarts.
"""

import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from enum import Enum


class JobStatus(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    SHARED = "shared"
    ACCEPTED = "accepted"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class Job:
    """Job data model"""
    def __init__(
        self,
        job_id: str,
        name: str,
        description: str,
        payload: Dict[str, Any],
        status: JobStatus = JobStatus.DRAFT,
        created_at: Optional[str] = None,
        owner_id: str = "system",
        shared_with: Optional[List[str]] = None,
        accepted_by: Optional[str] = None,
    ):
        self.job_id = job_id
        self.name = name
        self.description = description
        self.payload = payload
        self.status = status
        self.created_at = created_at or datetime.utcnow().isoformat()
        self.owner_id = owner_id
        self.shared_with = shared_with or []
        self.accepted_by = accepted_by

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "name": self.name,
            "description": self.description,
            "payload": self.payload,
            "status": self.status.value,
            "created_at": self.created_at,
            "owner_id": self.owner_id,
            "shared_with": self.shared_with,
            "accepted_by": self.accepted_by,
        }


class JobManager:
    """Manages job persistence and operations."""

    def __init__(self, db_path: str = "/app/data/jobs.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize SQLite database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    payload TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    owner_id TEXT NOT NULL,
                    shared_with TEXT,
                    accepted_by TEXT,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS job_events (
                    event_id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    actor_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    details TEXT,
                    FOREIGN KEY (job_id) REFERENCES jobs (job_id)
                )
                """
            )
            conn.commit()

    def create_job(
        self,
        name: str,
        description: str,
        payload: Dict[str, Any],
        owner_id: str = "system",
    ) -> Job:
        """Create a new job in DRAFT status."""
        job_id = str(uuid.uuid4())
        job = Job(
            job_id=job_id,
            name=name,
            description=description,
            payload=payload,
            status=JobStatus.DRAFT,
            owner_id=owner_id,
        )
        self._save_job(job)
        self._log_event(job_id, "created", owner_id, {"name": name})
        return job

    def submit_job(self, job_id: str, submitter_id: str = "system") -> Optional[Job]:
        """Submit a job, transitioning from DRAFT → SUBMITTED."""
        job = self.get_job(job_id)
        if not job:
            return None
        if job.status != JobStatus.DRAFT:
            raise ValueError(f"Cannot submit job in {job.status} status")

        job.status = JobStatus.SUBMITTED
        self._save_job(job)
        self._log_event(job_id, "submitted", submitter_id, {})
        return job

    def share_job(self, job_id: str, share_with: List[str], sharer_id: str = "system") -> Optional[Job]:
        """Share a job with other users, transitioning to SHARED status."""
        job = self.get_job(job_id)
        if not job:
            return None
        if job.status not in (JobStatus.DRAFT, JobStatus.SUBMITTED):
            raise ValueError(f"Cannot share job in {job.status} status")

        job.shared_with = list(set(job.shared_with + share_with))
        job.status = JobStatus.SHARED
        self._save_job(job)
        self._log_event(job_id, "shared", sharer_id, {"shared_with": share_with})
        return job

    def accept_job(self, job_id: str, acceptor_id: str = "system") -> Optional[Job]:
        """Accept a job, transitioning to ACCEPTED status."""
        job = self.get_job(job_id)
        if not job:
            return None
        if job.status not in (JobStatus.SHARED, JobStatus.SUBMITTED):
            raise ValueError(f"Cannot accept job in {job.status} status")

        job.accepted_by = acceptor_id
        job.status = JobStatus.ACCEPTED
        self._save_job(job)
        self._log_event(job_id, "accepted", acceptor_id, {})
        return job

    def get_job(self, job_id: str) -> Optional[Job]:
        """Retrieve a job by ID."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT name, description, payload, status, created_at, owner_id, shared_with, accepted_by FROM jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()

        if not row:
            return None

        name, description, payload_json, status, created_at, owner_id, shared_with, accepted_by = row
        return Job(
            job_id=job_id,
            name=name,
            description=description,
            payload=json.loads(payload_json),
            status=JobStatus(status),
            created_at=created_at,
            owner_id=owner_id,
            shared_with=json.loads(shared_with) if shared_with else [],
            accepted_by=accepted_by,
        )

    def search_jobs(self, query: str = "", status: Optional[str] = None, owner_id: Optional[str] = None) -> List[Job]:
        """Search jobs by name/description, optionally filtering by status or owner."""
        with sqlite3.connect(self.db_path) as conn:
            sql = "SELECT job_id, name, description, payload, status, created_at, owner_id, shared_with, accepted_by FROM jobs WHERE 1=1"
            params = []

            if query:
                sql += " AND (name LIKE ? OR description LIKE ?)"
                params.extend([f"%{query}%", f"%{query}%"])

            if status:
                sql += " AND status = ?"
                params.append(status)

            if owner_id:
                sql += " AND owner_id = ?"
                params.append(owner_id)

            sql += " ORDER BY created_at DESC"

            rows = conn.execute(sql, params).fetchall()

        jobs = []
        for row in rows:
            job_id, name, description, payload_json, status, created_at, owner_id, shared_with, accepted_by = row
            job = Job(
                job_id=job_id,
                name=name,
                description=description,
                payload=json.loads(payload_json),
                status=JobStatus(status),
                created_at=created_at,
                owner_id=owner_id,
                shared_with=json.loads(shared_with) if shared_with else [],
                accepted_by=accepted_by,
            )
            jobs.append(job)

        return jobs

    def list_jobs(self, limit: int = 50, offset: int = 0) -> List[Job]:
        """List all jobs with pagination."""
        return self.search_jobs()[:limit]

    def _save_job(self, job: Job):
        """Persist a job to the database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO jobs
                (job_id, name, description, payload, status, created_at, owner_id, shared_with, accepted_by, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job.job_id,
                    job.name,
                    job.description,
                    json.dumps(job.payload),
                    job.status.value,
                    job.created_at,
                    job.owner_id,
                    json.dumps(job.shared_with),
                    job.accepted_by,
                    datetime.utcnow().isoformat(),
                ),
            )
            conn.commit()

    def _log_event(self, job_id: str, event_type: str, actor_id: str, details: Dict[str, Any]):
        """Log a job event for audit trail."""
        event_id = str(uuid.uuid4())
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO job_events (event_id, job_id, event_type, actor_id, timestamp, details)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    job_id,
                    event_type,
                    actor_id,
                    datetime.utcnow().isoformat(),
                    json.dumps(details),
                ),
            )
            conn.commit()


# Global instance
_job_manager: Optional[JobManager] = None


def get_job_manager() -> JobManager:
    """Get or create the global job manager instance."""
    global _job_manager
    if _job_manager is None:
        _job_manager = JobManager()
    return _job_manager
