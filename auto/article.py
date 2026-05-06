#!/usr/bin/env python3
"""Generate one Austrian Wirtschaftsstrafrecht article end-to-end and post it.

usage: article.py <topic_index>
"""
import os, sys, json, time, base64, subprocess, urllib.request, urllib.error, html

BASE = "/home/student/Projects/wirtschaftsstrafrecht-heute"
OR_KEY = os.environ["OPENROUTER_API_KEY"]
OAI_KEY = os.environ["OPENAI_API_KEY"]
SM_KEY = os.environ.get("SIMPLEMESSAGE_API_KEY", "")
SITE = "https://nichtagentur.github.io/wirtschaftsstrafrecht-heute"
RAW = "https://raw.githubusercontent.com/nichtagentur/wirtschaftsstrafrecht-heute/main"

idx = int(sys.argv[1])
TOPICS = json.load(open(f"{BASE}/auto/topics.json"))
t = TOPICS[idx]
slug = t["slug"]
print(f"[{time.strftime('%H:%M:%S')}] === topic #{idx} {slug} ===", flush=True)

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
def http(url, *, method="GET", body=None, headers=None, timeout=180):
    h = {"User-Agent": UA}
    if headers: h.update(headers)
    req = urllib.request.Request(url, data=body, method=method, headers=h)
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        msg = e.read().decode()[:1500]
        print(f"HTTP {e.code} on {url}: {msg}", flush=True)
        raise

def or_chat(prompt, model="google/gemini-2.5-flash-lite"):
    body = json.dumps({
        "model": model,
        "messages":[{"role":"user","content":prompt}],
        "temperature":0.45,
    }).encode()
    r = http("https://openrouter.ai/api/v1/chat/completions", method="POST", body=body,
             headers={"Authorization": f"Bearer {OR_KEY}", "Content-Type":"application/json"})
    return json.loads(r.read())["choices"][0]["message"]["content"]

def gen_image(prompt, out_png):
    body = json.dumps({
        "model":"gpt-image-1","prompt":prompt,
        "size":"1536x1024","quality":"low","n":1,
    }).encode()
    r = http("https://api.openai.com/v1/images/generations", method="POST", body=body,
             headers={"Authorization": f"Bearer {OAI_KEY}", "Content-Type":"application/json"})
    d = json.loads(r.read())
    open(out_png,"wb").write(base64.b64decode(d["data"][0]["b64_json"]))

def gen_video(first_frame, prompt, duration, out_mp4):
    b64 = base64.b64encode(open(first_frame,"rb").read()).decode()
    body = json.dumps({
        "model":"alibaba/wan-2.7","prompt":prompt,"duration":duration,
        "aspect_ratio":"16:9",
        "frame_images":[{"type":"image_url","image_url":{"url":f"data:image/jpeg;base64,{b64}"},"frame_type":"first_frame"}],
    }).encode()
    r = http("https://openrouter.ai/api/v1/videos", method="POST", body=body,
             headers={"Authorization": f"Bearer {OR_KEY}", "Content-Type":"application/json"})
    job = json.loads(r.read())["id"]
    deadline = time.time()+360
    while time.time() < deadline:
        time.sleep(8)
        s = http(f"https://openrouter.ai/api/v1/videos/{job}",
                 headers={"Authorization": f"Bearer {OR_KEY}"})
        st = json.loads(s.read())["status"]
        if st == "completed": break
        if st in ("failed","error","cancelled"): raise RuntimeError(f"video {st}")
    c = http(f"https://openrouter.ai/api/v1/videos/{job}/content?index=0",
             headers={"Authorization": f"Bearer {OR_KEY}"}, timeout=300)
    open(out_mp4,"wb").write(c.read())

