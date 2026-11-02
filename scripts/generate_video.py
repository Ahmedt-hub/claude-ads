#!/usr/bin/env python3
"""
Generate short ad video creatives with Google Veo (Gemini API).

Supports text-to-video and image-to-video (animate a product shot or a
generated ad image). Outputs MP4 files sized for vertical (9:16: TikTok,
Reels, Shorts, Stories) or landscape (16:9: YouTube, in-stream, Display)
placements, and prints a JSON summary with --json.

Usage:
    python generate_video.py "prompt text" --ratio 9:16 --output reel.mp4
    python generate_video.py "prompt" --platform tiktok --duration 8 --json
    python generate_video.py "slow 360 orbit, studio light" --image product.png --ratio 9:16
    python generate_video.py --batch videos.json --output-dir ./ad-assets/video/
    python generate_video.py "prompt" --fast --estimate   # cost estimate only, no API call

Environment variables:
    GOOGLE_API_KEY   Gemini API key from https://aistudio.google.com/apikey
                     (GEMINI_API_KEY is also accepted). Billing must be enabled:
                     Veo is not available on the free tier.
    ADS_VIDEO_MODEL  Optional default model override.

Requires: pip install "google-genai>=1.16.0,<2.0.0"
See ads/references/video-providers.md for models, limits and pricing.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

DEFAULT_MODEL = "veo-3.1-generate-preview"
FAST_MODEL = "veo-3.1-fast-generate-preview"

# Veo only renders 16:9 and 9:16 natively.
SUPPORTED_RATIOS = ("9:16", "16:9")

# Platform shorthand → native Veo ratio (crop/pad other formats in post).
PLATFORM_RATIOS = {
    "tiktok": "9:16",
    "reels": "9:16",
    "meta-reels": "9:16",
    "stories": "9:16",
    "youtube-short": "9:16",
    "shorts": "9:16",
    "snapchat": "9:16",
    "youtube": "16:9",
    "youtube-instream": "16:9",
    "display": "16:9",
    "linkedin": "16:9",
    "meta-feed": "9:16",  # crop to 4:5 in post
}

VALID_DURATIONS = (4, 6, 8)
VALID_RESOLUTIONS = ("720p", "1080p")

# Approximate USD per second of output (with audio). Verify current pricing at
# https://ai.google.dev/gemini-api/docs/pricing before large batches.
PRICE_PER_SECOND = {
    DEFAULT_MODEL: 0.40,
    FAST_MODEL: 0.15,
}

POLL_INTERVAL = 10       # seconds between operation status checks
POLL_TIMEOUT = 15 * 60   # give up after 15 minutes
MAX_RETRIES = 4
RETRY_BACKOFF = [2, 4, 8, 16]

DEFAULT_NEGATIVE = "blurry, distorted text, watermark, low quality, deformed hands"


def _get_api_key() -> str:
    """Return the Gemini API key from the environment or exit with setup help."""
    key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not key:
        print(
            "Error: GOOGLE_API_KEY not set.\n"
            "  1. Create a key at https://aistudio.google.com/apikey (enable billing; Veo is paid-only)\n"
            "  2. export GOOGLE_API_KEY=\"your-key\"\n"
            "  Cloud sessions: add it in the environment settings, then start a new session.",
            file=sys.stderr,
        )
        sys.exit(1)
    return key


def _import_genai():
    """Import google-genai lazily so --help and --estimate work without it."""
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        print(
            "Error: google-genai package required.\n"
            "Install with: pip install \"google-genai>=1.16.0,<2.0.0\"",
            file=sys.stderr,
        )
        sys.exit(1)
    return genai, types


def resolve_ratio(ratio: str | None, platform: str | None) -> str:
    """Pick the Veo aspect ratio from an explicit ratio or a platform name."""
    if platform:
        key = platform.lower()
        if key not in PLATFORM_RATIOS:
            raise ValueError(f"Unknown platform '{platform}'. Options: {', '.join(PLATFORM_RATIOS)}")
        return PLATFORM_RATIOS[key]
    ratio = ratio or "9:16"
    if ratio not in SUPPORTED_RATIOS:
        raise ValueError(f"Veo supports only {' and '.join(SUPPORTED_RATIOS)} (got '{ratio}'). Crop in post for 1:1 or 4:5.")
    return ratio


def estimate_cost(model: str, duration: int, count: int = 1) -> float | None:
    """Approximate USD cost for `count` clips of `duration` seconds."""
    rate = PRICE_PER_SECOND.get(model)
    return round(rate * duration * count, 2) if rate is not None else None


def _load_image(types, path: str):
    """Load a reference/first-frame image for image-to-video."""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Reference image not found: {path}")
    ext = p.suffix.lower()
    mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}.get(ext)
    if not mime:
        raise ValueError(f"Unsupported image type '{ext}'. Use PNG, JPEG or WebP.")
    return types.Image(image_bytes=p.read_bytes(), mime_type=mime)


def generate_video(
    client,
    types,
    prompt: str,
    output_path: str,
    ratio: str = "9:16",
    duration: int = 8,
    resolution: str = "720p",
    model: str = DEFAULT_MODEL,
    image_path: str | None = None,
    negative_prompt: str | None = DEFAULT_NEGATIVE,
) -> dict:
    """Submit one Veo job, poll until done, download the MP4 and return metadata."""
    if duration not in VALID_DURATIONS:
        raise ValueError(f"Duration must be one of {VALID_DURATIONS} seconds")
    if resolution not in VALID_RESOLUTIONS:
        raise ValueError(f"Resolution must be one of {VALID_RESOLUTIONS}")
    if resolution == "1080p" and duration != 8:
        raise ValueError("1080p requires --duration 8")

    config = types.GenerateVideosConfig(
        aspect_ratio=ratio,
        duration_seconds=duration,
        resolution=resolution,
        number_of_videos=1,
        negative_prompt=negative_prompt or None,
    )
    kwargs = {"model": model, "prompt": prompt, "config": config}
    if image_path:
        kwargs["image"] = _load_image(types, image_path)

    operation = None
    for attempt in range(MAX_RETRIES):
        try:
            operation = client.models.generate_videos(**kwargs)
            break
        except Exception as e:  # rate limits are retried, everything else bubbles up
            msg = str(e)
            if ("429" in msg or "RESOURCE_EXHAUSTED" in msg) and attempt < MAX_RETRIES - 1:
                wait = RETRY_BACKOFF[attempt]
                print(f"Rate limit hit, retrying in {wait}s...", file=sys.stderr)
                time.sleep(wait)
                continue
            raise

    started = time.time()
    while not operation.done:
        if time.time() - started > POLL_TIMEOUT:
            raise TimeoutError(f"Veo operation did not finish within {POLL_TIMEOUT // 60} minutes")
        print(f"  ...rendering ({int(time.time() - started)}s)", file=sys.stderr)
        time.sleep(POLL_INTERVAL)
        operation = client.operations.get(operation)

    if getattr(operation, "error", None):
        raise RuntimeError(f"Veo error: {operation.error}")
    response = operation.response
    videos = getattr(response, "generated_videos", None) if response else None
    if not videos:
        reasons = getattr(response, "rai_media_filtered_reasons", None) if response else None
        raise RuntimeError(f"No video returned (possibly safety-filtered): {reasons or 'no reason given'}")

    video = videos[0].video
    client.files.download(file=video)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    video.save(output_path)

    return {
        "file": output_path,
        "model": model,
        "ratio": ratio,
        "duration_seconds": duration,
        "resolution": resolution,
        "image": image_path,
        "prompt": prompt,
        "render_seconds": int(time.time() - started),
        "estimated_cost_usd": estimate_cost(model, duration),
    }


def run_batch(client, types, batch_file: str, output_dir: str, defaults: dict) -> list[dict]:
    """
    Run a batch of jobs. Batch file format:
    [
      {"prompt": "...", "platform": "tiktok", "output": "tiktok-hook.mp4"},
      {"prompt": "...", "ratio": "16:9", "duration": 6, "image": "hero.png"}
    ]
    """
    with open(batch_file) as f:
        jobs = json.load(f)
    results = []
    for i, job in enumerate(jobs):
        result = {"index": i, "generation_success": False, "error": None}
        try:
            ratio = resolve_ratio(job.get("ratio"), job.get("platform"))
            out = str(Path(output_dir) / job.get("output", f"video_{i:03d}.mp4"))
            print(f"[{i + 1}/{len(jobs)}] Generating {out}...", file=sys.stderr)
            meta = generate_video(
                client, types, job["prompt"], out,
                ratio=ratio,
                duration=int(job.get("duration", defaults["duration"])),
                resolution=job.get("resolution", defaults["resolution"]),
                model=job.get("model", defaults["model"]),
                image_path=job.get("image"),
                negative_prompt=job.get("negative_prompt", defaults["negative_prompt"]),
            )
            result.update(meta, generation_success=True)
        except Exception as e:
            result["error"] = str(e)
            print(f"  ✗ Error: {e}", file=sys.stderr)
        results.append(result)
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Generate ad video creatives with Google Veo (Gemini API)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"Platforms: {', '.join(PLATFORM_RATIOS)}\nRatios: {', '.join(SUPPORTED_RATIOS)}",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("prompt", nargs="?", help="Video prompt (scene, motion, camera, style, audio)")
    group.add_argument("--batch", "-b", metavar="FILE", help="Batch JSON file with multiple jobs")

    parser.add_argument("--output", "-o", help="Output MP4 path (default: ad_video_<ratio>.mp4)")
    parser.add_argument("--output-dir", default=".", help="Output directory for batch mode")
    parser.add_argument("--ratio", "-r", help="9:16 (default) or 16:9")
    parser.add_argument("--platform", "-p", help="Platform shorthand; sets the ratio")
    parser.add_argument("--duration", "-d", type=int, default=8, choices=VALID_DURATIONS, help="Seconds (default 8)")
    parser.add_argument("--resolution", default="720p", choices=VALID_RESOLUTIONS, help="720p (default) or 1080p (8s only)")
    parser.add_argument("--image", "-i", help="First-frame image for image-to-video (e.g. a product shot)")
    parser.add_argument("--negative-prompt", default=DEFAULT_NEGATIVE, help="What to avoid; pass '' to disable")
    parser.add_argument("--model", "-m", help=f"Model override (default {DEFAULT_MODEL})")
    parser.add_argument("--fast", action="store_true", help=f"Use {FAST_MODEL} (cheaper, faster drafts)")
    parser.add_argument("--estimate", action="store_true", help="Print cost estimate and exit without calling the API")
    parser.add_argument("--json", "-j", action="store_true", help="Output result as JSON")
    args = parser.parse_args()

    model = args.model or (FAST_MODEL if args.fast else os.environ.get("ADS_VIDEO_MODEL", DEFAULT_MODEL))

    if args.batch:
        with open(args.batch) as f:
            count = len(json.load(f))
    else:
        count = 1

    if args.estimate:
        cost = estimate_cost(model, args.duration, count)
        out = {"model": model, "clips": count, "duration_seconds": args.duration, "estimated_cost_usd": cost}
        print(json.dumps(out, indent=2) if args.json else f"Estimated cost: ${cost} for {count} × {args.duration}s clip(s) on {model}")
        return

    try:
        ratio = resolve_ratio(args.ratio, args.platform) if not args.batch else None
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    api_key = _get_api_key()
    genai, types = _import_genai()
    client = genai.Client(api_key=api_key)
    defaults = {
        "duration": args.duration,
        "resolution": args.resolution,
        "model": model,
        "negative_prompt": args.negative_prompt,
    }

    if args.batch:
        Path(args.output_dir).mkdir(parents=True, exist_ok=True)
        results = run_batch(client, types, args.batch, args.output_dir, defaults)
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            ok = sum(r["generation_success"] for r in results)
            print(f"\nBatch complete: {ok}/{len(results)} videos generated")
            for r in results:
                print(f"  {'✓' if r['generation_success'] else '✗'} {r.get('file') or r['error']}")
        sys.exit(0 if all(r["generation_success"] for r in results) else 1)

    output = args.output or f"ad_video_{ratio.replace(':', '-')}.mp4"
    try:
        meta = generate_video(
            client, types, args.prompt, output,
            ratio=ratio, duration=args.duration, resolution=args.resolution,
            model=model, image_path=args.image, negative_prompt=args.negative_prompt,
        )
    except Exception as e:
        if args.json:
            print(json.dumps({"success": False, "error": str(e)}, indent=2))
        else:
            print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    meta["success"] = True
    if args.json:
        print(json.dumps(meta, indent=2))
    else:
        print(f"✓ Generated {meta['duration_seconds']}s {ratio} video → {output} (~${meta['estimated_cost_usd']})")


if __name__ == "__main__":
    main()
