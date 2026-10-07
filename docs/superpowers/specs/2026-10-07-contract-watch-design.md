# API Contract Watch design

Approved purpose: a portfolio-ready CLI that catches API contract regressions before release.
Python 3.10+ standard library; local OpenAPI 3.0.x JSON inputs only, no network or paid service.
Pipeline: strict JSON loading → basic structural validation → effective operation/parameter maps → directional compatibility rules → text/JSON output.
Detect removed paths/methods, newly required parameters (including inherited path parameters), removed parameters, changed primitive types, narrowed enums, and newly required request bodies. Operation parameter definitions override path definitions by (name, in).
Unclassified semantic changes produce review findings rather than a green result. References are explicitly unsupported and yield review. Metadata-only edits do not count. This is not a full OpenAPI validator or complete compatibility proof.
Exit 0: no findings within scope; 1: breaking findings; 2: manual review required or invalid input (review wins over breaking). Deterministic JSON findings include code, location, severity, message.
Tests cover core rules, inheritance/overrides, invalid input, references, non-mutating comparison and real CLI exit codes. Examples and GitHub Actions demonstrate pass/fail. Publish feature branch and PR, without merging.