# ---- 1. Article body via OpenRouter --------------------------------------
prompt = f"""Du bist Fachredakteur fuer oesterreichisches Wirtschaftsstrafrecht.
Schreibe einen Beitrag in deutscher Sprache zum folgenden Thema. Stand: 06.05.2026.

THEMA: {t['title']}
LEITFRAGE: {t['lead']}
KONTEXT: {t['context']}

Stil: praezise, sachlich, fundiert, fuer juristisch vorgebildete Leser.
Laenge: 1100-1400 Worte.

WICHTIG: Gib AUSSCHLIESSLICH ein HTML-Fragment zurueck (ohne <html>, <head>, <body>).
Verwende KEINE Umlaute -- ersetze ae/oe/ue/ss durch die ASCII-Variante. Verwende &sect; statt §.

Struktur exakt in dieser Reihenfolge:
1) Eine Einleitung als <p class="deck">...</p>
2) Eine kurze Inhaltsuebersicht: <div class="toc"><strong>Inhalt</strong><ol><li><a href="#sect1">..</a></li>...</ol></div>
3) 4-5 Hauptabschnitte: <h2 id="sect1">..</h2><p>..</p> ggf <h3>..</h3>, <ul><li>..</li></ul>
4) Genau ein <blockquote>..</blockquote> mit einer pointierten Aussage
5) Mindestens ein <div class="callout"><strong>Praxis-Tipp:</strong> ..</div>
6) Schlussabschnitt: <h2 id="fazit">Fazit</h2><p>..</p>
7) Quellen: <div class="sources"><h3>Quellen</h3><ol><li>..</li>..</ol></div>

Quellen muessen tatsaechlich existierende oesterreichische Rechtsquellen sein
(Gesetze, EU-Verordnungen). Erfinde KEINE konkreten OGH-Aktenzahlen --
zitiere nur Gesetzestexte. Aktuelle Bezuege auf 2026 sind erwuenscht.
Keine Floskeln, kein Marketing, keine ich-Form, kein "Wir bei...".
"""

print(f"[{time.strftime('%H:%M:%S')}] generating article body...", flush=True)
body = or_chat(prompt).strip()
# strip code fences if model added them
if body.startswith("```"):
    body = body.split("\n",1)[1]
    if body.endswith("```"): body = body[:-3]
    body = body.replace("```html","").replace("```","").strip()

# ---- 2. Hero image -------------------------------------------------------
print(f"[{time.strftime('%H:%M:%S')}] generating image...", flush=True)
img_png = f"{BASE}/images/{slug}.png"
gen_image(t["image_prompt"], img_png)
img_jpg = f"{BASE}/images/{slug}.jpg"
img_sm  = f"{BASE}/images/{slug}-sm.jpg"
subprocess.run(["convert", img_png, "-resize","1600x","-quality","82","-strip", img_jpg], check=True)
subprocess.run(["convert", img_png, "-resize","800x","-quality","80","-strip", img_sm], check=True)
os.unlink(img_png)

# ---- 3. Video (only if topic asks) --------------------------------------
video_block = ""
if t.get("with_video"):
    print(f"[{time.strftime('%H:%M:%S')}] generating video...", flush=True)
    raw_mp4 = f"{BASE}/images/{slug}-raw.mp4"
    web_mp4 = f"{BASE}/images/{slug}-web.mp4"
    try:
        gen_video(img_jpg, t["video_prompt"], 5, raw_mp4)
        subprocess.run(["ffmpeg","-y","-i",raw_mp4,"-vf","scale=720:-2",
                        "-c:v","libx264","-crf","26","-preset","veryfast",
                        "-c:a","aac","-b:a","96k","-movflags","+faststart",
                        web_mp4,"-loglevel","error"], check=True)
        os.unlink(raw_mp4)
        rel = f"/wirtschaftsstrafrecht-heute/images/{slug}-web.mp4"
        poster = f"/wirtschaftsstrafrecht-heute/images/{slug}.jpg"
        video_block = (
            f'<figure style="margin:1.6rem 0">'
            f'<video controls preload="metadata" poster="{poster}" '
            f'style="width:100%;border-radius:4px;display:block">'
            f'<source src="{rel}" type="video/mp4"></video>'
            f'<figcaption style="font-family:var(--sans);font-size:.8rem;'
            f'color:var(--ink-dim);margin-top:.5rem">'
            f'Generative Bewegtbild-Illustration zum Thema. '
            f'KI-erzeugt mit Wan 2.7.</figcaption></figure>'
        )
    except Exception as e:
        print(f"video skipped: {e}", flush=True)

# ---- 4. Compose full HTML page -------------------------------------------
date_iso = "2026-05-06"
title_full = t["title"]
title_safe = title_full.replace("&sect;","Paragraf").replace("&middot;","-").replace("&mdash;","-")
canonical = f"{SITE}/articles/{slug}.html"
img_url = f"{SITE}/images/{slug}.jpg"

# Meta description: short version of lead
meta_desc = t["lead"].replace("&sect;","Paragraf").replace("&middot;","-")[:300]

