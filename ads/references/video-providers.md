# Video Generation Providers

<!-- Updated: 2026-11-02 -->
<!-- Used by: ads-generate (video mode) -->

## Default Provider: Google Veo (Gemini API)

Script: `scripts/generate_video.py`. It uses the same Gemini API key as image generation.

### Setup
- API key from https://aistudio.google.com/apikey, exported as `GOOGLE_API_KEY`
  (`GEMINI_API_KEY` also accepted)
- Billing enabled on the Google Cloud project, because Veo has no free tier
- A consumer "Gemini Pro / Google AI Pro" app subscription does NOT grant API access
- `pip install "google-genai>=1.16.0,<2.0.0"`

### Models

| Model | Use | Approx. price* |
|-------|-----|----------------|
| `veo-3.1-generate-preview` (default) | Final ad creatives, native audio | ~$0.40 / second |
| `veo-3.1-fast-generate-preview` (`--fast`) | Drafts, concept testing, A/B volume | ~$0.15 / second |

*Prices change, so verify at https://ai.google.dev/gemini-api/docs/pricing. An 8s clip costs about $3.20
(standard) or $1.20 (fast). Run `--estimate` first, and ask the user before spending more than $5.
Override the model with `--model` or `ADS_VIDEO_MODEL` when Google releases a newer Veo version.

### Limits
- Aspect ratios: **9:16** and **16:9** only. Crop 9:16 to 4:5 for Meta Feed, and 16:9 to 1:1 if needed.
- Duration: 4, 6 or 8 seconds per clip. Stitch clips for 15s or 30s spots.
- Resolution: 720p (default) or 1080p (8s only).
- Render time: usually 1 to 6 minutes. The script polls for up to 15 minutes.
- Output includes a SynthID watermark. Disclose AI-generated content where the platform requires it
  (Meta, TikTok and YouTube all have AI-content labels).

### Platform Mapping (`--platform`)

| Platform | Ratio | Notes |
|----------|-------|-------|
| tiktok, reels, stories, shorts, youtube-short | 9:16 | Hook in the first 1 to 2s, keep the safe zone clear |
| meta-feed | 9:16 | Crop to 4:5 in post |
| youtube, youtube-instream, display, linkedin | 16:9 | Brand in the first 5s for skippable |

### Prompt Formula for Ad Video

Write prompts in this order:
1. **Subject**: product or person, with concrete visual details
2. **Action / motion**: what moves and how, e.g. "slowly rotates", "pours"
3. **Camera**: "slow dolly-in", "handheld UGC selfie", "top-down", "360 orbit"
4. **Setting and lighting**: location, time of day, light quality
5. **Style**: brand mood from `brand-profile.json` (see `voice-to-style.md`)
6. **Audio**: dialogue in quotes, SFX, music mood, e.g. `upbeat lo-fi, no vocals`

Rules:
- Do not ask Veo to render on-screen text, prices or logos, because it garbles them. Add text overlays in editing.
- For product accuracy, use image-to-video (`--image product.png`) with a clean packshot.
  Generate the packshot first with `/ads photoshoot` or `/ads generate`.
- Use one idea per clip. Use the batch file for hook variants.

### Batch File

```json
[
  {"prompt": "...", "platform": "tiktok", "output": "tiktok/hook-a.mp4"},
  {"prompt": "...", "platform": "youtube", "duration": 6, "image": "ad-assets/hero.png", "output": "yt/bumper.mp4"}
]
```

Output with `--json`: a list of objects with `file`, `model`, `ratio`, `duration_seconds`,
`estimated_cost_usd` and `generation_success`/`error` fields.
