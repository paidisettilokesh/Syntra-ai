import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.presentation.scheduler import AgentScheduler


@pytest.mark.asyncio
async def test_scheduler_run_loop():
    orchestrator = MagicMock()
    orchestrator.process_inboxes = AsyncMock()

    with patch("src.presentation.scheduler.settings") as mock_settings:
        mock_settings.app.poll_interval = 0.01
        scheduler = AgentScheduler(orchestrator)

        task = asyncio.create_task(scheduler.run())

        for _ in range(50):
            await asyncio.sleep(0.005)
            if orchestrator.process_inboxes.call_count >= 1:
                break

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert orchestrator.process_inboxes.call_count >= 1
