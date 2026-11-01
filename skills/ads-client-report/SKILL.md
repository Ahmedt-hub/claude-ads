---
name: ads-client-report
description: "End-of-campaign client report for a Meta (Facebook/Instagram) campaign, in Arabic, branded for the agency (Napster Digital Services). Pulls the campaign data from the Meta Ads MCP tools and produces a multi-page A4 PDF plus a 1080x1350 PNG summary card for WhatsApp/Messenger. Use when the user says client report, campaign report, تقرير, تقرير الحملة, تقرير العميل, or gives a campaign name and asks for its report."
user-invokable: false
---

# Client Campaign Report (تقرير الحملة للعميل)

Generates the report the agency sends to a client when a campaign ends.
Renderer: `scripts/client_report.py`. Agency config (logo, colors, contacts,
DZD packages): `skills/ads-client-report/assets/agency.json`. Example input:
`skills/ads-client-report/sample-data.json`.

## Hard rules (set by the agency owner)

1. Audience is the **client**. Language: **Arabic**. Every KPI gets a plain-language explanation (built into the renderer).
2. **Never show any USD amount.** Do not put `amount_spent` in the data file.
3. Cost per result = **package price (DZD) / results**, never from Ads Manager spend.
4. Show only the package the client bought (tier + days + DZD price), never Meta spend.
5. Video metrics only when the ad is a video. Image ads: `is_video: false`.
6. "Best ad" only when the campaign has **more than one** ad (renderer enforces it).
7. Previous-campaign comparison only if the client had an earlier campaign.
8. Package numbers (e.g. 3K / 6K) = **estimated reach range** (people). The reach
   badge appears only if actual reach ≥ the minimum; otherwise the renderer
   returns a warning: tell the agency owner privately, never the client.
9. Do not ask about sales; clients usually don't share them.
10. Visual style: agency blue as the base (backgrounds, numbers, headings) with only a
    little colour as accents: a thin coloured top line on the main KPI cards, the best day
    (green) and peak hours (orange) in charts, 🟢/🟡/🔴 rating badges, ✅/⚠️ in the
    comparison. Emojis on every section and KPI.

## Workflow

