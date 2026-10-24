"""Mirror the current EvoLink GPT Image 2 prompt gallery into Markdown."""

from __future__ import annotations

import html
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
SOURCE_URL = "https://evolink.ai/gpt-image-2-prompts"
OUTPUT = ROOT / "docs" / "evolink-gallery-2026.md"


def fetch(url: str) -> str:
    request = Request(url, headers={"User-Agent": "awesome-gpt-image-2-gallery-sync/1.0"})
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def clean(value: str) -> str:
    value = re.sub(r"<[^>]+>", "", value)
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def image_url(article: str) -> str:
    match = re.search(r'<img[^>]+src="([^"]+)"', article)
    if not match:
        return ""
    source = html.unescape(match.group(1))
    parsed = urlparse(source)
    if parsed.path == "/_next/image":
        encoded = parse_qs(parsed.query).get("url", [""])[0]
        return unquote(encoded)
    return source


def text(pattern: str, article: str) -> str:
    match = re.search(pattern, article, flags=re.S)
    return clean(match.group(1)) if match else ""


def item_list(page: str) -> dict[str, str]:
    for match in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', page, re.S):
        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if payload.get("@type") == "ItemList":
            return {item["name"]: item["url"] for item in payload.get("itemListElement", [])}
    raise RuntimeError("EvoLink ItemList schema was not found")


def parse_articles(page: str, links: dict[str, str]) -> list[dict[str, object]]:
    articles = re.findall(r"<article[^>]*>.*?</article>", page, flags=re.S)
    entries: list[dict[str, object]] = []
    for article in articles:
        title = text(r"<h3[^>]*>(.*?)</h3>", article)
        prompt = text(r"<p[^>]*max-h-0[^>]*>(.*?)</p>", article)
        summary = text(r"<h3[^>]*>.*?</h3>\s*</div>\s*<p[^>]*>(.*?)</p>", article)
        if not title or not prompt:
            continue
        labels = [
            clean(item)
            for item in re.findall(r"<span[^>]*>(.*?)</span>", article, flags=re.S)
        ]
        tags = [
            clean(item)
            for item in re.findall(r'<span class="[^"]*bg-neutral-100[^"]*">(.*?)</span>', article, flags=re.S)
        ]
        entries.append(
            {
                "title": title,
                "summary": summary,
                "prompt": prompt,
                "image": image_url(article),
                "labels": labels[:4],
                "tags": tags,
                "url": links.get(title, SOURCE_URL),
            }
        )
    if not entries:
        raise RuntimeError("No prompt cards were parsed from EvoLink")
    return entries


def render(entries: list[dict[str, object]]) -> str:
    lines = [
        "# EvoLink GPT Image 2 Prompt Gallery (2026)",
        "",
        f"> Synced from [EvoLink's current GPT Image 2 prompt gallery]({SOURCE_URL}) on {date.today().isoformat()}.",
        ">",
        "> This mirror follows the live card order and presentation metadata. The canonical 462-case README namespace remains unchanged.",
        "",
        f"**{len(entries)} featured examples** · images, summaries, tags, and copy-ready prompts",
        "",
    ]
    for index, entry in enumerate(entries, start=1):
        labels = " · ".join(str(label) for label in entry["labels"] if label)
        tags = ", ".join(str(tag) for tag in entry["tags"] if tag)
        lines.extend(
            [
                f"## {index}. [{entry['title']}]({entry['url']})",
                "",
                f"![{entry['title']}]({entry['image']})",
                "",
                f"**Display:** {labels or 'IMAGE'}",
                f"**Tags:** {tags or '—'}",
                "",
                str(entry["summary"]),
                "",
                "<details>",
                "<summary>Show prompt</summary>",
                "",
                "```text",
                str(entry["prompt"]),
                "```",
                "",
                "</details>",
                "",
            ]
        )
    return "\n".join(lines)


def main() -> None:
    page = fetch(SOURCE_URL)
    entries = parse_articles(page, item_list(page))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(render(entries), encoding="utf-8", newline="\n")
    print(f"synced {len(entries)} entries to {OUTPUT}")


if __name__ == "__main__":
    main()
