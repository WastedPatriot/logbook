#!/usr/bin/env python3
"""Build the logbook site from boxes/*/writeup.md.

No third-party libraries. Markdown support is the subset the template uses:
headings, paragraphs, lists, tables, quotes, fenced code, links, emphasis.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIFFICULTIES = ("Easy", "Medium", "Hard", "Insane")
KNOWN_KEYS = {
    "name",
    "os",
    "difficulty",
    "retired",
    "techniques",
    "summary",
    "example",
    "released",
    "retired_on",
    "updated",
}
DATE_KEYS = ("released", "retired_on", "updated")
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
TOKEN_RE = re.compile(r"`([^`]+)`|\[([^\]]+)\]\(([^)\s]+)\)")


class BuildError(Exception):
    pass


@dataclass
class Box:
    name: str
    slug: str
    os: str
    difficulty: str
    techniques: list[str]
    summary: str
    example: bool
    released: str | None
    retired_on: str | None
    updated: str | None
    body_html: str
    outline: list[tuple[str, str]]


def esc(value: str) -> str:
    return html.escape(value, quote=True)


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def stardate(when: date | None = None) -> str:
    when = when or date.today()
    # Year, a dot, the day of the year. Astronomy ends there.
    return f"{when.year}.{when.timetuple().tm_yday:03d}"


def display_date(iso: str) -> str:
    parsed = datetime.strptime(iso, "%Y-%m-%d")
    return f"{parsed.day} {parsed.strftime('%b %Y')}"


def parse_scalar(raw: str):
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in {'"', "'"}:
        return raw[1:-1]
    if raw == "true":
        return True
    if raw == "false":
        return False
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if not inner:
            return []
        return [parse_scalar(part.strip()) for part in inner.split(",") if part.strip()]
    return raw


def parse_frontmatter(text: str, path: Path) -> tuple[dict, str]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if not text.endswith("\n"):
        text += "\n"
    if not text.startswith("---\n"):
        raise BuildError(f"{rel(path)}: starts without --- frontmatter")
    end = text.find("\n---\n", 4)
    if end == -1:
        raise BuildError(f"{rel(path)}: frontmatter never closes")
    raw = text[4:end]
    body = text[end + 5 :].lstrip("\n")
    data: dict = {}
    list_key: str | None = None
    for lineno, line in enumerate(raw.splitlines(), start=2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith("  - "):
            if list_key is None:
                raise BuildError(f"{rel(path)}:{lineno}: list item without a key")
            data[list_key].append(parse_scalar(line[4:].strip()))
            continue
        if ":" not in line:
            raise BuildError(f"{rel(path)}:{lineno}: expected key: value")
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if not re.fullmatch(r"[a-z][a-z0-9_]*", key):
            raise BuildError(f"{rel(path)}:{lineno}: odd key {key!r}")
        if value in {">", "|", ">-", "|-", ">+", "|+"}:
            raise BuildError(
                f"{rel(path)}:{lineno}: keep {key} on one line. Folded scalars are not supported"
            )
        if value == "":
            data[key] = []
            list_key = key
        else:
            data[key] = parse_scalar(value)
            list_key = None
    return data, body


def check_date(path: Path, meta: dict, key: str) -> None:
    if key not in meta:
        return
    value = meta[key]
    if not isinstance(value, str):
        raise BuildError(f"{rel(path)}: {key} wants YYYY-MM-DD")
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise BuildError(f"{rel(path)}: {key} is not a real date") from exc


def validate(meta: dict, folder: Path) -> dict:
    path = folder / "writeup.md"
    unknown = set(meta) - KNOWN_KEYS
    if unknown:
        names = ", ".join(sorted(unknown))
        raise BuildError(f"{rel(path)}: unknown frontmatter ({names})")
    missing = [key for key in ("name", "os", "difficulty", "techniques", "summary") if key not in meta]
    if missing:
        raise BuildError(f"{rel(path)}: missing {', '.join(missing)}")
    if meta.get("retired") is not True:
        if meta.get("retired") is False:
            raise BuildError(f"{rel(path)}: retired is false. This log does not carry live boxes.")
        raise BuildError(f"{rel(path)}: retired must be true. This log does not carry live boxes.")
    name = meta["name"]
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 .'+-]{0,40}", name):
        raise BuildError(f"{rel(path)}: name is missing or peculiar")
    if slugify(name) != folder.name or not SLUG_RE.fullmatch(folder.name):
        raise BuildError(
            f"{rel(path)}: folder is {folder.name!r}, name slugifies to {slugify(name)!r}"
        )
    os_name = meta["os"]
    if not isinstance(os_name, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9 +./-]{0,31}", os_name):
        raise BuildError(f"{rel(path)}: os should be a short label such as Linux or Windows")
    if meta["difficulty"] not in DIFFICULTIES:
        joined = ", ".join(DIFFICULTIES)
        raise BuildError(f"{rel(path)}: difficulty must be one of {joined}")
    techniques = meta["techniques"]
    if not isinstance(techniques, list) or not techniques:
        raise BuildError(f"{rel(path)}: techniques must list at least one slug")
    for technique in techniques:
        if not isinstance(technique, str) or not SLUG_RE.fullmatch(technique):
            raise BuildError(f"{rel(path)}: technique {technique!r} wants lowercase words and hyphens")
    if len(techniques) != len(set(techniques)):
        raise BuildError(f"{rel(path)}: duplicate technique")
    summary = meta["summary"]
    if not isinstance(summary, str) or not summary.strip():
        raise BuildError(f"{rel(path)}: summary is empty")
    if "example" in meta and not isinstance(meta["example"], bool):
        raise BuildError(f"{rel(path)}: example wants true or false")
    for key in DATE_KEYS:
        check_date(path, meta, key)
    return meta


def safe_href(url: str) -> bool:
    if url.startswith(("#", "/", "./", "../")):
        return True
    lowered = url.lower()
    return lowered.startswith(("https://", "http://", "mailto:"))


def format_plain(raw: str) -> str:
    text = esc(raw)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)
    return text


def inline(raw: str) -> str:
    parts: list[str] = []
    cursor = 0
    for match in TOKEN_RE.finditer(raw):
        parts.append(format_plain(raw[cursor : match.start()]))
        if match.group(1) is not None:
            parts.append(f"<code>{esc(match.group(1))}</code>")
        else:
            href = match.group(3)
            if safe_href(href):
                parts.append(f'<a href="{esc(href)}">{format_plain(match.group(2))}</a>')
            else:
                parts.append(format_plain(match.group(0)))
        cursor = match.end()
    parts.append(format_plain(raw[cursor:]))
    return "".join(parts)


def split_row(line: str) -> list[str]:
    trimmed = line.strip()
    if trimmed.startswith("|"):
        trimmed = trimmed[1:]
    if trimmed.endswith("|"):
        trimmed = trimmed[:-1]
    return [cell.strip() for cell in trimmed.split("|")]


def is_separator(line: str) -> bool:
    cells = split_row(line)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def render_table(rows: list[str]) -> str:
    if len(rows) < 2 or not is_separator(rows[1]):
        raise BuildError("a table needs a header and a | --- | separator")
    header = split_row(rows[0])
    body: list[list[str]] = []
    for raw in rows[2:]:
        cells = split_row(raw)
        if len(cells) != len(header):
            raise BuildError(f"table row has {len(cells)} cells; the header has {len(header)}")
        body.append(cells)
    head = "".join(f"<th>{inline(cell)}</th>" for cell in header)
    rendered = []
    for cells in body:
        tds = "".join(f"<td>{inline(cell)}</td>" for cell in cells)
        rendered.append(f"<tr>{tds}</tr>")
    return "<table><thead><tr>" + head + "</tr></thead><tbody>" + "".join(rendered) + "</tbody></table>"


def render_markdown(src: str) -> tuple[str, list[tuple[str, str]]]:
    lines = src.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    html_parts: list[str] = []
    outline: list[tuple[str, str]] = []
    used: dict[str, int] = {}
    para: list[str] = []
    index = 0
    total = len(lines)

    def flush() -> None:
        if para:
            html_parts.append(f"<p>{inline(' '.join(para))}</p>")
            para.clear()

    def heading_id(text: str) -> str:
        base = slugify(text) or "section"
        seen = used.get(base, 0)
        used[base] = seen + 1
        return base if seen == 0 else f"{base}-{seen + 1}"

    while index < total:
        line = lines[index]
        stripped = line.strip()

        if stripped.startswith("```"):
            flush()
            lang = stripped[3:].strip()
            index += 1
            buf: list[str] = []
            while index < total and not lines[index].strip().startswith("```"):
                buf.append(lines[index])
                index += 1
            if index >= total:
                raise BuildError("unclosed code fence")
            index += 1
            klass = ""
            if re.fullmatch(r"[A-Za-z0-9_+.-]+", lang):
                klass = f' class="language-{esc(lang)}"'
            html_parts.append(f"<pre><code{klass}>{esc(chr(10).join(buf))}</code></pre>")
            continue

        if not stripped:
            flush()
            index += 1
            continue

        heading = re.match(r"^(#{1,3}) +(.+)$", stripped)
        if heading:
            flush()
            level = len(heading.group(1))
            text = heading.group(2).strip()
            hid = heading_id(text)
            if level == 2:
                outline.append((hid, text))
            html_parts.append(f'<h{level} id="{hid}">{inline(text)}</h{level}>')
            index += 1
            continue

        if re.fullmatch(r"([-*_])\1{2,}", stripped):
            flush()
            html_parts.append("<hr>")
            index += 1
            continue

        if stripped.startswith(">"):
            flush()
            chunks: list[str] = []
            while index < total and lines[index].strip().startswith(">"):
                content = lines[index].strip()[1:]
                if content.startswith(" "):
                    content = content[1:]
                chunks.append(content)
                index += 1
            html_parts.append("<blockquote>")
            quoted: list[str] = []

            def flush_quote() -> None:
                if quoted:
                    html_parts.append(f"<p>{inline(' '.join(quoted))}</p>")
                    quoted.clear()

            for chunk in chunks:
                if not chunk.strip():
                    flush_quote()
                else:
                    quoted.append(chunk.strip())
            flush_quote()
            html_parts.append("</blockquote>")
            continue

        if stripped.startswith("|"):
            flush()
            block: list[str] = []
            while index < total and lines[index].strip().startswith("|"):
                block.append(lines[index].strip())
                index += 1
            html_parts.append(render_table(block))
            continue

        if re.match(r"^[-*] ", stripped):
            flush()
            items: list[str] = []
            while index < total and re.match(r"^[-*] ", lines[index].strip()):
                items.append(re.sub(r"^[-*] +", "", lines[index].strip()))
                index += 1
                while (
                    index < total
                    and lines[index].startswith(("  ", "\t"))
                    and lines[index].strip()
                    and not re.match(r"^[-*] ", lines[index].strip())
                    and not re.match(r"^\d+\. ", lines[index].strip())
                ):
                    items[-1] += " " + lines[index].strip()
                    index += 1
            lis = "".join(f"<li>{inline(item)}</li>" for item in items)
            html_parts.append(f"<ul>{lis}</ul>")
            continue

        if re.match(r"^\d+\. ", stripped):
            flush()
            items = []
            while index < total and re.match(r"^\d+\. ", lines[index].strip()):
                items.append(re.sub(r"^\d+\. +", "", lines[index].strip()))
                index += 1
            lis = "".join(f"<li>{inline(item)}</li>" for item in items)
            html_parts.append(f"<ol>{lis}</ol>")
            continue

        para.append(stripped)
        index += 1

    flush()
    return "\n".join(html_parts), outline


def load_box(folder: Path) -> Box:
    path = folder / "writeup.md"
    if not path.is_file():
        raise BuildError(f"{rel(folder)}: no writeup.md")
    meta, body = parse_frontmatter(path.read_text(encoding="utf-8"), path)
    meta = validate(meta, folder)
    try:
        body_html, outline = render_markdown(body)
    except BuildError as exc:
        raise BuildError(f"{rel(path)}: {exc}") from exc
    return Box(
        name=meta["name"],
        slug=folder.name,
        os=meta["os"],
        difficulty=meta["difficulty"],
        techniques=list(meta["techniques"]),
        summary=meta["summary"].strip(),
        example=bool(meta.get("example", False)),
        released=meta.get("released"),
        retired_on=meta.get("retired_on"),
        updated=meta.get("updated"),
        body_html=body_html,
        outline=outline,
    )


def load_boxes() -> list[Box]:
    boxes_dir = ROOT / "boxes"
    if not boxes_dir.is_dir():
        raise BuildError("boxes/ is missing")
    folders = sorted(path for path in boxes_dir.iterdir() if path.is_dir())
    boxes = [load_box(folder) for folder in folders]
    boxes.sort(key=lambda box: (box.released or "9999-99-99", box.name.lower()))
    return boxes


def footer() -> str:
    return """<footer class="site-foot">
  <p>Retired boxes only. No live spoilers. MIT.</p>
  <details class="captains-log">
    <summary>Captain's log</summary>
    <p>Stardate <time id="stardate">----.---</time>. Nothing on this shelf is still live. End of log.</p>
  </details>
