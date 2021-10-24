from typing import Optional


class MoodleException(Exception):
    pass


class WebserviceException(MoodleException):
    def __init__(
        self, exception: str, errorcode: str, message: str, debuginfo: Optional[str]
    ) -> None:
        super().__init__(exception, errorcode, message, debuginfo)
        self.exception = exception
        self.errorcode = errorcode
        self.message = message
        self.debuginfo = debuginfo
