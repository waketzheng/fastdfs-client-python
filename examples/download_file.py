from fastdfs_client import FastdfsClient

client = FastdfsClient(["dfs.waketzheng.top"])

remote_file_id = "group1/M00/00/00/eE0vIWZ2WgWAQFe9AAAIxCfkTzQ4341.md"
r = client.download_to_file("temp.md", remote_file_id)
print(r)
