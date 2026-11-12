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
        # targeted UX follow-up: cover/title open-details, gallery zoom, copy, larger view
        "copy-invocation", "copy-status", "lightbox", "lightbox-close",
        "lightbox-img", "lightbox-name", "lightbox-label", "lightbox-source",
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


def test_cover_and_title_are_native_open_details_buttons(html: str) -> None:
    # cover is a native button carrying the record id and an explicit accessible name
    assert 'class="thumb-button" type="button" data-record=' in html
    assert 'aria-label="查看 ' in html and '详情"' in html
    # the title keeps heading semantics while a native button inside opens the detail dialog
    assert "<h3><button class=\"card-title\" type=\"button\" data-record=" in html
    # one delegated handler drives cover / title / detail buttons after re-render
    assert "querySelectorAll('[data-record]').forEach(button=>button.addEventListener" not in html
    assert "closest('[data-record],[data-image-record]')" in html


def test_cover_no_longer_hijacks_click_to_github(html: str) -> None:
    # the inert cover div and the outbound cover anchor are gone
    assert 'class="thumb-link"' not in html
    # GitHub stays on the explicit detail dialog link
    assert 'id="detail-github"' in html


def test_cover_badge_is_not_a_nested_interactive_element(html: str) -> None:
    # provenance badge is aria-hidden and pointer-events:none so it never swallows the click
    assert 'class="image-badge" aria-hidden="true"' in html
    assert ".image-badge {" in html and "pointer-events: none;" in html


def test_gallery_images_are_zoom_buttons_with_source_explanation(html: str) -> None:
    assert 'class="zoom-button" type="button" data-zoom=' in html
    assert "放大查看" in html
    # each caption explains provenance, and the generated fallback is called out as art, not a screenshot
    assert "不代表技能的实际界面截图" in html
    assert "不是图片生成操作的结果" in html
    assert 'class="gallery-note"' in html


def test_larger_view_uses_native_dialog_with_focus_return(html: str) -> None:
    assert '<dialog id="lightbox" aria-labelledby="lightbox-name">' in html
    assert "$('#lightbox').showModal()" in html
    assert "$('#lightbox').close()" in html
    # focus returns to the gallery button that opened it
    assert "lightboxReturn=trigger" in html
    assert "lightboxReturn.focus({preventScroll:true})" in html


def test_copy_invocation_has_clipboard_fallback_and_status(html: str) -> None:
    assert 'id="copy-invocation"' in html
    assert 'id="copy-status"' in html
    assert "navigator.clipboard" in html
    assert "execCommand('copy')" in html
    assert "已复制调用方式。" in html
    assert "复制失败" in html


def test_cover_thumb_button_uses_uniform_landscape_frame(html: str) -> None:
    # Landscape frames stay uniform even when original media is portrait.
    # Containment preserves the full original rather than stretching or cropping it.
    assert ".thumb-button {" in html
    assert "aspect-ratio: 16 / 9" in html
    # the button is the clipping box and the image absolutely fills it, contained
    assert "overflow: hidden;" in html
    assert ".thumb-button img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: contain;" in html
    # the dead .thumb rules that used to own this box are gone (no duplicate sizing)
    assert ".thumb {" not in html
    assert ".thumb img" not in html


def test_copy_fallback_runs_on_clipboard_rejection_not_just_absence(html: str) -> None:
    # clipboard write is awaited inside try; a rejection must fall through to the
    # textarea fallback rather than only using it when the API is entirely missing.
    assert "await navigator.clipboard.writeText(text);copied=true" in html
    assert "catch(error){copied=false}" in html
    assert "if(!copied)copied=copyViaTextarea(text)" in html


def test_copy_fallback_textarea_lives_inside_the_active_detail_dialog(html: str) -> None:
    # content outside an open <dialog> is inert and cannot be selected, so the helper
    # textarea must be appended to #detail and require it to be open.
    assert "function copyViaTextarea(text){const dialog=$('#detail');if(!dialog||!dialog.open)return false;" in html
    assert "dialog.appendChild(area)" in html
    assert "document.body.appendChild(area)" not in html


def test_copy_fallback_preserves_focus_and_cleans_up(html: str) -> None:
    # focus returns to the trigger on a real copy, and the helper textarea is removed
    assert "previous.focus({preventScroll:true})" in html
    assert "area.remove()" in html
    # reopening a record clears any leftover fallback textarea and resets the status
    assert "cleanupCopyFallback()" in html


def test_copy_reports_manual_select_instead_of_false_success(html: str) -> None:
    # when both programmatic paths fail, the text is revealed/selected for a manual copy
    # and the status explicitly says it failed rather than claiming success.
    assert "area.classList.add('copy-fallback-manual')" in html
    assert "复制失败，已选中调用方式文本，请按 Ctrl+C 手动复制。" in html
    # the manual reveal has a visible, selectable box
    assert ".copy-fallback-manual {" in html


def test_gallery_caption_github_link_is_not_a_tall_image_block(html: str) -> None:
    # The `.gallery a` image-wrapper rule (200px grid block) must not swallow the
    # figcaption "打开来源仓库" link, which would render a huge empty block under it.
    assert ".gallery figcaption .github { display: inline; min-height: 0;" in html


def test_open_details_controls_have_visible_hover_and_focus_feedback(html: str) -> None:
    # cover ring + hint on hover/focus, title underline, orange focus-visible ring
    assert ".thumb-button:hover::after, .thumb-button:focus-visible::after" in html
    assert ".thumb-button:hover .image-hint, .thumb-button:focus-visible .image-hint" in html
    assert ".card-title:hover" in html
    assert ":focus-visible { outline: 3px solid var(--orange);" in html
    # lightbox scrolls on small screens and the close control reaches 44px on phones
    assert "#lightbox { width:" in html and "overflow-y: auto;" in html
    assert ".lightbox-close { width: 44px; height: 44px; }" in html
