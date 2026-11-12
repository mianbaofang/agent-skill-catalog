# Agent Skill Catalog

Search the agent skills you already installed.

Point it at the folders where your `SKILL.md` files live and it builds a
searchable, self-contained local HTML catalog. Find an entry, inspect its source
location and invocation text, and tell a standalone Skill apart from a verified
parent/child family or a plugin bundle.

The generated catalog interface is Chinese. This repository's documentation is
available in English and Chinese; that does not make the generated UI bilingual.
GitHub enrichment is optional. Use the explicit offline flags below when your
library must stay off the network.

<table align="center"><tr><td><a href="https://github.com/mianbaofang/agent-skill-catalog/actions/workflows/validate.yml"><img src="https://img.shields.io/github/actions/workflow/status/mianbaofang/agent-skill-catalog/validate.yml?branch=main&amp;style=flat-square&amp;label=tests" alt="Test status"></a></td><td><a href="LICENSE"><img src="https://img.shields.io/github/license/mianbaofang/agent-skill-catalog?style=flat-square" alt="License"></a></td><td><a href="https://github.com/mianbaofang/agent-skill-catalog/releases/tag/v0.3.6"><img src="https://img.shields.io/github/v/release/mianbaofang/agent-skill-catalog?style=flat-square" alt="Latest release"></a></td></tr></table>

<p align="center">
  <a href="README.zh-CN.md">中文</a>
  &middot;
  <a href="skills/agent-skill-catalog/SKILL.md">Skill</a>
  &middot;
  <a href="docs/DEMO.md">Product walkthrough</a>
  &middot;
  <a href="https://mianbaofang.github.io/agent-skill-catalog/">Project site</a>
  &middot;
  <a href="DISCLAIMER.md">Disclaimer</a>
  &middot;
  <a href="ACKNOWLEDGEMENTS.md">Acknowledgements</a>
  &middot;
  <a href="CHANGELOG.md">Changelog</a>
  &middot;
  <a href="SECURITY.md">Security</a>
</p>

<p align="center">
  <a href="docs/DEMO.md">
    <img src="docs/media/agent-skill-catalog-demo.en.gif" alt="Agent Skill Catalog product walkthrough: choose explicit roots, generate the catalog, search a Skill name, inspect its source and invocation, and compare family and plugin entries" width="100%">
  </a>
</p>

## Install

Install the published Skill with GitHub CLI (the path validated on Windows):

```powershell
gh skill install mianbaofang/agent-skill-catalog agent-skill-catalog --pin main --agent codex --scope user
```

