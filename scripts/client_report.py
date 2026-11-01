#!/usr/bin/env python3
"""
Client campaign report generator (Arabic, RTL, agency-branded).

Turns a campaign data JSON (collected from the Meta Ads MCP tools) into:
  * a multi-page A4 PDF report for the client, and
  * every PDF page as a PNG image (<name>-page-N.png), and
  * a single 1080x1350 PNG summary card (for WhatsApp / Messenger).

Business rules (see skills/ads-client-report/SKILL.md):
  * No USD amounts anywhere. Cost per result = package price (DZD) / results.
  * Video metrics are shown only when the campaign used video.
  * "Best ad" is shown only when the campaign had more than one ad.
  * Previous-campaign comparison and client-feedback sections are optional.
  * Estimated-reach badge is shown only when actual reach >= package minimum;
    otherwise a warning is returned in the JSON output for the agency only.
  * Metrics that are missing (null) are omitted, never printed as zero.

Usage:
    python3 scripts/client_report.py --data campaign.json --out-dir reports/
    python3 scripts/client_report.py --data campaign.json --html-only

Output (stdout, JSON):
    {"pdf": "...", "png": "...", "pages": ["...-page-1.png", ...], "html": "...",
     "warnings": [...], "computed": {...}}
"""

from __future__ import annotations

import argparse
import base64
import html
import json
import os
import re
import shutil
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "skills" / "ads-client-report" / "assets"

# ----------------------------------------------------------------------------
# Labels & plain-language explanations (Arabic)
# ----------------------------------------------------------------------------

OBJECTIVES = {
    "messages": {"label": "رسائل", "result_key": "messaging_conversations",
                 "unit": "محادثة", "goal": "جلب أكبر عدد من الرسائل والمحادثات"},
    "engagement": {"label": "تفاعل", "result_key": "post_engagement",
                   "unit": "تفاعل", "goal": "زيادة التفاعل على المنشور"},
    "profile": {"label": "زيارة البروفايل", "result_key": "ig_profile_visits",
                "unit": "زيارة", "goal": "جلب زيارات ومتابعين جدد للبروفايل"},
    "video": {"label": "مشاهدات الفيديو", "result_key": "thruplays",
              "unit": "مشاهدة", "goal": "إيصال الفيديو لأكبر عدد ومشاهدته"},
}

METRICS = {
    # key: (label, explanation, kind)  kind: int | pct | dec | sec | dzd
    "reach": ("الوصول", "عدد الأشخاص المختلفين الذين شاهدوا إعلانك.", "int"),
    "impressions": ("الظهور", "عدد المرات التي ظهر فيها إعلانك على الشاشات، والشخص الواحد قد يراه أكثر من مرة.", "int"),
    "frequency": ("التكرار", "متوسط عدد المرات التي رأى فيها الشخص الواحد إعلانك.", "dec"),
    "clicks_all": ("الضغطات الكلية", "كل الضغطات على الإعلان: الصورة، الاسم، الزر، الرابط، و\"عرض المزيد\".", "int"),
    "link_clicks": ("ضغطات الرابط", "الضغطات التي أخذت الشخص إلى وجهتك (الرسائل، البروفايل أو الموقع).", "int"),
    "ctr_all": ("نسبة النقر الإجمالية", "من كل 100 مرة ظهر فيها الإعلان، كم مرة ضغط عليه أحدهم.", "pct"),
    "link_ctr": ("نسبة نقر الرابط", "من كل 100 ظهور، كم ضغطة ذهبت فعلاً إلى وجهتك.", "pct"),
    "messaging_conversations": ("المحادثات التي بدأت", "عدد الأشخاص الذين راسلوك بسبب الإعلان (مسنجر، واتساب أو إنستغرام).", "int"),
    "post_engagement": ("التفاعل مع المنشور", "مجموع كل ما فعله الناس مع إعلانك: إعجاب، تعليق، مشاركة، حفظ وضغط.", "int"),
    "reactions": ("الإعجابات", "عدد الإعجابات والتفاعلات (❤️ 👍 😮 …).", "int"),
    "comments": ("التعليقات", "عدد التعليقات على الإعلان.", "int"),
    "shares": ("المشاركات", "عدد المرات التي شارك فيها الناس إعلانك مع غيرهم.", "int"),
    "saves": ("الحفظ", "عدد الأشخاص الذين حفظوا المنشور للرجوع إليه لاحقاً، وهذا دليل اهتمام قوي.", "int"),
    "ig_profile_visits": ("زيارات بروفايل إنستغرام", "عدد المرات التي دخل فيها الناس إلى حسابك على إنستغرام من الإعلان.", "int"),
    "ig_follows": ("متابعون جدد على إنستغرام", "عدد الأشخاص الذين تابعوا حسابك على إنستغرام.", "int"),
    "fb_follows": ("متابعون جدد على فيسبوك", "عدد الأشخاص الذين تابعوا صفحتك على فيسبوك.", "int"),
    "video_3s": ("مشاهدات 3 ثوانٍ", "عدد المرات التي شوهد فيها الفيديو 3 ثوانٍ على الأقل.", "int"),
    "thruplays": ("المشاهدات الكاملة (ThruPlay)", "مشاهدة 15 ثانية من الفيديو، أو مشاهدته كاملاً إن كان أقصر.", "int"),
    "video_p50": ("مشاهدة 50%", "عدد المرات التي شوهد فيها نصف الفيديو.", "int"),
    "video_p100": ("مشاهدة 100%", "عدد المرات التي شوهد فيها الفيديو حتى النهاية.", "int"),
    "avg_watch_time": ("متوسط مدة المشاهدة", "متوسط الوقت الذي بقي فيه الشخص يشاهد الفيديو.", "sec"),
    "hook_rate": ("Hook / Thumb-Stop Rate", "من بين كل من مرّ عليهم الفيديو، كم بالمئة توقفوا عن التمرير وشاهدوه 3 ثوانٍ. يقيس قوة بداية الفيديو.", "pct"),
    "hold_rate": ("Hold Rate", "من بين من توقفوا لمشاهدة الفيديو، كم بالمئة أكملوا المشاهدة (ThruPlay). يقيس قدرة الفيديو على إبقاء الناس.", "pct"),
}

GROUPS = [
    ("👀 الوصول والظهور", ["reach", "impressions", "frequency"], "blue"),
    ("🎯 النتائج", ["messaging_conversations", "ig_profile_visits", "ig_follows", "fb_follows"], "green"),
    ("❤️ التفاعل", ["post_engagement", "reactions", "comments", "shares", "saves"], "red"),
    ("👆 الضغطات", ["clicks_all", "link_clicks", "ctr_all", "link_ctr"], "orange"),
]

