# Image Priority

Image selection is deterministic and local-first. Scanning never changes Skill roots. Original GIF/WebP bytes, including animation, are preserved.

1. **Manual override**: an image selected in the detail panel is copied into the output directory and recorded in `catalog-curation.json` (`curated-local`).
2. **Configured local override**: a valid local `curation.image_overrides` image (`curated-local`).
3. **Local frontmatter**: valid `preview_image`, `image`, `cover`, or `preview` paths (`verified-local`). Missing or remote values do not hide later local evidence.
4. **Local sidecar**: configured `sidecar_names` next to `SKILL.md` or under `assets/` (`verified-local`).
5. **Local README image**: bounded local README HTML/Markdown links to existing images inside the same Skill directory (`verified-local`, `readme:<filename>:<relative-path>`). Skip remote links, path escapes, badges, malformed URLs and oversized files. Prefer a landscape candidate within the README; use the first valid portrait if no landscape candidate is found.
6. **GitHub image fallback**: only entries without a usable local image request the observed repository's GitHub-hosted README image, then its social preview (`github-repository` / `github-social-preview`). Requests are deduplicated per repository and cached in the output. A repository image describes the repository, not necessarily each individual Skill.
7. **Metadata or category fallback**: remote frontmatter stays metadata-only; configured category covers are labeled `category-cover` and are not proof of the Skill itself.
8. **No usable image**: generate a clearly labeled text/category illustration (`generated-fallback`, `missing_evidence: true`). This is not an AI-generated screenshot or a newly generated animation.

Catalog card and detail-gallery cover frames are uniformly landscape **16:9**, with `object-fit: contain`. Portrait-only source art stays complete in the horizontal frame, without stretching or silently cropping text. The larger view shows the original. Animated images remain animated.

`image.max_embedded_bytes` applies to local and remote images. The shipped 512 KiB limit can exclude large originals; a local configuration can raise it explicitly. Skipped GIFs are never silently reduced to a static frame.

Automatic downloads allow only GitHub and supported GitHub image hosts, are size-limited and signature-checked, and may be disabled with `--no-github-images`. Local images are selected before the GitHub image worker pool runs. Source discovery is separate and uses `--no-github-discovery`. Do not infer reachability from a URL string or promote category graphics to source evidence.
