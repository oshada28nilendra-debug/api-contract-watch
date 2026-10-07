# API Contract Watch

Catch API contract regressions before releasing a new server version.
Compare a baseline OpenAPI document with a candidate and get readable findings,
JSON output, and exit codes suitable for CI. Built as a focused software-engineering
portfolio project; no AI, hosted service, credentials, or runtime dependencies required.

## Try it in one minute

Python 3.10 or later. Clone this repository and run from its root:

```sh
python -m api_contract_watch examples/baseline.json examples/compatible.json
python -m api_contract_watch examples/baseline.json examples/breaking.json
python -m api_contract_watch examples/baseline.json examples/review.json --format json
python -m unittest discover -s tests -v
```

The breaking example intentionally exits **1** and reports:

```text
API Contract Watch: BREAKING
[BREAKING] operation-removed | GET /health | Existing operation is no longer available.
[BREAKING] parameter-required | GET /pets / query:limit | New API requires a previously optional or absent parameter.
```

Optional installation in a virtual environment:

```sh
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install .
api-contract-watch examples/baseline.json examples/compatible.json --format json
```

Installation uses setuptools as a build dependency; running the module directly
needs only Python. No package has been published to PyPI.

## CI contract

| Exit | Meaning | Recommended action |
|---|---|---|
| 0 | No findings within the implemented scope | Continue other validation and tests |
| 1 | Breaking change detected | Restore compatibility or explicitly plan a versioned migration |
| 2 | Review required, unsupported input, or input error | Inspect findings; do not automatically pass |

Review takes precedence if both review and breaking findings exist. JSON reports
have `status`, `findings`, and either `scope` or `error`. Each finding has `code`,
`location`, `message`, and `severity`. Output order is deterministic.

The included workflow runs the tests and demonstrates all three outcomes. For your
own API, keep an approved baseline in source control and run:

```sh
python -m api_contract_watch contracts/baseline.json contracts/candidate.json
```

A nonzero exit fails a normal CI step. Do not use `continue-on-error` for this gate.
The example workflow expects the *demonstration* breaking fixture to fail; it is
not a gate against an external API.

## Rules and compatibility policy

Checks assume existing clients call the new server:

- Removed paths or HTTP methods → breaking.
- New required parameters or optional parameters becoming required → breaking.
- Path-level parameters are inherited; operation-level definitions override by `(name, in)`.
- Removed parameters → conservatively breaking (some servers may still accept them).
- Parameter schema type changes → conservatively breaking; numeric widening is not inferred.
- Narrowed parameter enums → breaking; wider enums are allowed.
- A newly required request body → breaking (body shape changes also request review).
- Other changes to existing operation, parameter, path or root semantics → manual review.
- Additional operations and optional parameters are allowed.

## Deliberate MVP limits

**Input is OpenAPI 3.0.x in JSON only.** YAML, Swagger 2, and OpenAPI 3.1/3.2 are
not supported. Convert YAML to JSON externally first if needed. This does basic
structural validation, not complete OpenAPI validation; validate specifications
with a full validator separately. Invalid documents may still pass that limited
validation. Inputs are treated as local data and never executed or fetched. Duplicate JSON keys,
nonfinite numbers, and integers over 4,300 digits are rejected.

`$ref` anywhere produces a review finding; references are not resolved, including
local component references. This conservative approach can flag references inside
examples. Deep response/request schema compatibility, composition, security
compatibility, runtime behavior, and client code generation are not inferred.
Changed response content, security, servers, components, extensions, and most
unclassified fields request review; this can produce false positives. Documentation
fields are ignored only in selected contexts, so nested documentation edits may
also request review. Header names and path template names are compared literally.

**PASS is not proof of full API compatibility**, even for unchanged contracts.
There is no web dashboard, automatic baseline update, deployment, or benchmark
claim. This is an educational implementation, not a novel research result or a
replacement for mature OpenAPI diff tools.

## Architecture and learning value

`core.py` loads strict JSON and validates basic structure, builds effective
operation/parameter maps, then applies directional rules without mutating inputs.
`__main__.py` handles arguments, formatting, and process exit status.
Tests exercise the actual CLI in subprocesses as well as pure engine functions.

Interview explanation: “I built a CI tool that compares API promises across
versions. The challenging part was separating changes that reject existing client
requests from additive changes, applying inherited parameter overrides, and
refusing to silently pass cases the tool cannot analyze.”

Design reference: [OpenAPI 3.0.3 specification](https://spec.openapis.org/oas/v3.0.3.html),
especially Path Item, Operation, Parameter and Request Body objects.
See `docs/project-status.md` for delivery state and the approval queue.
