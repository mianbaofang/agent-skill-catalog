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
    assert len(templates) == 8
    # No real SKILL.md may be committed under examples/, or it pollutes discovery.
    assert list(FIXTURES.rglob("SKILL.md")) == []


def test_fixture_boundaries_present() -> None:
    for template in FIXTURES.rglob("SKILL.md.example"):
        text = template.read_text(encoding="utf-8")
        assert "合成" in text, template
        assert "不会" in text or "不包含" in text or "不含" in text, template


def test_expected_counts(built) -> None:
    summary = built["summary"]
    # 8 template records; two same-named weather-lookup copies are retained, so 8 items.
    assert summary["skill_count"] == 6
    assert summary["plugin_skill_count"] == 2
    assert summary["plugin_count"] == 1
    assert summary["family_count"] == 4
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
    assert builder.inject_banner(builder.load_builder().render_html(public)) == built["__html__"]


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
