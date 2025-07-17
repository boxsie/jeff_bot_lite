# utils/scheduler.py
import asyncio
import datetime
import croniter
import logging
from typing import Dict, List, Callable, Coroutine, Any, Optional

logger = logging.getLogger('discord.scheduler')

class ScheduledJob:
    def __init__(self, cron_expression: str, callback, name: str = None, args: list = None, kwargs: dict = None):
        self.cron_expression = cron_expression
        self.callback = callback
        self.name = name or callback.__name__
        self.args = args or []
        self.kwargs = kwargs or {}
        self.next_run = None
        self._calculate_next_run()

    
    def _calculate_next_run(self):
        cron = croniter.croniter(self.cron_expression, datetime.datetime.now())
        self.next_run = cron.get_next(datetime.datetime)

    
    def should_run(self) -> bool:
        return datetime.datetime.now() >= self.next_run
    
    
    async def execute(self):
        try:
            logger.info(f"Executing job: {self.name}")
            if asyncio.iscoroutinefunction(self.callback):
                await self.callback(*self.args, **self.kwargs)
            else:
                self.callback(*self.args, **self.kwargs)
            logger.info(f"Job {self.name} executed successfully")
        except Exception as e:
            logger.error(f"Error executing job {self.name}: {str(e)}", exc_info=True)
        finally:
            self._calculate_next_run()


class Scheduler:
    def __init__(self, bot):
        self.bot = bot
        self.jobs: List[ScheduledJob] = []
        self.running = False
        self._task = None

    
    def add_job(self, cron_expression: str, callback, name: str = None, args: list = None, kwargs: dict = None) -> ScheduledJob:
        """
        Add a new job to the scheduler
        
        :param cron_expression: Cron expression (e.g. "0 0 * * *" for daily at midnight)
        :param callback: Function to call when job runs
        :param name: Optional name for the job
        :param args: Positional arguments to pass to the callback
        :param kwargs: Keyword arguments to pass to the callback
        :return: The created job
        """
        job = ScheduledJob(cron_expression, callback, name, args, kwargs)
        self.jobs.append(job)
        logger.info(f"Added job: {job.name}, next run: {job.next_run}")
        return job
    
    
    def remove_job(self, job_name: str) -> bool:
        """Remove a job by name"""
        for i, job in enumerate(self.jobs):
            if job.name == job_name:
                self.jobs.pop(i)
                logger.info(f"Removed job: {job_name}")
                return True
        return False
    
    
    async def _run_loop(self):
        """Main scheduler loop"""
        while self.running:
            for job in self.jobs:
                if job.should_run():
                    await job.execute()
            await asyncio.sleep(1)  # Check every second

    
    def start(self):
        """Start the scheduler"""
        if not self.running:
            self.running = True
            self._task = asyncio.create_task(self._run_loop())
            logger.info("Scheduler started")
            
    
    def stop(self):
        """Stop the scheduler"""
        if self.running:
            self.running = False
            if self._task:
                self._task.cancel()
            logger.info("Scheduler stopped")