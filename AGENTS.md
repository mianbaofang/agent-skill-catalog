# Agent Guidance

Canonical branch: `main`. Preserve existing project structure and assets, include regression coverage for behavior changes, and update `CHANGELOG.md` for completed iterations.

## GitHub Synchronization

- Standing maintainer instruction: after completing and validating an authorized change, commit the task's source, documentation, and tests, then push to the canonical GitHub branch. Do not leave completed work only in the local working tree unless the user explicitly requests local-only work or a concrete blocker prevents synchronization.
- Fetch before committing; preserve unrelated edits and review remote divergence. Never discard work or force-push to make branches match.
- Keep generated outputs, private data, secrets, local review reports, and release scratch files out of commits. Stage explicit task paths rather than blindly adding the entire working tree.
- Verify the remote branch SHA matches the local commit after pushing. Report the branch, commit, and any remaining unpushed work or synchronization blocker.
- Source synchronization does not itself authorize a new tag, GitHub Release, overwritten release asset, or package-registry publication. Keep unreleased behavior labeled accurately and report release-channel status separately.
