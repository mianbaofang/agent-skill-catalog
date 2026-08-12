# Security

## Reporting a concern

Please do not publish credentials, private Skill contents, or an exploit in a public issue. Open a private security report through the repository's GitHub security channel when it is enabled; otherwise contact the maintainer through the public profile before disclosing sensitive details.

Include the affected version or commit, operating system, reproduction steps, expected behavior, observed behavior, and any evidence that does not contain secrets or private paths.

## Security boundary

The catalog is designed to be read-only and local-first:

- Scanned roots are supplied explicitly and are never modified by the builder.
- GitHub preview retrieval is restricted to observed GitHub repository URLs and allowlisted GitHub image hosts. Responses are size-limited, image-signature checked, and cached only in the selected output directory. Skill-provided remote image URLs remain metadata-only.
- The refresh endpoint binds to localhost and accepts only the startup root/configuration contract.
- Absolute paths are redacted by default.
- The catalog is not a sandbox, malware scanner, permission boundary, or guarantee that a discovered Skill is safe to execute.

Keep private roots out of screenshots, demo records, issue reports, and public releases.
