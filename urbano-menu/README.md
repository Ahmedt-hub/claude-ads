# URBANO — Menu re-layout

Two edits applied to all 9 printed menu pages:

1. **Removed the heart ornament** that flanked every section title (42 glyphs across 21 titles).
2. **Added space between the menu lines** — +10 px per line, and the whole set now
   follows a single consistent rhythm instead of the original 24–51 px spread.

Every page is still **1066 × 1600 px**, matching the originals exactly, so they drop
straight back into whatever produced them.

## Deliverables — `final/`

| File | Page |
|---|---|
| `01-cover.jpg` / `.png` | Cover — MENU / Pizzeria & Cafeteria |
| `02-pizza-blanche` | Pizza Sauce Blanche |
| `03-tacos-fajitas` | Tacos + Fajitas |
| `04-pizza-tomate` | Pizza Sauce Tomate (XL / XXL) |
| `05-sandwich-burger` | Sandwich + Burger |
| `06-souflet-matlou3` | Souflet + Matlou3 |
| `07-crepe-gaufre-pancake` | Crêpe + Gaufre + Pancake + Extra |
| `08-tiramisu-cheesecake-dessert` | Tiramisu + Cheesecake + Dessert + Extra |
| `09-milkshake-jus-mojito-boissons` | Milkshake + Jus + Mojito + Boissons Chaudes |

`.jpg` is quality 97, 4:4:4 chroma, 300 dpi — for print. `.png` is lossless —
for editing. `before-after.jpg` shows the original above each updated page.
`summary.json` records the exact spacing change per page.

## What changed, page by page

| Page | Rows | Line spacing | Food photos |
|---|---|---|---|
| 1 Cover | – | unchanged | – |
| 2 Pizza Sauce Blanche | 10 | 46 → **49** | ×0.95 |
| 3 Tacos / Fajitas | 11 | 47 → **49** | ×0.96 |
| 4 Pizza Sauce Tomate | 9 | 51 → **49** | unchanged |
| 5 Sandwich / Burger | 12 | 43 → **49** | ×0.89 |
| 6 Souflet / Matlou3 | 12 | 44 → **49** | ×0.86 |
| 7 Crêpe / Gaufre / Pancake / Extra | 16 | 29 → **40** | ×0.80 |
| 8 Tiramisu / Cheesecake / Dessert / Extra | 20 | 27 → **39** | ×0.72 |
| 9 Milkshake / Jus / Mojito / Boissons | 25 | 24 → **31** | ×0.78 |

Pages 7–9 were the cramped ones (24–29 px between lines). They needed room, so the
decorative food photos on those pages were scaled down slightly — nothing overlaps
and no text was touched. Pages 2–6 gained a few px each and now sit on the same
49 px rhythm, so the whole set reads as one design.

## Notes

- Section titles, prices, Arabic subtitles, the dotted leader lines, the rules and
  the diamonds are all the **original artwork** — only their position moved.
- The dotted border frame is rebuilt from a clean template taken across all 9 pages,
  so no edge of a food photo bleeds into it.
- The cover had no list rows, so its interior is kept pixel-for-pixel.
- `page-layout.json` records the measured geometry of every page (titles, hearts,
  rules, rows, photos) — useful if further edits are needed.

## Source

`source/` holds the 9 original pages as supplied, unchanged.
