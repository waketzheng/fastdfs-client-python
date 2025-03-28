# fastdfs-client

FastDFS的Python客户端，支持最新版V6.12（截至2024.05.15）

要求Python3.9+

[English](./README.md) | **中文**

## 🚨 WARNING: DEPRECATED 🚨

2025-03-28
项目已停止维护，建议有储存需求的，采用其它工具。（BTW：minio是一个不错的选择，很容易上手）

## 安装

```bash
pip install fastdfs-client
```

## 使用

```py
from fastdfs_client import FastdfsClient

client = FastdfsClient('/etc/fdfs/client.conf')
ret = client.upload_by_filename('test.txt')
print(ret)
```
- 响应示例：
```JSON
{
    "Group name": "group1",
    "Status": "Upload successed.",
    "Remote file_id": "group1/M00/00/00/wKjzh0_xaR63RExnAAAaDqbNk5E1398.txt",
    "Uploaded size": "6.0KB",
    "Local file name": "test.txt",
    "Storage IP": "192.168.1.133"
}
```
## 其他用法
- 上传并返回URL地址
```py
from pathlib import Path
url = client.upload_as_url(Path('test.txt').read_bytes())
print(url)
# https://dfs.waketzheng.top/group1/M00/00/00/wKjzh0_xaR63RExnAAAaDqbNk5E1398.jpg
```
- 删除某个文件
```py
ret = client.delete_file(url)
print(ret)
# ('Delete file successed.', b'group1/M00/00/1B/eE0vIWaU9kyAVILJAAHM-px7j44359.jpg', b'120.77.47.33')
```
## 异步的方式
```py
url = await client.upload(Path('test.txt').read_bytes())
print(url)
# https://dfs.waketzheng.top/group1/M00/00/00/wKjzh0_xaR63RExnAAAaDqbNk5E1398.jpg
ret = await client.delete(url)
print(ret)
# ('Delete file successed.', b'group1/M00/00/1B/eE0vIWaU9kyAVILJAAHM-px7j44359.jpg', b'120.77.47.33')
```

## 说明
> 代码是在[fastdfs-client-py3 1.0.0](https://pypi.org/project/fastdfs-client-py3/)的基础上修改的：
1. 类名全部按照pep8规范的要求改成了驼峰
2. 所有的`from xxx import *`都改成了显式导入
3. 修复了已知的[TypeError](https://blog.csdn.net/jaket5219999/article/details/138918672)和[ResponseError](https://github.com/happyfish100/fastdfs/issues/679#issuecomment-1872550057)错误
4. 使用[ruff](https://github.com/astral-sh/ruff)进行格式化和导入排序
5. 部分函数增加了类型注解，所有代码均通过mypy检查
6. 增加了client.upload_as_url函数，支持上传二进制后返回完整URL
7. 扩展了FastdfsClient类的初始化，[直接传IP地址即可](./examples/init_with_ip.py)，无需传入.conf文件
8. 支持异步(asyncio/trio)的方式上传和删除文件

## 许可证

[GPL-3.0](./LICENSE)
