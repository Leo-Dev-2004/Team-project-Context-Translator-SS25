# UX Journey Diagram: User Flow & Notifications

## Rationale

This diagram visualizes the end-to-end user experience in the Context Translator, mapping all key actions, UI interactions, and notification feedback. It references both the backend logic and frontend UI microcopy, including German labels for presentation clarity. The technical version details every step and feedback event for engineering and QA. The visual version is optimized for onboarding and presentations, with color and simplified states.

## Diagram Versions

- **Technical:** Full user flow, UI actions, and notification events. Use for QA, UI/UX review, and feature validation.
- **Visual:** Simplified states, color-coded for clarity, German microcopy for user-facing communication.

## How This Journey Supports the Architecture

- Ensures all user actions are mapped to backend events and frontend feedback.
- Supports accessibility and localization by including German microcopy.
- Provides a clear reference for onboarding, documentation, and feature completeness.

## Render Instructions

To render the diagrams:

```sh
npx -y @mermaid-js/mermaid-cli -i technical/ux-journey-technical.mermaid -o technical/ux-journey-technical.svg
npx -y @mermaid-js/mermaid-cli -i visual/ux-journey-visual.mermaid -o visual/ux-journey-visual.svg
```

For PNG conversion:

```sh
rsvg-convert technical/ux-journey-technical.svg -o technical/ux-journey-technical.png
rsvg-convert visual/ux-journey-visual.svg -o visual/ux-journey-visual.png
```

## References

- See `CONTEXT.md` for backend logic and user flow.
- See frontend UI code for microcopy and notification logic.
