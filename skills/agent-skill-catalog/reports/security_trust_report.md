# Security Trust Report

- OK: `True`
- Scanned files: `23`
- Scripts: `4`
- Internal script modules: `1`
- Secret findings: `0`
- Network-capable scripts: `1`
- Network policy covered scripts: `1`
- Network policy missing scripts: `0`
- File-write scripts: `4`
- Permission approvals: `3 / 3`
- Permission approval gaps: `0`
- CLI help smoke checked: `3`
- CLI help smoke failures: `0`
- Interactive scripts: `0`
- Package hash scope: `source-contract-without-generated-reports`
- Package hash files: `23`
- Package SHA256: `e63712411d539ec32e48f1825bb04a79ec995b4a952d5c3ad193a1579d18adde`

## Failures

- None

## Warnings

- None

## Dependency Evidence

- Files: `requirements.txt`
- Pinned entries: `0`
- Unpinned entries: `0`

## Network Policy

- Policy file: `security/network_policy.json`
- Present: `True`
- Covered scripts: `1`
- Missing scripts: `none`
- Mismatches: `0`

## Permission Governance

- Policy file: `security/permission_policy.json`
- Present: `True`
- Required capabilities: `file_write, network, subprocess`
- Approved capabilities: `file_write, network, subprocess`
- Missing approvals: `none`
- Invalid approvals: `none`
- Expired approvals: `none`

## CLI Help Smoke

- Enabled: `True`
- Timeout seconds: `5.0`
- Checked scripts: `3`
- Passed scripts: `3`
- Failed scripts: `none`

## Script Surface

| Script | Interface | Declared | Argparse | Main Guard | Input | Network | File Write | Subprocess | Reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| scripts\build_catalog.py | cli | False | True | True | False | False | True | False | Default CLI classification; add SCRIPT_INTERFACE for internal modules. |
| scripts\github_preview.py | internal-module | True | False | False | False | True | True | False | Imported by build_catalog.py to isolate bounded GitHub preview retrieval. |
| scripts\import_legacy_catalog.py | cli | False | True | True | False | False | True | False | Default CLI classification; add SCRIPT_INTERFACE for internal modules. |
| scripts\serve_catalog.py | cli | False | True | True | False | False | True | True | Default CLI classification; add SCRIPT_INTERFACE for internal modules. |
