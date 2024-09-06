
# Available checks

In `check-markdown-files.conf`, the following checks and config options are available. All checks are disabled by default, and can be enabled in the configuration file.

If a check is enabled, it applies to all Markdown files (global configuration). Most checks can be disabled on a local level, using flags in the `suppresswarnings` header in Frontmatter.

## check_whitespaces_at_end

Warn if whitespaces exist at the end of lines. This check [excludes quotes](https://andreas.scherbaum.la/post/2024-03-01_blockquotes-in-hugo/), as whitespaces are sometimes necessary there.

Disable this check locally with:

```
suppresswarnings:
- skip_whitespaces_at_end
```

## check_find_more_separator

Hugo uses the following separator to split preview and posting content:

```
<!--more-->
```

If this separator does not exist, the preview (as example used on the index page) is "calculated" based on a hardcoded number of characters at the beginning. This might not be a good cut, therefore it is desired to manually specify the separator, and control the content of the preview.

You can add this separator into your [archetypes](https://gohugo.io/content-management/archetypes/).

Disable this check locally with:

```
suppresswarnings:
- skip_more_separator
```

## check_find_3_headline

Level 3 headlines are relatively small headlines. Depending on the stylesheet they might not be recognizable. This check warns if level 3 headlines are used.

Disable this check locally with:

```
suppresswarnings:
- skip_headline3
```

## check_find_4_headline

Level 4 headlines are small headlines. Depending on the stylesheet they might not be recognizable. This check warns if level 4 headlines are used.

Disable this check locally with:

```
suppresswarnings:
- skip_headline4
```

## check_find_5_headline

Level 5 headlines are very small headlines. Depending on the stylesheet they might not be recognizable. This check warns if level 5 headlines are used.

Disable this check locally with:

```
suppresswarnings:
- skip_headline5
```

## check_missing_tags

This check defines a list of keywords and tags. If the keyword appears in the text, then the tag must also be specified.

Example:

```
check_missing_tags: True
missing_tags:
  - word: 'Raspberry Pi'
    tag: raspberry-pi
  - word: 'ice cream'
    tag: 'icecream'
  - word: 'icecream'
    tag: 'icecream'
  - word: 'Ice Cream'
    tag: 'icecream'
  - word: 'Ice cream'
    tag: 'icecream'
```

If the word `Raspberry Pi` appears in the text, then the tag `raspberry-pi` must also be specified. Same for the word `Ice Cream` in a number of variations.

Sometimes it is not desirable to add a tag for a specific blog posting, even though globally this word/tag combination is set. The check for every keyword can be skipped in a Markdown file by adding the `skip_missing_tags_*` flag, where `*` stands for the flag. Example:

```
suppresswarnings:
- skip_missing_tags_raspberry-pi
```

The example file `check-markdown-files.conf` in this repository comes with a long list of country and city names already filled in.

## missing_words_as_tags

This check defines a list of words which should also be tags. The words and tags are handled lower-case.

The difference to the `check_missing_tags` check is that `missing_words_as_tags` defines words which are 1:1 translated into tags. This makes it easier to define a simple list of words to look out for.

Example:

```
missing_words_as_tags: True
missing_words:
  - berlin
  - backup
  - touchscreen
```

Sometimes it is not desirable to add a tag for a specific blog posting, even though globally this word is set. The check for every keyword can be skipped in a Markdown file by adding the `skip_missing_words_*` flag, where `*` stands for the flag. Example:

```
suppresswarnings:
- skip_missing_words_berlin
```

The example file `check-markdown-files.conf` in this repository comes with a long list of country and city names already filled in.

## check_invalid_tags

This check ensures that tags have a certain format: all lowercase, no spaces, no special characters. The special characters, when URL encoded, show up as `%xx` combinations.

Example: `pizza&juice` is `pizza%26juice` in encoded in the URL.

This check can't be disabled locally.

## check_invalid_categories

This check ensures that categories have a certain format: all lowercase, no spaces, no special characters. The special characters, when URL encoded, show up as `%xx` combinations.

Example: `pizza&juice` is `pizza%26juice` in encoded in the URL.

This check can't be disabled locally.

## check_missing_other_tags_one_way

This check ensures that if one tag is specified, a corresponding tag is also specified. This makes most sense when special tags should also specify more general tags.

Example:

```
check_missing_other_tags_one_way: True
missing_other_tags_one_way:
  - tag1: pljava
    tag2: java
```

In the first example, if the `pljava` tag is specified, the `java` tag should also be included.

Every combination of tags can also be excluded in a Markdown file from the check. Example:

```
suppresswarnings:
- skip_missing_other_tags_one_way_pljava_java
```

## check_missing_other_tags_both_ways

This chech ensures that if one tag is specified, a second tag is also specified. This makes most sense when different variations of tags should all be inluded.

Example:

```
check_missing_other_tags_both_ways: True
missing_other_tags_both_ways:
  - tag1: icecream
    tag2: ice-cream
  - tag1: openstreetmap
    tag2: osm
```

The first example ensured two different ways for `icecream` as tags. The second example ensures that `openstreetmap` is always specified in the long and short form.

Every combination of tags can also be excluded in a Markdown file from the check. Example:

```
suppresswarnings:
- skip_missing_other_tags_both_ways_openstreetmap_osm
```

## check_missing_cursive

This check ensures that a list of words is written in cursive (using `*word*` in Markdown). For names or places it makes sense to specify them in cursive in the text, to highlight that this is not a regular word. This check is not applied on headlines. Example:

```
check_missing_cursive: True
missing_cursive:
  - Ansible
  - PostgreSQL
  - Berlin
  - London
```

This example ensures that the words `Ansible`, `PostgreSQL`, `Berlin` and `London` are cursive.

In a Markdown file this check can be excluded for a word. Example:

```
suppresswarnings:
- skip_missing_cursive_Ansible
```

## check_http_link

This check ensures that all links use `https` instead of `http`.

Sometimes web resources are not available as `https`, then the check can be disabled in a Markdown file:

```
suppresswarnings:
- skip_httplink
```

## check_i_i_am

The words `I` and `I'm` are written uppercase in the English language. That's a common oversight. This check ensures that all occurrences are indeed uppercase.

Both checks can be disabled locally:

```
suppresswarnings:
- skip_i_in_text
- skip_i_am_in_text
```

## check_hugo_localhost

When writing new blog postings, Hugo provides a [server mode](https://gohugo.io/commands/hugo_server/) which allows local preview of modified content. It so happens that sometimes people copy the local preview link (`http://localhost:1313/`) and insert it into blog postings. This check ensures that the preview links do not appear in published content.

If for some reason this check must be disabled in a Markdown file:

```
suppresswarnings:
- skip_hugo_localhost
```

## check_changeme

My archetype templates have `changeme` as pre-defined tags and categories. This reminds me to update them before publishing a posting.

This check verifies that no `changeme` tags or categories are left in a posting.

Both checks can be disabled locally:

```
suppresswarnings:
- skip_changeme_tag
- skip_changeme_category
```

## check_code_blocks

This check ensures that every code block has a syntax highlight type specified.

The list of supported types/languages [can be found here](https://gohugo.io/content-management/syntax-highlighting/).

Disable this check locally with:

```
suppresswarnings:
- skip_unmatching_code_blocks
```

## check_psql_code_blocks

This check ensures that code blocks use `postgresql` instead of `psql` highlighting.

Disable this check locally with:

```
suppresswarnings:
- skip_psql_code
```

## check_image_inside_preview

This check ensures that no image is in the preview part of the posting (the part before `<!--more-->`).

Not every template can properly show images in the description of a posting, and if shown then it increases the size of the preview.

Disable this check locally with:

```
suppresswarnings:
- skip_image_inside_preview
```

## check_preview_thumbnail

This check ensures that a `thumbnail` header with an image is specified. This allows more control over which image is used as preview image in a template.

Otherwise, if no preview image is specified in a blog posting header, social media platforms will pick the first image in a posting, or randomly pick an image.

Your Hugo template might use another field instead of `thumbnail`, or not provide this functionality at all.

Disable this check locally with:

```
suppresswarnings:
- skip_preview_thumbnail
```

## check_preview_description

This check ensures that a `description` header with a text is specified. This allows more control over which text is used as preview in a template.

Otherwise, if no description is specified in a blog posting header, social media platforms will pick some text from the posting.

Your Hugo template might use another field instead of `description`, or not provide this functionality at all.

Disable this check locally with:

```
suppresswarnings:
- skip_preview_description
```

## check_image_size

This check ensures that all images/files in a directory are within a specified size.

This check requires the `image_size` parameter to be set, and specify the max size in bytes. Example:

```
check_image_size: True
image_size: 1048576
```

Simply said, images for the WWW should not be too large. It takes more time to load larger images, and it consumes bandwidth on both the server and the user device.

Sometimes there is a legitimate need for larger images in a posting, disable this check locally with:

```
suppresswarnings:
- skip_image_size
```

## check_dass

This check ensures that no 'daß' is used in the text.
This is a German word, and according to newer writing rules it is no longer allowed.
Instead 'dass' should be used.

Disable this check locally with:

```
suppresswarnings:
- skip_dass
```

## check_empty_line_after_header

This check ensures that a header line (`# ...`) is followed by an empty line.

Disable this check locally with:

```
suppresswarnings:
- skip_empty_line_after_header
```

## check_empty_line_after_list

This check ensures that a list line (`- ...` or `* ...` or `1. ...`) is followed by an empty line.

Disable this check locally with:

```
suppresswarnings:
- skip_empty_line_after_list
```

## check_empty_line_after_code

This check ensures that a code block is followed by an empty line.

Disable this check locally with:

```
suppresswarnings:
- skip_empty_line_after_code
```

## check_lineendings

This check ensures that all files have the correct line ending. The type of line endings is specified in `lineendings`, and must be one of `unix`, `mac` or `windows`.

Disable this check locally with:

```
suppresswarnings:
- skip_lineendings
```

## check_forbidden_words

This check ensures that a list of words (basically any free text) does not appear in the posting. Example:

```
check_forbidden_words: True
forbidden_words:
  - Markdown
  - TestCase
```

This example ensures that the words `Markdown` and `TestCase` do not appear in the posting.

In a Markdown file this check can be excluded for a word. Example:

```
suppresswarnings:
- skip_forbidden_words_Markdown
```

## check_forbidden_websites

This check ensures that a list of websites (just the domain names) does not appear in the posting. Example:

```
check_forbidden_websites: True
forbidden_websites:
  - example.invalid
  - example.arpa
```

This example ensures that the websites `example.invalid` and `example.arpa` do not appear in the posting. The check will complete the domain with `https` and `http` for the check, and find links with and without trailing `/` slash.

In a Markdown file this check can be excluded for a word. Example:

```
suppresswarnings:
- skip_forbidden_websites_example.invalid
```

## check_header_field_length

This check ensures that specified header (Frontmatter) fields are present, and have a minimum length. Example:

```
check_header_field_length: True
header_field_length:
  - description: 10
```

This example ensures that the Frontmatter field `description` is present. It also specifies that the field must have a minimum length of 10 characters.

In a Markdown file the length check can be excluded. Example:

```
suppresswarnings:
- skip_header_field_length_description
```

The presence check for the field can't be skipped.

## check_double_brackets

This check find double opening and closing brackets. This is sometimes a leftover from an editor auto-completing an opening `(` with a closing `)`, which goes unnoticed. Example:

```
check_double_brackets: True
```

Disable this check locally with:

```
suppresswarnings:
- skip_double_brackets_opening
- skip_double_brackets_closing
```

## check_fixme

This check find `FIXME` texts (in upper and lower case) in the blog posting. Example:

```
check_fixme: True
```

Disable this check locally with:

```
suppresswarnings:
- skip_fixme
```

## do_remove_whitespaces_at_end

Remove whitespaces at the end of lines. This check [excludes quotes](https://andreas.scherbaum.la/post/2024-03-01_blockquotes-in-hugo/), as whitespaces are sometimes necessary there.

Disable this check locally with:

```
suppresswarnings:
- skip_do_remove_whitespaces_at_end
```

## do_replace_broken_links

Replace known broken links with replacement links. This allows to find and replace links which are no longer working, as example with archive.org links.

Disable this check locally with:

```
suppresswarnings:
- skip_do_replace_broken_links
```

This can be handled with the `check_forbidden_websites` check, and then manually updating the websites. Doing this in this script allows updating a large number of postings at once. Handle with care!