`--pin main` installs the latest source on the repository's `main` branch. The
last tagged release is
[`v0.3.6`](https://github.com/mianbaofang/agent-skill-catalog/releases/tag/v0.3.6);
pin that instead if you want the previously published stable build.

Then tell your agent which roots to scan:

```text
Use agent-skill-catalog to scan my local Skill root and Codex plugin cache.
Keep standalone Skills and plugins separate, group real parent/child families,
and do not install, edit, or execute anything that was scanned.
```

## Build your first catalog from source

`gh skill install` puts the scripts inside the installed Skill package, not in a
working copy of this repository. To run the builder as shown below, clone or
download this repository first and run from its root, so the relative path to
`build_catalog.py` resolves:

```bash
git clone https://github.com/mianbaofang/agent-skill-catalog.git
cd agent-skill-catalog
```

Now replace the two paths with a real Skill folder and an empty output folder.
This first command stays fully offline and does **not** wait for missing Chinese
descriptions:

Bash:

```bash
python skills/agent-skill-catalog/scripts/build_catalog.py \
  --root "/path/to/skills" \
  --output-dir "/path/to/catalog-output" \
  --no-github-discovery \
  --no-github-images
```

PowerShell:

```powershell
python skills/agent-skill-catalog/scripts/build_catalog.py `
  --root "C:\path\to\skills" `
  --output-dir "$env:TEMP\agent-skill-catalog-preview" `
  --no-github-discovery `
  --no-github-images
```

Exit code 0 writes `catalog.json` and a self-contained `index.html`. Open
`index.html` in a browser and search. If the output folder already contains a
`catalog.json`, the builder stops and asks you to rerun with `--refresh`; check
that the target holds a catalog you are willing to regenerate before you do.

### Two completion states

| Build | Command | Success looks like |
|---|---|---|
| Quick preview | `build_catalog.py ... --no-github-discovery --no-github-images` | Exit code 0. Entries with missing Chinese descriptions still appear; you can browse and search right away. |
| Enriched catalog | add `--require-complete-descriptions` | Exit code 0 **and** `pending_description_count` equal to zero. Exit code 3 means Chinese descriptions are still pending, not that the program crashed. |

The enriched path is what an agent drives: it fills the pending Chinese
descriptions from bounded local `SKILL.md` and GitHub README evidence through a
resumable `description_queue.py next/apply` loop, then rebuilds with
`--refresh --require-complete-descriptions` until the queue is empty. The Python
scripts do not call a hidden model and do not need a provider key. See
[Build an offline skill catalog](https://mianbaofang.github.io/agent-skill-catalog/guides/offline-skill-catalog.html)
for the full enriched loop, and `references/workflow.md` in the Skill package
for the agent-facing steps.

## Task guides

Each guide covers one concrete job, with cross-platform commands, expected
output, limits, and troubleshooting:

- [Search the agent skills you already installed](https://mianbaofang.github.io/agent-skill-catalog/guides/search-installed-skills.html) —
  pick an explicit root, build, search, and open a Skill's invocation and source.
- [Build an offline skill catalog](https://mianbaofang.github.io/agent-skill-catalog/guides/offline-skill-catalog.html) —
  turn every GitHub request off, and understand the quick-preview and enriched
  completion states.
- [Inventory skills and plugins across folders](https://mianbaofang.github.io/agent-skill-catalog/guides/skills-and-plugin-inventory.html) —
  scan several roots, group plugins, and read verified duplicates versus
  same-name collisions and families.

These guides describe the current Chinese catalog UI.

## At a glance

| Question | Answer |
|---|---|
| What does it scan? | Only the local roots you pass explicitly, including optional roots labeled as plugin caches. |
| What is one entry? | A standalone Skill, or one parent/family record whose child Skills are listed in the detail view. |
| What about duplicate installs? | Copies backed by the same observed GitHub repository and Skill name collapse to one entry, while every source location stays available as evidence. |
| How are plugins shown? | Plugin aggregates get their own view and are not counted as standalone Skills. |
| What is kept per entry? | Category candidates, confidence, winner margin, source location, invocation text, image provenance, and an observed GitHub repository URL when the evidence supports one. |
| What if evidence is missing? | The catalog says `missing evidence`; a generated category cover is never presented as a Skill-specific image. |
| What stays off limits? | Scanning does not write to your roots. See [Safety](#safety-and-responsible-use) for the one optional, disabled-by-default server capability and the optional network reads. |

## Operating modes

| Mode | Use it when | Output |
|---|---|---|
| Static build | You only need a shareable local file | Deterministic `catalog.json` and self-contained `index.html`. |
| Local server | You want refresh and manual preview-image controls | The static catalog plus localhost-only `/api/refresh` and `/api/image` endpoints. |
| Reviewed curation | Automatic evidence is ambiguous | Scoped category, family, description, GitHub, or image overrides in a separate JSON file. |
| Plugin inventory | You scan a plugin cache | A separate plugin view with the Skills carried by each plugin. |

To use the in-page refresh action, start the local server with the same roots.
Add the two offline flags so the refresh path stays offline too:

```powershell
python skills/agent-skill-catalog/scripts/serve_catalog.py `
  --output-dir "$env:TEMP\agent-skill-catalog-preview" `
  --root "C:\path\to\skills" `
  --no-github-discovery `
  --no-github-images
```

## Product screenshots

The screenshots below come from a real generated catalog; the generated interface
is Chinese. The recorded demo animation above is a promotional walkthrough built
from non-personal synthetic test fixtures; it is not an install or runtime
dependency.

<table align="center"><tr><td><img src="docs/media/agent-skill-catalog-overview.en.png" alt="Generated catalog overview with category tabs, a searchable Skill list, separate Skills and plugins views, and category counts" width="100%"></td></tr></table>

<table align="center"><tr><td><img src="docs/media/agent-skill-catalog-filter.en.png" alt="Generated catalog search results for agent-skill-catalog showing the matching Skill card, preview image, and category filters" width="100%"></td></tr></table>

<table align="center"><tr><td><img src="docs/media/agent-skill-catalog-detail.en.png" alt="Generated catalog detail dialog showing the Skill summary, invocation text, source location, and evidence state" width="100%"></td></tr></table>

## Network use, and how to turn it off

A default build is **not** guaranteed offline. Here is exactly what can touch
the network and the switch that disables each one:

| What happens | When | Switch that disables it |
|---|---|---|
| Skill names from your library are sent to the GitHub repository search API as `"<name>" in:name` queries, to find candidate repositories for entries that have no repository metadata yet. | Default build | `--no-github-discovery` |
| For observed repositories, one public preview image is fetched from allowlisted GitHub hosts and cached in the output directory. | Default build | `--no-github-images` |
| Public GitHub README excerpts are fetched as evidence for the Chinese description queue. | `description_queue.py next` | `--no-github-readmes` |

GitHub reads are HTTPS-only, host-allowlisted, and size-limited. If a `GH_TOKEN`
or `GITHUB_TOKEN` environment variable is set, or you are already signed in with
the GitHub CLI, that existing credential is reused for these reads; the catalog
never stores it. A build with `--no-github-discovery --no-github-images` (and
`description_queue.py next --no-github-readmes` when you run the queue) makes no
GitHub request at all.

## Safety and responsible use

- Scan roots are explicit and read-only; the builder does not traverse unrelated folders.
- The local server has an optional delete capability, disabled unless you set `allow_delete` to `true` for a root. When enabled, it can permanently remove a top-level standalone Skill directory from the scanned source after you confirm the full Skill name. Family and plugin entries are excluded, and it does not delete root configuration. Keep it off if you want a strictly read-only browsing setup.
- Skill-provided remote image URLs remain metadata only. For an observed GitHub repository, the builder may read the public repository page and allowlisted GitHub image hosts to cache one size-limited, signature-checked preview.
- Manual preview images are written only to `curated-images/` and `catalog-curation.json` inside the selected output directory.
- Absolute paths are redacted by default. `--include-absolute-paths` is an intentional local diagnostic option.
- Refresh accepts only the roots, labels, kinds, config, and curation files that were recorded at startup.
- Category, family, image, and GitHub claims remain evidence-backed; uncertain records stay marked for review.

See the full [Disclaimer](DISCLAIMER.md) and [Security](SECURITY.md) notes before using the catalog with private or third-party Skill repositories.

## Repository layout

```text
skills/agent-skill-catalog/SKILL.md GitHub-discoverable Skill entry
skills/agent-skill-catalog/       versioned installable Skill package
skills/agent-skill-catalog/references config, schemas, curation, and workflow
skills/agent-skill-catalog/scripts  scanner, HTML renderer, and bounded server
docs/                              project site, guides, and generated demo
docs/media/                        README screenshots and product animation
tests/                             deterministic behavior checks
tools/                             package and release validation
.github/                           CI, issue, and pull-request templates
CHANGELOG.md                       release history
```

## Status

- Current published release: [`v0.3.6`](https://github.com/mianbaofang/agent-skill-catalog/releases/tag/v0.3.6)
- Installable package: [`agent-skill-catalog-skill.zip`](https://github.com/mianbaofang/agent-skill-catalog/releases/latest/download/agent-skill-catalog-skill.zip)
- Package checksum: [`agent-skill-catalog-skill.zip.sha256`](https://github.com/mianbaofang/agent-skill-catalog/releases/latest/download/agent-skill-catalog-skill.zip.sha256)
- Validation: GitHub Skill discovery, package structure, Python compilation, deterministic catalog tests, and release packaging run in CI and before release.

See the [Changelog](CHANGELOG.md) for version history.

## Acknowledgements

The project follows the public [Agent Skills specification](https://agentskills.io/specification) and uses Python's standard library for scanning, deterministic JSON generation, and the local HTTP server. The demo animation combines original explanatory information graphics with a real catalog UI recording. The public demo and screenshots use synthetic fixtures created for this project and placed under `examples/`; they are not part of the installable Skill package. Your own installed Skills, private prompts, and private assets are never bundled.

See [Acknowledgements](ACKNOWLEDGEMENTS.md) for the attribution and non-affiliation boundary.

## Author

Ethan <ethan.zl@hotmail.com>

## License

MIT.
