import importlib.util
import json
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
ROOT = REPO_ROOT / "skills" / "agent-skill-catalog"
BUILD_SCRIPT = ROOT / "scripts" / "build_catalog.py"
SERVER_SCRIPT = ROOT / "scripts" / "serve_catalog.py"
PERMISSION_POLICY = ROOT / "security" / "permission_policy.json"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _build_parser(script: Path, module_name: str):
    module = _load_module(module_name, script)
    return module.parser()


def test_shipped_config_examples_keep_deletion_disabled() -> None:
    for name in (
        "catalog-config.json",
        "catalog-config.windows.example.json",
        "catalog-config.posix.example.json",
    ):
        payload = json.loads((ROOT / "references" / name).read_text(encoding="utf-8"))
        roots = payload.get("roots")
        if not isinstance(roots, list):
            continue
        for entry in roots:
            if isinstance(entry, dict):
                assert entry.get("allow_delete", False) is False, name


def test_offline_flags_exist_on_builder_and_server() -> None:
    build_flags = {action.option_strings[0] for action in _build_parser(BUILD_SCRIPT, "build_catalog_contract")._actions}
    server_flags = {action.option_strings[0] for action in _load_module("serve_catalog_contract", SERVER_SCRIPT).parser()._actions}
    for flag in ("--no-github-discovery", "--no-github-images"):
        assert flag in build_flags
        assert flag in server_flags
    assert "--require-complete-descriptions" in build_flags
    assert "--require-complete-descriptions" in server_flags


def test_server_refresh_command_carries_flags_roots_and_curation_but_not_http_input() -> None:
    module = _load_module("serve_catalog_contract_command", SERVER_SCRIPT)
    command = module.build_refresh_command(
        Path("catalog-config.json"),
        Path("output"),
        ["curated.json"],
        "cli",
        [str(ROOT), str(ROOT / "plugins")],
        True,
        ["--no-github-discovery", "--no-github-images"],
    )
    assert command[1:3] == [str(module.BUILD_SCRIPT), "--config"]
    for token in (
        "--refresh",
        "--no-github-discovery",
        "--no-github-images",
        "--require-complete-descriptions",
        "--root",
        str(ROOT),
        "--curation",
        "curated.json",
    ):
        assert token in command
    # The command is derived only from startup values: there is no channel for an
    # HTTP body, header, or query string to add or replace roots, config, or flags.
    assert not any("http" in token.lower() for token in command)
    config_only = module.build_refresh_command(
        Path("catalog-config.json"),
        Path("output"),
        [],
        "config",
        [],
        False,
        [],
    )
    assert "--root" not in config_only
    assert "--require-complete-descriptions" not in config_only


def test_permission_policy_discloses_optional_network_and_opt_in_deletion() -> None:
    payload = json.loads(PERMISSION_POLICY.read_text(encoding="utf-8"))
    network = payload["capabilities"]["network"]["scope"]
    file_write = payload["capabilities"]["file_write"]["scope"]
    for token in ("--no-github-discovery", "--no-github-images", "--no-github-readmes"):
        assert token in network
    assert "GitHub CLI" in network or "GH_TOKEN" in network
    # Deletion is disclosed as a separately enabled capability, never as part of the
    # scanning or refresh approval, and every shipped config example leaves it off.
    assert "allow_delete" in file_write
    assert "not covered by this approval" in payload["capabilities"]["file_write"]["reason"]
    for name in ("catalog-config.json", "catalog-config.windows.example.json"):
        config = json.loads((ROOT / "references" / name).read_text(encoding="utf-8"))
        for root in config["roots"]:
            assert root.get("allow_delete", False) is False, name


@pytest.mark.parametrize(
    "document,required",
    [
        (
            ROOT / "SKILL.md",
            ["--no-github-discovery --no-github-images", "--require-complete-descriptions", "pending_description_count", "allow_delete"],
        ),
        (
            ROOT / "references" / "workflow.md",
            ["Quick preview", "--no-github-discovery --no-github-images", "--no-github-readmes", "exit code 0"],
        ),
        (
            REPO_ROOT / "SECURITY.md",
            ["api.github.com", "--no-github-discovery", "--no-github-readmes", "allow_delete"],
        ),
        (
            REPO_ROOT / "DISCLAIMER.md",
            ["--no-github-discovery", "--no-github-readmes", "allow_delete"],
        ),
    ],
)
def test_usage_documents_state_the_offline_and_deletion_contract(document: Path, required: list[str]) -> None:
    text = document.read_text(encoding="utf-8")
    for token in required:
        assert token in text, f"{document.name} is missing {token}"
