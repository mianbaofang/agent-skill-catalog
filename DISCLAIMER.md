# Disclaimer

Agent Skill Catalog is a local discovery and presentation tool. It reads only the roots that an operator explicitly supplies and produces a catalog for human or agent review.

- It does not install, execute, edit, upload, or clone the Skills and plugins it discovers. GitHub enrichment is optional and opt-out: unless you pass the offline flags (`--no-github-discovery --no-github-images`, plus `--no-github-readmes` for the description queue), it may search GitHub by Skill name, verify candidate repositories, read public repository pages, and cache allowlisted preview images and README excerpts only inside the selected catalog output directory. These reads may reuse an existing local GitHub CLI login or token and never store credentials.
- The optional localhost server can delete one top-level standalone Skill from a root that the operator explicitly marked `allow_delete: true`, and only after confirming the full Skill name. This capability ships disabled in every example and is never enabled without an explicit request.
- A category, family, image, GitHub link, or invocation is only as reliable as the local metadata and curation evidence available at scan time. Review low-confidence and `missing evidence` records before relying on them.
- A repository link does not imply that the referenced project is official, safe, maintained, compatible, or affiliated with this project.
- Users remain responsible for licenses, privacy, security, service terms, robots.txt, rate limits, and any actions taken after reading the catalog.
- This project is not affiliated with or endorsed by Codex, GitHub, OpenAI, Anthropic, or any listed third-party Skill, plugin, provider, or repository.

The catalog is not a security scanner and does not guarantee that a discovered Skill is harmless or suitable for a particular task.
