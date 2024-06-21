"""Core exceptions raised by fastdfs client"""


class FDFSError(Exception):
    pass


class ConfigError(FDFSError):
    pass


class ConnectionError(FDFSError):
    pass


class ResponseError(FDFSError):
    pass


class InvaildResponse(FDFSError):
    pass


class DataError(FDFSError):
    pass


class ParsingError(FDFSError):
    pass


class MissingSectionHeaderError(FDFSError):
    pass
