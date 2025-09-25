
# Class Diagram: UniversalMessage & Related Models

## Rationale

This diagram models the core data structures that enable real-time, decoupled communication and processing in the Context Translator system. It is directly mapped from the definitions in `CONTEXT.md` and the backend codebase. The technical version shows all field types and relationships for engineering and architecture review. The visual version is optimized for presentations, with simplified labels and color for clarity.

## Diagram Versions

- **Technical:** Full type annotations, explicit relationships, and all fields. Use for backend/API design, data validation, and integration.
- **Visual:** Simplified attributes, color-coded for model clarity, suitable for presentations and onboarding.

## How These Models Support the Architecture

- **UniversalMessage** is the backbone for all inter-process and client-server communication, ensuring consistency and traceability.
- **Detection** and **Explanation** objects represent the AI pipeline's queue entries, supporting asynchronous, file-based processing and delivery.
- **ProcessingPathEntry** and **ForwardingPathEntry** enable detailed tracking and debugging of message flow.

## Render Instructions

To render the diagrams:

```sh
npx -y @mermaid-js/mermaid-cli -i technical/classes-technical.mermaid -o technical/classes-technical.svg
npx -y @mermaid-js/mermaid-cli -i visual/classes-visual.mermaid -o visual/classes-visual.svg
rsvg-convert technical/classes-technical.svg -o technical/classes-technical.png
rsvg-convert visual/classes-visual.svg -o visual/classes-visual.png
```

Artifacts should be moved into their respective subdirectories for organization and archiving.

## References

- See `CONTEXT.md` for full field definitions and architectural rationale.
- See backend models in `Backend/models/UniversalMessage.py` and queue schemas in `Backend/AI/SmallModel.py` and `Backend/AI/MainModel.py`.

## Why two versions?

- **Visual (presentation):** Uses color and simplified attributes to communicate the main data models at a glance.
- **Technical (engineering):** Shows explicit types, relationships, and methods for software analysis, validation, and implementation.

## Why a class diagram?

Class diagrams clarify the structure of data models and their relationships, supporting robust data handling and extensibility in the system.

## How class architecture supports reliability & scalability

- **Reliability:** Explicit model definitions and validation methods prevent data corruption and support error handling.
- **Scalability:** Well-defined relationships and extensible models allow for future features and integration with other systems.
