# ER Diagram: Queue File Schemas

## Rationale

This diagram models the structure and relationships of the file-based queues and cache used in the Context Translator AI pipeline. It is mapped directly from the JSON schemas and sample records in `CONTEXT.md` and the backend codebase. The technical version shows all keys, types, and relationships for engineering and data validation. The visual version is optimized for presentations, with simplified attributes and color for clarity.

## Diagram Versions

- **Technical:** Full key annotations, explicit relationships, and sample records. Use for backend design, schema validation, and integration.
- **Visual:** Simplified attributes, color-coded for entity clarity, suitable for presentations and onboarding.

## How These Schemas Support the Architecture

- **detections_queue.json**: Buffers detected terms for explanation, supporting decoupled, asynchronous processing.
- **explanations_queue.json**: Stores generated explanations, enabling reliable delivery and status tracking.
- **explanation_cache.json**: Provides fast lookup for previously explained terms, reducing redundant LLM calls and improving performance.

## Render Instructions

To render the diagrams:

```sh
npx -y @mermaid-js/mermaid-cli -i technical/er-technical.mermaid -o technical/er-technical.svg
npx -y @mermaid-js/mermaid-cli -i visual/er-visual.mermaid -o visual/er-visual.svg
```

For PNG conversion:

```sh
rsvg-convert technical/er-technical.svg -o technical/er-technical.png
rsvg-convert visual/er-visual.svg -o visual/er-visual.png
```

## References

- See `CONTEXT.md` for full schema definitions and sample records.
- See backend queue logic in `Backend/AI/SmallModel.py` and `Backend/AI/MainModel.py`.
