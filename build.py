#!/usr/bin/env python3
"""Build the AyuRemedy static site.

    python3 build.py            -> public/   (clean URLs, for the live host)
    python3 build.py --preview  -> preview/  (relative index.html links, for the Claude preview)

Pages live in src/pages/*.html. Each starts with a small header block:

    title: Page title
    description: Meta description
    path: treatments/          (empty for the home page)
    nav: treatments            (which nav item is active)
    ---
    <page body html>

Inside page bodies and the layout, write internal links as "@/some/path/" and
the build rewrites them for the target.
"""
import json
import os
import re
import hashlib
import shutil
import subprocess
import datetime
from html import escape as html_escape, unescape as html_unescape
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
SITE = "https://www.ayuremedy.com"
PREVIEW = "--preview" in sys.argv
# GA4 measurement ID ("G-XXXXXXXXXX"). Empty means no analytics tag is added; the preview never gets one.
GA_ID = "G-ZJWDXWQ7RV"
OUT = os.path.join(ROOT, "preview" if PREVIEW else "public")

CLINIC = {
    "@context": "https://schema.org",
    "@type": "MedicalClinic",
    "@id": SITE + "/#clinic",
    "name": "AyurRemedy Ayurveda Clinic, Treatment Centre & Pharmacy",
    "alternateName": ["AyuRemedy", "Ayuremedy"],
    "url": SITE + "/",
    "logo": SITE + "/assets/img/logo.png",
    "image": [SITE + "/assets/img/storefront.jpg", SITE + "/assets/img/reception.jpg"],
    "telephone": "+91-80-48542888",
    "email": "info@ayuremedy.com",
    "priceRange": "₹₹",
    "medicalSpecialty": "Ayurveda",
    "availableService": [{"@type": "MedicalTherapy", "name": n} for n in (
        "Panchakarma", "Shirodhara", "Abhyanga", "Kati Vasti", "Janu Vasti",
        "Kshara Sutra", "Agnikarma", "Swarnabindu Prashana")],
    "address": {
        "@type": "PostalAddress",
        "streetAddress": "#38, Sai Krishna Apartment, TC Palya Main Road, near NeuroCyte Stem Cell",
        "addressLocality": "Ramamurthy Nagar, Bengaluru",
        "addressRegion": "Karnataka",
        "postalCode": "560016",
        "addressCountry": "IN",
    },
    "areaServed": ["Ramamurthy Nagar", "TC Palya", "Hoysala Nagar", "KR Puram", "Horamavu",
                   "Banaswadi", "Kasturi Nagar", "Kalyan Nagar", "Kalkere", "Kammanahalli", "Bengaluru"],
    "openingHoursSpecification": [
        {"@type": "OpeningHoursSpecification",
         "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
         "opens": "09:00", "closes": "20:00"},
        {"@type": "OpeningHoursSpecification", "dayOfWeek": "Sunday", "opens": "09:00", "closes": "13:00"},
    ],
    "geo": {"@type": "GeoCoordinates", "latitude": 13.0157936, "longitude": 77.6680717},
    "hasMap": "https://www.google.com/maps?cid=7949517302550241119",
    "sameAs": [
        "https://www.google.com/maps?cid=7949517302550241119",
        "https://www.facebook.com/Ayuremedy",
        "https://www.instagram.com/ayurremedyclinic/",
        "https://www.youtube.com/channel/UCA_t1cmEZWrdqLav08s4Lgw",
    ],
    "employee": [
        {"@type": "Physician", "name": "Dr Rasmi Johnson", "medicalSpecialty": "Ayurveda",
         "description": "BAMS, MS (Shalya Tantra). Senior physician; Kshara Sutra and para-surgical procedures."},
        {"@type": "Physician", "name": "Dr Harshitha Rai", "medicalSpecialty": "Ayurveda",
         "description": "BAMS, MD, PhD (Ayu). Senior physician; joint, skin and lifestyle disorders."},
    ],
}

# Tells Google which name to show as the site name in results (it was showing "Ayuremedy").
WEBSITE = {
    "@context": "https://schema.org",
    "@type": "WebSite",
    "@id": SITE + "/#website",
    "name": "AyurRemedy",
    "alternateName": ["AyuRemedy", "Ayuremedy", "AyurRemedy Clinic"],
    "url": SITE + "/",
    "publisher": {"@id": SITE + "/#clinic"},
}

