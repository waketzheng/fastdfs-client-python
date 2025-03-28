# fastdfs-client-python
![Python Versions](https://img.shields.io/pypi/pyversions/fastdfs-client)
[![LatestVersionInPypi](https://img.shields.io/pypi/v/fastdfs-client.svg?style=flat)](https://pypi.python.org/pypi/fastdfs-client)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
![Mypy coverage](https://img.shields.io/badge/mypy-100%25-green.svg)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/pre-commit/pre-commit/main.svg)](https://github.com/pre-commit/pre-commit)
[![GithubActionResult](https://github.com/waketzheng/asyncur/workflows/ci/badge.svg)](https://github.com/waketzheng/asyncur/actions?query=workflow:ci)

FastDFS Python client

*Manual pass upload test with fastdfs v6.12.1*

**English** | [中文](./README.zh.md)

## 🚨 WARNING: DEPRECATED 🚨

This project is deprecated. You should not use it. And if you use it for existing libraries, you should migrate to other projects.

## Motivation

Base on:
- [fastdfs-client-py3 1.0.0](https://pypi.org/project/fastdfs-client-py3/)

Fixes:
- TypeError:
```
Traceback (most recent call last):
  File "~/trying/something/upload.py", line 4, in <module>
    client = Fdfs_client(tracker_conf_path)
  File "~/trying/something/venv/lib/python3.10/site-packages/fdfs_client/client.py", line 52, in __init__
    self.tracker_pool = poolclass(**self.trackers)
TypeError: fdfs_client.connection.ConnectionPool() argument after ** must be a mapping, not str
```
- ResponseError
```
fdfs_client.exceptions.ResponseError: [-] Error: Tracker response length is invaild, expect: 40, actual: 70
```

## Requires

- Python3.9+ (No other dependence)

For Python3.8, use https://github.com/waketzheng/fastdfs-client-python/tree/1.0.1

## Install

```bash
pip install fastdfs-client
```

## Usage

```py
from fastdfs_client import FastdfsClient
client = FastdfsClient('/etc/fdfs/client.conf')
ret = client.upload_by_filename('test.txt')
print(ret)
```
- Response sample
```JSON
{
    "Group name": "group1",
    "Status": "Upload successed.",
    "Remote file_id": "group1/M00/00/00/wKjzh0_xaR63RExnAAAaDqbNk5E1398.txt",
    "Uploaded size": "6.0KB",
    "Local file name": "test.txt",
    "Storage IP": "192.168.243.133"
}
```

## Advance

- Upload as URL

```py
from pathlib import Path

p = Path('test.txt')
client = FastdfsClient(["dfs.waketzheng.top"])
url = client.upload_as_url(p.read_bytes(), p.suffix)
print(url)
# https://dfs.waketzheng.top/group1/M00/00/00/wKjzh0_xaR63RExnAAAaDqbNk5E1398.txt
```
- Download
```py
save_to = 'local.txt'
client.download_to_file(save_to, 'group1/M00/00/00/wKjzh0_xaR63RExnAAAaDqbNk5E1398.txt')
```
- Delete
```py
id_or_url = 'https://dfs.waketzheng.top/group1/M00/00/00/wKjzh0_xaR63RExnAAAaDqbNk5E1398.txt'
# id_or_url = 'group1/M00/00/00/wKjzh0_xaR63RExnAAAaDqbNk5E1398.txt'
client.delete_file(id_or_url)
```

## AsyncIO/Trio
- upload
```py
from pathlib import Path
from fastdfs_client import FastdfsClient

client = FastdfsClient(["dfs.waketzheng.top"])
p = Path('tests/test_async_client.py')
url = await client.upload(p.read_bytes(), p.suffix)
print(url)
# https://dfs.waketzheng.top/group1/M00/00/00/xxx.py
```
- delete
```py
url = 'https://dfs.waketzheng.top/group1/M00/00/00/xxx.py'
resp = await client.delete(url)
print(resp)
# ('Delete file successed.', b'group1/M00/00/1B/eE0vIWaU9kyAVILJAAHM-px7j44359.py', b'120.77.47.33')
```
