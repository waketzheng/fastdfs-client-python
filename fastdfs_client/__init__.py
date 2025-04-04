from .client import AsyncDfsClient, FastdfsClient

__version__ = "1.2.3"
VERSION = tuple(map(int, __version__.split(".")))


__all__ = (
    "VERSION",
    "FastdfsClient",
    "AsyncDfsClient",
)
