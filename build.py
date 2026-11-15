#!/usr/bin/env python3
"""Free Game Radar: builds a static site of live free-game giveaways (English + Arabic)
and posts new ones to Telegram. Standard library only, no API keys needed.
Data: GamerPower.com (attribution is required and shown in every page footer)."""
import html, json, os, re, shutil, sys, time, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SITE, STATE = ROOT / "site", ROOT / "state"
API = "https://www.gamerpower.com/api/giveaways?type=game&sort-by=popularity"
UA = {"User-Agent": "FreeGameRadar/1.0 (static site generator)"}
esc = html.escape

T = {
    "en": dict(dir="ltr", tag="Free games you can claim right now", free="Free", ends="Ends",
               noend="No end date listed", claim="Claim for free", back="All free games",
               join="Join on Telegram", other="العربية", empty="No free games right now. Check back soon.",
               how="How to claim", compare="Find it on sale", data="Data from",
               disc="Some links are affiliate links: we may earn a commission at no extra cost to you."),
    "ar": dict(dir="rtl", tag="ألعاب مجانية يمكنك الحصول عليها الآن", free="مجانًا", ends="ينتهي",
               noend="لا يوجد تاريخ انتهاء", claim="احصل عليها مجانًا", back="كل الألعاب المجانية",
               join="انضم على تيليجرام", other="English", empty="لا توجد ألعاب مجانية الآن. عد قريبًا.",
               how="طريقة الحصول عليها", compare="ابحث عنها بسعر مخفّض", data="البيانات من",
               disc="بعض الروابط تابعة: قد نحصل على عمولة دون أي تكلفة إضافية عليك."),
}

CSS = """
:root{--bg:#f5f7fa;--ink:#14202b;--mut:#566573;--line:#d9e0e6;--acc:#0a6b52;--btn-ink:#fff}
@media (prefers-color-scheme:dark){:root{--bg:#10171d;--ink:#e8eef3;--mut:#93a3b1;--line:#26333d;--acc:#5fe0aa;--btn-ink:#08241a}}
*{box-sizing:border-box}
html{color-scheme:light dark}
body{margin:0;background:var(--bg);color:var(--ink);font:17px/1.6 "Segoe UI",system-ui,-apple-system,"Noto Sans Arabic",Tahoma,sans-serif}
a{color:inherit;text-underline-offset:3px}
a:focus-visible{outline:3px solid var(--acc);outline-offset:3px}
.wrap{max-width:720px;margin:0 auto;padding:18px 16px 56px}
header{display:flex;flex-wrap:wrap;gap:6px 18px;justify-content:space-between;align-items:baseline;padding-bottom:12px;border-bottom:2px solid var(--ink)}
.brand{font-weight:700;font-size:1.15rem;text-decoration:none}
nav{display:flex;gap:16px}
h1{font-size:1.6rem;line-height:1.25;margin:28px 0 8px}
.row{display:grid;grid-template-columns:112px 1fr;gap:14px;padding:16px 0;border-bottom:1px solid var(--line);text-decoration:none;align-items:center}
.row img{width:112px;height:63px;object-fit:cover;border-radius:4px;background:var(--line)}
.row strong{display:block;font-size:1.05rem;line-height:1.3}
.row:hover strong{text-decoration:underline}
.meta{display:flex;flex-wrap:wrap;gap:2px 14px;color:var(--mut);font-size:.9rem;margin-top:4px}
.meta b{color:var(--acc)}
s{opacity:.7}
.hero{width:100%;max-height:360px;object-fit:cover;border-radius:6px}
.btn{display:inline-block;margin:14px 0;padding:12px 22px;background:var(--acc);color:var(--btn-ink);font-weight:700;border-radius:6px;text-decoration:none}
ol{padding-inline-start:1.3em}
.cmp{color:var(--mut)}
footer{margin-top:40px;padding-top:14px;border-top:1px solid var(--line);color:var(--mut);font-size:.85rem}
@media (max-width:480px){.row{grid-template-columns:88px 1fr}.row img{width:88px;height:50px}}
"""


def fetch_json(url, tries=3):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                return json.load(r)
        except Exception as e:
            print(f"fetch {i + 1}/{tries} failed: {e}", file=sys.stderr)
            time.sleep(3 * (i + 1))
    return None


def clean_title(t):
    t = re.sub(r"\s*\([^)]*\)\s*Giveaway\s*$", "", t or "", flags=re.I)
    return re.sub(r"\s*Giveaway\s*$", "", t, flags=re.I).strip() or "Free game"


def slug(t):
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")[:50] or "game"


