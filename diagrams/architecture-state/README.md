# State Diagram: Visual & Technical Views

## Why two versions?
- **Visual (presentation):** Uses color and simplified transitions to communicate the explanation lifecycle at a glance.
- **Technical (engineering):** Shows explicit states, transitions, timestamps, and retry logic for software analysis and debugging.

## Why a state diagram?
State diagrams clarify the lifecycle of explanations, including error handling and delivery. They help ensure robust queue management and reliable delivery in the system.

## How state architecture supports reliability & scalability
- **Reliability:** Explicit error and retry states prevent lost explanations and support recovery from failures.
- **Scalability:** Well-defined state transitions allow for parallel processing and future extension of the explanation pipeline.

## Render instructions
To render either version:
```zsh
./scripts/render-diagram.sh diagrams/architecture-state/visual/state-visual.mermaid
./scripts/render-diagram.sh diagrams/architecture-state/technical/state-technical.mermaid
```
Artifacts should be moved into their respective subdirectories for organization and archiving.
