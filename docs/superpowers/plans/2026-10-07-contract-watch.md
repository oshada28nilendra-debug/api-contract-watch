# API Contract Watch Implementation Plan

**Goal:** Build and publish the approved CLI MVP.
**Architecture:** Pure comparison engine plus filesystem/CLI adapter. Conservative review findings for changes outside the rule set.
**Tech Stack:** Python 3.10+, unittest, GitHub Actions.
**Spec:** docs/superpowers/specs/2026-10-07-contract-watch-design.md

## Global Constraints
- Local JSON, OpenAPI 3.0.x, no runtime dependencies or network.
- Existing repository and approved feature branch/PR only.
- Approval and native unattended execution are supplied by the scheduled request.

## Review Focus
Malformed input must not produce success; inherited overrides must work; unsupported semantics must not be silently green; CLI codes must be real process codes; no source mutation.

## Task 1: Engine and CLI
- [x] Write tests in tests/test_watch.py for compare(old,new), load(path), CLI text/JSON and exit 0/1/2.
- [x] Run python -m unittest discover -s tests -v; establish missing implementation failure.
- [x] Implement api_contract_watch/core.py returning sorted finding dictionaries and api_contract_watch/__main__.py.
- [x] Run full suite and fix failures.

## Task 2: Delivery
- [x] Add examples, README, pyproject.toml, CI and docs/project-status.md.
- [x] Exercise sample pass/break CLI, installation and malformed-input behavior.
- [x] Review branch, push via GitHub, open PR, record resulting links.
