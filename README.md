English · [Español](README.es.md) · [Technical architecture](docs/ARCHITECTURE.md)

# Trust Fracture

When an AI agent reads external content and can invoke privileged operations, an investigator needs to know where that content could influence the system, what actually ran, and which policy applies.

Trust Fracture is a CLI for investigating those questions. Give it a description of the system and the trace observations you have. It stores agents, tools, sources, operations, permissions, and policies in a Relate graph. You can inspect a bounded route, check the actor's authority, and produce a sealed finding that records the evidence and its limitations.

**Under construction.** The graph, investigation CLI, and sealed findings are usable today. The scenario corpus includes six negative controls. The broader corpus, control analysis, and visual interface are planned work. [Build roadmap](docs/LEVELS.md)

## What a finding says

| Result | Evidence the engine found |
| --- | --- |
| `POTENTIAL_PATH` | A structural route with incomplete or absent trace backing. |
| `OBSERVED_FLOW` | Trace events back every link in a route. |
| `VERIFIED_POLICY_VIOLATION` | An observed route meets the engine's modeled conditions for an authority gap on a policy-governed operation. |
| `INSUFFICIENT_EVIDENCE` | The bounded search returned no route to assess. |

The rules run without a language model. The JSON finding includes the selected route, supporting trace IDs, reasons, and limitations. An independent, standard-library-only verifier checks the SHA-256 digest of the canonical payload. The digest covers payload integrity, while trace provenance depends on the source records. [Evidence model](docs/EPISTEMIC_MODEL.md)

## Try the CLI

From the repository root, use Python 3.12 or later in a virtual environment. This example loads the synthetic catalog fixture into a fresh temporary database and seals a route with no recorded execution.

```bash
python -m pip install -e '.[dev]'
workdir=$(mktemp -d)
trust-fracture load tests/fixtures/negative_controls.json --database "$workdir/catalog.rl"

trust-fracture seal-finding --database "$workdir/catalog.rl" \
  --source structural-only-source --target structural-only-target \
  --actor structural-only-actor --operation structural-only-operation \
  --finding-id catalog-route --out "$workdir/finding.json"

python scripts/verify_finding.py "$workdir/finding.json"
```

The CLI reports `POTENTIAL_PATH` and the verifier reports a matching digest. To run all six control cases through the CLI and verifier, use `python -m pytest -q tests/test_negative_controls.py`. [Control cases](tests/test_negative_controls.py)

## Technical documentation

- The [architecture](docs/ARCHITECTURE.md) traces the pipeline from ingestion to findings.
- The [graph model](docs/GRAPH_MODEL.md) defines node types, relationships, and their provenance.
- The [threat model](docs/THREAT_MODEL.md) defines the assumptions and trust boundaries.
- The [Relate decision record](docs/decisions/ADR-001-language-selection.md) explains the storage choice.

## License

Trust Fracture is licensed under the [Apache License 2.0](LICENSE).
