# Security

## Reporting a concern

Please do not publish credentials, private Skill contents, or an exploit in a public issue. Open a private security report through the repository's GitHub security channel when it is enabled; otherwise contact the maintainer through the public profile before disclosing sensitive details.

Include the affected version or commit, operating system, reproduction steps, expected behavior, observed behavior, and any evidence that does not contain secrets or private paths.

## Security boundary

The catalog is read-only for scanned Skills and local-first:

- Scanned roots are supplied explicitly. Scanning, image selection, and refresh never modify them. The one exception is an explicit, opt-in deletion action in the optional localhost server: it runs only when the served config marks a Skill root `allow_delete: true`, only for one top-level standalone Skill, and only after the request confirms the full Skill name. Every shipped config and example ships with deletion disabled, and the static catalog page never deletes anything. The Agent does not enable deletion unless the operator asks for it.
- Network access is opt-out, not opt-in. Unless the offline flags below are used, an optional enrichment pass may:
  - search GitHub by Skill name through `api.github.com` to recover a missing repository link, then verify candidate repositories before linking one;
  - read public GitHub repository pages and allowlisted GitHub image hosts for observed repositories;
  - read one bounded README excerpt per queue item from `raw.githubusercontent.com`.
  These reads may reuse an existing local GitHub CLI login or `GH_TOKEN`/`GITHUB_TOKEN`; no credential is written, stored, or sent anywhere except GitHub over HTTPS. Requests are host-allowlisted, timeout-bounded, and size-limited, and the catalog is not built to send your Skill contents or your catalog to any service.
- Offline mode: use `--no-github-discovery --no-github-images` for a build, and start `serve_catalog.py` with the same flags to keep every refresh offline. The description queue additionally needs `--no-github-readmes`. These flags are operator-supplied at startup; HTTP requests cannot turn network access on or supply roots, config, or curation paths. With them, these scripts make no network request and call no hidden model: the Chinese description copy is written by the invoking Agent, whose own runtime and model provider are outside this tool's boundary and may transmit local evidence.
- GitHub preview retrieval is restricted to observed GitHub repository URLs and allowlisted GitHub image hosts. Responses are size-limited, image-signature checked, and cached only in the selected output directory. Skill-provided remote image URLs remain metadata-only.
- The refresh endpoint binds to localhost and accepts only the startup root/configuration contract.
- Absolute paths are redacted by default.
- The catalog is not a sandbox, malware scanner, permission boundary, or guarantee that a discovered Skill is safe to execute.

Keep private roots out of screenshots, demo records, issue reports, and public releases.
