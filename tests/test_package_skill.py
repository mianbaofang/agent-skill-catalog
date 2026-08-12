#!/usr/bin/env python3
"""Regression checks for the portable release Skill ZIP."""

from __future__ import annotations

import importlib.util
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "package_skill.py"


def load_module():
    spec = importlib.util.spec_from_file_location("package_skill", SCRIPT)
    if spec is None or spec.loader is None:
        raise AssertionError("Cannot load package_skill.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_report_allowlist() -> None:
    module = load_module()
    skill_root = ROOT / "skills" / "agent-skill-catalog"
    included = {relative.as_posix() for _, relative in module.package_paths(skill_root)}
    assert "reports/output_quality_scorecard.md" in included
    assert "reports/security_trust_report.md" in included
    assert "reports/install_simulation.md" not in included
    assert "reports/review-studio.html" not in included


def test_repository_has_one_github_discoverable_skill() -> None:
    assert not (ROOT / "SKILL.md").exists()
    assert (ROOT / "skills" / "agent-skill-catalog" / "SKILL.md").is_file()
    discovered = [path for path in ROOT.rglob("SKILL.md") if ".demo-fixtures" not in path.parts]
    assert discovered == [ROOT / "skills" / "agent-skill-catalog" / "SKILL.md"]
    demo_root = ROOT / "docs" / "demo"
    assert not demo_root.exists() or not any(path.is_file() for path in demo_root.rglob("*"))


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
            assert "agent-skill-catalog/reports/output_quality_scorecard.md" in names
            assert "agent-skill-catalog/reports/install_simulation.md" not in names
            assert sum(name.endswith("/SKILL.md") for name in names) == 1
            assert not any("demo" in Path(name).parts for name in names)
            for name in names:
                if Path(name).suffix.lower() not in {".md", ".json", ".py", ".yaml", ".yml", ".txt"}:
                    continue
                content = handle.read(name).decode("utf-8", errors="ignore")
                assert not module.PRIVATE_PATH.search(content), name


def main() -> None:
    test_report_allowlist()
    test_repository_has_one_github_discoverable_skill()
    test_release_archive_is_portable()
    print("ok")


if __name__ == "__main__":
    main()
