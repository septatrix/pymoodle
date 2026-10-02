# Code generation

The webservice API of Moodle is described by the Moodle source code itself:
every component lists its functions in `db/services.php`,
and each function has accompanying `*_parameters()` and `*_returns()` methods
which describe its arguments and results
using `external_value`, `external_single_structure`, and `external_multiple_structure`.

Generating typed bindings is split into two steps:

1. `export_webservices.php` extracts these descriptions from a Moodle checkout
   and serializes them to JSON.
2. `generate.py` converts the JSON into the typed Python code in `moodle/ws/`.

To regenerate the bindings, e.g. for a new Moodle release, run:

```sh
git clone --depth 1 --branch MOODLE_405_STABLE https://github.com/moodle/moodle.git /tmp/moodle
php codegen/export_webservices.php --output=/tmp/webservices.json /tmp/moodle
python codegen/generate.py /tmp/webservices.json
```

The shipped bindings target the latest Moodle LTS release.
To get bindings matching another Moodle version or including additional plugins,
run the same steps against the respective checkout.

## Exporting the webservice definitions

Only PHP (8.0 or newer, whatever the Moodle version requires) and a checkout of the Moodle source code are required.
In particular, there is no need to install Moodle, set up a database, or run a webserver:

```sh
git clone --depth 1 --branch MOODLE_405_STABLE https://github.com/moodle/moodle.git
php codegen/export_webservices.php --output=webservices.json moodle
```

Moodle 4.2 and newer are supported.
Third-party plugins are exported as well if they are placed into the checkout.

The script bootstraps Moodle only up to the point where it would connect to the database
(using the `ABORT_AFTER_CONFIG` mechanism Moodle provides for lightweight scripts),
loads the standard libraries,
and installs a stub database which pretends that every table is empty.
It then resolves every function listed in a `db/services.php`
using `external_api::external_function_info()`,
which is the same code Moodle uses for its built-in API documentation.

A few function descriptions depend on the site configuration,
which is not available.
For these, the values Moodle uses when a setting is unset are exported.
This mostly affects default values of parameters
(e.g. the defaults of `core_course_create_courses`).
Any PHP warnings emitted while describing a function
are recorded in the output for reference.
Furthermore, `core_calendar_create_calendar_events` uses the current time as a default value,
so this value changes with every export.

### Output format

```jsonc
{
  "format_version": 1,
  "moodle": {"version": "2024100714.03", "release": "4.5.14+ (Build: 20261002)", "branch": "405"},
  "functions": {
    "core_webservice_get_site_info": {
      "component": "core",
      "classname": "core_webservice_external",
      "methodname": "get_site_info",
      "description": "Return some site info / user info / list web service functions",
      "type": "read",              // "read" or "write"
      "ajax": false,               // callable via lib/ajax/service.php
      "loginrequired": true,
      "readonlysession": false,
      "capabilities": "",
      "services": ["moodle_mobile_app"],
      "deprecated": false,
      "parameters": { /* description, always of kind "single" */ },
      "returns": { /* description, or null if the function returns nothing */ }
    }
  },
  "errors": { /* function name -> error message, for functions which could not be exported */ },
  "warnings": { /* function name -> list of PHP warnings emitted while describing it */ }
}
```

Functions are sorted by name and the keys of structures retain their order from the Moodle source.
Each description has the following fields:

| Field       | Description                                                                                 |
| ----------- | ------------------------------------------------------------------------------------------- |
| `kind`      | `"value"` (scalar), `"single"` (object with fixed keys), or `"multiple"` (list)             |
| `desc`      | Human readable description                                                                  |
| `required`  | `"required"`, `"optional"` (may be omitted), or `"default"` (Moodle fills in `default`)    |
| `default`   | Default value, only present if `required` is `"default"`                                    |
| `allownull` | Whether `null` is accepted/returned                                                         |
| `class`     | Name of the PHP class if it is a well-known specialization, e.g. `external_warnings`        |
| `type`      | Only for values: the `PARAM_*` type, e.g. `"int"`, `"bool"`, `"raw"`, or `"alphanumext"`    |
| `keys`      | Only for single structures: mapping of key names to descriptions                            |
| `content`   | Only for multiple structures: description of the list items                                 |

## Generating Python code

`generate.py` writes the following modules to `moodle/ws/` (or the directory given with `--output-dir`)
and formats them using ruff:

- `types.py` contains a `TypedDict` for every structure in the parameters and return values.
  They are named after the function and the path to the structure,
  e.g. `CoreWebserviceGetSiteInfoReturns` or `CoreCourseGetCoursesParamsOptions`.
  `{Function}Returns` always names the return type of a function,
  as an alias if it is a list (whose items are named `{Function}ReturnsItem`) or a scalar.
  The items of `external_warnings` and `external_files` are shared as `ExternalWarning` and `ExternalFile`.
- `methods.py` contains the `WebserviceMethods` and `AsyncWebserviceMethods` mixins,
  which have one method per function and are inherited by `MoodleClient` and `AsyncMoodleClient`.
  All arguments are keyword-only.
  Arguments which are Python keywords get a trailing underscore (e.g. `from_`).
  Optional arguments default to `None`, in which case they are not sent and Moodle applies its default.
  The types module is only imported when type checking,
  as creating all TypedDicts would noticeably slow down importing pymoodle.
- `__init__.py` contains the version of Moodle the bindings were generated from.

The types reflect how Moodle validates parameters and return values:

| Moodle                                     | Parameters                                   | Return values                                       |
| ------------------------------------------ | -------------------------------------------- | --------------------------------------------------- |
| `VALUE_REQUIRED`                           | required key                                 | required key                                        |
| `VALUE_OPTIONAL`                           | `NotRequired`                                | `NotRequired`                                       |
| `VALUE_DEFAULT`                            | `NotRequired`                                | required for values, `NotRequired` for structures   |
| `NULL_ALLOWED`                             | ignored, `null` cannot be sent via REST      | `Optional`                                          |
| `PARAM_INT`, `PARAM_FLOAT`, `PARAM_BOOL`   | `int`, `float`, `bool`                       | `int`, `float`, `bool`                              |
| any other `PARAM_*`                        | `str`                                        | `str`                                               |

Note that `external_value` allows `null` by default,
so most scalar return values are typed as `Optional` even though Moodle rarely returns `null` for them.
Furthermore, `PARAM_RAW` technically passes through non-string values unchanged,
but values read from the database are always strings in Moodle.
