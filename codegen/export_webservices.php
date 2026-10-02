<?php
// This file is part of pymoodle - https://github.com/septatrix/pymoodle
// SPDX-License-Identifier: MIT

/**
 * Export the definitions of all Moodle webservice functions as JSON.
 *
 * Usage: php export_webservices.php [--output=FILE] /path/to/moodle
 *
 * Supports Moodle 4.2 and newer (tested with 4.5 and 5.1).
 *
 * The script only requires a checkout of the Moodle source code
 * (including any additional plugins one wants to export).
 * No installed Moodle instance, database, or webserver is necessary:
 * Moodle is bootstrapped only up to the point where it would connect to the database,
 * a stub database answering "nothing found" is put in place,
 * and the function definitions are then read from all `db/services.php` files
 * and resolved using `external_api::external_function_info()`,
 * i.e. the same code Moodle uses to e.g. generate its API documentation.
 *
 * Caveat: A few functions derive default values (or, rarely, parts of their structure)
 * from the site configuration, which is not available.
 * These will use the values Moodle falls back to when a setting is unset.
 */

const FORMAT_VERSION = 1;

// ---------------------------------------------------------------------------
// Command line handling.
// ---------------------------------------------------------------------------

if (PHP_SAPI !== 'cli') {
    exit("This script must be run from the command line.\n");
}

$options = getopt('ho:', ['help', 'output:'], $restindex);
$positional = array_slice($argv, $restindex);
if (isset($options['h']) || isset($options['help']) || count($positional) !== 1) {
    fwrite(STDERR, "Usage: php {$argv[0]} [--output=FILE] /path/to/moodle\n");
    exit(isset($options['h']) || isset($options['help']) ? 0 : 2);
}
$outputfile = $options['output'] ?? $options['o'] ?? null;

$moodleroot = realpath($positional[0]);
if ($moodleroot === false) {
    fwrite(STDERR, "Moodle directory {$positional[0]} does not exist.\n");
    exit(2);
}
// Moodle 5.1 moved all web-accessible code into a public/ subdirectory.
$setupfile = null;
foreach (["$moodleroot/public/lib/setup.php", "$moodleroot/lib/setup.php"] as $candidate) {
    if (file_exists($candidate)) {
        $setupfile = $candidate;
        break;
    }
}
if ($setupfile === null) {
    fwrite(STDERR, "$moodleroot does not look like a Moodle checkout.\n");
    exit(2);
}

// ---------------------------------------------------------------------------
// Bootstrap Moodle without a database.
// ---------------------------------------------------------------------------

define('CLI_SCRIPT', true);
// Makes lib/setup.php return right after the configuration and autoloader are set up,
// i.e. before the database connection is established.
define('ABORT_AFTER_CONFIG', true);
define('CACHE_DISABLE_ALL', true);
define('NO_DEBUG_DISPLAY', false);

$dataroot = sys_get_temp_dir() . '/pymoodle-export-dataroot-' . getmypid();
if (!is_dir($dataroot) && !mkdir($dataroot, 0700, true)) {
    fwrite(STDERR, "Could not create temporary dataroot $dataroot.\n");
    exit(1);
}
register_shutdown_function(function () use ($dataroot) {
    // Moodle may cache some files in the dataroot, so remove it recursively.
    $it = new RecursiveIteratorIterator(
        new RecursiveDirectoryIterator($dataroot, FilesystemIterator::SKIP_DOTS),
        RecursiveIteratorIterator::CHILD_FIRST,
    );
    foreach ($it as $file) {
        $file->isDir() ? rmdir($file->getPathname()) : unlink($file->getPathname());
    }
    rmdir($dataroot);
});

