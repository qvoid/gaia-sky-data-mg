class GaiaSkyDataError(Exception):
    pass


class ConfigError(GaiaSkyDataError):
    pass


class DescriptorFetchError(GaiaSkyDataError):
    pass


class DescriptorParseError(GaiaSkyDataError):
    pass


class DatasetNotFoundError(GaiaSkyDataError):
    pass


class DownloadError(GaiaSkyDataError):
    pass


class ChecksumMismatchError(DownloadError):
    def __init__(self, expected, actual):
        self.expected = expected
        self.actual = actual
        super().__init__(f"Checksum mismatch: expected {expected}, got {actual}")


class ExtractionError(GaiaSkyDataError):
    pass
