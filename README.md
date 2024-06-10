# check-markdown-files

Run a pre-flight check on Markdown files before committing blog postings

## Usage

Run this script from inside your `git` repository with your blog Markdown files.

The script will attempt to find the file `check-markdown-files.conf` in the root of your repository, which includes your configuration.

## git Commit Hook

In order to use this script as `git commit` hook, you have to execute it from `.git/hooks/pre-commit`, or make this script a symlink (*Linux*/*Unix* only).

The following example assumes that you are currently in the root directory of your blog repository, and this repository is checked out next to your blog repository.

```
cd .git/hooks/ && ln -s ../check-markdown-files/check-markdown-files.py pre-commit && cd -
```

## Configuration

In `check-markdown-files.conf`, the following checks and config options are available. All checks are disabled by default, and can be enabled in the configuration file.

If a check is enabled, it applies to all Markdown files (global configuration). Most checks can be disabled on a local level, using flags in the `suppresswarnings` header in Frontmatter.

All available checks are listes in the [CHECKS](CHECKS.md) document.

## Write a new check

Add the following parts:
* Default in `read_config` in `check-markdown-files.py`
* Add the call for the check in `handle_markdown_file` in `check-markdown-files.py`
* Write the actual function for the check:
  * The function receives the following parameters
    * a copy of the config
    * the full content of the file, as currently in progress
    * the filename of the currently processed file
    * the Frontmatter header, from initial reading the file (not updated during the execution of the different tests)
  * The function returns the content of the file, potentially modified
* Add documentation in `CHECKS.md`
* Add one or more tests for the check in `tests/`
  * Add the test(s) in `tests.yml`

## Tests

All tests are found in the `tests/` directory, or a subdirectory. Tests are defined in the `tests.yml` file, and run by the `run-tests.py` script.

### Write a new test

Add the new test in `tests.yml`, as example:

```
new_test:
    rc_expected: 0
    cmdoptions: ""
    test_subdirectory: ""
    stdout_expected: False
    stderr_expected: False
    stdout_must_include: []
    stderr_must_include: []
    stdout_must_not_include: []
    stderr_must_not_include: []
```

The following options are available:

* `rc_expected`: This is the expected return code of `check-markdown-files.py` when running this test
* `cmdoptions`: Which additional options to use when running the test
* `test_subdirectory`: In which subdirectory under `tests` is the test
* `stdout_expected`: Does this test expect output on stdout - if this is set to false, and output is produced, this is an error
* `stderr_expected`: Does this test expect output on stderr - if this is set to false, and output is produced, this is an error
* `stdout_lines_expected`: how many lines are expected on stdout - if the number of lines differ, this is an error
* `stderr_lines_expected`: how many lines are expected on stderr - if the number of lines differ, this is an error
* `stdout_must_include`: list of strings which must appear in the stdout output
* `stderr_must_include`: list of strings which must appear in the stderr output
* `stdout_must_not_include`: list of strings which must not appear in the stdout output
* `stderr_must_not_include`: list of strings which must not appear in the stderr output

The following files are used:

* `tests/new_test.conf`: This is the configfile for the test, enable all tests which should run
* `tests/new_test.input`: If this file exist, it will overwrite `tests/new_test.md` before the test is run, also `tests/new_test.md` will be deleted afterwards
* `tests/new_test.md`: The Markdown file for this test
* `tests/new_test.expected`: If this file exists, the content is matched against `tests/new_test.md` after the test - if the files differ, this is an error