# Mirrors the old WordPress menu so every page keeps its address and internal links.
NAV = [
    ("home", "Home", "@/"),
    ("about", "About Us", "@/about-us/"),
    ("doctors", "Our Doctors", "@/our-doctors/"),
    ("Specialities", [
        ("disease", "Disease Management", "@/disease-management/"),
        ("rehab", "Rehabilitation", "@/rehabilitation/"),
        ("natal", "Pre & Post Natal Care", "@/pre-post-natal-care/"),
        ("swarna", "Swarnabindu Prashana", "@/swarnabindu-prashana/"),
        ("wellness", "Wellness", "@/wellness/"),
        ("knee", "Knee Pain & Arthritis", "@/knee-pain-arthritis-treatment/"),
        ("back", "Back Pain & Sciatica", "@/back-pain-sciatica-treatment/"),
        ("piles", "Piles, Fissure & Fistula", "@/piles-fissure-fistula-treatment/"),
        ("pcod", "PCOD / PCOS", "@/pcod-pcos-treatment/"),
        ("skin", "Psoriasis, Eczema & Skin", "@/skin-disease-treatment/"),
    ]),
    ("Services", [
        ("protocol", "Our Protocol", "@/our-protocol/"),
        ("panchakarma", "Panchakarma Treatments", "@/panchakarma-treatments/"),
        ("classical", "Other Classical Treatments", "@/other-classical-treatments/"),
        ("parasurgical", "Kshara Sutra & Para Surgical", "@/para-surgical-procedures/"),
        ("wound", "Wound Management", "@/wound-management/"),
        ("cosmetic", "Cosmetic Treatment", "@/cosmetic-treatment/"),
        ("hydra", "Ayurvedic Hydra Facial", "@/ayurvedic-hydra-facial/"),
    ]),
    ("faq", "FAQs", "@/faqs/"),
    ("Gallery", [
        ("images", "Image Gallery", "@/image-gallery/"),
        ("videos", "Video Gallery", "@/video-gallery/"),
        ("tips", "Health Tips", "@/health-tips/"),
    ]),
    ("contact", "Contact Us", "@/contact-us/"),
]


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def parse_page(text):
    head, body = text.split("\n---\n", 1)
    meta = {}
    for line in head.strip().splitlines():
        k, _, v = line.partition(":")
        meta[k.strip()] = v.strip()
    return meta, body


def rewrite_links(html, page_path):
    depth = page_path.count("/")
    rel = "../" * depth

    def repl(m):
        target = m.group(1)
        frag = ""
        if "#" in target:
            target, frag = target.split("#", 1)
            frag = "#" + frag
        if not PREVIEW:
            return "/" + target + frag
        if target == "" or target.endswith("/"):
            return rel + target + "index.html" + frag
        return rel + target + frag

    return re.sub(r"@/([^\"'\s)>]*)", repl, html)


ASIDE = """<aside class="aside" aria-label="Book and explore">
  <h2>Book a consultation</h2>
  <p class="small muted">Share your details and the clinic will call you to confirm a time with Dr Rasmi Johnson or Dr Harshitha Rai.</p>
  <a class="btn btn-primary" href="@/book-appointment/">Book Appointment</a>
  <p class="small muted">Call <a href="tel:+918048542888">080-4854 2888</a> or WhatsApp <a href="https://wa.me/919448150492" target="_blank" rel="noopener">+91 94481 50492</a></p>
  <h2 style="font-size:1.05rem;margin-top:0.5rem">Specialities</h2>
  <ul class="small" style="margin:0;padding-left:1.1rem;display:grid;gap:0.25rem">
    <li><a href="@/disease-management/">Disease Management</a></li>
    <li><a href="@/rehabilitation/">Rehabilitation</a></li>
    <li><a href="@/pre-post-natal-care/">Pre &amp; Post Natal Care</a></li>
    <li><a href="@/swarnabindu-prashana/">Swarnabindu Prashana</a></li>
    <li><a href="@/wellness/">Wellness</a></li>
  </ul>
  <h2 style="font-size:1.05rem;margin-top:0.5rem">Conditions</h2>
  <ul class="small" style="margin:0;padding-left:1.1rem;display:grid;gap:0.25rem">
    <li><a href="@/knee-pain-arthritis-treatment/">Knee pain &amp; arthritis</a></li>
    <li><a href="@/back-pain-sciatica-treatment/">Back pain &amp; sciatica</a></li>
    <li><a href="@/piles-fissure-fistula-treatment/">Piles, fissure &amp; fistula</a></li>
    <li><a href="@/pcod-pcos-treatment/">PCOD / PCOS</a></li>
    <li><a href="@/skin-disease-treatment/">Psoriasis, eczema &amp; skin</a></li>
  </ul>
  <h2 style="font-size:1.05rem;margin-top:0.5rem">Services</h2>
  <ul class="small" style="margin:0;padding-left:1.1rem;display:grid;gap:0.25rem">
    <li><a href="@/our-protocol/">Our Protocol</a></li>
    <li><a href="@/panchakarma-treatments/">Panchakarma Treatments</a></li>
    <li><a href="@/other-classical-treatments/">Other Classical Treatments</a></li>
    <li><a href="@/para-surgical-procedures/">Kshara Sutra Treatment</a></li>
    <li><a href="@/wound-management/">Wound Management</a></li>
    <li><a href="@/cosmetic-treatment/">Cosmetic Treatment</a></li>
    <li><a href="@/ayurvedic-hydra-facial/">Ayurvedic Hydra Facial</a></li>
  </ul>
</aside>"""


