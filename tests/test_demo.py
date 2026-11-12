"""Tests for the reproducible public demo (tools/build_demo.py + examples/demo-library)."""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "examples" / "demo-library"
DEMO = REPO_ROOT / "docs" / "demo"
BUILD_DEMO = REPO_ROOT / "tools" / "build_demo.py"


def load_build_demo():
    spec = importlib.util.spec_from_file_location("build_demo_under_test", BUILD_DEMO)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def public_json(module, catalog: dict) -> str:
    return module.public_json(catalog)


@pytest.fixture(scope="module")
def builder():
    return load_build_demo()


@pytest.fixture(scope="module")
def built(builder):
    return builder.build_normalized(builder.load_builder())


def test_committed_fixtures_use_non_installable_templates() -> None:
    templates = sorted(FIXTURES.rglob("SKILL.md.example"))
    # 8 synthetic templates + 1 real public reference (agent-skill-catalog).
    assert len(templates) == 9
    # No real SKILL.md may be committed under examples/, or it pollutes discovery.
    assert list(FIXTURES.rglob("SKILL.md")) == []


def test_fixture_boundaries_present() -> None:
    for template in FIXTURES.rglob("SKILL.md.example"):
        text = template.read_text(encoding="utf-8")
        assert "合成" in text or "参考" in text, template
        assert "不会" in text or "不包含" in text or "不含" in text or "不是" in text, template


def test_expected_counts(built) -> None:
    summary = built["summary"]
    # 9 template records; two same-named weather-lookup copies are retained.
    assert summary["skill_count"] == 7
    assert summary["plugin_skill_count"] == 2
    assert summary["plugin_count"] == 1
    assert summary["family_count"] == 5
    assert summary["pending_description_count"] == 0
    assert summary["category_count"] == 13


def test_true_parent_child_family(built) -> None:
    families = {family["name"]: family for family in built["families"]}
    family = families["note-keeper"]
    assert len(family["skill_ids"]) == 3
    members = {item["name"] for item in built["items"] if item["id"] in family["skill_ids"]}
    assert members == {"note-keeper", "note-keeper-web", "note-keeper-cli"}
    primary = next(item for item in built["items"] if item["id"] == family["primary_id"])
    assert primary["name"] == "note-keeper"


def test_plugin_is_separate_from_families(built) -> None:
    plugin = built["plugins"][0]
    assert plugin["name"] == "toolkit"
    assert len(plugin["skill_ids"]) == 2
    member_names = {item["name"] for item in built["items"] if item["id"] in plugin["skill_ids"]}
    assert member_names == {"refresh-cache", "review-draft"}
    assert all(item["kind"] == "plugin" for item in built["items"] if item.get("plugin_id"))
    # Plugin members are not folded into any family.
    family_member_ids = {sid for family in built["families"] for sid in family["skill_ids"]}
    assert not (set(plugin["skill_ids"]) & family_member_ids)


def test_same_name_across_roots_is_retained_without_repo_evidence(built) -> None:
    copies = [item for item in built["items"] if item["name"] == "weather-lookup"]
    assert len(copies) == 2
    assert {item["source"] for item in copies} == {"社区技能示例", "个人技能示例"}
    # No fabricated repository evidence: nothing is merged or presented as verified.
    assert all(not item.get("deduplication") for item in copies)
    assert all(not item.get("github", {}).get("url") for item in copies)


def test_family_references_are_consistent(built) -> None:
    family_ids = {family["id"] for family in built["families"]}
    for item in built["items"]:
        family_id = item.get("family_id")
        if family_id is not None:
            assert family_id in family_ids, item["name"]
    for family in built["families"]:
        for member_id in family["skill_ids"]:
            assert member_id in {item["id"] for item in built["items"]}


def test_output_is_deterministic_and_portable(builder, built) -> None:
    first = public_json(builder, built)
    # Relocated temp root (a different temp dir each run) must yield identical bytes.
    rebuilt = builder.build_normalized(builder.load_builder())
    assert first == public_json(builder, rebuilt)
    # HTML re-rendered from the clean public catalog matches the shipped page.
    public = {key: value for key, value in built.items() if not key.startswith("__")}
    assert builder.inject_banner(builder.load_builder().render_html(public), public) == built["__html__"]


