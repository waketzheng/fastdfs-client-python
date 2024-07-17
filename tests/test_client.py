from contextlib import contextmanager
from pathlib import Path
from typing import Generator

import pytest

from fastdfs_client.client import Config, FastdfsClient, get_tracker_conf, is_IPv4
from fastdfs_client.exceptions import ConfigError, DataError


def test_ip():
    assert is_IPv4("8.8.8.8")
    assert not is_IPv4("8.8.8.1234")
    assert not is_IPv4("8.8.8.a")
    assert not is_IPv4("8.8.8")
    assert not is_IPv4("8.8.8")


def test_config_create():
    ip = "192.168.0.2"
    assert Config.create((ip,)) == {
        "host_tuple": (ip,),
        "port": Config.port,
        "timeout": Config.timeout,
        "name": Config.name,
    }


def test_conf_file():
    parent = Path(__file__).parent
    assert (
        get_tracker_conf("tests/trackers.conf")
        == FastdfsClient(parent / "trackers.conf").trackers
        == {
            "host_tuple": ("192.168.0.2",),
            "name": "Tracker Pool",
            "port": 22122,
            "timeout": 30,
        }
    )
    invalid_conf_file = parent / "invalid.conf"
    assert invalid_conf_file.exists()
    with pytest.raises(ConfigError):
        FastdfsClient(invalid_conf_file)


def test_conf_string_and_dict():
    conf = {
        "host_tuple": ("192.168.0.2",),
        "name": "Tracker Pool",
        "port": 22122,
        "timeout": 30,
    }
    assert (
        FastdfsClient(("192.168.0.2",)).trackers
        == FastdfsClient(["192.168.0.2"]).trackers
        == conf
    )
    assert FastdfsClient(conf).trackers == conf
    with pytest.raises(ConfigError):
        FastdfsClient({})


def test_build_host():
    domain = "dfs.waketzheng.top"
    ip = "120.77.47.33"
    client = FastdfsClient([domain])
    client._build_host(ip) == f"https://{domain}/"
    client2 = FastdfsClient([domain], ssl=False)
    client2._build_host(ip) == f"http://{domain}/"
    client3 = FastdfsClient([ip], ssl=False)
    client3._build_host(ip) == f"http://{ip}/"
    client4 = FastdfsClient([ip])
    client4._build_host(ip) == f"http://{ip}/"
    client5 = FastdfsClient([ip], ip_mapping={ip: domain})
    client5._build_host(ip) == f"https://{domain}/"
    client6 = FastdfsClient([domain], ip_mapping={ip: domain})
    client6._build_host(ip) == f"https://{domain}/"


def test_upload_url():
    to_upload = Path(__file__)
    domain = "dfs.waketzheng.top"
    client = FastdfsClient([domain])
    url = client.upload_as_url(to_upload.read_bytes(), to_upload.suffix)
    r = client.delete_file(url)
    assert Path(url).suffix == to_upload.suffix
    assert domain in url
    assert url.startswith("https")
    assert "success" in str(r)
    with pytest.raises(DataError):
        client._check_file(str(to_upload.parent))


def test_upload_filename():
    domain = "dfs.waketzheng.top"
    client = FastdfsClient([domain])
    ret = client.upload_by_filename(__file__)
    remote_file_id = ret["Remote file_id"]
    r = client.delete_file(remote_file_id)
    assert ret["Group name"].startswith("group")
    assert remote_file_id in str(r)
    assert ret["Local file name"] in __file__
    with pytest.raises(DataError):
        client.upload_by_filename(str(Path(__file__).parent))


def test_upload_file():
    domain = "dfs.waketzheng.top"
    client = FastdfsClient([domain])
    with pytest.raises(NotImplementedError):
        client.upload_by_file(__file__)


@contextmanager
def temp_remote_file(
    client: FastdfsClient, to_upload: Path, as_url=False
) -> Generator[str, None, None]:
    if as_url:
        url = client.upload_as_url(to_upload.read_bytes(), to_upload.suffix)
    else:
        ret = client.upload_by_filename(to_upload)
        url = ret["Remote file_id"]
    try:
        yield url
    finally:
        client.delete_file(url)


def test_download(tmp_path: Path):
    domain = "dfs.waketzheng.top"
    client = FastdfsClient([domain])
    with pytest.raises(DataError):
        client.download_to_file(tmp_path / "localfile", "not-exist-remote-file-id")
    to_upload = Path(__file__)
    temp_file = tmp_path / "foo"
    with temp_remote_file(client, to_upload) as remote_file_id:
        r = client.download_to_file(temp_file, remote_file_id)
    assert r["Content"] == temp_file
    assert temp_file.read_bytes() == to_upload.read_bytes()
    with pytest.raises(DataError):
        client.download_to_file(temp_file, remote_file_id)


def test_download_by_url(tmp_path: Path):
    domain = "dfs.waketzheng.top"
    client = FastdfsClient([domain])
    to_upload = Path(__file__)
    temp_file = tmp_path / "foo"
    with temp_remote_file(client, to_upload, as_url=True) as url:
        r = client.download_to_file(temp_file, url)
    assert r["Content"] == temp_file
    assert temp_file.read_bytes() == to_upload.read_bytes()
    with pytest.raises(DataError):
        client.download_to_file(temp_file, url)
