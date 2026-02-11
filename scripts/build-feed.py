#!/usr/bin/env python3
"""
Build script to generate an RSS feed (feed.xml) from puzzle JSON files.

Usage:
    python scripts/build-feed.py
"""

import json
import os
from datetime import datetime
from xml.etree.ElementTree import Element, SubElement, ElementTree, indent


EPOCH = datetime(2024, 1, 1)
SITE_URL = "https://cnmn.app"
FEED_TITLE = "cnmn"
FEED_DESCRIPTION = "A free daily synonym puzzle. New puzzle every day."
MAX_ITEMS = 30


def puzzle_number(date_str):
    """Calculate puzzle number from date (days since epoch + 1)."""
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    return (date_obj - EPOCH).days + 1


def build_feed():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(script_dir)
    puzzles_dir = os.path.join(root_dir, "puzzles")
    feed_path = os.path.join(root_dir, "feed.xml")

    today = datetime.now().strftime("%Y-%m-%d")

    # Collect puzzle files dated today or earlier
    puzzles = []
    for fname in os.listdir(puzzles_dir):
        if not fname.endswith(".json"):
            continue
        date_str = fname.replace(".json", "")
        if date_str > today:
            continue
        filepath = os.path.join(puzzles_dir, fname)
        with open(filepath, "r") as f:
            data = json.load(f)
        puzzles.append((date_str, data))

    # Sort by date descending, take latest 30
    puzzles.sort(key=lambda x: x[0], reverse=True)
    puzzles = puzzles[:MAX_ITEMS]

    # Build RSS XML
    rss = Element("rss", version="2.0")
    channel = SubElement(rss, "channel")
    SubElement(channel, "title").text = FEED_TITLE
    SubElement(channel, "link").text = SITE_URL
    SubElement(channel, "description").text = FEED_DESCRIPTION
    SubElement(channel, "language").text = "en"

    if puzzles:
        latest_date = datetime.strptime(puzzles[0][0], "%Y-%m-%d")
        SubElement(channel, "lastBuildDate").text = latest_date.strftime(
            "%a, %d %b %Y 06:00:00 +0000"
        )

    for date_str, data in puzzles:
        num = puzzle_number(date_str)
        theme = data.get("theme", "Puzzle")

        item = SubElement(channel, "item")
        SubElement(item, "title").text = f"cnmn #{num}: {theme}"
        SubElement(item, "link").text = SITE_URL
        SubElement(item, "description").text = (
            f"Today's theme: {theme}. Play now at cnmn.app!"
        )
        SubElement(item, "guid", isPermaLink="false").text = (
            f"cnmn-{date_str}"
        )
        pub_date = datetime.strptime(date_str, "%Y-%m-%d")
        SubElement(item, "pubDate").text = pub_date.strftime(
            "%a, %d %b %Y 06:00:00 +0000"
        )

    tree = ElementTree(rss)
    indent(tree, space="  ")

    with open(feed_path, "wb") as f:
        tree.write(f, encoding="utf-8", xml_declaration=True)

    print(f"Generated feed.xml with {len(puzzles)} items")


if __name__ == "__main__":
    build_feed()