def load_items():
    """Live giveaways. If the API is down, keep serving the last good copy."""
    cache = STATE / "giveaways.json"
    raw = fetch_json(API)
    if isinstance(raw, list):
        items = [dict(id=int(g["id"]), title=clean_title(g.get("title")), worth=g.get("worth") or "N/A",
                      image=g.get("image") or g.get("thumbnail") or "", desc=g.get("description") or "",
                      how=g.get("instructions") or "", platforms=g.get("platforms") or "",
                      end=g.get("end_date") or "N/A",
                      claim=g.get("open_giveaway_url") or g.get("gamerpower_url") or "")
                 for g in raw if isinstance(g, dict) and g.get("id")]
        STATE.mkdir(exist_ok=True)
        cache.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
        return items
    if isinstance(raw, dict):  # API answered "no active giveaways"
        return []
    if cache.exists():
        print("API unreachable: using cached data", file=sys.stderr)
        return json.loads(cache.read_text(encoding="utf-8"))
    return []


def fmt_end(e, L):
    m = re.match(r"\d{4}-\d{2}-\d{2}", e or "")
    return f'{L["ends"]} {m.group(0)}' if m else L["noend"]


def has_worth(g):
    return g["worth"] not in ("", "N/A")


def aff_links(title, cfg):
    out = []
    for name, a in (cfg.get("affiliates") or {}).items():
        u = a.get("url") or ""
        if a.get("enabled") and "{q}" in u:
            href = u.replace("{q}", urllib.parse.quote_plus(title))
            out.append(f'<a rel="sponsored nofollow noopener" href="{esc(href)}">{esc(name)}</a>')
    return out


def path_for(g, lang):
    return f'{"/ar" if lang == "ar" else ""}/g/{g["id"]}-{slug(g["title"])}.html'


def shell(lang, cfg, title, desc, body, here, there, img=""):
    L, base = T[lang], (cfg.get("site_url") or "").rstrip("/")
    other = "en" if lang == "ar" else "ar"
    tg = (cfg.get("telegram_url") or {}).get(lang, "")
    seo = (f'<link rel="canonical" href="{base}{here}">'
           f'<link rel="alternate" hreflang="{other}" href="{base}{there}">') if base else ""
    og = f'<meta property="og:image" content="{esc(img)}">' if img else ""
    join = f'<a href="{esc(tg)}" rel="noopener">{L["join"]}</a>' if tg else ""
    disc = f'<p>{L["disc"]}</p>' if any(aff_links("x", cfg)) else ""
    home = "/ar/" if lang == "ar" else "/"
    return (f'<!doctype html><html lang="{lang}" dir="{L["dir"]}"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{esc(title)}</title><meta name="description" content="{esc(desc)}">{seo}'
            f'<meta property="og:title" content="{esc(title)}">{og}<style>{CSS}</style></head>'
            f'<body><div class="wrap"><header><a class="brand" href="{home}">{esc(cfg["name"][lang])}</a>'
            f'<nav>{join}<a href="{there}" hreflang="{other}">{L["other"]}</a></nav></header>'
            f'<main>{body}</main><footer>{disc}<p>{L["data"]} '
            f'<a href="https://www.gamerpower.com" rel="noopener">GamerPower.com</a></p></footer></div></body></html>')


def row(g, lang):
    L = T[lang]
    price = f'<span><s>{esc(g["worth"])}</s> <b>{L["free"]}</b></span>' if has_worth(g) else f'<b>{L["free"]}</b>'
    img = (f'<img src="{esc(g["image"])}" alt="" width="112" height="63" loading="lazy">'
           if g["image"] else "<span></span>")
    return (f'<a class="row" href="{path_for(g, lang)}">{img}<span><strong>{esc(g["title"])}</strong>'
            f'<span class="meta">{price}<span>{esc(g["platforms"])}</span>'
            f'<span>{esc(fmt_end(g["end"], L))}</span></span></span></a>')


def index_page(items, lang, cfg):
    L = T[lang]
    rows = "".join(row(g, lang) for g in items) or f'<p>{L["empty"]}</p>'
    here, there = ("/ar/", "/") if lang == "ar" else ("/", "/ar/")
    return shell(lang, cfg, f'{cfg["name"][lang]}: {L["tag"]}', L["tag"],
                 f'<h1>{L["tag"]}</h1>{rows}', here, there)


