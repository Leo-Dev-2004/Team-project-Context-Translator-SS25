# Data Pipeline Diagram: AI Processing Flow

## Rationale

This diagram models the end-to-end AI processing pipeline in the Context Translator, showing all major components, queue files, atomic write steps, caching, and fallback logic. The technical version details every process and data flow for engineering and reliability review. The visual version is optimized for presentations, with color and simplified flow.

## Diagram Versions

- **Technical:** Full process, queue, and atomic write details. Use for backend design, reliability, and integration.
- **Visual:** Simplified flow, color-coded for clarity, suitable for onboarding and presentations.

## How This Pipeline Supports the Architecture

- Ensures reliable, decoupled processing via file-based queues and atomic writes.
- Reduces redundant LLM calls with caching.
- Supports fallback logic for robust term detection.
- Enables real-time delivery via WebSocket and frontend integration.

## Render Instructions

To render the diagrams:

```sh
npx -y @mermaid-js/mermaid-cli -i technical/data-pipeline-technical.mermaid -o technical/data-pipeline-technical.svg
npx -y @mermaid-js/mermaid-cli -i visual/data-pipeline-visual.mermaid -o visual/data-pipeline-visual.svg
```

For PNG conversion:

```sh
rsvg-convert technical/data-pipeline-technical.svg -o technical/data-pipeline-technical.png
rsvg-convert visual/data-pipeline-visual.svg -o visual/data-pipeline-visual.png
```

## References

- See `CONTEXT.md` for pipeline logic and reliability rationale.
- See backend code for atomic write and fallback logic.
