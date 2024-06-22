#!/usr/bin/env python3

"""
Run set of tests for check-markdown-files.py
"""

# pylint: disable=C0209, C0301, C0302, W1202

import os
import sys
import logging
import argparse
import hashlib
import shutil
import subprocess
import yaml

logging.basicConfig(level = logging.INFO,
		    format = '%(levelname)s: %(message)s')


#######################################################################
# Config class

class Config:
    """
    Configuration class

    Methods:
    __init__(Config) -> Config: Constructor
    print_help(Config) -> None
    parse_parameters(Config) -> None
    read_config(Config) -> None
    files(Config) -> list[str]:
    """


    def __init__(self) -> None:
        """
        Initialize the Config class.
        """

        self.arguments = False
        self.argument_parser = False
        self.configfile = False
        self.config = False


    # print_help()
    #
    # print the help
    #
    # parameter:
    #  - self
    # return:
    #  none
    def print_help(self) -> None:
        """
        print the help
        """

        self.argument_parser.print_help()


    # parse_parameters()
    #
    # parse commandline parameters, fill in array with arguments
    #
    # parameter:
    #  - self
    # return:
    #  none
    def parse_parameters(self) -> None:
        """
        Parse commandline parameters, fill in array with arguments.
        """

        parser = argparse.ArgumentParser(description = 'Run tests for check-markdown-files.py',
                                         add_help = False)
        self.argument_parser = parser
        parser.add_argument('--help', default = False, dest = 'help', action = 'store_true', help = 'show this help')
        # store_true: store "True" if specified, otherwise store "False"
        # store_false: store "False" if specified, otherwise store "True"
        parser.add_argument('-v', '--verbose', default = False, dest = 'verbose', action = 'store_true', help = 'be more verbose')
        parser.add_argument('-q', '--quiet', default = False, dest = 'quiet', action = 'store_true', help = 'run quietly')
        parser.add_argument('-t', default = 'tests.yml', dest = 'testsfile', help = "file with test configuration")

        # parse parameters
        args = parser.parse_args()

        if args.help is True:
            self.print_help()
            sys.exit(0)

        if args.verbose is True and args.quiet is True:
            self.print_help()
            print("")
            print("Error: --verbose and --quiet can't be set at the same time")
            sys.exit(1)

        if args.verbose is True:
            logging.getLogger().setLevel(logging.DEBUG)

        if args.quiet is True:
            logging.getLogger().setLevel(logging.ERROR)

        if args.testsfile != "":
            # verify that the testsfile exists
            if not os.path.exists(args.testsfile) or not os.access(args.testsfile, os.W_OK):
                self.print_help()
                logging.error("Error: testsfile must exist and must be readable")
                sys.exit(1)

        self.arguments = args
        logging.debug("Commandline arguments successfuly parsed")

# end Config class
#######################################################################


# read_tests()
#
# read in the file with the tests configuration
#
# parameter:
#  - filename with tests
# return:
#  - yaml structure with tests
def read_tests(testsfile:str) -> yaml:
    """
    read in the file with the tests configuration
    """

    try:
        with open(testsfile, 'r', encoding="utf-8") as file:
            test_config = yaml.safe_load(file)
            return test_config
    except FileNotFoundError:
        print("Error: testsfile '{c}' not found!".format(c = testsfile))
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"Error: Can't parse testsfile: {e}")
        sys.exit(1)