def detail_page(g, lang, cfg):
    L = T[lang]
    steps = [re.sub(r"^\s*\d+[.)]\s*", "", s) for s in g["how"].splitlines() if s.strip()]
    how = f'<h2>{L["how"]}</h2><ol>{"".join(f"<li>{esc(s)}</li>" for s in steps)}</ol>' if steps else ""
    links = aff_links(g["title"], cfg)
    cmp_ = f'<p class="cmp">{L["compare"]}: {" ".join(links)}</p>' if links else ""
    img = f'<img class="hero" src="{esc(g["image"])}" alt="" loading="lazy">' if g["image"] else ""
    price = f'<s>{esc(g["worth"])}</s> <b>{L["free"]}</b>' if has_worth(g) else f'<b>{L["free"]}</b>'
    other = "en" if lang == "ar" else "ar"
    body = (f'<p><a href="{"/ar/" if lang == "ar" else "/"}">{L["back"]}</a></p>{img}<h1>{esc(g["title"])}</h1>'
            f'<p class="meta">{price}<span>{esc(g["platforms"])}</span><span>{esc(fmt_end(g["end"], L))}</span></p>'
            f'<a class="btn" href="{esc(g["claim"])}" rel="noopener nofollow">{L["claim"]}</a>'
            f'<p>{esc(g["desc"])}</p>{how}{cmp_}')
    desc = f'{g["title"]}: {L["free"]}, {g["platforms"]}. {fmt_end(g["end"], L)}'
    return shell(lang, cfg, f'{g["title"]} ({L["free"]}) | {cfg["name"][lang]}', desc, body,
                 path_for(g, lang), path_for(g, other), g["image"])


def extras(items, cfg):
    """sitemap, robots and an RSS feed (only once site_url is set)."""
    base = (cfg.get("site_url") or "").rstrip("/")
    if not base:
        return
    urls = [f"{base}/", f"{base}/ar/"] + [base + path_for(g, l) for g in items for l in T]
    (SITE / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join(f"<url><loc>{esc(u)}</loc></url>" for u in urls) + "</urlset>", encoding="utf-8")
    (SITE / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {base}/sitemap.xml\n", encoding="utf-8")
    rss = "".join(f'<item><title>{esc(g["title"])}</title><link>{esc(base + path_for(g, "en"))}</link>'
                  f'<guid>{esc(base + path_for(g, "en"))}</guid></item>' for g in items)
    (SITE / "feed.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>{esc(cfg["name"]["en"])}</title>'
        f'<link>{esc(base)}/</link><description>{esc(T["en"]["tag"])}</description>{rss}</channel></rss>',
        encoding="utf-8")


def tg_send(token, chat, text):
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=json.dumps({"chat_id": chat, "text": text, "parse_mode": "HTML"}).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status == 200


def message(g, lang, cfg):
    L, base = T[lang], (cfg.get("site_url") or "").rstrip("/")
    link = base + path_for(g, lang) if base else g["claim"]
    was = f'<s>{esc(g["worth"])}</s> ' if has_worth(g) else ""
    return (f'<b>{esc(g["title"])}</b>\n{was}<b>{L["free"]}</b> - {esc(g["platforms"])}\n'
            f'{esc(fmt_end(g["end"], L))}\n\n{link}')


def post_new(items, cfg):
    """Post new giveaways to Telegram (max 5 per run). Without Telegram secrets, just stay in sync silently."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chats = {"en": os.environ.get("TELEGRAM_CHAT_EN", ""), "ar": os.environ.get("TELEGRAM_CHAT_AR", "")}
    sf = STATE / "posted.json"
    posted = json.loads(sf.read_text()) if sf.exists() else None
    ids = [g["id"] for g in items]
    STATE.mkdir(exist_ok=True)
    if posted is None or not (token and any(chats.values())):
        # first run, or Telegram not set up: remember what exists so we never flood a channel later
        sf.write_text(json.dumps(sorted(set((posted or []) + ids))[-400:]))
        return 0
    sent = []
    for g in [g for g in items if g["id"] not in posted][:5]:
        try:
            for lang, chat in chats.items():
                if chat:
                    tg_send(token, chat, message(g, lang, cfg))
                    time.sleep(1.5)
            sent.append(g["id"])
        except Exception as e:
            print(f'telegram failed for {g["id"]}: {e}', file=sys.stderr)
    sf.write_text(json.dumps(sorted(set(posted + sent))[-400:]))
    return len(sent)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main():
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    items = load_items()[: int(cfg.get("max_items", 40))]
    shutil.rmtree(SITE, ignore_errors=True)  # expired giveaways disappear with their pages
    for lang in T:
        out = SITE / ("ar" if lang == "ar" else "")
        write(out / "index.html", index_page(items, lang, cfg))
        for g in items:
            write(SITE / path_for(g, lang).lstrip("/"), detail_page(g, lang, cfg))
    extras(items, cfg)
    n = post_new(items, cfg)
    print(f"built {len(items)} giveaways, posted {n} to Telegram")


if __name__ == "__main__":
    main()
