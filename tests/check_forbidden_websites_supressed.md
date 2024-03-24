---
title: "forbidden websites"
date: 2024-01-01T00:00:00+00:00
draft: false
authors: ads
categories:
- testing
tags:
- testing
supresswarnings:
- skip_forbidden_websites_example.arpa
- skip_forbidden_websites_example.invalid
---

This blog post checks for forbidden websites in the posting

As example, the .example website example.invalid shall not appear, another example. is

https://example.invalid
https://example.invalid/
https://example.invalid/somelink

http://example.invalid
http://example.invalid/
http://example.invalid/anotherlink

Also don't allow example.arpa as website.