import pytest
from tools.system_control import SystemHardwareControlTool
from memory.pc_catalog import PCCatalogService


@pytest.mark.asyncio
async def test_system_hardware_control_tool():
    tool = SystemHardwareControlTool()
    res = await tool.execute(action="volume_up", value=2)
    assert res.success is True
    assert "SENSÖRÜ" in res.output


def test_pc_catalog_indexer():
    catalog = PCCatalogService(db_path="storage/db/test_pc_catalog.db")
    count = catalog.scan_and_index_pc()
    assert count >= 0
