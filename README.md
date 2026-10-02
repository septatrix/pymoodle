# pyMoodle

A python client for Moodle web services still in development.

## Usage

`MoodleClient` (and its asynchronous counterpart `AsyncMoodleClient`)
provides a typed method for every webservice function of Moodle.
Results are returned as `TypedDict`s,
so type checkers and IDEs know which keys are available:

```python
from moodle.session import MoodleClient

with MoodleClient("https://moodle.example.com", "TOKEN") as client:
    info = client.core_webservice_get_site_info()
    print(info["sitename"])

    userid = info["userid"]
    # Moodle declares most return values as nullable, so they need to be checked.
    assert userid is not None
    for course in client.core_enrol_get_users_courses(userid=userid):
        print(course["fullname"])
```

The types of parameters and return values can be imported from `moodle.ws.types`,
e.g. `CoreWebserviceGetSiteInfoReturns`.
Functions which are not covered by the bindings
(e.g. from third-party plugins)
can be called using `client.webservice("function_name", {"param": "value"})`.

The bindings are generated from the source code of the latest Moodle LTS release.
See [`codegen/`](codegen/README.md) for how they are generated
and how to generate bindings for other Moodle versions or additional plugins.

## Development

The development tools are listed in the `dev` dependency group:

```sh
pip install -e . --group dev
ruff check && ruff format --check
mypy && pyright
python -m unittest discover tests
```
