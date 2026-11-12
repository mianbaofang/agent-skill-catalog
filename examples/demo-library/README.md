# Demo fixtures (synthetic)

These fixtures are **original, synthetic example data** created for this project's
public demo. They are not real installed Skills, not third-party prompts or assets,
and they do not describe any real product, vendor, or GitHub repository.

- Every directory uses `SKILL.md.example` (not `SKILL.md`) so the committed copies are
  visibly non-installable templates and are never discovered as repository skills.
  `tools/build_demo.py` copies this tree into an isolated temporary directory and
  materializes real `SKILL.md` files there before running the real scanner.
- Every fixture body carries a visible boundary note: it is a demo record with no
  runnable implementation, no network access, and no real task execution.
- No absolute or machine-specific paths are stored here; the scanner records only
  relative paths, and the builder re-maps roots to logical placeholders.

## What the fixtures demonstrate

| Fixture | Scenario |
|---|---|
| `roots/community-skills/csv-clean` | A standalone Skill (single entry, no family/plugin). |
| `roots/community-skills/weather-lookup` | A standalone Skill that shares a name with a Skill in another root. Because there is no shared repository evidence, the scanner conservatively keeps both entries separate. |
| `roots/personal-skills/note-keeper`, `-web`, `-cli` | A true parent/child family: `note-keeper` is the primary entry and `-web` / `-cli` are routed child Skills (family of 3). |
| `roots/personal-skills/weather-lookup` | The second, same-named copy retained in a different root (see above). |
| `plugins/demo-corp/toolkit/1.0.0` | A plugin bundle (`demo-corp` is a synthetic provider) carrying `refresh-cache` and `review-draft`; plugin members appear in the separate plugin view. |

## Rebuild the public demo

```bash
python tools/build_demo.py            # regenerate docs/demo from these fixtures
python tools/build_demo.py --check    # verify tracked docs/demo matches (read-only)
```

The build is offline (no GitHub discovery or images), runs from a fresh clone with
the Python standard library, and pins the output to a documented build epoch so the
committed `docs/demo` is byte-stable. See `docs/DEMO.md` for details.
