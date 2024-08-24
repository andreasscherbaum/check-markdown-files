---
title: "check image exif tags forbidden"
date: 2024-01-01T00:00:00+00:00
draft: false
authors: ads
categories:
- testing
tags:
- testing
suppresswarnings:
- skip_image_exif_tags_forbidden
---

This check ensures that forbidden EXIF tags in images are identified.

This mostly makes sense with [Hugo Page Bundles](https://gohugo.io/content-management/page-bundles/), as this separates blog postings from each other, but also keeps the images in the blog posting directory.

The `forbidden_exif_tags` size parameter must also be specified, and defines the list of forbidden EXIF tags.

The warning is silenced.