</footer>"""


def masthead(home: str, on_index: bool) -> str:
    if on_index:
        side = "Retired boxes only"
    else:
        side = f'<a href="{esc(home)}">Index</a> · retired only'
    return f"""<header class="mast">
  <p class="brand"><a href="{esc(home)}">logbook</a></p>
  <p class="brand-side">{side}</p>
</header>"""


def document(*, title: str, description: str, depth: int, body: str, on_index: bool = False) -> str:
    pre = "../" * depth
    home = f"{pre}index.html"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<meta name="theme-color" content="#e9e2d2">
<link rel="icon" href="{pre}favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="{pre}assets/style.css">
</head>
<body>
<a class="skip" href="#content">Skip to content</a>
<div class="wrap">
{masthead(home, on_index)}
<main id="content">
{body}
</main>
{footer()}
</div>
<script src="{pre}assets/site.js"></script>
</body>
</html>
"""


def tag_set(box: Box) -> list[str]:
    return [box.os.lower(), box.difficulty.lower(), *box.techniques]


def haystack(box: Box) -> str:
    parts = [box.name, box.os, box.difficulty, box.summary, " ".join(box.techniques)]
    if box.example:
        parts.append("example")
    return " ".join(parts).lower()


def meta_line(box: Box) -> str:
    bits = [
        f"<span>{esc(box.os)}</span>",
        f'<span class="diff diff-{esc(box.difficulty.lower())}">{esc(box.difficulty)}</span>',
    ]
    if box.released:
        bits.append(f"<span>Released {esc(display_date(box.released))}</span>")
    if box.retired_on:
        bits.append(f"<span>Retired {esc(display_date(box.retired_on))}</span>")
    return ' <span aria-hidden="true">·</span> '.join(bits)


