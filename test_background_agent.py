import pytest
from services.background_agent import ProactiveBackgroundAgent


@pytest.mark.asyncio
async def test_background_agent_start_and_stop():
    agent = ProactiveBackgroundAgent(interval_seconds=1)
    await agent.start()
    assert agent.is_running is True
    
    # 1.5 saniye bekle, kalp atisi atsin
    import asyncio
    await asyncio.sleep(1.5)
    
    assert agent.stats["last_heartbeat"] is not None
    await agent.stop()
    assert agent.is_running is False