article_html = f"""<!doctype html>
<html lang="de-AT">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title_safe} &mdash; Wirtschaftsstrafrecht Heute</title>
<meta name="description" content="{meta_desc}">
<meta name="robots" content="index,follow,max-image-preview:large">
<meta name="author" content="Redaktion Wirtschaftsstrafrecht Heute">
<link rel="canonical" href="{canonical}">
<link rel="stylesheet" href="/wirtschaftsstrafrecht-heute/assets/style.css">
<meta property="og:title" content="{title_safe}">
<meta property="og:description" content="{meta_desc}">
<meta property="og:type" content="article">
<meta property="og:image" content="{img_url}">
<meta property="article:published_time" content="{date_iso}">
<meta name="twitter:card" content="summary_large_image">
<script type="application/ld+json">
{{
  "@context":"https://schema.org",
  "@type":"NewsArticle",
  "headline":{json.dumps(title_safe)},
  "description":{json.dumps(meta_desc)},
  "image":"{img_url}",
  "datePublished":"{date_iso}",
  "dateModified":"{date_iso}",
  "inLanguage":"de-AT",
  "author":{{"@type":"Organization","name":"Redaktion Wirtschaftsstrafrecht Heute"}},
  "publisher":{{"@type":"Organization","name":"Wirtschaftsstrafrecht Heute","url":"{SITE}/"}},
  "mainEntityOfPage":"{canonical}"
}}
</script>
</head>
<body>
<header class="site">
  <a class="brand" href="/wirtschaftsstrafrecht-heute/">Wirtschaftsstrafrecht <span>Heute</span></a>
  <nav><a href="/wirtschaftsstrafrecht-heute/">Startseite</a><a href="/wirtschaftsstrafrecht-heute/about.html">Redaktion</a><a href="/wirtschaftsstrafrecht-heute/impressum.html">Impressum</a></nav>
</header>

<section class="hero">
  <img src="/wirtschaftsstrafrecht-heute/images/{slug}.jpg" alt="Hero-Visual zum Beitrag {title_safe}">
  <div class="overlay">
    <div class="kicker">{t['topic_kicker']}</div>
    <h1>{title_full}</h1>
    <p class="lede">{t['lead']}</p>
  </div>
</section>

<main>
<article class="post">
  <div class="topic">{t['topic_kicker']}</div>
  <h1>{title_full}</h1>
  <div class="byline">
    <span>Von der <strong>Redaktion Wirtschaftsstrafrecht Heute</strong></span>
    <span>Veroeffentlicht 06.05.2026 &middot; Stand 06.05.2026</span>
  </div>

  {video_block}

  {body}

  <div class="author-card">
    <div class="avatar">WH</div>
    <div class="meta">
      <strong>Redaktion Wirtschaftsstrafrecht Heute</strong>
      Wir analysieren aktuelle Entwicklungen aus OGH-Rechtsprechung, EU-Regulierung und Compliance-Praxis &mdash; mit Schwerpunkt Oesterreich. Beitraege werden vor Veroeffentlichung redaktionell gegengelesen.
    </div>
  </div>

  <div class="disclaimer">
    <strong>Hinweis:</strong> Dieser Beitrag dient der allgemeinen Information ueber aktuelle Rechtsentwicklungen in Oesterreich und ersetzt keine anwaltliche Beratung im Einzelfall. Diese Publikation ist eine Demonstration KI-gestuetzter redaktioneller Workflows; jeder Beitrag ist als solcher gekennzeichnet.
  </div>
</article>
</main>

<footer class="site">
  <div>&copy; 2026 Wirtschaftsstrafrecht Heute</div>
  <div style="margin-top:.6rem"><a href="/wirtschaftsstrafrecht-heute/about.html">&Uuml;ber uns</a><a href="/wirtschaftsstrafrecht-heute/impressum.html">Impressum</a><a href="/wirtschaftsstrafrecht-heute/datenschutz.html">Datenschutz</a></div>
</footer>
</body>
</html>
"""

art_path = f"{BASE}/articles/{slug}.html"
open(art_path,"w").write(article_html)
print(f"[{time.strftime('%H:%M:%S')}] wrote {art_path}", flush=True)

# ---- 5. Update index.html: prepend a card --------------------------------
idx_path = f"{BASE}/index.html"
content = open(idx_path).read()

