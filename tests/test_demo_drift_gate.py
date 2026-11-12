"""Regression checks that the demo drift gate always runs and blocks."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
VALIDATE_WORKFLOW = WORKFLOWS / "validate.yml"
PAGES_WORKFLOW = WORKFLOWS / "pages.yml"
BUILD_DEMO_SCRIPT = ROOT / "tools" / "build_demo.py"
DRIFT_COMMAND = "python tools/build_demo.py --check"


def _steps(workflow_path: Path) -> list[dict[str, str]]:
    """Return the ``run``/``if``/``name`` fields of every step, stdlib only.

    Only the subset of step keys this test reasons about is parsed. A step is
    recognised by a top-level ``- `` list item inside a job's ``steps:`` block,
    which is enough to detect a conditional ``if:`` guarding a step command.
    """

    steps: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for raw in workflow_path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()
        if indent == 0:
            current = None
            continue
        if stripped.startswith("- "):
            current = {"indent": str(indent)}
            steps.append(current)
            stripped = stripped[2:].strip()
            if not stripped:
                continue
        if current is None:
            continue
        key, _, value = stripped.partition(":")
        key = key.strip()
        value = value.strip()
        if key in ("run", "if", "name", "uses"):
            current[key] = value
    return steps


def _drift_steps(workflow_path: Path) -> list[dict[str, str]]:
    return [step for step in _steps(workflow_path) if step.get("run") == DRIFT_COMMAND]


def test_build_demo_script_is_present() -> None:
    assert BUILD_DEMO_SCRIPT.is_file(), (
        "tools/build_demo.py must exist; the demo drift gate invokes it directly "
        "and a missing file must fail the build rather than be skipped."
    )


def test_validate_workflow_runs_demo_drift_unconditionally() -> None:
    drift_steps = _drift_steps(VALIDATE_WORKFLOW)
    assert drift_steps, (
        "validate workflow must run the demo drift gate on push and pull request."
    )
    for step in drift_steps:
        assert "if" not in step, (
            "demo drift gate must be unconditional; a conditional step would "
            "silently pass when it does not run."
        )


def test_pages_deploy_waits_for_validation_and_scopes_publish_permissions() -> None:
    text = PAGES_WORKFLOW.read_text(encoding="utf-8")
    assert "needs: validate" in text, "Pages deploy must wait for the validate job."
    validate_permissions = text.split("validate:", 1)[1].split("deploy:", 1)[0]
    assert "pages: write" not in validate_permissions, (
        "validate job must not hold Pages publishing permission."
    )
    assert "id-token: write" not in validate_permissions, (
        "validate job must not hold identity-token permission."
    )
    deploy_section = text.split("deploy:", 1)[1]
    assert "pages: write" in deploy_section
    assert "id-token: write" in deploy_section