def render_filters(boxes: list[Box]) -> str:
    systems: dict[str, str] = {}
    difficulties: dict[str, str] = {}
    techniques: dict[str, str] = {}
    for box in boxes:
        systems.setdefault(box.os.lower(), box.os)
        difficulties.setdefault(box.difficulty.lower(), box.difficulty)
        for technique in box.techniques:
            techniques.setdefault(technique, technique)

    def counts(key: str) -> int:
        return sum(1 for box in boxes if key in tag_set(box))

    def row(label: str, items: list[tuple[str, str]]) -> str:
        buttons = []
        for key, text in items:
            buttons.append(
                f'<button type="button" class="chip" data-filter="{esc(key)}" aria-pressed="false">'
                f"{esc(text)}<span class=\"n\">{counts(key)}</span></button>"
            )
        return (
            f'<div class="filter-row"><span class="filter-label">{esc(label)}</span>'
            + "".join(buttons)
            + "</div>"
        )

    diff_items = [(name.lower(), name) for name in DIFFICULTIES if name.lower() in difficulties]
    system_items = sorted(systems.items(), key=lambda item: item[1].lower())
    technique_items = sorted(techniques.items())
    return (
        '<div class="filter-block">'
        + row("System", system_items)
        + row("Difficulty", diff_items)
        + row("Technique", technique_items)
        + "</div>"
    )


