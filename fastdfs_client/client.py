from __future__ import annotations

import contextlib
import os
import random
import re
import socket
from functools import cached_property
from pathlib import Path
from typing import Annotated, Type, TypedDict, Union, cast, get_type_hints

from .connection import ConnectionPool
from .exceptions import ConfigError, DataError, ResponseError
from .protols import STORAGE_SET_METADATA_FLAG_OVERWRITE
from .storage_client import StorageClient
from .tracker_client import TrackerClient
from .utils import FastdfsConfigParser, fdfs_check_file, logger, split_remote_fileid

RE_IP = re.compile(r"(?:[0-9]{1,3}\.){3}[0-9]{1,3}$")


def is_IPv4(value: str) -> bool:
    return bool(RE_IP.match(value))


class ConfigDict(TypedDict):
    host_tuple: Annotated[
        tuple[str, ...], "IP or domain, e.g: ('192.168.0.2', 'example.com')"
    ]
    port: int
    timeout: int
    name: str


class Config:
    port = 22122
    timeout = 30
    name = "Tracker Pool"

    @classmethod
    def create(
        cls,
        hosts: tuple[str, ...],
        port: int | None = None,
        timeout: int | None = None,
    ) -> ConfigDict:
        return {
            "host_tuple": hosts,
            "port": port or cls.port,
            "timeout": timeout or cls.timeout,
            "name": cls.name,
        }


def get_tracker_conf(conf_path="client.conf") -> dict:
    cf = FastdfsConfigParser()
    tracker: dict = {}
    try:
        cf.read(conf_path)
        timeout = cf.getint("__config__", "connect_timeout")
        tracker_list = cf.get("__config__", "tracker_server")
        if isinstance(tracker_list, str):
            tracker_list = [tracker_list]
        tracker_ip_list = []
        for tr in tracker_list:
            tracker_ip, tracker_port = tr.split(":")
            tracker_ip_list.append(tracker_ip)
        tracker["host_tuple"] = tuple(tracker_ip_list)
        tracker["port"] = int(tracker_port)
        tracker["timeout"] = timeout
        tracker["name"] = "Tracker Pool"
    except Exception as e:
        logger.exception(e)
        raise ConfigError(str(e)) from e
    return tracker


TrackersConfType = Union[
    Annotated[Union[str, Path], "filename of trackers.conf"],
    Annotated[Union[dict, ConfigDict], "Config of trackers"],
    Annotated[Union[tuple[str, ...], list[str]], "IP list or domain list"],
]


class BaseClient:
    def __init__(
        self,
        trackers: TrackersConfType,
        ip_mapping: Annotated[dict[str, str], "ip: domain"] | None = None,
        ssl: bool = True,
    ) -> None:
        if isinstance(trackers, (str, Path)):
            trackers = get_tracker_conf(str(trackers))
        elif isinstance(trackers, (tuple, list)):
            trackers = Config.create(tuple(trackers))
        elif isinstance(trackers, dict):
            self._check_config(trackers)
        self.trackers = cast(dict, trackers)
        self.timeout = self.trackers["timeout"]
        self.ip_mapping = ip_mapping
        self.ssl = ssl

    def _check_config(self, trackers) -> None:
        expected = get_type_hints(ConfigDict)
        if missing := set(expected) - set(trackers):
            raise ConfigError(f"Invalid trackers: {missing=} (expected: {expected})")

    def _build_host(self, storage_ip: str) -> str:
        ip_mapping = self.ip_mapping or {}
        if storage_ip not in ip_mapping:
            listed_domains = ip_mapping.values()
            for ip_or_domain in self.trackers["host_tuple"]:
                if is_IPv4(ip_or_domain) or ip_or_domain in listed_domains:
                    continue
                if self.get_domain_ip(ip_or_domain) == storage_ip:
                    ip_mapping[storage_ip] = ip_or_domain
                    break
        if h := ip_mapping.get(storage_ip):
            if not h.endswith("/"):
                h += "/"
            if not h.startswith("http"):
                scheme = "https" if self.ssl else "http"
                h = f"{scheme}://" + h
            return h
        return f"http://{storage_ip}/"

    @staticmethod
    def get_domain_ip(domain: str) -> str:
        """Get domain IP by socket: github.com -> 140.82.113.3"""
        return socket.gethostbyname(domain)


