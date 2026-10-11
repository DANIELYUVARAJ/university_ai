# backend/pipeline/worker.py
"""
Asynchronous pipeline worker architecture for Phase 11.
Provides in-process background queuing and safe retry recovery without external dependencies.
Interfaces designed to allow pluggable distributed queues (Redis, Celery, RabbitMQ).
"""

from __future__ import annotations
import asyncio
import uuid
import logging
from typing import Dict, List, Optional
from datetime import datetime

from config import settings
from .schemas import PipelineValidateRequest
from .jobs import PipelineJob, JobState
from .pipeline_service import PipelineService, generate_pipeline_id, generate_execution_id

logger = logging.getLogger("datashield.worker")


class PipelineQueue:
    def __init__(self, concurrency: int = 4, maxsize: int = 1000):
        self.concurrency = concurrency
        self.maxsize = maxsize
        self._queue: Optional[asyncio.Queue[str]] = None
        self._jobs: Dict[str, PipelineJob] = {}
        self._worker_tasks: List[asyncio.Task] = []
        self._running = False

    def _get_queue(self) -> asyncio.Queue[str]:
        if self._queue is None:
            self._queue = asyncio.Queue(maxsize=self.maxsize)
        return self._queue

    @property
    def is_running(self) -> bool:
        return self._running

    def start_workers(self) -> None:
        """Start async background worker tasks."""
        if self._running:
            return
        self._running = True
        self._queue = asyncio.Queue(maxsize=self.maxsize)
        for i in range(self.concurrency):
            task = asyncio.create_task(self._worker_loop(worker_id=i + 1))
            self._worker_tasks.append(task)
        logger.info("Pipeline worker queue started with %d workers.", self.concurrency)

    async def start_worker(self) -> None:
        self.start_workers()

    async def stop_workers(self) -> None:
        """Gracefully stop background worker tasks."""
        self._running = False
        for task in self._worker_tasks:
            task.cancel()
        self._worker_tasks.clear()
        self._queue = None
        logger.info("Pipeline worker queue stopped.")

    async def stop_worker(self) -> None:
        await self.stop_workers()

    async def submit_job(self, request: PipelineValidateRequest) -> PipelineJob:
        """Submit a new analytical dataset validation job to the queue."""
        # Idempotency check: if request has execution_id and is already active/completed
        if request.execution_id:
            for existing_job in self._jobs.values():
                if existing_job.execution_id == request.execution_id and existing_job.state not in (JobState.FAILED, JobState.CANCELLED):
                    logger.info("Idempotent submit: Job with execution_id '%s' already exists (%s).", request.execution_id, existing_job.job_id)
                    return existing_job

        job_id = f"JOB-{uuid.uuid4().hex[:8].upper()}"
        pipeline_id = request.pipeline_id or generate_pipeline_id()
        execution_id = request.execution_id or generate_execution_id()

        job = PipelineJob(
            job_id=job_id,
            pipeline_id=pipeline_id,
            execution_id=execution_id,
            dataset_name=request.dataset_name,
            state=JobState.QUEUED,
            request_payload=request,
        )
        self._jobs[job_id] = job
        await self._get_queue().put(job_id)
        return job

    def get_job(self, job_id: str) -> Optional[PipelineJob]:
        """Retrieve job state by its unique job identifier."""
        return self._jobs.get(job_id)

    def list_jobs(self, limit: int = 50) -> List[PipelineJob]:
        """List most recent jobs."""
        jobs_list = list(self._jobs.values())
        jobs_list.reverse()
        return jobs_list[:limit]

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a pending job if it has not yet started running."""
        job = self._jobs.get(job_id)
        if not job:
            return False
        if job.state in (JobState.QUEUED, JobState.CREATED):
            job.mark_cancelled()
            return True
        return False

    async def retry_job(self, job_id: str) -> PipelineJob:
        """
        Safely retry a failed or blocked job.
        CRITICAL SECURITY RULE:
          A security violation (BLOCKED) must NOT bypass verification on retry.
        """
        job = self._jobs.get(job_id)
        if not job:
            raise ValueError(f"Job '{job_id}' not found.")

        if job.state in (JobState.BLOCKED, JobState.FAILED):
            if job.retry_count >= job.max_retries:
                job.state = JobState.DEAD_LETTERED
                job.completed_at = datetime.utcnow().isoformat() + "Z"
                raise ValueError(f"Job '{job_id}' has exceeded maximum retry limit of {job.max_retries} and is now DEAD_LETTERED.")
            job.retry_count += 1
            job.state = JobState.QUEUED
            await self._get_queue().put(job_id)
            return job

        raise ValueError(f"Job '{job_id}' is in state '{job.state.value}' and cannot be retried.")


    def get_stats(self) -> Dict[str, Any]:
        """Return real-time queue health and worker status metrics."""
        queued = sum(1 for j in self._jobs.values() if j.state == JobState.QUEUED)
        running = sum(1 for j in self._jobs.values() if j.state == JobState.RUNNING)
        completed = sum(1 for j in self._jobs.values() if j.state in (JobState.READY, JobState.PUBLISHED))
        blocked = sum(1 for j in self._jobs.values() if j.state == JobState.BLOCKED)
        failed = sum(1 for j in self._jobs.values() if j.state == JobState.FAILED)

        return {
            "status": "online" if self._running else "idle",
            "concurrency": self.concurrency,
            "active_workers": len(self._worker_tasks),
            "queued_jobs": queued,
            "running_jobs": running,
            "completed_jobs": completed,
            "blocked_jobs": blocked,
            "failed_jobs": failed,
            "total_jobs": len(self._jobs),
        }

    async def _worker_loop(self, worker_id: int) -> None:
        """Continuous consumer loop for worker task."""
        logger.debug("Worker #%d started.", worker_id)
        queue = self._get_queue()
        while self._running:
            try:
                job_id = await queue.get()
                job = self._jobs.get(job_id)
                if not job or job.state == JobState.CANCELLED:
                    queue.task_done()
                    continue

                job.mark_running()
                try:
                    # Execute complete pipeline validation gate
                    result = await PipelineService.validate_pipeline(job.request_payload)
                    job.mark_completed(result)
                except Exception as exc:
                    logger.error("Job %s execution failed: %s", job_id, exc)
                    job.mark_failed(str(exc))
                finally:
                    queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Worker #%d encountered unhandled exception: %s", worker_id, exc)
                await asyncio.sleep(0.5)


# Singleton queue instance
pipeline_queue = PipelineQueue(
    concurrency=settings.WORKER_CONCURRENCY,
    maxsize=settings.WORKER_MAX_QUEUE_SIZE,
)
