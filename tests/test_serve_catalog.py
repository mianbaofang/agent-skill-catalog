import json
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ROOT = REPO_ROOT / "skills" / "agent-skill-catalog"
BUILD_SCRIPT = ROOT / "scripts" / "build_catalog.py"
SERVER_SCRIPT = ROOT / "scripts" / "serve_catalog.py"


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