def last_changed(path):
    """Date (YYYY-MM-DD) of the last commit that touched a page, for the sitemap; today if it is uncommitted."""
    try:
        out = subprocess.run(["git", "log", "-1", "--format=%cs", "--", path], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        out = ""
    return out or datetime.date.today().isoformat()


def asset_version(rel):
    """Short content hash, appended to asset links so browsers fetch new copies after a change."""
    with open(os.path.join(ROOT, rel), "rb") as f:
        return hashlib.sha1(f.read()).hexdigest()[:8]


def breadcrumbs(body, path):
    """BreadcrumbList built from the page's visible crumbs, so the two always match."""
    m = re.search(r'<p class="crumbs">(.*?)</p>', body)
    if not m:
        return None
    items = []
    parts = m.group(1).split(" / ")
    for i, part in enumerate(parts):
        link = re.match(r'<a href="@/(.*?)">(.*?)</a>$', part.strip())
        if link:
            items.append((link.group(2), SITE + "/" + link.group(1)))
        elif i == len(parts) - 1:
            items.append((re.sub(r"<.*?>", "", part).strip(), SITE + "/" + path))
    return {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i, "name": html_unescape(name), "item": url}
        for i, (name, url) in enumerate(items, 1)]}


def build_page(layout, meta, body):
    body = body.replace("<!--aside-->", ASIDE)
    layout = (layout
              .replace("@/assets/css/site.css", "@/assets/css/site.css?v=" + asset_version("assets/css/site.css"))
              .replace("@/assets/js/site.js", "@/assets/js/site.js?v=" + asset_version("assets/js/site.js"))
              .replace("@/assets/img/logo.png", "@/assets/img/logo.png?v=" + asset_version("assets/img/logo.png")))
    path = meta.get("path", "")
    active = meta.get("nav", "")
    nav_parts, menu_parts = [], []
    for item in NAV:
        if isinstance(item[1], list):
            group, children = item
            is_active = any(key == active for key, _, _ in children)
            links = "".join('<a href="{}"{}>{}</a>'.format(h, ' aria-current="page"' if k == active else "", html_escape(l))
                            for k, l, h in children)
            nav_parts.append('<div class="drop{}"><button type="button" aria-haspopup="true">{}</button>'
                             '<div class="drop-panel">{}</div></div>'.format(" active" if is_active else "", group, links))
            menu_parts.append('<span class="group">{}</span>'.format(group))
            menu_parts += ['<a class="sub" href="{}">{}</a>'.format(h, html_escape(l)) for k, l, h in children]
        else:
            key, label, href = item
            nav_parts.append('<a href="{}"{}>{}</a>'.format(href, ' aria-current="page"' if key == active else "", label))
            menu_parts.append('<a href="{}">{}</a>'.format(href, label))
    menu_parts.append('<a href="@/book-appointment/">Book Appointment</a>')
    nav_html, menu_html = "\n".join(nav_parts), "\n".join(menu_parts)
    crumbs = breadcrumbs(body, path)
    nodes = [WEBSITE, CLINIC] if path == "" else [CLINIC, crumbs] if crumbs else CLINIC
    schema = json.dumps(nodes, ensure_ascii=False, indent=1)
    analytics = ""
    if GA_ID and not PREVIEW:
        # Google signals and ad personalisation stay off: this is a clinic site, so no audience building.
        analytics = ('<script async src="https://www.googletagmanager.com/gtag/js?id={0}"></script>\n'
                     '<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}'
                     'gtag("js",new Date());gtag("config","{0}",{{allow_google_signals:false,'
                     'allow_ad_personalization_signals:false}});</script>').format(GA_ID)
    lang = meta.get("lang", "en-IN")
    alternates = ""
    if meta.get("alt"):
        # Pages that exist in English and Kannada point at each other so Google shows the right one.
        other = "" if meta["alt"] == "/" else meta["alt"]
        en_path, kn_path = (other, path) if lang.startswith("kn") else (path, other)
        alternates = ('<link rel="alternate" hreflang="en-IN" href="{0}/{1}">\n'
                      '<link rel="alternate" hreflang="kn-IN" href="{0}/{2}">\n'
                      '<link rel="alternate" hreflang="x-default" href="{0}/{1}">').format(SITE, en_path, kn_path)
    if "<!--byline-->" in body:
        d = datetime.date.fromisoformat(meta.get("_updated", datetime.date.today().isoformat()))
        body = body.replace("<!--byline-->", '<p class="byline">Written by the AyurRemedy clinical team · Updated {} {} {}</p>'
                            .format(d.day, d.strftime("%B"), d.year))
    html = (layout
            .replace("{{lang}}", lang)
            .replace("{{alternates}}", alternates)
            .replace("{{title}}", meta["title"])
            .replace("{{description}}", meta["description"])
            .replace("{{canonical}}", SITE + "/" + path)
            .replace("{{nav}}", nav_html)
            .replace("{{menu}}", menu_html)
            .replace("{{schema}}", schema)
            .replace("{{analytics}}", analytics)
            .replace("{{body}}", body))
    return rewrite_links(html, path)


