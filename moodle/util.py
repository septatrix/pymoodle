from typing import Any, Dict


def flatten(data: dict, prefix: str = "") -> Dict[str, Any]:
    """
    Recursively flatten a dict into the representation used in Moodle/PHP.

    >>> flatten({"courseids": [1, 2, 3]})
    {'courseids[0]': 1, 'courseids[1]': 2, 'courseids[2]': 3}
    >>> flatten({"grades": [{"userid": 1, "grade": 1}]})
    {'grades[0][userid]': 1, 'grades[0][grade]': 1}
    >>> flatten({})
    {}
    """

    formatted_data = {}

    for key, value in data.items():
        new_key = f"{prefix}[{key}]" if prefix else key

        if isinstance(value, dict):
            formatted_data.update(flatten(value, prefix=new_key))
        elif isinstance(value, list):
            formatted_data.update(flatten(dict(enumerate(value)), prefix=new_key))
        else:
            formatted_data[new_key] = value

    return formatted_data