### Step 1: Ask the owner (before building), in one message
1. Which package did the client buy? (tier: ابتدائية / متوسطة / متقدمة + days)
2. Did the client give any feedback? (e.g. "no sales", "nobody engaged with the video")
3. Did the agency make the video/design for the client?
4. (Only if the campaign had real Instagram reach and the API can't return it) Instagram profile visits.
   - **Yes:** creative critique stays constructive ("next version we will…").
   - **No:** creative advice can be direct ("we recommend you film…").

### Step 2: Find the campaign
- `ads_get_ad_accounts`, then search campaigns by name in the accounts with
  `ads_get_ad_entities` (`level=campaign`, filter `name CONTAIN <name>`).
  Client campaigns usually live in **Napster 2** (`961156000042075`).
- Use the campaign's own run dates as the time range (`time_range`).
- Determine the objective → `objective`: `messages` | `engagement` | `profile` | `video`.

### Step 3: Pull the data
Verify field names with `ads_get_field_context` first, then `ads_get_ad_entities` with `object_ids=[campaign_id]`:
- Totals: reach, impressions, frequency, clicks (all), link clicks, CTR (all), link CTR,
  messaging conversations started, post engagement, reactions, comments, shares,
  saves, Instagram profile visits, IG follows, FB follows.
- **Instagram profile visits** (`ig_profile_visits`): try `ads_get_field_context` first; the Meta Ads
  MCP currently does not expose it. Only when the campaign had real Instagram reach, ask the owner
  for the Ads Manager column "Instagram profile visits"; otherwise `null` (hidden, never 0).
  Facebook Page visits are not part of the report (owner's decision).
- Video (if video): 3-second plays, ThruPlays, 50% and 100% plays, average watch time.
- Breakdowns (separate calls): `publisher_platform`, `age,gender`, `region`,
  hourly (`hourly_stats_aggregated_by_audience_time_zone`), daily (`time_increment="1"`).
- Ads: `level=ad` with the same metrics + creative thumbnail (`ads_get_creatives`).
- Previous campaign of the same client (same account, name contains client name,
  ended earlier): reach, results, and ask the owner which package it was.

Missing metrics → `null` (the renderer hides them, never shows 0).
Hook/Thumb-Stop rate = 3s plays / impressions; Hold rate = ThruPlays / 3s plays (auto-computed).
Messages per hour are not available: use hourly impressions with `"hourly_metric": "impressions"`.

### Step 3b: Inspect the ad itself (every report, required)
Look at the creative, not only the numbers:
1. `ads_get_creatives` (body, title, object_type) for the ad text.
2. `ads_get_ad_preview` (`ad_id`, `ad_format=MOBILE_FEED_STANDARD`), then screenshot it:
   `python3 scripts/ad_preview_screenshot.py --url "<preview_url>" --out reports/<client>/ad.png`
   and open the PNG.
3. Check and note every problem found:
   - **Page category** shown under the ad (e.g. "Grocery Store" for a shoe shop) → fix the category.
   - **Price** missing in text/visual ("ابتداءً من ... دج", per pack for wholesale).
   - **What is sold is clear** from the first line and first image (e.g. kids' sizes → say "أحذية أطفال").
   - **Delivery / COD** mentioned (58/69 wilayas, الدفع عند الاستلام).
   - **Number of images**: too many (> 6) dilutes; 4–6 best products or a carousel per product.
   - **Image quality**: background, light, cropped or unreadable overlay text.
   - **Off-topic hashtags** (#حلاقة, #ماشطة, #تكتوك …) → remove.
   - **Targeting fit** vs product (e.g. wholesale → shop owners/retail interests; women's jewellery → women).
   - Contact outside Messenger (phone, Telegram, WhatsApp) → those leads are not counted in results.
4. Put the client-relevant findings in `recommendations` (direct wording if the agency did not make
   the creative, constructive if it did). Put agency-side findings in the private notes to the owner.

**Engagement vs. quality:** in a messages campaign, few likes/comments do **not** mean a weak ad:
Meta delivers to people likely to message, not to react. Judge the ad by conversations, cost per
conversation and CTR (all). Say this to the owner whenever engagement looks low.

### Step 3c: Private checks for the owner (never in the client report)
- Excluded regions vs. the shop's address in the ad text (e.g. Batna excluded but shop in Batna).
- Instagram account linked? (`ads_get_ig_accounts`; IG reach ≈ 0 means not linked.)
- Ad set optimisation goal: Messenger lead form (`LEAD_GENERATION`) → completed leads vs conversations.
- Gender/age expansion turned on (people outside the targeting reached).
- Reach below the package minimum → explain why (objective, audience size, budget).
- Link CTR in Messenger campaigns is naturally low → `"hide_ratings": ["link_ctr"]` if it would show 🔴.

### Step 4: Write the analysis (Arabic, simple)
- `summary` (optional; auto-generated otherwise): 2–3 lines, the result and cost per result in DZD.
- `client_feedback.analysis`: if the client gave feedback, explain **why** from the data
  (e.g. peak hours vs. reply speed, hook rate, CTR, frequency, audience mismatch,
  missing price/delivery info in the ad). Be honest and constructive.
- `video_notes`: 1–3 lines reading hook/hold/completion.
- `ads[].why`: why the best ad won.
- `recommendations`: 3–5 concrete actions for the next campaign.
- `next_package`: suggested tier + days from the price list + reason.

### Step 5: Render
```bash
python3 scripts/client_report.py --data <campaign>.json --out-dir reports/<client>/
```
Outputs `<name>.pdf`, every PDF page as an image `<name>-page-N.png` (1588x2246),
the summary card `<name>.png`, `<name>.html` and JSON with `warnings`
and computed values. Open the PNG and the page images to check the layout, then send
the PDF, the page images and the summary card to the owner. Mention any warnings to the owner only.

## Data file schema
See `sample-data.json`. Keys: `client_name`, `campaign_name`, `objective`,
`start_date`, `end_date` (YYYY-MM-DD), `package {tier, days, price?}` (price = discounted
DZD amount the client actually paid), `is_video`, `hide_ratings[]`, `hourly_metric`,
`result_key` / `result_unit` (override the main result, e.g. `video_3s` for an engagement
campaign whose "engagements" are mostly video plays), `cost_basis: "reach_1000"` (cost per 1,000
people reached when cost per result would round to ~0 DZD),
`made_by_agency`, `metrics {...}`, `daily [{date, results}]`,
`hourly [{hour, results}]`, `platforms [{name, reach, results}]`,
`age_gender [{age, male, female}]`, `regions [{name, reach}]`,
`ads [{name, thumbnail, results, reach, link_ctr, hook_rate, why}]`,
`previous {campaign_name, package, reach, results, end_date}`,
`client_feedback {note, analysis[]}`, `video_notes[]`, `recommendations[]`,
`next_package {tier, days, reason}`, optional `summary`.

## Updating agency details
Prices, packages, contacts, colors: edit `assets/agency.json` only.
Font: Tajawal (OFL, `assets/fonts/`).
