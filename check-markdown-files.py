#!/usr/bin/env python3

"""
Check Markdown files for blog postings for common errors
"""

# pylint: disable=C0209, C0301, C0302, W1202

# run pre-flight checks on Markdown postings
# before committing the blog postings into git
# can be used standalone to check blog postings

import os
import sys
import re
from pathlib import Path
import logging
import argparse
from typing import Optional, Dict, Any
import subprocess

import json
import yaml


# start with 'info', can be overriden by '-q' later on
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

log_entries = []


#######################################################################
# Config class

class Config:
    """
    Configuration class

    Methods:
    __init__(Config) -> Config: Constructor
    find_configfile(Config, this_dir(str))
    parse_parameters(Config) -> None
    read_config(Config) -> None
    files(Config) -> list[str]:
    """

    def __init__(self) -> None:
        """
        Initialize the Config class.
        """

        self.arguments: Optional[argparse.Namespace] = None
        self.argument_parser: Optional[argparse] = None
        self.configfile: Optional[Path] = None
        self.configfile_stat: Optional[os.stat_result] = None
        self.config_contents: Optional[str] = None
        self.checks: Dict[str, Any] = {}


    def find_configfile(self, this_dir: Optional[Path] = None) -> Optional[Path]:
        """
        Searches for ``check-markdown-files.conf`` tree-upwards

        Searches for ``check-markdown-files.conf`` tree-upwards,
        starting in ``this_dir``, stops when it finds a ``.git`` directory or reaches ``/``.
        If ``this_dir`` is None, it starts from ``os.getcwd()``.

        Returns:
            str: a ``Path`` to the config file, or ``None`` if no config file can be found.
        """
        if this_dir is None:
            this_dir = os.getcwd()
        logging.debug("Checking {d} for configfile".format(d=this_dir))

        this_dir = Path(this_dir)
        configname = Path("check-markdown-files.conf")

        for d in [this_dir] + list(this_dir.parents):  # Check from the current dir upwards
            this_file = (d / configname).resolve()
            if this_file.is_file():
                logging.debug("Found configfile: {f}".format(f=this_file))
                return this_file

            this_git = d / ".git"
            if this_git.is_dir():
                logging.debug("Found .git dir in {d}, stop searching for configfile".format(d=this_dir))
                return None

        logging.error("Reached root directory, stopping search for configfile")

        return None


    def parse_parameters(self) -> None: # pylint: disable=R0915, R0912
        """
        Parse commandline parameters, fill in array with arguments.
        """

        parser = argparse.ArgumentParser(description='Check Markdown files before publishing blog postings',
                                         add_help=False)
        self.argument_parser = parser
        parser.add_argument('--help', '-h', default=False, dest='help', action='store_true', help='show this help')
        # store_true: store "True" if specified, otherwise store "False"
        # store_false: store "False" if specified, otherwise store "True"
        parser.add_argument('-v', '--verbose', default=False, dest='verbose', action='store_true', help='be more verbose')
        parser.add_argument('-q', '--quiet', default=False, dest='quiet', action='store_true', help='run quietly')
        parser.add_argument('-c', default='', dest='configfile', help="configuration file (default: 'check-markdown-files.conf in repository')")
        parser.add_argument('-a', '--all', default=False, dest='all', action='store_true', help="run on all files, not only newer files")
        parser.add_argument('-n', default=False, dest='dry_run', action='store_true', help='dry-run (don\'t change anything)')
        parser.add_argument('-r', default=False, dest='replace_quotes', action='store_true', help='replace words with quotes around it ("*...*") with `...`')
        parser.add_argument('-p', default=False, dest='print_dry', action='store_true', help='print result in dry-run mode')
        parser.add_argument('remainder', nargs=argparse.REMAINDER)

        # parse parameters
        args = parser.parse_args()
        if args.help:
            parser.print_help()
            sys.exit(0)

        if args.verbose and args.quiet:
            parser.print_help()
            print()
            print("Error: --verbose and --quiet can't be set at the same time")
            sys.exit(1)

        if args.verbose:
            logging.getLogger().setLevel(logging.DEBUG)

        if args.quiet:
            logging.getLogger().setLevel(logging.ERROR)

        # if no configfile is named, try to find it somewhere
        if not args.configfile:
            args.configfile = self.find_configfile()
        self.configfile = args.configfile  # Let's remember this for better error messages.

        if args.configfile:
            try:
                with open(args.configfile, 'r', encoding="utf-8") as f:
                    self.config_contents = f.read()
            except OSError as e:
                print("Can't read {c}: {e}".format(c=args.configfile, e=e))
                sys.exit(1)
        else:
            logging.error("No config file given, and none found in the standard locations.")
            sys.exit(1)

        self.configfile_stat = os.stat(args.configfile)

        # remaining arguments must be Markdown files
        remaining_files = []
        for f in args.remainder:
            f = Path(f)
            if not f.exists():
                logging.error("File ({f}) does not exist!".format(f=f))
                sys.exit(1)
            if not f.is_file():
                if f.is_dir():
                    # this is a directory, see if there is an 'index.md' file inside
                    index_file = os.path.join(f, 'index.md')
                    index_file_path = Path(index_file)
                    if index_file_path.is_file():
                        # yes, use that file instead
                        remaining_files.append(index_file)
                        logging.debug("Use Markdown file: {f}".format(f=index_file))
                        continue
                logging.error("Argument ({f}) is not a file!".format(f=f))
                sys.exit(1)
            if not f.name.endswith('.md'):
                logging.error("Argument ({f}) is not a Markdown file!".format(f=f))
                sys.exit(1)
            # build a new list with files
            remaining_files.append(f)
        args.remainder = remaining_files

        self.arguments = args
        logging.debug("Commandline arguments successfully parsed")


    def read_config(self) -> None: # pylint: disable=R0912, R0915
        """
        Sanity check for the configuration file.
        """

        # first set defaults
        # disable all checks here, as default
        self.checks['check_whitespaces_at_end'] = False
        self.checks['check_find_more_separator'] = False
        self.checks['check_find_3_headline'] = False
        self.checks['check_find_4_headline'] = False
        self.checks['check_find_5_headline'] = False
        self.checks['check_missing_tags'] = False
        self.checks['check_missing_words_as_tags'] = False
        self.checks['check_lowercase_tags'] = False
        self.checks['check_lowercase_categories'] = False
        self.checks['check_missing_other_tags_one_way'] = False
        self.checks['check_missing_other_tags_both_ways'] = False
        self.checks['check_missing_cursive'] = False
        self.checks['check_http_link'] = False
        self.checks['check_i_i_am'] = False
        self.checks['check_hugo_localhost'] = False
        self.checks['check_changeme'] = False
        self.checks['check_code_blocks'] = False
        self.checks['check_psql_code_blocks'] = False
        self.checks['check_image_inside_preview'] = False
        self.checks['check_preview_thumbnail'] = False
        self.checks['check_preview_description'] = False
        self.checks['check_image_size'] = False
        self.checks['check_image_exif_tags_forbidden'] = False
        self.checks['check_dass'] = False
        self.checks['check_empty_line_after_header'] = False
        self.checks['check_empty_line_after_list'] = False
        self.checks['check_empty_line_after_code'] = False
        self.checks['check_forbidden_words'] = False
        self.checks['check_forbidden_websites'] = False
        self.checks['check_header_field_length'] = False
        self.checks['check_double_brackets'] = False
        self.checks['check_fixme'] = False
        self.checks['do_remove_whitespaces_at_end'] = False
        self.checks['do_replace_broken_links'] = False

        if not self.arguments:
            logging.error('Config: No arguments read.')
            sys.exit(1)
        # Invariant: self.arguments is not None

        # load configfile if one is specified
        config_data = {}
        if self.config_contents:
            try:
                config_data = yaml.safe_load(self.config_contents)
            except yaml.YAMLError as e:
                logging.error("Error parsing configfile {c}: {e}".format(c=self.arguments.configfile, e=e))
                sys.exit(1)

            if config_data:
                # find all existing keys from self.checks and parse them from the config
                config_keys = list(self.checks.keys())
                for key in config_keys:
                    if key in config_data:
                        if isinstance(config_data[key], bool):
                            self.checks[key] = config_data[key]
                        elif config_data[key] in ["1", "y", "yes"]:
                            self.checks[key] = True
                        elif config_data[key] in ["0", "n", "no"]:
                            self.checks[key] = False

        # some config values need more config

        # broken links replacement needs a list of links
        if self.checks['do_replace_broken_links']:
            if 'broken_links' not in config_data:
                logging.error("'do_replace_broken_links' is activated, but 'broken_links' data is not specified!")
                sys.exit(1)
            if not isinstance(config_data['broken_links'], list):
                logging.error("'broken_links' must be a list!")
                sys.exit(1)
            self.checks['broken_links'] = []
            for data in config_data['broken_links']:
                if 'orig' in data and 'replace' in data:
                    if data['orig'].startswith('http') or '://' in data['orig']:
                        logging.error("The 'orig' link must not include the protocol!")
                        logging.error("Link: {o}".format(o=data['orig']))
                        sys.exit(1)
                    if '://' not in data['replace']:
                        logging.error("The 'replace' link must include the protocol!")
                        logging.error("Link: {o}".format(o=data['replace']))
                        sys.exit(1)
                    self.checks['broken_links'].append([data['orig'], data['replace']])
                else:
                    logging.error("Both 'orig' and 'replace' must be specified in 'broken_links'!")
                    sys.exit(1)

        # missing tags needs a list of keywords and tags
        if self.checks['check_missing_tags']:
            if 'missing_tags' not in config_data:
                logging.error("'check_missing_tags' is activated, but 'missing_tags' data is not specified!")
                sys.exit(1)
            if not isinstance(config_data['missing_tags'], list):
                logging.error("'missing_tags' must be a list!")
                sys.exit(1)
            self.checks['missing_tags'] = []
            for data in config_data['missing_tags']:
                if 'word' in data and 'tag' in data:
                    self.checks['missing_tags'].append([data['word'], data['tag']])
                else:
                    logging.error("Both 'word' and 'tag' must be specified in 'missing_tags'!")
                    sys.exit(1)
            if 'missing_tags_include' in config_data:
                self.checks['missing_tags'] = self.include_missing_tags(self.checks['missing_tags'], config_data['missing_tags_include'])

        # missing words as tags needs a list of words
        if self.checks['check_missing_words_as_tags']:
            if 'missing_words' not in config_data:
                logging.error("'check_missing_words_as_tags' is activated, but 'missing_words' data is not specified!")
                sys.exit(1)
            if not isinstance(config_data['missing_words'], list):
                logging.error("'missing_words' must be a list!")
                sys.exit(1)
            self.checks['missing_words'] = config_data['missing_words']
            if 'missing_words_include' in config_data:
                self.checks['missing_words'] = self.include_missing_words(self.checks['missing_words'], config_data['missing_words_include'])
            self.checks['missing_words'] = list(set(self.checks['missing_words']))

        # tuple of tags where the second tag must exist if the first one is specified
        if self.checks['check_missing_other_tags_one_way']:
            if 'missing_other_tags_one_way' not in config_data:
                logging.error("'check_missing_other_tags_one_way' is activated, but 'missing_other_tags_one_way' data is not specified!")
                sys.exit(1)
            if not isinstance(config_data['missing_other_tags_one_way'], list):
                logging.error("'missing_other_tags_one_way' must be a list!")
                sys.exit(1)
            self.checks['missing_other_tags_one_way'] = []
            for data in config_data['missing_other_tags_one_way']:
                if 'tag1' in data and 'tag2' in data:
                    self.checks['missing_other_tags_one_way'].append([data['tag1'], data['tag2']])
                else:
                    logging.error("Both 'tag1' and 'tag2' must be specified in 'missing_other_tags_one_way'!")
                    sys.exit(1)

        # tuple of tags where the both tags must exist if one is specified
        if self.checks['check_missing_other_tags_both_ways']:
            if 'missing_other_tags_both_ways' not in config_data:
                logging.error("'check_missing_other_tags_both_ways' is activated, but 'missing_other_tags_both_ways' data is not specified!")
                sys.exit(1)
            if not isinstance(config_data['missing_other_tags_both_ways'], list):
                logging.error("'missing_other_tags_both_ways' must be a list!")
                sys.exit(1)
            self.checks['missing_other_tags_both_ways'] = []
            for data in config_data['missing_other_tags_both_ways']:
                if 'tag1' in data and 'tag2' in data:
                    self.checks['missing_other_tags_both_ways'].append([data['tag1'], data['tag2']])
                else:
                    logging.error("Both 'tag1' and 'tag2' must be specified in 'missing_other_tags_both_ways'!")
                    sys.exit(1)

        # list of words which must be cursive
        if self.checks['check_missing_cursive']:
            if 'missing_cursive' not in config_data:
                logging.error("'check_missing_cursive' is activated, but 'missing_cursive' data is not specified!")
                sys.exit(1)
            if not isinstance(config_data['missing_cursive'], list):
                logging.error("'missing_cursive' must be a list!")
                sys.exit(1)
            self.checks['missing_cursive'] = config_data['missing_cursive']
            if 'missing_cursive_include' in config_data:
                self.checks['missing_cursive'] = self.include_missing_cursive(self.checks['missing_cursive'], config_data['missing_cursive_include'])
            self.checks['missing_cursive'] = list(set(self.checks['missing_cursive']))

        # list of words which are forbidden in postings
        if self.checks['check_forbidden_words']:
            if 'forbidden_words' not in config_data:
                logging.error("'check_forbidden_words' is activated, but 'forbidden_words' data is not specified!")
                sys.exit(1)
            if not isinstance(config_data['forbidden_words'], list):
                logging.error("'forbidden_words' must be a list!")
                sys.exit(1)
            self.checks['forbidden_words'] = config_data['forbidden_words']
            self.checks['forbidden_words'] = list(set(self.checks['forbidden_words']))

        # list of websites which are forbidden in postings
        if self.checks['check_forbidden_websites']:
            if 'forbidden_websites' not in config_data:
                logging.error("'check_forbidden_websites' is activated, but 'forbidden_websites' data is not specified!")
                sys.exit(1)
            if not isinstance(config_data['forbidden_websites'], list):
                logging.error("'forbidden_websites' must be a list!")
                sys.exit(1)
            self.checks['forbidden_websites'] = config_data['forbidden_websites']
            for data in config_data['forbidden_websites']:
                if data.startswith('http') or '://' in data:
                    logging.error("The link must not include the protocol!")
                    logging.error("Link: {o}".format(o=data))
                    sys.exit(1)
            self.checks['forbidden_websites'] = list(set(self.checks['forbidden_websites']))

        # maximum size for objects in the posting directory
        if self.checks['check_image_size']:
            if 'image_size' not in config_data:
                logging.error("'check_image_size' is activated, but 'image_size' data is not specified!")
                sys.exit(1)
            try:
                self.checks['image_size'] = config_data['image_size'] = int(config_data['image_size'])
                if self.checks['image_size'] <= 0:
                    logging.error("Image size must be greater zero!")
                    sys.exit(1)
            except ValueError:
                logging.error("Image size ('image_size') is not an integer!")
                sys.exit(1)

        # forbidden EXIF tags in images
        if self.checks['check_image_exif_tags_forbidden']:
            if 'forbidden_exif_tags' not in config_data:
                logging.error("'check_image_exif_tags_forbidden' is activated, but 'forbidden_exif_tags' data is not specified!")
                sys.exit(1)
            if not isinstance(config_data['forbidden_exif_tags'], list):
                logging.error("'forbidden_exif_tags' must be a list!")
                sys.exit(1)
            self.checks['forbidden_exif_tags'] = config_data['forbidden_exif_tags']
            self.checks['forbidden_exif_tags'] = list(set(self.checks['forbidden_exif_tags']))

        # list of header fields which must have a certain length
        if self.checks['check_header_field_length']:
            if 'header_field_length' not in config_data:
                logging.error("'check_header_field_length' is activated, but 'header_field_length' data is not specified!")
                sys.exit(1)
            if not isinstance(config_data['header_field_length'], list):
                logging.error("'header_field_length' must be a list!")
                sys.exit(1)
            self.checks['header_field_length'] = config_data['header_field_length']
            for data in config_data['header_field_length']:
                if not isinstance(data, dict):
                    logging.error("Header field entry must be a dict!")
                    logging.error("Data: {d}".format(d = str(data)))
                    sys.exit(1)
                _, l = list(data.items())[0]
                try:
                    # make this an integer, has to be an integer anyway
                    l = int(l)
                    if l < 0:
                        logging.error("Length must be greater zero!")
                        logging.error("Data: {d}".format(d = str(data)))
                        sys.exit(1)
                except ValueError:
                    logging.error("Length must be an integer!")
                    logging.error("Data: {d}".format(d = str(data)))
                    sys.exit(1)
                except TypeError:
                    logging.error("Unknown error!")
                    logging.error("Data: {d}".format(d = str(data)))
                    sys.exit(1)


    def files(self) -> list[str]:
        """
        Return the list of remaining command line arguments (files)
        """

        return self.arguments.remainder


    def include_missing_tags(self, missing_tags: list[str], missing_tags_include: Optional[Path]) -> list[str]:
        """
        Read 'missing_tags' from a file
        """

        # need the filename relative to the original configfile
        filename = os.path.join(os.path.dirname(os.path.realpath(self.arguments.configfile)), missing_tags_include)

        if not os.path.exists(filename):
            logging.error("File '{f}' does not exist!".format(f = filename))
            sys.exit(1)

        with open(filename, 'r', encoding="utf-8") as file:
            try:
                data = yaml.safe_load(file)
                for entry in data:
                    word = entry.get('word')
                    tag = entry.get('tag')
                    if word and tag:
                        missing_tags.append([word, tag])
            except yaml.YAMLError as e:
                print(f"Error reading YAML file: {e}")

        return missing_tags


    def include_missing_words(self, missing_words: list[str], missing_words_include: Optional[Path]) -> list[str]:
        """
        Read 'missing_words' from a file
        """

        # need the filename relative to the original configfile
        filename = os.path.join(os.path.dirname(os.path.realpath(self.arguments.configfile)), missing_words_include)

        if not os.path.exists(filename):
            logging.error("File '{f}' does not exist!".format(f = filename))
            sys.exit(1)

        with open(filename, 'r', encoding="utf-8") as file:
            try:
                data = yaml.safe_load(file)
                for entry in data:
                    missing_words.append(entry)
            except yaml.YAMLError as e:
                print(f"Error reading YAML file: {e}")

        return missing_words


    def include_missing_cursive(self, missing_cursive: list[str], missing_cursive_include: Optional[Path]) -> list[str]:
        """
        Read 'missing_cursive' from a file
        """

        # need the filename relative to the original configfile
        filename = os.path.join(os.path.dirname(os.path.realpath(self.arguments.configfile)), missing_cursive_include)

        if not os.path.exists(filename):
            logging.error("File '{f}' does not exist!".format(f = filename))
            sys.exit(1)

        with open(filename, 'r', encoding="utf-8") as file:
            try:
                data = yaml.safe_load(file)
                for entry in data:
                    missing_cursive.append(entry)
            except yaml.YAMLError as e:
                print(f"Error reading YAML file: {e}")

        return missing_cursive


