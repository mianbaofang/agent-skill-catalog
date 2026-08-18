import json
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
ROOT = REPO_ROOT / "skills" / "agent-skill-catalog"
BUILD_SCRIPT = ROOT / "scripts" / "build_catalog.py"
SERVER_SCRIPT = ROOT / "scripts" / "serve_catalog.py"


def _load_server_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location("serve_catalog_test", SERVER_SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def _wait_for_server(port: int, process: subprocess.Popen[bytes]) -> None:
    health_url = f"http://127.0.0.1:{port}/api/health"
    for _ in range(50):
        if process.poll() is not None:
            raise AssertionError("Catalog server exited before becoming ready")
        try:
            with urllib.request.urlopen(health_url, timeout=1) as response:
                assert response.status == 200
                return
        except OSError:
            time.sleep(0.1)
    raise AssertionError("Catalog server did not start")


def test_require_complete_descriptions_server_retries_after_curation() -> None:
    with tempfile.TemporaryDirectory() as temp:
        fixture = Path(temp)
        root = fixture / "skills"
        skill = root / "english"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            "---\nname: english\ndescription: Search public sources and produce a cited research brief.\n---\n",
            encoding="utf-8",
        )
        output = fixture / "output"
        subprocess.run(
            [sys.executable, str(BUILD_SCRIPT), "--root", str(root), "--output-dir", str(output)],
            check=True,
            capture_output=True,
            text=True,
        )

        port = _free_port()
        process = subprocess.Popen(
            [
                sys.executable,
                str(SERVER_SCRIPT),
                "--output-dir",
                str(output),
                "--root",
                str(root),
                "--port",
                str(port),
                "--require-complete-descriptions",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            _wait_for_server(port, process)
            refresh = urllib.request.Request(f"http://127.0.0.1:{port}/api/refresh", method="POST")
            try:
                urllib.request.urlopen(refresh, timeout=15)
            except urllib.error.HTTPError as error:
                assert error.code == 500
                payload = json.loads(error.read().decode("utf-8"))
                assert payload["ok"] is False
                assert "pending description" in payload["details"].casefold()
            else:
                raise AssertionError("A pending description queue must fail the required refresh")

            curation_path = output / "catalog-curation.json"
            curation = json.loads(curation_path.read_text(encoding="utf-8"))
            curation["description_overrides"]["english/SKILL.md"] = (
                "检索公开来源并整理为带引用的研究简报，适合需要核对事实、保留出处并形成可复查结论的任务。"
            )
            curation_path.write_text(json.dumps(curation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

            with urllib.request.urlopen(refresh, timeout=15) as response:
                payload = json.loads(response.read().decode("utf-8"))
            assert response.status == 200
            assert payload["ok"] is True
            catalog = json.loads((output / "catalog.json").read_text(encoding="utf-8"))
            assert catalog["summary"]["pending_description_count"] == 0
        finally:
            process.terminate()
            process.wait(timeout=5)


def test_delete_endpoint_requires_exact_name_and_deletes_one_top_level_skill() -> None:
    with tempfile.TemporaryDirectory() as temp:
        fixture = Path(temp)
        root = fixture / "skills"
        for name in ("delete-me", "keep-me"):
            skill = root / name
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text(
                f"---\nname: {name}\ndescription: 本地测试技能。\n---\n",
                encoding="utf-8",
            )
        config = fixture / "catalog-config.json"
        config.write_text(
            json.dumps(
                {
                    "roots": [{"path": str(root), "label": "Skills", "kind": "skill", "allow_delete": True}],
                    "categories": {"other": {"label": "其他", "keywords": []}},
                    "category_tie_break": ["other"],
                    "image": {"github_repository_previews": False},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        output = fixture / "output"
        subprocess.run(
            [sys.executable, str(BUILD_SCRIPT), "--config", str(config), "--output-dir", str(output)],
            check=True,
            capture_output=True,
            text=True,
        )
        item = next(item for item in json.loads((output / "catalog.json").read_text(encoding="utf-8"))["items"] if item["name"] == "delete-me")
        curated_image = output / "curated-images" / "delete-me.png"
        curated_image.parent.mkdir()
        curated_image.write_bytes(b"manual preview")
        curation_path = output / "catalog-curation.json"
        curation = json.loads(curation_path.read_text(encoding="utf-8"))
        curation["image_overrides"][item["relative_path"]] = str(curated_image.resolve())
        curation_path.write_text(json.dumps(curation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        port = _free_port()
        process = subprocess.Popen(
            [sys.executable, str(SERVER_SCRIPT), "--config", str(config), "--output-dir", str(output), "--port", str(port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            _wait_for_server(port, process)
            base_payload = {"id": item["id"], "name": item["name"], "relative_path": item["relative_path"]}
            invalid = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/delete",
                data=json.dumps({**base_payload, "confirmation": "wrong"}).encode("utf-8"),
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with pytest.raises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(invalid, timeout=15)
            assert error.value.code == 400
            assert (root / "delete-me" / "SKILL.md").is_file()

            valid = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/delete",
                data=json.dumps({**base_payload, "confirmation": "delete-me"}).encode("utf-8"),
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(valid, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))
            assert payload["ok"] is True
            assert not (root / "delete-me").exists()
            assert not curated_image.exists()
            curation = json.loads(curation_path.read_text(encoding="utf-8"))
            assert item["relative_path"] not in curation["image_overrides"]
            names = {entry["name"] for entry in json.loads((output / "catalog.json").read_text(encoding="utf-8"))["items"]}
            assert names == {"keep-me"}
        finally:
            process.terminate()
            process.wait(timeout=5)


def test_delete_helper_rejects_non_top_level_grouped_plugin_and_disabled_roots() -> None:
    module = _load_server_module()
    with tempfile.TemporaryDirectory() as temp:
        fixture = Path(temp)
        root = fixture / "skills"
        skill = root / "demo"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: demo\ndescription: demo\n---\n", encoding="utf-8")
        output = fixture / "output"
        output.mkdir()
        root_id = module.root_id(str(root))
        base_item = {
            "id": "skill:demo",
            "name": "demo",
            "relative_path": "demo/SKILL.md",
            "kind": "skill",
            "family_size": 1,
            "root_id": root_id,
            "allow_delete": True,
        }
        payload = {"id": "skill:demo", "name": "demo", "relative_path": "demo/SKILL.md", "confirmation": "demo"}
        allowed = [{"path": str(root), "label": "Skills", "kind": "skill", "allow_delete": True}]

        cases = [
            ({**base_item, "kind": "plugin"}, allowed),
            ({**base_item, "family_size": 2}, allowed),
            ({**base_item, "relative_path": "bundle/demo/SKILL.md"}, allowed),
            (base_item, [{**allowed[0], "allow_delete": False}]),
        ]
        for item, specs in cases:
            (output / "catalog.json").write_text(json.dumps({"items": [item]}), encoding="utf-8")
            request = {**payload, "relative_path": item["relative_path"]}
            with pytest.raises(PermissionError):
                module.delete_catalog_skill(output, specs, request)
            assert skill.is_dir()
