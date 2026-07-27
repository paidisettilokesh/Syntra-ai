import asyncio
import signal
import sys

from src.application.orchestrator import EmailOrchestrator
from src.config.settings import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class AgentScheduler:
    def __init__(self, orchestrator: EmailOrchestrator):
        self.orchestrator = orchestrator
        self.poll_interval = settings.app.poll_interval
        self._stop_event = asyncio.Event()

    def stop(self):
        """Signal the scheduler loop to stop on the next iteration."""
        logger.info("Shutdown signal received. Stopping scheduler...")
        self._stop_event.set()

    async def run(self):
        # Register signal handlers for graceful shutdown (Unix/Linux/macOS)
        # Windows handles Ctrl+C differently, so we also rely on KeyboardInterrupt in main.py
        if sys.platform != "win32":
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, self.stop)

        logger.info("🚀 AI Email Triage Agent Started. Listening for new emails...")
        
        while not self._stop_event.is_set():
            try:
                await self.orchestrator.process_inboxes()
            except Exception as e:
                logger.error(f"Agent loop encountered an error: {e}")

            if self._stop_event.is_set():
                break

            logger.info(f"Sleeping for {self.poll_interval} seconds...")
            
            # Use wait_for on the event instead of asyncio.sleep 
            # so we wake up immediately on shutdown signal
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.poll_interval)
            except asyncio.TimeoutError:
                # Timeout is the expected behavior when sleeping normally
                pass

        logger.info("Scheduler loop terminated gracefully.")
