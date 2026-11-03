# Design Rules for Nano Banana Pro Prompts

Lessons from real tests. Each rule exists because Gemini broke it without it.

## Photos

- **Describe photos by content, never by number.** The user does not control
  upload order. Use labels PHOTO A, PHOTO B... each with a precise description:
  "PHOTO D: brunette model, hair in a bun, wearing the WHITE set with small
  LILAC-PINK flowers".
- **Use every photo at least once.** Assign each photo to the section it fits best.
- **Base copy only on what is visible.** Never invent colors or variants.
- **Infographic or text-covered photos**: instruct to extract ONLY the product and
  ignore all text, icons, circles, measurement lines and other people. Even then
  leaks happen (an elderly man reappeared in a before/after). Prefer a cropped
  clean photo: offer to crop it.
- **Nano Banana Pro is required.** The basic model redraws the product when
  given 5 photos and a full page.

## Product Fidelity Block (always include, adapt details)

1. Real product photos: use EXACTLY as they are. Do not redraw, recolor or
   regenerate the product, the packaging, the model's face and body.
2. Spell out the critical visual facts, e.g. "fabric is WHITE with small printed
   flowers, never solid", "blue stays sky blue with purple leaves, never lavender".
3. Product-only photos → background-removed floating cut-outs.
4. Model photos → may ONLY replace the background to fit the usage context
   (example: cozy bedroom for home wear). Model and product unchanged.
5. Any close-up crop comes from the same photo it sits next to.
6. Printing on the product's own packaging stays as is (even if in English).
7. Generated people/scenes are allowed, but the product inside must be identical.
8. Before/after with generated people: the SAME person in both sides.
   With objects: the SAME object from the SAME angle.

## Seamless Background Block (always include)

1. ONE continuous canvas with ONE background from top to bottom.
2. NO boxes, cards, panels, frames, borders, color blocks, curved bands, wave
   shapes or solid footer blocks. This also applies to steps, icons, comparisons
   and price badges: everything floats on the background.
3. One long smooth vertical gradient, 4 colors taken from the product palette,
   ending in a deep shade at the bottom (white text and yellow button stay readable).
4. One connecting motif across the whole page (petals, light rays, kinetic lines,
   frosted glow...) matching the product.
5. Sections separated only by generous empty space.

Known leaks to watch: a hard band under the hero, a solid colored footer block,
step images inside boxes with arrows.

## Typography Block (always include)

1. Render ONLY the Arabic text inside quotation marks, right-to-left, connected.
2. No English words or labels (exception: printing on the product itself).
3. Size: headlines at least 1/12 of the page width in height; body at least 1/22.
   Applies to captions under images and steps too.
4. Each line exactly as written, explicit line breaks, never duplicate a word,
   never break a line mid-phrase.
5. Text never overlaps faces or the product.

Copy-side support for typography:
- Give each line separately ("Headline line 1", "Headline line 2").
- Keep lines short (about 6 words). Long lines get broken badly or duplicated.
- Put sizes on their own line: label line + numbers line.

## Format

- Aspect ratio **9:24**, 6 to 8 sections. 9:32 is too long: fidelity drops and
  the user scrolls too long before the form.
- Mood line: 3 to 5 adjectives matching the angle (e.g. "feminine, soft, intimate,
  cozy home mood").
- Accent colors: from the product or its packaging. CTA-like elements: black text
  on yellow.
