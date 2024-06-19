---
title: "missing tags both ways"
date: 2024-01-01T00:00:00+00:00
draft: false
authors: ads
categories:
- testing
tags:
- icecream
- osm
suppresswarnings:
- skip_missing_other_tags_both_ways_icecream_ice-cream
---

This blog post checks for missing tags which should appear. When one tag is given, the other tag should also appear. This goes both ways.

If `icecream` tag is there, the `ice-cream` tag must also be there, but this warning is silenced.

If `osm` tag is there, the `openstreetmap` tag must also be there (reversed tags).