EMOJI = {
    "reach": "👀", "impressions": "📺", "frequency": "🔁", "clicks_all": "👆", "link_clicks": "🔗",
    "ctr_all": "📊", "link_ctr": "🎯", "messaging_conversations": "💬", "post_engagement": "🔥",
    "reactions": "❤️", "comments": "🗨️", "shares": "🔄", "saves": "🔖", "ig_profile_visits": "📸",
    "ig_follows": "➕", "fb_follows": "👍", "video_3s": "▶️", "thruplays": "🎬", "video_p50": "⏯️",
    "video_p100": "🏁", "avg_watch_time": "⏱️", "hook_rate": "🪝", "hold_rate": "🧲",
}
OBJ_EMOJI = {"messages": "💬", "engagement": "🔥", "profile": "📸", "video": "🎬"}
# colour of each metric card / tile
KPI_COLOR = {"reach": "blue", "impressions": "purple", "frequency": "yellow", "link_clicks": "teal",
             "thruplays": "red"}
CYCLE = ["#146884"]
REC_STYLE = [("💡", "yellow"), ("🎯", "green"), ("⏰", "orange"), ("📣", "blue"), ("🚀", "purple"), ("✅", "teal")]
VIDEO_KEYS = ["video_3s", "hook_rate", "thruplays", "hold_rate", "video_p50",
              "video_p100", "avg_watch_time"]

# (good_threshold, excellent_threshold) – higher is better
RATINGS = {
    "hook_rate": (20.0, 30.0),
    "hold_rate": (25.0, 40.0),
    "link_ctr": (1.0, 2.0),
    "ctr_all": (1.5, 3.0),
}
# lower is better: (excellent_max, good_max)
RATINGS_LOW = {"frequency": (2.5, 4.0)}

# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


def esc(v) -> str:
    return html.escape(str(v), quote=True)


def num(v) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def fmt(v, kind="int") -> str:
    v = num(v)
    if v is None:
        return "—"
    if kind == "int":
        return f"{round(v):,}"
    if kind == "dec":
        return f"{v:.2f}"
    if kind == "pct":
        return f"{v:.2f}%"
    if kind == "sec":
        return f"{v:.1f} ث"
    if kind == "dzd":
        return f"{round(v):,} دج"
    return str(v)


def fmt_k(v) -> str:
    v = num(v) or 0
    if v >= 1000:
        s = f"{v / 1000:.1f}".rstrip("0").rstrip(".")
        return f"{s}K"
    return f"{round(v)}"


def parse_date(s: str) -> date | None:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def fmt_date(s: str) -> str:
    d = parse_date(s)
    return d.strftime("%d/%m/%Y") if d else esc(s or "")


def rating(key: str, v: float | None) -> tuple[str, str] | None:
    if v is None:
        return None
    if key in RATINGS_LOW:
        exc, good = RATINGS_LOW[key]
        if v <= exc:
            return ("🟢 ممتاز", "r-exc")
        return ("🟡 جيد", "r-good") if v <= good else ("🔴 مرتفع", "r-low")
    if key not in RATINGS:
        return None
    good, exc = RATINGS[key]
    if v >= exc:
        return ("🟢 ممتاز", "r-exc")
    if v >= good:
        return ("🟡 جيد", "r-good")
    return ("🔴 يحتاج تحسين", "r-low")


def b64_file(path: Path, mime: str) -> str:
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


def font_faces() -> str:
    out = []
    for w, name in [(400, "Regular"), (500, "Medium"), (700, "Bold"), (800, "ExtraBold")]:
        p = ASSETS / "fonts" / f"Tajawal-{name}.ttf"
        if p.exists():
            out.append(
                "@font-face{font-family:'Tajawal';font-weight:%d;"
                "src:url('%s') format('truetype');}" % (w, b64_file(p, "font/ttf")))
    return "\n".join(out)


def image_src(ref: str | None, base: Path) -> str | None:
    """Return a usable <img src>: http(s)/data URLs pass through, local files are inlined."""
    if not ref:
        return None
    if re.match(r"^(https?:|data:)", ref):
        return ref
    p = (base / ref) if not Path(ref).is_absolute() else Path(ref)
    if p.exists():
        mime = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
        return b64_file(p, mime)
    return None


# ----------------------------------------------------------------------------
# Computation
# ----------------------------------------------------------------------------


def lookup_package(agency: dict, pkg: dict) -> dict:
    tier = pkg.get("tier", "").replace("الباقة", "").replace("ال", "", 1).strip()
    # accept "الابتدائية" / "ابتدائية" / "المتوسطة" ...
    for name in agency["packages"]:
        if name in pkg.get("tier", "") or name == tier:
            tier = name
            break
    days = str(pkg.get("days"))
    entry = agency["packages"].get(tier, {}).get(days)
    if not entry:
        raise SystemExit(json.dumps({"error": f"Unknown package: tier={pkg.get('tier')} days={days}"},
                                    ensure_ascii=False))
    out = {"tier": tier, "days": int(days), **entry}
    if pkg.get("price"):  # negotiated / discounted price overrides the list price
        out["list_price"] = entry["price"]
        out["price"] = int(pkg["price"])
    return out


def compute(data: dict, agency: dict) -> tuple[dict, list[str]]:
    warnings: list[str] = []
    m = dict(data.get("metrics", {}))
    obj = OBJECTIVES.get(data.get("objective", "messages"), OBJECTIVES["messages"])
    pkg = lookup_package(agency, data["package"])

    # derived video rates
    imp, v3, thru = num(m.get("impressions")), num(m.get("video_3s")), num(m.get("thruplays"))
    if data.get("is_video"):
        if m.get("hook_rate") is None and imp and v3 is not None:
            m["hook_rate"] = v3 / imp * 100
        if m.get("hold_rate") is None and v3 and thru is not None:
            m["hold_rate"] = thru / v3 * 100
    if m.get("frequency") is None and num(m.get("reach")) and imp:
        m["frequency"] = imp / num(m["reach"])

    results = num(m.get(obj["result_key"]))
    cpr = pkg["price"] / results if results else None
    reach = num(m.get("reach"))
    cpm_reach = pkg["price"] / reach * 1000 if reach else None

    lo, hi = pkg["est_reach"]
    reach_ok = reach is not None and reach >= lo
    if reach is not None and not reach_ok:
        warnings.append(
            f"الوصول الفعلي ({fmt(reach)}) أقل من الحد الأدنى المتوقع للباقة ({fmt(lo)}). "
            "لم يُعرض قسم الوصول المتوقع في التقرير.")
    if data.get("is_video") is False:
        for k in VIDEO_KEYS:
            m.pop(k, None)

    prev = data.get("previous")
    comp = None
    if prev:
        ppkg = lookup_package(agency, prev["package"])
        pres = num(prev.get("results"))
        pcpr = ppkg["price"] / pres if pres else None
        comp = {"name": prev.get("campaign_name", "الحملة السابقة"),
                "package": ppkg, "results": pres, "reach": num(prev.get("reach")),
                "cpr": pcpr, "end_date": prev.get("end_date")}
        if pcpr and cpr:
            comp["cpr_change"] = (cpr - pcpr) / pcpr * 100
        if comp["reach"] and reach:
            comp["reach_change"] = (reach - comp["reach"]) / comp["reach"] * 100
        if pres and results:
            comp["results_change"] = (results - pres) / pres * 100

    return {"metrics": m, "objective": obj, "package": pkg, "results": results,
            "cpr": cpr, "cost_per_1000_reach": cpm_reach,
            "reach_ok": reach_ok, "comparison": comp}, warnings


