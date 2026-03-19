# Design System Document

## 1. Overview & Creative North Star
The Creative North Star for this design system is **"The Neon Manuscript."** 

This system bridges the gap between the high-octane energy of Cyberpunk aesthetics and the focused, immersive environment required for literary creation. It moves beyond the typical "gaming dashboard" by adopting a sophisticated editorial layout that treats AI insights as living, glowing annotations. We break the rigid, boxy nature of standard SaaS platforms through intentional asymmetry and a "Void-First" philosophy—where the deep black background isn't just a container, but an expansive stage for high-contrast typography and radiant UI "implants."

## 2. Colors
Our palette is rooted in absolute depth and high-voltage accents. We use color not just for decoration, but as a functional signal for AI-augmented states.

### Core Tones
*   **Background (The Void):** `#000000` (Direct use for base layer).
*   **Primary (Neon Pulse):** `#FACC15` (Primary Container). Used for active writing states and critical CTA paths.
*   **Secondary (Electric Vitality):** `#4ADE80` (Secondary). Reserved for progress tracking, AI-validated text, and "Success" states.
*   **Surface:** `#0f1419` to `#30353b`.

### The "No-Line" Rule
Traditional 1px borders are strictly prohibited for structural sectioning. Information architecture must be defined through:
*   **Tonal Shifts:** Placing a `surface-container-low` (`#171c22`) card on top of the `background` (`#000000`).
*   **Negative Space:** Utilizing the Spacing Scale (e.g., `spacing-12`) to create a cognitive break between the manuscript and the sidebar.

### Glassmorphism & Signature Textures
Floating panels (such as AI suggestion bubbles or floating toolbars) must use a **Glassmorphism** effect. Combine `surface-variant` (`#30353b`) at 60% opacity with a `backdrop-blur` of 12px. To add "soul," apply a subtle linear gradient to main buttons transitioning from `primary_fixed_dim` (`#eec200`) to `primary_container` (`#facc15`).

## 3. Typography
The system employs a dual-identity typographic approach: The "Interface" (Data/Tech) and the "Soul" (The Story).

*   **The Interface (Display & Labels):** We use **Space Grotesk** for high-impact headlines and **Inter** for functional UI labels. These fonts convey a high-tech, precise, and modular feel.
*   **The Soul (Manuscript & Titles):** We use **Noto Serif SC** for the actual writing experience. This provides the necessary readability and prestige for long-form Chinese and English content.

**Hierarchy Logic:**
*   **Display-LG (Space Grotesk):** For monumental chapter titles or AI stats. 
*   **Body-LG (Noto Serif SC):** For the primary writing experience. Optimized line-height (1.8) for maximum legibility against the dark background.
*   **Label-MD (Inter):** For metadata, tags, and small technical readouts.

## 4. Elevation & Depth
Depth in "The Neon Manuscript" is achieved through light and layering, never through heavy shadows or lines.

### The Layering Principle
We stack containers from dark to light to move "closer" to the user:
1.  **Level 0:** `background` (#000000) - The Editor workspace.
2.  **Level 1:** `surface-container-low` (#171c22) - Side navigation or inactive panels.
3.  **Level 2:** `surface-container-high` (#252a30) - Active cards or "AI insight" drawers.

### Ambient Glows
When an element needs to "float" (e.g., a modal), do not use a standard black shadow. Use an **Ambient Glow**:
*   **Color:** `primary` (#ffecb9) at 5-8% opacity.
*   **Blur:** 40px - 60px.
*   **Effect:** This mimics the way a neon sign illuminates the fog, making the UI feel like it exists in a 3D cyberpunk environment.

### The "Ghost Border" Fallback
If an element lacks sufficient contrast against its neighbor, use a **Ghost Border**: 1px width using `outline-variant` (#4d4632) at 15% opacity.

## 5. Components

### Buttons
*   **Primary:** Sharp edges (`radius-sm` / 4px). Background: `primary_container`. Text: `on_primary_container`. On hover, add a `primary` outer glow.
*   **Secondary:** Ghost style. No background. Border: `outline-variant` at 40%. Text: `secondary`.
*   **Tertiary:** Text-only with a subtle `primary` underline that expands on hover.

### Input Fields
*   **Manuscript Area:** No visible container. The text floats on the `background`.
*   **Metadata Inputs:** `surface_container_lowest` background. 4px radius. Focus state triggers a 1px `secondary` (electric green) bottom border and a subtle green glow.

### Cards
*   **Writing Stats Card:** `surface_container` background. Use `headline-sm` for the "Word Count" number in `primary`. Forbid dividers; use `spacing-4` to separate the label from the value.

### Chips (Genre/Status)
*   Compact, 2px radius. Use `surface_variant` for the background and `on_surface` for text. Active chips should use a high-contrast `secondary` background with `on_secondary` text to "pop."

### Custom Component: The "AI Pulse"
A small, glowing orb or spark (using `secondary` color) placed next to text that has been AI-generated or enhanced. It should have a soft 10px glow to distinguish "machine" from "human" input.

## 6. Do's and Don'ts

### Do
*   **Do** embrace the void. Use `#000000` for the majority of the workspace to reduce eye strain and increase "cool" factor.
*   **Do** use sharp 4px corners. It feels intentional, architectural, and "high-tech."
*   **Do** ensure Noto Serif SC is rendered with sufficient weight for Chinese characters to ensure legibility against high-contrast backgrounds.

### Don't
*   **Don't** use pure white (`#FFFFFF`) for body text. Use `on_surface` (#dee3eb) to prevent "halo" effects and visual fatigue.
*   **Don't** use rounded "pill" buttons. They are too friendly and "consumer-grade" for this aesthetic.
*   **Don't** use standard dividers. If you feel the need for a line, try a `spacing-8` gap instead. If that fails, use a 10% opacity `outline-variant` line that fades out at the edges.