class AsyncDfsClient(BaseClient):
    @cached_property
    def domain_ip(self) -> dict[str, str]:
        return {v.split("://")[-1]: k for k, v in (self.ip_mapping or {}).items()}

    def random_host(self) -> tuple[str, int]:
        ip_list: list[str] = []
        for host in self.trackers["host_tuple"]:
            if not is_IPv4(host):
                if host in self.domain_ip:
                    host = self.domain_ip[host]
                else:
                    host = self.get_domain_ip(host)
            ip_list.append(host)
        if len(ip_list) > 1:
            host = random.choice(ip_list)
        return host, self.trackers["port"]

    async def upload(self, content: bytes, suffix=".jpg") -> str:
        """Upload file content, if success return a URL

        :param content: bytes type of file content
        :param suffix: this will add at the end of URL with a dot before it

        Example::
        ```py
        from pathlib import Path
        from fastdfs_client import AsyncDfsClient

        client = AsyncDfsClient(['example.com'])
        url = await client.upload(Path('a.JPEG').read_bytes(), suffix='jpeg')
        print(url)
        # https://example.com/group1/M00/00/00/eE0vIWZEgMCAFnaMAAABXbxaFk89563.jpeg
        ```
        """
        store_serv = await TrackerClient.get_storage_server(self.random_host())
        store = StorageClient(store_serv.ip_addr, store_serv.port, self.timeout)  # type:ignore
        res = await store.upload_buffer(store_serv, content, suffix.lstrip("."))
        uri_path = res["Remote file_id"]  # 'group1/M00/00/00/eE..R458.jpg'
        return self._build_host(res["Storage IP"]) + uri_path

    async def delete(
        self, file: Annotated[str, "remote_file id or URL, e.g.: group1/M00/00/xxx.jpg"]
    ) -> tuple:
        """Delete uploaded file, if success return a tuple

        :param file: remote file id or URL
        :return: tuple -- ('Success message', b'remote file id', b'storage ip')

        Example::
        ```py
        from fastdfs_client import AsyncDfsClient

        client = AsyncDfsClient(['example.com'])
        url = https://example.com/group1/M00/00/00/eE0vIWZEgMCAFnaMAAABXbxaFk89563.jpeg'
        ret = await client.delete(url)
        print(ret)
        # ('Delete file successed.', b'group1/M00/00/1B/eE0vIWaU9kyAVILJAAHM-px7j44359.py', b'120.77.47.33')
        ```
        """
        maybe_url = True
        try:
            _, uri = file.split("://")
        except ValueError:
            host_info = self.random_host()
        else:
            ip_addr, file = uri.split("/", 1)
            maybe_url = False
            if not is_IPv4(ip_addr):
                ip_addr = self.get_domain_ip(ip_addr)
            host_info = (ip_addr, self.trackers["port"])
        if not (tmp := split_remote_fileid(file, maybe_url=maybe_url)):
            raise DataError("[-] Error: remote_file_id is invalid.(in delete file)")
        group_name, remote_filename = tmp
        store_serv = await TrackerClient.get_storage_server(
            host_info, group_name, remote_filename
        )
        store = StorageClient(store_serv.ip_addr, store_serv.port, self.timeout)
        return await store.delete_file(store_serv, remote_filename)


