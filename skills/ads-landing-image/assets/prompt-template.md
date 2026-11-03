# Prompt Template (STEP 2 output)

Fill every `[...]`. Remove section names. Keep the English structure, put the
Arabic text inside quotation marks. Output inside ONE code block.

```
Act as a world-class Mobile E-commerce Designer. Generate a long vertical infographic landing page (aspect ratio 9:24) for the product in the uploaded images.

UPLOADED PHOTOS (identify each by its content, not by upload order):
- PHOTO A: [precise description: what, color, angle, model or not]
- PHOTO B: [...]

PRODUCT FIDELITY RULES (HIGHEST PRIORITY):
1. These are real product photos. Use them EXACTLY as they are. DO NOT redraw, recolor or regenerate [the product / packaging / model].
2. [Critical visual facts that must never change: base color, print, shape, variant colors]
3. [Product-only photos]: remove the background and use them as clean floating cut-outs.
4. [Model photos]: you may ONLY replace the background with [scene matching real usage]. Keep the model, pose and product unchanged.
5. Any close-up crop must come from the same photo it is shown next to.
6. Use ALL uploaded photos.
[7. Infographic photo: extract ONLY the product. Ignore all text, icons, circles, lines and other people.]
[8. Before/after: the SAME person / object from the SAME angle on both sides.]

CRITICAL TEXT RULES:
1. ONLY render the exact Arabic text inside quotation marks " ", right-to-left, correctly connected.
2. ABSOLUTELY DO NOT render any English words or labels[, except the printing on the product packaging].
3. Mobile readability: headlines at least 1/12 of the page width in height, body text at least 1/22, including captions under images and steps.
4. Render each line exactly as written, keep the given line breaks, never duplicate any word, never break a line in the middle of a phrase.
5. Text must NEVER overlap faces or the product.

SEAMLESS BACKGROUND RULES (VERY IMPORTANT):
1. The whole page is ONE single continuous canvas with ONE background flowing from top to bottom.
2. ABSOLUTELY NO boxes, cards, panels, frames, borders, color blocks, curved bands, wave shapes, or solid footer blocks. This also applies to steps, icons, comparisons and price badges.
3. One long smooth vertical gradient: [color 1] at the top → [color 2] → [color 3] → [deep color 4] at the very bottom. All transitions extremely gradual and invisible.
4. Connect everything with [one motif matching the product] across the whole page.
5. Sections are separated only by generous empty space.

AESTHETIC: [3-5 mood adjectives matching the angle]. [Accent color] accents. Feature the product repeatedly.

* Visual Flow: [HERO scene: result + product, text at the top in empty space]
* Top Badge (Yellow Text): "[...]"
* Main Headline line 1 (HUGE BOLD [color]): "[...]"
* Main Headline line 2 (HUGE BOLD [color]): "[...]"
* Subhead (Large Dark Text): "[...]"
* Stars (Gold): "★★★★★"
* Mini Quote (Large Dark Text): "[...]"
* Trust (Large Green Text): "📦 حلّ الكولي وشوف سلعتك قبل ما تخلص"

[... 4 to 6 middle sections from section-library.md, same style: one Visual Flow line, then one line per text element with (Style) and "Arabic text" ...]

* Visual Flow: Bottom of the canvas where the gradient is deepest (no block, no band). [Product/model] glowing on one side, text on the other side.
* [Urgency with real reason, optional] (Large White Bold): "[...]"
* Trust line 1 (Large White Bold): "📦 حلّ الكولي وشوف سلعتك قبل ما تخلص"
* Trust line 2 (Large White Bold): "🔄 ضمان 36 ساعة: إذا ما عجبكش، نردولك دراهمك"
* Arrow (HUGE BOLD Yellow): "⬇️ املأ الاستمارة تحت واختار عرضك"
```

## Notes After the Code Block (Arabic, max 5 bullets)

- Which photos to upload in Gemini Pro with the prompt (order does not matter).
- Assumptions to verify (sizes format, fit, claims).
- Example reviews written by Claude, to replace with real ones.
- What was left out because it was not confirmed (price, durability, coverage).

## Fix-Up Message (after the user shows the result)

Give it in a code block, to paste in the SAME Gemini chat:

```
Keep everything exactly the same, only fix these points:
1. [specific problem + exact expected result]
2. [...]
```

Typical fixes: remove a solid band/footer block; fade an image's rectangle edges
into the background; use a specific photo exactly as uploaded without recoloring;
remove boxes and arrows around steps; enlarge small text to at least 1/22 of the
page width; remove a person that leaked from an infographic.