def test_no_machine_specific_paths_in_output(built) -> None:
    text = public_json(load_build_demo(), built)
    assert "E:\\" not in text and "/tmp/" not in text
    assert re.search(r"[A-Za-z]:\\\\", text) is None
    assert str(Path(tempfile_root())) not in text
    for root in built["roots"]:
        assert root["path"].startswith("<demo-root>")


def test_demo_labels_and_noindex(built) -> None:
    html = built["__html__"]
    assert "noindex" in html
    assert "Demo data" in html and "演示数据" in html


def test_guide_actions_are_compact_collapsible_and_accessible(built) -> None:
    html = built["__html__"]
    # Collapsed by default, toggle exposed with accessible state.
    assert 'id="demo-guide-toggle"' in html
    assert 'aria-expanded="false"' in html and 'aria-controls="demo-guide-panel"' in html
    assert 'id="demo-guide-panel" hidden' in html
    # Touch targets meet the 44px minimum.
    assert "min-height:44px" in html
    # Guide precedes the product UI and its wiring runs before </body>.
    assert html.find("demo-banner") < html.find('class="topbar"')
    assert html.find("demo-guide-panel") < html.rfind("</body>")


def test_guide_buttons_derive_from_real_fixture_data(built) -> None:
    html = built["__html__"]
    families = {family["name"]: family for family in built["families"]}
    family = families["note-keeper"]
    plugin = built["plugins"][0]
    members = len(family["skill_ids"])
    # Labels quote the real family/plugin names and the real member count (no fabrication).
    assert f"试试搜索 {family['name']}" in html
    assert f"看家族详情（{family['name']}，{members} 个技能）" in html
    assert f"看插件（{plugin['name']}）" in html
    assert f"重置演示" in html
    # The wiring targets the real record id so the native detail dialog opens.
    assert json.dumps(family["id"]) in html


def test_guide_actions_use_native_controls_only(built) -> None:
    html = built["__html__"]
    # Search fills the real input and dispatches the native input event.
    assert "getElementById('search')" in html and "new Event('input'" in html
    # Family detail / plugin / reset go through the page's own controls, no state copy.
    assert "data-record=" in html
    assert "data-mode=" in html and "data-category=" in html
    assert "closest('[data-demo]')" in html
    # The injected guide is the last script; it adds no network calls of its own.
    demo_script = html.rsplit("<script>", 1)[1]
    assert "demo-guide-panel" in demo_script
    assert "fetch(" not in demo_script


def test_guide_script_values_are_proper_js_literals(built) -> None:
    """Regression guard: injected names/ids must be quoted JS literals.

    A bare ``note-keeper`` parses as ``note - keeper`` (ReferenceError), and a
    ``clickRecord('"family:..."')`` wraps the id in extra quotes so no record
    matches. Both broke the guide in real browser runs.
    """
    html = built["__html__"]
    family = next(f for f in built["families"] if f["name"] == "note-keeper")
    demo_script = html.rsplit("<script>", 1)[1]
    # The search/detail fallback assigns a quoted string literal, not a bare token.
    assert f'input.value="{family["name"]}"' in demo_script
    assert f'input.value={family["name"]}' not in demo_script
    # clickRecord receives exactly the JSON string literal (no doubled quoting).
    assert f"clickRecord({json.dumps(family['id'])})" in demo_script
    assert 'clickRecord(\'"' not in demo_script


def test_generated_demo_files_exist_and_match(builder) -> None:
    # The demo is a committed build artifact; a missing demo is a failure, not a skip.
    assert DEMO.is_dir(), "docs/demo is missing; run `python tools/build_demo.py`"
    catalog = builder.build_normalized(builder.load_builder())
    assert (DEMO / "catalog.json").read_text(encoding="utf-8") == public_json(builder, catalog)
    assert (DEMO / "index.html").read_text(encoding="utf-8") == catalog["__html__"]