# end Config class
#######################################################################


#######################################################################
# helper functions

# handle_markdown_file()
#
# handle the checks for a single Markdown file
#
# parameter:
#  - config handle
#  - filename of Markdown file
# return:
#  - 0/1 (0: ok, 1: something wrong or changed)
def handle_markdown_file(config:str, filename:str) -> int: # pylint: disable=R0912, R0915
    """
    handle the checks for a single Markdown file
    """
    global log_entries # pylint: disable=W0603

    logging.debug("Working on file: {f}".format(f = filename))
    with open(filename, encoding="utf-8") as fh:
        data = fh.read()


    # reset the log array
    log_entries = []
    rc = 0

    # work on a copy of the original content
    output = data

    frontmatter, _ = split_file_into_frontmatter_and_markdown(data, filename)

    if config.checks['check_whitespaces_at_end']:
        output = check_whitespaces_at_end(config, output, filename, frontmatter)

    if config.checks['check_find_more_separator']:
        output = check_find_more_separator(config, output, filename, frontmatter)

    if config.checks['check_find_3_headline']:
        output = check_find_3_headline(config, output, filename, frontmatter)

    if config.checks['check_find_4_headline']:
        output = check_find_4_headline(config, output, filename, frontmatter)

    if config.checks['check_find_5_headline']:
        output = check_find_5_headline(config, output, filename, frontmatter)

    if config.checks['check_missing_tags']:
        output = check_missing_tags(config, output, filename, frontmatter)

    if config.checks['check_missing_words_as_tags']:
        output = check_missing_words_as_tags(config, output, filename, frontmatter)

    if config.checks['check_lowercase_tags']:
        output = check_lowercase_tags(config, output, filename, frontmatter)

    if config.checks['check_lowercase_categories']:
        output = check_lowercase_categories(config, output, filename, frontmatter)

    if config.checks['check_missing_other_tags_one_way']:
        output = check_missing_other_tags_one_way(config, output, filename, frontmatter)

    if config.checks['check_missing_other_tags_both_ways']:
        output = check_missing_other_tags_both_ways(config, output, filename, frontmatter)

    if config.checks['check_missing_cursive']:
        output = check_missing_cursive(config, output, filename, frontmatter)

    if config.checks['check_http_link']:
        output = check_http_link(config, output, filename, frontmatter)

    if config.checks['check_hugo_localhost']:
        output = check_hugo_localhost(config, output, filename, frontmatter)

    if config.checks['check_i_i_am']:
        output = check_i_i_am(config, output, filename, frontmatter)

    if config.checks['check_changeme']:
        output = check_changeme(config, output, filename, frontmatter)

    if config.checks['check_code_blocks']:
        output = check_code_blocks(config, output, filename, frontmatter)

    if config.checks['check_psql_code_blocks']:
        output = check_psql_code_blocks(config, output, filename, frontmatter)

    if config.checks['check_image_inside_preview']:
        output = check_image_inside_preview(config, output, filename, frontmatter)

    if config.checks['check_preview_thumbnail']:
        output = check_preview_thumbnail(config, output, filename, frontmatter)

    if config.checks['check_preview_description']:
        output = check_preview_description(config, output, filename, frontmatter)

    if config.checks['check_image_size']:
        output = check_image_size(config, output, filename, frontmatter)

    if config.checks['check_image_exif_tags_forbidden']:
        output = check_image_exif_tags_forbidden(config, output, filename, frontmatter)

    if config.checks['check_dass']:
        output = check_dass(config, output, filename, frontmatter)

    if config.checks['check_empty_line_after_header']:
        output = check_empty_line_after_header(config, output, filename, frontmatter)

    if config.checks['check_empty_line_after_list']:
        output = check_empty_line_after_list(config, output, filename, frontmatter)

    if config.checks['check_empty_line_after_code']:
        output = check_empty_line_after_code(config, output, filename, frontmatter)

    if config.checks['check_forbidden_words']:
        output = check_forbidden_words(config, output, filename, frontmatter)

    if config.checks['check_forbidden_websites']:
        output = check_forbidden_websites(config, output, filename, frontmatter)

    if config.checks['check_header_field_length']:
        output = check_header_field_length(config, output, filename, frontmatter)

    if config.checks['check_double_brackets']:
        output = check_double_brackets(config, output, filename, frontmatter)

    if config.checks['check_fixme']:
        output = check_fixme(config, output, filename, frontmatter)

    if config.checks['do_remove_whitespaces_at_end']:
        output = do_remove_whitespaces_at_end(config, output, filename, frontmatter)

    if config.checks['do_replace_broken_links']:
        output = do_replace_broken_links(config, output, filename, frontmatter)

    if len(log_entries) > 0:
        rc = 1
        print("File: {f}".format(f = os.path.realpath(filename)))
        for i in log_entries:
            print(i)

    if output != data:
        rc = 1
        logging.info("File is CHANGED!")
        if config.arguments.dry_run:
            if config.arguments.print_dry:
                logging.debug("Dry-run mode, output file:")
                print(output)
        else:
            logging.info("Write changed file ({f})".format(f = filename))
            with open(filename, "w", encoding="utf-8") as fh:
                fh.write(output)
    else:
        logging.debug("File is unchanged")

    return rc