new_card = f"""    <article class="card">
      <a class="thumb" href="/wirtschaftsstrafrecht-heute/articles/{slug}.html"><img src="/wirtschaftsstrafrecht-heute/images/{slug}-sm.jpg" alt="{t['topic_kicker']}"></a>
      <div class="body">
        <div class="topic">{t['topic_kicker']}</div>
        <h2><a href="/wirtschaftsstrafrecht-heute/articles/{slug}.html">{title_full}</a></h2>
        <p class="deck">{t['lead']}</p>
        <div class="meta">06. Mai 2026 &middot; Auto-Beitrag</div>
      </div>
    </article>

"""
# Insert immediately after `<section class="cards">`
content = content.replace('<section class="cards">\n',
                          '<section class="cards">\n'+new_card, 1)
open(idx_path,"w").write(content)

# ---- 6. Update sitemap ----------------------------------------------------
sm_path = f"{BASE}/sitemap.xml"
sm = open(sm_path).read()
new_url = f"  <url><loc>{canonical}</loc><lastmod>{date_iso}</lastmod><priority>0.8</priority></url>\n"
if canonical not in sm:
    sm = sm.replace("</urlset>", new_url+"</urlset>")
    open(sm_path,"w").write(sm)

# ---- 7. Git push ---------------------------------------------------------
def git(*args):
    return subprocess.run(["git","-c","user.email=github@nichtagentur.at",
                           "-c","user.name=nichtagentur",*args], cwd=BASE, check=True,
                          capture_output=True, text=True)
git("add",".")
git("commit","-qm",f"auto: {title_safe[:80]}")
git("push","-q","origin","main")
print(f"[{time.strftime('%H:%M:%S')}] pushed", flush=True)

# ---- 8. Wait for Pages build, then verify URL serves new content --------
print(f"[{time.strftime('%H:%M:%S')}] waiting for Pages...", flush=True)
url = f"{canonical}"
deadline = time.time()+180
while time.time() < deadline:
    code = subprocess.run(["curl","-s","-o","/dev/null","-w","%{http_code}",
                           f"{url}?cb={int(time.time())}"], capture_output=True, text=True).stdout
    if code == "200":
        # check that the title appears
        page = subprocess.run(["curl","-s",f"{url}?cb={int(time.time())}"],
                              capture_output=True, text=True).stdout
        if slug in page or title_full[:40] in page:
            break
    time.sleep(6)
print(f"[{time.strftime('%H:%M:%S')}] live", flush=True)

# ---- 9. Headless screenshot via Chrome -----------------------------------
shot_png = f"{BASE}/screens/auto-{slug}.png"
shot_jpg = f"{BASE}/screens/auto-{slug}.jpg"
subprocess.run([
    "google-chrome","--headless=new","--no-sandbox","--disable-gpu",
    "--hide-scrollbars",
    f"--screenshot={shot_png}",
    "--window-size=1280,1500",
    f"{url}?cb={int(time.time())}"
], check=True, timeout=90)
subprocess.run(["convert", shot_png, "-resize","1100x","-quality","82", shot_jpg], check=True)
os.unlink(shot_png)

git("add", f"screens/auto-{slug}.jpg")
git("commit","-qm",f"auto: shot {slug}")
git("push","-q","origin","main")

# wait briefly for raw.githubusercontent to serve the new file
shot_url = f"{RAW}/screens/auto-{slug}.jpg"
for _ in range(20):
    code = subprocess.run(["curl","-s","-o","/dev/null","-w","%{http_code}", shot_url],
                          capture_output=True, text=True).stdout
    if code == "200": break
    time.sleep(3)

# ---- 10. Post to simplemessage ------------------------------------------
preview = t["lead"][:260]
post_text = (
    f"**Neuer Auto-Beitrag:** {title_safe}\n\n"
    f"{preview}\n\n"
    f"![shot]({shot_url})\n\n"
    f"Live: {url}"
)
if len(post_text) > 990:
    post_text = post_text[:980] + "..."

body = json.dumps({"text": post_text}).encode()
r = http("https://simplemessage.franzai.com/api/messages", method="POST", body=body,
         headers={"Authorization": f"Bearer {SM_KEY}", "Content-Type":"application/json"})
print(f"[{time.strftime('%H:%M:%S')}] simplemessage:", json.loads(r.read()).get("id"), flush=True)
print(f"[{time.strftime('%H:%M:%S')}] done #{idx} {slug}", flush=True)
