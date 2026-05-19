## CHANGELOG

### 2026-05-06 (add-duo)

- Updated `model_use_conditions` in `registered/synapsemod.schema.json` from a free-form string array to a constrained enum of human-readable Data Use Ontology (DUO) labels (e.g. `"General research use (GRU)"`, `"Non-commercial use only (NCU)"`).
- Updated `examples/modelcard.example.json` to use the new human-readable DUO labels instead of bare DUO codes.

### 2026-05-06 (revisions-and-examples, PR #5)

- Added `registered/hf-basic-metadata.schema.json` covering the Hugging Face basic metadata template fields (pipeline_tag, tags, language, license, etc.).
- Added `registered/modelxchange-license.schema.json` as a standalone reusable license module.
- Added `examples/modelcard.example.json` with a complete example instance.
- Added `TEMPLATE_COMPARISON.md` comparing the basic metadata template vs. the human-readable template.
- Removed `privacy_risk` property per issue #2.
- Removed `additionalProperties: false` from the Synapse extension schema to allow forward compatibility.
- Fixed `$id` references in registered schemas.

### Draft

- Mapped the reference template variables into a Draft-07 JSON Schema.
- Created reusable schemas under `registered/` as flat, Synapse-compatible modules composed with `allOf`.
- Preserved the original template variable names as flat top-level properties.
- Preserved Hugging Face template semantics by making only non-optional fields required within the relevant flat modules.
- Added per-property `default` values based on the upstream template fallbacks.
- Added small type conveniences for common cases:
  - string arrays for fields like `developers`, `language`, and `model_card_authors`
  - strings for fields like `hours_used` and `co2_emitted`
- Included example objects for the Synapse extension schema.
- Added a separate composable Synapse extension schema containing only flat Synapse-specific fields plus `model_use_conditions`, represented as a list of ontology-like labels.
- Added `modelcardminimal.schema.json` that references only the required Hugging Face modules plus the Synapse extension fields.
- Added `modules/modelxchange-modelbase.schema.json` for the shared top-level `model_id` and `model_summary` properties.
- Added a Synapse dry-run validation script and a GitHub Actions workflow for PR validation using `SYNAPSE_AUTH_TOKEN`.
