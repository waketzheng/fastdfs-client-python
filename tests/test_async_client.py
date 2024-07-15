from pathlib import Path

import pytest

from fastdfs_client.client import AsyncDfsClient, FastdfsClient


class TestUpload:
    client_cls = AsyncDfsClient

    @pytest.mark.anyio
    async def test_upload_and_delete(self):
        to_upload = Path(__file__)
        domain = "dfs.waketzheng.top"
        client = self.client_cls([domain])
        url = await client.upload(to_upload.read_bytes(), to_upload.suffix)
        print(f"{url = }")
        r = await client.delete(url)
        assert Path(url).suffix == to_upload.suffix
        assert domain in url
        assert url.startswith("https")
        assert "success" in str(r)


class TestUploadCompare:
    client_cls = FastdfsClient