# split_file_into_frontmatter_and_markdown()
#
# separate the Frontmatter header and the Markdown content
#
# parameter:
#  - copy of the file content
#  - filename
# return:
#  - frontmatter
#  - markdown
def split_file_into_frontmatter_and_markdown(data:str, filename:str) -> list[str, str]:
    """
    separate the Frontmatter header and the Markdown content
    """

    if data[0:4] != "---\n":
        logging.error("Content does not start with Frontmatter!")
        logging.error("File: {f}".format(f = filename))
        sys.exit(1)

    parts = re.search(r'^---\n(.*?)\n---\n(.*)$', data, re.DOTALL)
    if not parts:
        logging.error("Can't extract Frontmatter from data!")
        logging.error("File: {f}".format(f = filename))
        sys.exit(1)

    frontmatter = parts.group(1).strip()
    body = parts.group(2).strip()

    return frontmatter, body


# suppresswarnings()
#
# find out if a warning should be suppressed
#
# parameter:
#  - frontmatter
#  - the name of the warning to suppress
#  - current filename
# return:
#  - True/False
def suppresswarnings(frontmatter:str, name:str, filename:str) -> bool:
    """
    find out if a warning should be suppressed
    """

    try:
        yml = yaml.safe_load(frontmatter)
    except yaml.YAMLError as e:
        logging.error("Error parsing frontmatter in {f}: {e}".format(f = filename, e = e))
        sys.exit(1)
    if 'suppresswarnings' not in yml:
        # nothing in Fromtmatter
        return False

    sw = yml['suppresswarnings']
    if sw is None:
        # it's empty
        return False
    if name in sw:
        return True

    return False


# split_text_into_tokens()
#
# split a text and separate it into word tokens
#
# parameter:
#  - text
# return:
#  - list of tokens
#  - unique list of tokens
#  - lowercase list of unique tokens list
def split_text_into_tokens(data:str) -> list[list, list, list]:
    """
    split a text and separate it into word tokens
    """

    body = data.replace("\n", " ")
    body = body.replace(",", " ")
    body = body.replace(".", " ")

    body = re.split(r"[\s\t]+", body)
    unique_body = set(body)
    lc_body = [x.lower() for x in unique_body]

    return body, unique_body, lc_body


# line_is_list()
#
# find out if the current line is part of a list
#
# parameter:
#  - line with text
# return:
#  - True/False
def line_is_list(line:str) -> bool:
    """
    find out if the current line is part of a list
    """

    # this checks for the following patterns as a list:
    #  - unsorted lists starting with '-', '*' or '+'
    #  - sorted lists starting with a number and a dot
    #  - opening shortcodes (which can include a list item)
    list_pattern = re.compile(r'^\s*([-*+]|\d+\.|\{\{\%)\s+.*', re.MULTILINE)

    return bool(list_pattern.match(line))


