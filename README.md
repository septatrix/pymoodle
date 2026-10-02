# pyMoodle

A python client for Moodle web services still in development.

## Development

The development tools are listed in the `dev` dependency group:

```sh
pip install -e . --group dev
ruff check && ruff format --check
mypy && pyright
python -m unittest discover tests
```
