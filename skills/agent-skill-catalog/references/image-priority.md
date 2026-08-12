# Image Priority

Image selection is deterministic and evidence-aware. GitHub preview collection is enabled by default and writes only to the selected catalog output cache; it never writes to scanned Skill roots.

1. **Manual override**: a local image selected from the catalog detail panel is copied into the chosen output directory and recorded in its `catalog-curation.json`. It is `curated-local` and always wins.
2. **GitHub repository image**: when a local GitHub repository URL exists, inspect its public repository page for a supported GitHub-hosted README image. Cache the verified result in `github-image-cache/` under the output directory. If no README image can be used, fall back to GitHub's repository social-preview image. These are `github-repository` or `github-social-preview`.
3. **Explicit frontmatter**: `preview_image`, `image`, `cover`, or `preview` on the skill's `SKILL.md`. A local path is `verified-local` only when the file exists. A URL remains metadata-only when remote metadata is allowed by config.
4. **Local sidecar**: the configured `sidecar_names` next to `SKILL.md` or under its `assets/` directory. Existing files are `verified-local`.
5. **Configured category cover**: used only when `category_cover_fallback` is enabled and the category has an explicit cover value. It is labeled `category-cover`; it is not evidence about the skill itself.
6. **No image**: generate a text-only catalog cover with `generated-fallback` and `missing_evidence: true`.

Only `github.com`, GitHub raw/user-image hosts, and `opengraph.githubassets.com` are allowed for automatic collection. Downloads are size-limited, image-signature checked, cached for seven days by default, and can be disabled with `--no-github-images`. Do not promote a category cover to a Skill preview, do not claim remote URL reachability from a string alone, and do not infer an image from a filename that does not exist. Reviewers should be able to tell whether an image describes the Skill, the repository, the category, or nothing.
