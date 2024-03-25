#!/usr/bin/env python3

# run pre-flight checks on Markdown postings
# before committing the blog postings into git
# can be used standalone to check blog postings

import os
import sys
import re
from pathlib import Path
import shutil
import logging
import argparse
from pprint import pprint
from typing import Optional, Dict, Any

import yaml
import requests


# start with 'info', can be overriden by '-q' later on
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

log_entries = []


#######################################################################
# Config class

class Config:

    def __init__(self) -> None:
        self.__cmdline_read: bool = False
        self.arguments: Optional[argparse.Namespace] = None
        self.argument_parser: Optional[argparse] = None
        self.configfile: Optional[Path] = None
        self.config_contents: Optional[str] = None
        self.checks: Dict[str, Any] = {}

    def find_configfile(self, this_dir: Optional[Path] = None) -> Optional[Path]:
        """
        Searches for ``check-markdown-files.conf`` tree-upwards,
        starting in ``this_dir``, stops when it finds a ``.git`` directory or reaches ``/``.
        If ``this_dir`` is None, we start from ``os.getcwd()``.

        :returns: A ``Path`` to the config file, or ``None`` if no config file can be found.
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

    def parse_parameters(self) -> None:
        """
        parse commandline parameters, fill in array with arguments.
        """
        parser = argparse.ArgumentParser(description='Check Markdown files before publishing blog postings',
                                         add_help=False)
        self.argument_parser = parser
        parser.add_argument('--help', default=False, dest='help', action='store_true', help='show this help')
        # store_true: store "True" if specified, otherwise store "False"
        # store_false: store "False" if specified, otherwise store "True"
        parser.add_argument('-v', '--verbose', default=False, dest='verbose', action='store_true', help='be more verbose')
        parser.add_argument('-q', '--quiet', default=False, dest='quiet', action='store_true', help='run quietly')
        parser.add_argument('-c', default='', dest='configfile', help="configuration file (default: 'check-markdown-files.conf in repository')")
        parser.add_argument('-n', default=False, dest='dry_run', action='store_true', help='dry-run (don\'t change anything)')
        parser.add_argument('-r', default=False, dest='replace_quotes', action='store_true', help='replace words with quotes around it ("*...*") with `...`')
        parser.add_argument('-p', default=False, dest='print_dry', action='store_true', help='print result in dry-run mode')
        parser.add_argument('remainder', nargs=argparse.REMAINDER)

        # parse parameters
        args = parser.parse_args()

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
                with open(args.configfile, 'r') as f:
                    self.config_contents = f.read()
            except OSError as e:
                print("Can't read {c}: {e}".format(c=args.configfile, e=e))
        else:
            logging.error("No config file given, and none found in the standard locations.")
            sys.exit(1)

        # remaining arguments must be Markdown files
        for f in args.remainder:
            f = Path(f)
            if f.exists():
                logging.error("File ({f}) does not exist!".format(f=f))
                sys.exit(1)
            if f.is_file():
                logging.error("Argument ({f}) is not a file!".format(f=f))
                sys.exit(1)
            if not f.name.endswith('.md'):
                logging.error("Argument ({f}) is not a Markdown file!".format(f=f))
                sys.exit(1)

        self.arguments = args
        logging.debug("Commandline arguments successfully parsed")

        return


    # read_config()
    #
    # read the configfile (if given) and set config values
    #
    # parameter:
    #  - self
    # return:
    #  none
    def read_config(self):
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
        self.checks['check_dass'] = False
        self.checks['check_empty_line_after_header'] = False
        self.checks['check_empty_line_after_list'] = False
        self.checks['check_empty_line_after_code'] = False
        self.checks['check_forbidden_words'] = False
        self.checks['check_forbidden_websites'] = False
        self.checks['do_remove_whitespaces_at_end'] = False
        self.checks['do_replace_broken_links'] = False

        # load configfile if one is specified
        if (self.arguments.configfile):
            with open(self.arguments.configfile, 'r') as configstream:
                try:
                    config_data = yaml.load(configstream, Loader = yaml.FullLoader)
                except yaml.YAMLError as e:
                    logging.error("Error loading configfile {c}: {e}".format(c = self.arguments.configfile, e = e))
                    sys.exit(1)

            if (config_data is not None):
                # find all existing keys from self.checks and parse them from the config
                config_keys = list(self.checks.keys())
                for key in config_keys:
                    if (key in config_data):
                        if type(config_data[key]) is bool:
                            self.checks[key] = config_data[key]
                        elif (config_data[key] == "1" or config_data[key] == "y" or config_data[key] == "yes"):
                            self.checks[key] = True
                        elif (config_data[key] == "0" or config_data[key] == "n" or config_data[key] == "no"):
                            self.checks[key] = False

        # some config values need more config

        # broken links replacement needs a list of links
        if (self.checks['do_replace_broken_links'] is True):
            if ('broken_links' not in config_data):
                logging.error("'do_replace_broken_links' is activated, but 'broken_links' data is not specified!")
                sys.exit(1)
            if (not isinstance(config_data['broken_links'], list)):
                logging.error("'broken_links' must be a list!")
                sys.exit(1)
            self.checks['broken_links'] = []
            for data in config_data['broken_links']:
                if ('orig' in data and 'replace' in data):
                    if (data['orig'].startswith('http') or '://' in data['orig']):
                        logging.error("The 'orig' link must not include the protocol!")
                        logging.error("Link: {o}".format(o = data['orig']))
                        sys.exit(1)
                    if ('://' not in data['replace']):
                        logging.error("The 'replace' link must include the protocol!")
                        logging.error("Link: {o}".format(o = data['replace']))
                        sys.exit(1)
                    self.checks['broken_links'].append([data['orig'], data['replace']])
                else:
                    logging.error("Both 'orig' and 'replace' must be specified in 'broken_links'!")
                    sys.exit(1)

        # missing tags needs a list of keywords and tags
        if (self.checks['check_missing_tags'] is True):
            if ('missing_tags' not in config_data):
                logging.error("'check_missing_tags' is activated, but 'missing_tags' data is not specified!")
                sys.exit(1)
            if (not isinstance(config_data['missing_tags'], list)):
                logging.error("'missing_tags' must be a list!")
                sys.exit(1)
            self.checks['missing_tags'] = []
            for data in config_data['missing_tags']:
                if ('word' in data and 'tag' in data):
                    self.checks['missing_tags'].append([data['word'], data['tag']])
                else:
                    logging.error("Both 'word' and 'tag' must be specified in 'missing_tags'!")
                    sys.exit(1)

        # missing words as tags tags needs a list of words
        if (self.checks['check_missing_words_as_tags'] is True):
            if ('missing_words' not in config_data):
                logging.error("'check_missing_words_as_tags' is activated, but 'missing_words' data is not specified!")
                sys.exit(1)
            if (not isinstance(config_data['missing_words'], list)):
                logging.error("'missing_words' must be a list!")
                sys.exit(1)
            self.checks['missing_words'] = config_data['missing_words']

        # tuple of tags where the second tag must exist if the first one is specified
        if (self.checks['check_missing_other_tags_one_way'] is True):
            if ('missing_other_tags_one_way' not in config_data):
                logging.error("'check_missing_other_tags_one_way' is activated, but 'missing_other_tags_one_way' data is not specified!")
                sys.exit(1)
            if (not isinstance(config_data['missing_other_tags_one_way'], list)):
                logging.error("'missing_other_tags_one_way' must be a list!")
                sys.exit(1)
            self.checks['missing_other_tags_one_way'] = []
            for data in config_data['missing_other_tags_one_way']:
                if ('tag1' in data and 'tag2' in data):
                    self.checks['missing_other_tags_one_way'].append([data['tag1'], data['tag2']])
                else:
                    logging.error("Both 'tag1' and 'tag2' must be specified in 'missing_other_tags_one_way'!")
                    sys.exit(1)

        # tuple of tags where the both tags must exist if one is specified
        if (self.checks['check_missing_other_tags_both_ways'] is True):
            if ('missing_other_tags_both_ways' not in config_data):
                logging.error("'check_missing_other_tags_both_ways' is activated, but 'missing_other_tags_both_ways' data is not specified!")
                sys.exit(1)
            if (not isinstance(config_data['missing_other_tags_both_ways'], list)):
                logging.error("'missing_other_tags_both_ways' must be a list!")
                sys.exit(1)
            self.checks['missing_other_tags_both_ways'] = []
            for data in config_data['missing_other_tags_both_ways']:
                if ('tag1' in data and 'tag2' in data):
                    self.checks['missing_other_tags_both_ways'].append([data['tag1'], data['tag2']])
                else:
                    logging.error("Both 'tag1' and 'tag2' must be specified in 'missing_other_tags_both_ways'!")
                    sys.exit(1)

        # list of words which must be cursive
        if (self.checks['check_missing_cursive'] is True):
            if ('missing_cursive' not in config_data):
                logging.error("'check_missing_cursive' is activated, but 'missing_cursive' data is not specified!")
                sys.exit(1)
            if (not isinstance(config_data['missing_cursive'], list)):
                logging.error("'missing_cursive' must be a list!")
                sys.exit(1)
            self.checks['missing_cursive'] = config_data['missing_cursive']

        # list of words which are forbidden in postings
        if (self.checks['check_forbidden_words'] is True):
            if ('forbidden_words' not in config_data):
                logging.error("'check_forbidden_words' is activated, but 'forbidden_words' data is not specified!")
                sys.exit(1)
            if (not isinstance(config_data['forbidden_words'], list)):
                logging.error("'forbidden_words' must be a list!")
                sys.exit(1)
            self.checks['forbidden_words'] = config_data['forbidden_words']

        # list of websites which are forbidden in postings
        if (self.checks['check_forbidden_websites'] is True):
            if ('forbidden_websites' not in config_data):
                logging.error("'check_forbidden_websites' is activated, but 'forbidden_websites' data is not specified!")
                sys.exit(1)
            if (not isinstance(config_data['forbidden_websites'], list)):
                logging.error("'forbidden_websites' must be a list!")
                sys.exit(1)
            self.checks['forbidden_websites'] = config_data['forbidden_websites']
            for data in config_data['forbidden_websites']:
                if (data.startswith('http') or '://' in data):
                    logging.error("The link must not include the protocol!")
                    logging.error("Link: {o}".format(o = data))
                    sys.exit(1)

        # maximum size for objects in the posting directory
        if (self.checks['check_image_size'] is True):
            if ('image_size' not in config_data):
                logging.error("'check_image_size' is activated, but 'image_size' data is not specified!")
                sys.exit(1)
            try:
                self.checks['image_size'] = config_data['image_size'] = int(config_data['image_size'])
                if (self.checks['image_size'] <= 0):
                    logging.error("Image size must be greater zero!")
                    sys.exit(1)
            except ValueError:
                logging.error("Image size ('image_size') is not an integer!")
                sys.exit(1)


    def files(self):
        return self.arguments.remainder


# end Config class
#######################################################################



#######################################################################
# helper functions




# handle_markdown_file()
#
# handle the checks for a single Markdown filr
#
# parameter:
#  - config handle
#  - filename of Markdown file
# return:
#  - 0/1 (0: ok, 1: something wrong or changed)
def handle_markdown_file(config, filename):
    global log_entries

    logging.debug("Working on file: {f}".format(f = filename))
    with open(filename) as fh:
        data = fh.read()


    # reset the log array
    log_entries = []
    rc = 0

    # work on a copy of the original content
    output = data

    frontmatter, body = split_file_into_frontmatter_and_markdown(data, filename)

    if (config.checks['check_whitespaces_at_end']):
        output = check_whitespaces_at_end(config, output, filename, frontmatter)

    if (config.checks['check_find_more_separator']):
        output = check_find_more_separator(config, output, filename, frontmatter)

    if (config.checks['check_find_3_headline']):
        output = check_find_3_headline(config, output, filename, frontmatter)

    if (config.checks['check_find_4_headline']):
        output = check_find_4_headline(config, output, filename, frontmatter)

    if (config.checks['check_find_5_headline']):
        output = check_find_5_headline(config, output, filename, frontmatter)

    if (config.checks['check_missing_tags']):
        output = check_missing_tags(config, output, filename, frontmatter)

    if (config.checks['check_missing_words_as_tags']):
        output = check_missing_words_as_tags(config, output, filename, frontmatter)

    if (config.checks['check_lowercase_tags']):
        output = check_lowercase_tags(config, output, filename, frontmatter)

    if (config.checks['check_lowercase_categories']):
        output = check_lowercase_categories(config, output, filename, frontmatter)

    if (config.checks['check_missing_other_tags_one_way']):
        output = check_missing_other_tags_one_way(config, output, filename, frontmatter)

    if (config.checks['check_missing_other_tags_both_ways']):
        output = check_missing_other_tags_both_ways(config, output, filename, frontmatter)

    if (config.checks['check_missing_cursive']):
        output = check_missing_cursive(config, output, filename, frontmatter)

    if (config.checks['check_http_link']):
        output = check_http_link(config, output, filename, frontmatter)

    if (config.checks['check_hugo_localhost']):
        output = check_hugo_localhost(config, output, filename, frontmatter)

    if (config.checks['check_i_i_am']):
        output = check_i_i_am(config, output, filename, frontmatter)

    if (config.checks['check_changeme']):
        output = check_changeme(config, output, filename, frontmatter)

    if (config.checks['check_code_blocks']):
        output = check_code_blocks(config, output, filename, frontmatter)

    if (config.checks['check_psql_code_blocks']):
        output = check_psql_code_blocks(config, output, filename, frontmatter)

    if (config.checks['check_image_inside_preview']):
        output = check_image_inside_preview(config, output, filename, frontmatter)

    if (config.checks['check_preview_thumbnail']):
        output = check_preview_thumbnail(config, output, filename, frontmatter)

    if (config.checks['check_preview_description']):
        output = check_preview_description(config, output, filename, frontmatter)

    if (config.checks['check_image_size']):
        output = check_image_size(config, output, filename, frontmatter)

    if (config.checks['check_dass']):
        output = check_dass(config, output, filename, frontmatter)

    if (config.checks['check_empty_line_after_header']):
        output = check_empty_line_after_header(config, output, filename, frontmatter)

    if (config.checks['check_empty_line_after_list']):
        output = check_empty_line_after_list(config, output, filename, frontmatter)

    if (config.checks['check_empty_line_after_code']):
        output = check_empty_line_after_code(config, output, filename, frontmatter)

    if (config.checks['check_forbidden_words']):
        output = check_forbidden_words(config, output, filename, frontmatter)

    if (config.checks['check_forbidden_websites']):
        output = check_forbidden_websites(config, output, filename, frontmatter)

    if (config.checks['do_remove_whitespaces_at_end']):
        output = do_remove_whitespaces_at_end(config, output, filename, frontmatter)

    if (config.checks['do_replace_broken_links']):
        output = do_replace_broken_links(config, output, filename, frontmatter)

    if (len(log_entries) > 0):
        rc = 1
        print("File: {f}".format(f = os.path.realpath(filename)))
        for i in log_entries:
            print(i)

    if (output != data):
        rc = 1
        logging.info("File is CHANGED!")
        if (config.arguments.dry_run):
            if (config.arguments.print_dry):
                logging.debug("Dry-run mode, output file:")
                print(output)
        else:
            logging.info("Write changed file ({f})".format(f = filename))
            with open(filename, "w") as fh:
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
def split_file_into_frontmatter_and_markdown(data, filename):
    if (data[0:4] != "---\n"):
        logging.error("Content does not start with Frontmatter!")
        logging.error("File: {f}".format(f = filename))
        sys.exit(1)

    parts = re.search(r'^---\n(.*?)\n---\n(.*)$', data, re.DOTALL)
    if (not parts):
        logging.error("Can't extract Frontmatter from data!")
        logging.error("File: {f}".format(f = filename))
        sys.exit(1)

    frontmatter = parts.group(1).strip()
    body = parts.group(2).strip()

    return frontmatter, body


# supresswarnings()
#
# find out if a warning should be supressed
#
# parameter:
#  - frontmatter
#  - the name of the warning to supress
# return:
#  - True/False
def supresswarnings(frontmatter, name):
    yml = yaml.safe_load(frontmatter)
    if ('supresswarnings' not in yml):
        # nothing in Fromtmatter
        return False

    sw = yml['supresswarnings']
    if (sw is None):
        # it's empty
        return False
    if (name in sw):
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
def split_text_into_tokens(data):
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
def line_is_list(line):
    list_pattern = re.compile(r'^\s*([-*+]|\d+\.)\s+.*', re.MULTILINE)

    return bool(list_pattern.match(line))


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
def check_whitespaces_at_end(config, data, filename, init_frontmatter):
    global log_entries

    if (supresswarnings(init_frontmatter, 'skip_whitespaces_at_end')):
        return data

    lines = data.splitlines()
    found_whitespaces = 0
    for line in lines:
        if (len(line) == 0):
            pass
        else:
            if (line[0] == '>'):
                # that's a quote, do not remove spaces at the end
                pass
            else:
                if (line != line.rstrip()):
                    found_whitespaces += 1

    if (found_whitespaces > 1):
        log_entries.append("Found {n} lines with whitespaces at the end".format(n = found_whitespaces))
        log_entries.append("  Use 'skip_whitespaces_at_end' in 'supresswarnings' to silence this warning")
    elif (found_whitespaces == 1):
        log_entries.append("Found 1 line with whitespaces at the end")
        log_entries.append("  Use 'skip_whitespaces_at_end' in 'supresswarnings' to silence this warning")

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
def check_find_more_separator(config, data, filename, init_frontmatter):
    global log_entries

    if (supresswarnings(init_frontmatter, 'skip_more_separator')):
        return data

    frontmatter, body = split_file_into_frontmatter_and_markdown(data, filename)

    if ('<!--more-->' not in body):
        if (not supresswarnings(frontmatter, 'more_separator')):
            log_entries.append("Missing '<!--more-->' separator in Markdown!")
            log_entries.append("  Use 'skip_more_separator' in 'supresswarnings' to silence this warning")

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
def check_find_3_headline(config, data, filename, init_frontmatter):
    global log_entries

    if (supresswarnings(init_frontmatter, 'skip_headline3')):
        return data

    frontmatter, body = split_file_into_frontmatter_and_markdown(data, filename)

    if ('### ' in data):
        if (not supresswarnings(frontmatter, 'headline3')):
            log_entries.append("Headline 3 in Markdown!")
            log_entries.append("  Use 'skip_headline3' in 'supresswarnings' to silence this warning")

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
def check_find_4_headline(config, data, filename, init_frontmatter):
    global log_entries

    if (supresswarnings(init_frontmatter, 'skip_headline4')):
        return data

    frontmatter, body = split_file_into_frontmatter_and_markdown(data, filename)

    if ('#### ' in data):
        if (not supresswarnings(frontmatter, 'headline4')):
            log_entries.append("Headline 4 in Markdown!")
            log_entries.append("  Use 'skip_headline4' in 'supresswarnings' to silence this warning")

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
def check_find_5_headline(config, data, filename, init_frontmatter):
    global log_entries

    if (supresswarnings(init_frontmatter, 'skip_headline5')):
        return data

    frontmatter, body = split_file_into_frontmatter_and_markdown(data, filename)

    if ('##### ' in data):
        if (not supresswarnings(frontmatter, 'headline5')):
            log_entries.append("Headline 5 in Markdown!")
            log_entries.append("  Use 'skip_headline5' in 'supresswarnings' to silence this warning")

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
def check_missing_tags(config, data, filename, init_frontmatter):
    global log_entries

    frontmatter, body = split_file_into_frontmatter_and_markdown(data, filename)

    tokens, unique_tokens, lc_tokens = split_text_into_tokens(body)
    lc_tokens = [x.strip('*') for x in lc_tokens]
    lc_tokens = [x.strip('`') for x in lc_tokens]

    yml = yaml.safe_load(frontmatter)
    try:
        tags = yml['tags']
    except KeyError:
        log_entries.append("No tags found!")
        return data
    body_string = data.replace("\n", " ")

    if (not isinstance(tags, list)):
        log_entries.append("Tags is not a list!")
        return data

    for mt in config.checks['missing_tags']:
        word = mt[0]
        tag = mt[1]
        tag_not_found = False
        if (word in body_string):
            if (tag not in tags):
                if (not supresswarnings(frontmatter, 'skip_missing_tags_' + tag)):
                    tag_not_found = True
        if (word in lc_tokens):
            if (tag not in tags):
                if (not supresswarnings(frontmatter, 'skip_missing_tags_' + tag)):
                    tag_not_found = True

        if (tag_not_found):
            log_entries.append("'{t}' tag is missing".format(t = tag))
            log_entries.append("  Use 'skip_missing_tags_{t}' in 'supresswarnings' to silence this warning".format(t = tag))

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
def check_missing_words_as_tags(config, data, filename, init_frontmatter):
    global log_entries

    frontmatter, body = split_file_into_frontmatter_and_markdown(data, filename)

    tokens, unique_tokens, lc_tokens = split_text_into_tokens(body)
    lc_tokens = [x.strip('*') for x in lc_tokens]
    lc_tokens = [x.strip('`') for x in lc_tokens]

    yml = yaml.safe_load(frontmatter)
    try:
        tags = yml['tags']
    except KeyError:
        log_entries.append("No tags found!")
        return data
    body_string = data.replace("\n", " ")

    if (not isinstance(tags, list)):
        log_entries.append("Tags is not a list!")
        return data

    for mt in config.checks['missing_words']:
        word = mt.lower()
        tag_not_found = False
        if (word in lc_tokens):
            if (word not in tags):
                if (not supresswarnings(frontmatter, 'skip_missing_words_' + word)):
                    tag_not_found = True

        if (tag_not_found):
            log_entries.append("'{t}' tag is missing".format(t = word))
            log_entries.append("  Use 'skip_missing_words_{t}' in 'supresswarnings' to silence this warning".format(t = word))

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
def check_lowercase_tags(config, data, filename, init_frontmatter):
    global log_entries

    # tags should be lowercase, no spaces,
    # and not include characters which must be escaped in the URL

    frontmatter, body = split_file_into_frontmatter_and_markdown(data, filename)

    yml = yaml.safe_load(frontmatter)
    try:
        tags = yml['tags']
    except KeyError:
        log_entries.append("No tags found!")
        return data
    body_string = data.replace("\n", " ")

    if (not isinstance(tags, list)):
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
        if (result):
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
def check_lowercase_categories(config, data, filename, init_frontmatter):
    global log_entries

    # categories should be lowercase, no spaces,
    # and not include characters which must be escaped in the URL

    frontmatter, body = split_file_into_frontmatter_and_markdown(data, filename)

    yml = yaml.safe_load(frontmatter)
    try:
        categories = yml['categories']
    except KeyError:
        log_entries.append("No categories found!")
        return data
    body_string = data.replace("\n", " ")

    if (not isinstance(categories, list)):
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
        if (result):
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
def check_missing_other_tags_one_way(config, data, filename, init_frontmatter):
    global log_entries

    frontmatter, body = split_file_into_frontmatter_and_markdown(data, filename)

    yml = yaml.safe_load(frontmatter)
    try:
        tags = yml['tags']
    except KeyError:
        log_entries.append("No tags found!")
        return data
    body_string = data.replace("\n", " ")

    if (not isinstance(tags, list)):
        log_entries.append("Tags is not a list!")
        return data

    for mt in config.checks['missing_other_tags_one_way']:
        tag1 = mt[0]
        tag2 = mt[1]
        if (tag1 in tags):
            if (tag2 not in tags):
                if (not supresswarnings(frontmatter, 'skip_missing_other_tags_one_way_' + tag1 + '_' + tag2)):
                    log_entries.append("Found '{t1}' tag but '{t2}' tag is missing".format(t1 = tag1, t2 = tag2))
                    log_entries.append("  Use 'skip_missing_other_tags_one_way_{t1}_{t2}' in 'supresswarnings' to silence this warning".format(t1 = tag1, t2 = tag2))

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
def check_missing_other_tags_both_ways(config, data, filename, init_frontmatter):
    global log_entries

    frontmatter, body = split_file_into_frontmatter_and_markdown(data, filename)

    yml = yaml.safe_load(frontmatter)
    try:
        tags = yml['tags']
    except KeyError:
        log_entries.append("No tags found!")
        return data
    body_string = data.replace("\n", " ")

    if (not isinstance(tags, list)):
        log_entries.append("Tags is not a list!")
        return data

    for mt in config.checks['missing_other_tags_both_ways']:
        tag1 = mt[0]
        tag2 = mt[1]
        if (tag1 in tags):
            if (tag2 not in tags):
                if (not supresswarnings(frontmatter, 'skip_missing_other_tags_both_ways_' + tag1 + '_' + tag2)):
                    log_entries.append("Found '{t1}' tag but '{t2}' tag is missing".format(t1 = tag1, t2 = tag2))
                    log_entries.append("  Use 'skip_missing_other_tags_both_ways_{t1}_{t2}' in 'supresswarnings' to silence this warning".format(t1 = tag1, t2 = tag2))
        tag1 = mt[1]
        tag2 = mt[0]
        if (tag1 in tags):
            if (tag2 not in tags):
                if (not supresswarnings(frontmatter, 'skip_missing_other_tags_both_ways_' + tag1 + '_' + tag2)):
                    log_entries.append("Found '{t1}' tag but '{t2}' tag is missing".format(t1 = tag1, t2 = tag2))
                    log_entries.append("  Use 'skip_missing_other_tags_both_ways_{t1}_{t2}' in 'supresswarnings' to silence this warning".format(t1 = tag1, t2 = tag2))

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
def check_missing_cursive(config, data, filename, init_frontmatter):
    global log_entries

    frontmatter, body = split_file_into_frontmatter_and_markdown(data, filename)

    lines = body.splitlines()
    lines2 = []
    for line in lines:
        if (line.startswith('#')):
            # skip headlines
            pass
        elif (line.startswith('>')):
            # skip quotes
            pass
        else:
            lines2.append(line)
    body = "\n".join(lines2)

    tokens, unique_tokens, lc_tokens = split_text_into_tokens(body)

    for mc in config.checks['missing_cursive']:
        if (mc in unique_tokens):
            if (not supresswarnings(frontmatter, 'skip_missing_cursive_' + mc)):
                log_entries.append("Found non-cursive token: {t}".format(t = mc))
                log_entries.append("  Use 'skip_missing_cursive_{t}' in 'supresswarnings' to silence this warning".format(t = mc))

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
def check_http_link(config, data, filename, init_frontmatter):
    global log_entries

    if (supresswarnings(init_frontmatter, 'skip_httplink')):
        return data

    frontmatter, body = split_file_into_frontmatter_and_markdown(data, filename)

    if ('http://' in body):
        log_entries.append("Found 'http://' link")
        log_entries.append("  Use 'skip_httplink' in 'supresswarnings' to silence this warning")

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
def check_hugo_localhost(config, data, filename, init_frontmatter):
    global log_entries

    if (supresswarnings(init_frontmatter, 'skip_hugo_localhost')):
        return data

    frontmatter, body = split_file_into_frontmatter_and_markdown(data, filename)

    if ('http://localhost:1313/' in body):
        log_entries.append("Found Hugo preview link")
        log_entries.append("  Use 'skip_hugo_localhost' in 'supresswarnings' to silence this warning")

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
def check_i_i_am(config, data, filename, init_frontmatter):
    global log_entries

    if (supresswarnings(init_frontmatter, 'skip_i_in_text') and supresswarnings(init_frontmatter, 'skip_i_am_in_text')):
        return data

    frontmatter, body = split_file_into_frontmatter_and_markdown(data, filename)

    body = body.replace("\n", " ")
    if (' i ' in body):
        if (not supresswarnings(frontmatter, 'skip_i_in_text')):
            log_entries.append("Found lowercase 'i' in text")
            log_entries.append("  Use 'skip_i_in_text' in 'supresswarnings' to silence this warning")
    if (' i\'m ' in body):
        if (not supresswarnings(frontmatter, 'skip_i_am_in_text')):
            log_entries.append("Found lowercase 'i\'m' in text")
            log_entries.append("  Use 'skip_i_am_in_text' in 'supresswarnings' to silence this warning")

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
def check_changeme(config, data, filename, init_frontmatter):
    global log_entries

    if (supresswarnings(init_frontmatter, 'skip_changeme_tag') and supresswarnings(init_frontmatter, 'skip_changeme_category')):
        return data

    frontmatter, body = split_file_into_frontmatter_and_markdown(data, filename)

    yml = yaml.safe_load(frontmatter)
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

    if ('changeme' in tags):
        if (not supresswarnings(frontmatter, 'skip_changeme_tag')):
            log_entries.append("Found 'changeme' tag!")
            log_entries.append("  Use 'skip_changeme_tag' in 'supresswarnings' to silence this warning")

    if ('changeme' in categories):
        if (not supresswarnings(frontmatter, 'skip_changeme_category')):
            log_entries.append("Found 'changeme' category!")
            log_entries.append("  Use 'skip_changeme_category' in 'supresswarnings' to silence this warning")

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
def check_code_blocks(config, data, filename, init_frontmatter):
    global log_entries

    if (supresswarnings(init_frontmatter, 'skip_unmatching_code_blocks')):
        return data

    frontmatter, body = split_file_into_frontmatter_and_markdown(data, filename)

    lines = body.splitlines()

    count_opening_tags = 0
    count_closing_tags = 0

    # code blocks are expected to have a type specified
    # like: ```natural, or ```basic

    for line in lines:
        if (line[0:3] == '```' and len(line) > 3):
            count_opening_tags += 1
        if (line == '```'):
            count_closing_tags += 1

    if (count_opening_tags > 0 or count_closing_tags > 0):
        if (count_opening_tags != count_closing_tags):
            log_entries.append("Found ummatching fenced code blocks")
            log_entries.append("  Use 'skip_unmatching_code_blocks' in 'supresswarnings' to silence this warning")
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
def check_psql_code_blocks(config, data, filename, init_frontmatter):
    global log_entries

    if (supresswarnings(init_frontmatter, 'skip_psql_code')):
        return data

    frontmatter, body = split_file_into_frontmatter_and_markdown(data, filename)

    lines = body.splitlines()

    count_opening_psql_tags = 0

    for line in lines:
        if (line == '```psql' or line == '````psql'):
            count_opening_psql_tags += 1

    if (count_opening_psql_tags > 0):
        log_entries.append("Found 'psql' code blocks, use 'postgresql' instead")
        log_entries.append("  Use 'skip_psql_code' in 'supresswarnings' to silence this warning")

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
def check_image_inside_preview(config, data, filename, init_frontmatter):
    global log_entries

    if (supresswarnings(init_frontmatter, 'skip_image_inside_preview')):
        return data

    frontmatter, body = split_file_into_frontmatter_and_markdown(data, filename)

    if ('<!--more-->' not in data):
        if ('![' in data):
            log_entries.append("Found image in preview, but no preview separator")
            log_entries.append("  Use 'skip_image_inside_preview' in 'supresswarnings' to silence this warning")
    else:
        body_parts = body.split('<!--more-->')

        # only interested in images in the preview
        if ('![' in body_parts[0]):
            log_entries.append("Found image in preview, move it further down")
            log_entries.append("  Use 'skip_image_inside_preview' in 'supresswarnings' to silence this warning")

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
def check_preview_thumbnail(config, data, filename, init_frontmatter):
    global log_entries

    if (supresswarnings(init_frontmatter, 'skip_preview_thumbnail')):
        return data

    frontmatter, body = split_file_into_frontmatter_and_markdown(data, filename)

    yml = yaml.safe_load(frontmatter)
    try:
        thumbnail = yml['thumbnail']
    except KeyError:
        thumbnail = ''

    if (thumbnail is None or len(thumbnail) < 1):
        log_entries.append("Found no preview image in header")
        log_entries.append("  Use 'skip_preview_thumbnail' in 'supresswarnings' to silence this warning")

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
def check_preview_description(config, data, filename, init_frontmatter):
    global log_entries

    if (supresswarnings(init_frontmatter, 'skip_preview_description')):
        return data

    frontmatter, body = split_file_into_frontmatter_and_markdown(data, filename)

    yml = yaml.safe_load(frontmatter)
    try:
        description = yml['description']
    except KeyError:
        description = ''

    if (description is None or len(description) < 1):
        log_entries.append("Found no preview description in header")
        log_entries.append("  Use 'skip_preview_description' in 'supresswarnings' to silence this warning")

    return data


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
def check_image_size(config, data, filename, init_frontmatter):
    global log_entries

    if (supresswarnings(init_frontmatter, 'skip_image_size')):
        return data

    frontmatter, body = split_file_into_frontmatter_and_markdown(data, filename)

    # this scans the same directory as the Markdown file
    # and therefore only works for Hugo Page Bundles
    # https://gohugo.io/content-management/page-bundles/
    # this does not scan the static directory

    max_image_size = config.checks['image_size']

    dirname = os.path.dirname(filename)
    found_large_files = []
    for rootdir, dirnames, filenames in os.walk(dirname):
        for this_filename in filenames:
            if (rootdir != dirname):
                # only want files in the same directory
                continue
            this_file = os.path.join(rootdir, this_filename)
            this_stat = os.stat(this_file)
            if (this_stat.st_size > max_image_size):
                found_large_files.append(this_file)

    if (len(found_large_files) > 0):
            log_entries.append("Found large images, either resize them or:")
            log_entries.append("  Use 'skip_image_size' to supress this warning")
            for n in found_large_files:
                log_entries.append("  Large file: {lf}".format(lf = n))

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
def check_dass(config, data, filename, init_frontmatter):
    global log_entries

    if (supresswarnings(init_frontmatter, 'skip_dass')):
        return data

    frontmatter, body = split_file_into_frontmatter_and_markdown(data, filename)

    if ('daß' in body):
        log_entries.append("Found 'daß' in text")
        log_entries.append("  Use 'skip_dass' in 'supresswarnings' to silence this warning")

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
def check_empty_line_after_header(config, data, filename, init_frontmatter):
    global log_entries

    if (supresswarnings(init_frontmatter, 'skip_empty_line_after_header')):
        return data

    frontmatter, body = split_file_into_frontmatter_and_markdown(data, filename)

    lines = body.splitlines()

    last_line_is_header = False
    last_header_line = ""
    in_code_block = False

    for line in lines:
        if (line[0:3] == '```'):
            if (not in_code_block):
                in_code_block = True
            else:
                in_code_block = False
            continue
        if (in_code_block):
            # do not check code, that's a false positive
            continue

        if (len(line) == 0):
            last_line_is_header = False
            last_header_line = ""
        elif (line[0:1] != '#' and last_line_is_header):
            # last line was a header, this line is not empty
            log_entries.append("Missing empty line after header")
            log_entries.append("  Use 'skip_empty_line_after_header' in 'supresswarnings' to silence this warning")
            log_entries.append("  Header: {h}".format(h = last_header_line))

        if (line[0:1] == '#'):
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
def check_empty_line_after_list(config, data, filename, init_frontmatter):
    global log_entries

    if (supresswarnings(init_frontmatter, 'skip_empty_line_after_list')):
        return data

    frontmatter, body = split_file_into_frontmatter_and_markdown(data, filename)

    lines = body.splitlines()

    last_line_is_list = False
    in_code_block = False

    for line in lines:
        if (line[0:3] == '```'):
            if (not in_code_block):
                in_code_block = True
            else:
                in_code_block = False
            continue
        if (in_code_block):
            # do not check code, that's a false positive
            continue

        if (len(line) == 0):
            last_line_is_list = False
        elif (not line_is_list(line) and last_line_is_list):
            # last line was a list, this line is not empty
            log_entries.append("Missing empty line after list")
            log_entries.append("  Use 'skip_empty_line_after_list' in 'supresswarnings' to silence this warning")

        if (line_is_list(line)):
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
def check_empty_line_after_code(config, data, filename, init_frontmatter):
    global log_entries

    if (supresswarnings(init_frontmatter, 'skip_empty_line_after_code')):
        return data

    frontmatter, body = split_file_into_frontmatter_and_markdown(data, filename)

    lines = body.splitlines()

    in_code_block = False
    last_line_ends_code_block = False

    for line in lines:
        if (last_line_ends_code_block and len(line) > 0):
            log_entries.append("Missing empty line after code block")
            log_entries.append("  Use 'skip_empty_line_after_code' in 'supresswarnings' to silence this warning")

        if (line[0:3] == '```' and not in_code_block):
            in_code_block = True
            continue
        if (line == '```' and in_code_block):
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
def check_forbidden_words(config, data, filename, init_frontmatter):
    global log_entries

    frontmatter, body = split_file_into_frontmatter_and_markdown(data, filename)

    for fb in config.checks['forbidden_words']:
        if (fb in body):
            if (not supresswarnings(frontmatter, 'skip_forbidden_words_' + fb)):
                log_entries.append("Found forbidden word: {t}".format(t = fb))
                log_entries.append("  Use 'skip_forbidden_words_{t}' in 'supresswarnings' to silence this warning".format(t = fb))

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
def check_forbidden_websites(config, data, filename, init_frontmatter):
    global log_entries

    frontmatter, body = split_file_into_frontmatter_and_markdown(data, filename)

    for fw in config.checks['forbidden_websites']:
        found_fw = False

        link = 'https://' + fw + '/'
        if (fw in body):
            found_fw = True

        link = 'https://' + fw
        if (fw in body):
            found_fw = True

        link = 'http://' + fw + '/'
        if (fw in body):
            found_fw = True

        link = 'http://' + fw
        if (fw in body):
            found_fw = True

        if (found_fw):
            if (not supresswarnings(frontmatter, 'skip_forbidden_websites_' + fw)):
                log_entries.append("Found forbidden website: {t}".format(t = fw))
                log_entries.append("  Use 'skip_forbidden_websites_{t}' in 'supresswarnings' to silence this warning".format(t = fw))

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
def do_remove_whitespaces_at_end(config, data, filename, init_frontmatter):
    global log_entries

    if (supresswarnings(init_frontmatter, 'skip_do_remove_whitespaces_at_end')):
        return data

    lines = data.splitlines()
    output = []
    for line in lines:
        if (len(line) == 0):
            output.append(line)
        else:
            if (line[0] == '>'):
                # that's a quote, do not remove spaces at the end
                output.append(line)
            else:
                output.append(line.rstrip())

    output = "\n".join(output) + "\n"

    if (data != output):
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
def do_replace_broken_links(config, data, filename, init_frontmatter):
    global log_entries

    if (supresswarnings(init_frontmatter, 'skip_do_replace_broken_links')):
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

    if (data != output):
        log_entries.append("Replacing broken links")

    return output





#######################################################################
# main

def main():
    config = Config()
    config.parse_parameters()
    config.read_config()

    global_rc = 0
    files = config.files()
    if (len(files) > 0):
        for f in files:
            rc = handle_markdown_file(config, f)
            if (rc != 0):
                global_rc = 1
    else:
        # find all index.md files
        start = "content/post"
        for rootpath, dirs, files in os.walk(start):
            for filename in files:
                if (not filename.endswith(".md")):
                    continue
                rc = handle_markdown_file(config, os.path.join(rootpath, filename))
                if (rc != 0):
                    global_rc = 1

    return global_rc


if __name__ == '__main__':
    rc = main()

    sys.exit(rc)
