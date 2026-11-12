from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
GUIDES = DOCS / "guides"
PAGES_WORKFLOW = ROOT / ".github" / "workflows" / "pages.yml"

SITE_BASE = "https://mianbaofang.github.io/agent-skill-catalog"

# (slug, english title fragment, chinese title fragment)
GUIDE_PAIRS = [
    ("search-installed-skills", "Search the agent skills you already installed", "搜索你已经安装的 Agent Skills"),
    ("offline-skill-catalog", "Build an offline skill catalog", "生成完全离线的 Skill 目录"),
    ("skills-and-plugin-inventory", "Inventory skills and plugins across folders", "跨目录清点 Skill 与插件"),
]

OVERVIEW_URLS = {f"{SITE_BASE}/", f"{SITE_BASE}/index-zh.html"}
GUIDE_URLS = {f"{SITE_BASE}/guides/{slug}{suffix}.html" for slug, _, _ in GUIDE_PAIRS for suffix in ("", "-zh")}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_pages_files_and_metadata() -> None:
    required = ["index.html", "index-zh.html", "robots.txt", "sitemap.xml", "llms.txt", ".nojekyll"]
    for name in required:
        assert (DOCS / name).is_file(), name

    for name in ("index.html", "index-zh.html"):
        html = _read(DOCS / name)
        assert re.search(r'<link[^>]+rel="canonical"', html)
        assert re.search(r'<meta[^>]+name="description"', html)
        assert "og:title" in html and "og:description" in html and "og:image" in html
        assert "twitter:card" in html and "twitter:title" in html
        assert 'application/ld+json' in html
        assert 'noindex' not in html.lower()
        assert "C:\\Users\\" not in html and "E:\\Object\\" not in html

    robots = _read(DOCS / "robots.txt")
    assert "Allow: /" in robots
    assert "Sitemap: https://mianbaofang.github.io/agent-skill-catalog/sitemap.xml" in robots

    sitemap = _read(DOCS / "sitemap.xml")
    for url in OVERVIEW_URLS | GUIDE_URLS:
        assert f"<loc>{url}</loc>" in sitemap, url

    llms = _read(DOCS / "llms.txt")
    assert "Canonical pages" in llms
    assert "Boundaries" in llms


def test_pages_media_links_are_repository_local() -> None:
    for name in ("index.html", "index-zh.html"):
        html = _read(DOCS / name)
        for asset in re.findall(r'(?:src|href)="(media/[^"?#]+|assets/[^"?#]+)"', html):
            assert (DOCS / asset).is_file(), asset


def test_pages_chinese_copy_and_supported_workflow_actions() -> None:
    chinese_html = _read(DOCS / "index-zh.html")
    assert '<html lang="zh-CN">' in chinese_html
    assert "搜索你已经安装的 Agent Skills" in chinese_html
    assert "任务教程" in chinese_html

    workflow = PAGES_WORKFLOW.read_text(encoding="utf-8")
    assert "actions/checkout@v6" in workflow
    assert "actions/configure-pages@v5" in workflow
    assert "actions/upload-pages-artifact@v4" in workflow
    assert "actions/deploy-pages@v4" in workflow


def test_guide_pages_exist_with_distinct_metadata() -> None:
    for slug, en_title, zh_title in GUIDE_PAIRS:
        for suffix, lang, expected_title, other_suffix in (
            ("", "en", en_title, "-zh"),
            ("-zh", "zh-CN", zh_title, ""),
        ):
            path = GUIDES / f"{slug}{suffix}.html"
            assert path.is_file(), f"missing guide page: {path.name}"
            html = _read(path)

            # Distinct, language-appropriate title and description.
            assert f'<html lang="{lang}">' in html, path.name
            title_match = re.search(r"<title>(.*?)</title>", html, re.S)
            assert title_match and expected_title in title_match.group(1), path.name
            assert re.search(r'<meta[^>]+name="description"[^>]+content="[^"]{30,}"', html), path.name

            # Canonical points at this exact page.
            canonical = re.search(r'<link[^>]+rel="canonical"[^>]+href="([^"]+)"', html)
            assert canonical, path.name
            assert canonical.group(1) == f"{SITE_BASE}/guides/{slug}{suffix}.html", path.name

            # Full hreflang pair: en, zh-CN, x-default.
            for code, target in (
                ("en", f"{slug}.html"),
                ("zh-CN", f"{slug}-zh.html"),
                ("x-default", f"{slug}.html"),
            ):
                pattern = rf'<link[^>]+hreflang="{re.escape(code)}"[^>]+href="([^"]+)"'
                found = re.search(pattern, html)
                assert found, f"{path.name} missing hreflang {code}"
                assert found.group(1).endswith(f"/guides/{target}"), path.name


