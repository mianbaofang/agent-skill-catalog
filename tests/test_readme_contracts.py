from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_both_readmes_present() -> None:
    assert (ROOT / "README.md").is_file()
    assert (ROOT / "README.zh-CN.md").is_file()


def test_primary_install_pins_main_not_a_release() -> None:
    for name in ("README.md", "README.zh-CN.md"):
        text = _read(name)
        assert "gh skill install mianbaofang/agent-skill-catalog agent-skill-catalog --pin main --agent codex --scope user" in text, name
        # v0.3.6 may be referenced as the prior tagged stable build, but must not
        # be the primary install command.
        assert "--pin v0.3.6 --agent" not in text, f"{name} still pins v0.3.6 as the primary install"


def test_offline_flags_are_complete_in_both_readmes() -> None:
    for name in ("README.md", "README.zh-CN.md"):
        text = _read(name)
        assert "--no-github-discovery" in text, name
        assert "--no-github-images" in text, name
        assert "--no-github-readmes" in text, name

    # Markdown emphasis can sit inside the phrase, so match on a bold-insensitive form.
    en_plain = re.sub(r"\*+", "", _read("README.md")).lower()
    assert "not guaranteed offline" in en_plain, "EN README should say the default build is not guaranteed offline"
    assert "不保证" in _read("README.zh-CN.md"), "ZH README should say the default build is not guaranteed offline"


def test_no_unsupported_timing_claims() -> None:
    banned = ["about a minute", "in about a minute", "一分钟生成", "Takes about"]
    for name in ("README.md", "README.zh-CN.md"):
        text = _read(name)
        for phrase in banned:
            assert phrase not in text, f"{name} contains unsupported timing claim: {phrase}"


def test_task_guides_are_linked_in_both_readmes() -> None:
    for name, slug in (
        ("README.md", "search-installed-skills"),
        ("README.md", "offline-skill-catalog"),
        ("README.md", "skills-and-plugin-inventory"),
        ("README.zh-CN.md", "search-installed-skills-zh"),
        ("README.zh-CN.md", "offline-skill-catalog-zh"),
        ("README.zh-CN.md", "skills-and-plugin-inventory-zh"),
    ):
        text = _read(name)
        assert f"/guides/{slug}.html" in text, f"{name} missing guide link {slug}"


def test_readme_image_references_resolve() -> None:
    for name in ("README.md", "README.zh-CN.md"):
        text = _read(name)
        for src in re.findall(r'<img[^>]+src="((?:docs/)?media/[^"?#]+)"', text):
            assert (ROOT / src).is_file(), f"{name} references missing image {src}"


def test_safety_and_license_links_preserved() -> None:
    for name in ("README.md", "README.zh-CN.md"):
        text = _read(name)
        for link in ("DISCLAIMER.md", "SECURITY.md", "ACKNOWLEDGEMENTS.md", "CHANGELOG.md", "LICENSE"):
            assert link in text, f"{name} missing {link}"


def test_interface_language_is_stated_truthfully() -> None:
    en = _read("README.md")
    zh = _read("README.zh-CN.md")
    assert "interface is Chinese" in en, "EN README should state the generated UI is Chinese"
    assert "界面是中文" in zh, "ZH README should state the generated UI is Chinese"