# ----------------------------------------------------------------------------
# SVG charts
# ----------------------------------------------------------------------------


def svg_bars(points: list[tuple[str, float]], width=680, height=210, color="#146884",
             highlight_top=0, label_every=1, value_labels=True, base="#AFD0FB") -> str:
    if not points:
        return ""
    pad_l, pad_r, pad_t, pad_b = 8, 8, 22, 28
    n = len(points)
    vmax = max(v for _, v in points) or 1
    cw = (width - pad_l - pad_r) / n
    bw = max(4.0, cw * 0.62)
    top_idx = set()
    if highlight_top:
        top_idx = {i for i, _ in sorted(enumerate(points), key=lambda t: -t[1][1])[:highlight_top]}
    parts = [f'<svg viewBox="0 0 {width} {height}" width="100%" dir="ltr" '
             f'xmlns="http://www.w3.org/2000/svg" font-family="Tajawal">']
    base_y = height - pad_b
    parts.append(f'<line x1="{pad_l}" y1="{base_y}" x2="{width - pad_r}" y2="{base_y}" '
                 f'stroke="#AFD0FB" stroke-width="1"/>')
    for i, (lab, v) in enumerate(points):
        h = (height - pad_t - pad_b) * (v / vmax)
        x = pad_l + i * cw + (cw - bw) / 2
        y = base_y - h
        fill = color if (not highlight_top or i in top_idx) else base
        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{max(h, 0.5):.1f}" '
                     f'rx="3" fill="{fill}"/>')
        if value_labels and v > 0 and (n <= 16 or i in top_idx):
            parts.append(f'<text x="{x + bw / 2:.1f}" y="{y - 5:.1f}" font-size="11" '
                         f'text-anchor="middle" fill="#1f2d3a" font-weight="700">{fmt_k(v)}</text>')
        if i % label_every == 0:
            parts.append(f'<text x="{x + bw / 2:.1f}" y="{height - 9}" font-size="10.5" '
                         f'text-anchor="middle" fill="#5b6b7a">{esc(lab)}</text>')
    parts.append("</svg>")
    return "".join(parts)


def hbars(rows: list[tuple[str, float]], total: float | None = None, colors: list[str] | None = None) -> str:
    if not rows:
        return ""
    vmax = max(v for _, v in rows) or 1
    tot = total or sum(v for _, v in rows) or 1
    out = ['<div class="hbars">']
    colors = colors or CYCLE
    for i, (lab, v) in enumerate(rows):
        color = colors[i % len(colors)]
        out.append(
            f'<div class="hb-row"><div class="hb-lab">{esc(lab)}</div>'
            f'<div class="hb-track"><div class="hb-fill" style="width:{v / vmax * 100:.1f}%;background:{color}"></div></div>'
            f'<div class="hb-val">{fmt(v)} <span>({v / tot * 100:.0f}%)</span></div></div>')
    out.append("</div>")
    return "".join(out)


def age_gender_chart(rows: list[dict]) -> str:
    if not rows:
        return ""
    vmax = max(max(num(r.get("male")) or 0, num(r.get("female")) or 0) for r in rows) or 1
    out = ['<div class="ag"><div class="ag-legend"><span class="dot gm"></span>👨 رجال'
           '<span class="dot gf"></span>👩 نساء</div>']
    for r in rows:
        mv, fv = num(r.get("male")) or 0, num(r.get("female")) or 0
        out.append(
            f'<div class="ag-row"><div class="ag-lab">{esc(r.get("age"))}</div><div class="ag-bars">'
            f'<div class="ag-bar gm" style="width:{mv / vmax * 100:.1f}%"></div><span>{fmt(mv)}</span>'
            f'<div class="ag-break"></div>'
            f'<div class="ag-bar gf" style="width:{fv / vmax * 100:.1f}%"></div><span>{fmt(fv)}</span>'
            f'</div></div>')
    out.append("</div>")
    return "".join(out)


# ----------------------------------------------------------------------------
# HTML building
# ----------------------------------------------------------------------------


