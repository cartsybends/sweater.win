#!/usr/bin/env python3
"""Split the generated Sweater site into a tiny crawler-friendly homepage and the full app bundle.

The browser still stays on the root URL: index.html fetches app.html and replaces the
current document. Link-preview crawlers get a small HTML response with complete Open
Graph metadata instead of downloading the multi-megabyte game page.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", default="site", help="generated site directory")
    parser.add_argument("--site-url", required=True, help="public site URL, e.g. https://sweater.win/")
    args = parser.parse_args()

    site_url = args.site_url.strip()
    if not site_url:
        raise SystemExit("--site-url cannot be empty")
    if not site_url.endswith("/"):
        site_url += "/"

    site_dir = Path(args.site).resolve()
    index = site_dir / "index.html"
    app = site_dir / "app.html"

    if not index.exists():
        raise SystemExit(f"Missing generated homepage: {index}")

    full_app = index.read_text(encoding="utf-8")
    if full_app.count('"headshot"') < 100:
        raise SystemExit("Generated homepage does not look like the full Sweater app; refusing to split it.")

    app.write_text(full_app, encoding="utf-8")

    image_url = f"{site_url}sweater-trivia-preview.png"
    shell = f"""<!doctype html>
<html lang="en" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sweater | NHL Trivia, Hockey Quizzes & Daily Games</title>
<meta name="description" content="Sweater is an NHL trivia and hockey quiz platform with daily player challenges, team and history games, awards, stats, and NHL EDGE tracking data.">
<meta name="robots" content="index,follow,max-image-preview:large,max-snippet:-1,max-video-preview:-1">
<meta name="application-name" content="Sweater">
<meta name="apple-mobile-web-app-title" content="Sweater">
<link rel="canonical" href="{site_url}">
<link rel="manifest" href="sweater.webmanifest">
<link rel="apple-touch-icon" href="sweater-icon.svg">
<meta name="theme-color" content="#111113">

<meta property="og:type" content="website">
<meta property="og:site_name" content="Sweater">
<meta property="og:title" content="Sweater · Daily NHL Trivia">
<meta property="og:description" content="Test your hockey knowledge with daily player guessing, Trophy Case, Playoff History, and more.">
<meta property="og:url" content="{site_url}">
<meta property="og:image" content="{image_url}">
<meta property="og:image:secure_url" content="{image_url}">
<meta property="og:image:type" content="image/png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="Sweater · Daily NHL Trivia">

<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="Sweater · Daily NHL Trivia">
<meta name="twitter:description" content="Test your hockey knowledge with daily player guessing, Trophy Case, Playoff History, and more.">
<meta name="twitter:image" content="{image_url}">

<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "WebSite",
  "name": "Sweater",
  "alternateName": ["Sweater NHL Trivia", "Sweater Hockey Trivia"],
  "url": "{site_url}",
  "description": "Sweater is an NHL trivia and hockey quiz platform with daily player challenges, team and history games, awards, stats, and NHL EDGE tracking data.",
  "inLanguage": "en"
}}
</script>

<style>
html,body{{margin:0;min-height:100%;background:#111113;color:#f5f5f7;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
body{{display:grid;place-items:center;padding:24px;text-align:center}}
a{{color:#fff}}
</style>
</head>
<body>
<p id="status">Opening Sweater…<br><small><a href="app.html">Continue to Sweater</a></small></p>
<script>
(async () => {{
  try {{
    const response = await fetch("./app.html", {{cache: "no-cache"}});
    if (!response.ok) throw new Error("HTTP " + response.status);
    const html = await response.text();
    document.open();
    document.write(html);
    document.close();
  }} catch (error) {{
    const status = document.getElementById("status");
    if (status) status.innerHTML = 'Could not load Sweater.<br><small><a href="app.html">Open the game directly</a></small>';
    console.error("Sweater bootstrap failed:", error);
  }}
}})();
</script>
</body>
</html>
"""
    index.write_text(shell, encoding="utf-8")

    # Keep the full app available offline once the service worker has installed.
    sw = site_dir / "sw.js"
    if sw.exists():
        sw_text = sw.read_text(encoding="utf-8")
        old = 'const CORE = ["./", "./share/",'
        new = 'const CORE = ["./", "./app.html", "./share/",'
        if old in sw_text:
            sw.write_text(sw_text.replace(old, new, 1), encoding="utf-8")
        elif '"./app.html"' not in sw_text:
            raise SystemExit("Could not add app.html to the service-worker core cache.")

    print(f"Preview shell: {index.stat().st_size:,} bytes")
    print(f"Full app:      {app.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
