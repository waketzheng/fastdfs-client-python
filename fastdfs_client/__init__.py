import importlib.metadata as importlib_metadata

from .client import AsyncDfsClient, FastdfsClient

__version__ = importlib_metadata.version(__name__)
VERSION = tuple(map(int, __version__.split(".")))


__all__ = (
    "VERSION",
    "FastdfsClient",
    "AsyncDfsClient",
)