global $CFG, $DB;
$CFG = new stdClass();
$CFG->dirroot = dirname($setupfile, 2);
$CFG->wwwroot = 'https://moodle.invalid';
$CFG->dataroot = $dataroot;
$CFG->dbtype = 'pgsql';
$CFG->dblibrary = 'native';
$CFG->prefix = 'mdl_';
$CFG->lang = 'en';
$CFG->debug = E_ALL;
$CFG->debugdisplay = 1;

require($setupfile);

// Load the standard libraries which lib/setup.php would have loaded next.
// The list differs between Moodle versions, so it is extracted from setup.php itself.
$setupsource = file_get_contents($setupfile);
$setupsource = substr($setupsource, strpos($setupsource, "defined('ABORT_AFTER_CONFIG')"));
preg_match_all('#^require_once\(\$CFG->libdir\s*\.\s*[\'"]/([\w/]+\.php)[\'"]\);#m', $setupsource, $matches);
if (!in_array('setuplib.php', $matches[1])) {
    fwrite(STDERR, "Could not determine standard libraries from $setupfile.\n");
    exit(1);
}
foreach ([...$matches[1], 'externallib.php'] as $lib) {
    require_once("{$CFG->libdir}/{$lib}");
}

// Values which would normally be initialised from the database.
define('SYSCONTEXTID', 1);
define('SITEID', 1);
$CFG->siteidentifier = 'pymoodle-export';
$CFG->config_php_settings = [];
$CFG->forced_plugin_settings = [];
$CFG->debugdeveloper = false;

/**
 * Stand-in for the database which pretends that every table is empty.
 *
 * Function descriptions mostly only query the configuration,
 * for which "not set" is a sensible answer.
 */
class pymoodle_stub_database {
    public function __call($name, $arguments) {
        if (str_starts_with($name, 'get_records') || str_starts_with($name, 'get_fieldset')) {
            return [];
        }
        if (str_starts_with($name, 'get_recordset')) {
            return new ArrayIterator([]);
        }
        if (str_starts_with($name, 'count_records')) {
            return 0;
        }
        return false;
    }
}
$DB = new pymoodle_stub_database();

// ---------------------------------------------------------------------------
// Serialisation.
// ---------------------------------------------------------------------------

/**
 * Convert an external_description into a JSON-serialisable array.
 *
 * Classes are detected by their properties instead of their names,
 * so plugins may define their own subclasses (like external_files does).
 */
function pymoodle_export_description($desc): ?array {
    if ($desc === null) {
        return null;
    }

    $result = [];
    if (property_exists($desc, 'type')) {
        $result['kind'] = 'value';
        $result['type'] = $desc->type;
    } else if (property_exists($desc, 'keys')) {
        $result['kind'] = 'single';
    } else if (property_exists($desc, 'content')) {
        $result['kind'] = 'multiple';
    } else {
        throw new coding_exception('Unknown external_description: ' . get_class($desc));
    }

    $result['desc'] = (string) $desc->desc;
    $result['required'] = match ($desc->required) {
        VALUE_REQUIRED => 'required',
        VALUE_OPTIONAL => 'optional',
        VALUE_DEFAULT => 'default',
        default => throw new coding_exception('Invalid required value: ' . var_export($desc->required, true)),
    };
    if ($desc->required === VALUE_DEFAULT) {
        $result['default'] = $desc->default;
    }
    $result['allownull'] = (bool) $desc->allownull;

    // Remember well-known specialisations, as a generator may want to reuse a single type for them.
    $class = (new ReflectionClass($desc))->getShortName();
    if (!in_array($class, ['external_value', 'external_single_structure', 'external_multiple_structure'])) {
        $result['class'] = $class;
    }

    if ($result['kind'] === 'single') {
        $keys = [];
        foreach ($desc->keys as $name => $subdesc) {
            $keys[$name] = pymoodle_export_description($subdesc);
        }
        // Cast to object so empty structures are encoded as {} instead of [].
        $result['keys'] = (object) $keys;
    } else if ($result['kind'] === 'multiple') {
        $result['content'] = pymoodle_export_description($desc->content);
    }

    return $result;
}

