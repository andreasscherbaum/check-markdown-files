---
title: "check image size"
date: 2024-01-01T00:00:00+00:00
draft: false
authors: ads
categories:
- testing
tags:
- testing
supresswarnings:
- skip_image_size
---

This check ensures that any files in the same directory do not exceed a certain size limit.

This mostly makes sense with [Hugo Page Bundles](https://gohugo.io/content-management/page-bundles/), as this separates blog postings from each other, but also keeps the images in the blog posting directory.

The `image_size` size parameter must also be specified, and defines the maximum size of allowed objects.

The warning is silenced.
