# Themes for architecture-flowchart

This directory holds theme variants and metadata for the `architecture-flowchart` diagram.

Files here:

- `meta-light.yaml` — metadata sidecar for the light-theme render.
- `meta-dark.yaml` — metadata sidecar for the dark-theme render.

Naming conventions for rendered files (placed in the parent diagram folder or this folder):

- `architecture-flowchart-light.svg` / `architecture-flowchart-light.png`
- `architecture-flowchart-dark.svg` / `architecture-flowchart-dark.png`

Recommended workflow:

1. Generate both theme variants with the project render script (e.g. `./scripts/render-diagram.sh`), passing any theme-specific init blocks in the mermaid source or by post-processing.
2. Place the `*-light.*` and `*-dark.*` files into this folder or the parent diagram folder for consistency.
3. Update the corresponding `meta-*.yaml` file with the actual `mermaid-cli` version and commit SHA after generation.

Notes:
- The `meta-*.yaml` files are intentionally lightweight and human-editable.
- If you add automation (CI job), update its output path to include these variants.