def main():
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    shutil.copytree(os.path.join(ROOT, "assets"), os.path.join(OUT, "assets"))
    # Same files, same paths as the old WordPress uploads, so old image links keep working.
    shutil.copytree(os.path.join(ROOT, "wp-content"), os.path.join(OUT, "wp-content"))
    shutil.copy(os.path.join(ROOT, "src", "favicon.ico"), os.path.join(OUT, "favicon.ico"))
    layout = read(os.path.join(ROOT, "src", "layout.html"))
    urls = []
    pages_dir = os.path.join(ROOT, "src", "pages")
    for name in sorted(os.listdir(pages_dir)):
        if not name.endswith(".html"):
            continue
        meta, body = parse_page(read(os.path.join(pages_dir, name)))
        meta["_updated"] = last_changed(os.path.join(pages_dir, name))
        path = meta.get("path", "")
        if name == "404.html":
            dest = os.path.join(OUT, "404.html")
        else:
            dest = os.path.join(OUT, path, "index.html")
            urls.append((SITE + "/" + path, last_changed(os.path.join(pages_dir, name))))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8") as f:
            f.write(build_page(layout, meta, body))
    if PREVIEW:
        # The Claude preview wraps the main page in its own document skeleton.
        home = os.path.join(OUT, "index.html")
        html = read(home)
        for tag in ("<!doctype html>\n", '<html lang="en-IN">\n', "<head>\n", "</head>\n<body>\n", "</body>\n</html>"):
            html = html.replace(tag, "", 1)
        html = re.sub(r"<title>.*?</title>", "<title>AyuRemedy Clinic Website</title>", html, count=1)
        with open(home, "w", encoding="utf-8") as f:
            f.write(html)
    else:
        # Root files, including Google Search Console verification files (google<id>.html).
        verify = [n for n in os.listdir(os.path.join(ROOT, "src")) if re.match(r"google[0-9a-f]+\.html$", n)]
        for extra in [".htaccess", "_redirects", "robots.txt"] + verify:
            src = os.path.join(ROOT, "src", extra)
            if os.path.exists(src):
                shutil.copy(src, os.path.join(OUT, extra))
        # GitHub Pages has no server-side redirects, so leftover WordPress addresses get small forwarding pages.
        for old, new in (("home", "/"), ("author/ayuremedy", "/about-us/"), ("feed", "/")):
            d = os.path.join(OUT, old)
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as f:
                f.write('<!doctype html><meta charset="utf-8"><title>AyurRemedy</title>'
                        '<link rel="canonical" href="{0}{1}"><meta name="robots" content="noindex">'
                        '<meta http-equiv="refresh" content="0; url={1}"><a href="{1}">Continue to AyurRemedy</a>'.format(SITE, new))
        with open(os.path.join(OUT, "CNAME"), "w") as f:
            f.write("www.ayuremedy.com\n")
        open(os.path.join(OUT, ".nojekyll"), "w").close()
        sitemap = ['<?xml version="1.0" encoding="UTF-8"?>',
                   '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
        sitemap += ["  <url><loc>{}</loc><lastmod>{}</lastmod></url>".format(u, d) for u, d in urls]
        sitemap.append("</urlset>")
        with open(os.path.join(OUT, "sitemap.xml"), "w", encoding="utf-8") as f:
            f.write("\n".join(sitemap) + "\n")
    print("Built {} pages into {}".format(len(urls), OUT))


if __name__ == "__main__":
    main()
