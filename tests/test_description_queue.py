import argparse
import importlib.util
import json
import subprocess
import sys
import tempfile
from unittest.mock import patch
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = REPO_ROOT / "skills" / "agent-skill-catalog"
BUILD_SCRIPT = SKILL_ROOT / "scripts" / "build_catalog.py"
QUEUE_SCRIPT = SKILL_ROOT / "scripts" / "description_queue.py"


def load_description_queue():
    spec = importlib.util.spec_from_file_location("description_queue_test", QUEUE_SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, *args], capture_output=True, text=True, check=check)


def write_skill(root: Path, name: str, description: str) -> None:
    skill = root / name
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\n# {name}\n\nReturn a factual result.\n",
        encoding="utf-8",
    )


def test_description_batches_resume_and_close_the_builder_gate() -> None:
    with tempfile.TemporaryDirectory() as temp:
        fixture = Path(temp)
        root = fixture / "skills"
        write_skill(root, "first", "Search public sources and prepare a cited brief.")
        write_skill(root, "second", "Review a code change and identify concrete risks.")
        output = fixture / "output"

        first_build = run(
            str(BUILD_SCRIPT),
            "--root",
            str(root),
            "--output-dir",
            str(output),
            "--require-complete-descriptions",
            check=False,
        )
        assert first_build.returncode == 3

        run(
            str(QUEUE_SCRIPT),
            "next",
            "--root",
            str(root),
            "--output-dir",
            str(output),
            "--batch-size",
            "1",
            "--no-github-readmes",
        )
        batch_path = output / "description-batch.json"
        first_batch = json.loads(batch_path.read_text(encoding="utf-8"))
        assert first_batch["batch_count"] == 1
        assert first_batch["pending_before"] == 2
        assert first_batch["items"][0]["local_skill"]["status"] == "local-skill"
        assert "Return a factual result" in first_batch["items"][0]["local_skill"]["excerpt"]
        assert str(root) not in batch_path.read_text(encoding="utf-8")

        first_key = first_batch["items"][0]["curation_key"]
        response_path = output / "description-batch.responses.json"
        response_path.write_text(
            json.dumps(
                {
                    "items": [
                        {
                            "curation_key": first_key,
                            "description": "读取公开资料并整理成带出处的研究简报，适合需要核对事实、保留引用并交付可复查结论的任务。",
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        run(str(QUEUE_SCRIPT), "apply", "--output-dir", str(output), "--input", str(response_path))

        run(
            str(QUEUE_SCRIPT),
            "next",
            "--root",
            str(root),
            "--output-dir",
            str(output),
            "--batch-size",
            "1",
            "--no-github-readmes",
        )
        second_batch = json.loads(batch_path.read_text(encoding="utf-8"))
        assert second_batch["pending_before"] == 1
        second_key = second_batch["items"][0]["curation_key"]
        assert second_key != first_key

        response_path.write_text(
            json.dumps(
                {
                    "items": [
                        {
                            "curation_key": second_key,
                            "description": "检查代码改动中的行为回归、错误处理和测试缺口，输出按严重程度排序且可定位到具体文件的审查意见。",
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        run(str(QUEUE_SCRIPT), "apply", "--output-dir", str(output), "--input", str(response_path))

        final_build = run(
            str(BUILD_SCRIPT),
            "--root",
            str(root),
            "--output-dir",
            str(output),
            "--refresh",
            "--require-complete-descriptions",
            check=False,
        )
        assert final_build.returncode == 0
        catalog = json.loads((output / "catalog.json").read_text(encoding="utf-8"))
        assert catalog["summary"]["pending_description_count"] == 0
        assert {item["description_source"] for item in catalog["items"]} == {"curation"}


def test_github_readme_fetch_uses_15_second_default_timeout() -> None:
    module = load_description_queue()
    calls: list[int] = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def read(self, _limit: int) -> bytes:
            return b"# Catalog\n\nEvidence-backed README excerpt."

    def open_allowed(_request, timeout, _allowed_hosts):
        calls.append(timeout)
        return Response()

    with tempfile.TemporaryDirectory() as temp:
        with patch.object(module, "open_allowed", open_allowed):
            result = module.fetch_github_readme(
                "https://github.com/example/catalog",
                Path(temp),
            )

    assert result["status"] == "github-readme"
    assert calls == [15]


def test_github_readme_failures_are_retryable() -> None:
    module = load_description_queue()
    calls: list[int] = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def read(self, _limit: int) -> bytes:
            return b"# Catalog\n\nEvidence-backed README excerpt."

    def open_allowed(_request, timeout, _allowed_hosts):
        calls.append(timeout)
        if len(calls) <= 4:
            raise OSError("temporary failure")
        return Response()

    with tempfile.TemporaryDirectory() as temp:
        cache_dir = Path(temp)
        with patch.object(module, "open_allowed", open_allowed):
            first = module.fetch_github_readme("https://github.com/example/catalog", cache_dir)
            assert not list(cache_dir.glob("*.json"))
            second = module.fetch_github_readme("https://github.com/example/catalog", cache_dir)

        assert first["status"] == "missing-evidence"
        assert second["status"] == "github-readme"
        assert calls == [15, 15, 15, 15, 15]
        assert list(cache_dir.glob("*.json"))


def test_description_batch_passes_configured_readme_timeout() -> None:
    module = load_description_queue()
    with tempfile.TemporaryDirectory() as temp:
        fixture = Path(temp)
        root = fixture / "skills"
        write_skill(root, "catalog", "Search public sources at https://github.com/example/catalog.")
        output = fixture / "output"
        config = fixture / "config.json"
        config.write_text(
            json.dumps(
                {
                    "image": {
                        "github_repository_previews": False,
                        "github_request_timeout_seconds": 4,
                    }
                }
            ),
            encoding="utf-8",
        )
        run(str(BUILD_SCRIPT), "--config", str(config), "--root", str(root), "--output-dir", str(output))
        calls: list[int] = []

        def fake_fetch(repository_url, cache_dir, timeout):
            calls.append(timeout)
            return {"status": "github-readme", "repository_url": repository_url, "excerpt": "证据", "truncated": False}

        args = argparse.Namespace(
            output_dir=str(output),
            config=str(config),
            root=[str(root)],
            batch_size=1,
            output=None,
            no_github_readmes=False,
        )
        with patch.object(module, "fetch_github_readme", fake_fetch):
            assert module.prepare_batch(args) == 0
        assert calls == [4]


def test_description_apply_rejects_non_chinese_copy() -> None:
    with tempfile.TemporaryDirectory() as temp:
        fixture = Path(temp)
        root = fixture / "skills"
        write_skill(root, "english", "Search public sources and prepare a cited brief.")
        output = fixture / "output"
        run(str(BUILD_SCRIPT), "--root", str(root), "--output-dir", str(output))
        queue = json.loads((output / "description-enrichment.json").read_text(encoding="utf-8"))
        response = fixture / "responses.json"
        response.write_text(
            json.dumps({"items": [{"curation_key": queue["items"][0]["curation_key"], "description": "English only description that should fail."}]}),
            encoding="utf-8",
        )

        result = run(
            str(QUEUE_SCRIPT),
            "apply",
            "--output-dir",
            str(output),
            "--input",
            str(response),
            check=False,
        )
        assert result.returncode == 2
        assert "not-zh-CN" in result.stderr
        curation = json.loads((output / "catalog-curation.json").read_text(encoding="utf-8"))
        assert curation["description_overrides"] == {}


def test_description_batch_does_not_read_outside_a_scan_root() -> None:
    with tempfile.TemporaryDirectory() as temp:
        fixture = Path(temp)
        root = fixture / "skills"
        write_skill(root, "inside", "Search public sources and prepare a cited brief.")
        outside = fixture / "outside" / "SKILL.md"
        outside.parent.mkdir()
        outside.write_text("private evidence", encoding="utf-8")
        output = fixture / "output"
        run(str(BUILD_SCRIPT), "--root", str(root), "--output-dir", str(output))

        queue_path = output / "description-enrichment.json"
        queue = json.loads(queue_path.read_text(encoding="utf-8"))
        queue["items"][0]["relative_path"] = "../outside/SKILL.md"
        queue_path.write_text(json.dumps(queue, ensure_ascii=False), encoding="utf-8")

        run(
            str(QUEUE_SCRIPT),
            "next",
            "--root",
            str(root),
            "--output-dir",
            str(output),
            "--no-github-readmes",
        )
        batch = json.loads((output / "description-batch.json").read_text(encoding="utf-8"))
        assert batch["items"][0]["local_skill"]["status"] == "missing-evidence"
        assert "private evidence" not in json.dumps(batch, ensure_ascii=False)