def render_card(box: Box) -> str:
    kicker = '<p class="card-kicker">Example note</p>' if box.example else ""
    tags = []
    for technique in box.techniques:
        tags.append(
            f'<button type="button" class="chip" data-filter="{esc(technique)}" aria-pressed="false">{esc(technique)}</button>'
        )
    return f"""<li class="card" data-tags="{esc(",".join(tag_set(box)))}" data-hay="{esc(haystack(box))}">
  {kicker}
  <h2><a href="boxes/{esc(box.slug)}/">{esc(box.name)}</a></h2>
  <p class="meta">{meta_line(box)}</p>
  <p class="summary">{esc(box.summary)}</p>
  <div class="card-tags">{"".join(tags)}</div>
</li>"""


def render_index(boxes: list[Box]) -> str:
    if not boxes:
        body = """<div class="empty">
  <h1>The shelf is empty.</h1>
  <p>That is a valid state. It is also a bit bleak. Copy <code>templates/writeup.md</code> to <code>boxes/&lt;name&gt;/writeup.md</code>, keep <code>retired: true</code>, and run the generator.</p>
</div>"""
        return document(
            title="logbook",
            description="Methodology notes for retired Hack The Box machines.",
            depth=0,
            body=body,
            on_index=True,
        )

    noun = "box" if len(boxes) == 1 else "boxes"
    cards = "\n".join(render_card(box) for box in boxes)
    body = f"""<div class="intro">
  <h1>Notes on machines that are already retired.</h1>
  <p>Recon, foothold, privilege, lesson. Kept for CPTS study. Live boxes do not get a page.</p>
</div>
<form class="search" role="search" action="index.html">
  <label for="q">Search</label>
  <input id="q" name="q" type="search" placeholder="Name, system, technique" autocomplete="off">
</form>
<p class="hint" id="search-hint">Tags combine. Every selected one has to match. <kbd>/</kbd> focuses search.</p>
<noscript><p class="noscript">Tag search needs JavaScript. The write-ups themselves are ordinary pages.</p></noscript>
{render_filters(boxes)}
<p class="count" id="count" aria-live="polite">{len(boxes)} retired {noun}</p>
<ul class="cards">
{cards}
</ul>
<div id="empty" class="empty" hidden role="status">
  <p class="empty-title">Nothing under that heading.</p>
  <p>Either the tag is wrong, or you went looking for a live box. Those do not get a page.</p>
</div>"""
    return document(
        title="logbook",
        description="Methodology notes for retired Hack The Box machines.",
        depth=0,
        body=body,
        on_index=True,
    )


