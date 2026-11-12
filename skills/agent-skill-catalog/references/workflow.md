# Workflow

## Quick preview (default)

Supply roots explicitly, or a user-owned config built from the Windows/POSIX
examples. The preview command stays fully offline and does not wait for Chinese
descriptions:

```text
python scripts/build_catalog.py --root <skills-root> --output-dir <output-dir> --no-github-discovery --no-github-images
python scripts/build_catalog.py --config <config.json> --output-dir <output-dir> --no-github-discovery --no-github-images
```

Success is exit code 0 with `index.html` in the output directory. Pending
Chinese descriptions are expected in a preview; report them as pending instead of
running the description queue unless the user asked for enriched copy. Use
`--root` repeatedly for multiple roots. A root is a skill root by default;
plugin caches must be declared with `{"kind":"plugin"}` in a config file. To keep
a served preview offline as well, start `serve_catalog.py` with the same
`--no-github-discovery --no-github-images` flags; they apply to every refresh it
runs and cannot be supplied over HTTP.

## First enriched build

Only start this path when the user asked for complete Chinese descriptions. Drop
the offline flags only when the user accepts the optional GitHub reads described
below.

```text
python scripts/build_catalog.py --root <skills-root> --output-dir <output-dir> --require-complete-descriptions
python scripts/build_catalog.py --config <config.json> --output-dir <output-dir> --require-complete-descriptions
```

Without `--no-github-discovery`, the build scans every family-primary Skill that
still lacks a repository link and runs an exact-name GitHub search. The search
sends Skill names to `api.github.com` and may reuse an existing local
`GH_TOKEN`/`GITHUB_TOKEN` or GitHub CLI login without storing it. Search results
are candidates only. A candidate is associated automatically only after the
repository is active, contains a matching `SKILL.md`, agrees with the local Skill
content, and is the unique high-confidence result. Forks, archived repositories,
unverified copies, and ties remain unlinked and are reported together in
`catalog.github_discovery`.

The first build also writes `description-enrichment.json`. This is a required
Agent work queue in this mode, not a user editing task. Exit code 3 starts the
following resumable loop:

```text
python scripts/description_queue.py next --root <skills-root> --output-dir <output-dir> --batch-size 12 --no-github-readmes
# Read description-batch.json and write description-batch.responses.json.
python scripts/description_queue.py apply --output-dir <output-dir> --input <output-dir>/description-batch.responses.json
```

For a config-root build, pass the same `--config` to `next` instead of `--root`.
`--no-github-readmes` keeps the queue offline; without it, the batch includes a
cached excerpt from the observed public GitHub README. The batch contains bounded
local `SKILL.md` evidence. The invoking Agent writes factual natural Chinese
covering purpose, typical use, and important output or limits. `apply` rejects
unknown queue keys, short copy, and non-Chinese copy, then stores accepted
progress in the output-owned `catalog-curation.json`. Repeat until `next` reports
`batch_count: 0`, then rebuild with `--refresh --require-complete-descriptions`.

The Python tools coordinate evidence, validation, and resumable state; they do not
call a hidden text model or require a provider key. The invoking Agent runtime is a
separate boundary: it may send local Skill evidence to its own model provider, so
"no network request" only holds for the offline script commands shown above.
Do not edit a scanned Skill
and do not hand the queue to the user. A completed enriched build has exit code 0
and `summary.pending_description_count == 0`; a preview without that flag reports
pending items and still exits 0. If the source is genuinely insufficient, keep
missing evidence explicit instead of inventing details.

## Review

Inspect `catalog.json` before opening the page:

- `summary` and `category_coverage`
- `category_candidates`, `category_winner_margin`, `category_tie_reason`, and `low_confidence`
- `image.missing_evidence` and image status
- `description_enrichment.pending_count` and its reasons
- `families`, `plugins`, `unresolved_roots`, and `warnings`

The default output hides absolute paths. Use `--include-absolute-paths` only for a local diagnostic build.

## Refresh

`--refresh` is an explicit replacement gate. The local server must be started with the exact startup roots and curation files:

```text
python scripts/serve_catalog.py --output-dir <output-dir> --root <skills-root> --root <plugin-root> --curation <curation.json> --require-complete-descriptions
```

For an offline served catalog, add the same `--no-github-discovery --no-github-images`
flags used by the build; they apply to every refresh the server runs and are
operator-supplied at startup only, never accepted from HTTP requests.

The server binds to localhost and rejects a refresh when explicit roots are
missing or the curation count does not match the startup catalog. With
`--require-complete-descriptions`, it also refuses to report a successful refresh
while the Agent-owned queue is unfinished. In the detail panel, `选择本地图片`
picks a supported image and `保存图片` then copies it into
`<output-dir>/curated-images/`, writes the matching override
to `<output-dir>/catalog-curation.json`, and rebuilds immediately. `恢复自动图`
removes that output-owned override. Neither action writes to a scanned root.

The server also exposes an optional deletion action. It stays disabled unless the
serving config marks a Skill root `allow_delete: true`; the shipped Windows and
POSIX examples leave it off. When enabled, it removes only one top-level
standalone Skill from that root after the request confirms the full Skill name,
then refreshes. Never enable this for a served catalog unless the operator asked
for it, and never present it as a default action.

## Boundaries

Scanning is read-only for discovered Skills and never executes them. Network use
is opt-out: unless the offline flags are passed, GitHub source detection may send
Skill names to `api.github.com` and reuse an existing local `GH_TOKEN`/`GITHUB_TOKEN`
or GitHub CLI login without storing it. Source detection accepts explicit
curation, `gh skill install` lock/frontmatter metadata, nearby package or plugin
metadata, manifest values, an explicit GitHub URL in the Skill body, a local Git
remote, or a uniquely verified discovery result. When an observed or verified
GitHub repository URL is available and no usable local preview exists, the default image pass may read the public
repository page and cache one size-limited, signature-checked GitHub image in
`<output-dir>/github-image-cache/`, and the description queue may read one README
excerpt for that repository. Family and plugin aggregates select the strongest
verified member image. Use `--no-github-discovery --no-github-images` for an
offline build; the description queue additionally needs `--no-github-readmes`. Remote
image URLs found only in a Skill frontmatter remain metadata-only. No category or
family is inferred from an unverified repository or description-only ecosystem marker.

## Optional Agent-owned public research

Use `description_queue.py next --web-research` with the same roots/config/output to prepare public-introduction work, even for already complete descriptions. The Agent searches and opens exact Skill matches using its own networking tools. Responses carry `web_research: true` and per-item `sources` with URL, title, `retrieved_at` date and `identity_evidence`. `apply` validates these fields, persists them in output-owned `description_sources`, and the rebuilt detail shows clickable sources. This validates the response format, not independent web truth: the Agent must actually inspect the sources. If browsing is unavailable or no exact identity match can be verified, retain local copy and report that research item unresolved. Offline previews never enable this mode.

## Repository collections and landscape previews

Multiple standalone Skills with one observed/verified repository are grouped automatically, including differently named members and installations across scan roots. Details retain all members and invocations. Explicit manual family mappings take precedence. Plugin identities and conflicting repositories are not merged. Local actual previews win before GitHub fallback, and both cards and detail-gallery covers use 16:9 frames while preserving original media and animation.
