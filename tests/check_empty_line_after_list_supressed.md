---
title: "Empty line after list"
date: 2024-01-01T00:00:00+00:00
draft: false
authors: ads
categories:
- testing
tags:
- testing
suppresswarnings:
- skip_empty_line_after_list
---

This blog posting checks that there are empty lines after list lines.
All error messages are silenced.

- a list
without empty line afterwards

- another
  - list
without empty line afterwards

* a
  * third
    * list
without empty line afterwards

1. numbered
2. list
without empty line afterwards

- and a list

followed by an empty line and
followed by text
