# Image Priority

Image selection is deterministic and evidence-aware. The generator does not download, probe, or synthesize images.

1. **Explicit frontmatter**: `preview_image`, `image`, `cover`, or `preview` on the skill's `SKILL.md`. A local path is `verified-local` only when the file exists. A URL is `metadata-only` when remote metadata is allowed by config.
2. **Local sidecar**: the configured `sidecar_names` next to `SKILL.md` or under its `assets/` directory. Existing files are `verified-local`.
3. **Configured category cover**: used only when `category_cover_fallback` is enabled and the category has an explicit cover value. It is labeled `category-cover`; it is not evidence about the skill itself.
4. **No image**: return `status: "missing"`, `source: "none"`, and `missing_evidence: true`.

Do not promote a category cover to a skill preview, do not claim remote URL reachability from a string alone, and do not infer an image from a filename that does not exist. Reviewers should be able to tell whether an image describes the skill, the category, or nothing.
