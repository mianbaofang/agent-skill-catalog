#!/usr/bin/env python3
"""Regression checks for the portable release Skill ZIP."""

from __future__ import annotations

import importlib.util
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "package_skill.py"
VALIDATOR_SCRIPT = ROOT / "tools" / "validate_package.py"


def load_module():
    spec = importlib.util.spec_from_file_location("package_skill", SCRIPT)
    if spec is None or spec.loader is None:
        raise AssertionError("Cannot load package_skill.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_package", VALIDATOR_SCRIPT)
    if spec is None or spec.loader is None:
        raise AssertionError("Cannot load validate_package.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_install_doc(root: Path, relative: str, pin: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"gh skill install mianbaofang/agent-skill-catalog agent-skill-catalog --pin {pin}\n",
        encoding="utf-8",
    )


def pin_failures(pins: dict[str, str]) -> list[str]:
    module = load_validator()
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        for relative in module.INSTALL_DOCS:
            write_install_doc(root, relative, pins[relative])
        return module.validate_install_pins(root, "0.3.6")


def test_install_package_excludes_maintenance_evidence() -> None:
    module = load_module()
    skill_root = ROOT / "skills" / "agent-skill-catalog"
    included = {relative.as_posix() for _, relative in module.package_paths(skill_root)}
    assert "scripts/build_catalog.py" in included
    assert "scripts/catalog_aggregation.py" in included
    assert "scripts/catalog_page.py" in included
    assert "scripts/description_queue.py" in included
    assert "scripts/github_discovery.py" in included
    assert "scripts/github_preview.py" in included
    assert "references/workflow.md" in included
    assert not any(relative.split("/", 1)[0] in {"build", "evals", "reports"} for relative in included)


def test_governance_evidence_stays_outside_the_install_boundary() -> None:
    governance = ROOT / "governance" / "agent-skill-catalog"
    assert (governance / "evals" / "trigger_cases.json").is_file()
    assert (governance / "reports" / "output_quality_scorecard.md").is_file()
    assert not (ROOT / "skills" / "agent-skill-catalog" / "evals").exists()


def test_repository_has_one_github_discoverable_skill() -> None:
    assert not (ROOT / "SKILL.md").exists()
    assert (ROOT / "skills" / "agent-skill-catalog" / "SKILL.md").is_file()
    discovered = [
        path
        for path in ROOT.rglob("SKILL.md")
        if ".demo-fixtures" not in path.parts and "build" not in path.parts
    ]
    assert discovered == [ROOT / "skills" / "agent-skill-catalog" / "SKILL.md"]
    # The public demo may hold generated HTML/JSON, but never an installable Skill.
    demo_root = ROOT / "docs" / "demo"
    if demo_root.is_dir():
        assert not (demo_root / "SKILL.md").exists()


def test_release_archive_is_portable() -> None:
    module = load_module()
    skill_root = ROOT / "skills" / "agent-skill-catalog"
    with tempfile.TemporaryDirectory() as temporary:
        archive = Path(temporary) / "agent-skill-catalog-skill.zip"
        module.write_package(skill_root, archive)
        with zipfile.ZipFile(archive) as handle:
            names = set(handle.namelist())
            assert "agent-skill-catalog/SKILL.md" in names
            assert "agent-skill-catalog/LICENSE" in names
            assert "agent-skill-catalog/scripts/github_preview.py" in names
            assert "agent-skill-catalog/scripts/github_discovery.py" in names
            assert "agent-skill-catalog/scripts/catalog_page.py" in names
            assert "agent-skill-catalog/scripts/catalog_aggregation.py" in names
            assert "agent-skill-catalog/scripts/description_queue.py" in names
            assert sum(name.endswith("/SKILL.md") for name in names) == 1
            assert not any(part in {"build", "evals", "reports", "__pycache__"} for name in names for part in Path(name).parts)
            for name in names:
                if Path(name).suffix.lower() not in {".md", ".json", ".py", ".yaml", ".yml", ".txt"}:
                    continue
                content = handle.read(name).decode("utf-8", errors="ignore")
                assert not module.PRIVATE_PATH.search(content), name


def test_package_boundary_excludes_nested_skills_examples_and_symlinks() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as temporary:
        skill_root = Path(temporary)
        (skill_root / "SKILL.md").write_text("---\nname: root\n---\n", encoding="utf-8")
        (skill_root / "scripts").mkdir()
        (skill_root / "scripts" / "kept.py").write_text("print('ok')\n", encoding="utf-8")
        (skill_root / "skills" / "child").mkdir(parents=True)
        (skill_root / "skills" / "child" / "SKILL.md").write_text("child\n", encoding="utf-8")
        (skill_root / "examples").mkdir()
        (skill_root / "examples" / "sample.md").write_text("sample\n", encoding="utf-8")
        (skill_root / "nested").mkdir()
        (skill_root / "nested" / "SKILL.md").write_text("nested\n", encoding="utf-8")
        try:
            (skill_root / "linked.txt").symlink_to(skill_root / "scripts" / "kept.py")
        except (OSError, NotImplementedError):
            pass

        included = {relative.as_posix() for _, relative in module.package_paths(skill_root)}
        assert included == {"SKILL.md", "scripts/kept.py"}


def test_install_docs_accept_current_source_or_release_pin() -> None:
    docs = load_validator().INSTALL_DOCS
    assert pin_failures({relative: "main" for relative in docs}) == []


def test_install_docs_accept_current_release_pin() -> None:
    docs = load_validator().INSTALL_DOCS
    assert pin_failures({relative: "v0.3.6" for relative in docs}) == []


def test_install_docs_reject_arbitrary_mismatched_tag() -> None:
    docs = load_validator().INSTALL_DOCS
    failures = pin_failures({relative: "v0.0.1" for relative in docs})
    assert failures, "An arbitrary mismatched tag must fail validation."


def test_install_docs_require_a_pin() -> None:
    module = load_validator()
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        for relative in module.INSTALL_DOCS:
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                "Install the catalog Skill with `gh skill install`.\n", encoding="utf-8"
            )
        failures = module.validate_install_pins(root, "0.3.6")
        assert failures, "Install docs without any pin must fail validation."


def test_demo_fixtures_do_not_become_installable_skills() -> None:
    module = load_module()
    skill_root = ROOT / "skills" / "agent-skill-catalog"
    included = {relative.as_posix() for _, relative in module.package_paths(skill_root)}
    assert not any("SKILL.md.example" in relative for relative in included)
    assert not any(part in {"examples", ".demo-fixtures"} for relative in included for part in Path(relative).parts)


def main() -> None:
    test_install_package_excludes_maintenance_evidence()
    test_governance_evidence_stays_outside_the_install_boundary()
    test_repository_has_one_github_discoverable_skill()
    test_release_archive_is_portable()
    test_package_boundary_excludes_nested_skills_examples_and_symlinks()
    test_install_docs_accept_current_source_or_release_pin()
    test_install_docs_accept_current_release_pin()
    test_install_docs_reject_arbitrary_mismatched_tag()
    test_install_docs_require_a_pin()
    test_demo_fixtures_do_not_become_installable_skills()
    print("ok")


if __name__ == "__main__":
    main()
