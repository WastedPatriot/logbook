# Security

This is a static shelf of notes about retired machines. It does not run those machines, and it should not contain anything that would let someone else do so either.

## What belongs here

Write-ups of retired boxes. The class of issue, the impact, the lesson. No passwords, no payloads, no live boxes, and no credentials of any sort. If a note needs a secret to make sense, the note is wrong.

## Reporting a problem

A leaked secret, or a write-up that can be turned into an open redirect or a wiped source tree, wants [private vulnerability reporting](https://github.com/WastedPatriot/logbook/security/advisories/new). An ordinary issue is the right place for a broken page, and the wrong place for a key.

Anything that was actually secret gets rotated. With any luck that list stays short.

## What the build already refuses

Links in a note may be relative, or `http`, `https`, and `mailto`. A protocol-relative URL (`//somewhere`) is not a local path, however much the string would like to be one. `javascript:` and `data:` are not links either. They are rendered as text.

`scripts/build.py` deletes the output directory before it writes. It will not do that to the repository root, to anything outside the repository, or to `boxes/`, `templates/`, `scripts/`, or `.github/`.

## Dependencies

The generator is the Python standard library. Actions are pinned to a commit, Dependabot looks at them weekly, and gitleaks runs on push. None of that is a substitute for not committing the key.
