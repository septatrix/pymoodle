from enum import IntEnum, unique


@unique
class LoginType(IntEnum):
    LOGIN_VIA_APP = 1
    LOGIN_VIA_BROWSER = 2
    LOGIN_VIA_EMBEDDED_BROWSER = 3


@unique
class TextFormat(IntEnum):
    MOODLE = 0
    HTML = 1
    PLAIN_TEXT = 2
    MARKDOWN = 4
