from pathlib import Path

from fastdfs_client import FastdfsClient

client = FastdfsClient(["dfs.waketzheng.top"])

p = Path(__file__).parent.parent / "README.md"
url = client.upload_as_url(p.read_bytes(), p.suffix)
print(f"{url = }")
# url = 'https://dfs.waketzheng.top/group1/M00/00/00/eE0vIWZ1IXCAdnE5AAAIuzDpzQ46480.md'