def test_guide_pages_crawlable_content_and_no_snippet_fakery() -> None:
    # Language-aware, task-specific evidence. A page must actually teach the task
    # with a step, a runnable command, a stated expected result, troubleshooting,
    # and a path onward -- not merely reach a word count.
    required_markers = {
        "": {
            "step": re.compile(r"Step 1"),
            "command": "build_catalog.py",
            "outcome": re.compile(r"Expected result"),
            "troubleshoot": re.compile(r"Troubleshooting"),
            "next": re.compile(r"Where to go next"),
        },
        "-zh": {
            "step": re.compile(r"第 1 步"),
            "command": "build_catalog.py",
            "outcome": re.compile(r"预期结果"),
            "troubleshoot": re.compile(r"排错"),
            "next": re.compile(r"接下来"),
        },
    }

    for slug, _, _ in GUIDE_PAIRS:
        for suffix in ("", "-zh"):
            html = _read(GUIDES / f"{slug}{suffix}.html")
            markers = required_markers[suffix]

            for name, marker in markers.items():
                if name == "command":
                    assert marker in html, f"{slug}{suffix}.html missing a runnable {marker} command"
                else:
                    assert marker.search(html), f"{slug}{suffix}.html missing {name} section"

            # A concrete root argument and an offline switch appear in the how-to.
            assert "--root" in html, f"{slug}{suffix}.html missing an explicit --root example"
            assert "--output-dir" in html, f"{slug}{suffix}.html missing an --output-dir example"

            # No invented rich-result markup.
            assert "aggregateRating" not in html, f"{slug}{suffix}.html has aggregateRating"
            assert '"@type": "FAQPage"' not in html and '"@type":"FAQPage"' not in html, f"{slug}{suffix}.html has FAQPage"

            # No local machine paths leaked.
            assert "C:\\Users\\" not in html and "E:\\Object\\" not in html, f"{slug}{suffix}.html leaks a local path"

            # Every internal link resolves to a real file; no skipping.
            for href in re.findall(r'href="(\.\./[^"#?]+|[\w.-]+\.html[^"#?]*)"', html):
                target = href.split("#")[0].split("?")[0]
                if not target:
                    continue
                resolved = (GUIDES / target).resolve()
                assert resolved.is_file(), f"{slug}{suffix}.html links to missing {href}"


def test_synthetic_demo_is_noindexed() -> None:
    # The demo is a synthetic, non-indexed product proof, not a long-tail landing page.
    demo = DOCS / "demo" / "index.html"
    assert demo.is_file(), "docs/demo/index.html must exist"
    html = _read(demo)
    assert "noindex" in html.lower(), "synthetic demo must be noindex"


def test_sitemap_urls_match_existing_indexable_pages() -> None:
    sitemap = _read(DOCS / "sitemap.xml")
    locs = set(re.findall(r"<loc>(.*?)</loc>", sitemap))
    expected = OVERVIEW_URLS | GUIDE_URLS
    assert locs == expected, f"sitemap mismatch: extra={locs - expected} missing={expected - locs}"

    llms = _read(DOCS / "llms.txt")
    for url in GUIDE_URLS:
        assert url in llms, f"llms.txt missing {url}"


def test_install_and_offline_contract_is_consistent() -> None:
    # The primary install path and the offline builder flags must agree across
    # the READMEs and the site so a reader cannot follow a contradictory command.
    pin_fragment = "--pin main --agent codex --scope user"
    offline_flags = ("--no-github-discovery", "--no-github-images")
    for readme in ("README.md", "README.zh-CN.md"):
        text = _read(ROOT / readme)
        assert pin_fragment in text, f"{readme} missing the main install command"
        for flag in offline_flags:
            assert flag in text, f"{readme} missing offline flag {flag}"
        assert "--no-github-readmes" in text, f"{readme} missing the queue offline flag"

    for name in ("index.html", "index-zh.html"):
        html = _read(DOCS / name)
        assert pin_fragment in html, f"{name} missing the main install command"
        for flag in offline_flags:
            assert flag in html, f"{name} missing offline flag {flag}"
