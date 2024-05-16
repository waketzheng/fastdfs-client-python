from fastdfs_client import FastdfsClient

# Initial with IP address
client1 = FastdfsClient(
    trackers=("192.168.0.2",),
)

# Equals to the following conf
tracker_conf = """
connect_timeout=30
tracker_server=192.168.0.2:22122
"""
with open("./tracker.conf", "w") as f:
    f.write(tracker_conf)

# Old format
client2 = FastdfsClient(trackers="./tracker.conf")

print("client1:", client1.trackers)
print("client2:", client2.trackers)
assert client1.trackers == client2.trackers