def render_box(box: Box, earlier: Box | None, later: Box | None) -> str:
    kicker = '<p class="eyebrow">Example methodology note</p>' if box.example else ""
    techs = "".join(
        f'<li><a href="../../index.html?tag={esc(technique)}">{esc(technique)}</a></li>'
        for technique in box.techniques
    )
    contents = ""
    if len(box.outline) >= 2:
        items = "".join(f'<li><a href="#{esc(hid)}">{esc(text)}</a></li>' for hid, text in box.outline)
        contents = f'<nav class="contents" aria-label="Contents"><ol>{items}</ol></nav>'
    links = ['<nav class="turn" aria-label="Adjacent boxes">']
    if earlier:
        links.append(f'<a href="../{esc(earlier.slug)}/">Earlier · {esc(earlier.name)}</a>')
    if later:
        links.append(f'<a class="later" href="../{esc(later.slug)}/">Later · {esc(later.name)}</a>')
    links.append("</nav>")
    turn = "".join(links) if earlier or later else ""
    body = f"""<article class="writeup">
  {kicker}
  <h1>{esc(box.name)}</h1>
  <p class="meta">{meta_line(box)}</p>
  <ul class="techs">{techs}</ul>
  <p class="lede">{esc(box.summary)}</p>
  {contents}
  {box.body_html}
  {turn}
</article>"""
    return document(
        title=f"{box.name} — logbook",
        description=box.summary,
        depth=2,
        body=body,
    )


