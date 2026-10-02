from collections.abc import Mapping
from typing import Any, cast


def flatten(data: Mapping[Any, object], prefix: str = "") -> dict[str, Any]:
    """
    Recursively flatten a dict into the representation used in Moodle/PHP.

    >>> flatten({"courseids": [1, 2, 3]})
    {'courseids[0]': 1, 'courseids[1]': 2, 'courseids[2]': 3}
    >>> flatten({"grades": [{"userid": 1, "grade": 1}]})
    {'grades[0][userid]': 1, 'grades[0][grade]': 1}
    >>> flatten({})
    {}
    """

    formatted_data: dict[str, Any] = {}

    for key, value in data.items():
        new_key = f"{prefix}[{key}]" if prefix else str(key)

        if isinstance(value, dict):
            nested = cast("dict[Any, object]", value)
            formatted_data.update(flatten(nested, prefix=new_key))
        elif isinstance(value, list):
            items = cast("list[object]", value)
            formatted_data.update(flatten(dict(enumerate(items)), prefix=new_key))
        else:
            formatted_data[new_key] = value

    return formatted_data
