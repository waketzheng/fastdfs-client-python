import os
import random
import socket
from contextlib import contextmanager
from itertools import chain
from typing import Generator

from .exceptions import ConnectionError
from .utils import logger


class Connection:
    """Manage TCP comunication to and from Fastdfs Server."""

    def __init__(self, host_tuple, port, timeout, **kwargs) -> None:
        self.host_tuple = host_tuple
        self.remote_port = port
        self.timeout = timeout
        self.pid = os.getpid()
        self.remote_addr = None
        self._sock = None

    def __del__(self):
        try:
            self.disconnect()
        except Exception as e:
            logger.debug(f"disconnect error: {e}")

    def connect(self):
        """Connect to fdfs server."""
        if self._sock:
            return
        try:
            sock = self._connect()
        except socket.error as e:
            raise ConnectionError(self._errormessage(e))
        self._sock = sock
        # print '[+] Create a connection success.'
        # print '\tLocal address is %s:%s.' % self._sock.getsockname()
        # print '\tRemote address is %s:%s' % (self.remote_addr, self.remote_port)

    def _connect(self):
        """Create TCP socket. The host is random one of host_tuple."""
        self.remote_addr = random.choice(self.host_tuple)
        # print '[+] Connecting... remote: %s:%s' % (self.remote_addr, self.remote_port)
        # sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # sock.settimeout(self.timeout)
        sock = socket.create_connection(
            (self.remote_addr, self.remote_port), self.timeout
        )
        return sock

    def disconnect(self) -> None:
        """Disconnect from fdfs server."""
        if self._sock is None:
            return
        try:
            self._sock.close()
        except socket.error as e:
            raise ConnectionError(self._errormessage(e))
        self._sock = None

    def get_sock(self):
        return self._sock

    def _errormessage(self, exception) -> str:
        # args for socket.error can either be (errno, "message")
        # or just "message" '''
        if len(exception.args) == 1:
            return "[-] Error: connect to %s:%s. %s." % (
                self.remote_addr,
                self.remote_port,
                exception.args[0],
            )
        else:
            return "[-] Error: %s connect to %s:%s. %s." % (
                exception.args[0],
                self.remote_addr,
                self.remote_port,
                exception.args[1],
            )


class ConnectionPool:
    """Generic Connection Pool"""

    def __init__(
        self, name="", conn_class=Connection, max_conn=None, **conn_kwargs
    ) -> None:
        self.pool_name = name
        self.pid = os.getpid()
        self.conn_class = conn_class
        self.max_conn = max_conn or 2**31
        self.conn_kwargs = conn_kwargs
        self._init()

    def _init(self) -> None:
        self._conns_created = 0
        self._conns_available: list[Connection] = []
        self._conns_inuse: set[Connection] = set()

    def _check_pid(self) -> None:
        if self.pid != os.getpid():
            self.destroy()
            self._init()

    def make_conn(self) -> Connection:
        """Create a new connection."""
        if self._conns_created >= self.max_conn:
            raise ConnectionError("[-] Error: Too many connections.")
        num_try = 10
        for _ in range(num_try):
            try:
                conn_instance = self.conn_class(**self.conn_kwargs)
                conn_instance.connect()
                self._conns_created += 1
                break
            except ConnectionError as e:
                logger.debug(e)
        else:
            raise ConnectionError(f"Failed to connect with {num_try} times")
        return conn_instance

    def get_connection(self) -> Connection:
        """Get a connection from pool."""
        self._check_pid()
        try:
            conn = self._conns_available.pop()
            # print '[+] Get a connection from pool %s.' % self.pool_name
            # print '\tLocal address is %s:%s.' % conn._sock.getsockname()
            # print '\tRemote address is %s:%s' % (conn.remote_addr, conn.remote_port)
        except IndexError:
            conn = self.make_conn()
        self._conns_inuse.add(conn)
        return conn

    @contextmanager
    def open_connection(self) -> Generator[Connection, None, None]:
        conn = self.get_connection()
        try:
            yield conn
        finally:
            self.release(conn)

    def remove(self, conn) -> None:
        """Remove connection from pool."""
        if conn in self._conns_inuse:
            self._conns_inuse.remove(conn)
            self._conns_created -= 1
        if conn in self._conns_available:
            self._conns_available.remove(conn)
            self._conns_created -= 1

    def destroy(self) -> None:
        """Disconnect all connections in the pool."""
        all_conns = chain(self._conns_inuse, self._conns_available)
        for conn in all_conns:
            conn.disconnect()
            # print '[-] Destroy connection pool %s.' % self.pool_name

    def release(self, conn) -> None:
        """Release the connection back to the pool."""
        self._check_pid()
        if conn.pid == self.pid:
            self._conns_inuse.remove(conn)
            self._conns_available.append(conn)
            # print '[-] Release connection back to pool %s.' % self.pool_name


def tcp_recv_response(conn, bytes_size, buffer_size=4096) -> tuple[bytes, int]:
    """Receive response from server.
    It is not include tracker header.
    arguments:
    @conn: connection
    @bytes_size: int, will be received byte_stream size
    @buffer_size: int, receive buffer size
    @Return: tuple,(response, received_size)
    """
    recv_buff = []
    total_size = 0
    try:
        while bytes_size > 0:
            resp = conn._sock.recv(buffer_size)
            recv_buff.append(resp)
            total_size += len(resp)
            bytes_size -= len(resp)
    except (socket.error, socket.timeout) as e:
        raise ConnectionError("[-] Error: while reading from socket: (%s)" % e.args)
    return (b"".join(recv_buff), total_size)


def tcp_send_data(conn, bytes_stream) -> None:
    """Send buffer to server.
    It is not include tracker header.
    arguments:
    @conn: connection
    @bytes_stream: trasmit buffer
    @Return bool
    """
    try:
        conn._sock.sendall(bytes_stream)
    except (socket.error, socket.timeout) as e:
        raise ConnectionError("[-] Error: while writting to socket: (%s)" % e.args)