def render_404() -> str:
    # GitHub Pages serves this file for unknown URLs but leaves the browser on
    # the missing path, so relative asset links would point at the wrong place.
    # The small script finds the site root. Python's own http.server will not
    # use this file; Pages will.
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Not in the log — logbook</title>
<meta name="description" content="This page is not a retired box.">
<meta name="theme-color" content="#e9e2d2">
<style>
  body { margin: 0; background: #e9e2d2; color: #1c1915; font-family: Georgia, "Noto Serif", serif; }
  a { color: #234037; }
</style>
<script>
(function () {
  var top = {assets:1, boxes:1, "index.html":1, "index.json":1, "404.html":1, "favicon.svg":1};
  var root = "/";
  if (location.protocol !== "file:" && location.hostname.endsWith("github.io")) {
    var seg = location.pathname.split("/").filter(Boolean)[0];
    if (seg && !top[seg]) root = "/" + seg + "/";
  }
  function add(rel, href) {
    var node = document.createElement("link");
    node.rel = rel;
    node.href = root + href;
    if (rel === "icon") node.type = "image/svg+xml";
    document.head.appendChild(node);
  }
  add("icon", "favicon.svg");
  add("stylesheet", "assets/style.css");
  document.addEventListener("DOMContentLoaded", function () {
    var home = document.getElementById("home");
    if (home) home.href = root;
    var script = document.createElement("script");
    script.src = root + "assets/site.js";
    document.body.appendChild(script);
  });
})();
</script>
</head>
<body>
<a class="skip" href="#content">Skip to content</a>
<div class="wrap">
<header class="mast">
  <p class="brand"><a id="home" href="/">logbook</a></p>
  <p class="brand-side">Retired boxes only</p>
</header>
<main id="content">
<div class="page-404">
  <h1>404</h1>
  <p class="lede">This page is not in the log.</p>
  <p>It may have been a typo. It may have been a live machine, in which case the omission is the point. The retired ones are on the index, which is still where it was.</p>
</div>
</main>
<footer class="site-foot">
  <p>Retired boxes only. No live spoilers. MIT.</p>
  <details class="captains-log">
    <summary>Captain's log</summary>
    <p>Stardate <time id="stardate">----.---</time>. We appear to be lost. The shelf, however, is not. End of log.</p>
  </details>
</footer>
</div>
</body>
</html>
"""


def index_payload(boxes: list[Box]) -> dict:
    return {
        "rule": "retired boxes only",
        "boxes": [
            {
                "name": box.name,
                "slug": box.slug,
                "os": box.os,
                "difficulty": box.difficulty,
                "released": box.released,
                "retired_on": box.retired_on,
                "updated": box.updated,
                "example": box.example,
                "techniques": box.techniques,
                "summary": box.summary,
                "href": f"boxes/{box.slug}/",
            }
            for box in boxes
        ],
    }


def resolve_out(raw: str) -> Path:
    out = (ROOT / raw).resolve()
    if out == ROOT or ROOT not in out.parents:
        raise BuildError(f"refusing to write to {out}")
    return out


def copy_assets(out: Path) -> None:
    target = out / "assets"
    target.mkdir(parents=True, exist_ok=True)
    for name in ("style.css", "site.js"):
        shutil.copyfile(ROOT / "assets" / name, target / name)
    shutil.copyfile(ROOT / "assets" / "favicon.svg", out / "favicon.svg")
    (out / ".nojekyll").write_text("", encoding="utf-8")


def write_site(boxes: list[Box], out: Path) -> None:
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    copy_assets(out)
    (out / "index.html").write_text(render_index(boxes), encoding="utf-8")
    (out / "404.html").write_text(render_404(), encoding="utf-8")
    (out / "index.json").write_text(
        json.dumps(index_payload(boxes), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    for position, box in enumerate(boxes):
        earlier = boxes[position - 1] if position else None
        later = boxes[position + 1] if position + 1 < len(boxes) else None
        page = out / "boxes" / box.slug / "index.html"
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(render_box(box, earlier, later), encoding="utf-8")


def self_test() -> None:
    html_out, outline = render_markdown(
        "## Hello\n\nA **bold** and *word* and `code`.\n\n"
        "- alpha\n- beta\n\n> quoted **bit**\n\n```\nnot **bold**\n```\n\n"
        "| H | I |\n| --- | --- |\n| a | [b](https://example.com) |\n"
    )
    assert '<h2 id="hello">' in html_out
    assert "<strong>bold</strong>" in html_out
    assert "<em>word</em>" in html_out
    assert "<code>code</code>" in html_out
    assert "<li>alpha</li>" in html_out
    assert "<blockquote>" in html_out
    assert "not **bold**" in html_out
    assert outline == [("hello", "Hello")]
    assert 'href="https://example.com"' in html_out
    assert safe_href("javascript:alert(1)") is False

    meta, body = parse_frontmatter(
        "---\nname: Lame\nretired: true\ntechniques:\n  - smb\nsummary: Hi\n---\n\n## Recon\n",
        Path("sample.md"),
    )
    assert meta["retired"] is True
    assert meta["techniques"] == ["smb"]
    assert body.startswith("## Recon")

    try:
        validate(
            {
                "name": "Nope",
                "os": "Linux",
                "difficulty": "Easy",
                "retired": False,
                "techniques": ["smb"],
                "summary": "No",
            },
            ROOT / "boxes" / "nope",
        )
    except BuildError as exc:
        if "live" not in str(exc):
            raise SystemExit(f"retired:false message went odd: {exc}") from exc
    else:
        raise SystemExit("retired: false was accepted")

    if stardate(date(2026, 11, 11)) != "2026.315":
        raise SystemExit(f"stardate drifted: {stardate(date(2026, 11, 11))}")
    print("self-test ok")


def report(boxes: list[Box], out: Path) -> None:
    noun = "box" if len(boxes) == 1 else "boxes"
    print(f"indexed {len(boxes)} retired {noun}")
    width = max((len(box.slug) for box in boxes), default=4)
    for box in boxes:
        print(f"  {box.slug:<{width}}  {box.os:<8} {box.difficulty:<8} {', '.join(box.techniques)}")
    print(f"wrote {out.relative_to(ROOT)}/")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="build.py",
        description="Build the logbook site from boxes/*/writeup.md.",
        epilog="Retired boxes only. If you have to ask, it is not retired.",
    )
    parser.add_argument(
        "--out",
        default="site",
        help="directory to write, relative to the repository (default: site)",
    )
    parser.add_argument("--self-test", action="store_true", help="check the parser and exit")
    parser.add_argument("--stardate", action="store_true", help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.stardate:
        print(f"Captain's log, stardate {stardate()}.")
        print("Compiling the index. Live boxes stay off the ship.")
        print()
    if args.self_test:
        self_test()
        return 0
    boxes = load_boxes()
    out = resolve_out(args.out)
    write_site(boxes, out)
    report(boxes, out)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BuildError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
