# Hand-Drawn Diagram Prompts (OpenAI image2)

Style inspiration: Ben Thompson (Stratechery) - iPad + Paper app aesthetic. Simple hand-drawn boxes, arrows, and labels. Not polished, not sketch-note busy. Just clear thinking drawn quickly.

---

## Diagram 1: Architecture Flow

**Prompt:**
```
A simple hand-drawn architecture diagram on a cream/off-white paper background. Four boxes connected by arrows from left to right: "Slack" → "FastAPI" → "Claude Agent" → "Deepline API (441 tools)". Hand-drawn style with slightly wobbly lines, blue ink pen aesthetic. No gradients, no shadows. Simple labels in neat handwriting. The Claude Agent box has a small robot doodle. The Deepline box has "441+" written small above it. Minimal, not busy. Think quick whiteboard sketch, not polished infographic.
```

---

## Diagram 2: What We Built vs What We Should Have Built

**Prompt:**
```
A hand-drawn comparison diagram on cream paper. Two columns side by side. Left column labeled "What we built" with red X, showing a tall stack of boxes: "Custom Slack Bot (400 LOC)" → "Markdown Converter (150 LOC)" → "Stream Handler (200 LOC)" → "Agent Logic (300 LOC)". Right column labeled "What we should have built" with green checkmark, showing shorter stack: "Vercel AI SDK (npm install)" → "Thin Slack Adapter (50 LOC)" → "Agent Logic (300 LOC)". Hand-drawn arrows connecting each box. Wobbly lines, blue pen style, simple labels. A big arrow between columns with "vs" written on it.
```

---

## Diagram 3: Pain Distribution (80/20)

**Prompt:**
```
A hand-drawn horizontal bar chart on cream paper showing effort distribution. One long bar split into two sections. The larger section (labeled "80%") is shaded with red diagonal hatching and labeled "Slack Integration" with small annotations: "formatting bugs, reconnection, dedup, tables". The smaller section (labeled "20%") is shaded with green diagonal hatching and labeled "Agent Logic" with annotation: "this part worked". Hand-drawn style with pen strokes visible. Below the bar, a handwritten note: "The chat layer was 80% of the bugs." Simple, not cluttered.
```

---

## Style Notes for OpenAI image2

- Use "hand-drawn", "pen sketch", "whiteboard style", "wobbly lines"
- Specify "cream paper background" or "off-white paper texture"
- Avoid: "professional", "polished", "infographic", "clean lines"
- Keep text labels short (AI handles short text better)
- Request "blue ink pen" or "black marker" aesthetic
- Mention "not busy", "minimal", "quick sketch" to avoid over-rendering

## Alternative: Excalidraw

If AI-generated images don't work well, use [Excalidraw](https://excalidraw.com) to create these manually:
- Enable "hand-drawn" style in settings
- Use the arrow tool for connections
- Keep it rough - perfection looks worse than imperfection
- Export as PNG with transparent or white background

Ben Thompson's approach: "iPads and the ability to edit endlessly" - iterate until the diagram communicates the idea simply.