CSS = """
:root{--primary:%(primary)s;--secondary:%(secondary)s;--accent:%(accent)s;--soft:%(soft)s;--bg:%(background)s;
--ink:#1f2d3a;--muted:#5b6b7a;--ok:#16a34a;--warn:#f08a24;--bad:#e5484d;}
*{box-sizing:border-box;margin:0;padding:0}
html,body{background:#fff;color:var(--ink);font-family:'Tajawal','Noto Color Emoji',sans-serif;-webkit-print-color-adjust:exact;print-color-adjust:exact}
@page{size:A4;margin:0}
.page{width:210mm;height:297mm;position:relative;overflow:hidden;page-break-after:always;background:#fff;padding:0 13mm 22mm;display:flex;flex-direction:column}
.body{flex:1;min-height:0;overflow:hidden;margin:0 -13mm;padding:0 13mm}
#src{position:absolute;left:-10000px;top:0;width:184mm;visibility:hidden}
.page:last-of-type{page-break-after:auto}
/* colour themes */
.c-blue,.c-green,.c-orange,.c-yellow,.c-red,.c-purple,.c-teal{--ci:var(--primary);--cbg:var(--bg)}
.c-blue{--c:#3b82f6}.c-green{--c:#22c55e}.c-orange{--c:#fb8c3c}.c-yellow{--c:#facc15}
.c-red{--c:#f05252}.c-purple{--c:#a78bfa}.c-teal{--c:#2dd4bf}
.band{height:28mm;margin:0 -13mm 5mm;padding:0 13mm;display:flex;align-items:center;justify-content:space-between;
 background:linear-gradient(90deg,var(--bg) 0%%,var(--bg) 55%%,var(--soft) 100%%);border-bottom:3px solid var(--primary)}
.band img{height:19mm}
.band .t h1{font-size:20pt;font-weight:800;color:var(--primary);line-height:1.15}
.band .t p{font-size:11pt;color:var(--secondary);font-weight:700}
.mini-band{flex:none;height:16mm;margin:0 -13mm 6mm;padding:0 13mm;display:flex;align-items:center;justify-content:space-between;
 background:var(--bg);border-bottom:2px solid var(--primary)}
.mini-band img{height:10mm}
.mini-band span{font-size:11pt;color:var(--primary);font-weight:700}
.footer{position:absolute;bottom:0;left:0;right:0;height:14mm;background:var(--primary);color:#fff;display:flex;
 align-items:center;justify-content:center;gap:5mm;font-size:9pt;font-weight:500;padding:0 8mm}
.footer b{color:var(--soft);font-weight:700}
.pn{position:absolute;bottom:17mm;left:13mm;font-size:8.5pt;color:var(--muted)}
h2{font-size:14pt;color:var(--primary);font-weight:800;margin:0 0 3mm;display:flex;align-items:center;gap:2mm}
.chapter{font-size:16pt}.chapter span{font-size:9.5pt;color:var(--muted);font-weight:500;margin-inline-start:2mm}
.grp{font-size:12pt;color:var(--ci);font-weight:800;margin:0 0 2.5mm}
.sec{margin-bottom:4.5mm;break-inside:avoid}
.client{display:grid;grid-template-columns:repeat(4,1fr);gap:3mm;margin-bottom:5mm}
.client>div{background:var(--bg);border-radius:3.5mm;padding:3mm 3.5mm}
.client small{display:block;font-size:8.5pt;color:var(--muted)}
.client strong{font-size:11.5pt;color:var(--ci);font-weight:800}
.client strong.dates{font-size:10pt;line-height:1.5}
.summary{background:linear-gradient(135deg,var(--primary),var(--secondary));color:#fff;border-radius:5mm;padding:4mm 6mm;margin-bottom:5mm}
.summary h3{font-size:12.5pt;font-weight:800;color:var(--soft);margin-bottom:1.5mm}
.summary p{font-size:12pt;line-height:1.75;font-weight:500}
.summary b{color:#fff;font-weight:800}
.hero{display:grid;grid-template-columns:repeat(3,1fr);gap:3mm;margin-bottom:5mm}
.kpi{position:relative;border-radius:4.5mm;padding:3mm 3.5mm;background:var(--bg);border-top:3px solid var(--c)}
.kpi .kic{position:absolute;left:3mm;top:3mm;font-size:17pt}
.kpi small{font-size:9.5pt;color:var(--muted);font-weight:700}
.kpi strong{display:block;font-size:20pt;color:var(--ci);font-weight:800;line-height:1.3}
.kpi em{font-style:normal;font-size:8.5pt;color:var(--muted);line-height:1.45;display:block}
.promise{display:flex;align-items:center;gap:4mm;background:#e8f9ee;border:1.5px solid #86efac;border-radius:4mm;padding:3mm 5mm;margin-bottom:5mm}
.promise .ic{font-size:20pt;flex:none}
.promise p{font-size:11pt;line-height:1.6}
.promise b{color:#15803d}
.mgrid{display:grid;grid-template-columns:1fr 1fr;gap:2mm}
.m{display:grid;grid-template-columns:9mm 1fr;gap:2.5mm;align-items:start;border-radius:3.5mm;background:var(--bg);padding:2.2mm 3mm}
.m .ic{width:9mm;height:9mm;border-radius:50%%;background:#fff;display:flex;align-items:center;justify-content:center;font-size:13pt}
.m .top{display:flex;justify-content:space-between;align-items:baseline;gap:2mm}
.m .lab{font-size:10pt;font-weight:700;color:var(--ink)}
.m .val{font-size:14pt;font-weight:800;color:var(--ci);white-space:nowrap}
.m .exp{font-size:8.6pt;color:var(--muted);line-height:1.45;margin-top:.5mm}
.badge{display:inline-block;font-size:7.8pt;font-weight:700;padding:.3mm 2mm;border-radius:6mm;margin-inline-start:1.5mm;vertical-align:middle}
.r-exc{background:#dcfce7;color:#15803d}.r-good{background:#fef3c7;color:#a16207}.r-low{background:#fee2e2;color:#c81e1e}
.chart{background:var(--cbg,var(--bg));border-radius:4mm;padding:3mm 4mm 1mm}
.note{font-size:9.5pt;color:var(--muted);margin-top:1.5mm;line-height:1.55}
.two{display:grid;grid-template-columns:1fr 1fr;gap:5mm}
.hbars{display:flex;flex-direction:column;gap:2mm}
.hb-row{display:grid;grid-template-columns:24mm 1fr 25mm;align-items:center;gap:2mm;font-size:9.5pt}
.hb-lab{font-weight:700}
.hb-track{height:4.6mm;background:#fff;border-radius:2.3mm;overflow:hidden}
.hb-fill{height:100%%;border-radius:2.3mm}
.hb-val{font-weight:800;color:var(--primary);font-size:9.5pt}.hb-val span{color:var(--muted);font-weight:500;font-size:8.5pt}
.ag-legend{font-size:9.5pt;color:var(--muted);display:flex;align-items:center;gap:1.5mm;margin-bottom:2mm}
.dot{width:3mm;height:3mm;border-radius:50%%;display:inline-block;margin-inline-start:3mm}
.dot.gm,.ag-bar.gm{background:var(--primary)}.dot.gf,.ag-bar.gf{background:var(--accent)}
.ag-row{display:grid;grid-template-columns:13mm 1fr;align-items:center;gap:2mm;margin-bottom:1.6mm}
.ag-lab{font-size:9.5pt;font-weight:700}
.ag-bars{display:flex;flex-wrap:wrap;align-items:center;gap:0 1.5mm;font-size:8pt;color:var(--muted)}
.ag-bar{height:2.8mm;border-radius:1.4mm;min-width:.6mm}
.ag-break{flex-basis:100%%;height:.8mm}
.best{display:grid;grid-template-columns:52mm 1fr;gap:5mm;background:var(--bg);border-radius:4mm;padding:4mm}
.best img{width:52mm;height:52mm;object-fit:cover;border-radius:3mm;background:#fff}
.best .noimg{width:52mm;height:52mm;border-radius:3mm;background:var(--soft);display:flex;align-items:center;justify-content:center;font-size:30pt}
.best h4{font-size:12.5pt;color:var(--primary);margin-bottom:2mm}
.best ul{list-style:none;display:grid;grid-template-columns:1fr 1fr;gap:2mm}
.best li{background:#fff;border-radius:2.5mm;padding:2mm 3mm;font-size:9pt;color:var(--muted)}
.best li b{display:block;font-size:13pt;color:var(--primary)}
.best p{font-size:9.5pt;line-height:1.55;margin-top:2.5mm}
table.cmp{width:100%%;border-collapse:separate;border-spacing:0;font-size:10pt;border-radius:3mm;overflow:hidden}
table.cmp th{background:var(--primary);color:#fff;padding:2.4mm 3mm;font-weight:700;text-align:right}
table.cmp td{padding:2.4mm 3mm;background:var(--bg);border-bottom:1px solid #fff}
.up{color:#15803d;font-weight:800;background:#dcfce7;border-radius:5mm;padding:.5mm 2.5mm}
.down{color:#c81e1e;font-weight:800;background:#fee2e2;border-radius:5mm;padding:.5mm 2.5mm}
.fb{border-right:4px solid #fb8c3c;background:var(--bg);border-radius:3.5mm;padding:4mm 5mm}
.fb .q{font-size:10.5pt;font-weight:700;margin-bottom:2mm}
.fb ul{list-style:none;font-size:10pt;line-height:1.7}
.fb li:before{content:"👉 "}
ol.recs{list-style:none;display:flex;flex-direction:column;gap:2.5mm}
ol.recs li{display:flex;gap:3mm;align-items:flex-start;font-size:10.5pt;line-height:1.6;background:var(--bg);border-radius:3.5mm;padding:2.8mm 4mm}
ol.recs li .ri{flex:none;font-size:13pt;line-height:1.3}
.next{display:flex;justify-content:space-between;align-items:center;gap:5mm;background:linear-gradient(135deg,var(--primary),var(--secondary));color:#fff;border-radius:5mm;padding:5mm 6mm}
.next h3{font-size:13pt;font-weight:800}
.next p{font-size:10.5pt;line-height:1.6;margin-top:1mm}
.next .price{flex:none;text-align:center;background:#fff;color:var(--primary);border-radius:3.5mm;padding:3mm 5mm}
.next .price b{display:block;font-size:19pt;font-weight:800}
.next .price small{font-size:9pt;color:var(--muted)}
.thanks{text-align:center;margin-top:6mm;font-size:13pt;color:var(--primary);font-weight:800}
"""