// ---------------------------------------------------------------------------
// Export.
// ---------------------------------------------------------------------------

if (!class_exists(\core_external\external_api::class)) {
    fwrite(STDERR, "Moodle 4.2 or newer is required.\n");
    exit(1);
}

$components = core_component::get_component_list();
// The core component itself is not part of the list.
$components['core']['core'] = $CFG->libdir;

// Collect warnings instead of printing them, so they can be attributed to a function.
$warnings = [];
// Paths are made relative to the Moodle root so the output does not depend on its location.
$relativepath = fn(string $path): string => str_replace("$moodleroot/", '', $path);
set_error_handler(function ($errno, $errstr, $errfile, $errline) use (&$warnings, $relativepath) {
    $warnings[] = "$errstr in {$relativepath($errfile)}:$errline";
    return true;
});

$exported = [];
$errors = [];
$functionwarnings = [];
foreach ($components as $plugintype => $plugins) {
    foreach ($plugins as $component => $directory) {
        $servicesfile = "$directory/db/services.php";
        if ($directory === null || !file_exists($servicesfile)) {
            continue;
        }

        $functions = [];
        include($servicesfile);

        foreach ($functions as $name => $definition) {
            // Apply the same defaults as external_update_descriptions() in lib/upgradelib.php.
            $function = (object) array_merge(
                ['methodname' => 'execute', 'classpath' => null],
                $definition,
                ['name' => $name, 'component' => $component],
            );

            $warnings = [];
            ob_start();
            try {
                $info = \core_external\external_api::external_function_info($function);
                $exported[$name] = [
                    'component' => $component,
                    'classname' => $info->classname,
                    'methodname' => $info->methodname,
                    'description' => $info->description,
                    'type' => $info->type ?? 'read',
                    'ajax' => (bool) ($definition['ajax'] ?? false),
                    'loginrequired' => (bool) ($definition['loginrequired'] ?? true),
                    'readonlysession' => (bool) ($definition['readonlysession'] ?? false),
                    'capabilities' => $definition['capabilities'] ?? '',
                    'services' => $definition['services'] ?? [],
                    'deprecated' => (bool) ($info->deprecated ?? false),
                    'parameters' => pymoodle_export_description($info->parameters_desc),
                    'returns' => pymoodle_export_description($info->returns_desc),
                ];
            } catch (Throwable $e) {
                $errors[$name] = get_class($e) . ': ' . $e->getMessage()
                    . " in {$relativepath($e->getFile())}:{$e->getLine()}";
            }
            $output = trim(ob_get_clean());
            if ($output !== '') {
                $warnings[] = $output;
            }
            if ($warnings) {
                $functionwarnings[$name] = array_values(array_unique($warnings));
            }
        }
    }
}
restore_error_handler();

ksort($exported);
ksort($errors);
ksort($functionwarnings);

// Read the version information without polluting the global scope.
$versioninfo = (function () use ($CFG) {
    require("{$CFG->dirroot}/version.php");
    return ['version' => (string) $version, 'release' => $release, 'branch' => $branch];
})();

$json = json_encode(
    [
        'format_version' => FORMAT_VERSION,
        'moodle' => $versioninfo,
        'functions' => (object) $exported,
        'errors' => (object) $errors,
        'warnings' => (object) $functionwarnings,
    ],
    JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_PRESERVE_ZERO_FRACTION
        | JSON_THROW_ON_ERROR,
) . "\n";

if ($outputfile === null) {
    echo $json;
} else if (file_put_contents($outputfile, $json) === false) {
    fwrite(STDERR, "Could not write to $outputfile.\n");
    exit(1);
}

fwrite(STDERR, sprintf(
    "Exported %d functions from Moodle %s (%d errors, %d with warnings).\n",
    count($exported), $versioninfo['release'], count($errors), count($functionwarnings),
));
exit($errors ? 1 : 0);
