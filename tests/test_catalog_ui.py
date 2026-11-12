"""Render checks for the generated catalog UI.

These exercise the real ``render_catalog_html`` output (no browser needed) and
assert the structural contracts the task requires: a responsive, self-contained,
search-led page whose live write actions stay disabled unless a genuine local
catalog service is detected.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "agent-skill-catalog" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from catalog_page import render_catalog_html  # noqa: E402


def _catalog() -> dict:
    return {
        "generated_at": "2026-11-12T00:00:00Z",
        "categories": {"data": {"label": "数据与研究"}, "other": {"label": "其他"}},
        "items": [
            {
                "id": "skill:1",
                "name": "sample-skill",
                "description": "A sample skill description.",
                "invocation": "调用方式",
                "relative_path": "root/sample-skill/SKILL.md",
                "category": "data",
                "confidence": 0.9,
                "category_tie_reason": "manifest",
                "allow_delete": True,
                "family_size": 1,
                "image": {"status": "github-repository", "source": "github", "value": "data:image/png;base64,AAA"},
            }
        ],
        "families": [
            {
                "id": "family:1",
                "name": "sample-skill",
                "description": "A sample skill description.",
                "invocation": "调用方式",
                "category": "data",
                "confidence": 0.9,
                "category_tie_reason": "manifest",
                "primary_id": "skill:1",
                "skill_ids": ["skill:1"],
                "locations": ["Root 1:sample-skill/SKILL.md"],
                "image": {"status": "github-repository", "source": "github", "value": "data:image/png;base64,AAA"},
            }
        ],
        "plugins": [],
    }


@pytest.fixture()
def html() -> str:
    return render_catalog_html(_catalog())


def test_renders_self_contained_document(html: str) -> None:
    assert html.lstrip().startswith("<!doctype html>")
    assert '<html lang="zh-CN">' in html
    assert 'name="viewport" content="width=device-width,initial-scale=1"' in html
    # self-contained: no external stylesheet, script or remote font/icon reference
    assert "rel=\"stylesheet\"" not in html
    assert "fonts.googleapis" not in html
    assert 'rel="icon" href="data:image/svg+xml' in html


def test_no_forced_desktop_min_width(html: str) -> None:
    # the previous baseline forced body min-width 1180px and overflowed every phone width
    assert "min-width: 1180px" not in html
    assert "min-width:1180px" not in html
    assert "repeat(auto-fill, minmax(min(100%, 292px), 1fr))" in html


def test_key_data_contract_ids_present(html: str) -> None:
    for element_id in (
        "status", "refresh", "total", "stat-label", "search", "overview",
        "result-title", "count", "list", "detail", "close", "detail-media",
        "detail-gallery", "image-editor", "image-file", "image-save", "image-remove",
        "image-editor-status", "detail-content", "detail-tag", "detail-name",
        "detail-description", "github-panel", "detail-github", "subskills-label",
        "detail-subskills", "detail-locations", "detail-evidence", "danger-zone",
        "delete-open", "delete-confirm",
    ):
        assert f'id="{element_id}"' in html, element_id


def test_data_fields_wired_into_script(html: str) -> None:
    for field in (
        "generated_at", "categories", "items", "families", "plugins",
        "skill_ids", "primary_id", "allow_delete", "family_size", "confidence",
        "relative_path", "invocation",
    ):
        assert field in html, field


def test_embedded_catalog_payload_is_injected(html: str) -> None:
    # the real catalog data replaces the placeholder, and item names appear in the payload
    assert "__CATALOG__" not in html
    assert "sample-skill" in html
    assert "Root 1:sample-skill/SKILL.md" in html


def test_write_actions_default_to_disabled_static_context(html: str) -> None:
    # SERVER_MODE starts false and is only enabled by a bounded local health probe
    assert "let SERVER_MODE=false" in html
    assert "const LOCAL_ORIGIN=" in html
    assert "function applyStaticMode()" in html
    assert "async function probeServerMode()" in html
    # probe runs only on a loopback http origin, and requires a JSON ok+catalog health body
    assert "location.protocol==='http:'" in html
    assert "payload.ok===true&&payload.catalog===true" in html
    # the refresh button ships disabled with an explanation and the editor hidden
    assert 'id="refresh"' in html and "disabled" in html
    assert "静态目录" in html


def test_delete_capability_gated_behind_server_mode(html: str) -> None:
    # canDelete must refuse when not running against the local service
    assert "function canDelete(record){if(!SERVER_MODE)return false;" in html
    # the delete confirmation still requires the exact skill name
    assert "confirmation!==item.name" in html


def test_responsive_and_reduced_motion_rules(html: str) -> None:
    # detail stacks to a single full-height column on small screens
    assert "@media (max-width: 820px)" in html
    assert "100dvh" in html
    # phone touch targets reach the 44px minimum
    assert "@media (max-width: 600px)" in html
    assert ".button { min-height: 44px; }" in html
    assert ".category-chip { min-height: 44px; }" in html
    # paths and long names wrap instead of clipping
    assert "overflow-wrap: anywhere" in html
    assert "white-space: pre-wrap" in html
    # motion respects the OS reduced-motion preference
    assert "prefers-reduced-motion: reduce" in html


def test_provenance_labels_preserved(html: str) -> None:
    # image provenance is surfaced on cards, in the gallery and in the evidence panel
    assert "imageLabel" in html
    assert "自动生成封面" in html
    assert "GitHub 项目图片" in html
    assert "图片来源" in html


def test_visible_search_label_not_placeholder_only(html: str) -> None:
    assert 'class="search-label" for="search"' in html
    assert "搜索技能与插件" in html


def test_render_is_deterministic() -> None:
    assert render_catalog_html(_catalog()) == render_catalog_html(_catalog())


def test_minimal_catalog_renders_without_optional_fields() -> None:
    minimal = {"generated_at": None, "categories": {}, "items": [], "families": [], "plugins": []}
    html = render_catalog_html(minimal)
    assert 'id="list"' in html
    assert 'id="overview"' in html