def footer_html(agency: dict) -> str:
    c = agency["contacts"]
    phones = " / ".join(c["phones"])
    return (f'<div class="footer"><span><b>IG</b> {esc(c["instagram"])}</span>'
            f'<span><b>FB</b> {esc(c["facebook"])}</span>'
            f'<span dir="ltr">📞 {esc(phones)}</span><span>📍 {esc(c["address"])}</span></div>')


def metric_card(key: str, m: dict, color: str = "blue") -> str:
    if key not in METRICS or m.get(key) is None:
        return ""
    label, exp, kind = METRICS[key]
    v = num(m[key])
    r = rating(key, v)
    badge = f'<span class="badge {r[1]}">{r[0]}</span>' if r else ""
    return (f'<div class="m c-{color}"><div class="ic">{EMOJI.get(key, "📌")}</div><div>'
            f'<div class="top"><span class="lab">{esc(label)}{badge}</span>'
            f'<span class="val">{fmt(v, kind)}</span></div><div class="exp">{esc(exp)}</div></div></div>')


def rec_li(text: str, i: int) -> str:
    icon, col = REC_STYLE[i % len(REC_STYLE)]
    return f'<li class="c-{col}"><span class="ri">{icon}</span><span>{esc(text)}</span></li>'


def auto_summary(data: dict, c: dict) -> str:
    m, obj = c["metrics"], c["objective"]
    parts = []
    if m.get("reach") is not None:
        parts.append(f"👀 وصل إعلانك إلى <b>{fmt(m['reach'])}</b> شخص وظهر <b>{fmt(m.get('impressions'))}</b> مرة.")
    if c["results"]:
        parts.append(f"🎯 حققت الحملة <b>{fmt(c['results'])}</b> {obj['unit']}، "
                     f"أي أن كل {obj['unit']} كلّفتك حوالي <b>{fmt(c['cpr'], 'dzd')}</b> فقط.")
    return " ".join(parts)


def blk(inner: str, new_page: bool = False) -> str:
    attr = ' data-np="1"' if new_page else ""
    return f'<div class="blk"{attr}>{inner}</div>'


