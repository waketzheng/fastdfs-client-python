from pathlib import Path

import pytest

from fastdfs_client.client import AsyncDfsClient, FastdfsClient


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_upload_and_delete():
    to_upload = Path(__file__)
    domain = "dfs.waketzheng.top"
    client = AsyncDfsClient([domain])
    url = await client.upload(to_upload.read_bytes(), to_upload.suffix)
    assert Path(url).suffix == to_upload.suffix
    assert domain in url
    assert url.startswith("https")
    remote_file_id = url.split("://")[-1].split("/", 1)[-1]
    r = await client.delete(remote_file_id)
    assert "success" in str(r)


@pytest.mark.anyio
async def test_compare():
    to_upload = Path(__file__)
    domain = "dfs.waketzheng.top"
    client = FastdfsClient([domain])
    url = await client.upload(to_upload.read_bytes(), to_upload.suffix)
    assert Path(url).suffix == to_upload.suffix
    assert domain in url
    assert url.startswith("https")
    remote_file_id = url.split("://")[-1].split("/", 1)[-1]
    r = await client.delete(remote_file_id)
    assert "success" in str(r)
