#!/usr/bin/env python
import sys
from pathlib import Path

import anyio

from fastdfs_client import FastdfsClient


async def main() -> None:
    client = FastdfsClient(["dfs.waketzheng.top"])

    p = Path(__file__)
    url = await client.upload(p.read_bytes(), p.suffix)
    print(f"{url = }")
    # url = 'https://dfs.waketzheng.top/group1/M00/00/00/eE0vIWZ1IXCAdnE5AAAIuzDpzQ46480.py'

    if "--save" not in sys.argv:
        r = await client.delete(url)
        print(r)


if __name__ == "__main__":
    anyio.run(main)