def build_blocks(data: dict, agency: dict, c: dict, base: Path) -> list[str]:
    """Return content blocks in reading order. The in-browser paginator packs them
    into A4 pages; a block with new_page=True always starts a fresh page."""
    m, obj, pkg = c["metrics"], c["objective"], c["package"]
    logo = image_src(agency["logo"], ASSETS)
    title = data.get("client_name", "")
    B: list[str] = []

    # ---------------- Overview ----------------
    B.append(blk(f'<div class="band"><div class="t"><h1>📊 تقرير نتائج الحملة الإعلانية</h1>'
                 f'<p>{esc(title)}</p></div><img src="{logo}" alt=""></div>'))
    B.append(blk(
        '<div class="client">'
        f'<div class="c-blue"><small>👤 العميل</small><strong>{esc(title)}</strong></div>'
        f'<div class="c-green"><small>🎯 هدف الحملة</small><strong>{esc(obj["label"])}</strong></div>'
        f'<div class="c-orange"><small>📦 الباقة</small><strong>{esc(pkg["tier"])} <bdi>· {pkg["days"]} أيام</bdi></strong></div>'
        f'<div class="c-purple"><small>📅 المدة</small><strong class="dates">من <bdi>{fmt_date(data.get("start_date"))}</bdi>'
        f'<br>إلى <bdi>{fmt_date(data.get("end_date"))}</bdi></strong></div></div>'))
    summ = data.get("summary") or auto_summary(data, c)
    B.append(blk(f'<div class="summary"><h3>✨ باختصار</h3><p>{summ}</p></div>'))

    hero = []
    if c["results"] is not None:
        hero.append(f'<div class="kpi c-green"><span class="kic">{OBJ_EMOJI.get(data.get("objective"), "🎯")}</span>'
                    f'<small>{esc(METRICS[obj["result_key"]][0])}</small>'
                    f'<strong>{fmt(c["results"])}</strong><em>{esc(METRICS[obj["result_key"]][1])}</em></div>')
    if c["cpr"]:
        hero.append(f'<div class="kpi c-orange"><span class="kic">💰</span><small>تكلفة {esc(obj["unit"])} الواحدة</small>'
                    f'<strong>{fmt(c["cpr"], "dzd")}</strong>'
                    f'<em>سعر الباقة ({fmt(pkg["price"], "dzd")}) مقسوماً على عدد النتائج.</em></div>')
    for k in ["reach", "impressions", "frequency", "link_clicks"]:
        if m.get(k) is not None and len(hero) < 6:
            lab, exp, kind = METRICS[k]
            hero.append(f'<div class="kpi c-{KPI_COLOR.get(k, "blue")}"><span class="kic">{EMOJI[k]}</span>'
                        f'<small>{esc(lab)}</small><strong>{fmt(m[k], kind)}</strong>'
                        f'<em>{esc(exp)}</em></div>')
    B.append(blk('<div class="hero">' + "".join(hero) + "</div>"))

    if c["reach_ok"]:
        lo, hi = pkg["est_reach"]
        B.append(blk(f'<div class="promise"><div class="ic">🎉</div><p>الوصول المتوقع لباقتك كان بين '
                     f'<b>{fmt(lo)}</b> و<b>{fmt(hi)}</b> شخص، وإعلانك وصل فعلياً إلى '
                     f'<b>{fmt(m["reach"])}</b> شخص.</p></div>'))

    daily = data.get("daily") or []
    if daily:
        pts = []
        for d in daily:
            dd = parse_date(d.get("date"))
            pts.append((dd.strftime("%d/%m") if dd else str(d.get("date")), num(d.get("results")) or 0))
        every = 1 if len(pts) <= 15 else (2 if len(pts) <= 30 else 3)
        best = max(daily, key=lambda d: num(d.get("results")) or 0)
        B.append(blk(f'<div class="sec c-green"><h2>📅 النتائج يوماً بيوم</h2><div class="chart">'
                     f'{svg_bars(pts, height=125, label_every=every, value_labels=len(pts) <= 16, color="#22c55e", base="#5292B5", highlight_top=1)}</div>'
                     f'<p class="note">🏆 أفضل يوم كان <b><bdi>{fmt_date(best.get("date"))}</bdi></b> بـ '
                     f'{fmt(best.get("results"))} {esc(obj["unit"])}.</p></div>'))

    # ---------------- Detailed metrics ----------------
    first = True
    for gname, keys, gcol in GROUPS:
        cards = "".join(metric_card(k, m, gcol) for k in keys)
        if cards:
            head = ('<h2 class="chapter">📊 تفاصيل النتائج <span>كل رقم مع شرح بسيط لمعناه</span></h2>'
                    if first else "")
            B.append(blk(f'{head}<div class="sec c-{gcol}"><h3 class="grp">{esc(gname)}</h3>'
                         f'<div class="mgrid">{cards}</div></div>', new_page=first))
            first = False

    # ---------------- Video ----------------
    if data.get("is_video"):
        vcol = {"video_3s": "blue", "hook_rate": "orange", "thruplays": "green", "hold_rate": "purple",
                "video_p50": "teal", "video_p100": "green", "avg_watch_time": "yellow"}
        cards = "".join(metric_card(k, m, vcol[k]) for k in VIDEO_KEYS)
        if cards:
            B.append(blk(f'<div class="sec"><h2>🎬 أداء الفيديو</h2><div class="mgrid">{cards}</div></div>',
                         new_page=True))
            funnel = [(lab, num(m.get(k))) for lab, k in
                      [("الظهور", "impressions"), ("3 ثوانٍ", "video_3s"), ("ThruPlay", "thruplays"),
                       ("50%", "video_p50"), ("100%", "video_p100")] if m.get(k) is not None]
            if len(funnel) >= 3:
                B.append(blk('<div class="sec c-blue"><h2>🎢 رحلة المشاهد مع الفيديو</h2><div class="chart" style="padding:4mm">'
                             + hbars(funnel, total=funnel[0][1],
                                     colors=["#146884", "#2a7a98", "#5292B5", "#76a9d6", "#8AB5F5"]) +
                             '<p class="note">كل سطر يوضح كم شخصاً بقي يشاهد في كل مرحلة، '
                             'والنسبة محسوبة من عدد الظهور.</p></div></div>'))
            if data.get("video_notes"):
                B.append(blk('<div class="sec"><h2>🧐 قراءتنا للفيديو</h2><ol class="recs">'
                             + "".join(rec_li(t, i) for i, t in enumerate(data["video_notes"])) + "</ol></div>"))

    # ---------------- Audience & timing ----------------
    np_flag = True
    hourly = data.get("hourly") or []
    if hourly:
        hkey = data.get("hourly_metric", "results")
        hmap = {int(h.get("hour", 0)): num(h.get(hkey)) or 0 for h in hourly}
        pts = [(f"{h:02d}", hmap.get(h, 0)) for h in range(24)]
        top = [t for t in sorted(pts, key=lambda t: -t[1])[:3] if t[1] > 0]
        B.append(blk(f'<div class="sec c-orange"><h2>⏰ أوقات الذروة</h2><div class="chart">'
                     f'{svg_bars(pts, height=160, highlight_top=3, label_every=2, color="#fb8c3c", base="#AFD0FB")}</div>'
                     f'<p class="note">🔥 {"أكثر الساعات التي شوهد فيها إعلانك" if hkey == "impressions" else "أكثر الساعات نشاطاً"}: <b>{"، ".join(f"<bdi>{t[0]}:00</bdi>" for t in top)}</b>. '
                     f'ننصحك بأن تكون متاحاً للرد في هذه الأوقات.</p></div>', new_page=np_flag))
        np_flag = False
    plats = data.get("platforms") or []
    ag = data.get("age_gender") or []
    if plats or ag:
        left = right = ""
        if plats:
            key = "reach" if all(x.get("reach") is not None for x in plats) else "results"
            pcol = {}
            left = (f'<div class="sec c-blue"><h2>📱 حسب المنصة</h2><div class="chart" style="padding:4mm">'
                    + hbars([(x["name"], num(x.get(key)) or 0) for x in plats],
                            colors=["#146884", "#8AB5F5", "#5292B5"]) +
                    f'<p class="note">حسب {"الوصول" if key == "reach" else "النتائج"}.</p></div></div>')
        if ag:
            right = ('<div class="sec c-purple"><h2>👥 العمر والجنس</h2><div class="chart" style="padding:4mm">'
                     + age_gender_chart(ag) + '</div></div>')
        B.append(blk(f'<div class="two">{left}{right}</div>', new_page=np_flag))
        np_flag = False
    regions = data.get("regions") or []
    if regions:
        rows = sorted(((r["name"], num(r.get("reach") or r.get("results")) or 0) for r in regions),
                      key=lambda t: -t[1])[:8]
        B.append(blk('<div class="sec c-teal"><h2>📍 حسب الولاية</h2><div class="chart" style="padding:4mm">'
                     + hbars(rows) + '</div></div>', new_page=np_flag))
        np_flag = False

    # ---------------- Best ad / comparison / feedback / recommendations ----------------
    np_flag = True
    ads = data.get("ads") or []
    if len(ads) > 1:
        best = max(ads, key=lambda a: num(a.get("results")) or 0)
        src = image_src(best.get("thumbnail"), base)
        img = f'<img src="{src}" alt="">' if src else '<div class="noimg">🏆</div>'
        li = []
        if best.get("results") is not None:
            li.append(f'<li><b>{fmt(best["results"])}</b>{esc(obj["unit"])}</li>')
        for k in ["reach", "link_ctr", "hook_rate"]:
            if best.get(k) is not None:
                li.append(f'<li><b>{fmt(best[k], METRICS[k][2])}</b>{esc(METRICS[k][0])}</li>')
        why = f'<p>{esc(best["why"])}</p>' if best.get("why") else ""
        B.append(blk(f'<div class="sec"><h2>🏆 أفضل إعلان في الحملة</h2><div class="best">{img}<div>'
                     f'<h4>{esc(best.get("name", ""))}</h4><ul>{"".join(li)}</ul>{why}</div></div></div>',
                     new_page=np_flag))
        np_flag = False
    comp = c["comparison"]
    if comp:
        def chg(v, lower_better=False):
            if v is None:
                return "—"
            good = (v < 0) if lower_better else (v > 0)
            arrow = "▲" if v > 0 else "▼"
            icon = "✅" if good else "⚠️"
            return f'<span class="{"up" if good else "down"}">{icon} {arrow} {abs(v):.0f}%</span>'
        rows = [
            ("الباقة", f'{comp["package"]["tier"]} <bdi>· {comp["package"]["days"]} أيام</bdi>',
             f'{pkg["tier"]} <bdi>· {pkg["days"]} أيام</bdi>', "—"),
            ("الوصول", fmt(comp["reach"]), fmt(m.get("reach")), chg(comp.get("reach_change"))),
            (f'عدد النتائج ({obj["unit"]})', fmt(comp["results"]), fmt(c["results"]),
             chg(comp.get("results_change"))),
            (f'تكلفة {obj["unit"]} الواحدة', fmt(comp["cpr"], "dzd"), fmt(c["cpr"], "dzd"),
             chg(comp.get("cpr_change"), lower_better=True)),
        ]
        body = "".join(f"<tr><td><b>{esc(a)}</b></td><td>{b}</td><td>{cc}</td><td>{d}</td></tr>"
                       for a, b, cc, d in rows)
        B.append(blk('<div class="sec"><h2>📈 مقارنة مع حملتك السابقة</h2><table class="cmp"><thead><tr>'
                     '<th>المؤشر</th><th>الحملة السابقة</th><th>هذه الحملة</th><th>التغيّر</th></tr></thead>'
                     f'<tbody>{body}</tbody></table>'
                     '<p class="note">التكلفة محسوبة من سعر الباقة في كل حملة.</p></div>', new_page=np_flag))
        np_flag = False
    fb = data.get("client_feedback")
    if fb and fb.get("note"):
        reasons = "".join(f"<li>{esc(r)}</li>" for r in fb.get("analysis", []))
        B.append(blk(f'<div class="sec"><h2>💡 بخصوص ملاحظتك</h2><div class="fb"><div class="q">🗣️ «{esc(fb["note"])}»</div>'
                     f'<ul>{reasons}</ul></div></div>', new_page=np_flag))
        np_flag = False
    recs = data.get("recommendations") or []
    if recs:
        B.append(blk('<div class="sec"><h2>🚀 توصياتنا للحملة القادمة</h2><ol class="recs">'
                     + "".join(rec_li(r, i) for i, r in enumerate(recs[:6])) + "</ol></div>", new_page=np_flag))
        np_flag = False
    nxt = data.get("next_package")
    if nxt:
        np_ = lookup_package(agency, nxt)
        lo, hi = np_["est_reach"]
        B.append(blk(f'<div class="sec"><div class="next"><div><h3>🎁 الباقة المقترحة لك: {esc(np_["tier"])} '
                     f'<bdi>· {np_["days"]} أيام</bdi></h3>'
                     f'<p>{esc(nxt.get("reason", ""))}<br>👀 الوصول المتوقع: <bdi>{fmt(lo)} – {fmt(hi)}</bdi> شخص.</p></div>'
                     f'<div class="price"><b>{fmt(np_["price"], "dzd")}</b><small>{np_["days"]} أيام</small></div>'
                     f'</div></div>', new_page=np_flag))
    B.append(blk(f'<div class="thanks">شكراً لثقتك في {esc(agency["agency_name"])} 💙</div>'))
    return B


