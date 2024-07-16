from pathlib import Path

import httpx
import pytest

from fastdfs_client.client import AsyncDfsClient, FastdfsClient


class TestUpload:
    client_cls = AsyncDfsClient
    domain = "dfs.waketzheng.top"

    @pytest.mark.anyio
    async def test_upload_and_delete(self):
        to_upload = Path(__file__)
        client = self.client_cls([self.domain])
        content = to_upload.read_bytes()
        url = await client.upload(content, to_upload.suffix)
        print(f"{url = }")
        try:
            uploaded = await self.http_get(url)
        finally:
            r = await client.delete(url)
        assert Path(url).suffix == to_upload.suffix
        assert self.domain in url
        assert url.startswith("https")
        assert "success" in str(r)
        print(f"Success to delete remote file: {Path(url).name}")
        assert uploaded == content

    @staticmethod
    async def http_get(url) -> bytes:
        async with httpx.AsyncClient() as client:
            r = await client.get(url)
            return r.content

    @pytest.mark.anyio
    async def test_client_with_ip_mapping(self):
        remote_ip = FastdfsClient.get_domain_ip(self.domain)
        client = self.client_cls([remote_ip], ip_mapping={remote_ip: self.domain})
        content = Path(__file__).read_bytes() * 2
        url = await client.upload(content)
        print(f"{url = }")
        try:
            uploaded = await self.http_get(url)
        finally:
            r = await client.delete(url)
        assert url.endswith(".jpg")
        assert self.domain in url
        assert url.startswith("https")
        assert "success" in str(r)
        print(f"Success to delete remote file: {Path(url).name}")
        assert uploaded == content


class TestUploadCompare:
    client_cls = FastdfsClient
