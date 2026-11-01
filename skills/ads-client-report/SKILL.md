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
10. Visual style: fun and easy on the eye: colourful cards (green, orange, yellow, red,
    blue, purple), emojis on every section and KPI, 🟢/🟡/🔴 rating badges. Red only for
    negative signals.

## Workflow

### Step 1: Ask the owner (before building), in one message
1. Which package did the client buy? (tier: ابتدائية / متوسطة / متقدمة + days)
2. Did the client give any feedback? (e.g. "no sales", "nobody engaged with the video")
3. Did the agency make the video/design for the client?
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
- Video (if video): 3-second plays, ThruPlays, 50% and 100% plays, average watch time.
- Breakdowns (separate calls): `publisher_platform`, `age,gender`, `region`,
  hourly (`hourly_stats_aggregated_by_audience_time_zone`), daily (`time_increment="1"`).
- Ads: `level=ad` with the same metrics + creative thumbnail (`ads_get_creatives`).
- Previous campaign of the same client (same account, name contains client name,
  ended earlier): reach, results, and ask the owner which package it was.

Missing metrics → `null` (the renderer hides them, never shows 0).
Hook/Thumb-Stop rate = 3s plays / impressions; Hold rate = ThruPlays / 3s plays (auto-computed).

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
Outputs `<name>.pdf`, `<name>.png`, `<name>.html` and JSON with `warnings`
and computed values. Open the PNG and the PDF pages to check the layout, then send
both files to the owner. Mention any warnings to the owner only.

## Data file schema
See `sample-data.json`. Keys: `client_name`, `campaign_name`, `objective`,
`start_date`, `end_date` (YYYY-MM-DD), `package {tier, days}`, `is_video`,
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