def test_check_detects_tampering(builder, tmp_path) -> None:
    assert (DEMO / "catalog.json").is_file(), "docs/demo is missing; run `python tools/build_demo.py`"
    module = load_build_demo()
    import shutil

    copied = tmp_path / "demo"
    shutil.copytree(DEMO, copied)
    # Pristine copy passes.
    assert module.check_output(copied) == 0
    # Any content drift is detected.
    catalog = copied / "catalog.json"
    catalog.write_text(catalog.read_text(encoding="utf-8") + "\n<!-- drift -->", encoding="utf-8")
    assert module.check_output(copied) == 1
    # A missing generated file is detected.
    (copied / "index.html").unlink()
    assert module.check_output(copied) == 1


def tempfile_root() -> str:
    import tempfile

    return tempfile.gettempdir()


# --- Real animated reference (agent-skill-catalog) ---------------------------

REAL_REFERENCE_MANIFEST = FIXTURES / "media" / "agent-skill-catalog-preview.manifest.json"
REAL_REFERENCE_CLIP = (
    FIXTURES / "roots" / "community-skills" / "agent-skill-catalog" / "preview.gif"
)


def _real_reference(built) -> dict:
    matches = [item for item in built["items"] if item["name"] == "agent-skill-catalog"]
    assert len(matches) == 1, "the real public reference record must appear exactly once"
    return matches[0]


def test_real_reference_carries_animated_preview(built) -> None:
    """The key selling point: one record shows a real moving preview, offline."""
    item = _real_reference(built)
    image = item["image"]
    # verified-local is the honest offline-replayable status (not github-repository).
    assert image["status"] == "verified-local"
    assert image["missing_evidence"] is False
    value = image["value"]
    assert value.startswith("data:image/gif;base64,"), "preview must be an embedded animated GIF"
    import base64

    raw = base64.b64decode(value.split(",", 1)[1])
    # GIF signature + a real multi-frame animation (not a static single-frame image).
    assert raw[:4] == b"GIF8"
    from PIL import Image
    import io

    gif = Image.open(io.BytesIO(raw))
    assert gif.n_frames >= 2, "preview must actually animate (multiple frames)"
    assert gif.size == (400, 225)


def test_real_reference_preview_bytes_match_captured_snapshot() -> None:
    """The embedded preview is the committed byte snapshot, not regenerated art."""
    import base64

    module = load_build_demo()
    catalog = module.build_normalized(module.load_builder())
    item = _real_reference(catalog)
    raw = base64.b64decode(item["image"]["value"].split(",", 1)[1])
    assert raw == REAL_REFERENCE_CLIP.read_bytes(), (
        "the embedded preview must be byte-identical to the committed captured clip"
    )
    manifest = json.loads(REAL_REFERENCE_MANIFEST.read_text(encoding="utf-8"))
    import hashlib

    assert hashlib.sha256(REAL_REFERENCE_CLIP.read_bytes()).hexdigest() == manifest["derived_sha256"]


def test_real_reference_provenance_is_honest() -> None:
    """Provenance must disclose documentation-derived origin, never auto-fetch."""
    manifest = json.loads(REAL_REFERENCE_MANIFEST.read_text(encoding="utf-8"))
    assert manifest["kind"] == "documentation-derived"
    assert manifest["not_auto_fetch"] is True
    assert manifest["catalog_image_status"] == "verified-local"
    assert manifest["source_repository"] == "https://github.com/mianbaofang/agent-skill-catalog"
    assert "github-repository" != manifest["catalog_image_status"]
    # The fixture text carries the same honest boundary.
    fixture = (
        FIXTURES / "roots" / "community-skills" / "agent-skill-catalog" / "SKILL.md.example"
    ).read_text(encoding="utf-8")
    assert "documentation-derived" in fixture or "文档派生" in fixture
    assert "github.com/mianbaofang/agent-skill-catalog" in fixture


def test_real_reference_is_distinct_from_synthetic_records(built) -> None:
    """The real reference is labelled; synthetic records stay generated-fallback."""
    item = _real_reference(built)
    assert item["image"]["status"] == "verified-local"
    synthetic = [i for i in built["items"] if i["name"] != "agent-skill-catalog"]
    assert synthetic, "synthetic examples must remain"
    assert all(i["image"]["status"] == "generated-fallback" for i in synthetic)
    # The synthetic fixtures still carry their visible fictional boundary note.
    for template in FIXTURES.rglob("SKILL.md.example"):
        if template.parent.name == "agent-skill-catalog":
            continue
        assert "合成" in template.read_text(encoding="utf-8")
