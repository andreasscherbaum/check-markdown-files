---
title: "Empty line after code"
date: 2024-01-01T00:00:00+00:00
draft: false
authors: ads
categories:
- testing
tags:
- testing
suppresswarnings:
- skip_empty_line_after_code
---

This blog posting checks that there are empty lines after list lines.
All error messages are silenced.

This blog posting checks that there are empty lines after header lines.

```natural
First code block
```
without an empty line afterwards


```postgresql
Second code block
```
without an empty line afterwards

```postgresql
Third code block
```

with an empty line afterwards

followed by text
