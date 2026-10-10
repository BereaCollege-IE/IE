#!/usr/bin/env python3
"""Build step for the IE&A website. Run from the site folder:  python3 tools/build.py

What it does, in order:
  1. Stamps the shared header and footer (partials/) into every page, between the
     <!-- BEGIN:header --> / <!-- END:header --> and <!-- BEGIN:footer --> / <!-- END:footer --> markers.
     Edit the partials, never the stamped copies; the next build overwrites them.
  2. Marks the current section in the main menu (from each page's <meta name="section">).
  3. Fills the "Page last reviewed" date from each page's <meta name="last-reviewed" content="YYYY-MM-DD">.
  4. Rebuilds search-index.json, which the search page reads.
  5. Checks every page for em dashes and for links to files that don't exist.

Uses only the Python standard library.
"""
import html
import json
import re
import sys
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent
CONFIG = json.loads((SITE / "tools" / "site_config.json").read_text(encoding="utf-8"))
SKIP_DIRS = {"partials", "tools", "files", "assets", ".git"}

NAV = [
    ("assessment", "Assessment", "assessment/"),
    ("accreditation", "Accreditation", "accreditation/"),
    ("ai", "AI", "ai/"),
    ("data", "Data &amp; Reports", "data/"),
]

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]


def pages():
    for p in sorted(SITE.rglob("*.html")):
        rel = p.relative_to(SITE)
        if rel.parts[0] in SKIP_DIRS:
            continue
        yield p, rel


def meta(text, name):
    m = re.search(r'<meta\s+name="%s"\s+content="([^"]*)"' % re.escape(name), text)
    return m.group(1) if m else ""


def pretty_date(iso):
    try:
        d = date.fromisoformat(iso)
    except ValueError:
        return "[date not set]"
    return f"{MONTHS[d.month - 1]} {d.day}, {d.year}"


def stamp(text, block, content):
    pattern = re.compile(r"(<!-- BEGIN:%s -->)(.*?)(<!-- END:%s -->)" % (block, block), re.S)
    if not pattern.search(text):
        raise SystemExit(f"Missing {block} markers")
    return pattern.sub(lambda m: m.group(1) + "\n" + content + m.group(3), text, count=1)


class TextGrab(HTMLParser):
    """Collects visible text inside <main>, plus resource rows marked data-resource."""

    def __init__(self):
        super().__init__()
        self.in_main = 0
        self.skip = 0
        self.chunks = []
        self.resources = []
        self._res = None
        self._res_depth = 0
        self._cap = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "main":
            self.in_main += 1
        if tag in ("script", "style", "svg"):
            self.skip += 1
        if self._res is not None:
            self._res_depth += 1
            if tag == "h3":
                self._cap = "title"
            elif tag == "p":
                self._cap = "desc"
            elif tag == "a" and "href" in a:
                self._res["href"] = a["href"]
        elif tag == "li" and "data-resource" in a:
            self._res = {"title": "", "desc": "", "href": "", "section": a.get("data-resource", "")}
            self._res_depth = 1

    def handle_endtag(self, tag):
        if tag == "main":
            self.in_main -= 1
        if tag in ("script", "style", "svg") and self.skip:
            self.skip -= 1
        if self._res is not None:
            if tag in ("h3", "p"):
                self._cap = None
            self._res_depth -= 1
            if self._res_depth == 0:
                self.resources.append(self._res)
                self._res = None

    def handle_data(self, data):
        if self.in_main and not self.skip:
            self.chunks.append(data)
            if self._res is not None and self._cap:
                self._res[self._cap] += data


def clean(s):
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def main():
    header_t = (SITE / "partials" / "header.html").read_text(encoding="utf-8")
    footer_t = (SITE / "partials" / "footer.html").read_text(encoding="utf-8")
    index, problems = [], []

    for path, rel in pages():
        text = path.read_text(encoding="utf-8")
        depth = len(rel.parts) - 1
        root = "../" * depth if depth else "./"
        section = meta(text, "section")

        nav_items = []
        for key, label, href in NAV:
            cur = ' aria-current="page"' if key == section else ""
            nav_items.append(f'        <li><a href="{root}{href}"{cur}>{label}</a></li>')
        header = header_t.replace("{{root}}", root).replace("{{nav}}", "\n".join(nav_items))
        footer = (footer_t.replace("{{root}}", root)
                  .replace("{{reviewed}}", pretty_date(meta(text, "last-reviewed")))
                  .replace("{{contact}}", CONFIG["contact"])
                  .replace("{{aa_home}}", CONFIG["aa_home"]))

        text = stamp(text, "header", header)
        text = stamp(text, "footer", footer)
        path.write_text(text, encoding="utf-8")

        # Checks
        for n, line in enumerate(text.splitlines(), 1):
            if "\u2014" in line:
                problems.append(f"{rel}:{n}: em dash")
        for href in re.findall(r'(?:href|src)="([^"#?:]+)"', text):
            if href.startswith(("http", "mailto", "//")):
                continue
            target = (path.parent / href).resolve()
            if href.endswith("/"):
                target = target / "index.html"
            if not target.exists():
                problems.append(f"{rel}: broken link {href}")

        # Search index
        g = TextGrab()
        g.feed(text)
        title = clean(re.search(r"<title>(.*?)</title>", text, re.S).group(1))
        url = "" if str(rel) == "index.html" else str(rel.parent).replace("\\", "/") + "/"
        index.append({"kind": "page", "title": title.split(" | ")[0], "url": url,
                      "section": section, "text": clean(" ".join(g.chunks))[:4000]})
        for r in g.resources:
            href = r["href"]
            full = (Path(url) / href).as_posix() if url else href
            index.append({"kind": "file", "title": clean(r["title"]), "url": full,
                          "section": section, "group": r["section"], "text": clean(r["desc"])})

    (SITE / "search-index.json").write_text(json.dumps(index, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"Built {sum(1 for _ in pages())} pages; search index has {len(index)} entries.")
    if problems:
        print("PROBLEMS:")
        for p in problems:
            print("  " + p)
        sys.exit(1)
    print("No problems found.")


if __name__ == "__main__":
    main()
