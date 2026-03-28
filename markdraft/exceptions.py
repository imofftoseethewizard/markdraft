import errno


class AlreadyRunningError(RuntimeError):
    pass


class ReadmeNotFoundError(FileNotFoundError):
    """
    Raised when a README file cannot be found.
    """

    def __init__(self, path: str | None = None, message: str | None = None) -> None:
        self.path = path
        self.message = message
        super().__init__(errno.ENOENT, "README not found", path)

    def __repr__(self) -> str:
        return "{0}({1!r}, {2!r})".format(type(self).__name__, self.path, self.message)

    def __str__(self) -> str:
        if self.message:
            return self.message
        if self.path is not None:
            return "No README found at {0}".format(self.path)
        return self.strerror or "README not found"
