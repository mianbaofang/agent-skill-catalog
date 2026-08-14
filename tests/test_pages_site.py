from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
PAGES_WORKFLOW = ROOT / ".github" / "workflows" / "pages.yml"


def test_pages_files_and_metadata() -> None:
    required = ["index.html", "index-zh.html", "robots.txt", "sitemap.xml", "llms.txt", ".nojekyll"]
    for name in required:
        assert (DOCS / name).is_file(), name

    for name in ("index.html", "index-zh.html"):
        html = (DOCS / name).read_text(encoding="utf-8")
        assert re.search(r'<link[^>]+rel="canonical"', html)
        assert re.search(r'<meta[^>]+name="description"', html)
        assert "og:title" in html and "og:description" in html and "og:image" in html
        assert "twitter:card" in html and "twitter:title" in html
        assert 'application/ld+json' in html
        assert 'noindex' not in html.lower()
        assert "C:\\Users\\" not in html and "E:\\Object\\" not in html

    robots = (DOCS / "robots.txt").read_text(encoding="utf-8")
    assert "Allow: /" in robots
    assert "Sitemap: https://mianbaofang.github.io/agent-skill-catalog/sitemap.xml" in robots

    sitemap = (DOCS / "sitemap.xml").read_text(encoding="utf-8")
    assert "https://mianbaofang.github.io/agent-skill-catalog/" in sitemap
    assert "index-zh.html" in sitemap

    llms = (DOCS / "llms.txt").read_text(encoding="utf-8")
    assert "Canonical pages" in llms
    assert "Boundaries" in llms


def test_pages_media_links_are_repository_local() -> None:
    for name in ("index.html", "index-zh.html"):
        html = (DOCS / name).read_text(encoding="utf-8")
        for asset in re.findall(r'(?:src|href)="(media/[^"?#]+|assets/[^"?#]+)"', html):
            assert (DOCS / asset).is_file(), asset


def test_pages_chinese_copy_and_supported_workflow_actions() -> None:
    chinese_html = (DOCS / "index-zh.html").read_text(encoding="utf-8")
    assert '<html lang="zh-CN">' in chinese_html
    assert "本地 AI Agent Skill 与 Codex 插件管理器" in chinese_html
    assert "为什么需要它" in chinese_html

    workflow = PAGES_WORKFLOW.read_text(encoding="utf-8")
    assert "actions/checkout@v6" in workflow
    assert "actions/configure-pages@v5" in workflow
    assert "actions/upload-pages-artifact@v4" in workflow
    assert "actions/deploy-pages@v4" in workflow


if __name__ == "__main__":
    test_pages_files_and_metadata()
    test_pages_media_links_are_repository_local()
    test_pages_chinese_copy_and_supported_workflow_actions()