# get_exif_data_from_image()
#
# reads all EXIF data from a picture using exiftool
#
# parameter:
#  - path to the image file
# return:
#  - dictionary with EXIF data
def get_exif_data_from_image(image_path: str) -> Dict[str, Any]:
    """
    reads all EXIF data from a picture using exiftool

    Args:
    - image_path (str): path to the image file

    Returns:
    - dict: dictionary containing all EXIF data
    """

    try:
        result = subprocess.run( # pylint: disable=W1510
            ['exiftool', '-json', image_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if result.returncode != 0:
            raise Exception(f"Error running exiftool: {result.stderr.strip()}") # pylint: disable=W0719

        exif_data = json.loads(result.stdout)

        # exiftool returns a list of dictionaries
        # we only need the first one
        if exif_data:
            return exif_data[0]
        return {}

    except Exception as e: # pylint: disable=W0718
        print(f"An error occurred: {e}")
        return {}


#######################################################################
# content check functions


# check_whitespaces_at_end()
#
# check if lines end in whitespaces
#
# parameter:
#  - config handle
#  - copy of the file content
#  - filename
#  - initial frontmatter copy
# return:
#  - (modified) copy of the file content
def check_whitespaces_at_end(config:Config, data:str, filename:str, init_frontmatter:str) -> str: # pylint: disable=W0613
    """
    check if lines end in whitespaces
    """

    if suppresswarnings(init_frontmatter, 'skip_whitespaces_at_end', filename):
        return data

    lines = data.splitlines()
    found_whitespaces = 0
    for line in lines:
        if len(line) == 0:
            pass
        else:
            if line[0] == '>':
                # that's a quote, do not remove spaces at the end
                pass
            else:
                if line != line.rstrip():
                    found_whitespaces += 1

    if found_whitespaces > 1:
        log_entries.append("Found {n} lines with whitespaces at the end".format(n = found_whitespaces))
        log_entries.append("  Use 'skip_whitespaces_at_end' in 'suppresswarnings' to silence this warning")
    elif found_whitespaces == 1:
        log_entries.append("Found 1 line with whitespaces at the end")
        log_entries.append("  Use 'skip_whitespaces_at_end' in 'suppresswarnings' to silence this warning")

    return data


# check_find_more_string()
#
# check if a <!--more--> separator exists in Markdown
#
# parameter:
#  - config handle
#  - copy of the file content
#  - filename
#  - initial frontmatter copy
# return:
#  - (modified) copy of the file content
def check_find_more_separator(config:Config, data:str, filename:str, init_frontmatter:str) -> str: # pylint: disable=W0613
    """
    check if a <!--more--> separator exists in Markdown
    """

    if suppresswarnings(init_frontmatter, 'skip_more_separator', filename):
        return data

    frontmatter, body = split_file_into_frontmatter_and_markdown(data, filename)

    if '<!--more-->' not in body:
        if not suppresswarnings(frontmatter, 'more_separator', filename):
            log_entries.append("Missing '<!--more-->' separator in Markdown!")
            log_entries.append("  Use 'skip_more_separator' in 'suppresswarnings' to silence this warning")

    return data


# check_find_3_headline()
#
# check if level 3 headlines are in the content
#
# parameter:
#  - config handle
#  - copy of the file content
#  - filename
#  - initial frontmatter copy
# return:
#  - (modified) copy of the file content
def check_find_3_headline(config:Config, data:str, filename:str, init_frontmatter:str) -> str: # pylint: disable=W0613
    """
    check if level 3 headlines are in the content
    """

    if suppresswarnings(init_frontmatter, 'skip_headline3', filename):
        return data

    frontmatter, _ = split_file_into_frontmatter_and_markdown(data, filename)

    if '### ' in data:
        if not suppresswarnings(frontmatter, 'headline3', filename):
            log_entries.append("Headline 3 in Markdown!")
            log_entries.append("  Use 'skip_headline3' in 'suppresswarnings' to silence this warning")

    return data


# check_find_4_headline()
#
# check if level 4 headlines are in the content
#
# parameter:
#  - config handle
#  - copy of the file content
#  - filename
#  - initial frontmatter copy
# return:
#  - (modified) copy of the file content
def check_find_4_headline(config:Config, data:str, filename:str, init_frontmatter:str) -> str: # pylint: disable=W0613
    """
    check if level 4 headlines are in the content
    """

    if suppresswarnings(init_frontmatter, 'skip_headline4', filename):
        return data

    frontmatter, _ = split_file_into_frontmatter_and_markdown(data, filename)

    if '#### ' in data:
        if not suppresswarnings(frontmatter, 'headline4', filename):
            log_entries.append("Headline 4 in Markdown!")
            log_entries.append("  Use 'skip_headline4' in 'suppresswarnings' to silence this warning")

    return data


# check_find_5_headline()
#
# check if level 5 headlines are in the content
#
# parameter:
#  - config handle
#  - copy of the file content
#  - filename
#  - initial frontmatter copy
# return:
#  - (modified) copy of the file content
def check_find_5_headline(config:Config, data:str, filename:str, init_frontmatter:str) -> str: # pylint: disable=W0613
    """
    check if level 5 headlines are in the content
    """

    if suppresswarnings(init_frontmatter, 'skip_headline5', filename):
        return data

    frontmatter, _ = split_file_into_frontmatter_and_markdown(data, filename)

    if '##### ' in data:
        if not suppresswarnings(frontmatter, 'headline5', filename):
            log_entries.append("Headline 5 in Markdown!")
            log_entries.append("  Use 'skip_headline5' in 'suppresswarnings' to silence this warning")

    return data


# check_missing_tags()
#
# check which tags should be in the posting, based on content
#
# parameter:
#  - config handle
#  - copy of the file content
#  - filename
#  - initial frontmatter copy
# return:
#  - (modified) copy of the file content
def check_missing_tags(config:Config, data:str, filename:str, init_frontmatter:str) -> str: # pylint: disable=W0613
    """
    check which tags should be in the posting, based on content
    """

    frontmatter, body = split_file_into_frontmatter_and_markdown(data, filename)

    _, _, lc_tokens = split_text_into_tokens(body)
    lc_tokens = [x.strip('*') for x in lc_tokens]
    lc_tokens = [x.strip('`') for x in lc_tokens]

    try:
        yml = yaml.safe_load(frontmatter)
    except yaml.YAMLError as e:
        logging.error("Error parsing frontmatter in {f}: {e}".format(f = filename, e = e))
        sys.exit(1)
    try:
        tags = yml['tags']
    except KeyError:
        log_entries.append("No tags found!")
        return data
    body_string = data.replace("\n", " ")

    if not isinstance(tags, list):
        log_entries.append("Tags is not a list!")
        return data

    for mt in config.checks['missing_tags']:
        word = mt[0]
        tag = mt[1]
        tag_not_found = False
        if word in body_string:
            if tag not in tags:
                if not suppresswarnings(frontmatter, 'skip_missing_tags_' + tag, filename):
                    tag_not_found = True
        if word in lc_tokens:
            if tag not in tags:
                if not suppresswarnings(frontmatter, 'skip_missing_tags_' + tag, filename):
                    tag_not_found = True

        if tag_not_found:
            log_entries.append("'{t}' tag is missing".format(t = tag))
            log_entries.append("  Use 'skip_missing_tags_{t}' in 'suppresswarnings' to silence this warning".format(t = tag))

    return data


# check_missing_words_as_tags()
#
# check which words should also be tags
#
# parameter:
#  - config handle
#  - copy of the file content
#  - filename
#  - initial frontmatter copy
# return:
#  - (modified) copy of the file content
def check_missing_words_as_tags(config:Config, data:str, filename:str, init_frontmatter:str) -> str: # pylint: disable=W0613
    """
    check which words should also be tags
    """

    frontmatter, body = split_file_into_frontmatter_and_markdown(data, filename)

    _, _, lc_tokens = split_text_into_tokens(body)
    lc_tokens = [x.strip('*') for x in lc_tokens]
    lc_tokens = [x.strip('`') for x in lc_tokens]

    try:
        yml = yaml.safe_load(frontmatter)
    except yaml.YAMLError as e:
        logging.error("Error parsing frontmatter in {f}: {e}".format(f = filename, e = e))
        sys.exit(1)
    try:
        tags = yml['tags']
    except KeyError:
        log_entries.append("No tags found!")
        return data

    if not isinstance(tags, list):
        log_entries.append("Tags is not a list!")
        return data

    for mt in config.checks['missing_words']:
        word = mt.lower()
        tag_not_found = False
        if word in lc_tokens:
            if word not in tags:
                if not suppresswarnings(frontmatter, 'skip_missing_words_' + word, filename):
                    tag_not_found = True

        if tag_not_found:
            log_entries.append("'{t}' tag is missing".format(t = word))
            log_entries.append("  Use 'skip_missing_words_{t}' in 'suppresswarnings' to silence this warning".format(t = word))

    return data


# check_lowercase_tags()
#
# make sure that all tags follow a uniform format
#
# parameter:
#  - config handle
#  - copy of the file content
#  - filename
#  - initial frontmatter copy
# return:
#  - (modified) copy of the file content
def check_lowercase_tags(config:Config, data:str, filename:str, init_frontmatter:str) -> str: # pylint: disable=W0613
    """
    make sure that all tags follow a uniform format
    """

    # tags should be lowercase, no spaces,
    # and not include characters which must be escaped in the URL

    frontmatter, _ = split_file_into_frontmatter_and_markdown(data, filename)

    try:
        yml = yaml.safe_load(frontmatter)
    except yaml.YAMLError as e:
        logging.error("Error parsing frontmatter in {f}: {e}".format(f = filename, e = e))
        sys.exit(1)
    try:
        tags = yml['tags']
    except KeyError:
        log_entries.append("No tags found!")
        return data

    if not isinstance(tags, list):
        log_entries.append("Tags is not a list!")
        return data

    allowed = re.compile(r'[^a-z0-9\-._äöüß]')
    for tag in tags:
        try:
            result = allowed.search(tag)
        except TypeError:
            # something went wrong
            logging.error("Invalid tag!")
            logging.error("File: {f}".format(f = filename))
            logging.error("Tag: {tag}".format(tag = str(tag)))
            sys.exit(1)
        if result:
            # tag does not match regex, raise an error
            # do not allow skipping this error, instead disable this check
            log_entries.append("Invalid tag: {t}".format(t = tag))

    return data


# check_lowercase_categories()
#
# make sure that all categories follow a uniform format
#
# parameter:
#  - config handle
#  - copy of the file content
#  - filename
#  - initial frontmatter copy
# return:
#  - (modified) copy of the file content
def check_lowercase_categories(config:Config, data:str, filename:str, init_frontmatter:str) -> str: # pylint: disable=W0613
    """
    make sure that all categories follow a uniform format
    """

    # categories should be lowercase, no spaces,
    # and not include characters which must be escaped in the URL

    frontmatter, _ = split_file_into_frontmatter_and_markdown(data, filename)

    try:
        yml = yaml.safe_load(frontmatter)
    except yaml.YAMLError as e:
        logging.error("Error parsing frontmatter in {f}: {e}".format(f = filename, e = e))
        sys.exit(1)
    try:
        categories = yml['categories']
    except KeyError:
        log_entries.append("No categories found!")
        return data

    if not isinstance(categories, list):
        log_entries.append("Categories is not a list!")
        return data

    allowed = re.compile(r'[^a-z0-9\-._äöüß]')
    for category in categories:
        try:
            result = allowed.search(category)
        except TypeError:
            # something went wrong
            logging.error("Invalid category!")
            logging.error("File: {f}".format(f = filename))
            logging.error("Category: {category}".format(category = str(category)))
            sys.exit(1)
        if result:
            # category does not match regex, raise an error
            # do not allow skipping this error, instead disable this check
            log_entries.append("Invalid category: {t}".format(t = category))

    return data


# check_missing_other_tags_one_way()
#
# check which other tags should be in the posting, based on existing tags
#
# parameter:
#  - config handle
#  - copy of the file content
#  - filename
#  - initial frontmatter copy
# return:
#  - (modified) copy of the file content
def check_missing_other_tags_one_way(config:Config, data:str, filename:str, init_frontmatter:str) -> str: # pylint: disable=W0613
    """
    check which other tags should be in the posting, based on existing tags
    """

    frontmatter, _ = split_file_into_frontmatter_and_markdown(data, filename)

    try:
        yml = yaml.safe_load(frontmatter)
    except yaml.YAMLError as e:
        logging.error("Error parsing frontmatter in {f}: {e}".format(f = filename, e = e))
        sys.exit(1)
    try:
        tags = yml['tags']
    except KeyError:
        log_entries.append("No tags found!")
        return data

    if not isinstance(tags, list):
        log_entries.append("Tags is not a list!")
        return data

    for mt in config.checks['missing_other_tags_one_way']:
        tag1 = mt[0]
        tag2 = mt[1]
        if tag1 in tags:
            if tag2 not in tags:
                if not suppresswarnings(frontmatter, 'skip_missing_other_tags_one_way_' + tag1 + '_' + tag2, filename):
                    log_entries.append("Found '{t1}' tag but '{t2}' tag is missing".format(t1 = tag1, t2 = tag2))
                    log_entries.append("  Use 'skip_missing_other_tags_one_way_{t1}_{t2}' in 'suppresswarnings' to silence this warning".format(t1 = tag1, t2 = tag2))

    return data


# check_missing_other_tags_both_ways()
#
# check which other tags should be in the posting, based on existing tags
#
# parameter:
#  - config handle
#  - copy of the file content
#  - filename
#  - initial frontmatter copy
# return:
#  - (modified) copy of the file content
def check_missing_other_tags_both_ways(config:Config, data:str, filename:str, init_frontmatter:str) -> str: # pylint: disable=W0613
    """
    check which other tags should be in the posting, based on existing tags
    """

    frontmatter, _ = split_file_into_frontmatter_and_markdown(data, filename)

    try:
        yml = yaml.safe_load(frontmatter)
    except yaml.YAMLError as e:
        logging.error("Error parsing frontmatter in {f}: {e}".format(f = filename, e = e))
        sys.exit(1)
    try:
        tags = yml['tags']
    except KeyError:
        log_entries.append("No tags found!")
        return data

    if not isinstance(tags, list):
        log_entries.append("Tags is not a list!")
        return data

    for mt in config.checks['missing_other_tags_both_ways']:
        tag1 = mt[0]
        tag2 = mt[1]
        if tag1 in tags:
            if tag2 not in tags:
                if not suppresswarnings(frontmatter, 'skip_missing_other_tags_both_ways_' + tag1 + '_' + tag2, filename):
                    log_entries.append("Found '{t1}' tag but '{t2}' tag is missing".format(t1 = tag1, t2 = tag2))
                    log_entries.append("  Use 'skip_missing_other_tags_both_ways_{t1}_{t2}' in 'suppresswarnings' to silence this warning".format(t1 = tag1, t2 = tag2))
        tag1 = mt[1]
        tag2 = mt[0]
        if tag1 in tags:
            if tag2 not in tags:
                if not suppresswarnings(frontmatter, 'skip_missing_other_tags_both_ways_' + tag1 + '_' + tag2, filename):
                    log_entries.append("Found '{t1}' tag but '{t2}' tag is missing".format(t1 = tag1, t2 = tag2))
                    log_entries.append("  Use 'skip_missing_other_tags_both_ways_{t1}_{t2}' in 'suppresswarnings' to silence this warning".format(t1 = tag1, t2 = tag2))

    return data


# check_missing_cursive()
#
# check if words should be cursive
#
# parameter:
#  - config handle
#  - copy of the file content
#  - filename
#  - initial frontmatter copy
# return:
#  - (modified) copy of the file content
def check_missing_cursive(config:Config, data:str, filename:str, init_frontmatter:str) -> str: # pylint: disable=W0613
    """
    check if words should be cursive
    """

    frontmatter, body = split_file_into_frontmatter_and_markdown(data, filename)

    lines = body.splitlines()
    lines2 = []
    for line in lines:
        if line.startswith('#'):
            # skip headlines
            pass
        elif line.startswith('>'):
            # skip quotes
            pass
        elif line.startswith('!'):
            # skip images
            pass
        else:
            lines2.append(line)
    body = "\n".join(lines2)

    _, unique_tokens, _ = split_text_into_tokens(body)

    for mc in config.checks['missing_cursive']:
        if mc in unique_tokens:
            if not suppresswarnings(frontmatter, 'skip_missing_cursive_' + mc, filename):
                log_entries.append("Found non-cursive token: {t}".format(t = mc))
                log_entries.append("  Use 'skip_missing_cursive_{t}' in 'suppresswarnings' to silence this warning".format(t = mc))

    return data


# check_http_link()
#
# check if http links are in the document (should be https)
#
# parameter:
#  - config handle
#  - copy of the file content
#  - filename
#  - initial frontmatter copy
# return:
#  - (modified) copy of the file content
def check_http_link(config:Config, data:str, filename:str, init_frontmatter:str) -> str: # pylint: disable=W0613
    """
    check if http links are in the document (should be https)
    """

    if suppresswarnings(init_frontmatter, 'skip_httplink', filename):
        return data

    _, body = split_file_into_frontmatter_and_markdown(data, filename)

    if 'http://' in body:
        log_entries.append("Found 'http://' link")
        log_entries.append("  Use 'skip_httplink' in 'suppresswarnings' to silence this warning")

    return data


# check_hugo_localhost()
#
# check if a Hugo localhost (preview) link appears in the document
#
# parameter:
#  - config handle
#  - copy of the file content
#  - filename
#  - initial frontmatter copy
# return:
#  - (modified) copy of the file content
def check_hugo_localhost(config:Config, data:str, filename:str, init_frontmatter:str) -> str: # pylint: disable=W0613
    """
    check if a Hugo localhost (preview) link appears in the document
    """

    if suppresswarnings(init_frontmatter, 'skip_hugo_localhost', filename):
        return data

    _, body = split_file_into_frontmatter_and_markdown(data, filename)

    if 'http://localhost:1313/' in body:
        log_entries.append("Found Hugo preview link")
        log_entries.append("  Use 'skip_hugo_localhost' in 'suppresswarnings' to silence this warning")

    return data


# check_i_i_am()
#
# check if lowercase "i" or "i'm" appear in the text
#
# parameter:
#  - config handle
#  - copy of the file content
#  - filename
#  - initial frontmatter copy
# return:
#  - (modified) copy of the file content
def check_i_i_am(config:Config, data:str, filename:str, init_frontmatter:str) -> str: # pylint: disable=W0613
    """
    check if lowercase "i" or "i'm" appear in the text
    """

    if suppresswarnings(init_frontmatter, 'skip_i_in_text', filename) and suppresswarnings(init_frontmatter, 'skip_i_am_in_text', filename):
        return data

    frontmatter, body = split_file_into_frontmatter_and_markdown(data, filename)

    body = body.replace("\n", " ")
    if ' i ' in body:
        if not suppresswarnings(frontmatter, 'skip_i_in_text', filename):
            log_entries.append("Found lowercase 'i' in text")
            log_entries.append("  Use 'skip_i_in_text' in 'suppresswarnings' to silence this warning")
    if ' i\'m ' in body:
        if not suppresswarnings(frontmatter, 'skip_i_am_in_text', filename):
            log_entries.append("Found lowercase 'i\'m' in text")
            log_entries.append("  Use 'skip_i_am_in_text' in 'suppresswarnings' to silence this warning")

    return data


# check_changeme()
#
# check if 'changeme' appears in tags or categories
#
# parameter:
#  - config handle
#  - copy of the file content
#  - filename
#  - initial frontmatter copy
# return:
#  - (modified) copy of the file content
def check_changeme(config:Config, data:str, filename:str, init_frontmatter:str) -> str: # pylint: disable=W0613
    """
    check if 'changeme' appears in tags or categories
    """

    if suppresswarnings(init_frontmatter, 'skip_changeme_tag', filename) and suppresswarnings(init_frontmatter, 'skip_changeme_category', filename):
        return data

    frontmatter, _ = split_file_into_frontmatter_and_markdown(data, filename)

    try:
        yml = yaml.safe_load(frontmatter)
    except yaml.YAMLError as e:
        logging.error("Error parsing frontmatter in {f}: {e}".format(f = filename, e = e))
        sys.exit(1)
    try:
        tags = yml['tags']
    except KeyError:
        log_entries.append("No tags found!")
        tags = []

    try:
        categories = yml['categories']
    except KeyError:
        log_entries.append("No categories found!")
        categories = []

    if 'changeme' in tags:
        if not suppresswarnings(frontmatter, 'skip_changeme_tag', filename):
            log_entries.append("Found 'changeme' tag!")
            log_entries.append("  Use 'skip_changeme_tag' in 'suppresswarnings' to silence this warning")

    if 'changeme' in categories:
        if not suppresswarnings(frontmatter, 'skip_changeme_category', filename):
            log_entries.append("Found 'changeme' category!")
            log_entries.append("  Use 'skip_changeme_category' in 'suppresswarnings' to silence this warning")

    return data


# check_code_blocks()
#
# check if every code block has a syntax highlighting type specified
#
# parameter:
#  - config handle
#  - copy of the file content
#  - filename
#  - initial frontmatter copy
# return:
#  - (modified) copy of the file content
def check_code_blocks(config:Config, data:str, filename:str, init_frontmatter:str) -> str: # pylint: disable=W0613
    """
    check if every code block has a syntax highlighting type specified
    """

    if suppresswarnings(init_frontmatter, 'skip_unmatching_code_blocks', filename):
        return data

    _, body = split_file_into_frontmatter_and_markdown(data, filename)

    lines = body.splitlines()

    count_opening_tags = 0
    count_closing_tags = 0

    # code blocks are expected to have a type specified
    # like: ```natural, or ```basic

    for line in lines:
        if line[0:3] == '```' and len(line) > 3:
            count_opening_tags += 1
        if line == '```':
            count_closing_tags += 1

    if count_opening_tags > 0 or count_closing_tags > 0:
        if count_opening_tags != count_closing_tags:
            log_entries.append("Found ummatching fenced code blocks")
            log_entries.append("  Use 'skip_unmatching_code_blocks' in 'suppresswarnings' to silence this warning")
            log_entries.append("  Language list: https://gohugo.io/content-management/syntax-highlighting/")

    return data


# check_psql_code_blocks()
#
# check if 'changeme' appears in tags or categories
#
# parameter:
#  - config handle
#  - copy of the file content
#  - filename
#  - initial frontmatter copy
# return:
#  - (modified) copy of the file content
def check_psql_code_blocks(config:Config, data:str, filename:str, init_frontmatter:str) -> str: # pylint: disable=W0613
    """
    check if 'changeme' appears in tags or categories
    """

    if suppresswarnings(init_frontmatter, 'skip_psql_code', filename):
        return data

    _, body = split_file_into_frontmatter_and_markdown(data, filename)

    lines = body.splitlines()

    count_opening_psql_tags = 0

    for line in lines:
        if line in ('```psql', '````psql'):
            count_opening_psql_tags += 1

    if count_opening_psql_tags > 0:
        log_entries.append("Found 'psql' code blocks, use 'postgresql' instead")
        log_entries.append("  Use 'skip_psql_code' in 'suppresswarnings' to silence this warning")

    return data


# check_image_inside_preview()
#
# check if there is an image inside the preview
#
# parameter:
#  - config handle
#  - copy of the file content
#  - filename
#  - initial frontmatter copy
# return:
#  - (modified) copy of the file content
def check_image_inside_preview(config:Config, data:str, filename:str, init_frontmatter:str) -> str: # pylint: disable=W0613
    """
    check if there is an image inside the preview
    """

    if suppresswarnings(init_frontmatter, 'skip_image_inside_preview', filename):
        return data

    _, body = split_file_into_frontmatter_and_markdown(data, filename)

    if '<!--more-->' not in data:
        if '![' in data:
            log_entries.append("Found image in preview, but no preview separator")
            log_entries.append("  Use 'skip_image_inside_preview' in 'suppresswarnings' to silence this warning")
    else:
        body_parts = body.split('<!--more-->')

        # only interested in images in the preview
        if '![' in body_parts[0]:
            log_entries.append("Found image in preview, move it further down")
            log_entries.append("  Use 'skip_image_inside_preview' in 'suppresswarnings' to silence this warning")

    return data


# check_preview_thumbnail()
#
# check if a preview image is specified
#
# parameter:
#  - config handle
#  - copy of the file content
#  - filename
#  - initial frontmatter copy
# return:
#  - (modified) copy of the file content
def check_preview_thumbnail(config:Config, data:str, filename:str, init_frontmatter:str) -> str: # pylint: disable=W0613
    """
    check if a preview image is specified
    """

    if suppresswarnings(init_frontmatter, 'skip_preview_thumbnail', filename):
        return data

    frontmatter, _ = split_file_into_frontmatter_and_markdown(data, filename)

    try:
        yml = yaml.safe_load(frontmatter)
    except yaml.YAMLError as e:
        logging.error("Error parsing frontmatter in {f}: {e}".format(f = filename, e = e))
        sys.exit(1)
    try:
        thumbnail = yml['thumbnail']
    except KeyError:
        thumbnail = ''

    if thumbnail is None or len(thumbnail) < 1:
        log_entries.append("Found no preview image in header")
        log_entries.append("  Use 'skip_preview_thumbnail' in 'suppresswarnings' to silence this warning")

    return data


# check_preview_description()
#
# check if a preview description is specified
#
# parameter:
#  - config handle
#  - copy of the file content
#  - filename
#  - initial frontmatter copy
# return:
#  - (modified) copy of the file content
def check_preview_description(config:Config, data:str, filename:str, init_frontmatter:str) -> str: # pylint: disable=W0613
    """
    check if a preview description is specified
    """

    if suppresswarnings(init_frontmatter, 'skip_preview_description', filename):
        return data

    frontmatter, _ = split_file_into_frontmatter_and_markdown(data, filename)

    try:
        yml = yaml.safe_load(frontmatter)
    except yaml.YAMLError as e:
        logging.error("Error parsing frontmatter in {f}: {e}".format(f = filename, e = e))
        sys.exit(1)
    try:
        description = yml['description']
    except KeyError:
        description = ''

    if description is None or len(description) < 1:
        log_entries.append("Found no preview description in header")
        log_entries.append("  Use 'skip_preview_description' in 'suppresswarnings' to silence this warning")

    return data


# file_is_ignored_in_git()
#
# check if a file is ignored in git
#
# parameter:
#  - filename
# return:
#  - True: file is ignored
#  - False: file is not ignored, or not a git repository
def file_is_ignored_in_git(filename:str) -> bool:
    """
    check if a file is ignored in git
    """

    rc = False
    try:
        result = subprocess.run( # pylint: disable=W1510
            ['git', 'check-ignore', filename],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        return_code = result.returncode
        if return_code == 0: # pylint: disable=R1703
            # RC=0 is only set if the file is ignored
            rc = True
        else:
            # RC=1 is set when file is not ignored
            # RC=128 is set when this is not a git repository
            rc = False
        #stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        if len(stderr) > 0:
            # something went wrong
            rc = False

    except Exception as e: # pylint: disable=W0718,W0612
        rc = False

    return rc


# check_image_size()
#
# check if larger images are present
#
# parameter:
#  - config handle
#  - copy of the file content
#  - filename
#  - initial frontmatter copy
# return:
#  - (modified) copy of the file content
def check_image_size(config:Config, data:str, filename:str, init_frontmatter:str) -> str: # pylint: disable=W0613
    """
    check if larger images are present
    """

    if suppresswarnings(init_frontmatter, 'skip_image_size', filename):
        return data

    # this scans the same directory as the Markdown file
    # and therefore only works for Hugo Page Bundles
    # https://gohugo.io/content-management/page-bundles/
    # this does not scan the static directory

    max_image_size = config.checks['image_size']

    dirname = os.path.dirname(filename)
    found_large_files = []
    for rootdir, _, filenames in os.walk(dirname):
        for this_filename in filenames:
            if rootdir != dirname:
                # only want files in the same directory
                continue
            this_file = os.path.join(rootdir, this_filename)
            this_stat = os.stat(this_file)
            if this_stat.st_size > max_image_size:
                if not file_is_ignored_in_git(this_file):
                    found_large_files.append(this_file)

    if len(found_large_files) > 0:
        log_entries.append("Found large images, either resize them or:")
        log_entries.append("  Use 'skip_image_size' to suppress this warning")
        for n in found_large_files:
            log_entries.append("  Large file: {lf}".format(lf = n))

    return data


# check_image_exif_tags_forbidden()
#
# check if EXIF image tags are in the image which must be excluded
#
# parameter:
#  - config handle
#  - copy of the file content
#  - filename
#  - initial frontmatter copy
# return:
#  - (modified) copy of the file content
def check_image_exif_tags_forbidden(config:Config, data:str, filename:str, init_frontmatter:str) -> str: # pylint: disable=W0613, R0912, R0914
    """
    check if EXIF image tags are in the image which must be excluded
    """

    if suppresswarnings(init_frontmatter, 'skip_image_exif_tags_forbidden', filename):
        return data

    # this scans the same directory as the Markdown file
    # and therefore only works for Hugo Page Bundles
    # https://gohugo.io/content-management/page-bundles/
    # this does not scan the static directory

    forbidden_exif_tags = config.checks['forbidden_exif_tags']

    dirname = os.path.dirname(filename)
    found_image_files = []
    found_images_with_exif_tags = []
    found_exif_tags = []
    for rootdir, _, filenames in os.walk(dirname):
        for this_filename in filenames:
            if rootdir != dirname:
                # only want files in the same directory
                continue
            this_file = os.path.join(rootdir, this_filename)
            if not (this_file.endswith('.jpg') or
                    this_file.endswith('.jpeg') or
                    this_file.endswith('.png') or
                    this_file.endswith('.webp')):
                continue
            if not file_is_ignored_in_git(this_file):
                found_image_files.append(this_file)

    if len(found_image_files) > 0:
        # these images are not ignored in git
        for n in found_image_files:
            exif_tags = get_exif_data_from_image(n)
            exif_tags_found = False
            for t in forbidden_exif_tags:
                if t in exif_tags:
                    exif_tags_found = True
                    found_exif_tags.append(t)
            if exif_tags_found:
                found_images_with_exif_tags.append(n)

    if len(found_images_with_exif_tags) > 0:
        log_entries.append("Found forbidden EXIF tags in images, either remove them or:")
        log_entries.append("  Use 'skip_image_exif_tags_forbidden' to suppress this warning")
        for n in found_images_with_exif_tags:
            log_entries.append("  Image file: {lf}".format(lf = n))
        found_exif_tags = list(set(found_exif_tags))
        found_exif_tags.sort()
        log_entries.append("  EXIF tags: {et}".format(et = ", ".join(found_exif_tags)))

    return data


# check_dass()
#
# check if the German 'daß' appears in the text
#
# parameter:
#  - config handle
#  - copy of the file content
#  - filename
#  - initial frontmatter copy
# return:
#  - (modified) copy of the file content
def check_dass(config:Config, data:str, filename:str, init_frontmatter:str) -> str: # pylint: disable=W0613
    """
    check if the German 'daß' appears in the text
    """

    if suppresswarnings(init_frontmatter, 'skip_dass', filename):
        return data

    _, body = split_file_into_frontmatter_and_markdown(data, filename)

    if 'daß' in body:
        log_entries.append("Found 'daß' in text")
        log_entries.append("  Use 'skip_dass' in 'suppresswarnings' to silence this warning")

    return data


# check_empty_line_after_header()
#
# check for empty lines after headers
#
# parameter:
#  - config handle
#  - copy of the file content
#  - filename
#  - initial frontmatter copy
# return:
#  - (modified) copy of the file content
def check_empty_line_after_header(config:Config, data:str, filename:str, init_frontmatter:str) -> str: # pylint: disable=W0613
    """
    check for empty lines after headers
    """

    if suppresswarnings(init_frontmatter, 'skip_empty_line_after_header', filename):
        return data

    _, body = split_file_into_frontmatter_and_markdown(data, filename)

    lines = body.splitlines()

    last_line_is_header = False
    last_header_line = ""
    in_code_block = False

    for line in lines:
        if line[0:3] == '```':
            if not in_code_block: # pylint: disable=R1703
                in_code_block = True
            else:
                in_code_block = False
            continue
        if in_code_block:
            # do not check code, that's a false positive
            continue

        if len(line) == 0:
            last_line_is_header = False
            last_header_line = ""
        elif line[0:1] != '#' and last_line_is_header:
            # last line was a header, this line is not empty
            log_entries.append("Missing empty line after header")
            log_entries.append("  Use 'skip_empty_line_after_header' in 'suppresswarnings' to silence this warning")
            log_entries.append("  Header: {h}".format(h = last_header_line))

        if line[0:1] == '#':
            last_line_is_header = True
            last_header_line = line

    return data


# check_empty_line_after_list()
#
# check for empty lines after a list
#
# parameter:
#  - config handle
#  - copy of the file content
#  - filename
#  - initial frontmatter copy
# return:
#  - (modified) copy of the file content
def check_empty_line_after_list(config:Config, data:str, filename:str, init_frontmatter:str) -> str: # pylint: disable=W0613
    """
    check for empty lines after a list
    """

    if suppresswarnings(init_frontmatter, 'skip_empty_line_after_list', filename):
        return data

    _, body = split_file_into_frontmatter_and_markdown(data, filename)

    lines = body.splitlines()

    last_line_is_list = False
    in_code_block = False

    for line in lines:
        if line[0:3] == '```':
            if not in_code_block: # pylint: disable=R1703
                in_code_block = True
            else:
                in_code_block = False
            continue
        if in_code_block:
            # do not check code, that's a false positive
            continue

        if len(line) == 0:
            last_line_is_list = False
        elif not line_is_list(line) and last_line_is_list:
            # last line was a list, this line is not empty
            log_entries.append("Missing empty line after list")
            log_entries.append("  Use 'skip_empty_line_after_list' in 'suppresswarnings' to silence this warning")

        if line_is_list(line):
            last_line_is_list = True

    return data


# check_empty_line_after_code()
#
# check for empty lines after code blocks
#
# parameter:
#  - config handle
#  - copy of the file content
#  - filename
#  - initial frontmatter copy
# return:
#  - (modified) copy of the file content
def check_empty_line_after_code(config:Config, data:str, filename:str, init_frontmatter:str) -> str: # pylint: disable=W0613
    """
    check for empty lines after code blocks
    """

    if suppresswarnings(init_frontmatter, 'skip_empty_line_after_code', filename):
        return data

    _, body = split_file_into_frontmatter_and_markdown(data, filename)

    lines = body.splitlines()

    in_code_block = False
    last_line_ends_code_block = False

    for line in lines:
        if last_line_ends_code_block and len(line) > 0:
            log_entries.append("Missing empty line after code block")
            log_entries.append("  Use 'skip_empty_line_after_code' in 'suppresswarnings' to silence this warning")

        if line[0:3] == '```' and not in_code_block:
            in_code_block = True
            continue
        if line == '```' and in_code_block:
            in_code_block = False
            last_line_ends_code_block = True
            continue

        last_line_ends_code_block = False

    return data


# check_forbidden_words()
#
# check for forbidden words in the posting
#
# parameter:
#  - config handle
#  - copy of the file content
#  - filename
#  - initial frontmatter copy
# return:
#  - (modified) copy of the file content
def check_forbidden_words(config:Config, data:str, filename:str, init_frontmatter:str) -> str: # pylint: disable=W0613
    """
    check for forbidden words in the posting
    """

    frontmatter, body = split_file_into_frontmatter_and_markdown(data, filename)

    for fb in config.checks['forbidden_words']:
        if fb in body:
            if not suppresswarnings(frontmatter, 'skip_forbidden_words_' + fb, filename):
                log_entries.append("Found forbidden word: {t}".format(t = fb))
                log_entries.append("  Use 'skip_forbidden_words_{t}' in 'suppresswarnings' to silence this warning".format(t = fb))

    return data


# check_forbidden_websites()
#
# check for forbidden websites in the posting
#
# parameter:
#  - config handle
#  - copy of the file content
#  - filename
#  - initial frontmatter copy
# return:
#  - (modified) copy of the file content
def check_forbidden_websites(config:Config, data:str, filename:str, init_frontmatter:str) -> str: # pylint: disable=W0613
    """
    check for forbidden websites in the posting
    """

    frontmatter, body = split_file_into_frontmatter_and_markdown(data, filename)

    for fw in config.checks['forbidden_websites']:
        found_fw = False

        link = 'https://' + fw + '/'
        if link in body:
            found_fw = True

        link = 'https://' + fw
        if link in body:
            found_fw = True

        link = 'http://' + fw + '/'
        if link in body:
            found_fw = True

        link = 'http://' + fw
        if link in body:
            found_fw = True

        if found_fw:
            if not suppresswarnings(frontmatter, 'skip_forbidden_websites_' + fw, filename):
                log_entries.append("Found forbidden website: {t}".format(t = fw))
                log_entries.append("  Use 'skip_forbidden_websites_{t}' in 'suppresswarnings' to silence this warning".format(t = fw))

    return data


# check_header_field_length()
#
# check if header (frontmatter) fields have at least a certain length
#
# parameter:
#  - config handle
#  - copy of the file content
#  - filename
#  - initial frontmatter copy
# return:
#  - (modified) copy of the file content
def check_header_field_length(config:Config, data:str, filename:str, init_frontmatter:str) -> str: # pylint: disable=W0613
    """
    check if header (frontmatter) fields have at least a certain length
    """

    frontmatter, _ = split_file_into_frontmatter_and_markdown(data, filename)
    try:
        yml = yaml.safe_load(frontmatter)
    except yaml.YAMLError as e:
        logging.error("Error parsing frontmatter in {f}: {e}".format(f = filename, e = e))
        sys.exit(1)

    for hfl in config.checks['header_field_length']:
        f, l = list(hfl.items())[0]

        if f not in yml:
            # can't suppress the missing field
            log_entries.append("Missing Frontmatter entry: {f}".format(f = f))
            continue

        try:
            fl = len(yml[f])
        except TypeError:
            fl = 0
        if fl < l:
            if not suppresswarnings(frontmatter, 'skip_header_field_length_' + f, filename):
                log_entries.append("Frontmatter entry too short: {f} ({fl} < {l} chars): {f}".format(f = f, fl = fl, l = l))
                log_entries.append("  Use 'skip_header_field_length_{f}' in 'suppresswarnings' to silence this warning".format(f = f))

    return data


# check_double_brackets()
#
# check if opening or closing double brackets (parenthesis) appear in the text
#
# parameter:
#  - config handle
#  - copy of the file content
#  - filename
#  - initial frontmatter copy
# return:
#  - (modified) copy of the file content
def check_double_brackets(config:Config, data:str, filename:str, init_frontmatter:str) -> str: # pylint: disable=W0613
    """
    check if opening or closing double brackets (parenthesis) appear in the text
    """

    if suppresswarnings(init_frontmatter, 'skip_double_brackets_opening', filename) and suppresswarnings(init_frontmatter, 'skip_double_brackets_closing', filename):
        return data


    frontmatter, body = split_file_into_frontmatter_and_markdown(data, filename)

    lines = body.splitlines()
    in_code_block = False
    body_lines = []

    for line in lines:
        if line[0:3] == '```':
            if not in_code_block: # pylint: disable=R1703
                in_code_block = True
            else:
                in_code_block = False
        if in_code_block:
            continue
        body_lines.append(line)

    body = "".join(body_lines)

    if '((' in body:
        if not suppresswarnings(frontmatter, 'skip_double_brackets_opening', filename):
            log_entries.append("Found opening double brackets!")
            log_entries.append("  Use 'skip_double_brackets_opening' in 'suppresswarnings' to silence this warning")

    if '))' in body:
        if not suppresswarnings(frontmatter, 'skip_double_brackets_closing', filename):
            log_entries.append("Found closing double brackets!")
            log_entries.append("  Use 'skip_double_brackets_closing' in 'suppresswarnings' to silence this warning")

    return data


# check_fixme()
#
# check if FIXME texts appear in the text
#
# parameter:
#  - config handle
#  - copy of the file content
#  - filename
#  - initial frontmatter copy
# return:
#  - (modified) copy of the file content
def check_fixme(config:Config, data:str, filename:str, init_frontmatter:str) -> str: # pylint: disable=W0613
    """
    check if FIXME texts appear in the text
    """

    if suppresswarnings(init_frontmatter, 'skip_fixme', filename):
        return data


    _, body = split_file_into_frontmatter_and_markdown(data, filename)

    body_lower = body.lower()
    if 'fixme' in body_lower:
        log_entries.append("Found FIXME in text!")
        log_entries.append("  Use 'skip_fixme' in 'suppresswarnings' to silence this warning")

    return data


# do_remove_whitespaces_at_end()
#
# removes whitespaces at the end of lines
#
# parameter:
#  - config handle
#  - copy of the file content
#  - filename
#  - initial frontmatter copy
# return:
#  - (modified) copy of the file content
def do_remove_whitespaces_at_end(config:Config, data:str, filename:str, init_frontmatter:str) -> str: # pylint: disable=W0613
    """
    removes whitespaces at the end of lines
    """

    if suppresswarnings(init_frontmatter, 'skip_do_remove_whitespaces_at_end', filename):
        return data

    lines = data.splitlines()
    output = []
    for line in lines:
        if len(line) == 0:
            output.append(line)
        else:
            if line[0] == '>':
                # that's a quote, do not remove spaces at the end
                output.append(line)
            else:
                output.append(line.rstrip())

    output = "\n".join(output) + "\n"

    if data != output:
        log_entries.append("Removing whitespaces at end of lines")

    return output


# do_replace_broken_links()
#
# replace broken links in text
#
# parameter:
#  - config handle
#  - copy of the file content
#  - filename
#  - initial frontmatter copy
# return:
#  - (modified) copy of the file content
def do_replace_broken_links(config:Config, data:str, filename:str, init_frontmatter:str) -> str: # pylint: disable=W0613
    """
    replace broken links in text
    """

    if suppresswarnings(init_frontmatter, 'skip_do_replace_broken_links', filename):
        return data

    broken_links = config.checks['broken_links']

    output = data

    for bl in broken_links:
        l_orig = bl[0]
        l_replace = bl[1]
        # make sure the list is in order to grab the ending / first
        orig = 'https://' + l_orig + '/'
        output = output.replace(orig, l_replace)
        orig = 'https://' + l_orig
        output = output.replace(orig, l_replace)
        orig = 'http://' + l_orig + '/'
        output = output.replace(orig, l_replace)
        orig = 'http://' + l_orig
        output = output.replace(orig, l_replace)

    if data != output:
        log_entries.append("Replacing broken links")

    return output


# work_on_this_markdown_file()
#
# decide if this Markdown file needs to be processed
#
# parameter:
#  - config handle
#  - filename
# return:
#  - True/False
def work_on_this_markdown_file(config:Config, filename:str) -> bool:
    """
    decide if this Markdown file needs to be processed

    if the --all option is not given, then only process files which are
    younger than the configfile
    """

    if config.arguments.all:
        # the --all option is passed, process every file
        return True

    # compare timestamps
    last_change_configfile = config.configfile_stat.st_mtime
    stat_filename = os.stat(filename)
    last_change_filename = stat_filename.st_mtime
    if last_change_filename >= last_change_configfile:
        return True

    # also (briefly) check the content of the file
    # if it is in 'draft' state, include it in the list
    try:
        with open(filename, 'r', encoding="utf-8") as f:
            file_content = f.read()
    except OSError as e:
        print("Can't read {f}: {e}".format(f=filename, e=e))
        sys.exit(1)
    # don't really parse Frontmatter, too expensive
    if 'draft: true' in file_content:
        return True

    return False


#######################################################################
# main

def main() -> int:
    """
    main function, work on all Markdown files
    """
    config = Config()
    config.parse_parameters()
    config.read_config()

    global_rc = 0
    files = config.files()
    if len(files) > 0:
        for f in files:
            rc = handle_markdown_file(config, f)
            if rc != 0:
                global_rc = 1
    else:
        # find all Markdown files
        # only scan directories where blog postings are expected
        # the 'content' directory can have other entries which are not to be checked
        all_files = []
        directories = ["content/post", "content/posts", "content/blog", "content/blogs",
                       "content/businesses", "content/places", "content/restaurants",
                       "content/trips", "content/events"]
        for directory in directories:
            for rootpath, _, files in os.walk(directory):
                for filename in files:
                    if not filename.endswith(".md"):
                        continue
                    if not work_on_this_markdown_file(config, os.path.join(rootpath, filename)):
                        logging.debug("Skipping file (too old): {f}".format(f = os.path.join(rootpath, filename)))
                        continue
                    # add the filenames to a list, and sort it later
                    all_files.append(os.path.join(rootpath, filename))

        all_files.sort(reverse=False)
        for f in all_files:
            rc = handle_markdown_file(config, f)
            if rc != 0:
                global_rc = 1

    return global_rc


if __name__ == '__main__':
    rc_main = main()

    sys.exit(rc_main)
