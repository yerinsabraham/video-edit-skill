# Releasing

1. Update `VERSION`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
   and `CHANGELOG.md`.
2. Run the checks in CONTRIBUTING.md and an end-to-end edit on real clips.
3. Check nothing generated is tracked: `git status --short` and `git ls-files`.
4. Tag and push: `git tag vX.Y.Z && git push origin main vX.Y.Z`.
5. Create the GitHub release from the tag with the CHANGELOG entry and the
   install snippet.