PAGINATE_JS = r"""
(function(){
  function layout(){
    const src=document.getElementById('src');
    const tpl=document.getElementById('tpl-page');
    const blocks=[...src.children];
    const out=document.getElementById('pages');
    let first=true, cur=null;
    function newPage(){
      const pg=tpl.content.firstElementChild.cloneNode(true);
      if(first){pg.querySelector('.mini-band').remove();}
      first=false; out.appendChild(pg); cur=pg.querySelector('.body'); return cur;
    }
    newPage();
    for(const b of blocks){
      if(b.dataset.np && cur.children.length) newPage();
      cur.appendChild(b);
      if(cur.scrollHeight>cur.clientHeight+1 && cur.children.length>1){
        cur.removeChild(b); newPage(); cur.appendChild(b);
      }
    }
    src.remove();
    const pages=[...out.querySelectorAll('.page')];
    pages.forEach((p,i)=>{p.querySelector('.pn').textContent=(i+1)+' / '+pages.length;});
    window.__reportReady=true;
  }
  document.fonts.ready.then(()=>requestAnimationFrame(layout));
})();
"""


def build_report_html(data: dict, agency: dict, c: dict, base: Path) -> str:
    css = CSS % agency["colors"]
    logo = image_src(agency["logo"], ASSETS)
    title = esc(data.get("client_name", ""))
    blocks = "".join(build_blocks(data, agency, c, base))
    tpl = (f'<template id="tpl-page"><section class="page">'
           f'<div class="mini-band"><span>📊 تقرير الحملة · {title}</span><img src="{logo}" alt=""></div>'
           f'<div class="body"></div><div class="pn" dir="ltr"></div>{footer_html(agency)}</section></template>')
    return (f'<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">'
            f'<title>تقرير {title}</title><style>{font_faces()}{css}</style></head><body>'
            f'{tpl}<div id="pages"></div><div id="src" class="page-measure">{blocks}</div>'
            f'<script>{PAGINATE_JS}</script></body></html>')


