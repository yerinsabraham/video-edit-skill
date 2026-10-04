# Clean-Room Notes

The referenced open-source repository is useful as a product reference, but
this package should not copy its implementation.

## Allowed

- Use the general idea of an agent-driven reel editor.
- Compare feature categories: ingest, transcript, EDL, assembly, captions,
  overlays, QA, revision.
- Build original scripts and docs.

## Not Allowed

- Copy unlicensed code.
- Copy prose from another `SKILL.md`.
- Copy look values, templates, or internal implementation details.
- Preserve another repo's branding.

## Authorship

Package and future commit metadata should use:

- Author: Yerins Abraham
- Email: `yerinssaibs@gmail.com`

Do not add generated co-author lines, generated-with footers, assistant
identity metadata, or AI contributor entries.

Before any future publish session, check for stray agent refs:

```bash
git for-each-ref --format='%(refname)' \
  | grep -v '^refs/heads/\|^refs/remotes/\|^refs/tags/'
```

Delete any unexpected internal refs before pushing.
