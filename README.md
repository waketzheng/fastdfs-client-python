# fastdfs-client-python
FastDFS Python client

## Motivation

Base on [fastdfs-client-py3 1.0.0](https://pypi.org/project/fastdfs-client-py3/)

Fixes:
- TypeError:
```
Traceback (most recent call last):
  File "/home/wenping/trying/something/upload.py", line 4, in <module>
    client = Fdfs_client(tracker_conf_path)
  File "/home/wenping/trying/something/venv/lib/python3.10/site-packages/fdfs_client/client.py", line 52, in __init__
    self.tracker_pool = poolclass(**self.trackers)
TypeError: fdfs_client.connection.ConnectionPool() argument after ** must be a mapping, not str
```
- ResponseError
```
fdfs_client.exceptions.ResponseError: [-] Error: Tracker response length is invaild, expect: 40, actual: 70
```

## Install

```bash
pip install git+http://github.com/waketzheng/fastdfs-client-python@1.0.1#egg=fdfs-client
```
- Or
```bash
pip install git+ssh://git@github.com/waketzheng/fastdfs-client-python@1.0.1#egg=fdfs-client
```

## Usage

```py
from fdfs_client.client import Fdfs_client
client = Fdfs_client('/etc/fdfs/client.conf')
ret = client.upload_by_filename('test.txt')
print(ret)
```
- Response sample
```JSON
{"Group name":"group1","Status":"Upload successed.", "Remote file_id":"group1/M00/00/00/
	wKjzh0_xaR63RExnAAAaDqbNk5E1398.py","Uploaded size":"6.0KB","Local file name":"test"
	, "Storage IP":"192.168.243.133"}
```