def build_card_html(data: dict, agency: dict, c: dict) -> str:
    m, obj, pkg = c["metrics"], c["objective"], c["package"]
    col = agency["colors"]
    logo = image_src(agency["logo"], ASSETS)
    tiles = []  # (emoji, label, value, colour)
    if c["results"] is not None:
        tiles.append((OBJ_EMOJI.get(data.get("objective"), "🎯"), METRICS[obj["result_key"]][0],
                      fmt(c["results"]), "green"))
    if c["cpr"]:
        tiles.append(("💰", f"تكلفة {obj['unit']} الواحدة", fmt(c["cpr"], "dzd"), "orange"))
    for k in ["reach", "impressions", "link_clicks", "frequency"]:
        if m.get(k) is not None and len(tiles) < 6:
            tiles.append((EMOJI[k], METRICS[k][0], fmt(m[k], METRICS[k][2]), KPI_COLOR.get(k, "blue")))
    if data.get("is_video") and m.get("thruplays") is not None and len(tiles) < 6:
        tiles.append(("🎬", "المشاهدات الكاملة", fmt(m["thruplays"]), "red"))
    tiles_html = "".join(
        f'<div class="t c-{cl}"><span class="e">{e}</span><small>{esc(a)}</small><b>{esc(v)}</b></div>'
        for e, a, v, cl in tiles)
    promise = ""
    if c["reach_ok"]:
        lo, hi = pkg["est_reach"]
        promise = (f'<div class="pr">🎉 الوصول المتوقع للباقة: <bdi dir="ltr">{fmt_k(lo)} – {fmt_k(hi)}</bdi>'
                   f'&nbsp;&nbsp;|&nbsp;&nbsp;الوصول الفعلي: <b><bdi>{fmt_k(m["reach"])}</bdi></b> ✅</div>')
    contacts = agency["contacts"]
    themes = """
    .c-blue{--c:#3b82f6}.c-green{--c:#22c55e}.c-orange{--c:#fb8c3c}.c-yellow{--c:#facc15}
    .c-red{--c:#f05252}.c-purple{--c:#a78bfa}.c-teal{--c:#2dd4bf}"""
    rainbow = col["primary"]
    css = f"""
    {font_faces()}
    {themes}
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{width:1080px;height:1350px;font-family:'Tajawal','Noto Color Emoji';background:#fff;color:#1f2d3a;overflow:hidden}}
    .top{{height:12px;background:{rainbow}}}
    .wrap{{position:relative;height:100%;padding:44px 64px}}
    .head{{display:flex;justify-content:space-between;align-items:center}}
    .head img{{height:115px}}
    .head h1{{font-size:46px;font-weight:800;color:{col['primary']};line-height:1.2}}
    .head p{{font-size:31px;color:{col['secondary']};font-weight:700}}
    .meta{{margin-top:28px;display:flex;gap:14px}}
    .meta span{{border-radius:40px;padding:10px 24px;font-size:24px;font-weight:700;background:{col['background']};color:{col['primary']}}}
    .grid{{margin-top:30px;display:grid;grid-template-columns:1fr 1fr;gap:20px}}
    .t{{position:relative;background:{col['background']};border-radius:30px;padding:26px 32px;border-top:6px solid var(--c)}}
    .t .e{{position:absolute;left:28px;top:24px;font-size:50px}}
    .t small{{font-size:26px;font-weight:700;color:#5b6b7a}}
    .t b{{display:block;font-size:62px;font-weight:800;color:{col['primary']};line-height:1.2;margin-top:4px}}
    .pr{{margin-top:24px;background:#e8f9ee;border:3px solid #86efac;color:#15803d;border-radius:24px;padding:18px 26px;font-size:27px;font-weight:700;text-align:center}}
    .sum{{margin-top:22px;font-size:28px;line-height:1.7;font-weight:500;background:{col['background']};border-radius:24px;padding:22px 30px;border-right:8px solid {col['primary']}}}
    .sum b{{color:{col['primary']};font-weight:800}}
    .foot{{position:absolute;left:0;right:0;bottom:12px;height:100px;background:{col['primary']};color:#fff;display:flex;align-items:center;justify-content:center;gap:34px;font-size:24px;font-weight:500}}
    .foot b{{color:{col['soft']}}}
    .bot{{position:absolute;left:0;right:0;bottom:0;height:12px;background:{rainbow}}}
    """
    summary = data.get("summary") or auto_summary(data, c)
    period = f'📅 من <bdi>{fmt_date(data.get("start_date"))}</bdi> إلى <bdi>{fmt_date(data.get("end_date"))}</bdi>'
    return (f'<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><style>{css}</style></head><body>'
            f'<div class="top"></div><div class="wrap"><div class="head"><div><h1>📊 نتائج حملتك الإعلانية</h1>'
            f'<p>{esc(data.get("client_name", ""))}</p></div><img src="{logo}" alt=""></div>'
            f'<div class="meta"><span class="c-orange">📦 الباقة ال{esc(pkg["tier"])} <bdi>· {pkg["days"]} أيام</bdi></span>'
            f'<span class="c-green">🎯 {esc(obj["label"])}</span><span class="c-purple">{period}</span></div>'
            f'<div class="grid">{tiles_html}</div>{promise}<div class="sum">✨ {summary}</div></div>'
            f'<div class="foot"><span><b>IG</b> {esc(contacts["instagram"])}</span>'
            f'<span dir="ltr">📞 {esc(" / ".join(contacts["phones"]))}</span>'
            f'<span>📍 {esc(contacts["address"])}</span></div><div class="bot"></div></body></html>')


# ----------------------------------------------------------------------------
# Rendering
# ----------------------------------------------------------------------------


def slug(s: str) -> str:
    s = re.sub(r"[^\w\-]+", "-", s, flags=re.UNICODE).strip("-")
    return s or "report"


def render(report_html: str, card_html: str, out_dir: Path, name: str) -> dict:
    from playwright.sync_api import sync_playwright

    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = out_dir / f"{name}.html"
    card_path = out_dir / f"{name}-card.html"
    html_path.write_text(report_html, encoding="utf-8")
    card_path.write_text(card_html, encoding="utf-8")
    pdf_path = out_dir / f"{name}.pdf"
    png_path = out_dir / f"{name}.png"
    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch()
        except Exception:  # browser build mismatch: fall back to a system Chromium
            exe = os.environ.get("CHROMIUM_PATH") or next(
                (p for p in ["/opt/pw-browsers/chromium", shutil.which("chromium") or "",
                             shutil.which("google-chrome") or ""] if p and Path(p).exists()), None)
            if not exe:
                raise
            browser = pw.chromium.launch(executable_path=exe, args=["--no-sandbox"])
        page = browser.new_page()
        page.goto(html_path.as_uri())
        page.wait_for_load_state("networkidle")
        page.wait_for_function("window.__reportReady === true", timeout=20000)
        page.pdf(path=str(pdf_path), format="A4", print_background=True,
                 margin={"top": "0", "right": "0", "bottom": "0", "left": "0"})
        # every PDF page also as an image (A4 at 2x: 1588x2246) for WhatsApp/Messenger
        shots = browser.new_page(viewport={"width": 794, "height": 1123}, device_scale_factor=2)
        shots.goto(html_path.as_uri())
        shots.wait_for_function("window.__reportReady === true", timeout=20000)
        pages_el = shots.locator(".page")
        page_imgs = []
        for i in range(pages_el.count()):
            ip = out_dir / f"{name}-page-{i + 1}.png"
            pages_el.nth(i).screenshot(path=str(ip))
            page_imgs.append(str(ip))
        card = browser.new_page(viewport={"width": 1080, "height": 1350})
        card.goto(card_path.as_uri())
        card.wait_for_load_state("networkidle")
        card.evaluate("document.fonts.ready")
        card.screenshot(path=str(png_path), full_page=False)
        browser.close()
    card_path.unlink(missing_ok=True)
    return {"pdf": str(pdf_path), "png": str(png_path), "pages": page_imgs, "html": str(html_path)}


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate an Arabic client campaign report (PDF + PNG).")
    ap.add_argument("--data", required=True, help="Path to campaign data JSON")
    ap.add_argument("--agency", default=str(ASSETS / "agency.json"), help="Agency config JSON")
    ap.add_argument("--out-dir", default="reports", help="Output directory")
    ap.add_argument("--name", help="Output file base name (default: client + end date)")
    ap.add_argument("--html-only", action="store_true", help="Only write HTML, skip PDF/PNG")
    args = ap.parse_args()

    data_path = Path(args.data)
    data = json.loads(data_path.read_text(encoding="utf-8"))
    agency = json.loads(Path(args.agency).read_text(encoding="utf-8"))
    c, warnings = compute(data, agency)

    report_html = build_report_html(data, agency, c, data_path.parent)
    card_html = build_card_html(data, agency, c)
    name = args.name or slug(f'{data.get("client_name", "client")}-{data.get("end_date", "")}')
    out_dir = Path(args.out_dir).resolve()

    if args.html_only:
        out_dir.mkdir(parents=True, exist_ok=True)
        hp = out_dir / f"{name}.html"
        hp.write_text(report_html, encoding="utf-8")
        result = {"html": str(hp)}
    else:
        result = render(report_html, card_html, out_dir, name)

    result["warnings"] = warnings
    result["computed"] = {
        "package": c["package"], "results": c["results"],
        "cost_per_result_dzd": round(c["cpr"]) if c["cpr"] else None,
        "reach_within_estimate": c["reach_ok"],
        "comparison": c["comparison"],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