class FastdfsClient(BaseClient):
    """
    Class FastdfsClient implemented Fastdfs client protol V6.12

    It's useful upload, download, delete file to or from fdfs server, etc. It's uses
    connection pool to manage connection to server.
    """

    def __init__(
        self,
        trackers: TrackersConfType,
        poolclass: Type[ConnectionPool] | None = None,
        ip_mapping: dict[str, str] | None = None,
        ssl: bool = True,
    ) -> None:
        super().__init__(trackers, ip_mapping, ssl)
        if poolclass is None:
            poolclass = ConnectionPool
        self.tracker_pool = poolclass(**self.trackers)

    def __del__(self) -> None:
        try:
            self.pool.destroy()  # type:ignore
            self.pool = None  # pragma: no cover
        except Exception as e:
            logger.debug(f"Failed to destroy: {e}")

    def upload_as_url(self, content: bytes, suffix="jpg") -> str:
        """Upload file content, if success return a URL

        :param content: bytes type of file content
        :param suffix: this will add at the end of URL with a dot before it

        Example::
        ```py
        from pathlib import Path
        from fastdfs_client import FastdfsClient

        client = FastdfsClient(
            trackers=('120.7.7.3',),
            ip_mapping={'120.7.7.3': 'https://example.com'}
        )
        p = Path('a.py')
        ret = client.upload_as_url(p.read_bytes(), p.suffix)
        print(ret)
        # https://example.com/group1/M00/00/00/eE0vIWZEgMCAFnaMAAABXbxaFk89563.py
        ```
        """
        res = self.upload_by_buffer(content, suffix.lstrip("."))
        uri_path = res["Remote file_id"]  # 'group1/M00/00/00/eE..R458.jpg'
        return self._build_host(res["Storage IP"]) + uri_path

    def upload_by_filename(self, filename: str | Path, meta_dict=None) -> dict:
        """
        Upload a file to Storage server.
        arguments:
        @filename: string, name of file that will be uploaded
        @meta_dict: dictionary e.g.:{
            'ext_name'  : 'jpg',
            'file_size' : '10240B',
            'width'     : '160px',
            'hight'     : '80px'
        } meta_dict can be null
        @return dict {
            'Group name'      : group_name,
            'Remote file_id'  : remote_file_id,
            'Status'          : 'Upload successed.',
            'Local file name' : local_file_name,
            'Uploaded size'   : upload_size,
            'Storage IP'      : storage_ip
        } if success else None
        """
        self._check_file(filename)
        tc = TrackerClient(self.tracker_pool)
        store_serv = tc.tracker_query_storage_stor_without_group()
        store = StorageClient(store_serv.ip_addr, store_serv.port, self.timeout)
        return store.storage_upload_by_filename(
            tc, store_serv, str(filename), meta_dict
        )

    def _check_file(self, filename, info="(uploading)") -> None:
        isfile, errmsg = fdfs_check_file(filename)
        if not isfile:
            raise DataError(errmsg + info)

    def upload_by_file(self, filename, meta_dict=None):
        self._check_file(filename)
        tc = TrackerClient(self.tracker_pool)
        store_serv = tc.tracker_query_storage_stor_without_group()
        store = StorageClient(store_serv.ip_addr, store_serv.port, self.timeout)
        return store.storage_upload_by_file(tc, store_serv, filename, meta_dict)

    def upload_by_buffer(
        self, filebuffer: bytes, file_ext_name=None, meta_dict=None
    ) -> dict:
        """
        Upload a buffer to Storage server.
        arguments:
        @filebuffer: string, buffer
        @file_ext_name: string, file extend name
        @meta_dict: dictionary e.g.:{
            'ext_name'  : 'jpg',
            'file_size' : '10240B',
            'width'     : '160px',
            'hight'     : '80px'
        }
        @return dict {
            'Group name'      : group_name,
            'Remote file_id'  : remote_file_id,
            'Status'          : 'Upload successed.',
            'Local file name' : '',
            'Uploaded size'   : upload_size,
            'Storage IP'      : storage_ip
        } if success else None
        """
        if not filebuffer:
            raise DataError("[-] Error: argument filebuffer can not be null.")
        tc = TrackerClient(self.tracker_pool)
        store_serv = tc.tracker_query_storage_stor_without_group()
        store = StorageClient(store_serv.ip_addr, store_serv.port, self.timeout)
        return store.storage_upload_by_buffer(
            tc, store_serv, filebuffer, file_ext_name, meta_dict
        )

    def upload_slave_by_filename(
        self, filename, remote_file_id, prefix_name, meta_dict=None
    ):
        """
        Upload slave file to Storage server.
        arguments:
        @filename: string, local file name
        @remote_file_id: string, remote file id
        @prefix_name: string
        @meta_dict: dictionary e.g.:{
            'ext_name'  : 'jpg',
            'file_size' : '10240B',
            'width'     : '160px',
            'hight'     : '80px'
        }
        @return dictionary {
            'Status'        : 'Upload slave successed.',
            'Local file name' : local_filename,
            'Uploaded size'   : upload_size,
            'Remote file id'  : remote_file_id,
            'Storage IP'      : storage_ip
        }
        """
        self._check_file(filename, "(uploading slave)")
        tmp = split_remote_fileid(remote_file_id)
        if not tmp:
            raise DataError("[-] Error: remote_file_id is invalid.(uploading slave)")
        if not prefix_name:
            raise DataError("[-] Error: prefix_name can not be null.")
        group_name, remote_filename = tmp
        tc = TrackerClient(self.tracker_pool)
        store_serv = tc.tracker_query_storage_stor_with_group(group_name)
        store = StorageClient(store_serv.ip_addr, store_serv.port, self.timeout)
        try:
            ret_dict = store.storage_upload_slave_by_filename(
                tc, store_serv, filename, prefix_name, remote_filename, meta_dict=None
            )
        except Exception as e:
            logger.exception(e)
            raise e
        ret_dict["Status"] = "Upload slave file successed."
        return ret_dict

    def upload_slave_by_file(
        self, filename, remote_file_id, prefix_name, meta_dict=None
    ):
        """
        Upload slave file to Storage server.
        arguments:
        @filename: string, local file name
        @remote_file_id: string, remote file id
        @prefix_name: string
        @meta_dict: dictionary e.g.:{
            'ext_name'  : 'jpg',
            'file_size' : '10240B',
            'width'     : '160px',
            'hight'     : '80px'
        }
        @return dictionary {
            'Status'        : 'Upload slave successed.',
            'Local file name' : local_filename,
            'Uploaded size'   : upload_size,
            'Remote file id'  : remote_file_id,
            'Storage IP'      : storage_ip
        }
        """
        self._check_file(filename, "(uploading slave)")
        tmp = split_remote_fileid(remote_file_id)
        if not tmp:
            raise DataError("[-] Error: remote_file_id is invalid.(uploading slave)")
        if not prefix_name:
            raise DataError("[-] Error: prefix_name can not be null.")
        group_name, remote_filename = tmp
        tc = TrackerClient(self.tracker_pool)
        store_serv = tc.tracker_query_storage_stor_with_group(group_name)
        store = StorageClient(store_serv.ip_addr, store_serv.port, self.timeout)
        try:
            ret_dict = store.storage_upload_slave_by_file(
                tc, store_serv, filename, prefix_name, remote_filename, meta_dict=None
            )
        except Exception as e:
            logger.exception(e)
            raise DataError(str(e)) from e
        ret_dict["Status"] = "Upload slave file successed."
        return ret_dict

    def upload_slave_by_buffer(
        self, filebuffer, remote_file_id, meta_dict=None, file_ext_name=None
    ):
        """
        Upload slave file by buffer
        arguments:
        @filebuffer: string
        @remote_file_id: string
        @meta_dict: dictionary e.g.:{
            'ext_name'  : 'jpg',
            'file_size' : '10240B',
            'width'     : '160px',
            'hight'     : '80px'
        }
        @return dictionary {
            'Status'        : 'Upload slave successed.',
            'Local file name' : local_filename,
            'Uploaded size'   : upload_size,
            'Remote file id'  : remote_file_id,
            'Storage IP'      : storage_ip
        }
        """
        if not filebuffer:
            raise DataError("[-] Error: argument filebuffer can not be null.")
        tmp = split_remote_fileid(remote_file_id)
        if not tmp:
            raise DataError("[-] Error: remote_file_id is invalid.(uploading slave)")
        group_name, remote_filename = tmp
        tc = TrackerClient(self.tracker_pool)
        store_serv = tc.tracker_query_storage_update(group_name, remote_filename)
        store = StorageClient(store_serv.ip_addr, store_serv.port, self.timeout)
        return store.storage_upload_slave_by_buffer(
            tc, store_serv, filebuffer, remote_filename, meta_dict, file_ext_name
        )

    def upload_appender_by_filename(self, local_filename, meta_dict=None):
        """
        Upload an appender file by filename.
        arguments:
        @local_filename: string
        @meta_dict: dictionary e.g.:{
            'ext_name'  : 'jpg',
            'file_size' : '10240B',
            'width'     : '160px',
            'hight'     : '80px'
        }    Notice: it can be null
        @return dict {
            'Group name'      : group_name,
            'Remote file_id'  : remote_file_id,
            'Status'          : 'Upload successed.',
            'Local file name' : '',
            'Uploaded size'   : upload_size,
            'Storage IP'      : storage_ip
        } if success else None
        """
        self._check_file(local_filename, "(uploading appender)")
        tc = TrackerClient(self.tracker_pool)
        store_serv = tc.tracker_query_storage_stor_without_group()
        store = StorageClient(store_serv.ip_addr, store_serv.port, self.timeout)
        return store.storage_upload_appender_by_filename(
            tc, store_serv, local_filename, meta_dict
        )

    def upload_appender_by_file(self, local_filename, meta_dict=None):
        """
        Upload an appender file by file.
        arguments:
        @local_filename: string
        @meta_dict: dictionary e.g.:{
            'ext_name'  : 'jpg',
            'file_size' : '10240B',
            'width'     : '160px',
            'hight'     : '80px'
        }    Notice: it can be null
        @return dict {
            'Group name'      : group_name,
            'Remote file_id'  : remote_file_id,
            'Status'          : 'Upload successed.',
            'Local file name' : '',
            'Uploaded size'   : upload_size,
            'Storage IP'      : storage_ip
        } if success else None
        """
        self._check_file(local_filename, "(uploading appender)")
        tc = TrackerClient(self.tracker_pool)
        store_serv = tc.tracker_query_storage_stor_without_group()
        store = StorageClient(store_serv.ip_addr, store_serv.port, self.timeout)
        return store.storage_upload_appender_by_file(
            tc, store_serv, local_filename, meta_dict
        )

    def upload_appender_by_buffer(self, filebuffer, file_ext_name=None, meta_dict=None):
        """
        Upload a buffer to Storage server.
        arguments:
        @filebuffer: string
        @file_ext_name: string, can be null
        @meta_dict: dictionary, can be null
        @return dict {
            'Group name'      : group_name,
            'Remote file_id'  : remote_file_id,
            'Status'          : 'Upload successed.',
            'Local file name' : '',
            'Uploaded size'   : upload_size,
            'Storage IP'      : storage_ip
        } if success else None
        """
        if not filebuffer:
            raise DataError("[-] Error: argument filebuffer can not be null.")
        tc = TrackerClient(self.tracker_pool)
        store_serv = tc.tracker_query_storage_stor_without_group()
        store = StorageClient(store_serv.ip_addr, store_serv.port, self.timeout)
        return store.storage_upload_appender_by_buffer(
            tc, store_serv, filebuffer, meta_dict, file_ext_name
        )

    def delete_file(self, remote_file_id: str) -> tuple[str, bytes, bytes]:
        """
        Delete a file from Storage server.
        arguments:
        @remote_file_id: string, file_id of file that is on storage server
        @return tuple ('Delete file successed.', remote_file_id, storage_ip)
        """
        tmp = split_remote_fileid(remote_file_id)
        if not tmp:
            raise DataError("[-] Error: remote_file_id is invalid.(in delete file)")
        group_name, remote_filename = tmp
        tc = TrackerClient(self.tracker_pool)
        store_serv = tc.tracker_query_storage_update(group_name, remote_filename)
        store = StorageClient(store_serv.ip_addr, store_serv.port, self.timeout)
        return store.storage_delete_file(tc, store_serv, remote_filename)

    def download_to_file(self, local_filename, remote_file_id, offset=0, down_bytes=0):
        """
        Download a file from Storage server.
        arguments:
        @local_filename: string, local name of file
        @remote_file_id: string, file_id of file that is on storage server
        @offset: long
        @downbytes: long
        @return dict {
            'Remote file_id'  : remote_file_id,
            'Content'         : local_filename,
            'Download size'   : downloaded_size,
            'Storage IP'      : storage_ip
        }
        """
        tmp = split_remote_fileid(remote_file_id)
        if not tmp:
            raise DataError("[-] Error: remote_file_id is invalid.(in download file)")
        group_name, remote_filename = tmp
        file_offset = 0
        if offset:
            with contextlib.suppress(TypeError, ValueError):
                file_offset = int(offset)
        if not down_bytes:
            download_bytes = int(down_bytes)
        tc = TrackerClient(self.tracker_pool)
        store_serv = tc.tracker_query_storage_fetch(group_name, remote_filename)
        store = StorageClient(store_serv.ip_addr, store_serv.port, self.timeout)
        return store.storage_download_to_file(
            tc, store_serv, local_filename, file_offset, download_bytes, remote_filename
        )

    def download_to_buffer(self, remote_file_id, offset=0, down_bytes=0):
        """
        Download a file from Storage server and store in buffer.
        arguments:
        @remote_file_id: string, file_id of file that is on storage server
        @offset: long
        @down_bytes: long
        @return dict {
            'Remote file_id'  : remote_file_id,
            'Content'         : file_buffer,
            'Download size'   : downloaded_size,
            'Storage IP'      : storage_ip
        }
        """
        tmp = split_remote_fileid(remote_file_id)
        if not tmp:
            raise DataError("[-] Error: remote_file_id is invalid.(in download file)")
        group_name, remote_filename = tmp
        file_offset = 0
        if offset:
            with contextlib.suppress(TypeError, ValueError):
                file_offset = int(offset)
        if not down_bytes:
            download_bytes = int(down_bytes)
        tc = TrackerClient(self.tracker_pool)
        store_serv = tc.tracker_query_storage_fetch(group_name, remote_filename)
        store = StorageClient(store_serv.ip_addr, store_serv.port, self.timeout)
        file_buffer = None
        return store.storage_download_to_buffer(
            tc, store_serv, file_buffer, file_offset, download_bytes, remote_filename
        )

    def list_one_group(self, group_name):
        """
        List one group information.
        arguments:
        @group_name: string, group name will be list
        @return Group_info,  instance
        """
        tc = TrackerClient(self.tracker_pool)
        return tc.tracker_list_one_group(group_name)

    def list_servers(self, group_name, storage_ip=None):
        """
        List all storage servers information in a group
        arguments:
        @group_name: string
        @return dictionary {
            'Group name' : group_name,
            'Servers'    : server list,
        }
        """
        tc = TrackerClient(self.tracker_pool)
        return tc.tracker_list_servers(group_name, storage_ip)

    def list_all_groups(self):
        """
        List all group information.
        @return dictionary {
            'Groups count' : group_count,
            'Groups'       : list of groups
        }
        """
        tc = TrackerClient(self.tracker_pool)
        return tc.tracker_list_all_groups()

    def get_meta_data(self, remote_file_id):
        """
        Get meta data of remote file.
        arguments:
        @remote_fileid: string, remote file id
        @return dictionary, meta data
        """
        tmp = split_remote_fileid(remote_file_id)
        if not tmp:
            raise DataError("[-] Error: remote_file_id is invalid.(in get meta data)")
        group_name, remote_filename = tmp
        tc = TrackerClient(self.tracker_pool)
        store_serv = tc.tracker_query_storage_update(group_name, remote_filename)
        store = StorageClient(store_serv.ip_addr, store_serv.port, self.timeout)
        return store.storage_get_metadata(tc, store_serv, remote_filename)

    def set_meta_data(
        self, remote_file_id, meta_dict, op_flag=STORAGE_SET_METADATA_FLAG_OVERWRITE
    ):
        """
        Set meta data of remote file.
        arguments:
        @remote_file_id: string
        @meta_dict: dictionary
        @op_flag: char, 'O' for overwrite, 'M' for merge
        @return dictionary {
            'Status'     : status,
            'Storage IP' : storage_ip
        }
        """
        tmp = split_remote_fileid(remote_file_id)
        if not tmp:
            raise DataError("[-] Error: remote_file_id is invalid.(in set meta data)")
        group_name, remote_filename = tmp
        tc = TrackerClient(self.tracker_pool)
        try:
            store_serv = tc.tracker_query_storage_update(group_name, remote_filename)
            store = StorageClient(store_serv.ip_addr, store_serv.port, self.timeout)
            status = store.storage_set_metadata(
                tc, store_serv, remote_filename, meta_dict
            )
        except (ConnectionError, ResponseError, DataError):
            raise
        if status == 2:
            raise DataError(
                "[-] Error: remote file %s does not exist." % remote_file_id
            )
        elif status != 0:
            raise DataError("[-] Error: %d, %s" % (status, os.strerror(status)))
        ret_dict = {}
        ret_dict["Status"] = "Set meta data success."
        ret_dict["Storage IP"] = store_serv.ip_addr
        return ret_dict

    def append_by_filename(self, local_filename, remote_fileid):
        self._check_file(local_filename, "(append)")
        tmp = split_remote_fileid(remote_fileid)
        if not tmp:
            raise DataError("[-] Error: remote_file_id is invalid.(append)")
        group_name, appended_filename = tmp
        tc = TrackerClient(self.tracker_pool)
        store_serv = tc.tracker_query_storage_update(group_name, appended_filename)
        store = StorageClient(store_serv.ip_addr, store_serv.port, self.timeout)
        return store.storage_append_by_filename(
            tc, store_serv, local_filename, appended_filename
        )

    def append_by_file(self, local_filename, remote_fileid):
        self._check_file(local_filename, "(append)")
        tmp = split_remote_fileid(remote_fileid)
        if not tmp:
            raise DataError("[-] Error: remote_file_id is invalid.(append)")
        group_name, appended_filename = tmp
        tc = TrackerClient(self.tracker_pool)
        store_serv = tc.tracker_query_storage_update(group_name, appended_filename)
        store = StorageClient(store_serv.ip_addr, store_serv.port, self.timeout)
        return store.storage_append_by_file(
            tc, store_serv, local_filename, appended_filename
        )

    def append_by_buffer(self, file_buffer, remote_fileid):
        if not file_buffer:
            raise DataError("[-] Error: file_buffer can not be null.")
        tmp = split_remote_fileid(remote_fileid)
        if not tmp:
            raise DataError("[-] Error: remote_file_id is invalid.(append)")
        group_name, appended_filename = tmp
        tc = TrackerClient(self.tracker_pool)
        store_serv = tc.tracker_query_storage_update(group_name, appended_filename)
        store = StorageClient(store_serv.ip_addr, store_serv.port, self.timeout)
        return store.storage_append_by_buffer(
            tc, store_serv, file_buffer, appended_filename
        )

    def truncate_file(self, truncated_filesize, appender_fileid):
        """
        Truncate file in Storage server.
        arguments:
        @truncated_filesize: long
        @appender_fileid: remote_fileid
        @return: dictionary {
            'Status'     : 'Truncate successed.',
            'Storage IP' : storage_ip
        }
        """
        trunc_filesize = int(truncated_filesize)
        tmp = split_remote_fileid(appender_fileid)
        if not tmp:
            raise DataError("[-] Error: appender_fileid is invalid.(truncate)")
        group_name, appender_filename = tmp
        tc = TrackerClient(self.tracker_pool)
        store_serv = tc.tracker_query_storage_update(group_name, appender_filename)
        store = StorageClient(store_serv.ip_addr, store_serv.port, self.timeout)
        return store.storage_truncate_file(
            tc, store_serv, trunc_filesize, appender_filename
        )

    def modify_by_filename(self, filename, appender_fileid, offset=0):
        """
        Modify a file in Storage server by file.
        arguments:
        @filename: string, local file name
        @offset: long, file offset
        @appender_fileid: string, remote file id
        @return: dictionary {
            'Status'     : 'Modify successed.',
            'Storage IP' : storage_ip
        }
        """
        self._check_file(filename, "(modify)")
        filesize = os.stat(filename).st_size
        tmp = split_remote_fileid(appender_fileid)
        if not tmp:
            raise DataError("[-] Error: remote_fileid is invalid.(modify)")
        group_name, appender_filename = tmp
        file_offset = 0
        if offset:
            with contextlib.suppress(TypeError, ValueError):
                file_offset = int(offset)
        tc = TrackerClient(self.tracker_pool)
        store_serv = tc.tracker_query_storage_update(group_name, appender_filename)
        store = StorageClient(store_serv.ip_addr, store_serv.port, self.timeout)
        return store.storage_modify_by_filename(
            tc, store_serv, filename, file_offset, filesize, appender_filename
        )

    def modify_by_file(self, filename, appender_fileid, offset=0):
        """
        Modify a file in Storage server by file.
        arguments:
        @filename: string, local file name
        @offset: long, file offset
        @appender_fileid: string, remote file id
        @return: dictionary {
            'Status'     : 'Modify successed.',
            'Storage IP' : storage_ip
        }
        """
        self._check_file(filename, "(modify)")
        filesize = os.stat(filename).st_size
        tmp = split_remote_fileid(appender_fileid)
        if not tmp:
            raise DataError("[-] Error: remote_fileid is invalid.(modify)")
        group_name, appender_filename = tmp
        file_offset = 0
        if offset:
            with contextlib.suppress(TypeError, ValueError):
                file_offset = int(offset)
        tc = TrackerClient(self.tracker_pool)
        store_serv = tc.tracker_query_storage_update(group_name, appender_filename)
        store = StorageClient(store_serv.ip_addr, store_serv.port, self.timeout)
        return store.storage_modify_by_file(
            tc, store_serv, filename, file_offset, filesize, appender_filename
        )

    def modify_by_buffer(self, filebuffer, appender_fileid, offset=0):
        """
        Modify a file in Storage server by buffer.
        arguments:
        @filebuffer: string, file buffer
        @offset: long, file offset
        @appender_fileid: string, remote file id
        @return: dictionary {
            'Status'     : 'Modify successed.',
            'Storage IP' : storage_ip
        }
        """
        if not filebuffer:
            raise DataError("[-] Error: filebuffer can not be null.(modify)")
        filesize = len(filebuffer)
        tmp = split_remote_fileid(appender_fileid)
        if not tmp:
            raise DataError("[-] Error: remote_fileid is invalid.(modify)")
        group_name, appender_filename = tmp
        file_offset = 0
        if offset:
            with contextlib.suppress(TypeError, ValueError):
                file_offset = int(offset)
        tc = TrackerClient(self.tracker_pool)
        store_serv = tc.tracker_query_storage_update(group_name, appender_filename)
        store = StorageClient(store_serv.ip_addr, store_serv.port, self.timeout)
        return store.storage_modify_by_buffer(
            tc, store_serv, filebuffer, file_offset, filesize, appender_filename
        )

    @property
    def async_client(self) -> "AsyncDfsClient":
        return AsyncDfsClient(self.trackers, self.ip_mapping, self.ssl)

    async def upload(self, content: bytes, suffix=".jpg") -> str:
        return await self.async_client.upload(content, suffix)

    async def delete(self, file: str) -> tuple:
        return await self.async_client.delete(file)

    upload.__doc__ = AsyncDfsClient.upload.__doc__
    delete.__doc__ = AsyncDfsClient.delete.__doc__