# run_test()
#
# run a single test
#
# parameter:
#  - the name of the test
#  - the test configuration
#  - copy of the general configuration
# return:
#  - 0/1 (0: Test OK, 1: Test Failed)
def run_test(testname:str, testconfig:dict, config:Config) -> int: # pylint: disable=R0914, W0613, R0912, R0915
    """
    run a single test
    """

    try:
        rc_expected = testconfig['rc_expected']
    except KeyError:
        logging.error("Missing 'rc_expected' in test config: {c}".format(c = testname))
        sys.exit(1)

    try:
        cmdoptions = testconfig['cmdoptions']
    except KeyError:
        logging.debug("Set 'cmdoptions' to empty")
        cmdoptions = ""

    try:
        test_subdirectory = testconfig['test_subdirectory']
    except KeyError:
        logging.debug("Set 'test_subdirectory' to empty")
        test_subdirectory = ""

    try:
        stdout_expected = testconfig['stdout_expected']
    except KeyError:
        logging.debug("Set 'stderr_expected' to False")
        stderr_expected = False

    try:
        stderr_expected = testconfig['stderr_expected']
    except KeyError:
        logging.debug("Set 'stderr_expected' to False")
        stderr_expected = False

    try:
        stdout_must_include = testconfig['stdout_must_include']
    except KeyError:
        logging.debug("Set 'stdout_must_include' to []")
        stdout_must_include = []
    if not isinstance(stdout_must_include, list):
        logging.error("'stdout_must_include' must be a list in test config: {c}".format(c = testname))
        sys.exit(1)

    try:
        stderr_must_include = testconfig['stderr_must_include']
    except KeyError:
        logging.debug("Set 'stderr_must_include' to []")
        stderr_must_include = []
    if not isinstance(stderr_must_include, list):
        logging.error("'stderr_must_include' must be a list in test config: {c}".format(c = testname))
        sys.exit(1)

    try:
        stdout_must_not_include = testconfig['stdout_must_not_include']
    except KeyError:
        logging.debug("Set 'stdout_must_not_include' to []")
        stdout_must_not_include = []
    if not isinstance(stdout_must_not_include, list):
        logging.error("'stdout_must_not_include' must be a list in test config: {c}".format(c = testname))
        sys.exit(1)

    try:
        stderr_must_not_include = testconfig['stderr_must_not_include']
    except KeyError:
        logging.debug("Set 'stderr_must_not_include' to []")
        stderr_must_not_include = []
    if not isinstance(stderr_must_not_include, list):
        logging.error("'stderr_must_not_include' must be a list in test config: {c}".format(c = testname))
        sys.exit(1)

    if stdout_expected:
        try:
            stdout_lines_expected = testconfig['stdout_lines_expected']
        except KeyError:
            logging.error("'stdout_lines_expected' must be set in test config: {c}".format(c = testname))
            sys.exit(1)

        try:
            stdout_lines_expected = int(stdout_lines_expected)
        except ValueError:
            logging.error("'stdout_lines_expected' must be an integer in test config: {c}".format(c = testname))
            sys.exit(1)

        if len(stdout_must_include) == 0:
            logging.error("'stdout_must_include' can't be empty in test config: {c}".format(c = testname))
            sys.exit(1)

    if stderr_expected:
        try:
            stderr_lines_expected = testconfig['stderr_lines_expected']
        except KeyError:
            logging.error("'stderr_lines_expected' must be set in test config: {c}".format(c = testname))
            sys.exit(1)

        try:
            stderr_lines_expected = int(stderr_lines_expected)
        except ValueError:
            logging.error("'stderr_lines_expected' must be an integer in test config: {c}".format(c = testname))
            sys.exit(1)

        if len(stderr_must_include) == 0:
            logging.error("'stderr_must_include' can't be empty in test config: {c}".format(c = testname))
            sys.exit(1)


    if test_subdirectory == "":
        md_file = os.path.join("tests", "{t}.md".format(t = testname))
        conf_file = os.path.join("tests", "{t}.conf".format(t = testname))
        input_file = os.path.join("tests", "{t}.input".format(t = testname))
        expected_file = os.path.join("tests", "{t}.expected".format(t = testname))
    else:
        md_file = os.path.join("tests", test_subdirectory, "{t}.md".format(t = testname))
        conf_file = os.path.join("tests", test_subdirectory, "{t}.conf".format(t = testname))
        input_file = os.path.join("tests", test_subdirectory, "{t}.input".format(t = testname))
        expected_file = os.path.join("tests", test_subdirectory, "{t}.expected".format(t = testname))

    if os.path.exists(input_file):
        # if the input file exists, this is the gold copy for this test
        # the test is expected to change the .md file
        shutil.copy(input_file, md_file)

    if len(cmdoptions) > 0:
        run_options = cmdoptions.split(" ")
    else:
        run_options = []
    run_cmd = ["python3", "check-markdown-files.py"]
    if len(run_options):
        run_cmd.extend(run_options)
    run_cmd.extend(["-c", conf_file])
    run_cmd.append(md_file)
    logging.debug("Run command: {c}".format(c = " ".join(run_cmd)))
    result = subprocess.run(run_cmd, capture_output = True, text = True) # pylint: disable=W1510
    has_error = False
    error_lines = []
    if result.returncode != rc_expected:
        has_error = True
        error_lines.append("Expected RC {rc1}, got {rc2}".format(rc1 = rc_expected, rc2 = result.returncode))

    if len(result.stdout) > 0 and not stdout_expected:
        has_error = True
        error_lines.append("Expected no stdout, got:")
        error_lines.append(result.stdout.strip())
    elif stdout_expected:
        lines_stdout = len(result.stdout.splitlines())
        if lines_stdout != stdout_lines_expected:
            has_error = True
            error_lines.append("Expected {l1} lines in stdout, got {l2}".format(l1 = stdout_lines_expected, l2 = lines_stdout))

    if len(result.stderr) > 0 and not stderr_expected:
        has_error = True
        error_lines.append("Expected no stderr, got:")
        error_lines.append(result.stderr.strip())
    elif stderr_expected:
        lines_stderr = len(result.stderr.splitlines())
        if lines_stderr != stderr_lines_expected:
            has_error = True
            error_lines.append("Expected {l1} lines in stderr, got {l2}".format(l1 = stderr_lines_expected, l2 = lines_stderr))

    if len(stdout_must_include) > 0:
        for l in stdout_must_include:
            if l not in result.stdout:
                has_error = True
                error_lines.append("Missing string in stdout: {l}".format(l = l))

    if len(stderr_must_include) > 0:
        for l in stderr_must_include:
            if l not in result.stderr:
                has_error = True
                error_lines.append("Missing string in stderr: {l}".format(l = l))

    if len(stdout_must_not_include) > 0:
        for l in stdout_must_not_include:
            if l in result.stdout:
                has_error = True
                error_lines.append("Forbidden string appears in stdout: {l}".format(l = l))

    if len(stderr_must_not_include) > 0:
        for l in stderr_must_not_include:
            if l in result.stderr:
                has_error = True
                error_lines.append("Forbidden string appears in stderr: {l}".format(l = l))

    if os.path.exists(expected_file):
        with open(md_file, "rb") as f:
            bytes_md = f.read()
            hash_md = hashlib.sha256(bytes_md).hexdigest()

        with open(expected_file, "rb") as f:
            bytes_expected = f.read()
            hash_expected = hashlib.sha256(bytes_expected).hexdigest()

        if hash_md != hash_expected:
            has_error = True
            error_lines.append("Output file differs from Expected file")
            # consider printing the diff

    if os.path.exists(input_file):
        try:
            # remove the work copy
            os.unlink(md_file)
        except FileNotFoundError:
            pass

    if has_error: # pylint: disable=R1705
        logging.error("Error in test: {t}.md".format(t = testname))
        for l in error_lines:
            logging.error(l)
        return 1
    else:
        return 0




if __name__ == "__main__":
    confighandle = Config()
    confighandle.parse_parameters()
    tests = read_tests(confighandle.arguments.testsfile)

    fail_count = 0
    ok_count = 0
    for this_testname in tests:
        logging.info("Running test: {t}".format(t = this_testname))
        rc = run_test(this_testname, tests[this_testname], confighandle)
        if rc == 0:
            logging.info("  Test OK")
            ok_count += 1
        else:
            logging.info("  Test FAIL")
            fail_count += 1
        if confighandle.arguments.quiet is False:
            print("")

    print("Tests:      {c}".format(c = len(tests)))
    print("Tests OK:   {c}".format(c = ok_count))
    print("Tests FAIL: {c}".format(c = fail_count))

    if fail_count > 0:
        sys.exit(1)
    else:
        sys.exit(0)
