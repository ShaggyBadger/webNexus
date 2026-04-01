# Guiding Principles: webNexus

This document serves as the foundational reference for the development, design, and evolution of the **webNexus** platform. It outlines our core intentions, architectural scope, and aesthetic standards to ensure consistency and operational excellence.

---

## 1. Project Intention & Philosophy
**"Base Camp" / "Field-Built" Utility**

*   **Mobile-First Priority:** The primary device is a smartphone in the field. Every UI element must be touch-optimized, high-contrast, and legible in sunlight.
*   **Operational First:** Every feature must solve a real-world, field-level problem.
*   **Rugged Reliability:** The interface should feel robust and dependable.
*   **Tactical Aesthetic:** High-contrast "Command Console" vibe using deep blacks, charcoals, and tactical accents.

## 2. Scope & Roadmap
The current scope is focused on consolidating field data into a single, reliable command center.

*   **Phase 1 (Current):** Centralizing the TankGauge application. Migrating legacy data and refining fuel estimation logic.
*   **Phase 2 (Future):** Expanding into broader asset management and field reporting modules, only as operational needs dictate.

## 3. Design & Styling Conventions
Consistency is managed through a centralized **Theme Engine** in `context_processors.py`.

### A. Color Palette (Tactical Standard)
*   **Backgrounds:** Deep charcoal (`#121417`) and dark grays (`#1c1f23`).
*   **Primary Action:** Tactical Blue (`#4092ff`).
*   **Accents:** Warning/Highlight Pink-Red (`#e94560`) and "Caution" Orange.
*   **Typography:** High-legibility light grays (`#f8f9fa`) for readability in various lighting conditions.

### B. Typography
*   **Primary Font:** `JetBrains Mono` (Monospaced) for all operational data, headers, and UI elements to ensure maximum character distinction and a "console" feel.
*   **Secondary Font:** `Inter` (Sans-Serif) as a fallback for standard body text if needed.

### C. Components
*   **Cards:** Use `tactical-card` classes with large touch targets and high-contrast indicators.
*   **Buttons:** Standardized primary buttons with clear, action-oriented labels (e.g., "INITIALIZE SESSION").
*   **Iconography:** Font Awesome 6 (Solid) for symbols that represent physical tools (gauges, shields, microchips).

## 4. Engineering Standards
*   **DRY (Don't Repeat Yourself):** Use global context processors and custom template filters to manage shared logic.
*   **Surgical Edits:** When modifying code, prioritize minimal, targeted changes that align with existing project conventions.
*   **Environment-Driven:** All sensitive configurations (DB credentials, secrets) MUST stay in environment variables.
*   **Documentation:** Maintain `GEMINI.md` for project status and `GUIDING_PRINCIPLES.md` for the vision.
