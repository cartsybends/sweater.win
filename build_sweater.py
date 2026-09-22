#!/usr/bin/env python3
"""
Build Sweater (NHL player guessing game) with current data from NHL.com.

Pulls every team's current roster from the NHL's public web API
(api-web.nhle.com, the same data that powers nhl.com), including each
player's official NHL.com headshot, and writes a ready-to-play sweater.html.

Usage:
    python build_sweater.py              # players with an assigned sweater number
    python build_sweater.py --min-games 1   # include anyone with an NHL game recently
    python build_sweater.py --all        # everyone on the roster, no filters

Standard library only. Everything the game needs is inside this one file.
"""
import argparse
import random
import shutil
import json
import sys
import time
from concurrent.futures import TimeoutError as FuturesTimeout, as_completed
from concurrent.futures import ThreadPoolExecutor
import traceback
import webbrowser
import re
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

API = "https://api-web.nhle.com/v1/roster/{team}/current"
STATS = ("https://api.nhle.com/stats/rest/en/{kind}/summary?limit=-1"
         "&cayenneExp=seasonId={season}%20and%20gameTypeId=2")
TEAMS = [
    "BOS", "BUF", "DET", "FLA", "MTL", "OTT", "TBL", "TOR",
    "CAR", "CBJ", "NJD", "NYI", "NYR", "PHI", "PIT", "WSH",
    "CHI", "COL", "DAL", "MIN", "NSH", "STL", "UTA", "WPG",
    "ANA", "CGY", "EDM", "LAK", "SEA", "SJS", "VAN", "VGK",
]
HERE = Path(__file__).resolve().parent
VERSION = "62 · Map Zoom Feel"


TEMPLATE = r'''<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sweater · Daily NHL Trivia</title>
<meta name="description" content="Daily NHL trivia with player guessing, Trophy Case, Playoff History, and more hockey challenges.">
<meta name="theme-color" content="#0b0b0c">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Sweater">
<meta property="og:title" content="Sweater · Daily NHL Trivia">
<meta property="og:description" content="Test your hockey knowledge with daily player guessing, Trophy Case, Playoff History, and more.">
<meta property="og:url" content="/*__SITE__*/">
<meta property="og:image" content="/*__SITE__*/sweater-trivia-preview.png">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="Sweater · Daily NHL Trivia">
<meta name="twitter:description" content="Test your hockey knowledge with daily player guessing, Trophy Case, Playoff History, and more.">
<meta name="twitter:image" content="/*__SITE__*/sweater-trivia-preview.png">
<meta name="theme-color" content="#111113">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<link rel="manifest" href="sweater.webmanifest">
<link rel="apple-touch-icon" href="sweater-icon.svg">
<link rel="icon" type="image/svg+xml" sizes="any" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='5' fill='%230b0b0c'/%3E%3Cpath fill='%23f4f4f5' d='M11 4h12v3H11zM8 7h3v6H8zM11 13h9v3h-9zM20 16h3v6h-3zM8 22h12v3H8z'/%3E%3Cpath fill='%237950f2' d='M8 28h15v2H8z'/%3E%3C/svg%3E">
<script>
  // Apply saved appearance choices before the page paints.
  try {
    const root = document.documentElement, theme = JSON.parse(localStorage.getItem("sweater-theme"));
    const accent = JSON.parse(localStorage.getItem("sweater-accent"));
    if (theme) root.dataset.theme = theme;
    if (/^#[0-9a-f]{6}$/i.test(accent || "")) root.style.setProperty("--accent", accent);
  } catch {}
</script>
<style>
  :root {
    --bg: #ffffff; --fg: #111; --muted: #666; --cell: #ebebeb; --cell-fg: #222;
    --hit: #528f4f; --hit-fg: #fff; --near: #e3b83b; --near-fg: #1d1a10; --line: #ddd; --link: #1a6f7a;
    --panel: #fff; --scrim: rgba(0,0,0,.5); --cream: #f3e9d2; --silbg: transparent;
    --sea: #dfe9f3; --land: #f3e9d2; --coast: #b9ab8c;
    --grouped: #f2f2f7; --row: #ffffff; --sep: rgba(60,60,67,.14); --label2: #6e6e73;
  }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {
      --bg: #16181b; --fg: #eee; --muted: #9aa; --cell: #2a2d31; --cell-fg: #e6e6e6;
      --hit: #4f8a4c; --hit-fg: #fff; --near: #c9a227; --near-fg: #17140a; --line: #33373c; --link: #6cc3cf;
      --panel: #1f2226; --scrim: rgba(0,0,0,.7); --silbg: var(--cream);
      --sea: #1b2a38; --land: #3a3f46; --coast: #5c636d;
      --grouped: #000000; --row: #1c1c1e; --sep: rgba(84,84,88,.5); --label2: #98989d;
    }
  }
  :root[data-theme="dark"] {
      --bg: #16181b; --fg: #eee; --muted: #9aa; --cell: #2a2d31; --cell-fg: #e6e6e6;
      --hit: #4f8a4c; --hit-fg: #fff; --near: #c9a227; --near-fg: #17140a; --line: #33373c; --link: #6cc3cf;
      --panel: #1f2226; --scrim: rgba(0,0,0,.7); --silbg: var(--cream);
      --sea: #1b2a38; --land: #3a3f46; --coast: #5c636d;
      --grouped: #000000; --row: #1c1c1e; --sep: rgba(84,84,88,.5); --label2: #98989d;
  }
  body, td, .search input, .list, .card { transition: background-color .3s ease, color .3s ease, border-color .3s ease; }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--bg); color: var(--fg);
         font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI Variable Text", "Segoe UI", Inter, Roboto, Helvetica, Arial, sans-serif;
         -webkit-font-smoothing: antialiased; transition: background-color .3s; }
  body.hubmode { background: var(--grouped); }
  header { text-align: center; padding: 24px 16px 8px; }
  h1 { margin: 0; font-size: 48px; font-weight: 800; letter-spacing: .5px; }
  .sub { margin: 2px 0 14px; font-size: 14px; }
  .linkbtn { background: none; border: 0; color: var(--link); font: inherit;
             font-size: 14px; letter-spacing: .5px; cursor: pointer; padding: 4px 8px; }
  .linkbtn:focus-visible, input:focus-visible, button:focus-visible { outline: 2px solid var(--link); outline-offset: 2px; }
  main { max-width: 1500px; margin: 0 auto; padding: 8px 16px 40px; }
  .search { position: relative; max-width: 1480px; margin: 0 auto 12px; }
  .search input { width: 100%; padding: 16px 14px; font-size: 16px; border: 1px solid #bbb;
                  border-radius: 4px; background: var(--bg); color: var(--fg); }
  .search input:disabled { opacity: .6; }
  .list { position: absolute; left: 0; right: 0; top: 100%; z-index: 5; margin: 2px 0 0;
          padding: 4px 0; list-style: none; background: var(--panel); border: 1px solid var(--line);
          border-radius: 4px; max-height: 300px; overflow-y: auto; box-shadow: 0 6px 18px rgba(0,0,0,.15); }
  .list li { padding: 8px 14px; cursor: pointer; display: flex; justify-content: space-between; gap: 12px; }
  .list li small { color: var(--muted); }
  .list li[aria-selected="true"], .list li:hover { background: var(--cell); }
  .board { overflow-x: auto; }
  [hidden] { display: none !important; }
  .board table { border-collapse: separate; border-spacing: 8px; margin: 0 auto; min-width: 1000px; }
  .board th { font-weight: 400; font-size: 16px; padding: 4px 0 8px; border-bottom: 1px solid var(--line); }
  .board td { height: 72px; background: var(--cell); color: var(--cell-fg); text-align: center;
       font-size: 16px; padding: 0 14px; min-width: 120px; }
  .board td.name { background: none; text-align: left; min-width: 200px; padding-left: 4px; }
  .board td.team { min-width: 90px; }
  .board td.team img { width: 34px; height: 34px; display: block; margin: 0 auto 2px; }
  td.hit { background: var(--hit); color: var(--hit-fg); }
  td.near { background: var(--near); color: var(--near-fg); }

  /* game tabs */
  .tabs { display: inline-flex; gap: 4px; padding: 4px; border: 1px solid var(--line); border-radius: 999px; margin: 2px 0 8px; }
  .tabs button { background: none; border: 0; color: var(--fg); font: inherit; font-size: 15px;
                 padding: 7px 18px; border-radius: 999px; cursor: pointer; transition: background-color .2s, color .2s; }
  .tabs button[aria-selected="true"] { background: var(--fg); color: var(--bg); }
  .tabs.small button { font-size: 13px; padding: 5px 14px; }
  .tabrow { display: flex; justify-content: center; }
  .view { max-width: 1480px; margin: 0 auto; }
  #view-statline .search { max-width: 620px; }
  .ttcard .pname { font-size: 22px; font-weight: 600; margin: 0 0 2px; }
  .ttcard .pmeta { font-size: 14px; color: var(--muted); margin: 0; }
  .intro { text-align: center; color: var(--muted); margin: 6px 0 14px; font-size: 15px; }
  .hint { text-align: center; color: var(--muted); font-size: 14px; margin: 10px 0; }
  .nodata { text-align: center; color: var(--muted); padding: 30px 10px; }

  /* more games */
  .tabs.wrap { flex-wrap: wrap; justify-content: center; border-radius: 18px; max-width: 100%; }
  .search.narrow { max-width: 620px; }
  .jypath { display: flex; flex-wrap: wrap; justify-content: center; align-items: center; gap: 8px; max-width: 900px; margin: 6px auto 12px; }
  .jystop { display: flex; flex-direction: column; align-items: center; gap: 2px; min-width: 104px; padding: 10px 12px;
            border-radius: 10px; background: var(--cell); color: var(--cell-fg); text-align: center; animation: rowin .35s ease both; }
  .jystop img { width: 42px; height: 42px; }
  .jystop b { font-size: 14px; }
  .jystop small { font-size: 12px; opacity: .75; font-variant-numeric: tabular-nums; }
  .jyarrow { color: var(--muted); font-size: 18px; }
  .chips.hints { margin: 0 0 10px; }
  .chip.hintchip { background: var(--near); color: var(--near-fg); display: inline-flex; align-items: center; gap: 4px; animation: rowin .35s ease both; }
  .hintchip img { width: 20px; height: 20px; }
  .blurbox { width: 220px; height: 220px; margin: 4px auto 12px; border-radius: 50%; overflow: hidden; background: var(--cream); }
  .blurbox img { width: 100%; height: 100%; object-fit: cover; transform: scale(1.12); transition: filter .6s ease;
                 user-select: none; -webkit-user-drag: none; }
  .numrow { display: flex; justify-content: center; gap: 8px; margin: 10px auto; max-width: 320px; }
  .numrow.wide { max-width: 560px; }
  .numrow input { flex: 1; min-width: 0; padding: 12px 14px; font-size: 18px; border: 1px solid #bbb; border-radius: 6px;
                  background: var(--bg); color: var(--fg); text-align: center; }
  .numrow.wide input { text-align: left; }
  .numrow .btn { margin: 0; }
  .numrow input:disabled { opacity: .6; }
  .numchip { font-weight: 600; }
  .chips .chip.hit { background: var(--hit); color: var(--hit-fg); }
  .chips .chip.near { background: var(--near); color: var(--near-fg); }
  .chips .chip.missed { background: transparent; border: 1px dashed var(--line); color: var(--muted); }
  #roFound { max-width: 760px; margin: 10px auto 0; }
  .tmeta { display: flex; align-items: center; gap: 6px; }
  .tmeta img { width: 22px; height: 22px; }
  .rologo { background: var(--panel) !important; padding: 8px; }
  .romsg { min-height: 1.3em; }
  .romsg.bad { color: #c0392b; }
  .hlscore .urgent b { color: #c0392b; }
  .shake { animation: shake .35s ease; }
  @keyframes shake { 20%, 60% { transform: translateX(-6px); } 40%, 80% { transform: translateX(6px); } }
  @media (prefers-reduced-motion: reduce) { .shake, .jystop, .hintchip { animation: none; } .blurbox img { transition: none; } }

  /* draft day */
  #drHist { display: flex; flex-direction: column; align-items: center; gap: 6px; margin: 8px 0; }
  .drrow { display: flex; gap: 6px; }
  .numrow select { padding: 11px 10px; font-size: 16px; border: 1px solid #bbb; border-radius: 6px; background: var(--bg); color: var(--fg); }

  /* birthplace map */
  .mapwrap { max-width: 900px; margin: 6px auto 0; }
  .mapsvg { display: block; width: 100%; aspect-ratio: 16 / 9; border-radius: 10px; touch-action: none; cursor: crosshair;
            border: 1px solid var(--line); user-select: none; -webkit-user-select: none; }
  .mapsvg .sea { fill: var(--sea); }
  .mapsvg .land { fill: var(--land); stroke: var(--coast); stroke-width: 1; vector-effect: non-scaling-stroke; }
  .mapsvg .lakes { fill: var(--sea); stroke: var(--coast); stroke-width: .8; vector-effect: non-scaling-stroke; }
  .mapsvg .borders { fill: none; stroke: var(--coast); stroke-width: .8; vector-effect: non-scaling-stroke; opacity: .8; }
  .mapsvg .subdivisions { fill: none; stroke: var(--coast); stroke-width: .85; opacity: .72; vector-effect: non-scaling-stroke; pointer-events: none; }
  #mapCities { pointer-events: none; }
  .mapsvg .capital-dot { fill: var(--fg); stroke: var(--land); stroke-width: 1.3; }
  .mapsvg .capital-label { fill: var(--fg); stroke: var(--land); stroke-width: 3; paint-order: stroke; stroke-linejoin: round; font: 600 11px system-ui, sans-serif; }
  .mapsvg .regional .capital-label { font-weight: 500; }
  .mapcredit { font-size: 11px; color: var(--muted); margin: 7px 0 0; text-align: center; }
  .mapcredit a { color: inherit; text-decoration: underline; text-underline-offset: 2px; }
  .mapsvg .pin { fill: #c0392b; stroke: #fff; }
  .mapsvg .draftpin { fill: var(--fg); opacity: .85; }
  .mapsvg .answer { fill: var(--hit); stroke: #fff; }
  .mapsvg .pinline { stroke: #c0392b; stroke-dasharray: 1 1; opacity: .7; }
  .mapsvg text { fill: #fff; font-weight: 700; pointer-events: none; }
  .mapctl { display: flex; justify-content: space-between; align-items: center; gap: 8px; flex-wrap: wrap; margin: 8px 0 0; }
  .zoombtns { display: flex; gap: 6px; }
  #mpGo { min-width: 240px; }
  #mpHist { margin: 4px auto; }

  /* connections */
  .cngrid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; max-width: 640px; margin: 6px auto; }
  .cntile { background: var(--cell); color: var(--cell-fg); border: 0; border-radius: 8px; min-height: 72px; padding: 6px 4px;
            font: inherit; cursor: pointer; display: flex; flex-direction: column; align-items: center; justify-content: center;
            gap: 1px; transition: background-color .15s, transform .1s; overflow-wrap: anywhere; }
  .cntile small { font-size: 11px; opacity: .75; }
  .cntile b { font-size: 15px; text-transform: uppercase; letter-spacing: .02em; }
  .cntile.sel { background: var(--fg); color: var(--bg); }
  .cntile:active { transform: scale(.97); }
  .cngroup { max-width: 640px; margin: 0 auto 8px; border-radius: 8px; padding: 12px; text-align: center; color: #1c1c1c;
             animation: rowin .35s ease both; }
  .cngroup b { display: block; font-size: 15px; text-transform: uppercase; letter-spacing: .03em; }
  .cngroup span { font-size: 14px; }
  .cngroup.tier0 { background: #f5d44b; } .cngroup.tier1 { background: #9fcf7a; }
  .cngroup.tier2 { background: #9ebce9; } .cngroup.tier3 { background: #c29bd6; }
  .cngroup.missedgrp { opacity: .75; }
  .cnctl { display: flex; justify-content: center; gap: 8px; flex-wrap: wrap; margin: 8px 0; }
  .cnctl .btn { margin: 0; }
  .btn.ghost { background: transparent; color: var(--fg); box-shadow: inset 0 0 0 1px var(--line); }
  .btn:disabled { opacity: .5; cursor: default; }

  /* home screen */
  header h1 a { color: inherit; text-decoration: none; }
  header h1 a:focus-visible { outline: 2px solid var(--link); outline-offset: 4px; border-radius: 4px; }
  header h1::after { content: ""; display: block; width: 132px; height: 7px; margin: 6px auto 0;
                     background: linear-gradient(var(--hit) 0 2px, transparent 2px 5px, var(--hit) 5px 7px); }
  .sub { margin: 8px 0 6px; color: var(--muted); }
  #view-hub { max-width: 980px; }
  .hubprogress { text-align: center; color: var(--muted); margin: 4px 0 18px; }
  .hubsec { --tone: var(--hit); margin: 0 0 26px; }
  .hubsec.tone-blue { --tone: #4a78b5; }
  .hubsec.tone-amber { --tone: #c9962a; }
  .hubsec h2 { font-size: 17px; font-weight: 600; margin: 0 0 10px; padding-left: 12px; border-left: 4px solid var(--tone); }
  .hubgrid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
  .gcard { display: grid; grid-template-columns: 48px 1fr auto; align-items: center; gap: 14px; text-align: left;
           background: var(--panel); color: var(--fg); border: 1px solid var(--line); border-radius: 12px;
           padding: 14px 16px; font: inherit; cursor: pointer; transition: border-color .15s, background-color .15s; }
  .gcard:hover:not(:disabled) { border-color: var(--tone); }
  .gcard:focus-visible { outline: 2px solid var(--tone); outline-offset: 2px; }
  .gcard:disabled { opacity: .5; cursor: default; }
  .gicon { width: 48px; height: 48px; border-radius: 10px; display: grid; place-items: center; font-size: 24px;
           background: color-mix(in srgb, var(--tone) 16%, transparent); }
  .gtext b { display: block; font-size: 16px; }
  .gtext small { display: block; color: var(--muted); font-size: 13px; line-height: 1.35; margin-top: 2px; }
  .gstat { font-size: 13px; font-weight: 600; white-space: nowrap; padding: 5px 10px; border-radius: 999px;
           background: var(--cell); color: var(--cell-fg); }
  .gcard.done .gstat { background: var(--hit); color: var(--hit-fg); }
  .gcard.missed .gstat { background: transparent; box-shadow: inset 0 0 0 1px var(--line); color: var(--muted); }
  .gcard.going .gstat { background: var(--near); color: var(--near-fg); }
  .hubnext { text-align: center; color: var(--muted); font-size: 14px; }
  .hubnext b { font-variant-numeric: tabular-nums; color: var(--fg); }

  /* game bar */
  .gamebar { --tone: var(--hit); max-width: 1100px; margin: 0 auto 14px; }
  .gamebar[data-tone="blue"] { --tone: #2f7cf6; }
  .gamebar[data-tone="amber"] { --tone: #f2a100; }
  .gamebar[data-tone="red"] { --tone: #e5484d; }
  .backbtn { display: inline-flex; align-items: center; gap: 2px; background: none; border: 0; color: var(--label2);
             font: inherit; font-size: 15px; padding: 4px 8px 4px 2px; margin: 0 0 6px -2px; border-radius: 8px; cursor: pointer; }
  .backbtn span { font-size: 20px; line-height: 0; vertical-align: -2px; }
  .backbtn:hover { color: var(--fg); }
  .gtitle { display: flex; align-items: center; gap: 14px; padding: 0 0 14px;
            border-bottom: 1px solid var(--sep); }
  .gticon { width: 46px; height: 46px; flex: none; border-radius: 12px; display: grid; place-items: center; font-size: 24px;
            background: color-mix(in srgb, var(--tone) 18%, transparent); }
  .gtwords { min-width: 0; }
  .gtitle h2 { margin: 0; font-size: 28px; font-weight: 700; letter-spacing: -.02em; line-height: 1.1; }
  #modeLabel { display: block; margin-top: 3px; font-size: 13px; color: var(--label2); font-variant-numeric: tabular-nums; }
  .gamesel { display: block; margin: 0 auto 12px; padding: 8px 12px; font: inherit; font-size: 15px; border-radius: 8px;
             border: 1px solid var(--line); background: var(--bg); color: var(--fg); max-width: 100%; }
  .pickstat { display: inline-flex; align-items: center; gap: 8px; font-size: 14px; color: var(--muted); }
  .pickstat select { padding: 7px 10px; font: inherit; font-size: 15px; border-radius: 8px; border: 1px solid var(--line);
                     background: var(--bg); color: var(--fg); }
  #classicOpts { gap: 16px; }
  #silBtn { text-transform: none; letter-spacing: 0; font-size: 15px; }

  /* navigation bar */
  .navbar { position: sticky; top: 0; z-index: 8; display: flex; align-items: center; justify-content: space-between; gap: 12px;
            padding: 10px max(16px, env(safe-area-inset-left)); background: color-mix(in srgb, var(--bg) 78%, transparent);
            -webkit-backdrop-filter: saturate(180%) blur(18px); backdrop-filter: saturate(180%) blur(18px);
            border-bottom: 1px solid var(--sep); }
  body.hubmode .navbar { background: color-mix(in srgb, var(--grouped) 78%, transparent); }
  .brand { color: var(--fg); text-decoration: none; font-weight: 800; font-size: 19px; letter-spacing: .06em; }
  .brand span { display: inline-block; padding-bottom: 5px;
                background: linear-gradient(var(--hit) 0 2px, transparent 2px 4px, var(--hit) 4px 6px) bottom / 100% 6px no-repeat; }
  .brand:focus-visible { outline: 2px solid var(--link); outline-offset: 4px; border-radius: 4px; }
  .navactions { display: flex; align-items: center; gap: 6px; }
  .navactions .iconbtn { width: 36px; height: 36px; min-width: 36px; border: 0; background: var(--cell); color: var(--fg); font-size: 16px; }
  .navactions .iconbtn:hover { background: color-mix(in srgb, var(--fg) 12%, var(--cell)); }
  .navactions .switch { margin: 0 4px; font-size: 14px; }

  /* home screen, grouped-list style */
  #view-hub { max-width: 680px; padding-top: 18px; }
  .hubhead { margin: 0 4px 18px; }
  .hubdate { margin: 0; color: var(--label2); font-size: 15px; font-weight: 500; }
  .hubtitle { margin: 2px 0 12px; font-size: 34px; font-weight: 700; letter-spacing: -.02em; }
  .hubmeter { height: 6px; border-radius: 3px; background: var(--sep); overflow: hidden; }
  .hubmeter i { display: block; height: 100%; width: 0; border-radius: 3px; background: var(--hit); transition: width .6s cubic-bezier(.2,.8,.2,1); }
  .hubprogress { display: flex; justify-content: space-between; flex-wrap: wrap; gap: 4px 12px; margin: 8px 0 0;
                 color: var(--label2); font-size: 13px; text-align: left; }
  .hubnext b { font-variant-numeric: tabular-nums; color: var(--fg); font-weight: 600; }
  .partycard { position: relative; overflow: hidden; display: grid; grid-template-columns: 1fr auto; align-items: end; gap: 12px;
               width: 100%; min-height: 150px; margin: 0 0 26px; padding: 20px; border: 0; border-radius: 22px; cursor: pointer;
               text-align: left; font: inherit; color: #fff; background: #0f2440; }
  .partycard .rink { position: absolute; inset: 0; width: 100%; height: 100%; color: rgba(255,255,255,.2); opacity: .45; }
  .partycard > span { position: relative; }
  .partytext b { display: block; font-size: 24px; font-weight: 700; letter-spacing: -.01em; }
  .partytext span { display: block; margin-top: 4px; font-size: 15px; opacity: .85; max-width: 30ch; }
  .partycta { padding: 9px 16px; border-radius: 999px; background: #fff; color: #0f2440; font-weight: 600; font-size: 14px; white-space: nowrap; }
  .partycard:focus-visible { outline: 3px solid var(--link); outline-offset: 3px; }
  .partycard:disabled { cursor: default; opacity: .6; }
  .hubsec { --tone: #34a853; margin: 0 0 24px; }
  .hubsec.tone-blue { --tone: #2f7cf6; }
  .hubsec.tone-amber { --tone: #f2a100; }
  .hubsec.tone-red { --tone: #e5484d; }
  .hubsec h2 { margin: 0 4px 8px; padding: 0; border: 0; font-size: 20px; font-weight: 700; letter-spacing: -.01em; }
  .glist { background: var(--row); border-radius: 14px; overflow: hidden; }
  .grow { position: relative; display: grid; grid-template-columns: 40px 1fr auto 12px; align-items: center; gap: 12px;
          width: 100%; padding: 11px 14px; border: 0; background: none; color: var(--fg); font: inherit; text-align: left; cursor: pointer; }
  .grow + .grow::before { content: ""; position: absolute; top: 0; left: 66px; right: 0; border-top: 1px solid var(--sep); }
  .grow:hover:not(:disabled) { background: color-mix(in srgb, var(--fg) 5%, transparent); }
  .grow:active:not(:disabled) { background: color-mix(in srgb, var(--fg) 10%, transparent); }
  .grow:focus-visible { outline: 2px solid var(--tone); outline-offset: -2px; }
  .grow:disabled { opacity: .45; cursor: default; }
  .grow .gicon { width: 40px; height: 40px; border-radius: 10px; font-size: 21px; display: grid; place-items: center;
                 background: color-mix(in srgb, var(--tone) 18%, transparent); }
  .grow .gtext b { display: block; font-size: 16px; font-weight: 600; }
  .grow .gtext small { display: block; margin-top: 1px; color: var(--label2); font-size: 13px; line-height: 1.3; }
  .grow .gstat { background: none; padding: 0; color: var(--label2); font-size: 14px; font-weight: 400; white-space: nowrap; }
  .grow.done .gstat { color: var(--hit); font-weight: 600; background: none; }
  .grow.done .gstat::before { content: "✓ "; }
  .grow.going .gstat { color: #c98a00; background: none; }
  .grow.missed .gstat { box-shadow: none; }
  .chev { color: var(--label2); font-size: 22px; line-height: 1; opacity: .6; }

  /* rank 'em */
  .rklist { list-style: none; padding: 0; margin: 10px auto; max-width: 560px; display: grid; gap: 8px; touch-action: none; }
  .rkrow { display: grid; grid-template-columns: 24px 44px 1fr auto auto; align-items: center; gap: 10px; padding: 8px 10px;
           border-radius: 12px; background: var(--cell); color: var(--cell-fg); border: 2px solid transparent;
           user-select: none; transition: border-color .2s, box-shadow .2s; }
  .rkrow.done { grid-template-columns: 24px 44px 1fr auto; }
  .rkrow.good { border-color: var(--hit); }
  .rkrow.lifted { box-shadow: 0 8px 22px rgba(0,0,0,.18); }
  .rkpos { font-weight: 700; font-size: 18px; text-align: center; font-variant-numeric: tabular-nums; }
  .rkrow img { width: 44px; height: 44px; border-radius: 50%; background: var(--cream); object-fit: cover; pointer-events: none; }
  .rkname b { display: block; font-size: 15px; }
  .rkname small { font-size: 12px; opacity: .7; }
  .rkval { font-weight: 700; font-variant-numeric: tabular-nums; }
  .rkbtns { display: flex; gap: 4px; }
  .rkbtns button { width: 32px; height: 32px; border-radius: 8px; border: 1px solid var(--line); background: var(--bg); color: var(--fg); cursor: pointer; font-size: 11px; }
  .rkbtns button:disabled { opacity: .3; cursor: default; }
  .rkgrip { cursor: grab; font-size: 20px; color: var(--muted); padding: 0 2px; }
  .rklist.dragging { cursor: grabbing; }

  /* puck drop */
  .pkrule { text-align: center; font-size: 17px; margin: 4px 0 8px; }
  .pkrule b { color: var(--hit); }
  .rinklane { position: relative; height: 230px; max-width: 900px; margin: 10px auto; border-radius: 26px; overflow: hidden;
              background: linear-gradient(90deg, transparent 49.6%, rgba(229,72,77,.55) 49.6% 50.4%, transparent 50.4%),
                          linear-gradient(90deg, transparent 32.5%, rgba(91,141,239,.5) 32.5% 33.3%, transparent 33.3% 66.6%, rgba(91,141,239,.5) 66.6% 67.4%, transparent 67.4%),
                          linear-gradient(180deg, #f3f8fb, #dfeaf1);
              border: 2px solid color-mix(in srgb, var(--fg) 15%, transparent); touch-action: manipulation; }
  .puck { position: absolute; left: 0; height: 26%; padding: 0 16px; border: 0; border-radius: 999px; background: #121417; color: #fff;
          font: inherit; font-size: 15px; font-weight: 600; white-space: nowrap; cursor: pointer; will-change: transform;
          box-shadow: 0 3px 0 #000, 0 6px 14px rgba(0,0,0,.25); }
  .puck.good { background: var(--hit); }
  .puck.bad { background: #c0392b; }
  .puck.tapped { pointer-events: none; opacity: .85; }
  .pksummary { position: absolute; inset: 0; display: flex; flex-wrap: wrap; align-content: center; justify-content: center; gap: 6px; padding: 14px; overflow: auto; }
  .chips .chip.bad, .pksummary .chip.bad { background: #c0392b; color: #fff; }

  /* shootout */
  .shdots { display: flex; flex-wrap: wrap; justify-content: center; gap: 6px; margin: 4px 0 10px; }
  .shdot { width: 34px; height: 34px; border-radius: 50%; display: grid; place-items: center; background: var(--cell); color: var(--cell-fg); font-weight: 600; }
  .shdot.now { box-shadow: 0 0 0 2px var(--fg); }
  .shnet { display: block; width: min(460px, 100%); margin: 0 auto; overflow: visible; user-select: none; }
  .shnet .ice { fill: color-mix(in srgb, #bfdcf0 45%, var(--bg)); }
  .shnet .netback { fill: color-mix(in srgb, var(--fg) 3%, var(--bg)); }
  .shnet .meshline { stroke: color-mix(in srgb, var(--fg) 20%, transparent); stroke-width: .7; fill: none; }
  .shnet .crease { fill: rgba(80,150,220,.28); stroke: #d6312f; stroke-width: 1.2; }
  .shnet .posts { fill: none; stroke: url(#gPost); stroke-width: 7; stroke-linejoin: round; stroke-linecap: round; }
  .shnet .postshine { fill: none; stroke: rgba(255,255,255,.35); stroke-width: 1; }
  .shnet .lamp { fill: color-mix(in srgb, var(--fg) 15%, transparent); transition: fill .2s, filter .2s; }
  .shnet.scored .lamp { fill: #ff3b30; filter: drop-shadow(0 0 6px #ff3b30); animation: lamp .5s ease-in-out 3; }
  .shnet.scored .posts { filter: drop-shadow(0 0 4px rgba(255,59,48,.8)); }
  .shnet.scored .mesh { animation: ripple .45s ease-out; transform-box: fill-box; transform-origin: center; }
  @keyframes lamp { 50% { fill: #7a1712; filter: none; } }
  @keyframes ripple { 30% { transform: scale(1.015, 1.03); } }

  .goalie { transform-box: fill-box; transform-origin: 50% 100%; transition: transform .3s cubic-bezier(.25,1.3,.5,1); }
  .goalie .posewrap { transition: transform 0s; }
  .goalie.mirror .posewrap { transform: matrix(-1, 0, 0, 1, 300, 0); }
  .goalie.mirror .crestS { transform: scale(-1, 1); transform-box: fill-box; transform-origin: center; }
  .goalie .pose { opacity: 0; transform-box: fill-box; transform-origin: 50% 100%; transform: scale(.94);
                  transition: opacity .14s ease-out, transform .3s cubic-bezier(.25,1.4,.5,1); }
  .goalie[data-pose="ready"] .pose-ready, .goalie[data-pose="stretch"] .pose-stretch,
  .goalie[data-pose="split"] .pose-split { opacity: 1; transform: none; }
  .goalie .shaft { stroke: #3a2a1d; stroke-width: 4; stroke-linecap: round; }
  .goalie .paddle, .goalie .blade { fill: #1b1b1b; }
  .goalie .tape { fill: #f4f4f4; opacity: .85; }
  .goalie .skate { fill: #3a3d42; }
  .goalie .pad rect:first-child { fill: url(#gPad); stroke: #8e9bb0; stroke-width: 1; }
  .goalie .knee { fill: #fff; stroke: #8e9bb0; stroke-width: .8; }
  .goalie .trim { fill: #2d63c4; }
  .goalie .seam { stroke: #b8c2d2; stroke-width: .8; fill: none; }
  .goalie .pants { fill: #10295a; }
  .goalie .arm { stroke: #1f4ea6; stroke-width: 15; stroke-linecap: round; fill: none; }
  .goalie .armstripe { stroke: #fff; stroke-width: 15; fill: none; opacity: .92; }
  .goalie .jersey { fill: url(#gJersey); stroke: #0f2a5a; stroke-width: 1; }
  .goalie .stripe { fill: #fff; opacity: .92; }
  .goalie .crest { fill: #fff; stroke: #0f2a5a; stroke-width: 1; }
  .goalie .crestS { fill: #173f86; font-size: 11px; font-weight: 800; text-anchor: middle; font-family: inherit; }
  .goalie .blocker { fill: #fbfbfc; stroke: #8e9bb0; stroke-width: 1; }
  .goalie .blockertrim { fill: none; stroke: #2d63c4; stroke-width: 1.4; }
  .goalie .glove { fill: #fbfbfc; stroke: #8e9bb0; stroke-width: 1; }
  .goalie .pocket { stroke: #2d63c4; stroke-width: 1.4; fill: none; stroke-linecap: round; }
  .goalie .cuff { fill: #2d63c4; }
  .goalie .helmet { fill: url(#gHelmet); stroke: #8e9bb0; stroke-width: 1; }
  .goalie .helmetstripe { stroke: #2d63c4; stroke-width: 3.5; fill: none; stroke-linecap: round; }
  .goalie .face { fill: #2a2d33; }
  .goalie .cage { stroke: #d9dde4; stroke-width: 1; fill: none; }
  .goalie .throat { fill: #dfe5ee; stroke: #8e9bb0; stroke-width: .6; }

  .zone { cursor: pointer; transition: opacity .2s; }
  .zone circle:first-child { fill: rgba(52,168,83,.12); stroke: var(--hit); stroke-width: 1.6; stroke-dasharray: 3 3; }
  .zone .dot { fill: var(--hit); }
  .zone:hover circle:first-child { fill: rgba(52,168,83,.3); stroke-dasharray: none; }
  .zone.off { opacity: 0; pointer-events: none; }

  .shpuck { opacity: 0; transform-box: fill-box; transform-origin: center; transition: opacity .2s; }
  .shnet.aim .shpuck { opacity: 1; }
  .shpuck .puckside { fill: #050505; }
  .shpuck .pucktop { fill: #2c2c2e; stroke: rgba(255,255,255,.4); stroke-width: .6; }
  .shpuck .puckshine { fill: rgba(255,255,255,.22); }
  .shpuck.fly { opacity: 1; animation: shot .42s cubic-bezier(.3,.6,.4,1) forwards; }
  .shpuck.fly.saved { animation: shot .42s cubic-bezier(.3,.6,.4,1) forwards, deflect .35s .42s ease-out forwards; }
  @keyframes shot { from { transform: translate(0, 0) scale(1.15) rotate(0); } to { transform: translate(var(--tx), var(--ty)) scale(.62) rotate(-8deg); } }
  @keyframes deflect { from { transform: translate(var(--tx), var(--ty)) scale(.62); } to { transform: translate(calc(var(--tx) * .5), -2px) scale(.8); opacity: 0; } }
  @media (prefers-reduced-motion: reduce) { .goalie { transition: none; } .shpuck.fly, .shpuck.fly.saved { animation-duration: .01s; } .shnet.scored .lamp, .shnet.scored .mesh { animation: none; } }
  .shopts { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; max-width: 560px; margin: 0 auto; }
  .shopt { padding: 12px; border-radius: 12px; border: 0; background: var(--cell); color: var(--cell-fg); font: inherit; font-size: 15px; cursor: pointer; }
  .shopt:hover:not(:disabled) { background: color-mix(in srgb, var(--fg) 12%, var(--cell)); }
  .shopt.right { background: var(--hit); color: var(--hit-fg); }
  .shopt.wrong { background: #c0392b; color: #fff; }
  .shopt.dim { opacity: .45; }
  .shopt:disabled { cursor: default; }

  /* zamboni */
  .zambox { position: relative; width: min(300px, 80vw); aspect-ratio: 1; margin: 6px auto 12px; border-radius: 24px; overflow: hidden; background: var(--cream); }
  .zambox img, .zambox canvas { position: absolute; inset: 0; width: 100%; height: 100%; }
  .zambox img { object-fit: cover; user-select: none; -webkit-user-drag: none; }
  .zambox canvas { touch-action: none; cursor: crosshair; }

  /* party mode */
  #view-party { max-width: 900px; }
  .ptchoice { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
  .ptpanel { background: var(--cell); color: var(--cell-fg); border-radius: 18px; padding: 18px; }
  .ptpanel h3 { margin: 0 0 6px; font-size: 20px; }
  .ptpanel p { margin: 0 0 14px; font-size: 14px; opacity: .8; }
  .ptpanel label { display: block; font-size: 13px; margin: 0 0 10px; }
  .ptpanel input { display: block; width: 100%; box-sizing: border-box; margin-top: 4px; padding: 11px 12px; font: inherit; font-size: 17px;
                   border-radius: 10px; border: 1px solid var(--line); background: var(--bg); color: var(--fg); }
  #ptCode { text-transform: uppercase; letter-spacing: .3em; font-weight: 700; }
  .ptpanel .btn { margin: 4px 0 0; width: 100%; }
  .ptnote { text-align: center; color: var(--muted); }
  .ptlobby { text-align: center; }
  .ptlabel { margin: 10px 0 0; color: var(--muted); }
  .ptcode { margin: 4px 0; font-size: clamp(64px, 14vw, 120px); font-weight: 800; letter-spacing: .12em; font-variant-numeric: tabular-nums; }
  .ptlink { margin: 0 0 16px; color: var(--muted); font-size: 13px; word-break: break-all; }
  .ptplayers { display: flex; flex-wrap: wrap; justify-content: center; gap: 8px; min-height: 40px; margin: 0 0 16px; }
  .ptplayers .chip { animation: rowin .3s ease both; }
  .ptcontrols { display: flex; justify-content: center; align-items: center; gap: 12px; flex-wrap: wrap; margin: 14px 0; }
  .ptcontrols select { padding: 8px 10px; font: inherit; border-radius: 8px; border: 1px solid var(--line); background: var(--bg); color: var(--fg); }
  .ptcontrols .btn { margin: 0; }
  .pthead { display: flex; justify-content: space-between; color: var(--muted); font-size: 14px; margin: 4px 0 8px; }
  .pttimer { position: relative; height: 10px; border-radius: 5px; background: var(--cell); overflow: hidden; margin: 0 0 12px; }
  .pttimer i { position: absolute; inset: 0 auto 0 0; background: var(--hit); transition: width 1s linear; }
  .pttimer b { display: none; }
  .ptq { text-align: center; font-size: clamp(22px, 3.4vw, 34px); font-weight: 700; margin: 10px 0 16px; letter-spacing: -.01em; }
  .ptq.small { font-size: 19px; }
  .pttiles { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
  .pttile { position: relative; display: flex; align-items: center; gap: 12px; min-height: 84px; padding: 14px 16px; border: 0; border-radius: 16px;
            color: #fff; font: inherit; font-size: 18px; font-weight: 600; text-align: left; cursor: pointer; transition: opacity .2s, transform .1s; }
  .pttiles.big .pttile { min-height: 110px; font-size: clamp(18px, 2.4vw, 26px); }
  .pttile .shape { font-size: 22px; opacity: .9; }
  .pttile.c0 { background: #e5484d; } .pttile.c1 { background: #2f7cf6; } .pttile.c2 { background: #d99a00; } .pttile.c3 { background: #2f9e57; }
  .pttile:active:not(:disabled) { transform: scale(.98); }
  .pttile:disabled { cursor: default; }
  .pttile.picked { box-shadow: inset 0 0 0 4px #fff; }
  .pttile.faded { opacity: .3; }
  .pttile.right { box-shadow: inset 0 0 0 4px #fff, 0 0 0 3px var(--hit); }
  .pttile .count { margin-left: auto; font-size: 22px; }
  .ptboard { list-style: none; padding: 0; margin: 16px auto; max-width: 520px; }
  .ptboard li { display: grid; grid-template-columns: 30px 1fr auto; gap: 10px; padding: 8px 12px; border-bottom: 1px solid var(--line); }
  .ptboard li.me { background: var(--cell); border-radius: 8px; }
  .ptboard em { font-style: normal; font-weight: 700; font-variant-numeric: tabular-nums; }
  .ptpodium { display: flex; justify-content: center; align-items: flex-end; gap: 10px; margin: 10px 0; }
  .ptpodium .step { display: flex; flex-direction: column; align-items: center; justify-content: flex-end; gap: 2px; width: 30%; max-width: 180px;
                    padding: 12px 8px; border-radius: 14px 14px 0 0; background: var(--cell); color: var(--cell-fg); }
  .ptpodium .s0 { order: 2; min-height: 170px; } .ptpodium .s1 { order: 1; min-height: 130px; } .ptpodium .s2 { order: 3; min-height: 100px; }
  .ptpodium span { font-size: 34px; } .ptpodium em { font-style: normal; font-variant-numeric: tabular-nums; }
  .ptwait { text-align: center; padding: 30px 10px; border-radius: 18px; background: var(--cell); color: var(--cell-fg); }
  .ptwait.good { background: var(--hit); color: var(--hit-fg); }
  .ptwait.bad { background: #c0392b; color: #fff; }
  .ptbig { font-size: 28px; font-weight: 700; margin: 0 0 6px; }
  .ptleave { display: block; margin: 18px auto 0; color: var(--muted); text-decoration: underline; letter-spacing: 0; text-transform: none; }

  /* two truths */
  .twlist { display: grid; gap: 8px; max-width: 560px; margin: 4px auto 0; }
  .twline { display: flex; align-items: center; gap: 12px; padding: 14px 16px; border: 0; border-radius: 12px;
            background: var(--cell); color: var(--cell-fg); font: inherit; font-size: 16px; text-align: left; cursor: pointer;
            transition: background-color .2s, transform .1s; }
  .twline:hover:not(:disabled) { background: color-mix(in srgb, var(--fg) 12%, var(--cell)); }
  .twline:active:not(:disabled) { transform: scale(.99); }
  .twline:disabled { cursor: default; }
  .twmark { width: 26px; height: 26px; flex: none; border-radius: 50%; display: grid; place-items: center;
            background: color-mix(in srgb, var(--fg) 12%, transparent); font-weight: 700; font-size: 14px; }
  .twtext { flex: 1; }
  .twtag { font-size: 12px; font-weight: 600; letter-spacing: .03em; opacity: .8; white-space: nowrap; }
  .twline.istrue { background: var(--cell); opacity: .65; }
  .twline.isfalse { background: color-mix(in srgb, var(--hit) 18%, var(--cell)); box-shadow: inset 0 0 0 2px var(--hit); opacity: 1; }
  .twline.isfalse .twmark { background: var(--hit); color: var(--hit-fg); }
  .twline.mine { opacity: 1; box-shadow: inset 0 0 0 3px var(--fg); }
  .twline.istrue.mine { background: color-mix(in srgb, #c0392b 16%, var(--cell)); }
  .twline.istrue.mine .twmark { background: #c0392b; color: #fff; }
  .hint .good { color: var(--hit); }
  .hint .bad { color: #c0392b; }

  /* team higher or lower */
  .hltlogo { width: 92px; height: 92px; object-fit: contain; }

  /* mystery season */
  .selist { display: flex; flex-wrap: wrap; justify-content: center; gap: 8px; max-width: 620px; margin: 14px auto 0; }
  .sebtn { padding: 10px 14px; border: 0; border-radius: 10px; background: var(--cell); color: var(--cell-fg);
           font: inherit; font-size: 15px; font-variant-numeric: tabular-nums; cursor: pointer; transition: background-color .2s; }
  .sebtn:hover:not(:disabled) { background: color-mix(in srgb, var(--fg) 12%, var(--cell)); }
  .sebtn.hit { background: var(--hit); color: var(--hit-fg); }
  .sebtn.miss { opacity: .45; }
  .sebtn:disabled { cursor: default; }

  /* mystery roster */
  .mrlist { list-style: none; padding: 0; margin: 10px auto; max-width: 560px; display: grid; gap: 8px; }
  .mrrow { display: flex; align-items: center; gap: 12px; padding: 8px 12px; border-radius: 12px;
           background: var(--cell); color: var(--cell-fg); }
  .mrnum { width: 46px; height: 46px; flex: none; border-radius: 10px; display: grid; place-items: center;
           background: color-mix(in srgb, var(--fg) 10%, transparent); font-weight: 700; font-variant-numeric: tabular-nums; }
  .mrrow b { display: block; font-size: 16px; }
  .mrrow small { font-size: 12px; opacity: .7; }

  /* playoff history grid */
  #view-cups { max-width: 1440px; }
  .cups-controls { position: sticky; top: 0; z-index: 3; padding: 6px 0 10px; background: var(--bg); border-bottom: 1px solid var(--sep); }
  .cups-controls .intro { margin-top: 0; }
  #view-cups .cuboard { width: 100%; max-width: 100%; margin: 10px auto 0; overflow-x: visible; }
  .cutable { width: 100%; table-layout: fixed; border-collapse: separate; border-spacing: 0 5px; }
  .cutable th { font-size: 12px; font-weight: 600; color: var(--muted); text-align: left; padding: 8px 10px; }
  #view-cups .cutable thead th { position: sticky; top: var(--cups-header-top, 0px); z-index: 2; background: var(--bg); box-shadow: 0 4px 0 var(--bg); }
  .cutable td { height: 34px; padding: 7px 10px; background: var(--cell); color: var(--cell-fg); font-size: 14px; overflow-wrap: anywhere; }
  .cutable td:first-child { border-radius: 8px 0 0 8px; font-weight: 600; font-variant-numeric: tabular-nums; width: 88px; }
  .cutable td:last-child { border-radius: 0 8px 8px 0; }
  .cutable th:first-child { width: 9%; }
  .cutable th:not(:first-child) { width: 30.333%; }
  .cucell.got { background: color-mix(in srgb, var(--hit) 26%, var(--cell)); font-weight: 600; }
  .cucell.miss { color: var(--muted); font-style: italic; }
  .cuanswer { display: flex; align-items: center; gap: 8px; min-width: 0; }
  .culogo { width: 24px; height: 24px; flex: none; object-fit: contain; }
  @media (max-width: 700px) {
    .cups-controls { position: static; }
    #view-cups .cutable thead th { position: static; }
    #view-cups .cuboard { overflow-x: auto; }
    #view-cups .cutable { min-width: 700px; }
    .cutable td, .cutable th { font-size: 12px; padding: 6px; }
    .cutable td:first-child { width: 64px; }
  }

  @keyframes trophysetup { from { opacity: .25; transform: translateY(7px); } to { opacity: 1; transform: none; } }
  #view-trophy.setup-change .shdots, #view-trophy.setup-change .ttq,
  #view-trophy.setup-change .shopts, #view-trophy.setup-change #trMsg {
    animation: trophysetup .28s ease both;
  }

  /* options, archive */
  .optrow { display: flex; justify-content: center; align-items: center; gap: 10px; margin: 6px 0 0; font-size: 14px; }
  .optnote { color: var(--muted); font-size: 13px; }
  .optnote.center { display: block; text-align: center; min-height: 1em; margin: 4px 0 0; }
  .tabs button:disabled { cursor: not-allowed; opacity: .55; }
  .tabs button[aria-selected="true"]:disabled { opacity: .8; }
  .switch input:disabled + .track { opacity: .5; }
  .slhint { display: flex; align-items: center; justify-content: center; gap: 6px; flex-wrap: wrap;
            width: fit-content; max-width: 100%; margin: 10px auto 0; padding: 8px 14px; border-radius: 999px;
            background: var(--near); color: var(--near-fg); font-size: 14px; animation: rowin .35s ease both; }
  .slhint img { width: 24px; height: 24px; }
  .archbar { display: flex; justify-content: center; align-items: center; flex-wrap: wrap; gap: 4px 12px;
             margin: 2px auto 6px; padding: 6px 14px; width: fit-content; max-width: 100%;
             border-radius: 999px; background: var(--cell); color: var(--cell-fg); font-size: 14px; }
  .archbar .linkbtn { color: var(--fg); text-decoration: underline; text-underline-offset: 2px; letter-spacing: 0; font-size: 14px; padding: 2px 4px; }
  .arlist { list-style: none; padding: 0; margin: 10px 0 0; max-height: 60vh; overflow-y: auto; }
  .arbtn { display: grid; grid-template-columns: 56px 1fr auto; align-items: center; gap: 10px; width: 100%;
           background: none; border: 0; border-bottom: 1px solid var(--line); color: var(--fg); font: inherit;
           padding: 11px 8px; text-align: left; cursor: pointer; font-variant-numeric: tabular-nums; }
  .arbtn:hover, .arbtn.on { background: var(--cell); color: var(--cell-fg); }
  .arno { color: var(--muted); font-weight: 600; }
  .arstat { font-size: 14px; font-weight: 600; }
  .arlist .empty { text-align: center; color: var(--muted); padding: 30px 0; }

  /* leaderboard */
  .lbcard { width: min(480px, 94vw); }
  .lbtabs { display: flex; width: fit-content; max-width: 100%; margin: 0 auto 10px; flex-wrap: wrap; justify-content: center; }
  .lb { list-style: none; padding: 0; margin: 6px 0; min-height: 120px; }
  .lb li { display: grid; grid-template-columns: 36px 1fr auto; align-items: center; gap: 10px;
           padding: 9px 8px; border-bottom: 1px solid var(--line); font-variant-numeric: tabular-nums; }
  .lb li.me { background: var(--cell); color: var(--cell-fg); border-radius: 6px; }
  .lb .rk { text-align: center; color: var(--muted); font-weight: 600; }
  .lb .nm { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .lb .pt { font-weight: 600; text-align: right; }
  .lb small { display: block; color: var(--muted); font-weight: 400; font-size: 12px; }
  .lb li.empty { display: block; text-align: center; color: var(--muted); border: 0; padding: 36px 0; }
  .lbname { display: flex; gap: 8px; justify-content: center; align-items: center; flex-wrap: wrap; margin: 12px 0 4px; font-size: 14px; }
  .lbname input { padding: 9px 12px; font-size: 16px; border: 1px solid var(--line); border-radius: 6px;
                  background: var(--bg); color: var(--fg); width: 190px; }
  .lbname .btn { margin: 0; padding: 9px 16px; }
  .lberr { color: #c0392b; width: 100%; text-align: center; font-size: 13px; margin: 2px 0 0; min-height: 1em; }
  .lbrules { font-size: 13px; color: var(--muted); text-align: center; margin: 10px 0 0; line-height: 1.5; }
  .stlb { text-align: center; font-size: 14px; margin: 14px 0 0; }
  .stlb .linkbtn { color: var(--fg); text-decoration: underline; text-underline-offset: 2px; letter-spacing: 0; }

  /* higher or lower */
  .hlscore { display: flex; justify-content: center; gap: 22px; font-size: 15px; color: var(--muted); margin: 0 0 6px; }
  .hlscore b { color: var(--fg); font-size: 22px; font-variant-numeric: tabular-nums; margin-left: 4px; }
  .hlpair { display: grid; grid-template-columns: 1fr auto 1fr; align-items: stretch; gap: 14px;
            max-width: 760px; margin: 10px auto 0; }
  .hlpair.slide .hlcard { animation: rowin .4s cubic-bezier(.2,.8,.2,1) both; }
  .hlpair > div:not(.hlvs) { display: flex; }
  .hlpair .hlcard { flex: 1; }
  @media (hover: none) { .keytip { display: none; } }
  .hlvs { align-self: center; font-weight: 800; color: var(--muted); font-size: 18px; }
  .hlcard { background: var(--cell); color: var(--cell-fg); border-radius: 12px; padding: 18px 14px 16px;
            text-align: center; display: flex; flex-direction: column; align-items: center; min-height: 330px;
            border: 3px solid transparent; transition: border-color .25s, background-color .25s; }
  .hlcard.ok { border-color: var(--hit); }
  .hlcard.bad { border-color: #c0392b; }
  .hlimg { width: 112px; height: 112px; border-radius: 50%; background: var(--cream); object-fit: cover; }
  .hlname { font-size: 20px; font-weight: 600; margin: 10px 0 2px; }
  .hlteam { display: flex; align-items: center; gap: 6px; font-size: 13px; opacity: .75; margin: 0 0 10px; }
  .hlteam img { width: 20px; height: 20px; }
  .hlval { margin: 4px 0 0; line-height: 1; }
  .hlval b { font-size: 46px; font-weight: 700; font-variant-numeric: tabular-nums; }
  .hlunit { margin: 4px 0 0; font-size: 14px; }
  .hlyr { margin: 4px 0 0; font-size: 13px; opacity: .7; }
  .hlbtns { display: flex; flex-direction: column; gap: 8px; width: min(200px, 100%); margin: 10px 0 2px; }
  .hlbtns .hlbtn { margin: 0; font-size: 16px; padding: 11px 14px; background: var(--fg); color: var(--bg);
                  transition: opacity .15s, transform .1s; }
  .hlbtns .hlbtn:hover:not(:disabled) { opacity: .85; }
  .hlbtns .hlbtn:active:not(:disabled) { transform: scale(.98); }
  .hlbtn:disabled { opacity: .5; cursor: default; }

  /* stats: guess the player */
  .seasons { border-collapse: separate; border-spacing: 0 6px; width: min(620px, 100%); margin: 6px auto; }
  .seasons th { font-weight: 500; font-size: 13px; color: var(--muted); padding: 0 8px 2px; }
  .seasons td { background: var(--cell); color: var(--cell-fg); text-align: center; height: 44px;
                padding: 0 8px; font-size: 16px; font-variant-numeric: tabular-nums; }
  .seasons td:first-child { border-radius: 6px 0 0 6px; font-weight: 600; }
  .seasons td:last-child { border-radius: 0 6px 6px 0; }
  .seasons tr.locked td { background: transparent; color: var(--muted); border: 1px dashed var(--line); border-width: 1px 0; }
  .seasons tr.locked td:first-child { border-left-width: 1px; }
  .seasons tr.locked td:last-child { border-right-width: 1px; }
  .wrong { list-style: none; padding: 0; margin: 10px auto; width: min(620px, 100%); }
  .wrong li { display: flex; align-items: center; gap: 10px; padding: 8px 12px; border-bottom: 1px solid var(--line); }
  .wrong li small { margin-left: auto; color: var(--muted); }
  .wrong .x { color: #c0392b; font-weight: 700; }

  /* stats: guess the team */
  .ttcard { display: flex; align-items: center; justify-content: center; gap: 16px; margin: 4px 0; }
  .ttcard img { width: 96px; height: 96px; border-radius: 50%; background: var(--cream); object-fit: cover; }
  .ttcard .pname { margin: 0; }
  .ttq { text-align: center; font-size: 19px; margin: 14px 0 10px; }
  .chips { display: flex; flex-wrap: wrap; justify-content: center; gap: 8px; }
  .chip { background: var(--cell); color: var(--cell-fg); border-radius: 999px; padding: 6px 14px; font-size: 14px;
          font-variant-numeric: tabular-nums; }
  .chip b { font-size: 16px; }
  .divs { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; max-width: 960px; margin: 12px auto 0; }
  .divs h4 { margin: 0 0 8px; font-size: 13px; font-weight: 600; color: var(--muted); text-align: center; }
  .teambtn { display: flex; align-items: center; gap: 10px; width: 100%; background: var(--cell); color: var(--cell-fg);
             border: 0; border-radius: 6px; padding: 6px 10px; margin: 0 0 6px; font: inherit; font-size: 14px;
             text-align: left; cursor: pointer; transition: background-color .25s, opacity .25s, transform .1s; }
  .teambtn img { width: 28px; height: 28px; flex: none; }
  .teambtn:hover:not(:disabled) { transform: translateY(-1px); box-shadow: 0 0 0 2px var(--fg) inset; }
  .teambtn:disabled { cursor: default; }
  .teambtn.hit { background: var(--hit); color: var(--hit-fg); }
  .teambtn.near { background: var(--near); color: var(--near-fg); }
  .teambtn.miss { opacity: .35; text-decoration: line-through; }
  .num { display: flex; justify-content: space-between; align-items: center; padding: 0 12px; }
  .arrow { font-size: 22px; line-height: 1; }
  .banner { text-align: center; margin: 18px auto; display: none; }
  .banner img { width: 160px; height: 160px; border-radius: 50%; background: var(--cream); object-fit: cover; }
  .banner p { margin: 8px 0; font-size: 18px; }
  .banner .headline { font-size: clamp(26px, 3.4vw, 34px); font-weight: 500; letter-spacing: -0.01em;
                      margin: 8px 0 0; line-height: 1.2; }
  .banner .cheer { font-size: 15px; color: var(--muted); margin: 14px 0 22px; line-height: 1.4; }
  .banner .pname { font-size: 24px; font-weight: 600; margin: 10px 0 0; }
  .banner .pmeta { font-size: 14px; color: var(--muted); margin: 2px 0 12px; }
  .profile { display: inline-block; background: var(--fg); color: var(--bg); text-decoration: none;
             padding: 9px 18px; border-radius: 999px; font-size: 14px; font-weight: 600;
             transition: transform .15s ease, opacity .15s ease, background-color .3s, color .3s; }
  .profile:hover { transform: translateY(-1px); opacity: .88; }
  .profile:focus-visible { outline: 2px solid var(--hit); outline-offset: 3px; }
  .banner.won .headline { color: var(--fg); }
  .banner.pop .headline { animation: rise .5s cubic-bezier(.2,.8,.2,1) both; }
  .banner.pop .cheer { animation: rise .5s cubic-bezier(.2,.8,.2,1) .08s both; }
  @keyframes rise { from { transform: translateY(8px); opacity: 0; } to { transform: none; opacity: 1; } }
  .banner.pop img { animation: pop .6s cubic-bezier(.2,1.4,.4,1) .12s both; }
  @keyframes pop { from { transform: scale(.4); opacity: 0; } to { transform: scale(1); opacity: 1; } }
  #confetti { position: fixed; inset: 0; width: 100%; height: 100%; pointer-events: none; z-index: 30; }
  @media (prefers-reduced-motion: reduce) { .banner.pop .headline, .banner.pop .cheer, .banner.pop img { animation: none; } }
  .btn { background: var(--hit); color: #fff; border: 0; border-radius: 4px;
         padding: 10px 18px; font-size: 15px; cursor: pointer; margin-top: 6px; }
  .modal { position: fixed; inset: 0; background: var(--scrim); display: flex;
           align-items: center; justify-content: center; z-index: 10;
           opacity: 0; visibility: hidden;
           transition: opacity .28s ease, visibility 0s linear .28s; }
  .modal.open { opacity: 1; visibility: visible;
                transition: opacity .28s ease, visibility 0s; }
  .card { background: var(--panel); padding: 24px; width: min(300px, 90vw); border-radius: 8px;
          box-shadow: 0 16px 40px rgba(0,0,0,.3);
          transform: translateY(16px) scale(.94); opacity: 0;
          transition: transform .38s cubic-bezier(.2,.9,.3,1.15), opacity .28s ease; }
  .modal.open .card { transform: none; opacity: 1; }
  .silbox img { transform: scale(1.06); transition: transform .6s cubic-bezier(.2,.8,.2,1) .05s; }
  .modal.open .silbox img { transform: scale(1); }
  @media (prefers-reduced-motion: reduce) {
    .modal, .modal.open, .card, .silbox img { transition: opacity .15s linear, visibility 0s; transform: none; }
  }
  .themebtn { background: none; border: 1px solid var(--line); color: var(--fg); border-radius: 999px;
              width: 34px; height: 34px; cursor: pointer; font-size: 16px; line-height: 1; display: grid; place-items: center; }
  .themebtn:hover { background: var(--cell); }
  .card h2 { margin: 0 0 12px; font-size: 20px; font-weight: 400; }
  .silbox { background: var(--silbg); transition: background-color .3s ease; border-radius: 4px; overflow: hidden; line-height: 0; }
  .card img { width: 100%; aspect-ratio: 1; object-fit: cover; filter: brightness(0);
              user-select: none; -webkit-user-drag: none; }
  .topbar-unused { position: absolute; top: 14px; right: 18px; display: flex; align-items: center;
            gap: 14px; font-size: 14px; }
  #modeLabel { color: var(--muted); }
  .switch { display: flex; align-items: center; gap: 8px; cursor: pointer; user-select: none; }
  .switch input { position: absolute; opacity: 0; width: 1px; height: 1px; }
  .track { width: 36px; height: 20px; border-radius: 10px; background: #bbb; position: relative; transition: background .2s; }
  .track::after { content: ""; position: absolute; top: 2px; left: 2px; width: 16px; height: 16px;
                  border-radius: 50%; background: #fff; transition: transform .2s; }
  .switch input:checked + .track { background: var(--hit); }
  .switch input:checked + .track::after { transform: translateX(16px); }
  .switch input:focus-visible + .track { outline: 2px solid var(--link); outline-offset: 2px; }
  .countdown { font-variant-numeric: tabular-nums; color: var(--muted); }
  body { position: relative; }
  .topleft-unused { display: none; }
  .iconbtn { background: none; border: 1px solid var(--line); color: var(--fg); border-radius: 999px;
             height: 34px; min-width: 34px; padding: 0 12px; cursor: pointer; font: inherit; font-size: 14px;
             display: inline-flex; align-items: center; justify-content: center; gap: 6px; }
  .iconbtn:hover { background: var(--cell); }
  .iconbtn.round { padding: 0; font-weight: 700; font-size: 16px; }
  .card.wide { width: min(440px, 92vw); max-height: 88vh; overflow-y: auto; position: relative; }
  .card h3 { font-size: 14px; font-weight: 700; margin: 20px 0 10px; }
  .xbtn { position: absolute; top: 10px; right: 12px; background: none; border: 0; color: var(--muted);
          font-size: 26px; line-height: 1; cursor: pointer; padding: 4px; }
  .statgrid { display: grid; grid-template-columns: repeat(4, 1fr); text-align: center; gap: 4px; }
  .statgrid b { display: block; font-size: 32px; font-weight: 500; font-variant-numeric: tabular-nums; }
  .statgrid span { font-size: 12px; color: var(--muted); }
  .distrow { display: flex; align-items: center; gap: 8px; margin: 5px 0; font-size: 14px; }
  .distrow .k { width: 12px; text-align: right; }
  .distrow .bar { background: var(--cell); color: var(--cell-fg); text-align: right; padding: 2px 8px;
                  min-width: 26px; font-weight: 600; font-variant-numeric: tabular-nums;
                  transition: width .5s cubic-bezier(.2,.8,.2,1); }
  .distrow .bar.today { background: var(--hit); color: var(--hit-fg); }
  .statfoot { display: flex; align-items: center; justify-content: space-between; gap: 16px;
              margin-top: 22px; padding-top: 16px; border-top: 1px solid var(--line); }
  .statfoot small { color: var(--muted); display: block; }
  .statfoot b { font-size: 24px; font-variant-numeric: tabular-nums; font-weight: 500; }
  .help p, .help li { font-size: 14px; line-height: 1.55; }
  .help a { color: var(--fg); text-underline-offset: 2px; }
  .helpintro { margin: 0 0 12px; font-size: 15px !important; }
  .helpkeys { list-style: none; padding: 0; margin: 0 0 12px; display: grid; gap: 6px; }
  .helpkeys li { display: flex; align-items: center; gap: 10px; }
  .helpkeys li > span:first-child { width: 28px; text-align: center; flex: none; font-size: 17px; }
  .keyswitch { display: inline-block; width: 24px !important; height: 14px; border-radius: 7px; background: var(--hit); position: relative; }
  .keyswitch::after { content: ""; position: absolute; top: 2px; right: 2px; width: 10px; height: 10px; border-radius: 50%; background: #fff; }
  .colourkey { display: flex; flex-wrap: wrap; gap: 6px 16px; margin: 0 0 4px; padding: 10px 12px; border-radius: 8px; background: var(--cell); color: var(--cell-fg); }
  .colourkey span { display: inline-flex; align-items: center; gap: 6px; }
  .colourkey .swatch { margin: 0; }
  .helplead { margin: -4px 0 8px; color: var(--muted); }
  .helpgame { --tone: var(--hit); border-bottom: 1px solid var(--line); }
  .helpgame.tone-blue { --tone: #4a78b5; }
  .helpgame.tone-amber { --tone: #c9962a; }
  .helpgame summary { display: flex; align-items: center; gap: 10px; padding: 10px 2px; cursor: pointer; font-weight: 600; list-style: none; }
  .helpgame summary::-webkit-details-marker { display: none; }
  .helpgame summary::after { content: "+"; margin-left: auto; color: var(--muted); font-weight: 400; font-size: 20px; line-height: 1; }
  .helpgame[open] summary::after { content: "−"; }
  .helpgame summary:focus-visible { outline: 2px solid var(--tone); outline-offset: 2px; border-radius: 4px; }
  .hicon { width: 30px; height: 30px; border-radius: 8px; display: grid; place-items: center; font-size: 16px;
           background: color-mix(in srgb, var(--tone) 16%, transparent); }
  .helpbody { padding: 0 2px 10px 40px; }
  .helpbody p { margin: 0 0 6px; }
  .helpfoot { color: var(--muted); font-size: 13px !important; margin: 12px 0 0; }
  .swatch { display: inline-block; width: 14px; height: 14px; border-radius: 3px; vertical-align: -2px; margin-right: 4px; }
  .toast { position: fixed; left: 50%; top: 80px; transform: translateX(-50%); background: var(--fg); color: var(--bg);
           padding: 8px 14px; border-radius: 6px; font-size: 14px; z-index: 20; opacity: 0; transition: opacity .2s; pointer-events: none; }
  .toast.show { opacity: 1; }
  @media (max-width: 700px) {
    .topleft { top: 10px; left: 12px; }
    .topbar { position: static; justify-content: flex-end; padding: 10px 12px 0; gap: 10px; }
    .switch .long { display: none; }
    .hubgrid { grid-template-columns: 1fr; gap: 8px; }
    .navbar { padding: 8px 10px; }
    .brand { font-size: 16px; }
    .navactions { gap: 4px; }
    .navactions .iconbtn { width: 32px; height: 32px; min-width: 32px; font-size: 14px; }
    .navactions .switch > span:last-child { display: none; }
    .hubtitle { font-size: 30px; }
    .grow { grid-template-columns: 36px 1fr auto 10px; padding: 10px 12px; gap: 10px; }
    .grow .gicon { width: 36px; height: 36px; font-size: 19px; border-radius: 9px; }
    .grow + .grow::before { left: 58px; }
    .grow .gstat { font-size: 12px; max-width: 26vw; white-space: normal; text-align: right; }
    .partycard { grid-template-columns: 1fr; min-height: 170px; }
    .partycta { justify-self: start; }
    .rkrow { grid-template-columns: 20px 36px 1fr auto auto; gap: 8px; padding: 6px 8px; }
    .rkrow img { width: 36px; height: 36px; }
    .rinklane { height: 200px; border-radius: 18px; }
    .puck { font-size: 13px; padding: 0 12px; }
    .shopts, .pttiles { grid-template-columns: 1fr; }
    .pttile { min-height: 64px; }
    .ptchoice { grid-template-columns: 1fr; }
    .gcard { grid-template-columns: 40px 1fr auto; padding: 10px 12px; gap: 12px; }
    .gicon { width: 40px; height: 40px; font-size: 20px; }
    .gtext small { font-size: 12px; }
    .gstat { font-size: 12px; padding: 4px 9px; max-width: 34vw; white-space: normal; text-align: center; }
    .gtitle h2 { font-size: 23px; }
    .gtitle { gap: 11px; padding-bottom: 11px; }
    .gticon { width: 40px; height: 40px; font-size: 21px; border-radius: 11px; }
    .backbtn { font-size: 14px; }
    header { padding-top: 14px; }
    h1 { font-size: 36px; }
    main { padding: 4px 10px 32px; }
    .search input { padding: 14px 12px; }
    .board { overflow: visible; }
    .board table, .board tbody { display: block; min-width: 0; }
    .board thead { display: none; }
    .board tr { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; margin: 0 0 16px; }
    .board td { display: flex; flex-direction: column; align-items: center; justify-content: center;
         height: 58px; min-width: 0; padding: 14px 2px 4px; font-size: 14px; position: relative; }
    .board td::before { content: attr(data-label); position: absolute; top: 4px; left: 0; right: 0;
                 font-size: 10px; opacity: .75; }
    .board td.name { grid-column: 1 / -1; height: auto; padding: 0 2px; font-weight: 600; font-size: 15px;
              align-items: flex-start; min-width: 0; }
    .board td.name::before { content: none; }
    .board td.team { min-width: 0; flex-direction: row; gap: 4px; }
    .board td.team img { width: 20px; height: 20px; margin: 0; }
    .tabs button { padding: 6px 13px; font-size: 14px; }
    .seasons td { font-size: 14px; height: 40px; padding: 0 4px; }
    .divs { grid-template-columns: repeat(2, 1fr); gap: 10px; }
    .teambtn { font-size: 13px; padding: 6px 8px; gap: 6px; }
    .teambtn img { width: 22px; height: 22px; }
    .ttcard img { width: 76px; height: 76px; }
    .hltlogo { width: 62px; height: 62px; }
    .twline { font-size: 14px; padding: 12px; gap: 10px; }
    .sebtn { font-size: 13px; padding: 8px 11px; }
    .jystop { min-width: 88px; padding: 8px; }
    .cngrid { gap: 5px; }
    .cntile { min-height: 64px; }
    .cntile b { font-size: 12px; }
    .cntile small { font-size: 10px; }
    .mapsvg { aspect-ratio: 4 / 3; }
    .mapctl .tabs button { padding: 5px 9px; font-size: 12px; }
    .jyarrow { display: none; }
    .blurbox { width: 180px; height: 180px; }
    .tabs button { padding: 6px 11px; }
    .hlpair { grid-template-columns: 1fr 1fr; gap: 8px; }
    .hlvs { display: none; }
    .hlcard { min-height: 290px; padding: 12px 8px; }
    .hlimg { width: 76px; height: 76px; }
    .hlname { font-size: 16px; }
    .hlval b { font-size: 36px; }
    .hlbtns .hlbtn { font-size: 14px; padding: 10px 8px; }
    .lbtabs button { font-size: 12px; padding: 5px 9px; }
    .iconbtn .txt { display: none; }
    .iconbtn { padding: 0; width: 34px; }
    .topleft { gap: 6px; }
    .lbtabs { gap: 2px; }
    .num { padding: 0; gap: 4px; justify-content: center; }
    .arrow { font-size: 16px; }
    .card { padding: 20px; }
    .statgrid b { font-size: 26px; }
  }
  .foot small { display: block; margin-top: 6px; font-size: 12px; opacity: .85; }
  .foot { text-align: center; color: var(--muted); font-size: 13px; padding: 32px 16px 8px; }
  @media (prefers-reduced-motion: no-preference) {
    td { transition: background .3s; }
    .newrow { animation: rowin .35s cubic-bezier(.2,.8,.2,1) both; }
  }
  @keyframes rowin { from { opacity: 0; transform: translateY(-8px); } to { opacity: 1; transform: none; } }
  /* Rinkside visual edition — a deliberately separate, reversible skin. */
  :root {
    --bg: #f5f8fa; --fg: #102636; --muted: #62717b; --cell: #e8eef2; --cell-fg: #18303e;
    --hit: #157a65; --hit-fg: #fff; --near: #e2ac34; --near-fg: #30230a; --line: #d5e0e6; --link: #0d6f89;
    --panel: #ffffff; --scrim: rgba(5, 23, 34, .58); --cream: #edf1ea; --silbg: transparent;
    --sea: #dcecf3; --land: #eef0e7; --coast: #aab9ae;
    --grouped: #edf3f5; --row: #ffffff; --sep: rgba(16, 38, 54, .12); --label2: #61727e;
  }
  :root[data-theme="dark"] {
    --bg: #0b1822; --fg: #edf5f7; --muted: #a6b5bd; --cell: #182b38; --cell-fg: #eef6f8;
    --hit: #35ad91; --hit-fg: #071c20; --near: #f0bd48; --near-fg: #201807; --line: #2d4655; --link: #70d2e3;
    --panel: #11232e; --scrim: rgba(0,0,0,.72); --cream: #253a39; --silbg: var(--cream);
    --sea: #12303d; --land: #263c3d; --coast: #50706c;
    --grouped: #09151d; --row: #11232e; --sep: rgba(184, 211, 220, .16); --label2: #a6b5bd;
  }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {
      --bg: #0b1822; --fg: #edf5f7; --muted: #a6b5bd; --cell: #182b38; --cell-fg: #eef6f8;
      --hit: #35ad91; --hit-fg: #071c20; --near: #f0bd48; --near-fg: #201807; --line: #2d4655; --link: #70d2e3;
      --panel: #11232e; --scrim: rgba(0,0,0,.72); --cream: #253a39; --silbg: var(--cream);
      --sea: #12303d; --land: #263c3d; --coast: #50706c;
      --grouped: #09151d; --row: #11232e; --sep: rgba(184, 211, 220, .16); --label2: #a6b5bd;
    }
  }
  body {
    min-height: 100vh;
    background:
      radial-gradient(900px 480px at 50% -240px, rgba(57, 146, 176, .16), transparent 70%),
      linear-gradient(135deg, #f8fbfc 0%, var(--bg) 52%, #edf5f3 100%);
  }
  body.hubmode {
    background:
      radial-gradient(800px 420px at 85% -140px, rgba(38, 151, 132, .15), transparent 68%),
      radial-gradient(620px 360px at 6% 18%, rgba(27, 117, 157, .10), transparent 70%),
      var(--grouped);
  }
  :root[data-theme="dark"] body { background: var(--bg); }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) body { background: var(--bg); }
  }
  .navbar {
    min-height: 58px; padding-top: 11px; padding-bottom: 11px;
    box-shadow: 0 1px 0 rgba(9, 31, 45, .05), 0 8px 28px rgba(22, 54, 70, .05);
  }
  .brand { font-size: 18px; letter-spacing: .12em; }
  .brand span { padding: 4px 9px 7px; background-color: color-mix(in srgb, var(--hit) 10%, transparent);
                border-radius: 7px 7px 4px 4px; background-position: bottom 3px center; }
  .navactions .iconbtn { border-radius: 10px; background: color-mix(in srgb, var(--panel) 82%, var(--cell));
                           box-shadow: inset 0 0 0 1px var(--sep); }
  header { padding: 34px 16px 16px; }
  h1 { font-size: clamp(40px, 6vw, 58px); letter-spacing: -.045em; }
  header h1::after { width: 114px; height: 6px; margin-top: 8px; border-radius: 99px;
                     background: linear-gradient(90deg, var(--hit), #56b9cc, var(--hit)); }
  .sub { font-size: 15px; letter-spacing: .01em; }
  main { padding-bottom: 56px; }
  #view-hub { max-width: 760px; padding-top: 28px; }
  .hubhead { padding: 20px 22px; margin: 0 0 20px; border: 1px solid var(--line); border-radius: 18px;
             background: color-mix(in srgb, var(--panel) 88%, transparent); box-shadow: 0 12px 32px rgba(23, 59, 75, .06); }
  .hubdate { color: var(--hit); font-weight: 700; letter-spacing: .06em; text-transform: uppercase; font-size: 12px; }
  .hubtitle { margin-top: 4px; font-size: clamp(29px, 5vw, 38px); letter-spacing: -.04em; }
  .hubmeter { height: 7px; background: color-mix(in srgb, var(--hit) 12%, var(--cell)); }
  .hubmeter i { background: linear-gradient(90deg, var(--hit), #2e9db5); }
  .hubsec { margin-bottom: 28px; }
  .hubsec h2 { display: flex; align-items: center; gap: 9px; margin: 0 4px 10px; font-size: 18px; letter-spacing: -.02em; }
  .hubsec h2::before { content: ""; width: 7px; height: 7px; border-radius: 50%; background: var(--tone); box-shadow: 0 0 0 4px color-mix(in srgb, var(--tone) 14%, transparent); }
  .glist, .hubgrid { border: 1px solid var(--line); border-radius: 17px; overflow: hidden;
                      box-shadow: 0 10px 28px rgba(22, 54, 70, .055); }
  .grow, .gcard { min-height: 74px; background: color-mix(in srgb, var(--row) 94%, transparent); }
  .grow:hover:not(:disabled), .gcard:hover:not(:disabled) { background: color-mix(in srgb, var(--tone) 7%, var(--panel)); }
  .grow .gicon, .gcard .gicon { border-radius: 13px; background: color-mix(in srgb, var(--tone) 13%, transparent); }
  .grow .gtext b, .gcard .gtext b { font-weight: 700; letter-spacing: -.015em; }
  .grow .gtext small, .gcard .gtext small { color: var(--muted); }
  .grow .gstat, .gcard .gstat { color: var(--muted); font-size: 13px; }
  .partycard { border: 1px solid rgba(118, 208, 201, .3); border-radius: 20px; background: linear-gradient(115deg, #09283a, #0e5360 110%);
               box-shadow: 0 16px 34px rgba(7, 42, 55, .18); }
  .partycta { color: #0b3140; box-shadow: 0 5px 14px rgba(0,0,0,.14); }
  .gamebar { max-width: 1180px; margin-bottom: 20px; padding: 18px 20px; border: 1px solid var(--line); border-radius: 17px;
             background: color-mix(in srgb, var(--panel) 88%, transparent); box-shadow: 0 10px 28px rgba(23, 59, 75, .055); }
  .backbtn { color: var(--muted); }
  .gtitle { padding-bottom: 2px; border-bottom: 0; }
  .gticon { border-radius: 14px; background: color-mix(in srgb, var(--tone) 14%, transparent); }
  .gtitle h2 { font-size: clamp(25px, 4vw, 32px); letter-spacing: -.04em; }
  #modeLabel { color: var(--muted); }
  .gamesel, .pickstat select, .numrow select, .search input, .numrow input, .lbname input {
    border-color: var(--line); border-radius: 10px; background: color-mix(in srgb, var(--panel) 95%, transparent);
    box-shadow: inset 0 1px 1px rgba(13, 39, 52, .03); }
  .gamesel:focus, .pickstat select:focus, .numrow select:focus, .search input:focus, .numrow input:focus, .lbname input:focus {
    border-color: var(--link); box-shadow: 0 0 0 3px color-mix(in srgb, var(--link) 18%, transparent); outline: none; }
  .tabs { padding: 4px; border-color: var(--line); background: color-mix(in srgb, var(--panel) 78%, transparent); box-shadow: 0 5px 16px rgba(23, 59, 75, .04); }
  .tabs button[aria-selected="true"] { background: var(--fg); color: var(--panel); box-shadow: 0 2px 6px rgba(8, 30, 44, .18); }
  .btn, .profile { border-radius: 10px; box-shadow: 0 3px 9px rgba(11, 42, 57, .12); }
  .ttcard, .ptquestion { border: 1px solid var(--line); border-radius: 18px; padding: 16px 20px; margin: 10px auto;
                          width: min(660px, 100%); background: color-mix(in srgb, var(--panel) 92%, transparent); box-shadow: 0 9px 24px rgba(23, 59, 75, .05); }
  .ttcard img { border: 4px solid color-mix(in srgb, var(--hit) 12%, var(--panel)); box-shadow: 0 4px 16px rgba(15, 48, 64, .12); }
  .ttq { font-size: 20px; font-weight: 650; letter-spacing: -.02em; }
  .shopts { gap: 10px; }
  .shopt { border-radius: 12px; border: 1px solid var(--line); background: color-mix(in srgb, var(--panel) 90%, transparent);
           box-shadow: 0 4px 12px rgba(23, 59, 75, .04); }
  .shopt:hover:not(:disabled) { border-color: var(--link); transform: translateY(-2px); }
  .chips .chip, .archbar { border: 1px solid var(--line); background: color-mix(in srgb, var(--panel) 82%, var(--cell)); }
  .seasons { border-spacing: 0 8px; }
  .seasons td, .cutable td { box-shadow: 0 3px 9px rgba(23, 59, 75, .045); }
  .cuboard { padding: 10px; border: 1px solid var(--line); border-radius: 17px; background: color-mix(in srgb, var(--panel) 87%, transparent); box-shadow: 0 10px 28px rgba(23, 59, 75, .05); }
  .cutable { border-spacing: 0 7px; }
  .cutable th { padding: 9px 11px; color: var(--muted); font-size: 11px; letter-spacing: .055em; text-transform: uppercase; }
  #view-cups .cutable thead th { background: var(--panel); box-shadow: 0 5px 0 var(--panel); }
  .cutable td { background: color-mix(in srgb, var(--cell) 78%, var(--panel)); }
  .cutable tr:hover td { background: color-mix(in srgb, var(--link) 8%, var(--panel)); }
  .cups-controls { border: 1px solid var(--line); border-radius: 17px; padding: 16px; background: color-mix(in srgb, var(--panel) 90%, transparent); box-shadow: 0 10px 28px rgba(23, 59, 75, .05); }
  .hlcard, .mapwrap .mapsvg { border-radius: 17px; box-shadow: 0 10px 24px rgba(23, 59, 75, .06); }
  .hlcard { border-color: var(--line); background: color-mix(in srgb, var(--panel) 88%, var(--cell)); }
  .foot { margin-top: 28px; }
  @media (max-width: 700px) {
    header { padding: 24px 14px 10px; }
    #view-hub { padding-top: 16px; }
    .hubhead { padding: 17px; border-radius: 15px; }
    .gamebar { padding: 13px 14px; border-radius: 14px; }
    .grow, .gcard { min-height: 64px; }
    .ttcard, .ptquestion, .cups-controls { border-radius: 14px; }
    .cuboard { padding: 5px; border-radius: 14px; }
  }
  @media (prefers-reduced-motion: no-preference) {
    .glist, .hubgrid, .gamebar, .ttcard, .ptquestion, .cups-controls, .cuboard { animation: rinkfade .38s ease both; }
    @keyframes rinkfade { from { opacity: 0; transform: translateY(7px); } to { opacity: 1; transform: none; } }
  }
  /* Arena visual edition — polished game UI, layered over the Rinkside skin. */
  :root { --arena: #071b29; --arena-deep: #04131e; --arena-blue: #1d92b5; --arena-mint: #4bd5bb; --arena-glow: rgba(75, 213, 187, .22); }
  body {
    background:
      radial-gradient(900px 540px at 50% -240px, rgba(31, 155, 185, .23), transparent 68%),
      radial-gradient(700px 430px at 108% 25%, rgba(68, 207, 179, .12), transparent 70%),
      linear-gradient(145deg, #f6fafb, var(--bg) 55%, #e7f1f2);
  }
  body.hubmode {
    background:
      radial-gradient(940px 520px at 50% -260px, rgba(30, 146, 177, .20), transparent 68%),
      radial-gradient(640px 420px at 105% 20%, rgba(52, 189, 161, .12), transparent 70%),
      var(--grouped);
  }
  body::before {
    content: ""; position: fixed; inset: 58px 0 0; z-index: 0; pointer-events: none; opacity: .38;
    background-image: linear-gradient(rgba(16, 76, 94, .035) 1px, transparent 1px), linear-gradient(90deg, rgba(16, 76, 94, .025) 1px, transparent 1px);
    background-size: 44px 44px;
    -webkit-mask-image: linear-gradient(to bottom, black, transparent 68%); mask-image: linear-gradient(to bottom, black, transparent 68%);
  }
  main, .navbar { position: relative; z-index: 1; }
  .navbar {
    min-height: 62px; padding-top: 12px; padding-bottom: 12px; color: #edf8fb;
    background: linear-gradient(105deg, var(--arena-deep), var(--arena) 55%, #0c3341);
    border-bottom-color: rgba(131, 220, 226, .18);
    box-shadow: 0 12px 30px rgba(2, 14, 23, .20);
  }
  body.hubmode .navbar { background: linear-gradient(105deg, var(--arena-deep), var(--arena) 55%, #0c3341); }
  .navbar .brand, .navbar .backbtn, .navbar .switch { color: #edf8fb; }
  .navbar .brand { font-size: 17px; letter-spacing: .15em; }
  .navbar .brand span { background-color: rgba(94, 224, 207, .09); background-image: linear-gradient(90deg, var(--arena-mint), #7ecfe7, var(--arena-mint)); }
  .navbar .navactions .iconbtn, .navbar .themebtn {
    color: #ecf8fa; border-color: rgba(171, 230, 236, .19); background: rgba(255,255,255,.075); box-shadow: none;
  }
  .navbar .navactions .iconbtn:hover, .navbar .themebtn:hover { background: rgba(255,255,255,.15); }
  .navbar .track { background: rgba(235, 249, 251, .25); }
  .navbar .switch input:checked + .track { background: var(--arena-mint); }
  header { padding-top: 44px; }
  h1 { font-weight: 850; }
  #view-hub { max-width: 800px; }
  .hubhead {
    position: relative; isolation: isolate; overflow: hidden; padding: 28px 28px 24px; border: 1px solid rgba(104, 212, 222, .26); border-radius: 22px;
    color: #f2fbfc; background: linear-gradient(118deg, #061d2b, #0b3d4b 62%, #0a5960);
    box-shadow: 0 22px 48px rgba(7, 37, 49, .18), inset 0 1px rgba(255,255,255,.12);
  }
  .hubhead::before { content: ""; position: absolute; z-index: -1; width: 330px; aspect-ratio: 1; right: -88px; top: -162px; border: 1px solid rgba(172, 241, 238, .26); border-radius: 50%; box-shadow: 0 0 0 38px rgba(172, 241, 238, .035), 0 0 0 76px rgba(172, 241, 238, .025); }
  .hubhead::after { content: ""; position: absolute; z-index: -1; left: 0; right: 0; bottom: 0; height: 3px; background: linear-gradient(90deg, var(--arena-mint), #80dced, var(--arena-mint)); }
  .hubdate { color: #94e4dd; }
  .hubtitle { color: #fff; margin-bottom: 15px; }
  .hubmeter { background: rgba(255,255,255,.16); box-shadow: inset 0 1px 2px rgba(0,0,0,.22); }
  .hubmeter i { background: linear-gradient(90deg, var(--arena-mint), #7ddded); box-shadow: 0 0 16px rgba(98, 222, 213, .5); }
  .hubprogress, .hubnext b { color: rgba(239, 251, 252, .78); }
  .partycard { min-height: 164px; border-radius: 21px; background: linear-gradient(120deg, #071b29, #133f58 60%, #1f6870); box-shadow: 0 18px 34px rgba(7, 37, 49, .17); }
  .partycard:hover:not(:disabled) { transform: translateY(-3px); box-shadow: 0 23px 40px rgba(7, 37, 49, .24); }
  .partycta { background: linear-gradient(135deg, #ecffff, #a1e7e5); color: #073039; }
  .hubsec { margin-bottom: 30px; }
  .hubsec h2 { margin-left: 7px; font-size: 14px; font-weight: 800; letter-spacing: .095em; text-transform: uppercase; color: var(--muted); }
  .hubsec h2::before { width: 8px; height: 8px; box-shadow: 0 0 0 5px color-mix(in srgb, var(--tone) 16%, transparent), 0 0 14px color-mix(in srgb, var(--tone) 32%, transparent); }
  .glist, .hubgrid { border-radius: 18px; border-color: rgba(18, 79, 98, .14); background: rgba(255,255,255,.36); box-shadow: 0 16px 34px rgba(14, 51, 66, .08), inset 0 1px rgba(255,255,255,.7); }
  .grow, .gcard { min-height: 78px; transition: transform .22s cubic-bezier(.2,.8,.2,1), background-color .22s, box-shadow .22s; }
  .grow::after, .gcard::after { content: ""; position: absolute; left: 0; top: 15px; bottom: 15px; width: 3px; border-radius: 0 5px 5px 0; background: var(--tone); opacity: 0; transition: opacity .2s; }
  .grow:hover:not(:disabled), .gcard:hover:not(:disabled) { transform: translateX(4px); background: color-mix(in srgb, var(--tone) 9%, var(--panel)); box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--tone) 22%, transparent); }
  .grow:hover:not(:disabled)::after, .gcard:hover:not(:disabled)::after { opacity: 1; }
  .grow .gicon, .gcard .gicon { position: relative; overflow: hidden; background: linear-gradient(135deg, color-mix(in srgb, var(--tone) 24%, white), color-mix(in srgb, var(--tone) 8%, transparent)); }
  .grow .gicon::after, .gcard .gicon::after { content: ""; position: absolute; inset: 0; background: linear-gradient(135deg, rgba(255,255,255,.5), transparent 44%); }
  .grow .gstat, .gcard .gstat { padding: 5px 9px; border-radius: 999px; background: color-mix(in srgb, var(--cell) 72%, var(--panel)); }
  .gamebar {
    position: relative; isolation: isolate; overflow: hidden; max-width: 1220px; padding: 19px 22px; border: 1px solid rgba(95, 210, 218, .25); border-radius: 19px;
    color: #edf9fb; background: linear-gradient(112deg, #061d2b, #0a3948 62%, #0c5960); box-shadow: 0 18px 40px rgba(8, 38, 51, .15);
  }
  .gamebar::after { content: ""; position: absolute; z-index: -1; width: 280px; aspect-ratio: 1; right: -70px; top: -148px; border-radius: 50%; border: 1px solid rgba(183, 243, 239, .25); box-shadow: 0 0 0 42px rgba(183, 243, 239, .045), 0 0 0 85px rgba(183, 243, 239, .025); }
  .gamebar .backbtn, .gamebar #modeLabel { color: rgba(235, 249, 250, .72); }
  .gamebar .backbtn:hover { color: #fff; }
  .gamebar .gticon { color: #052d35; background: linear-gradient(135deg, #b7f3ec, #64cbd5); box-shadow: 0 8px 20px rgba(0,0,0,.18); }
  .gamebar .gtitle h2 { color: #fff; }
  .tabs { border-color: var(--line); border-radius: 12px; }
  .tabs button { border-radius: 8px; font-weight: 650; }
  .tabs button[aria-selected="true"] { background: linear-gradient(135deg, var(--arena), #13546a); color: #effbfc; }
  .btn, .profile { border-radius: 10px; font-weight: 750; letter-spacing: .01em; background: linear-gradient(135deg, #188c78, #27a88f); box-shadow: 0 7px 15px rgba(18, 122, 101, .22), inset 0 1px rgba(255,255,255,.18); transition: transform .16s ease, box-shadow .16s ease, filter .16s ease; }
  .btn:hover:not(:disabled), .profile:hover { transform: translateY(-2px); filter: brightness(1.04); box-shadow: 0 10px 20px rgba(18, 122, 101, .28), inset 0 1px rgba(255,255,255,.2); opacity: 1; }
  .btn:active:not(:disabled), .profile:active { transform: translateY(1px); box-shadow: 0 3px 8px rgba(18, 122, 101, .18); }
  .search input, .numrow input, .gamesel, .pickstat select, .numrow select { min-height: 48px; border-radius: 12px; }
  .list { border-radius: 12px; box-shadow: 0 14px 30px rgba(10, 43, 57, .16); }
  .ttcard, .ptquestion { border-radius: 18px; }
  .ttcard { background: linear-gradient(145deg, color-mix(in srgb, var(--panel) 94%, transparent), color-mix(in srgb, var(--cell) 28%, var(--panel))); }
  .ttq { position: relative; margin: 14px auto 12px; padding: 16px 18px; width: min(660px, 100%); border: 1px solid var(--line); border-radius: 14px; background: color-mix(in srgb, var(--panel) 82%, transparent); box-shadow: 0 8px 19px rgba(17, 54, 68, .045); }
  #view-trophy .optrow { width: fit-content; max-width: 100%; margin: 0 auto 14px; padding: 7px 11px; border: 1px solid var(--line); border-radius: 13px; background: color-mix(in srgb, var(--panel) 88%, transparent); box-shadow: 0 8px 18px rgba(17, 54, 68, .045); }
  #view-trophy .pickstat { font-weight: 700; color: var(--muted); }
  #view-trophy .pickstat select { min-height: 38px; margin-left: 3px; font-weight: 600; }
  .shdots { gap: 8px; margin-bottom: 13px; }
  .shdot { width: 32px; height: 32px; border: 1px solid var(--line); background: color-mix(in srgb, var(--panel) 74%, var(--cell)); box-shadow: 0 3px 8px rgba(17, 54, 68, .045); }
  .shdot.now { color: #06313b; border-color: transparent; background: linear-gradient(135deg, #b7f3ec, #6dd4da); box-shadow: 0 0 0 3px var(--arena-glow), 0 4px 11px rgba(36, 164, 159, .18); }
  .shopt { position: relative; overflow: hidden; min-height: 62px; border-radius: 13px; font-weight: 700; text-align: left; padding: 13px 16px 13px 48px; transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease, background-color .18s; }
  .shopt::before { content: ""; position: absolute; left: 16px; top: 50%; width: 18px; height: 18px; transform: translateY(-50%); border: 2px solid color-mix(in srgb, var(--fg) 32%, transparent); border-radius: 50%; }
  .trname { position: relative; z-index: 1; display: block; padding-right: 56px; }
  .trlogo { position: absolute; z-index: 0; right: -5px; top: 50%; width: 92px; height: 92px; object-fit: contain;
             transform: translateY(-50%); opacity: .18; filter: drop-shadow(0 5px 5px rgba(4, 24, 35, .14)); pointer-events: none; }
  .shopt:hover:not(:disabled) .trlogo { opacity: .28; transform: translateY(-50%) scale(1.06); }
  /* Keep the crest in its real team colours after a choice is graded. The
     former white inversion turned detailed crests into an unrecognizable blob. */
  .shopt.right .trlogo { opacity: .43; filter: brightness(1.16) saturate(1.2) drop-shadow(0 5px 6px rgba(0,0,0,.2)); animation: trophy-crest-win .62s cubic-bezier(.18,.85,.25,1.16) both; }
  .shopt.wrong .trlogo { opacity: .31; filter: brightness(1.12) saturate(1.15) drop-shadow(0 5px 6px rgba(0,0,0,.2)); }
  @keyframes trophy-crest-win {
    0% { transform: translateY(-50%) scale(.42) rotate(-14deg); }
    58% { transform: translateY(-50%) scale(1.28) rotate(4deg); }
    78% { transform: translateY(-50%) scale(.93) rotate(-1deg); }
    100% { transform: translateY(-50%) scale(1) rotate(0); }
  }
  @keyframes trophy-answer-win {
    0% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--hit) 0%, transparent); }
    45% { box-shadow: 0 0 0 6px color-mix(in srgb, var(--hit) 20%, transparent), 0 0 26px color-mix(in srgb, var(--hit) 48%, transparent); }
    100% { box-shadow: 0 0 0 12px transparent, 0 0 0 transparent; }
  }
  .shopt.right { animation: trophy-answer-win .62s ease-out both; }
  .shopt:hover:not(:disabled) { transform: translateY(-3px); border-color: var(--arena-blue); background: color-mix(in srgb, var(--arena-blue) 8%, var(--panel)); box-shadow: 0 10px 18px rgba(18, 74, 92, .12); }
  .shopt.right, .shopt.wrong { color: #fff; }
  .shopt.right::before { border-color: #fff; box-shadow: inset 0 0 0 4px var(--hit-fg); }
  .shopt.wrong::before { border-color: #fff; box-shadow: inset 0 0 0 4px #fff; }
  .chips .chip, .archbar { border-radius: 10px; }
  .cuboard, .cups-controls { border-radius: 18px; }
  .cutable td { background: color-mix(in srgb, var(--panel) 70%, var(--cell)); }
  .hlcard { border-radius: 18px; }
  .modal { -webkit-backdrop-filter: blur(8px); backdrop-filter: blur(8px); }
  .card { border: 1px solid var(--line); border-radius: 18px; box-shadow: 0 24px 70px rgba(1, 17, 27, .34); }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) body, :root:not([data-theme="light"]) body.hubmode { background: radial-gradient(700px 460px at 50% -190px, #123c4d, var(--bg) 62%); }
    :root:not([data-theme="light"]) .glist, :root:not([data-theme="light"]) .hubgrid { background: rgba(14, 39, 52, .82); border-color: rgba(134, 210, 219, .16); }
  }
  :root[data-theme="dark"] body, :root[data-theme="dark"] body.hubmode { background: radial-gradient(700px 460px at 50% -190px, #123c4d, var(--bg) 62%); }
  :root[data-theme="dark"] .glist, :root[data-theme="dark"] .hubgrid { background: rgba(14, 39, 52, .82); border-color: rgba(134, 210, 219, .16); }
  @media (max-width: 700px) {
    body::before { display: none; }
    .navbar { min-height: 54px; }
    header { padding-top: 28px; }
    .hubhead { padding: 22px 19px 19px; border-radius: 18px; }
    .hubtitle { font-size: 31px; }
    .partycard { min-height: 166px; }
    .grow, .gcard { min-height: 67px; }
    .grow:hover:not(:disabled), .gcard:hover:not(:disabled) { transform: none; }
    .gamebar { padding: 15px; border-radius: 16px; }
    .shopt { min-height: 56px; }
    .trlogo { width: 78px; height: 78px; right: -4px; }
    #view-trophy .optrow { width: 100%; justify-content: center; gap: 7px; }
  }
  @media (prefers-reduced-motion: reduce) {
    .shopt.right, .shopt.right .trlogo { animation: none; }
    .partycard, .grow, .gcard, .btn, .profile, .shopt { transition: none; }
  }

  /* Neutral foundation + player-selected interface colour.  Green and red are
     reserved for game feedback, never used as the app's decorative colour. */
  :root {
    --accent: #242424; --accent-ink: #fff;
    --hit: #1b9853; --hit-fg: #fff; --near: #ddb237; --near-fg: #2b2108;
    --arena: #242424; --arena-deep: #111; --arena-blue: var(--accent); --arena-mint: var(--accent); --arena-glow: color-mix(in srgb, var(--accent) 20%, transparent);
  }
  :root[data-theme="dark"] { --hit: #35b96d; --hit-fg: #07190d; --near: #e6bd4e; --near-fg: #211905; }
  @media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --hit: #35b96d; --hit-fg: #07190d; --near: #e6bd4e; --near-fg: #211905; } }
  body {
    background: radial-gradient(800px 400px at 50% -220px, rgba(0,0,0,.055), transparent 70%), linear-gradient(145deg, #fbfbfa, #f2f2ef 65%, #ebebe7);
  }
  body.hubmode { background: radial-gradient(750px 400px at 50% -230px, rgba(0,0,0,.065), transparent 70%), #f0f0ed; }
  body::before { opacity: .18; background-image: linear-gradient(rgba(0,0,0,.05) 1px, transparent 1px), linear-gradient(90deg, rgba(0,0,0,.04) 1px, transparent 1px); }
  .navbar, body.hubmode .navbar {
    background: linear-gradient(105deg, color-mix(in srgb, var(--accent) 72%, #000), var(--accent) 75%, color-mix(in srgb, var(--accent) 84%, #000));
    border-bottom-color: color-mix(in srgb, var(--accent-ink) 17%, transparent);
  }
  .navbar .brand span { background-color: color-mix(in srgb, var(--accent-ink) 9%, transparent); background-image: linear-gradient(90deg, var(--accent-ink), color-mix(in srgb, var(--accent-ink) 62%, transparent), var(--accent-ink)); }
  .navbar .switch input:checked + .track { background: color-mix(in srgb, var(--accent-ink) 76%, var(--accent)); }
  .hubhead {
    border-color: color-mix(in srgb, var(--accent) 35%, transparent); background: linear-gradient(118deg, color-mix(in srgb, var(--accent) 77%, #000), var(--accent) 70%, color-mix(in srgb, var(--accent) 82%, #000));
  }
  .hubhead::after { background: linear-gradient(90deg, color-mix(in srgb, var(--accent-ink) 80%, transparent), var(--accent-ink), color-mix(in srgb, var(--accent-ink) 80%, transparent)); }
  .hubdate { color: color-mix(in srgb, var(--accent-ink) 70%, transparent); }
  .hubmeter i { background: var(--accent-ink); box-shadow: 0 0 16px color-mix(in srgb, var(--accent-ink) 32%, transparent); }
  .partycard { border-color: color-mix(in srgb, var(--accent) 38%, transparent); background: linear-gradient(120deg, color-mix(in srgb, var(--accent) 82%, #000), var(--accent) 74%, color-mix(in srgb, var(--accent) 68%, #000)); }
  .partycta { background: var(--accent-ink); color: var(--accent); }
  .hubsec h2::before { background: var(--accent); box-shadow: 0 0 0 5px color-mix(in srgb, var(--accent) 14%, transparent), 0 0 14px color-mix(in srgb, var(--accent) 30%, transparent); }
  .grow:hover:not(:disabled), .gcard:hover:not(:disabled) { background: color-mix(in srgb, var(--accent) 8%, var(--panel)); box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--accent) 25%, transparent); }
  .grow::after, .gcard::after { background: var(--accent); }
  .gamebar { border-color: color-mix(in srgb, var(--accent) 38%, transparent); background: linear-gradient(112deg, color-mix(in srgb, var(--accent) 82%, #000), var(--accent) 72%, color-mix(in srgb, var(--accent) 66%, #000)); }
  .gamebar .gticon { color: var(--accent); background: var(--accent-ink); }
  .tabs button[aria-selected="true"] { background: var(--accent); color: var(--accent-ink); }
  .btn, .profile { color: var(--accent-ink); background: linear-gradient(135deg, color-mix(in srgb, var(--accent) 88%, white), var(--accent)); box-shadow: 0 7px 15px color-mix(in srgb, var(--accent) 25%, transparent), inset 0 1px color-mix(in srgb, var(--accent-ink) 18%, transparent); }
  .btn:hover:not(:disabled), .profile:hover { box-shadow: 0 10px 20px color-mix(in srgb, var(--accent) 30%, transparent), inset 0 1px color-mix(in srgb, var(--accent-ink) 20%, transparent); }
  .switch input:checked + .track { background: var(--accent); }
  .shdot.now { color: var(--accent-ink); background: var(--accent); box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent) 19%, transparent), 0 4px 11px color-mix(in srgb, var(--accent) 20%, transparent); }
  .shopt:hover:not(:disabled) { border-color: var(--accent); background: color-mix(in srgb, var(--accent) 7%, var(--panel)); box-shadow: 0 10px 18px color-mix(in srgb, var(--accent) 14%, transparent); }
  .settingscard { width: min(460px, 92vw); padding: 25px; }
  .settingskicker { margin: 0 0 4px; color: var(--muted); font-size: 12px; font-weight: 800; letter-spacing: .09em; text-transform: uppercase; }
  .settingscard h2 { margin: 0 0 7px; font-weight: 800; letter-spacing: -.03em; }
  .settingsintro { margin: 0 0 19px; color: var(--muted); font-size: 14px; line-height: 1.45; }
  .accentgrid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 9px; }
  .accentchoice { display: grid; place-items: center; gap: 6px; min-height: 72px; padding: 8px 4px; border: 1px solid var(--line); border-radius: 12px; background: color-mix(in srgb, var(--panel) 88%, var(--cell)); color: var(--fg); font: inherit; font-size: 12px; cursor: pointer; transition: border-color .16s, transform .16s, box-shadow .16s; }
  .accentchoice i { display: block; width: 25px; height: 25px; border-radius: 50%; background: var(--swatch); box-shadow: inset 0 1px rgba(255,255,255,.38), 0 3px 7px rgba(0,0,0,.14); }
  .accentchoice:hover { transform: translateY(-2px); border-color: color-mix(in srgb, var(--swatch) 60%, var(--line)); }
  .accentchoice[aria-pressed="true"] { border-color: var(--accent); box-shadow: 0 0 0 2px color-mix(in srgb, var(--accent) 19%, transparent); }
  .accentchoice[aria-pressed="true"] i { box-shadow: inset 0 0 0 3px color-mix(in srgb, var(--panel) 92%, transparent), 0 3px 7px rgba(0,0,0,.14); }
  .customaccent { display: flex; align-items: center; justify-content: space-between; gap: 14px; margin-top: 13px; padding: 12px 13px; border: 1px solid var(--line); border-radius: 12px; background: color-mix(in srgb, var(--panel) 72%, var(--cell)); cursor: pointer; }
  .customaccent b, .customaccent small { display: block; }
  .customaccent b { font-size: 14px; }
  .customaccent small { margin-top: 2px; color: var(--muted); font-size: 12px; }
  #accentPicker { width: 42px; height: 34px; padding: 2px; border: 1px solid var(--line); border-radius: 9px; background: var(--panel); cursor: pointer; }
  #accentPicker::-webkit-color-swatch-wrapper { padding: 0; }
  #accentPicker::-webkit-color-swatch { border: 0; border-radius: 6px; }
  :root[data-theme="dark"] body, :root[data-theme="dark"] body.hubmode { background: radial-gradient(800px 440px at 50% -220px, rgba(255,255,255,.045), transparent 70%), var(--bg); }
  :root[data-theme="dark"] .glist, :root[data-theme="dark"] .hubgrid { background: rgba(25,25,25,.82); border-color: rgba(255,255,255,.12); }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) body, :root:not([data-theme="light"]) body.hubmode { background: radial-gradient(800px 440px at 50% -220px, rgba(255,255,255,.045), transparent 70%), var(--bg); }
    :root:not([data-theme="light"]) .glist, :root:not([data-theme="light"]) .hubgrid { background: rgba(25,25,25,.82); border-color: rgba(255,255,255,.12); }
  }
  @media (max-width: 700px) {
    .settingscard { padding: 21px; }
    .accentgrid { grid-template-columns: repeat(4, 1fr); gap: 7px; }
    .accentchoice { min-height: 66px; font-size: 11px; }
  }

  /* Contrast mode: quiet black surfaces, hard type hierarchy, and a single
     accent used only for active states—the visual rhythm from the reference. */
  :root { --accent: #7950f2; --accent-ink: #fff; }
  :root[data-theme="dark"] {
    --bg: #000; --fg: #f4f4f5; --muted: #929299; --cell: #171718; --cell-fg: #f4f4f5;
    --panel: #0d0d0e; --line: #28282b; --grouped: #000; --row: #0d0d0e; --sep: #27272a; --label2: #a1a1a7;
    --scrim: rgba(0,0,0,.82); --cream: #222225; --silbg: #171718; --link: var(--accent);
    --hit: #16b864; --hit-fg: #061a0d; --near: #dcb539; --near-fg: #231b04;
  }
  :root[data-theme="dark"] body, :root[data-theme="dark"] body.hubmode { background: #000; }
  :root[data-theme="dark"] body::before { display: none; }
  :root[data-theme="dark"] .navbar, :root[data-theme="dark"] body.hubmode .navbar {
    background: #171718; border-bottom-color: #252527; box-shadow: 0 1px #232325;
  }
  :root[data-theme="dark"] .navbar .brand span { padding-bottom: 6px; background-color: transparent; background-image: linear-gradient(90deg, var(--accent), var(--accent), var(--accent)); }
  :root[data-theme="dark"] .navbar .navactions .iconbtn, :root[data-theme="dark"] .navbar .themebtn { background: transparent; border-color: transparent; color: #ededee; }
  :root[data-theme="dark"] .navbar .navactions .iconbtn:hover, :root[data-theme="dark"] .navbar .themebtn:hover { background: #262629; }
  :root[data-theme="dark"] .hubhead, :root[data-theme="dark"] .gamebar {
    background: #0d0d0e; border-color: #29292c; box-shadow: none;
  }
  :root[data-theme="dark"] .hubhead { border-radius: 16px; }
  :root[data-theme="dark"] .hubhead::before, :root[data-theme="dark"] .gamebar::after { display: none; }
  :root[data-theme="dark"] .hubhead::after { background: var(--accent); }
  :root[data-theme="dark"] .hubdate { color: var(--accent); }
  :root[data-theme="dark"] .hubmeter { background: #242427; }
  :root[data-theme="dark"] .hubmeter i { background: var(--accent); box-shadow: none; }
  /* Keep the light appearance genuinely white. The refresh label gets a
     modest weight/contrast lift without changing the rest of the theme. */
  :root[data-theme="light"] body, :root[data-theme="light"] body.hubmode { background: #fff; }
  :root[data-theme="light"] .hubnext { color: rgba(255,255,255,.96); font-weight: 700; text-shadow: 0 1px 2px rgba(0,0,0,.18); }
  :root[data-theme="light"] .hubnext b { color: #fff; font-weight: 800; }
  :root[data-theme="dark"] .partycard { background: #111113; border-color: #2b2b2e; box-shadow: none; }
  :root[data-theme="dark"] .partycard:hover:not(:disabled) { transform: none; background: #18181a; box-shadow: inset 0 0 0 1px var(--accent); }
  :root[data-theme="dark"] .partycta { background: var(--accent); color: var(--accent-ink); box-shadow: none; }
  :root[data-theme="dark"] .hubsec h2 { color: #b1b1b7; }
  :root[data-theme="dark"] .hubsec h2::before { background: var(--accent); box-shadow: none; }
  :root[data-theme="dark"] .glist, :root[data-theme="dark"] .hubgrid { background: #0d0d0e; border-color: #28282b; box-shadow: none; }
  :root[data-theme="dark"] .grow, :root[data-theme="dark"] .gcard { background: #0d0d0e; }
  :root[data-theme="dark"] .grow + .grow::before { border-color: #262629; }
  :root[data-theme="dark"] .grow:hover:not(:disabled), :root[data-theme="dark"] .gcard:hover:not(:disabled) { transform: none; background: #171719; box-shadow: inset 3px 0 var(--accent); }
  :root[data-theme="dark"] .grow::after, :root[data-theme="dark"] .gcard::after { display: none; }
  :root[data-theme="dark"] .grow .gicon, :root[data-theme="dark"] .gcard .gicon { background: #1b1b1e; }
  :root[data-theme="dark"] .grow .gstat, :root[data-theme="dark"] .gcard .gstat { background: #202023; color: #c3c3c8; }
  :root[data-theme="dark"] .gamebar .gticon { background: var(--accent); color: var(--accent-ink); box-shadow: none; }
  :root[data-theme="dark"] .tabs { border: 0; border-radius: 0; background: transparent; box-shadow: none; }
  :root[data-theme="dark"] .tabs button { border-radius: 0; color: #aaaab0; font-weight: 750; }
  :root[data-theme="dark"] .tabs button[aria-selected="true"] { background: transparent; color: var(--accent); box-shadow: inset 0 -3px var(--accent); }
  :root[data-theme="dark"] .btn, :root[data-theme="dark"] .profile { background: var(--accent); color: var(--accent-ink); box-shadow: none; }
  :root[data-theme="dark"] .btn:hover:not(:disabled), :root[data-theme="dark"] .profile:hover { box-shadow: none; filter: brightness(1.1); }
  :root[data-theme="dark"] .search input, :root[data-theme="dark"] .numrow input, :root[data-theme="dark"] .gamesel, :root[data-theme="dark"] .pickstat select, :root[data-theme="dark"] .numrow select {
    background: #171718; border-color: #2c2c30; box-shadow: none;
  }
  :root[data-theme="dark"] .ttcard, :root[data-theme="dark"] .ttq, :root[data-theme="dark"] #view-trophy .optrow, :root[data-theme="dark"] .cups-controls, :root[data-theme="dark"] .cuboard {
    background: #0d0d0e; border-color: #29292c; box-shadow: none;
  }
  :root[data-theme="dark"] .shdot { background: #19191b; border-color: #2b2b2e; box-shadow: none; }
  :root[data-theme="dark"] .shdot.now { background: var(--accent); color: var(--accent-ink); box-shadow: none; }
  :root[data-theme="dark"] .shopt { background: #171718; border-color: #2c2c30; box-shadow: none; }
  :root[data-theme="dark"] .shopt:hover:not(:disabled) { background: #202023; border-color: var(--accent); box-shadow: none; }
  :root[data-theme="dark"] .shopt.right { background: var(--hit); border-color: var(--hit); color: var(--hit-fg); }
  :root[data-theme="dark"] .shopt.wrong { background: #cf4d4d; border-color: #cf4d4d; }
  :root[data-theme="dark"] .cutable td, :root[data-theme="dark"] .seasons td { background: #171718; box-shadow: none; }
  :root[data-theme="dark"] .cutable tr:hover td { background: #202023; }
  :root[data-theme="dark"] .hlcard { background: #171718; border-color: #2c2c30; box-shadow: none; }
  :root[data-theme="dark"] .card { background: #171718; border-color: #303034; box-shadow: 0 24px 70px rgba(0,0,0,.6); }
  :root[data-theme="dark"] .accentchoice, :root[data-theme="dark"] .customaccent { background: #202023; border-color: #303034; }
  :root[data-theme="dark"] .accentchoice[aria-pressed="true"] { border-color: var(--accent); box-shadow: 0 0 0 1px var(--accent); }
  :root[data-theme="dark"] #accentPicker { background: #111113; border-color: #353539; }
  @media (max-width: 700px) {
    :root[data-theme="dark"] .hubhead, :root[data-theme="dark"] .gamebar { border-radius: 12px; }
  }

  /* Navigation and game-heading refinement. */
  .navbar .navactions { gap: 4px; }
  .navbar .navactions .iconbtn, .navbar .themebtn {
    width: 36px; height: 36px; min-width: 36px; padding: 0; display: inline-grid; place-items: center;
    font-size: 16px !important; line-height: 1; text-align: center;
  }
  .navbar .switch {
    gap: 6px; margin: 0 4px; padding: 3px 8px 3px 5px; border: 1px solid rgba(255,255,255,.14); border-radius: 999px;
    background: rgba(255,255,255,.045); color: rgba(255,255,255,.82); font-size: 12px; font-weight: 650; letter-spacing: .01em;
  }
  .navbar .track { width: 28px; height: 16px; background: rgba(255,255,255,.22); }
  .navbar .track::after { top: 2px; left: 2px; width: 12px; height: 12px; }
  .navbar .switch input:checked + .track { background: var(--accent); }
  .navbar .switch input:checked + .track::after { transform: translateX(12px); }
  .gamebar { display: grid; grid-template-columns: minmax(118px, 1fr) auto minmax(118px, 1fr); align-items: center; }
  .gamebar .backbtn { grid-column: 1; justify-self: start; margin: 0; }
  .gamebar .gtitle { grid-column: 2; justify-self: center; padding: 0; margin: 0; }
  .gamebar .gtwords { text-align: center; }
  @media (max-width: 700px) {
    .navbar .navactions .iconbtn, .navbar .themebtn { width: 32px; height: 32px; min-width: 32px; font-size: 15px !important; }
    .navbar .switch { margin: 0 2px; padding: 3px; }
    .gamebar { grid-template-columns: 1fr; gap: 8px; }
    .gamebar .backbtn { grid-column: 1; }
    .gamebar .gtitle { grid-column: 1; }
  }

  /* Playoff History answer tiles use the same oversized, background-logo
     treatment as Trophy Case while preserving the compact table layout. */
  .cucell { position: relative; overflow: hidden; min-height: 54px; }
  .cuanswer { position: relative; display: flex; align-items: center; min-height: 38px; padding: 4px 56px 4px 0; }
  .cuname { position: relative; z-index: 1; }
  .culogo { position: absolute; z-index: 0; right: -6px; top: 50%; width: 74px; height: 74px; transform: translateY(-50%); opacity: .17;
            filter: drop-shadow(0 4px 5px rgba(0,0,0,.14)); pointer-events: none; }
  /* A filled Playoff History square is a fact on the board, not an answer
     button—keep it neutral, mark it with the player's chosen accent, and let
     the actual crest carry the colour. */
  .cucell.got { background: color-mix(in srgb, var(--accent) 6%, var(--cell)); box-shadow: inset 3px 0 0 var(--accent); }
  .cucell.got .culogo { opacity: .31; filter: brightness(1.13) saturate(1.12) drop-shadow(0 4px 6px rgba(0,0,0,.16)); }
  :root[data-theme="dark"] .cucell.got { background: #171718; box-shadow: inset 3px 0 0 var(--accent); }
  :root[data-theme="dark"] .cucell.miss { background: #171718; }
  /* Keep the table's readable row rhythm and column dividers, while extending
     the sticky header just past that row gutter so season text cannot enter it. */
  @media (min-width: 701px) {
    #view-cups .cutable { border-spacing: 0 7px; }
    #view-cups .cutable thead th { z-index: 6; box-shadow: 0 9px 0 var(--panel); }
    #view-cups .cutable thead th:not(:last-child), #view-cups .cutable tbody td:not(:last-child) {
      border-right: 1px solid var(--line); background-clip: padding-box;
    }
    #view-cups .cutable tbody td { border-bottom: 0; }
  }
  /* Keep the light-mode Playoff History controls looking exactly as before,
     but make their near-white surface solid instead of 90% transparent. */
  :root[data-theme="light"] #view-cups .cups-controls { background: #fefeff; }
  @media (prefers-color-scheme: light) {
    :root:not([data-theme="dark"]) #view-cups .cups-controls { background: #fefeff; }
  }
  @media (max-width: 700px) {
    .cucell { min-height: 48px; }
    .cuanswer { min-height: 34px; padding-right: 46px; }
    .culogo { width: 62px; height: 62px; }
  }

  /* Blue-heavy crests (especially Toronto and Tampa Bay) are darker by
     design, so raise them just enough to match the visual weight of the
     warmer-coloured marks on dark tiles. */
  .trlogo.logo-blue { opacity: .31; filter: brightness(1.6) saturate(1.28) drop-shadow(0 5px 6px rgba(82, 140, 255, .18)); }
  .shopt:hover:not(:disabled) .trlogo.logo-blue { opacity: .42; }
  .culogo.logo-blue { opacity: .31; filter: brightness(1.6) saturate(1.28) drop-shadow(0 4px 6px rgba(82, 140, 255, .18)); }
  .cucell.got .culogo.logo-blue { opacity: .38; filter: brightness(1.68) saturate(1.32) drop-shadow(0 4px 6px rgba(82, 140, 255, .2)); }
  .shopt.right .trlogo.logo-blue { opacity: .48; filter: brightness(1.72) saturate(1.35) drop-shadow(0 5px 7px rgba(82, 140, 255, .22)); }
  .shopt.wrong .trlogo.logo-blue { opacity: .37; filter: brightness(1.62) saturate(1.32) drop-shadow(0 5px 7px rgba(82, 140, 255, .2)); }

  /* Sweater progression: the home screen is now a game lobby first, library second. */
  .hubfeatures { display: grid; grid-template-columns: 1.35fr 1fr; gap: 12px; margin: 0 0 18px; }
  .hubfeature { position: relative; overflow: hidden; min-height: 152px; padding: 18px; border: 1px solid var(--line); border-radius: 18px;
                background: color-mix(in srgb, var(--panel) 92%, transparent); color: var(--fg); font: inherit; text-align: left; cursor: pointer;
                box-shadow: 0 10px 26px rgba(0,0,0,.07); transition: transform .2s ease, border-color .2s ease, box-shadow .2s ease; }
  .hubfeature:hover { transform: translateY(-3px); border-color: var(--accent); box-shadow: 0 16px 32px color-mix(in srgb, var(--accent) 16%, transparent); }
  .hubfeature.primary { background: linear-gradient(135deg, color-mix(in srgb, var(--accent) 21%, var(--panel)), color-mix(in srgb, var(--panel) 96%, transparent) 72%); }
  .hubfeature.primary::after { content: ""; position: absolute; width: 170px; height: 170px; right: -56px; top: -72px; border-radius: 50%;
                               border: 22px solid color-mix(in srgb, var(--accent) 15%, transparent); box-shadow: 0 0 0 26px color-mix(in srgb, var(--accent) 6%, transparent); pointer-events: none; }
  .featureeyebrow, .libraryhead p { margin: 0 0 6px; color: var(--accent); font-size: 11px; font-weight: 800; letter-spacing: .105em; text-transform: uppercase; }
  .featuretitle { position: relative; z-index: 1; display: flex; align-items: center; gap: 9px; margin: 0; font-size: 22px; font-weight: 760; letter-spacing: -.035em; }
  .featureicon { width: 33px; height: 33px; display: grid; place-items: center; border-radius: 10px; font-size: 18px; background: color-mix(in srgb, var(--accent) 15%, transparent); }
  .featurecopy { position: relative; z-index: 1; max-width: 340px; margin: 7px 0 16px; color: var(--muted); font-size: 13px; line-height: 1.4; }
  .featurefooter { position: relative; z-index: 1; display: flex; justify-content: space-between; align-items: center; gap: 10px; color: var(--accent); font-size: 13px; font-weight: 750; }
  .featurefooter b { font-variant-numeric: tabular-nums; color: var(--fg); }
  .queststack { display: grid; grid-template-rows: 1fr 1fr; gap: 12px; }
  .hubfeature.quest { min-height: 70px; padding: 13px 15px; box-shadow: none; }
  .hubfeature.quest .featuretitle { font-size: 16px; }
  .hubfeature.quest .featurecopy { margin: 3px 0 0; font-size: 12px; }
  .questprogress { position: absolute; right: 13px; top: 13px; min-width: 34px; text-align: center; padding: 5px 7px; border-radius: 999px;
                   background: color-mix(in srgb, var(--accent) 14%, transparent); color: var(--accent); font-size: 12px; font-weight: 800; font-variant-numeric: tabular-nums; }
  .libraryhead { display: flex; align-items: end; justify-content: space-between; gap: 12px; margin: 26px 4px 16px; }
  .libraryhead h2 { margin: 0; font-size: 25px; letter-spacing: -.035em; }
  .librarytoggle { display: inline-flex; align-items: center; gap: 7px; border: 1px solid var(--line); border-radius: 999px; padding: 9px 13px; background: var(--panel); color: var(--fg); font: inherit; font-size: 13px; font-weight: 700; cursor: pointer; }
  .librarytoggle span { font-size: 19px; line-height: .7; transition: transform .2s ease; }
  .librarytoggle[aria-expanded="true"] span { transform: rotate(90deg); }
  .libraryfilters { display: flex; gap: 7px; overflow-x: auto; margin: -8px 4px 14px; padding: 2px 0 4px; scrollbar-width: none; }
  .libraryfilters::-webkit-scrollbar { display: none; }
  .libraryfilter { flex: none; border: 1px solid var(--line); border-radius: 999px; padding: 7px 11px; background: transparent; color: var(--muted); font: inherit; font-size: 12px; font-weight: 700; cursor: pointer; }
  .libraryfilter[aria-pressed="true"] { border-color: var(--accent); background: color-mix(in srgb, var(--accent) 12%, transparent); color: var(--accent); }
  .hubshelf { margin: 0 0 18px; padding: 14px; border: 1px solid var(--line); border-radius: 17px; background: color-mix(in srgb, var(--panel) 92%, transparent); box-shadow: 0 10px 28px rgba(22, 54, 70, .045); }
  .shelfhead { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; margin: 0 2px 10px; }
  .shelfhead b { font-size: 14px; letter-spacing: -.01em; }
  .shelfhead span { color: var(--muted); font-size: 11px; font-weight: 700; letter-spacing: .07em; text-transform: uppercase; }
  .shelfscroll { display: grid; grid-auto-flow: column; grid-auto-columns: minmax(164px, 1fr); grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; overflow-x: auto; padding-bottom: 2px; scrollbar-width: none; }
  .shelfscroll::-webkit-scrollbar { display: none; }
  .shelfcard { min-width: 0; min-height: 93px; padding: 11px; border: 1px solid var(--line); border-radius: 13px; background: var(--cell); color: var(--cell-fg); font: inherit; text-align: left; cursor: pointer; transition: transform .18s ease, border-color .18s ease; }
  .shelfcard:hover { transform: translateY(-2px); border-color: var(--accent); }
  .shelfcard b, .shelfcard small { display: block; }
  .shelfcard b { margin-top: 6px; font-size: 14px; letter-spacing: -.015em; }
  .shelfcard small { margin-top: 3px; color: var(--muted); font-size: 11px; line-height: 1.3; }
  .shelfcard .shelficon { display: inline-grid; width: 26px; height: 26px; place-items: center; border-radius: 8px; background: color-mix(in srgb, var(--accent) 14%, transparent); font-size: 15px; }
  .modebadges { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 5px; }
  .modebadge { display: inline-flex; align-items: center; min-height: 17px; padding: 2px 5px; border-radius: 999px; background: color-mix(in srgb, var(--fg) 7%, transparent); color: var(--muted); font-size: 9px; font-weight: 800; letter-spacing: .055em; line-height: 1; text-transform: uppercase; }
  .modebadge.difficulty-hard { background: color-mix(in srgb, var(--near) 20%, transparent); color: color-mix(in srgb, var(--near) 74%, var(--fg)); }
  .modebadge.difficulty-expert { background: color-mix(in srgb, var(--accent) 16%, transparent); color: var(--accent); }
  .librarygame { position: relative; display: grid; grid-template-columns: minmax(0, 1fr) 40px; }
  .librarygame + .librarygame::before { content: ""; position: absolute; top: 0; left: 66px; right: 0; border-top: 1px solid var(--sep); }
  .librarygame .grow { grid-column: 1; min-width: 0; }
  .favtoggle { grid-column: 2; z-index: 1; align-self: stretch; width: 40px; border: 0; background: transparent; color: var(--muted); font: inherit; font-size: 18px; cursor: pointer; }
  .favtoggle:hover, .favtoggle[aria-pressed="true"] { color: var(--accent); }
  .favtoggle[aria-pressed="true"] { text-shadow: 0 2px 9px color-mix(in srgb, var(--accent) 30%, transparent); }
  .resultrecap { width: min(450px, 100%); margin: 15px auto 11px; padding: 11px 12px; display: flex; align-items: center; justify-content: space-between; gap: 12px;
                 border: 1px solid color-mix(in srgb, var(--accent) 20%, var(--line)); border-radius: 13px; background: color-mix(in srgb, var(--accent) 7%, var(--panel)); text-align: left; }
  .recapstats { display: flex; align-items: center; gap: 12px; min-width: 0; }
  .recapstats i { width: 30px; height: 30px; display: grid; place-items: center; flex: none; border-radius: 9px; background: color-mix(in srgb, var(--accent) 16%, transparent); font-style: normal; }
  .recapstats b, .recapstats small { display: block; }
  .recapstats b { font-size: 13px; letter-spacing: -.01em; }
  .recapstats small { margin-top: 1px; color: var(--muted); font-size: 11px; }
  .recapactions { display: flex; gap: 5px; }
  .recapactions button { border: 0; border-radius: 9px; padding: 7px 9px; background: var(--fg); color: var(--bg); font: inherit; font-size: 12px; font-weight: 700; cursor: pointer; }
  .recapactions button.ghost { background: transparent; color: var(--fg); box-shadow: inset 0 0 0 1px var(--line); }
  .appearancechoice { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; margin: 16px 0 14px; }
  .appearancechoice button { display: flex; align-items: center; justify-content: center; gap: 7px; min-height: 42px; border: 1px solid var(--line); border-radius: 11px; background: var(--cell); color: var(--cell-fg); font: inherit; font-size: 13px; font-weight: 700; cursor: pointer; }
  .appearancechoice button[aria-pressed="true"] { border-color: var(--accent); box-shadow: inset 0 0 0 1px var(--accent); }
  .appearancechoice span { color: var(--accent); font-size: 15px; }
  .lockercard h3 { margin: 22px 0 10px; }
  .lockerhero { display: grid; grid-template-columns: auto 1fr; align-items: center; gap: 14px; padding: 14px; border: 1px solid var(--line); border-radius: 15px; background: color-mix(in srgb, var(--accent) 7%, var(--panel)); }
  .levelmark { width: 64px; aspect-ratio: 1; display: grid; place-items: center; border-radius: 18px; background: var(--accent); color: var(--accent-ink); font-size: 19px; font-weight: 850; box-shadow: 0 8px 20px color-mix(in srgb, var(--accent) 25%, transparent); }
  .levelcopy b, .levelcopy small { display: block; }
  .levelcopy b { font-size: 17px; letter-spacing: -.025em; }
  .levelcopy small { color: var(--muted); font-size: 12px; margin-top: 2px; }
  .xpbar { height: 7px; margin-top: 9px; overflow: hidden; border-radius: 99px; background: color-mix(in srgb, var(--fg) 9%, transparent); }
  .xpbar i { display: block; height: 100%; border-radius: inherit; background: var(--accent); }
  .lockerstats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1px; margin-top: 12px; border: 1px solid var(--line); border-radius: 13px; overflow: hidden; background: var(--line); }
  .lockerstats div { padding: 10px 5px; background: var(--panel); text-align: center; }
  .lockerstats b, .lockerstats span { display: block; }
  .lockerstats b { font-size: 17px; font-variant-numeric: tabular-nums; }
  .lockerstats span { margin-top: 2px; color: var(--muted); font-size: 10px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; }
  .achievementgrid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; }
  .achievement { min-height: 70px; padding: 10px; display: grid; grid-template-columns: 28px 1fr; gap: 9px; align-items: center; border: 1px solid var(--line); border-radius: 12px; background: var(--panel); }
  .achievement.locked { opacity: .45; filter: grayscale(1); }
  .achievement i { width: 28px; height: 28px; display: grid; place-items: center; border-radius: 9px; background: color-mix(in srgb, var(--accent) 14%, transparent); font-style: normal; font-size: 15px; }
  .achievement b, .achievement small { display: block; }
  .achievement b { font-size: 12px; }
  .achievement small, .lockerhint { color: var(--muted); font-size: 11px; line-height: 1.35; }
  .lockerhint { margin: 0; }
  .lockerbench { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
  .lockerbenchsection { min-width: 0; }
  .lockerbenchsection > b { display: block; margin: 0 0 6px; color: var(--muted); font-size: 10px; letter-spacing: .075em; text-transform: uppercase; }
  .lockerlist { display: grid; gap: 6px; }
  .lockerrow { display: grid; grid-template-columns: 27px minmax(0, 1fr) 12px; align-items: center; gap: 7px; width: 100%; min-height: 43px; padding: 7px 8px; border: 1px solid var(--line); border-radius: 11px; background: var(--panel); color: var(--fg); font: inherit; text-align: left; cursor: pointer; }
  .lockerrow:hover { border-color: var(--accent); }
  .lockerrow i { width: 27px; height: 27px; display: grid; place-items: center; border-radius: 8px; background: color-mix(in srgb, var(--accent) 13%, transparent); font-style: normal; font-size: 14px; }
  .lockerrow span { min-width: 0; }
  .lockerrow b, .lockerrow small { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .lockerrow b { font-size: 12px; }
  .lockerrow small { margin-top: 1px; color: var(--muted); font-size: 10px; }
  .lockerrow em { color: var(--muted); font-size: 17px; font-style: normal; }
  .recapfact { margin-top: 3px; }
  .recapfact small { display: block; max-width: 280px; color: var(--muted); font-size: 10px; line-height: 1.3; }
  .welcomecard { width: min(430px, 92vw); text-align: center; }
  .welcomecard h2 { margin: 4px 0 8px; font-size: 29px; letter-spacing: -.045em; line-height: 1.05; }
  .welcomecard .settingsintro { margin: 0 auto; max-width: 350px; }
  .welcomeactions { display: grid; gap: 8px; margin-top: 20px; }
  .welcomeactions .btn { width: 100%; margin: 0; }
  .welcomeskip { margin-top: 12px; color: var(--muted); }
  .cudecades { display: grid; grid-template-columns: repeat(5, 1fr); gap: 7px; max-width: 980px; margin: 12px auto 4px; }
  .cudecade { min-width: 0; padding: 8px 9px; border: 1px solid var(--line); border-radius: 10px; background: color-mix(in srgb, var(--panel) 86%, transparent); }
  .cudecade b, .cudecade small { display: block; }
  .cudecade b { font-size: 11px; letter-spacing: .03em; }
  .cudecade small { margin-top: 3px; color: var(--muted); font-size: 10px; font-variant-numeric: tabular-nums; }
  .cudecade i { display: block; height: 4px; margin-top: 6px; overflow: hidden; border-radius: 99px; background: color-mix(in srgb, var(--fg) 10%, transparent); }
  .cudecade i span { display: block; height: 100%; border-radius: inherit; background: var(--accent); transition: width .35s ease; }
  :root[data-theme="dark"] .hubfeature, :root[data-theme="dark"] .lockerhero, :root[data-theme="dark"] .resultrecap { background: #171718; }
  :root[data-theme="dark"] .hubfeature.primary { background: linear-gradient(135deg, color-mix(in srgb, var(--accent) 21%, #171718), #171718 76%); }
  :root[data-theme="dark"] .librarytoggle, :root[data-theme="dark"] .achievement, :root[data-theme="dark"] .lockerstats div { background: #171718; }
  @media (max-width: 700px) {
    .hubfeatures { grid-template-columns: 1fr; }
    .queststack { grid-template-columns: 1fr 1fr; grid-template-rows: none; }
    .hubfeature { min-height: 138px; }
    .hubfeature.quest { min-height: 94px; }
    .libraryhead { align-items: center; margin-top: 22px; }
    .libraryhead h2 { font-size: 22px; }
    .librarytoggle { padding: 8px 10px; font-size: 12px; }
    .shelfscroll { grid-auto-columns: minmax(152px, 72%); grid-template-columns: none; }
    .modebadges { display: none; }
    .lockerbench { grid-template-columns: 1fr; }
    .achievementgrid { grid-template-columns: 1fr; }
    .cudecades { grid-template-columns: repeat(3, 1fr); }

    /* Shared mobile guardrails: controls should wrap instead of colliding. */
    .optrow { flex-wrap: wrap; align-items: stretch; }
    .optrow .pickstat { flex: 1 1 138px; justify-content: space-between; min-width: 0; }
    .optrow .pickstat select { flex: 1; min-width: 0; max-width: 100%; }
    .tabs { max-width: 100%; overflow-x: auto; scrollbar-width: none; white-space: nowrap; }
    .tabs::-webkit-scrollbar { display: none; }
    .numrow.wide { width: 100%; max-width: 100%; }

    /* Playoff History becomes a readable set of season cards on phones. */
    #view-cups .cups-controls { padding: 14px 13px; }
    #view-cups .cuboard { overflow: visible; padding: 0; border: 0; background: none; box-shadow: none; }
    #view-cups .cutable { display: block; width: 100%; min-width: 0 !important; table-layout: auto; border-spacing: 0; }
    #view-cups .cutable thead { display: none; }
    #view-cups .cutable tbody { display: block; }
    #view-cups .cutable tr { display: grid; grid-template-columns: 76px minmax(0, 1fr); margin: 0 0 9px; overflow: hidden;
                             border: 1px solid var(--line); border-radius: 13px; background: color-mix(in srgb, var(--panel) 88%, transparent); }
    #view-cups .cutable td { display: flex; align-items: center; width: auto !important; min-width: 0 !important; height: auto; min-height: 48px;
                             padding: 7px 10px; border: 0; border-radius: 0; background: transparent; box-shadow: none; font-size: 12px; }
    #view-cups .cutable td.cuyear { grid-row: 1 / span 3; justify-content: center; align-self: stretch; padding: 8px; background: color-mix(in srgb, var(--accent) 10%, var(--cell));
                                    color: var(--fg); font-size: 12px; line-height: 1.2; text-align: center; white-space: nowrap; }
    #view-cups .cutable td.cucell { position: relative; gap: 8px; border-top: 1px solid var(--line); }
    #view-cups .cutable td.cucell:nth-child(2) { border-top: 0; }
    #view-cups .cutable td.cucell::before { content: attr(data-label); width: 72px; flex: none; color: var(--muted); font-size: 10px; font-weight: 800; letter-spacing: .045em; line-height: 1.15; text-transform: uppercase; }
    #view-cups .cutable td.cucell:not(.got):not(.miss)::after { content: "—"; color: var(--muted); font-size: 16px; }
    #view-cups .cutable .cuanswer { flex: 1; min-width: 0; min-height: 32px; padding: 0 42px 0 0; }
    #view-cups .cutable .culogo { right: -3px; width: 52px; height: 52px; opacity: .24; }
    #view-cups .cutable td.cucell.got { box-shadow: inset 3px 0 0 var(--accent); }
    #view-cups .cutable .cucell.got .culogo { opacity: .34; }
    #view-cups .cutable .cucell.got .culogo.logo-blue { opacity: .42; }
    #view-cups .cutable .cuname { overflow-wrap: anywhere; }
  }
  @media (max-width: 420px) {
    .cngrid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    #view-trophy .optrow .pickstat { flex-basis: 100%; }
  }
  @media (prefers-reduced-motion: reduce) {
    .hubfeature, .librarytoggle span { transition: none; }
    .hubfeature:hover { transform: none; }
  }
  /* Visual polish: shared icons, lighter section framing, and a focused ballot. */
  .ui-icon { display: block; width: 22px; height: 22px; flex: none; pointer-events: none; }
  .navbar .iconbtn .ui-icon { width: 20px; height: 20px; }
  .navbar .iconbtn:focus-visible, .favtoggle:focus-visible, .shelfcard:focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; }
  .gticon .ui-icon { width: 27px; height: 27px; }
  .favtoggle { display: grid; place-items: center; }
  .favtoggle .ui-icon { width: 18px; height: 18px; }
  .favtoggle[aria-pressed="true"] .ui-icon { fill: currentColor; }
  #view-hub { max-width: 960px; }
  #view-hub .hubhead { padding: 0 0 20px; margin-bottom: 20px; border: 0; border-bottom: 1px solid var(--line); border-radius: 0; background: transparent; box-shadow: none; }
  #view-hub .hubhead::before, #view-hub .hubhead::after { display: none; }
  #view-hub .hubtitle { margin: 6px 0 14px; font-size: 28px; color: var(--fg); }
  #view-hub .hubdate { color: var(--muted); font-size: 12px; }
  #view-hub .hubprogress, #view-hub .hubnext { color: var(--muted); font-size: 13px; font-weight: 500; text-shadow: none; }
  #view-hub .hubnext b { color: var(--fg); }
  #view-hub .hubmeter { height: 3px; background: var(--line); }
  #view-hub .hubmeter i { background: var(--accent); box-shadow: none; }
  #view-hub .hubfeatures { grid-template-columns: 1.5fr 1fr; gap: 28px; margin-bottom: 26px; }
  #view-hub .hubfeature.primary { padding: 26px; min-height: 208px; border-radius: 18px; box-shadow: none; }
  #view-hub .hubfeature.primary .featuretitle { margin-top: 12px; font-size: 32px; line-height: 1.12; }
  #view-hub .featurecopy { font-size: 14px; line-height: 1.5; }
  #view-hub .featureicon { background: transparent; width: 30px; height: 34px; color: var(--accent); }
  #view-hub .featureicon .ui-icon { width: 28px; height: 28px; }
  #view-hub .hubfeature.primary::after { opacity: .5; }
  #view-hub .queststack { gap: 0; }
  #view-hub .hubfeature.quest { padding: 18px 46px 18px 0; border: 0; border-radius: 0; background: transparent; box-shadow: none; transform: none; }
  #view-hub .hubfeature.quest + .hubfeature.quest { border-top: 1px solid var(--line); }
  #view-hub .hubfeature.quest:hover .featuretitle { color: var(--accent); }
  #view-hub .hubfeature.quest .featureeyebrow { color: var(--muted); font-size: 11px; }
  #view-hub .hubfeature.quest .featurecopy { font-size: 13px; }
  #view-hub .questprogress { top: 20px; right: 0; background: transparent; color: var(--muted); }
  #view-hub .hubshelf { padding: 0; border: 0; border-radius: 0; background: transparent; box-shadow: none; margin-bottom: 24px; }
  #view-hub .shelfhead span { display: none; }
  #view-hub .shelfscroll { grid-template-columns: none; grid-auto-columns: minmax(180px, calc((100% - 16px) / 3)); }
  #view-hub .shelfcard { display: flex; align-items: center; gap: 10px; min-height: 64px; padding: 12px 14px; background: var(--panel); border-radius: 12px; }
  #view-hub .shelfcard b { margin: 0; font-size: 14px; }
  #view-hub .shelficon { background: transparent; color: var(--muted); }
  #view-hub .partycard { min-height: 84px; padding: 16px 20px; margin-bottom: 24px; border-radius: 14px; align-items: center; box-shadow: none; }
  #view-hub .partycard .rink { opacity: .12; }
  #view-hub .partytext b { font-size: 18px; }
  #view-hub .partytext span { font-size: 13px; max-width: none; }
  #view-hub .partycta { font-size: 13px; }
  #view-hub .libraryhead { margin-top: 12px; }
  #view-hub .libraryhead > div > p { display: none; }
  #view-hub .libraryfilters { margin-top: 0; margin-bottom: 24px; }
  #view-hub .hubsec { margin-bottom: 28px; }
  #view-hub .hubsec h2 { font-size: 12px; margin-bottom: 8px; }
  #view-hub .glist { border: 0; border-radius: 0; background: transparent; box-shadow: none; }
  #view-hub .librarygame { border-bottom: 1px solid var(--line); }
  #view-hub .librarygame::before, #view-hub .grow::before { display: none; }
  #view-hub .grow { padding: 14px 8px; min-height: 78px; border-radius: 10px; background: transparent; box-shadow: none; }
  #view-hub .grow:hover { background: color-mix(in srgb, var(--accent) 5%, var(--panel)); transform: none; }
  #view-hub .grow .gicon { background: transparent; box-shadow: none; color: var(--muted); }
  #view-hub .grow .gtext small { font-size: 14px; line-height: 1.45; }
  #view-hub .grow .gstat { background: transparent; font-size: 12px; }
  #view-hub .modebadges { display: none; }
  .gamebar[data-game="trophy"] { max-width: 760px; margin: 18px auto 24px; padding: 0 0 20px; border: 0; border-bottom: 1px solid var(--line); border-radius: 0; background: transparent; box-shadow: none; }
  .gamebar[data-game="trophy"] .gtitle h2 { color: var(--fg); font-size: 26px; }
  .gamebar[data-game="trophy"] .backbtn { color: var(--muted); }
  .gamebar[data-game="trophy"] #modeLabel { color: var(--muted); }
  .gamebar[data-game="trophy"] .gticon { background: transparent; color: var(--accent); box-shadow: none; }
  #view-trophy { max-width: 760px; }
  #view-trophy .optrow { width: 100%; max-width: none; margin: 0 0 22px; padding: 0; border: 0; border-radius: 0; background: transparent; box-shadow: none; display: flex; justify-content: space-between; gap: 16px; }
  #view-trophy .pickstat { font-size: 13px; gap: 10px; }
  #view-trophy .pickstat select { min-height: 42px; background: var(--panel); color: var(--fg); box-shadow: none; }
  #view-trophy #trDots { margin: 0 auto 20px; flex-wrap: wrap; gap: 6px; }
  #view-trophy #trDots .shdot { width: 27px; height: 27px; font-size: 12px; box-shadow: none; }
  #view-trophy #trQ { width: 100%; max-width: none; margin: 0 0 26px; padding: 16px 10px; border: 0; border-radius: 0; background: transparent; box-shadow: none; text-align: center; }
  .trophy-prompt { display: block; font-size: 14px; font-weight: 500; color: var(--muted); }
  .trophy-title { display: block; margin: 8px auto 10px; font-size: clamp(26px, 3vw, 34px); font-weight: 750; line-height: 1.15; letter-spacing: -.035em; text-wrap: balance; }
  .trophy-season { display: block; font-size: 20px; font-weight: 600; font-variant-numeric: tabular-nums; color: var(--muted); }
  #view-trophy #trOpts { width: 100%; max-width: none; gap: 12px; }
  #view-trophy .shopt { min-height: 104px; padding: 22px 16px 22px 46px; border-radius: 14px; }
  #view-trophy .trname { padding-right: 62px; font-size: 16px; line-height: 1.35; }
  #view-trophy .trlogo { width: 110px; height: 110px; right: -4px; opacity: var(--crest-opacity, .32); filter: brightness(var(--crest-brightness, 1.15)) saturate(1.08); }
  #view-trophy .trlogo[data-team="FLA"] { --crest-opacity: .46; --crest-brightness: 1.4; }
  #view-trophy .trlogo[data-team="DET"] { --crest-opacity: .42; --crest-brightness: 1.35; }
  #view-trophy .trlogo[data-team="CGY"] { --crest-opacity: .38; --crest-brightness: 1.2; }
  #view-trophy .trlogo[data-team="COL"] { --crest-opacity: .32; --crest-brightness: 1.1; }
  #view-trophy .trlogo.logo-blue { --crest-opacity: .42; --crest-brightness: 1.65; }
  #view-trophy .shopt:hover:not(:disabled) .trlogo { opacity: calc(var(--crest-opacity, .32) + .08); }
  #view-trophy .shopt.right .trlogo { opacity: .48; filter: brightness(1.15) saturate(1.1); }
  #view-trophy .shopt.wrong .trlogo { opacity: .38; filter: brightness(1.1) saturate(1.1); }
  :root[data-theme="light"] #view-trophy .trlogo { filter: saturate(1.05); }
  #view-trophy #trNext { min-height: 44px; margin-top: 8px; }
  :root[data-theme] .gamebar[data-game="trophy"],
  :root[data-theme] #view-trophy .optrow { background: transparent; box-shadow: none; border-radius: 0; }
  :root[data-theme] .gamebar[data-game="trophy"] .gticon { background: transparent; color: var(--accent); box-shadow: none; }
  @media (max-width: 700px) {
    .navbar { flex-wrap: wrap; row-gap: 8px; }
    .navbar .navactions { margin-left: auto; }
    #view-hub .hubfeatures { grid-template-columns: 1fr; gap: 8px; margin-bottom: 20px; }
    #view-hub .hubfeature.primary { min-height: 190px; padding: 22px; }
    #view-hub .hubfeature.primary .featuretitle { font-size: 30px; }
    #view-hub .queststack { grid-template-columns: 1fr 1fr; gap: 16px; }
    #view-hub .hubfeature.quest { padding: 14px 0; min-height: 110px; }
    #view-hub .hubfeature.quest + .hubfeature.quest { border-top: 0; }
    #view-hub .questprogress { position: static; float: right; padding: 0; min-width: 0; font-size: 11px; }
    #view-hub .hubfeature.quest .featureeyebrow { font-size: 10px; letter-spacing: .055em; }
    #view-hub .hubfeature.quest .featuretitle { font-size: 15px; }
    #view-hub .shelfscroll { grid-auto-columns: minmax(160px, 65%); }
    #view-hub .partycard { grid-template-columns: 1fr auto; gap: 10px; padding: 16px; }
    #view-hub .partycta { padding: 8px 10px; }
    #view-hub .grow { grid-template-columns: 30px minmax(0, 1fr) 12px; gap: 10px; }
    #view-hub .grow .gicon { width: 30px; }
    #view-hub .grow .gstat { display: none; }
    #view-hub .grow .gtext small { font-size: 13px; }
    .gamebar[data-game="trophy"] { margin: 8px auto 20px; padding-bottom: 16px; }
    #view-trophy .optrow { gap: 12px; }
    #view-trophy .optrow .pickstat { flex: 1 1 100%; }
    #view-trophy #trQ { padding: 6px 0; margin-bottom: 22px; }
    #view-trophy #trOpts { grid-template-columns: 1fr; gap: 10px; }
    #view-trophy .shopt { min-height: 88px; }
    #view-trophy .trlogo { width: 100px; height: 100px; }
  }
  @media (prefers-reduced-motion: reduce) {
    .shelfcard { transition: none; }
    .shelfcard:hover { transform: none; }
  }
  /* New arcade modes: scoped surfaces keep both existing themes unchanged. */
  #view-goalie, #view-overtime { max-width: 760px; margin-inline: auto; }
  .arc-hud { display: grid; grid-template-columns: repeat(3,1fr); gap: 10px; margin: 20px 0 16px; }
  .arc-hud > div { padding: 14px 8px; border: 1px solid var(--line); border-radius: 14px; background: var(--bg); text-align: center; }
  .arc-hud small { display: block; color: var(--muted); font-size: 11px; letter-spacing: .08em; text-transform: uppercase; }
  .arc-hud strong { display: block; font-size: clamp(24px,5vw,34px); font-variant-numeric: tabular-nums; line-height: 1.3; }
  .arc-controls { display: flex; justify-content: center; gap: 12px; margin: 18px 0 12px; }
  .arc-controls button { min-height: 46px; }
  .arc-note { text-align: center; color: var(--muted); font-size: 13px; line-height: 1.6; margin: 12px auto; max-width: 580px; }
  .goalie-rink { position: relative; aspect-ratio: 1.6; overflow: clip; border: 1px solid var(--line); border-radius: 20px; isolation: isolate;
    background: radial-gradient(ellipse at 50% 5%,color-mix(in srgb,var(--fg) 7%,transparent),transparent 65%),var(--bg); touch-action: pan-y; }
  .goalie-net { position: absolute; inset: 27% 6% 6%; border: 4px solid #ce404b; border-radius: 26px 26px 8px 8px;
    background: repeating-linear-gradient(0deg,transparent 0 23px,var(--line) 23px 24px), repeating-linear-gradient(90deg,transparent 0 23px,var(--line) 23px 24px); opacity: .65; }
  .goalie-crease { position: absolute; width: 65%; height: 45%; border: 1px solid var(--line); border-radius: 50%; left: 17.5%; bottom: -26%; background: var(--cell); }
  .goalie-zone { position: absolute; width: 29%; height: 27%; transform: translate(-50%,-50%); border: 1px solid transparent; border-radius: 16px;
    background: transparent; color: var(--muted); cursor: pointer; font: inherit; font-size: 12px; z-index: 2; touch-action: manipulation; }
  .goalie-zone:nth-of-type(1) { left: 21%; top: 43%; } .goalie-zone:nth-of-type(2) { left: 79%; top: 43%; }
  .goalie-zone:nth-of-type(3) { left: 21%; top: 78%; } .goalie-zone:nth-of-type(4) { left: 79%; top: 78%; }
  .goalie-zone:nth-of-type(5) { left: 50%; top: 78%; }
  .goalie-zone:focus-visible { outline: 3px solid var(--fg); outline-offset: -3px; }
  .goalie-zone.chosen { background: color-mix(in srgb,var(--fg) 12%,transparent); border-color: var(--fg); color: var(--fg); }
  .goalie-zone.saved { background: rgba(34,197,94,.2); border-color: #22c55e; }
  .goalie-zone.conceded { background: rgba(239,68,68,.2); border-color: #ef4444; }
  .goalie-zone kbd { display: block; font: inherit; font-size: 10px; margin-top: 3px; opacity: .6; }
  .goalie-puck { position: absolute; left: 50%; top: 10%; width: 25px; height: 25px; border-radius: 50%; background: #151515; border: 2px solid #f4f4f5;
    box-shadow: 0 5px 12px #0006; transform: translate(-50%,-50%); z-index: 3; pointer-events: none; }
  .goalie-glove { position: absolute; width: 62px; height: 62px; left: 50%; top: 91%; transform: translate(-50%,-50%); color: var(--fg); z-index: 4; pointer-events: none;
    filter: drop-shadow(0 4px 5px #0004); transition: left .13s ease-out,top .13s ease-out; }
  .goalie-zone.chosen span,.goalie-zone.chosen kbd { visibility: hidden; }
  .goalie-status { position: absolute; top: 7%; left: 0; width: 100%; text-align: center; color: var(--fg); font-weight: 700; font-size: clamp(15px,3vw,22px); pointer-events: none; }
  .goalie-rink.live .goalie-status { top: 2%; font-size: 12px; color: var(--muted); }
  .goalie-rink.live .goalie-zone span, .goalie-rink.live .goalie-zone kbd { opacity: .45; }
  .ot-time.urgent { color: #ef4444; }
  .ot-meter { height: 4px; border-radius: 4px; background: var(--line); overflow: hidden; margin: -6px 0 24px; }
  .ot-meter i { display: block; width: 50%; height: 100%; background: var(--fg); }
  .ot-question { text-align: center; min-height: 110px; display: grid; align-content: center; gap: 10px; margin: 18px 0; }
  .ot-question small { color: var(--muted); font-size: 11px; letter-spacing: .1em; text-transform: uppercase; }
  .ot-question h3 { margin: 0; font-size: clamp(22px,4vw,30px); line-height: 1.25; }
  .ot-answers { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .ot-answer { min-height: 82px; border: 1px solid var(--line); border-radius: 14px; background: var(--bg); color: var(--fg); padding: 16px;
    font: inherit; font-weight: 600; font-size: 16px; cursor: pointer; text-align: left; transition: border-color .15s,background .15s; }
  .ot-answer:not(:disabled):hover { border-color: var(--fg); }
  .ot-answer.right { background: rgba(34,197,94,.16); border-color: #22c55e; }
  .ot-answer.wrong { background: rgba(239,68,68,.16); border-color: #ef4444; }
  .ot-answer:disabled { cursor: default; opacity: 1; }
  .ot-question.next-round { animation: overtime-in .18s ease-out; }
  @keyframes overtime-in { from { opacity: .3; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }
  @media(max-width:600px) { .arc-hud { gap: 6px; } .goalie-rink { aspect-ratio: 1.12; } .goalie-zone { width: 29%; height: 28%; font-size: 11px; }
    .goalie-zone kbd { display: none; } .ot-answers { gap: 8px; } .ot-answer { padding: 12px; min-height: 86px; font-size: 14px; overflow-wrap: anywhere; } }
  @media(prefers-reduced-motion:reduce) { .ot-question.next-round { animation: none; } .ot-answer,.goalie-glove { transition: none; } }
</style>
</head>
<body class="hubmode">
<nav class="navbar">
  <a href="./" id="homeLink" class="brand" title="All games"><span>SWEATER</span></a>
  <div class="navactions">
    <button class="iconbtn round" id="statsBtn" type="button" aria-label="Statistics" title="Statistics">📊</button>
    <button class="iconbtn round" id="lbBtn" type="button" aria-label="Leaderboard" title="Leaderboard" hidden>🏆</button>
    <button class="iconbtn round" id="archiveBtn" type="button" aria-label="Archive" title="Past puzzles">📅</button>
    <button class="iconbtn round" id="helpBtn" type="button" aria-label="How to play" title="How to play">?</button>
    <button class="iconbtn round" id="profileBtn" type="button" aria-label="Your locker" title="Your locker">★</button>
    <label class="switch" title="Play as many puzzles as you like"><input type="checkbox" id="unlimited"><span class="track"></span><span>Unlimited</span></label>
    <button class="iconbtn round" id="settingsBtn" type="button" aria-label="Theme settings" title="Theme settings">🖌️</button>
  </div>
</nav>
<main>
  <div class="gamebar" id="gameBar" hidden>
    <button class="backbtn" id="backHub" type="button"><span aria-hidden="true">‹</span> All games</button>
    <div class="gtitle">
      <span class="gticon" id="gIcon" aria-hidden="true"></span>
      <span class="gtwords"><h2 id="gTitle"></h2><span id="modeLabel"></span></span>
    </div>
  </div>
  <p class="archbar" id="archBar" hidden><span id="archText"></span>
    <button class="linkbtn" id="pickDay" type="button">Pick another day</button>
    <button class="linkbtn" id="backToday" type="button">Back to today</button></p>

  <section class="view" id="view-hub">
    <div class="hubhead">
      <p class="hubdate" id="hubDate"></p>
      <h1 class="hubtitle">Today's games</h1>
      <div class="hubmeter" aria-hidden="true"><i id="hubBar"></i></div>
      <p class="hubprogress"><span id="hubProgress"></span> <span class="hubnext">New puzzles in <b id="hubNext">--:--:--</b></span></p>
    </div>
    <section class="hubfeatures" id="hubFeatures" aria-label="Featured games"></section>
    <section class="hubshelf" id="hubShelf" aria-label="Your game shelf" hidden></section>
    <button type="button" class="partycard" data-open="party">
      <svg class="rink" viewBox="0 0 400 160" aria-hidden="true" preserveAspectRatio="xMidYMid slice">
        <rect x="6" y="6" width="388" height="148" rx="70" fill="none" stroke="currentColor" stroke-width="2"/>
        <line x1="200" y1="6" x2="200" y2="154" stroke="#e5484d" stroke-width="4"/>
        <line x1="140" y1="6" x2="140" y2="154" stroke="#5b8def" stroke-width="4"/>
        <line x1="260" y1="6" x2="260" y2="154" stroke="#5b8def" stroke-width="4"/>
        <circle cx="200" cy="80" r="30" fill="none" stroke="currentColor" stroke-width="2"/>
        <circle cx="70" cy="45" r="22" fill="none" stroke="#e5484d" stroke-width="2"/>
        <circle cx="70" cy="115" r="22" fill="none" stroke="#e5484d" stroke-width="2"/>
        <circle cx="330" cy="45" r="22" fill="none" stroke="#e5484d" stroke-width="2"/>
        <circle cx="330" cy="115" r="22" fill="none" stroke="#e5484d" stroke-width="2"/>
      </svg>
      <span class="partytext"><b>Party Mode</b><span>Host on a big screen. Friends answer from their phones.</span></span>
      <span class="partycta">Start a party</span>
    </button>
    <div class="libraryhead"><div><p>All modes</p><h2>Game library</h2></div><button type="button" class="librarytoggle" id="libraryToggle" aria-expanded="false">Browse all games <span aria-hidden="true">›</span></button></div>
    <div class="libraryfilters" id="libraryFilters" role="group" aria-label="Filter game library"></div>
    <div id="hubSections" hidden></div>
  </section>

  <section class="view" id="view-classic" hidden>
    <div class="optrow" id="classicOpts">
      <button class="linkbtn" id="silBtn" type="button">Show silhouette</button>
      <label class="switch"><input type="checkbox" id="hardMode"><span class="track"></span><span>Hard mode</span></label>
      <span class="optnote" id="hardNote"></span>
    </div>
    <div class="search">
      <input id="guess" autocomplete="off" role="combobox" aria-expanded="false"
             aria-controls="opts" placeholder="Guess 1 of 8">
      <ul class="list" id="opts" role="listbox" hidden></ul>
    </div>
    <div class="slot">
      <div class="banner" id="banner">
        <p class="headline" id="result"></p>
        <p class="cheer" id="cheer"></p>
        <img id="reveal" alt="">
        <p class="pname" id="pname"></p>
        <p class="pmeta" id="pmeta"></p>
        <div class="resultrecap" id="resultRecap" hidden></div>
        <a class="profile" id="profile" target="_blank" rel="noopener">View profile on NHL.com</a>
        <p class="countdown" id="countdown" hidden></p>
        <button class="btn" id="again" hidden>Next player</button>
      </div>
    </div>
    <p class="nodata" hidden>This game isn't available right now.</p>
    <div class="board">
      <table>
        <thead><tr><th></th><th>TEAM</th><th>CONF</th><th>DIV</th><th>POS</th><th>SHOOTS</th><th>AGE</th><th>NATION</th><th>#</th></tr></thead>
        <tbody id="rows"></tbody>
      </table>
    </div>
  </section>

  <section class="view" id="view-statline" hidden>
    <p class="intro" id="slIntro"></p>
    <div class="search">
      <input id="slGuess" autocomplete="off" role="combobox" aria-expanded="false"
             aria-controls="slOpts" placeholder="Guess 1 of 8">
      <ul class="list" id="slOpts" role="listbox" hidden></ul>
    </div>
    <div class="slot"></div>
    <p class="nodata" hidden>This game needs career stats. Rebuild the site to load them.</p>
    <div class="tabrow"><div class="tabs small" role="tablist" aria-label="Reveal order">
      <button type="button" role="tab" data-order="oldest">Oldest season first</button>
      <button type="button" role="tab" data-order="newest">Newest season first</button>
    </div></div>
    <p class="optnote center" id="slOrderNote"></p>
    <p class="slhint" id="slHint" hidden></p>
    <table class="seasons">
      <thead><tr id="slHead"></tr></thead>
      <tbody id="slRows"></tbody>
    </table>
    <p class="hint" id="slLeft"></p>
    <ul class="wrong" id="slWrong"></ul>
  </section>

  <section class="view" id="view-hl" hidden>
    <div class="optrow"><label class="pickstat">Stat <select id="hlStatSel" aria-label="Stat to compare"></select></label></div>
    <p class="intro" id="hlIntro"></p>
    <div class="hlscore"><span>Streak<b id="hlStreak">0</b></span><span>Best<b id="hlBest">0</b></span></div>
    <div class="slot"></div>
    <p class="nodata" hidden>This game needs career stats. Rebuild the site to load them.</p>
    <div class="hlpair" id="hlPair">
      <div id="hlA"></div>
      <div class="hlvs">VS</div>
      <div id="hlB"></div>
    </div>
    <p class="hint"><b id="hlLeft"></b><span id="hlStat" hidden></span></p>
    <p class="hint"><span id="hlNote"></span><span class="keytip"> Tip: use the ↑ and ↓ keys.</span></p>
  </section>

  <section class="view" id="view-journey" hidden>
    <p class="intro">Whose NHL career path is this?</p>
    <div class="jypath" id="jyPath"></div>
    <div class="chips hints" id="jyHints"></div>
    <div class="search narrow">
      <input id="jyGuess" autocomplete="off" role="combobox" aria-expanded="false" aria-controls="jyOpts" placeholder="Guess 1 of 6">
      <ul class="list" id="jyOpts" role="listbox" hidden></ul>
    </div>
    <div class="slot"></div>
    <p class="nodata" hidden>This game needs career stats. Rebuild the site to load them.</p>
    <p class="hint" id="jyLeft"></p>
    <ul class="wrong" id="jyWrong"></ul>
  </section>

  <section class="view" id="view-blur" hidden>
    <p class="intro">Who's behind the blur?</p>
    <div class="blurbox"><img id="blImg" alt="Blurred photo of the mystery player" draggable="false"></div>
    <div class="chips hints" id="blHints"></div>
    <div class="search narrow">
      <input id="blGuess" autocomplete="off" role="combobox" aria-expanded="false" aria-controls="blOpts" placeholder="Guess 1 of 6">
      <ul class="list" id="blOpts" role="listbox" hidden></ul>
    </div>
    <div class="slot"></div>
    <p class="nodata" hidden>This game isn't available right now.</p>
    <p class="hint" id="blLeft"></p>
    <ul class="wrong" id="blWrong"></ul>
  </section>

  <section class="view" id="view-number" hidden>
    <div class="ttcard">
      <img id="numImg" alt="">
      <div><p class="pname" id="numName"></p><p class="pmeta tmeta" id="numMeta"></p></div>
    </div>
    <p class="ttq">What number does he wear?</p>
    <div class="numrow">
      <input id="numGuess" type="text" inputmode="numeric" maxlength="2" autocomplete="off" placeholder="0–99" aria-label="Sweater number">
      <button class="btn" id="numGo" type="button">Guess</button>
    </div>
    <div class="chips" id="numHist"></div>
    <p class="hint" id="numLeft"></p>
    <div class="slot"></div>
    <p class="nodata" hidden>This game isn't available right now.</p>
  </section>

  <section class="view" id="view-roster" hidden>
    <div class="ttcard">
      <img id="roLogo" class="rologo" alt="">
      <div><p class="pname" id="roTeam"></p><p class="pmeta">Name as many players on this team's roster as you can in 60 seconds.</p></div>
    </div>
    <div class="hlscore"><span>Time<b id="roTime">60</b></span><span>Named<b id="roCount">0</b>/<span id="roTotal">0</span></span></div>
    <div class="numrow wide">
      <input id="roInput" autocomplete="off" autocorrect="off" autocapitalize="words" spellcheck="false" enterkeyhint="send" placeholder="Press Start to begin" aria-label="Player name">
      <button class="btn" id="roStart" type="button">Start</button>
    </div>
    <p class="hint romsg" id="roMsg" aria-live="polite"></p>
    <div class="slot"></div>
    <p class="nodata" hidden>This game isn't available right now.</p>
    <div class="chips" id="roFound"></div>
  </section>

  <section class="view" id="view-draft" hidden>
    <div class="ttcard">
      <img id="drImg" alt="">
      <div><p class="pname" id="drName"></p><p class="pmeta tmeta" id="drMeta"></p></div>
    </div>
    <p class="ttq">When was he drafted, and in which round?</p>
    <div class="numrow wide">
      <input id="drYear" type="text" inputmode="numeric" maxlength="4" autocomplete="off" aria-label="Draft year">
      <select id="drRound" aria-label="Draft round"></select>
      <button class="btn" id="drGo" type="button">Guess</button>
    </div>
    <div class="chips hints" id="drHints"></div>
    <div id="drHist"></div>
    <p class="hint" id="drLeft"></p>
    <div class="slot"></div>
    <p class="nodata" hidden>This game needs draft info. Rebuild the site to load it.</p>
  </section>

  <section class="view" id="view-map" hidden>
    <div class="ttcard">
      <img id="mpImg" alt="">
      <div><p class="pname" id="mpName"></p><p class="pmeta tmeta" id="mpMeta"></p></div>
    </div>
    <p class="ttq">Where was he born?</p>
    <div class="mapwrap">
      <svg id="mapSvg" class="mapsvg" role="img" aria-label="World map. Tap to place a pin." viewBox="-130 -85 260 145" preserveAspectRatio="xMidYMid meet">
        <rect x="-400" y="-300" width="800" height="600" class="sea"/>
        <g transform="scale(0.72,1)"><path class="land" fill-rule="evenodd" d="M180,16.17L179.56,16.64L179.57,16.75L179.93,16.52L179.93,16.74L179.42,16.81L179.2,16.71L179.01,16.9L178.71,16.98L178.6,16.8L178.5,16.79L178.58,16.62L178.81,16.63L178.96,16.48L179.55,16.25L180,16.17ZM143.18,11.95L143.11,12.3L143.4,12.64L143.59,13.44L143.55,13.74L143.76,14.35L143.96,14.46L144.47,14.23L144.65,14.49L145.29,14.94L145.27,15.48L145.46,16.06L145.43,16.41L145.75,16.88L145.91,16.91L146.13,17.64L146.03,18.27L146.33,18.55L146.3,18.84L146.38,18.98L147.14,19.39L147.42,19.38L147.74,19.77L148.76,20.29L148.88,20.48L148.73,20.47L148.68,20.58L149.2,21.13L149.45,21.58L149.7,22.44L149.82,22.39L149.97,22.55L149.94,22.31L150.02,22.17L150.54,22.56L150.62,22.37L150.76,22.58L150.84,23.46L151.15,23.78L151.83,24.12L152.13,24.6L152.46,24.8L152.65,25.2L152.91,25.43L152.92,25.69L153.16,25.96L153.08,26.3L153.12,27.19L153.58,28.24L153.62,28.67L153.6,28.85L153.35,29.29L153.27,29.89L153.03,30.56L152.94,31.43L152.56,32.05L152.47,32.44L152.14,32.68L152.16,32.76L151.81,32.9L151.43,33.52L151.29,33.58L151.28,33.93L151.12,34.01L151.23,34.03L150.87,34.5L150.8,35.01L150.57,35.21L150.2,35.83L149.96,36.85L149.93,37.53L149.48,37.77L148.26,37.83L147.88,37.93L146.86,38.66L146.22,38.73L146.34,38.89L146.47,38.84L146.48,39.07L146.4,39.15L146.16,38.87L145.94,38.9L145.79,38.67L145.4,38.54L145.54,38.39L145.48,38.24L145.29,38.24L144.96,38.5L144.72,38.34L144.91,38.34L145.12,38.09L144.89,37.9L144.4,38.14L144.67,38.21L143.54,38.82L142.46,38.39L141.72,38.27L141.59,38.39L141.42,38.36L141.01,38.08L140.63,38.03L140.39,37.9L139.78,37.25L139.74,37.06L139.86,36.66L139.73,36.37L139.47,36.01L138.97,35.58L139.18,35.52L139.29,35.61L139.28,35.38L138.52,35.64L138.18,35.61L138.51,35.02L138.49,34.76L138.09,34.17L137.69,35.14L136.88,35.24L137.01,34.92L137.39,34.91L137.49,34.16L137.93,33.58L137.85,33.2L137.99,33.09L137.78,32.58L137.79,32.82L137.44,33.19L137.24,33.63L136.43,34.03L135.89,34.66L135.97,34.98L135.79,34.86L135.65,34.94L135.32,34.64L135.12,34.59L135.22,34.49L135.45,34.58L135.22,33.96L134.89,33.63L134.72,33.26L134.3,33.17L134.1,32.75L134.23,32.73L134.23,32.55L133.67,32.21L133.21,32.18L132.76,31.96L132.21,32.01L131.72,31.7L131.14,31.5L130.78,31.6L128.95,31.7L127.32,32.26L125.92,32.3L124.76,32.88L124.24,33.02L123.87,33.6L123.51,33.92L123.21,33.99L122.78,33.89L122.15,33.99L122.06,33.87L121.41,33.83L119.85,33.97L119.64,34.1L119.45,34.37L118.9,34.48L118.14,34.99L117.86,35.05L116.52,34.99L115.99,34.8L115.57,34.43L115.01,34.26L114.99,33.52L115.18,33.64L115.36,33.64L115.52,33.53L115.68,33.19L115.62,32.67L115.73,32.4L115.7,31.69L115.08,30.56L114.86,29.14L114.17,28.08L114.03,27.35L113.18,26.18L113.32,26.24L113.36,26.08L113.58,26.56L113.73,26.6L113.84,26.5L113.85,26.33L113.59,26.1L113.4,25.71L113.45,25.6L113.71,25.83L113.72,26.13L113.85,26.01L113.99,26.32L114.09,26.39L114.22,26.29L114.21,25.85L113.42,24.44L113.49,23.87L113.76,23.42L113.8,22.91L113.68,22.64L114.02,21.88L114.12,21.83L114.14,21.91L114.14,22.48L114.38,22.34L114.71,21.82L115.46,21.49L116.01,21.03L116.71,20.65L117.41,20.72L118.2,20.38L118.75,20.26L119.1,20L119.59,20.04L120.43,19.84L121,19.6L121.34,19.32L121.83,18.48L122.35,18.11L122.15,17.55L122.26,17.14L122.72,16.79L122.97,16.44L123.56,17.52L123.59,17.03L123.83,17.12L123.87,16.92L123.49,16.49L123.63,16.42L123.61,16.22L123.73,16.19L123.86,16.38L124.04,16.26L124.3,16.39L124.77,16.4L124.4,16.3L124.42,16.13L124.58,16.11L124.65,15.87L124.61,15.82L124.5,15.97L124.38,15.76L124.44,15.49L124.56,15.5L124.69,15.27L125.06,15.44L125.07,15.31L124.91,15.31L124.84,15.16L125.04,15L125.36,15.12L125.38,15.02L125.24,14.94L125.18,14.71L125.28,14.58L125.58,14.48L125.63,14.26L125.7,14.29L125.66,14.53L125.82,14.47L125.89,14.62L126.02,14.49L126.11,14.11L126.05,13.98L126.18,14L126.26,14.16L126.4,14.02L126.57,14.16L126.78,13.96L126.78,13.79L126.9,13.74L127.46,14.03L128.2,14.75L128.07,15.33L128.16,15.23L128.25,15.3L128.18,15.04L128.58,14.77L129.06,14.88L129.22,15.16L129.27,14.87L129.46,14.93L129.63,15.14L129.64,14.85L129.85,14.83L129.6,14.65L129.7,14.56L129.38,14.39L129.71,13.98L129.84,13.57L130.26,13.3L130.13,13.15L130.17,12.96L130.32,12.88L130.4,12.69L130.62,12.65L130.62,12.43L130.87,12.56L130.87,12.37L131.02,12.34L131.02,12.21L131.22,12.18L131.29,12.07L131.44,12.28L132.06,12.28L132.25,12.19L132.41,12.3L132.51,12.13L132.71,12.12L132.63,12.04L132.67,11.65L132.48,11.49L132.07,11.47L131.82,11.3L131.96,11.18L132.16,11.31L132.33,11.22L132.68,11.51L132.96,11.41L133.19,11.71L133.9,11.83L134.42,12.05L134.73,11.98L135.03,12.19L135.22,12.22L135.92,11.83L135.7,12.21L136.01,12.19L136.08,12.42L136.26,12.43L136.33,12.31L136.27,12.13L136.54,11.96L136.61,12.13L136.9,12.24L136.95,12.35L136.54,12.78L136.59,13L136.46,13.23L136.29,13.14L135.93,13.3L135.95,13.93L135.88,14.15L135.41,14.76L135.45,14.92L136.21,15.4L136.29,15.57L136.7,15.69L136.78,15.89L137,15.88L137.7,16.23L138.25,16.72L139.01,16.9L139.25,17.33L140.04,17.7L140.51,17.62L140.83,17.41L141.41,16.07L141.63,15.06L141.52,14.47L141.59,14.15L141.47,13.8L141.65,13.26L141.61,12.94L141.78,12.78L141.92,12.8L141.85,12.58L141.68,12.49L141.69,12.35L141.87,11.98L141.96,12.05L142.17,10.95L142.46,10.71L142.61,10.75L142.55,10.87L142.72,11.01L142.84,11.31L142.87,11.82L143.18,11.95ZM178.28,17.37L178.59,17.65L178.67,18.08L177.96,18.26L177.32,18.08L177.26,17.86L177.5,17.54L177.82,17.39L178.19,17.31L178.28,17.37ZM164.2,20.25L164.44,20.28L165.19,20.77L165.66,21.27L166.94,22.09L166.97,22.32L166.77,22.38L166.47,22.26L164.93,21.29L164.17,20.48L164.04,20.17L164.2,20.25ZM127.73,-0.85L127.88,-0.83L127.97,-1.04L128.16,-1.16L128.22,-1.4L128.69,-1.57L128.7,-1.11L128.3,-0.88L128.26,-0.73L128.61,-0.55L128.69,-0.36L128.9,-0.22L127.98,-0.47L127.89,-0.3L127.98,0.25L128.43,0.89L128.05,0.71L127.69,0.24L127.71,-0.29L127.54,-0.61L127.61,-0.85L127.43,-1.14L127.63,-1.84L128.04,-2.2L127.89,-1.83L128.01,-1.7L128.01,-1.33L127.65,-1.01L127.73,-0.85ZM69.18,49.11L69.59,48.97L69.64,49.12L69.41,49.18L69.54,49.26L70.32,49.06L70.48,49.08L70.56,49.2L70.39,49.43L70.17,49.34L69.76,49.43L69.99,49.58L70.25,49.53L70.31,49.58L70.12,49.7L69.15,49.53L69.09,49.65L68.87,49.71L68.78,49.65L68.87,49.44L68.8,49.23L68.88,49.16L68.77,49.07L68.83,48.85L69.06,48.66L69.14,48.86L69.03,49.02L69.18,49.11ZM63.37,-80.7L62.52,-80.82L63.12,-80.97L64.1,-81L64.31,-81.18L65.17,-81.14L65.38,-81.06L65.44,-80.93L64.55,-80.76L63.37,-80.7ZM57.96,-80.12L57.33,-80.16L57.19,-80.4L57.01,-80.47L57.08,-80.49L58.48,-80.46L59.26,-80.34L58.4,-80.32L57.96,-80.12ZM-25.43,-70.92L-25.47,-70.78L-25.35,-70.69L-25.4,-70.65L-26.22,-70.45L-26.6,-70.55L-28.04,-70.49L-27.71,-70.71L-27.71,-70.9L-27.62,-70.91L-26.62,-70.88L-25.82,-71.04L-25.43,-70.92ZM159.75,9.27L159.97,9.43L160.35,9.42L160.63,9.59L160.82,9.86L160.65,9.93L159.8,9.76L159.61,9.47L159.63,9.31L159.75,9.27ZM117.31,-8.44L117.22,-8.37L117.23,-8.46L117.35,-8.71L117.88,-9.24L118.11,-9.35L119.22,-10.48L119.31,-10.97L119.5,-11.35L119.55,-11.31L119.53,-10.95L119.69,-10.5L119.37,-10.33L119.19,-10.06L118.78,-9.92L118.77,-9.77L118.43,-9.26L117.31,-8.44ZM122.5,-11.62L122.84,-11.6L122.93,-11.53L122.89,-11.44L123.16,-11.54L123.12,-11.29L122.8,-10.99L122.77,-10.82L121.95,-10.44L122.1,-11.64L121.89,-11.79L121.92,-11.85L122.03,-11.9L122.5,-11.62ZM123.13,-9.06L122.99,-9.06L122.87,-9.32L122.56,-9.48L122.4,-9.82L122.47,-9.96L122.86,-10.09L122.82,-10.5L122.98,-10.89L123.26,-10.99L123.51,-10.92L123.57,-10.78L123.16,-9.86L123.15,-9.61L123.32,-9.27L123.13,-9.06ZM124.57,-11.34L124.93,-11.37L125.03,-11.21L125.01,-10.79L125.16,-10.64L125.27,-10.31L125.14,-10.19L124.99,-10.37L125.03,-10.03L124.78,-10.17L124.74,-10.88L124.66,-10.96L124.45,-10.92L124.31,-11.49L124.57,-11.34ZM125.24,-12.53L125.32,-12.32L125.54,-12.19L125.46,-11.95L125.49,-11.59L125.57,-11.24L125.74,-11.05L125.63,-11.13L125.23,-11.15L124.95,-11.48L125,-11.76L124.45,-12.15L124.33,-12.4L124.29,-12.57L125.24,-12.53ZM120.7,-13.48L121.2,-13.43L121.52,-13.13L121.54,-12.64L121.39,-12.3L121.24,-12.22L120.92,-12.51L120.65,-13.17L120.34,-13.41L120.4,-13.52L120.7,-13.48ZM155.96,6.69L155.91,6.8L155.72,6.86L155.34,6.72L155.21,6.53L155.2,6.31L154.76,5.93L154.73,5.44L155.09,5.62L155.47,6.15L155.82,6.38L155.96,6.69ZM152.97,4.76L152.89,4.83L152.74,4.64L152.67,4.13L152.28,3.58L151.07,2.83L150.75,2.74L150.83,2.71L150.83,2.57L151.23,2.87L152.03,3.25L153.02,4.11L153.13,4.35L152.97,4.76ZM138.54,8.27L138.3,8.41L137.65,8.39L138.08,7.57L138.3,7.44L138.77,7.39L138.99,7.7L138.79,8.06L138.54,8.27ZM129.75,2.87L129.98,2.98L130.38,2.99L130.57,3.13L130.86,3.57L130.81,3.86L129.84,3.33L129.51,3.33L129.47,3.45L128.86,3.23L128.52,3.45L128.13,3.16L127.9,3.5L127.88,3.22L128.2,2.87L128.99,2.83L129.17,2.93L129.48,2.79L129.75,2.87ZM126.86,3.09L127.03,3.17L127.24,3.47L127.23,3.63L126.94,3.76L126.55,3.77L126.06,3.42L126.09,3.11L126.86,3.09ZM122.78,8.61L121.65,8.9L121.41,8.81L121.33,8.92L121.04,8.94L120.55,8.8L120.12,8.78L119.91,8.86L119.81,8.7L119.87,8.42L120.61,8.24L121.44,8.58L121.97,8.46L122.32,8.63L122.85,8.3L122.92,8.22L122.76,8.19L122.85,8.09L122.98,8.15L123.01,8.33L122.78,8.61ZM120.01,9.37L120.29,9.65L120.56,9.72L120.78,9.96L120.8,10.11L120.44,10.29L120.14,10.2L119.6,9.77L119.04,9.67L118.96,9.52L119.19,9.38L119.8,9.38L119.94,9.3L120.01,9.37ZM118.24,8.32L118.61,8.28L118.71,8.41L118.93,8.3L119.13,8.67L119.08,8.73L118.82,8.71L118.75,8.74L118.83,8.83L118.43,8.86L118.38,8.67L118.19,8.84L117.51,9.01L117.06,9.1L116.79,9.01L116.84,8.53L117.16,8.37L117.57,8.43L117.81,8.71L117.97,8.73L118.23,8.59L117.81,8.34L117.76,8.15L118.12,8.12L118.24,8.32ZM116.64,8.61L116.51,8.82L116.59,8.89L116.24,8.91L115.86,8.79L116.08,8.74L116.06,8.44L116.4,8.2L116.72,8.34L116.64,8.61ZM115.45,8.16L115.7,8.41L115.33,8.62L115.14,8.85L115.06,8.57L114.61,8.38L114.47,8.17L114.94,8.19L115.15,8.07L115.45,8.16ZM106.05,1.67L106.37,2.46L106.82,2.57L106.61,2.9L106.67,3.07L106,2.82L105.79,2.18L105.13,2.04L105.37,1.81L105.46,1.57L105.59,1.53L105.7,1.73L105.72,1.53L105.91,1.5L106.05,1.67ZM22.62,-58.62L22.96,-58.61L23.32,-58.45L22.73,-58.23L22.37,-58.22L22.15,-57.97L22,-57.93L22.19,-58.15L21.88,-58.26L21.98,-58.39L21.86,-58.5L22.62,-58.62ZM21.61,-78.6L22.04,-78.58L22.3,-78.23L22.99,-78.25L23.45,-78.15L23.15,-78.09L23.12,-77.99L24.9,-77.76L24.13,-77.66L23.74,-77.46L22.8,-77.28L22.43,-77.32L22.44,-77.43L22.69,-77.55L20.93,-77.46L20.87,-77.57L21.2,-77.62L21.65,-77.92L21.04,-78.06L20.53,-78.33L20.56,-78.42L20.23,-78.48L21.61,-78.6ZM62.17,-80.83L62.23,-80.79L62.08,-80.62L61.05,-80.42L60.28,-80.49L59.65,-80.43L59.29,-80.57L59.39,-80.71L59.72,-80.84L62.17,-80.83ZM47.44,-80.85L48.45,-80.81L48.69,-80.72L48.68,-80.63L47.71,-80.77L47.3,-80.61L46.14,-80.45L45.97,-80.57L44.9,-80.61L47.44,-80.85ZM50.28,-80.93L50.8,-80.91L51.7,-80.69L50.96,-80.54L49.85,-80.5L49.59,-80.38L48.81,-80.35L48.68,-80.3L48.96,-80.27L48.98,-80.16L47.74,-80.08L47.63,-80.11L47.98,-80.21L47.89,-80.24L46.99,-80.18L46.64,-80.3L47.9,-80.53L49.09,-80.52L49.19,-80.56L49.15,-80.71L49.24,-80.82L50.28,-80.93ZM50.27,-69.19L50.22,-69.05L50.09,-69.13L49.63,-68.86L48.91,-68.74L48.44,-68.8L48.28,-69.04L48.41,-69.35L48.95,-69.51L49.23,-69.51L50.27,-69.19ZM60.45,-69.93L60.44,-69.73L59.72,-69.71L59.5,-69.87L58.95,-69.89L58.47,-70.27L59.05,-70.46L60.45,-69.93ZM70.67,-73.1L69.92,-73.08L70,-73.36L70.35,-73.48L71.02,-73.5L71.63,-73.22L70.67,-73.1ZM92.68,-79.69L92.15,-79.68L91.07,-79.98L92.17,-80.05L93.8,-79.9L92.68,-79.69ZM113.39,-74.4L112.78,-74.1L112.11,-74.16L111.5,-74.35L111.88,-74.36L112.08,-74.55L113.39,-74.4ZM141.01,-74L140.41,-73.92L140.18,-74L140.1,-74.18L140.94,-74.26L141.1,-74.17L141.01,-74ZM23.85,-35.54L24.17,-35.6L24.11,-35.5L24.35,-35.36L24.72,-35.42L25.48,-35.31L25.73,-35.35L25.79,-35.12L26.32,-35.32L26.17,-35.02L24.8,-34.93L24.71,-35.09L24.46,-35.16L23.59,-35.26L23.57,-35.53L23.67,-35.51L23.74,-35.66L23.85,-35.54ZM23.42,-38.96L23.52,-38.81L24.13,-38.65L24.28,-38.22L24.56,-38.15L24.58,-38.02L24.36,-38.02L24.04,-38.39L23.65,-38.44L23.25,-38.8L22.88,-38.85L23.26,-39.03L23.42,-38.96ZM34.46,-35.59L33.94,-35.29L33.91,-35.2L34.05,-34.99L33.7,-34.97L33.41,-34.75L33.06,-34.67L33.01,-34.57L32.45,-34.73L32.32,-34.95L32.3,-35.08L32.88,-35.18L32.94,-35.39L33.61,-35.35L34.46,-35.59ZM19.08,-57.84L18.81,-57.71L18.79,-57.48L18.91,-57.4L18.15,-56.92L18.29,-57.08L18.11,-57.27L18.14,-57.56L18.54,-57.83L18.9,-57.92L19.08,-57.84ZM12.57,-55.79L12.55,-55.66L12.22,-55.47L12.41,-55.29L12.09,-55.19L12.05,-54.82L11.86,-54.77L11.65,-55.19L11.29,-55.2L11.12,-55.6L10.98,-55.72L11.32,-55.75L11.47,-55.94L11.63,-55.96L11.69,-55.73L11.82,-55.7L11.93,-55.9L11.87,-55.97L12.22,-56.12L12.58,-56.06L12.57,-55.79ZM10.65,-55.61L10.82,-55.32L10.79,-55.13L10.62,-55.05L9.99,-55.16L9.86,-55.36L9.86,-55.52L10.65,-55.61ZM3.15,-39.79L3.46,-39.7L3.24,-39.39L3.07,-39.3L2.8,-39.39L2.7,-39.54L2.5,-39.48L2.37,-39.57L2.9,-39.91L3.2,-39.96L3.15,-39.79ZM-178.88,-71.58L-178.35,-71.53L-177.5,-71.22L-177.82,-71.07L-179.16,-70.94L-180,-70.99L-180,-71.54L-178.88,-71.58ZM-58.85,51.27L-58.43,51.32L-58.38,51.37L-58.51,51.48L-58.27,51.57L-58.26,51.42L-57.92,51.4L-57.81,51.52L-57.96,51.58L-57.79,51.64L-57.84,51.71L-58.68,51.94L-58.65,52.1L-59.2,52.02L-59.07,52.17L-59.34,52.2L-59.4,52.31L-59.53,52.24L-59.65,52.13L-59.57,51.93L-59.06,51.69L-59.1,51.49L-58.85,51.27ZM-37.1,54.07L-36.7,54.11L-36.61,54.19L-36.65,54.26L-36.33,54.25L-36.07,54.55L-35.9,54.55L-35.91,54.71L-35.8,54.76L-36.09,54.87L-36.51,54.51L-36.89,54.34L-37.63,54.17L-37.69,54.08L-37.62,54.04L-38.02,54.01L-37.38,53.98L-37.1,54.07ZM-73.77,43.35L-74.11,43.36L-74.39,43.23L-74.21,42.88L-74.04,41.8L-73.53,41.9L-73.42,42.19L-73.53,42.31L-73.47,42.47L-73.79,42.59L-73.44,42.94L-73.75,43.16L-73.77,43.35ZM-60.29,51.46L-59.39,51.36L-59.27,51.43L-59.92,51.97L-60.25,51.99L-60.51,52.19L-60.96,52.06L-60.24,51.77L-60.58,51.71L-60.25,51.64L-60.57,51.36L-60.29,51.46ZM-74.48,49.15L-74.52,49.62L-74.46,49.69L-74.59,50.01L-74.76,50.01L-74.88,49.73L-74.72,49.42L-74.96,49.53L-75.07,49.85L-75.55,49.79L-75.52,49.62L-75.34,49.63L-75.31,49.49L-75.47,49.36L-75.09,49.27L-75.21,49.15L-74.95,48.96L-74.98,48.82L-74.9,48.73L-74.55,48.77L-74.48,49.15ZM-72.99,44.78L-73.23,44.86L-73.4,44.77L-73.45,44.64L-73.26,44.35L-72.78,44.51L-72.99,44.78ZM-61.8,-49.09L-63.04,-49.22L-63.57,-49.4L-63.78,-49.6L-64.49,-49.89L-64.13,-49.94L-62.86,-49.71L-61.82,-49.28L-61.7,-49.14L-61.8,-49.09ZM-61.11,-45.94L-60.87,-45.98L-61.04,-45.88L-60.97,-45.84L-61.06,-45.7L-60.74,-45.75L-60.46,-45.97L-60.73,-45.96L-60.3,-46.31L-60.23,-46.2L-59.87,-46.16L-59.93,-46.02L-59.83,-45.97L-60.67,-45.59L-61.28,-45.57L-61.45,-45.72L-61.5,-45.94L-61.41,-46.17L-60.87,-46.8L-60.49,-47.01L-60.41,-47L-60.33,-46.77L-60.49,-46.27L-61.11,-45.94ZM-171.46,-63.64L-170.87,-63.59L-170.43,-63.7L-169.55,-63.37L-168.72,-63.31L-168.85,-63.17L-169.36,-63.17L-169.68,-62.96L-169.82,-63.12L-170.85,-63.44L-171.63,-63.35L-171.82,-63.48L-171.75,-63.7L-171.46,-63.64ZM-166.14,-60.38L-165.73,-60.31L-165.71,-60.07L-165.59,-59.91L-166.1,-59.85L-166.15,-59.76L-167.14,-60.01L-167.44,-60.21L-166.84,-60.22L-166.48,-60.38L-166.14,-60.38ZM-163.48,-54.98L-163.38,-54.82L-163.08,-54.67L-163.36,-54.74L-163.58,-54.63L-164.07,-54.62L-164.59,-54.4L-164.82,-54.42L-164.9,-54.54L-164.48,-54.91L-163.81,-55.05L-163.48,-54.98ZM-77.26,-18.46L-76.35,-18.15L-76.21,-17.91L-76.52,-17.87L-76.85,-17.97L-76.94,-17.85L-77.12,-17.88L-77.2,-17.71L-77.36,-17.83L-77.77,-17.88L-78.04,-18.17L-78.29,-18.22L-78.33,-18.35L-77.87,-18.52L-77.26,-18.46ZM-66.13,-18.44L-65.63,-18.38L-65.62,-18.24L-65.97,-17.97L-67.2,-17.99L-67.17,-18.22L-67.26,-18.36L-67.16,-18.5L-66.13,-18.44ZM-152.9,-57.82L-152.43,-57.83L-152.48,-57.7L-152.22,-57.58L-152.41,-57.45L-152.94,-57.5L-152.68,-57.35L-153.73,-57.05L-153.64,-56.96L-153.97,-56.77L-154.07,-56.82L-153.79,-56.99L-154.1,-57.02L-154.04,-57.12L-154.24,-57.14L-154.38,-57.1L-154.18,-57.01L-154.34,-56.92L-154.71,-57.34L-154.54,-57.56L-154.12,-57.65L-153.69,-57.31L-153.84,-57.64L-153.69,-57.66L-153.91,-57.79L-153.84,-57.86L-153.49,-57.73L-153.22,-57.8L-153.16,-57.97L-152.85,-57.9L-152.9,-57.82ZM-152.42,-58.36L-152.32,-58.41L-151.97,-58.31L-152.11,-58.16L-152.27,-58.25L-152.31,-58.13L-152.6,-58.16L-152.93,-57.99L-153.38,-58.09L-152.98,-58.3L-152.77,-58.28L-152.84,-58.42L-152.42,-58.36ZM-130.98,-55.49L-131.19,-55.21L-131.42,-55.28L-131.45,-55.41L-131.76,-55.17L-131.81,-55.22L-131.85,-55.42L-131.65,-55.59L-131.62,-55.83L-131.27,-55.96L-131,-55.73L-130.98,-55.49ZM-133.57,-56.34L-133.2,-56.32L-133.1,-56.09L-132.6,-55.9L-132.17,-55.48L-132.51,-55.59L-132.63,-55.47L-132.42,-55.48L-132.16,-55.32L-132.21,-55.22L-131.98,-55.21L-132.02,-54.73L-132.55,-54.95L-132.62,-55.14L-132.78,-55.05L-133.12,-55.33L-132.96,-55.4L-133.08,-55.5L-133.03,-55.59L-133.3,-55.61L-133.68,-55.79L-133.41,-55.8L-133.24,-55.92L-133.37,-56.04L-133.74,-55.96L-133.53,-56.15L-133.57,-56.34ZM-133.37,-57L-133,-56.93L-132.96,-56.68L-133.03,-56.62L-133.33,-56.83L-133.16,-56.5L-133.48,-56.45L-133.63,-56.48L-133.68,-56.8L-133.98,-57.01L-133.87,-57.07L-133.37,-57ZM-134.97,-57.35L-134.62,-56.72L-134.68,-56.22L-134.98,-56.52L-134.88,-56.68L-135.33,-56.82L-135.2,-57.03L-135.45,-57.25L-135.66,-57.03L-135.81,-57.01L-135.82,-57.28L-135.45,-57.53L-134.97,-57.35ZM-134.68,-58.16L-134.24,-58.14L-133.82,-57.63L-134.18,-58.01L-134.31,-58.03L-134.27,-57.88L-133.94,-57.58L-133.91,-57.37L-134.44,-57.06L-134.61,-57.14L-134.49,-57.48L-134.66,-57.64L-134.93,-58.33L-134.68,-58.16ZM-135.73,-58.24L-135.59,-58.15L-135.69,-58.04L-135.61,-57.99L-135.35,-58.12L-134.95,-58.02L-134.97,-57.82L-135.34,-57.77L-134.98,-57.72L-134.87,-57.59L-134.93,-57.48L-135.56,-57.67L-135.69,-57.42L-135.91,-57.45L-136.08,-57.67L-136.57,-57.97L-136.32,-58.22L-136.14,-58.1L-136.09,-58.2L-135.73,-58.24ZM-128.55,-52.94L-128.51,-52.52L-128.68,-52.29L-128.75,-52.76L-128.9,-52.67L-129.18,-52.99L-129.03,-53.28L-128.63,-53.11L-128.55,-52.94ZM-132.66,-54.13L-132.3,-54.1L-132.17,-53.96L-132.18,-53.85L-132.53,-53.65L-132.19,-53.68L-132.13,-54.03L-131.67,-54.14L-132.01,-53.27L-132.52,-53.19L-132.75,-53.31L-132.43,-53.35L-132.85,-53.51L-133.05,-53.78L-133.1,-54.01L-133.05,-54.16L-132.66,-54.13ZM-131.75,-53.2L-131.63,-52.92L-131.97,-52.88L-131.46,-52.7L-131.59,-52.58L-131.43,-52.42L-131.26,-52.42L-131.32,-52.3L-131.14,-52.29L-131.22,-52.15L-132.17,-52.78L-132.26,-52.93L-132.14,-53L-132.55,-53.14L-131.75,-53.2ZM-63.81,-46.47L-63.68,-46.56L-63.13,-46.42L-62.16,-46.49L-62.02,-46.42L-62.53,-46.2L-62.53,-45.98L-63.02,-46.07L-62.89,-46.12L-63.06,-46.22L-62.98,-46.32L-63.27,-46.2L-63.21,-46.16L-63.64,-46.23L-63.76,-46.4L-64.11,-46.43L-64.14,-46.6L-64.39,-46.64L-64.35,-46.77L-63.99,-47.06L-64.09,-46.78L-63.81,-46.47ZM-72.51,-40.99L-72.58,-40.92L-72.52,-40.91L-71.9,-41.06L-73.19,-40.65L-73.9,-40.57L-73.82,-40.66L-74.03,-40.64L-73.57,-40.92L-72.63,-40.99L-72.27,-41.15L-72.51,-40.99ZM151.92,4.3L152.12,4.21L152.41,4.34L152.35,4.82L151.98,5.07L152.14,5.36L152.08,5.46L151.87,5.56L151.52,5.55L151.23,5.92L150.47,6.26L149.65,6.29L149.38,6.08L149.1,6.12L148.34,5.67L148.43,5.47L149.36,5.58L149.83,5.52L149.96,5.45L150.09,5.01L150.17,5.07L150.07,5.31L150.18,5.52L150.9,5.45L151.33,4.96L151.67,4.88L151.59,4.2L151.92,4.3ZM127.3,8.42L126.49,8.91L125.41,9.28L124.43,10.15L123.86,10.34L123.6,10.27L123.72,10.08L123.59,9.97L123.71,9.61L123.98,9.37L124.89,8.97L125.18,8.65L125.8,8.49L126.62,8.46L126.97,8.32L127.3,8.42ZM145.04,40.79L145.28,40.77L146.32,41.16L146.72,41.08L146.85,41.17L146.86,41.06L146.99,40.99L147.45,41L147.62,40.84L147.87,40.87L147.97,40.78L148.22,40.85L148.29,40.95L148.34,42.22L148.29,42.25L148.18,42.06L148.21,41.97L148.02,42.26L147.91,42.66L147.98,43.16L147.79,43.22L147.65,43.02L147.8,42.93L147.57,42.85L147.45,43.03L147.3,42.79L147.35,42.93L147.25,43.22L147,43.16L147.08,43.28L146.87,43.61L146.55,43.51L146.04,43.55L145.99,43.38L146.21,43.32L145.87,43.29L145.49,42.93L145.2,42.23L145.47,42.49L145.52,42.35L145.33,42.15L145.23,42.2L145.24,42.02L144.77,41.39L144.65,40.98L144.72,40.67L145.04,40.79ZM96.53,-81.08L96.75,-80.96L97.87,-80.76L97.86,-80.7L97.11,-80.61L97.03,-80.54L97.42,-80.32L97.18,-80.24L93.65,-80.01L91.64,-80.27L91.52,-80.36L92.83,-80.62L93.26,-80.79L92.61,-80.81L93.36,-81.03L95.8,-81.28L96.53,-81.08ZM97.67,-80.16L98.02,-80.02L97.63,-79.85L97.65,-79.76L98.06,-79.9L98.35,-79.88L98.6,-80.05L99.29,-80.02L100.06,-79.78L99.78,-79.63L99.68,-79.32L99.04,-79.29L99.9,-79.01L99.44,-78.83L97.56,-78.83L96.81,-78.98L95.8,-79L95.53,-79.1L95.02,-79.05L94.65,-79.13L94.22,-79.4L93.07,-79.5L94.99,-80.1L95.28,-80.03L95.5,-80.11L97.67,-80.16ZM102.88,-79.25L102.41,-78.84L102.95,-79.06L103.8,-79.15L104.63,-78.84L105.15,-78.82L105.31,-78.67L105.31,-78.5L104.74,-78.34L102.8,-78.19L101.2,-78.19L100.08,-77.97L99.29,-78.04L100.02,-78.34L100.42,-78.75L100.96,-78.79L100.86,-78.9L101.05,-79.12L101.54,-79.25L101.59,-79.35L102.25,-79.26L102.18,-79.37L102.4,-79.43L103.04,-79.33L102.88,-79.25ZM140.05,-75.83L140.82,-75.63L140.94,-75.7L140.99,-75.96L141.49,-76.14L142.67,-75.86L143.69,-75.86L145.36,-75.53L144.8,-75.42L144.73,-75.37L144.88,-75.27L144.02,-75.04L143.17,-75.12L142.82,-75.27L142.7,-75.45L142.73,-75.54L142.99,-75.63L142.94,-75.71L142.31,-75.69L142.09,-75.66L142.2,-75.39L142.62,-75.13L143.13,-74.97L142.47,-74.82L141.99,-74.99L140.27,-74.85L139.68,-74.96L139.33,-74.69L139.1,-74.66L138.09,-74.8L137.01,-75.24L136.98,-75.37L137.29,-75.35L137.22,-75.55L137.27,-75.75L137.71,-75.76L137.5,-75.91L137.63,-75.99L138.81,-76.2L140.05,-75.83ZM142.18,-73.9L143.34,-73.57L143.46,-73.46L143.45,-73.23L141.6,-73.31L140.66,-73.45L139.93,-73.36L139.69,-73.43L140.38,-73.48L141.08,-73.87L142.18,-73.9ZM146.8,-75.37L148.43,-75.41L148.51,-75.39L148.47,-75.27L148.59,-75.24L150.1,-75.22L150.53,-75.1L150.82,-75.16L150.58,-74.92L149.84,-74.8L148.3,-74.8L146.15,-75.2L146.44,-75.56L146.75,-75.51L146.8,-75.37ZM173.27,34.93L173.45,34.84L173.47,34.95L174.1,35.14L174.14,35.3L174.32,35.25L174.58,35.79L174.4,35.8L174.8,36.31L174.75,36.49L174.82,36.61L174.72,36.84L175.3,36.99L175.39,37.21L175.54,37.2L175.49,36.69L175.39,36.56L175.46,36.48L175.68,36.75L175.77,36.74L176.11,37.65L177.27,37.99L177.56,37.9L178.01,37.55L178.54,37.69L178.27,38.55L177.98,38.72L177.91,39.24L177.79,39.11L177.52,39.07L177.08,39.22L176.94,39.56L177.11,39.67L176.84,40.16L175.98,41.21L175.31,41.61L175.17,41.42L174.88,41.42L174.87,41.22L174.76,41.33L174.64,41.29L175.16,40.62L175.25,40.29L175.16,40.11L175.01,39.95L173.93,39.51L173.76,39.32L173.84,39.14L174.4,38.96L174.6,38.79L174.84,38.02L174.8,37.9L174.93,37.8L174.59,37.1L174.73,37.22L174.93,37.08L174.78,36.94L174.48,36.94L174.19,36.49L174.4,36.6L174.39,36.24L174.04,36.12L173.91,35.91L174.17,36.33L174.1,36.39L173.41,35.54L173.63,35.32L173.38,35.5L173.12,35.21L173.19,35.02L172.71,34.46L173.04,34.43L172.96,34.54L173.27,34.93ZM173.12,41.28L173.95,40.92L173.8,41.27L174.02,41.07L174,40.99L174.3,41.02L174.04,41.24L174.37,41.1L174.07,41.43L174.16,41.56L174.08,41.67L174.28,41.74L173.22,42.98L172.62,43.27L172.73,43.35L172.53,43.46L172.69,43.44L172.81,43.62L173.07,43.68L173.07,43.87L172.5,43.84L172.58,43.77L172.48,43.73L172.3,43.87L172.04,43.7L172.18,43.9L171.24,44.26L171.31,44.3L171.15,44.91L171,44.91L171.11,45.04L170.7,45.68L170.78,45.87L170.34,45.99L169.69,46.55L169.1,46.63L168.38,46.61L168.19,46.36L167.84,46.37L167.54,46.15L167.37,46.24L166.83,46.23L166.71,46.13L166.92,45.96L166.73,46.05L166.65,46.04L166.72,45.89L166.49,45.96L166.51,45.81L167,45.71L166.8,45.65L166.99,45.53L166.73,45.54L166.78,45.41L166.92,45.41L166.87,45.31L167.16,45.41L167.12,45.32L167.23,45.29L167.03,45.22L167.03,45.12L167.26,45.08L167.17,45L167.41,44.83L167.47,44.96L167.48,44.77L167.79,44.6L167.91,44.66L167.86,44.5L168.37,44.08L169.07,43.86L169.18,43.91L169.17,43.78L169.83,43.54L169.86,43.43L170.24,43.16L170.4,43.18L170.3,43.11L170.46,43.04L170.61,43.09L170.52,43.01L170.67,42.96L170.74,43.03L170.97,42.72L171.04,42.86L171.03,42.7L171.31,42.46L171.25,42.4L171.49,41.79L171.95,41.54L172.27,40.76L172.64,40.52L172.94,40.52L172.73,40.54L172.7,40.67L172.99,40.85L173.12,41.28ZM126.01,-9.32L126.19,-9.28L126.3,-8.95L126.14,-8.6L126.37,-8.48L126.46,-8.2L126.44,-7.83L126.57,-7.68L126.58,-7.25L126.44,-7.01L126.19,-6.85L126.19,-6.31L125.82,-7.33L125.69,-7.26L125.38,-6.69L125.59,-6.47L125.67,-5.98L125.35,-5.6L125.24,-5.76L125.23,-6.07L125.04,-5.87L124.93,-5.88L124.21,-6.23L124.08,-6.4L123.99,-6.99L124.21,-7.4L123.97,-7.66L123.67,-7.82L123.49,-7.81L123.39,-7.41L123.18,-7.53L123.1,-7.7L122.99,-7.55L122.84,-7.53L122.79,-7.72L122.62,-7.76L122.47,-7.64L122.14,-6.95L121.96,-6.97L121.92,-7.2L122.24,-7.95L122.91,-8.16L123.05,-8.43L123.43,-8.7L123.68,-8.62L123.85,-8.43L123.8,-8.05L124.2,-8.23L124.4,-8.6L124.73,-8.56L124.87,-8.97L125.14,-8.87L125.21,-9.03L125.5,-9.01L125.41,-9.67L125.47,-9.76L125.88,-9.51L126.01,-9.32ZM121.1,-18.62L121.85,-18.3L122.04,-18.33L122.15,-18.49L122.27,-18.46L122.32,-18.32L122.18,-18.06L122.15,-17.66L122.41,-17.18L122.52,-17.12L122.14,-16.18L121.6,-15.93L121.61,-15.67L121.39,-15.32L121.7,-14.74L121.63,-14.58L121.77,-14.17L121.91,-14.02L122.21,-13.93L122.29,-14L122.2,-14.15L122.63,-14.32L122.93,-14.19L123.1,-13.75L123.3,-13.84L123.32,-14.06L123.82,-13.84L123.81,-13.72L123.55,-13.65L123.82,-13.27L123.79,-13.11L124.14,-13.04L124.06,-12.57L123.88,-12.69L123.95,-12.92L123.63,-12.91L123.31,-13.04L123.16,-13.44L122.6,-13.91L122.47,-13.89L122.67,-13.4L122.6,-13.19L122.38,-13.52L121.78,-13.94L121.5,-13.84L121.34,-13.65L121.1,-13.68L120.84,-13.88L120.64,-13.8L120.62,-14.19L120.92,-14.49L120.94,-14.65L120.58,-14.88L120.59,-14.48L120.44,-14.45L120.25,-14.79L120.08,-14.85L119.77,-16.26L119.83,-16.33L120.16,-16.05L120.37,-16.11L120.3,-16.65L120.43,-17.38L120.36,-17.64L120.6,-18.51L121.1,-18.62ZM133.47,0.73L133.97,0.74L134.11,0.85L134.07,1L134.26,1.36L134.11,1.72L134.19,2.31L134.46,2.83L134.48,2.58L134.63,2.54L134.7,2.93L134.84,2.91L134.89,3.21L135.09,3.35L135.49,3.35L136.24,2.58L136.39,2.27L137.07,2.11L137.17,2.03L137.12,1.84L137.91,1.48L139.79,2.35L140.62,2.45L140.75,2.61L141.19,2.63L142.55,3.2L143.51,3.43L144.07,3.81L144.48,3.83L145.09,4.35L145.33,4.39L145.77,4.82L145.75,5.4L147.03,5.92L147.42,5.97L147.8,6.32L147.81,6.7L147.12,6.72L146.95,6.83L146.96,6.93L147.26,7.46L148.13,8.1L148.25,8.55L148.45,8.69L148.58,9.05L149.2,9.03L149.26,9.5L150.01,9.69L149.76,9.81L149.87,10.01L150.36,10.19L150.85,10.24L150.64,10.34L150.45,10.31L150.65,10.52L150.32,10.65L150.02,10.58L149.75,10.35L147.77,10.07L147.02,9.39L146.93,9.25L146.96,9.06L146.86,9.09L146.63,8.95L146.03,8.08L144.97,7.8L144.86,7.63L144.51,7.57L144.43,7.68L144.14,7.76L143.65,7.46L143.94,7.94L143.84,7.94L143.83,8.03L143.52,8L143.61,8.2L142.52,8.32L142.35,8.17L142.21,8.2L142.33,8.2L142.47,8.37L142.8,8.35L143.11,8.47L143.38,8.76L143.37,8.96L142.65,9.33L142.23,9.17L141.13,9.22L140,8.2L140.12,7.92L139.93,8.1L139.39,8.19L139.25,7.98L138.93,8.26L138.86,8.15L139.09,7.59L138.75,7.25L139.18,7.19L138.85,7.14L138.6,6.94L138.86,6.86L138.44,6.34L138.3,5.95L138.37,5.84L138.2,5.81L138.34,5.68L138.09,5.71L138.06,5.47L137.28,4.95L137.2,4.99L136.62,4.82L135.98,4.53L135.2,4.45L134.68,4.08L134.71,3.95L134.89,3.94L134.27,3.95L134.15,3.8L133.97,3.82L133.68,3.48L133.7,3.25L133.84,3.05L133.7,3.09L133.65,3.36L133.52,3.41L133.4,3.9L133.25,4.06L132.97,4.09L132.75,3.7L132.87,3.55L132.75,3.29L132.35,2.98L132.01,2.86L131.97,2.79L132.23,2.68L132.72,2.79L133.19,2.44L133.7,2.62L133.75,2.45L133.9,2.39L133.9,2.3L133.79,2.29L133.92,2.1L132.96,2.27L132.31,2.24L132.02,1.99L131.93,1.56L131.29,1.39L131,1.42L131.19,1.17L131.26,0.86L131.8,0.7L132.13,0.45L132.51,0.35L132.86,0.42L133.47,0.73ZM124.89,-1L124.43,-0.47L123.75,-0.31L123.27,-0.33L123,-0.49L121.01,-0.44L120.58,-0.53L120.35,-0.45L120.19,-0.27L120.01,0.2L120.06,0.56L120.24,0.87L120.52,1.04L120.67,1.37L121.15,1.34L121.58,0.83L121.97,0.93L122.28,0.76L122.89,0.76L122.83,0.66L123.17,0.57L123.38,0.65L123.43,0.78L123.38,1L122.9,0.9L122.25,1.56L121.86,1.69L121.65,1.9L121.36,1.88L121.58,2.15L121.77,2.24L122.08,2.75L122.29,2.91L122.4,3.2L122.25,3.62L122.69,4.08L122.85,4.06L122.87,4.39L122.72,4.34L122.72,4.41L122.11,4.54L122.04,4.83L121.59,4.76L121.49,4.58L121.62,4.09L120.89,3.52L121.05,3.17L121.05,2.75L120.88,2.65L120.65,2.67L120.26,2.95L120.44,3.71L120.36,4.09L120.42,4.62L120.28,5.15L120.43,5.59L119.95,5.58L119.72,5.69L119.56,5.61L119.36,5.31L119.59,4.52L119.62,4.03L119.47,3.51L118.99,3.54L118.87,3.4L118.78,2.72L119.09,2.48L119.32,1.93L119.31,1.41L119.51,0.91L119.71,0.68L119.84,0.86L119.72,0.09L119.87,-0.04L119.81,-0.24L119.91,-0.45L120.27,-0.97L120.42,-0.85L120.6,-0.85L120.87,-1.25L121.08,-1.33L121.4,-1.24L121.59,-1.07L122.44,-1.02L122.84,-0.85L123.07,-0.94L123.93,-0.85L124.53,-1.23L124.6,-1.39L124.99,-1.7L125.16,-1.64L125.23,-1.5L124.89,-1ZM107.37,6.01L107.67,6.22L108.33,6.29L108.68,6.79L110.43,6.95L110.83,6.42L110.97,6.44L111.18,6.69L111.54,6.65L112.09,6.89L112.54,6.93L112.65,7.22L112.79,7.3L112.79,7.55L113.01,7.66L113.5,7.72L114.07,7.63L114.41,7.79L114.39,8.41L114.58,8.77L113.25,8.29L112.68,8.41L111.51,8.31L110.61,8.15L110.04,7.89L109.28,7.7L108.74,7.67L108.45,7.8L108.22,7.78L107.28,7.47L106.46,7.37L106.42,7.24L106.52,7.05L105.94,6.86L105.26,6.84L105.27,6.73L105.37,6.66L105.48,6.78L105.66,6.47L105.79,6.46L105.87,6.12L106.08,5.91L106.83,6.1L107.05,5.9L107.37,6.01ZM96.49,-5.23L97.55,-5.21L98.25,-4.41L98.31,-4.09L99.73,-3.18L100.52,-2.19L100.89,-1.95L100.83,-2.24L101.05,-2.26L101.48,-1.69L101.78,-1.62L102.02,-1.44L102.39,-0.84L102.95,-0.66L103.07,-0.49L103.01,-0.42L102.55,-0.22L102.9,-0.28L103.34,-0.51L103.67,-0.29L103.79,-0.05L103.43,0.19L103.41,0.36L103.51,0.47L103.44,0.58L103.72,0.89L104.36,1.04L104.52,1.82L104.85,2.09L104.65,2.43L104.65,2.6L104.97,2.37L105.4,2.38L105.58,2.49L106.04,3.11L105.84,3.61L105.93,3.83L105.83,4.16L105.89,5.01L105.75,5.82L105.35,5.55L105.08,5.75L104.64,5.52L104.68,5.89L104.6,5.9L103.83,5.08L102.54,4.15L102.13,3.6L101.58,3.17L100.89,2.25L100.86,1.93L100.31,0.83L99.67,-0.05L99.16,-0.35L98.6,-1.86L97.7,-2.36L97.59,-2.85L97.39,-2.98L96.97,-3.58L96.44,-3.82L95.43,-4.87L95.21,-5.28L95.28,-5.59L95.74,-5.58L96.13,-5.29L96.49,-5.23ZM116.81,-6.69L116.79,-6.61L116.91,-6.66L117.13,-6.97L117.23,-6.94L117.29,-6.68L117.61,-6.51L117.69,-6.35L117.64,-6L117.5,-5.88L118,-6.05L118.12,-5.86L117.93,-5.79L117.97,-5.71L118.35,-5.81L118.59,-5.59L119.26,-5.37L119.25,-5.2L119.13,-5.1L118.67,-4.96L118.26,-4.99L118.19,-4.83L118.56,-4.5L118.55,-4.38L118.01,-4.25L117.7,-4.34L117.5,-4.13L117.78,-3.69L117.63,-3.64L117.51,-3.73L117.45,-3.63L117.06,-3.62L117.35,-3.43L117.35,-3.19L117.61,-3.06L117.57,-2.93L117.7,-2.89L117.64,-2.83L117.79,-2.75L118.07,-2.32L117.79,-2.03L118.98,-0.98L118.53,-0.81L118.2,-0.87L117.91,-1.1L117.96,-0.89L117.75,-0.73L117.52,-0.24L117.46,0.32L117.56,0.77L116.91,1.22L116.74,1.04L116.75,1.33L116.28,1.78L116.42,1.78L116.42,2.05L116.31,2.14L116.53,2.21L116.55,2.41L116.53,2.51L116.32,2.55L116.33,2.9L116.15,2.98L116.26,3.13L115.96,3.6L114.69,4.17L114.53,3.38L114.45,3.48L114.34,3.44L114.34,3.24L114.24,3.36L114.08,3.28L113.71,3.46L113.61,3.2L113.34,3.25L113.03,2.93L112.97,3.19L112.76,3.32L112.6,3.4L112.28,3.32L111.86,3.55L111.82,3.06L111.69,2.89L111.63,2.98L111.37,2.93L110.93,3.07L110.83,3L110.9,2.91L110.7,3.02L110.57,2.89L110.26,2.97L110.1,2L109.96,1.86L110.04,1.53L109.98,1.27L109.68,0.94L109.29,0.85L109.37,0.64L109.13,0.45L109.26,-0.03L108.94,-0.36L108.91,-0.79L108.96,-1.13L109.13,-1.25L109.01,-1.24L109.08,-1.5L109.38,-1.92L109.63,-2.03L109.86,-1.76L110.35,-1.72L111.22,-1.4L111.03,-1.56L111.27,-2.14L111.21,-2.38L111.44,-2.38L111.51,-2.74L112.99,-3.16L113.92,-4.24L114.01,-4.58L114.42,-4.66L115,-5.02L115.03,-4.9L115.43,-4.97L115.58,-5.19L115.42,-5.41L115.6,-5.6L115.74,-5.53L115.88,-5.61L116.75,-6.98L116.83,-6.95L116.81,-6.69ZM67.77,-76.24L61.36,-75.31L60.72,-75.07L60.28,-75.01L60.5,-74.9L59.75,-74.75L59.67,-74.61L59.24,-74.69L59.04,-74.49L58.53,-74.5L58.67,-74.29L58.62,-74.23L57.77,-74.01L57.87,-73.85L57.76,-73.77L57.31,-73.84L57.54,-73.66L56.96,-73.37L56.63,-73.3L55.01,-73.45L54.3,-73.35L54.13,-73.48L54.2,-73.54L53.76,-73.77L54.64,-73.96L55.34,-74.42L56.14,-74.5L55.58,-74.63L56.5,-74.96L56,-75L55.82,-75.09L55.92,-75.17L56.57,-75.1L56.88,-75.24L56.84,-75.35L57.61,-75.34L57.78,-75.51L58.09,-75.59L58.06,-75.66L60.04,-75.98L60.28,-76.1L60.94,-76.07L61.05,-76.12L61.03,-76.23L61.2,-76.28L62.97,-76.24L64.46,-76.38L65.76,-76.58L66.06,-76.75L66.83,-76.92L67.65,-77.01L68.49,-76.93L68.94,-76.71L68.9,-76.57L68.17,-76.28L67.77,-76.24ZM55.32,-73.31L56.43,-73.2L56.19,-73.03L56.12,-72.81L55.72,-72.77L55.62,-72.6L55.4,-72.55L55.36,-72.41L55.52,-72.22L55.3,-71.94L56.45,-71.11L57.63,-70.73L57.15,-70.59L56.39,-70.73L56.26,-70.71L56.56,-70.59L56.43,-70.56L56.14,-70.66L55.8,-70.62L55.69,-70.69L54.65,-70.74L54.6,-70.68L53.72,-70.81L53.38,-70.87L53.61,-70.91L53.59,-71.05L54.16,-71.13L53.41,-71.34L53.32,-71.4L53.41,-71.53L51.94,-71.47L51.59,-71.57L51.44,-71.78L51.44,-71.93L51.58,-72.07L52.25,-72.13L52.62,-72.3L52.92,-72.67L52.55,-72.77L52.91,-72.9L53.37,-72.92L53.25,-72.97L53.19,-73.1L53.25,-73.18L54.8,-73.39L55.32,-73.31ZM142.76,-54.39L142.98,-54.14L142.92,-53.79L143.32,-52.96L143.32,-52.61L143.17,-52.35L143.19,-51.94L143.32,-51.58L143.46,-51.47L143.82,-50.28L144.34,-49.18L144.69,-48.87L144.71,-48.64L144.54,-48.89L144.05,-49.25L143.73,-49.31L143.1,-49.2L142.57,-48.07L142.56,-47.74L142.94,-47.32L143.22,-46.79L143.49,-46.75L143.58,-46.36L143.43,-46.03L143.28,-46.56L142.58,-46.7L142.41,-46.55L142.08,-45.92L141.96,-46.01L141.83,-46.45L142.04,-47.14L141.96,-47.59L142.18,-48.01L142.14,-48.29L141.87,-48.75L142.14,-49.57L142.07,-50.63L142.21,-51.22L141.72,-51.74L141.81,-51.79L141.67,-51.93L141.66,-52.27L141.86,-52.79L141.82,-53.34L142.14,-53.5L142.32,-53.41L142.53,-53.45L142.58,-53.54L142.51,-53.59L142.68,-53.67L142.71,-53.9L142.33,-54.28L142.76,-54.39ZM143.82,-44.12L144.72,-43.93L145.37,-44.33L145.13,-43.87L145.14,-43.66L145.34,-43.3L145.83,-43.39L145.51,-43.17L144.92,-43L144.2,-42.97L143.97,-42.88L143.43,-42.42L143.24,-42L141.85,-42.58L141.41,-42.55L140.99,-42.34L140.71,-42.56L140.48,-42.56L140.33,-42.29L141.15,-41.81L141,-41.74L140.66,-41.82L140.27,-41.46L140.04,-41.47L140.11,-41.91L139.84,-42.28L139.86,-42.58L140.43,-42.95L140.49,-43.05L140.39,-43.3L141.14,-43.18L141.37,-43.28L141.4,-43.64L141.64,-44.02L141.76,-44.48L141.78,-44.72L141.58,-45.16L141.67,-45.4L141.94,-45.51L142.88,-44.67L143.82,-44.12ZM141.23,-41.37L141.46,-41.4L141.43,-40.72L141.8,-40.29L141.99,-39.79L141.98,-39.43L141.9,-39.11L141.66,-38.97L141.55,-38.76L141.47,-38.4L141.11,-38.34L140.96,-38.15L141,-37.11L140.73,-36.73L140.57,-36.23L140.87,-35.72L140.46,-35.51L140.35,-35.18L139.84,-34.91L139.83,-35.3L140.1,-35.59L139.83,-35.66L139.65,-35.41L139.74,-35.25L139.68,-35.15L139.47,-35.3L139.25,-35.28L139.13,-35.15L139.09,-34.84L138.84,-34.62L138.76,-34.7L138.8,-34.97L138.9,-35.03L138.72,-35.12L138.58,-35.09L138.19,-34.6L137.54,-34.66L137.06,-34.58L137.28,-34.77L136.96,-34.83L136.94,-34.72L136.87,-34.73L136.9,-35.04L136.8,-35.05L136.53,-34.68L136.88,-34.43L136.85,-34.32L136.33,-34.18L135.92,-33.56L135.7,-33.49L135.45,-33.55L135.13,-34.01L135.1,-34.29L135.31,-34.42L135.42,-34.62L135.04,-34.63L134.74,-34.77L134.25,-34.71L133.97,-34.53L133.14,-34.3L132.66,-34.25L132.31,-34.32L132.15,-33.84L131.74,-34.05L130.92,-33.98L130.89,-34.26L131,-34.39L131.35,-34.41L132.92,-35.51L133.98,-35.51L135.17,-35.75L135.27,-35.72L135.23,-35.59L135.33,-35.53L135.68,-35.5L135.9,-35.61L136.1,-35.77L136.01,-35.99L136.07,-36.12L136.7,-36.74L136.72,-37.2L136.84,-37.38L137.32,-37.52L137.34,-37.44L136.9,-37.12L137.02,-36.84L137.25,-36.75L137.51,-36.95L138.32,-37.22L138.63,-37.47L138.89,-37.84L139.36,-38.1L139.52,-38.5L139.8,-38.88L140.06,-39.62L139.99,-39.86L139.74,-39.92L139.91,-40.02L140.01,-40.26L139.97,-40.67L140.28,-40.85L140.39,-41.23L140.63,-41.2L140.75,-40.83L140.94,-40.94L141.12,-40.88L141.23,-40.99L141.24,-41.21L140.8,-41.14L140.8,-41.25L140.94,-41.51L141.23,-41.37ZM134.36,-34.26L134.64,-34.23L134.74,-33.82L134.38,-33.61L134.18,-33.25L133.96,-33.45L133.63,-33.51L133.29,-33.36L132.98,-32.84L132.8,-32.75L132.64,-32.76L132.71,-32.9L132.5,-32.92L132.43,-33.06L132.51,-33.29L132.41,-33.33L132.41,-33.43L132.03,-33.34L132.64,-33.69L132.78,-33.99L132.94,-34.1L133.19,-33.93L133.58,-34.02L133.6,-34.24L133.95,-34.35L134.36,-34.26ZM131.17,-33.6L131.7,-33.6L131.54,-33.27L131.9,-33.25L131.85,-33.12L132,-32.88L131.66,-32.47L131.34,-31.4L131.07,-31.44L131.1,-31.26L130.69,-31.02L130.79,-31.27L130.7,-31.58L130.78,-31.71L130.66,-31.72L130.56,-31.56L130.54,-31.4L130.64,-31.27L130.59,-31.18L130.2,-31.29L130.15,-31.41L130.29,-31.45L130.32,-31.6L130.19,-31.77L130.19,-32.09L130.39,-32.22L130.64,-32.62L130.5,-32.66L130.55,-32.83L130.24,-33.18L130.13,-33.1L130.18,-32.85L130.33,-32.85L130.34,-32.7L130.05,-32.77L129.77,-32.57L129.83,-32.73L129.69,-32.88L129.68,-33.06L129.99,-32.85L129.58,-33.24L129.61,-33.34L129.84,-33.32L129.83,-33.44L130.37,-33.63L130.48,-33.83L130.72,-33.93L130.95,-33.87L131.17,-33.6ZM121.01,-22.62L120.84,-21.93L120.74,-21.96L120.58,-22.36L120.32,-22.55L120.08,-23.09L120.13,-23.65L121.04,-25.03L121.59,-25.28L121.93,-24.97L121.82,-24.82L121.83,-24.53L121.4,-23.17L121.01,-22.62ZM110.89,-19.99L111.01,-19.66L110.82,-19.56L110.64,-19.29L110.45,-18.75L110.07,-18.45L109.52,-18.22L108.7,-18.54L108.67,-19.3L109.28,-19.76L109.18,-19.77L109.26,-19.88L110.17,-20.05L110.59,-19.98L110.65,-20.14L110.89,-19.99ZM79.98,-9.81L80.25,-9.8L80.71,-9.37L81.23,-8.51L81.37,-8.43L81.42,-8.15L81.87,-7.29L81.86,-6.9L81.64,-6.43L80.72,-5.98L80.27,-6.01L80.1,-6.15L79.86,-6.83L79.71,-8.18L79.75,-8.29L79.81,-8.05L79.93,-8.9L80.1,-9.21L80.09,-9.58L80.43,-9.48L80.05,-9.65L79.98,-9.81ZM49.54,12.43L49.94,13.07L50.17,14.04L50.24,14.73L50.44,15.15L50.4,15.63L50.18,15.96L50.02,15.8L49.89,15.46L49.66,15.52L49.84,16.49L49.77,16.82L49.6,16.93L49.45,17.24L49.48,17.9L49.36,18.34L47.91,22.47L47.56,23.87L47.18,24.79L46.73,25.15L46.16,25.23L45.51,25.56L45.12,25.54L44.81,25.33L44.35,25.23L44.04,25L43.67,24.3L43.65,23.74L43.72,23.53L43.57,23.08L43.36,22.79L43.26,22.38L43.29,21.93L43.5,21.36L43.8,21.18L44.4,19.92L44.45,19.43L44.24,19.08L44.23,18.74L44.04,18.29L43.98,17.39L44.42,16.7L44.48,16.22L44.91,16.17L45.22,15.95L45.34,16.04L45.6,15.99L45.7,15.81L46.16,15.74L46.4,15.92L46.33,15.71L46.48,15.51L46.94,15.22L47.03,15.45L47.1,15.43L47.09,15.15L47.35,14.77L47.46,14.71L47.48,15.01L47.77,14.64L47.96,14.67L47.81,14.54L47.77,14.37L48,13.96L47.88,13.81L47.94,13.66L48.04,13.6L48.26,13.72L48.8,13.27L48.92,12.84L48.79,12.47L48.93,12.44L49.21,12.08L49.54,12.43ZM53.11,-38.8L53.05,-39.1L53.11,-38.8ZM50.18,-44.85L50,-44.94L50.02,-45.04L50.11,-45.08L50.04,-44.95L50.18,-44.85ZM-69.17,52.67L-68.79,52.58L-68.57,52.69L-68.24,53.08L-68.43,53.06L-68.49,53.26L-68.16,53.31L-68.01,53.56L-67.29,54.05L-66.24,54.53L-65.18,54.68L-65.47,54.91L-66.51,55.03L-68.22,54.82L-69.08,54.91L-69.49,54.86L-69.72,54.71L-70.03,54.82L-70.28,54.75L-70.5,54.81L-71.9,54.6L-71.93,54.53L-71.8,54.43L-71.61,54.5L-71.36,54.4L-71.08,54.44L-70.8,54.33L-70.7,54.35L-70.7,54.49L-70.31,54.53L-70.86,54.11L-70.87,53.88L-70.64,53.82L-70.7,53.73L-70.53,53.63L-70.38,53.99L-70.63,54.01L-70.24,54.35L-69.74,54.31L-69.36,54.44L-69.31,54.57L-69.05,54.43L-69.99,54.11L-70.15,53.89L-70.09,53.72L-69.35,53.48L-69.39,53.37L-70.21,53.41L-70.46,53.21L-70.39,53.03L-70.13,52.94L-70.38,52.75L-69.94,52.82L-69.5,52.49L-69.17,52.67ZM-81.84,-23.16L-81.26,-23.16L-81.14,-23.05L-80.65,-23.1L-80.36,-22.94L-79.82,-22.89L-79.85,-22.83L-79.28,-22.41L-78.69,-22.37L-77.64,-21.8L-77.5,-21.79L-77.58,-21.89L-77.5,-21.87L-77.14,-21.64L-77.37,-21.61L-77.25,-21.48L-77.1,-21.59L-76.84,-21.4L-76.87,-21.33L-75.72,-21.11L-75.6,-20.99L-75.66,-20.9L-75.6,-20.84L-75.74,-20.81L-75.72,-20.71L-74.88,-20.65L-74.51,-20.38L-74.17,-20.29L-74.15,-20.17L-75.12,-19.9L-75.15,-20.01L-75.29,-19.89L-76.16,-19.99L-77.72,-19.86L-77.55,-20.08L-77.1,-20.41L-77.23,-20.64L-78.12,-20.76L-78.49,-21.05L-78.58,-21.41L-78.73,-21.59L-79.36,-21.59L-80.23,-21.87L-80.49,-22.12L-81.04,-22.07L-81.19,-22.27L-81.28,-22.11L-81.85,-22.21L-82.08,-22.39L-81.71,-22.5L-81.7,-22.59L-81.84,-22.67L-82.74,-22.69L-83.38,-22.22L-83.9,-22.17L-84.03,-21.94L-84.5,-21.78L-84.5,-21.93L-84.84,-21.83L-84.88,-21.89L-84.33,-22.07L-84.36,-22.38L-84.04,-22.67L-83.26,-22.97L-82.1,-23.19L-81.84,-23.16ZM20.9,-80.25L21.55,-80.24L22.29,-80.05L22.44,-80.19L22.45,-80.4L23.01,-80.47L23.32,-80.43L23.11,-80.19L24.4,-80.36L25.84,-80.18L26.86,-80.16L27.15,-80.06L27.2,-79.91L26.01,-79.62L25.64,-79.4L24.75,-79.36L23.95,-79.19L22.9,-79.23L22.7,-79.33L22.87,-79.41L20.86,-79.4L19.9,-79.53L19.75,-79.62L20.49,-79.63L20.78,-79.75L18.94,-79.74L18.32,-79.86L18.26,-79.93L18.86,-80.04L17.92,-80.14L18.78,-80.19L19.34,-80.12L19.54,-80.16L19.18,-80.33L19.75,-80.23L19.81,-80.33L19.61,-80.46L20.36,-80.4L20.9,-80.25ZM16.79,-79.91L17.22,-79.94L17.83,-79.8L17.96,-79.7L17.69,-79.53L17.67,-79.39L18.4,-79.61L18.82,-79.43L18.81,-79.3L18.68,-79.26L19.09,-79.16L19.75,-79.15L19.89,-79.06L20.16,-79.15L20.61,-79.11L20.77,-79.06L20.5,-78.98L21.39,-78.74L19.68,-78.61L19.15,-78.38L18.98,-78.23L19,-78.08L18.44,-78.03L18.36,-77.68L18.23,-77.52L17.62,-77.4L17.15,-77.05L17.25,-76.97L16.98,-76.81L17.06,-76.66L16.7,-76.58L15.55,-76.89L15.12,-77.09L14.37,-77.23L14,-77.51L14.38,-77.58L14.7,-77.53L14.92,-77.69L17.03,-77.8L16.91,-77.9L14.09,-77.77L13.79,-77.85L13.68,-78.03L13.94,-78.09L14.31,-78.01L14.25,-78.07L15.7,-78.23L15.66,-78.3L15.78,-78.33L17,-78.37L17.17,-78.42L16.73,-78.41L16.45,-78.5L16.78,-78.66L15.42,-78.47L15.25,-78.59L15.38,-78.77L15.02,-78.63L14.69,-78.72L14.47,-78.68L14.52,-78.58L14.43,-78.49L14.64,-78.41L14.11,-78.27L13.15,-78.24L11.77,-78.72L11.76,-78.81L11.86,-78.83L11.37,-78.95L12.4,-78.95L11.98,-79.03L11.89,-79.15L12.08,-79.27L11.98,-79.29L11.58,-79.28L11.62,-79.21L11.52,-79.15L11.21,-79.13L10.74,-79.52L10.81,-79.64L10.68,-79.76L11.15,-79.72L11.7,-79.82L12.29,-79.71L12.22,-79.8L12.28,-79.82L13.69,-79.86L13.91,-79.82L13.78,-79.72L12.56,-79.57L13.33,-79.57L13.38,-79.48L13.96,-79.34L14.06,-79.38L14.04,-79.59L14.59,-79.8L14.83,-79.77L15.76,-79.17L16.34,-78.98L15.88,-79.52L15.83,-79.71L16.1,-79.88L16.09,-80.01L16.25,-80.05L16.79,-79.91ZM9.63,-40.88L9.81,-40.5L9.64,-40.27L9.71,-40.02L9.56,-39.17L9.06,-39.24L8.97,-38.96L8.65,-38.93L8.42,-39.21L8.4,-39.48L8.55,-39.84L8.41,-39.92L8.47,-40.29L8.19,-40.65L8.22,-40.91L8.57,-40.85L9.23,-41.26L9.62,-41.02L9.55,-40.93L9.63,-40.88ZM9.48,-42.81L9.55,-42.13L9.19,-41.38L8.81,-41.59L8.89,-41.7L8.72,-41.76L8.74,-41.93L8.62,-41.93L8.7,-42.1L8.59,-42.16L8.68,-42.28L8.57,-42.36L8.81,-42.61L9.31,-42.71L9.36,-43.02L9.46,-42.98L9.48,-42.81ZM15.58,-38.22L15.1,-37.46L15.3,-37.06L15.12,-36.84L15.11,-36.69L14.5,-36.8L14.26,-37.05L13.8,-37.14L12.92,-37.57L12.64,-37.59L12.44,-37.82L12.55,-38.05L12.73,-38.18L12.9,-38.03L13.29,-38.19L13.79,-37.98L15.12,-38.15L15.5,-38.29L15.63,-38.27L15.58,-38.22ZM-52.73,-69.94L-52.05,-69.81L-51.9,-69.6L-52.11,-69.49L-53.58,-69.26L-54.18,-69.4L-53.66,-69.47L-53.83,-69.54L-54.73,-69.61L-54.92,-69.71L-54.79,-69.95L-54.32,-69.94L-54.83,-70.13L-54.71,-70.26L-54.37,-70.32L-53.3,-70.21L-52.73,-69.94ZM-127.2,-50.64L-125.48,-50.32L-124.83,-49.53L-124,-49.22L-123.5,-48.58L-123.42,-48.7L-123.28,-48.46L-123.57,-48.32L-124.87,-48.65L-125.14,-48.8L-124.85,-49.03L-124.81,-49.21L-124.93,-49.01L-125.49,-48.93L-125.83,-49.09L-125.64,-49.19L-125.95,-49.25L-125.94,-49.4L-126.55,-49.42L-126.54,-49.59L-126.13,-49.67L-126.53,-49.72L-126.9,-49.94L-127.11,-49.88L-127.25,-50.14L-127.35,-50.05L-127.47,-50.16L-127.86,-50.13L-127.84,-50.29L-127.96,-50.35L-127.91,-50.45L-127.49,-50.4L-127.47,-50.58L-127.75,-50.61L-127.73,-50.54L-128.06,-50.5L-128.35,-50.7L-128.3,-50.79L-127.92,-50.86L-127.2,-50.64ZM-71.95,-19.72L-71.74,-19.74L-71.56,-19.9L-70.95,-19.91L-70.19,-19.64L-69.96,-19.67L-69.74,-19.3L-69.23,-19.27L-69.61,-19.21L-69.62,-19.12L-68.68,-18.9L-68.38,-18.67L-68.36,-18.54L-68.69,-18.21L-68.93,-18.41L-69.27,-18.44L-69.77,-18.44L-70.48,-18.22L-70.64,-18.34L-71.03,-18.27L-71.44,-17.64L-71.63,-17.77L-71.71,-18.01L-72.06,-18.23L-72.88,-18.15L-73.51,-18.25L-73.75,-18.19L-73.88,-18.04L-74.46,-18.39L-74.39,-18.62L-72.79,-18.43L-72.35,-18.62L-72.81,-19.07L-72.7,-19.44L-73.4,-19.66L-73.4,-19.81L-72.88,-19.93L-71.95,-19.72ZM-49.63,0.23L-49.12,0.16L-48.39,0.3L-48.57,0.89L-48.84,1.23L-48.83,1.39L-49.04,1.51L-49.17,1.41L-49.23,1.6L-49.51,1.51L-49.59,1.71L-49.81,1.79L-50.07,1.7L-50.51,1.79L-50.76,1.24L-50.73,1.13L-50.58,1.1L-50.71,1.08L-50.8,0.91L-50.65,0.27L-50.25,0.12L-49.63,0.23ZM-3.11,-58.52L-3.21,-58.32L-3.99,-57.96L-4.04,-57.85L-3.86,-57.82L-4.13,-57.58L-3.4,-57.71L-2.07,-57.7L-1.78,-57.47L-2.59,-56.56L-3.31,-56.36L-2.89,-56.4L-2.65,-56.32L-2.67,-56.25L-3.36,-56.03L-3.79,-56.1L-3.05,-55.95L-2.6,-56.03L-2.15,-55.9L-1.66,-55.57L-1.23,-54.7L-0.67,-54.5L-0.08,-54.12L-0.21,-54.02L0.12,-53.61L-0.27,-53.74L-0.66,-53.72L-0.29,-53.69L0.27,-53.34L0.36,-53.16L0.05,-52.91L0.28,-52.81L0.56,-52.97L1.06,-52.96L1.66,-52.75L1.75,-52.47L1.59,-52.12L1.23,-51.97L1.27,-51.85L1.19,-51.8L0.75,-51.73L0.9,-51.69L0.89,-51.57L0.42,-51.47L1.41,-51.36L1.4,-51.18L1.04,-51.05L0.96,-50.93L0.21,-50.76L-0.79,-50.77L-1.42,-50.9L-1.33,-50.82L-1.52,-50.75L-2.03,-50.73L-1.96,-50.63L-2.04,-50.6L-3,-50.72L-3.4,-50.63L-3.68,-50.24L-4.19,-50.39L-4.73,-50.29L-5.12,-50.04L-5.62,-50.05L-5.66,-50.13L-4.89,-50.53L-4.58,-50.78L-4.52,-50.98L-4.3,-51.03L-4.19,-51.19L-3.14,-51.21L-2.43,-51.74L-3.29,-51.39L-3.56,-51.41L-3.89,-51.59L-4.23,-51.57L-4.09,-51.66L-4.39,-51.74L-4.9,-51.63L-5.17,-51.74L-5.26,-51.88L-5.18,-51.95L-4.22,-52.28L-3.98,-52.54L-4.08,-52.61L-4.1,-52.92L-4.68,-52.81L-4.27,-53.14L-3.76,-53.31L-3.33,-53.35L-3.1,-53.26L-3.17,-53.39L-3.06,-53.43L-2.92,-53.31L-2.75,-53.31L-3.06,-53.51L-2.93,-53.73L-3.03,-53.77L-3.03,-53.91L-2.9,-53.96L-2.85,-54.14L-3.17,-54.13L-3.59,-54.56L-3.46,-54.77L-3.04,-54.95L-3.55,-54.95L-3.96,-54.78L-4.25,-54.85L-4.52,-54.76L-4.82,-54.85L-4.91,-54.69L-5.03,-54.76L-5.17,-54.99L-5.06,-54.99L-4.68,-55.5L-4.89,-55.7L-4.87,-55.87L-4.58,-55.94L-4.84,-56.05L-4.8,-56.16L-5.23,-55.89L-5.22,-56.07L-5.08,-56.2L-5.41,-56L-5.39,-55.77L-5.56,-55.39L-5.73,-55.33L-5.68,-55.62L-5.5,-55.8L-5.62,-55.81L-5.61,-56.06L-5.19,-56.76L-5.65,-56.53L-6.13,-56.71L-5.73,-56.85L-5.86,-56.9L-5.59,-57.1L-5.56,-57.23L-5.79,-57.38L-5.8,-57.47L-5.58,-57.55L-5.74,-57.67L-5.61,-57.88L-5.16,-57.88L-5.41,-58.07L-5.34,-58.24L-5.01,-58.26L-5.09,-58.38L-5.02,-58.57L-4.43,-58.51L-3.26,-58.65L-3.05,-58.63L-3.11,-58.52ZM-7.18,-55.06L-6.95,-55.18L-6.13,-55.22L-5.72,-54.82L-5.88,-54.64L-5.58,-54.66L-5.47,-54.5L-5.48,-54.44L-5.67,-54.55L-5.66,-54.38L-5.56,-54.37L-5.61,-54.27L-6.35,-53.99L-6.14,-53.58L-6.03,-52.93L-6.22,-52.54L-6.46,-52.35L-6.33,-52.25L-6.89,-52.16L-6.97,-52.25L-7,-52.17L-7.53,-52.1L-8.06,-51.83L-8.41,-51.89L-8.34,-51.79L-8.41,-51.71L-9.3,-51.5L-9.84,-51.48L-9.58,-51.69L-10.12,-51.6L-9.6,-51.87L-10.34,-51.8L-10.38,-51.87L-9.91,-52.12L-10.39,-52.13L-10.36,-52.21L-9.77,-52.25L-9.91,-52.4L-9.63,-52.55L-8.78,-52.68L-8.99,-52.76L-9.18,-52.63L-9.92,-52.57L-9.46,-52.82L-9.39,-52.9L-9.46,-52.95L-9.3,-53.1L-8.93,-53.21L-9.51,-53.24L-9.63,-53.33L-9.88,-53.34L-9.8,-53.39L-10.09,-53.41L-10.12,-53.55L-9.72,-53.6L-9.91,-53.66L-9.9,-53.73L-9.58,-53.81L-9.58,-53.88L-9.91,-53.86L-9.86,-54.1L-10.09,-54.16L-10.06,-54.26L-8.55,-54.24L-8.62,-54.35L-8.23,-54.51L-8.13,-54.64L-8.76,-54.68L-8.38,-54.89L-8.39,-55.02L-8.27,-55.15L-7.67,-55.26L-7.56,-55.12L-7.66,-54.97L-7.48,-55.05L-7.52,-55.25L-7.3,-55.3L-7.31,-55.37L-6.96,-55.24L-7.18,-55.06ZM-179.8,-68.94L-178.87,-68.75L-178.54,-68.59L-178.75,-68.66L-178.69,-68.55L-178.1,-68.42L-178.06,-68.26L-177.8,-68.34L-178.25,-68.54L-177.53,-68.29L-177.59,-68.22L-177.3,-68.22L-175.35,-67.68L-175.23,-67.45L-175.37,-67.36L-175,-67.44L-174.85,-67.35L-174.94,-67.09L-174.77,-66.78L-174.92,-66.62L-174.5,-66.54L-174.39,-66.34L-174.08,-66.47L-174.07,-66.23L-173.77,-66.43L-174.23,-66.63L-174.01,-66.78L-174.09,-66.94L-174.55,-67.09L-173.68,-67.14L-173.16,-67.07L-173.32,-66.95L-173.35,-66.85L-173.26,-66.84L-173.18,-66.86L-173.19,-66.99L-172.52,-66.95L-173.01,-67.06L-171.8,-66.93L-170.51,-66.34L-170.6,-66.25L-170.3,-66.29L-170.19,-66.2L-170.24,-66.17L-169.78,-66.14L-169.73,-66.06L-170.54,-65.87L-170.56,-65.66L-170.67,-65.62L-171.42,-65.81L-171.05,-65.55L-171.17,-65.5L-171.91,-65.5L-172.44,-65.67L-172.78,-65.68L-172.35,-65.5L-172.42,-65.45L-172.23,-65.46L-172.31,-65.28L-172.66,-65.25L-172.29,-65.21L-172.21,-65.05L-173.07,-64.85L-172.8,-64.79L-172.9,-64.63L-172.49,-64.54L-172.38,-64.43L-172.74,-64.41L-172.9,-64.53L-172.92,-64.37L-173.16,-64.28L-173.38,-64.35L-173.33,-64.54L-173.73,-64.36L-174.57,-64.72L-175.44,-64.82L-175.85,-65.01L-175.86,-65.23L-176.09,-65.47L-177.06,-65.61L-177.49,-65.5L-178.41,-65.5L-178.53,-65.59L-178.5,-65.74L-178.94,-66.03L-178.75,-66.01L-178.53,-66.4L-178.87,-66.19L-179.11,-66.23L-179.14,-66.38L-179.34,-66.29L-179.33,-66.16L-179.68,-66.18L-179.79,-65.9L-179.37,-65.64L-179.35,-65.52L-179.7,-65.19L-180,-65.07L-180,-68.98L-179.8,-68.94ZM-15.54,-66.23L-14.6,-66.38L-14.91,-66.28L-15.12,-66.1L-14.7,-66.02L-14.69,-65.9L-14.83,-65.76L-14.39,-65.79L-14.32,-65.68L-14.47,-65.58L-14.17,-65.64L-13.62,-65.52L-13.8,-65.35L-13.64,-65.28L-13.75,-65.19L-13.56,-65.12L-13.6,-65.04L-13.85,-64.99L-13.85,-64.86L-14.04,-64.74L-14.39,-64.75L-14.43,-64.54L-14.63,-64.42L-15.83,-64.18L-16.64,-63.87L-17.82,-63.71L-17.95,-63.54L-18.65,-63.41L-20.2,-63.56L-20.49,-63.69L-20.36,-63.76L-20.41,-63.81L-20.65,-63.74L-21.11,-63.94L-22.65,-63.83L-22.7,-64.08L-22.51,-63.99L-22.19,-64.04L-21.46,-64.38L-22.05,-64.31L-21.9,-64.39L-22,-64.41L-21.95,-64.51L-21.59,-64.63L-22.11,-64.53L-22.32,-64.62L-22.25,-64.73L-22.47,-64.79L-23.35,-64.82L-23.82,-64.74L-24.03,-64.86L-22.79,-65.05L-21.89,-65.05L-21.78,-65.19L-22.04,-65.13L-22.51,-65.2L-21.84,-65.45L-22.9,-65.58L-23.9,-65.41L-24.48,-65.53L-24.25,-65.61L-23.86,-65.54L-24.09,-65.78L-23.62,-65.68L-23.29,-65.75L-23.83,-65.85L-23.52,-65.88L-23.78,-66.02L-23.43,-66.02L-23.6,-66.11L-23.45,-66.18L-23.06,-66.09L-23.02,-65.98L-22.66,-66.03L-22.62,-65.87L-22.44,-65.91L-22.45,-66.07L-22.95,-66.21L-22.48,-66.27L-23.12,-66.34L-22.89,-66.44L-22.43,-66.43L-21.41,-66.03L-21.52,-65.97L-21.31,-65.9L-21.37,-65.74L-21.66,-65.72L-21.36,-65.58L-21.43,-65.47L-21.23,-65.42L-21.13,-65.27L-20.8,-65.64L-20.45,-65.57L-20.36,-65.72L-20.36,-66.03L-20.21,-66.1L-19.49,-65.77L-19.38,-66.08L-18.85,-66.18L-18.14,-65.73L-18.1,-65.83L-18.3,-66.16L-17.91,-66.14L-17.55,-65.96L-17.15,-66.2L-16.84,-66.13L-16.49,-66.2L-16.43,-66.28L-16.54,-66.45L-16.25,-66.52L-15.99,-66.51L-15.54,-66.23ZM5.93,-53.46L5.65,-53.47L5.93,-53.46ZM5.33,-53.39L5.58,-53.44L5.33,-53.39ZM-67.58,55.89L-67.85,55.84L-67.54,55.83L-67.58,55.89ZM-72.8,-18.78L-72.82,-18.71L-73.08,-18.79L-73.28,-18.95L-72.8,-18.78ZM16.65,-43L17.19,-42.92L16.85,-42.9L16.65,-43ZM17.19,-43.13L16.38,-43.21L17.19,-43.13ZM16.79,-43.27L16.42,-43.32L16.6,-43.38L16.83,-43.35L16.89,-43.31L16.79,-43.27ZM-59.79,-43.94L-60.12,-43.95L-59.73,-44L-59.79,-43.94ZM-65.43,-18.11L-65.57,-18.14L-65.37,-18.16L-65.29,-18.13L-65.43,-18.11ZM-64.77,-17.79L-64.58,-17.75L-64.89,-17.7L-64.77,-17.79ZM-77.35,-25.01L-77.56,-25.03L-77.33,-25.08L-77.27,-25.04L-77.35,-25.01ZM-175.16,21.17L-175.08,21.13L-175.16,21.26L-175.36,21.11L-175.16,21.17ZM36.9,-25.38L36.53,-25.6L36.53,-25.69L36.9,-25.38ZM152.89,-76.12L152.56,-76.14L152.8,-76.19L152.89,-76.12ZM67.34,-69.53L67.26,-69.44L67.03,-69.48L67.22,-69.58L67.34,-69.53ZM66.56,-70.54L66.41,-70.62L66.44,-70.77L66.56,-70.54ZM55.48,-80.27L54.98,-80.26L55.48,-80.27ZM-86.42,-16.38L-86.63,-16.3L-86.42,-16.38ZM-45.72,60.52L-45.23,60.64L-45.17,60.73L-45.94,60.62L-45.93,60.53L-45.72,60.52ZM-55.17,61.22L-55.3,61.25L-55.44,61.11L-55.39,61.07L-54.67,61.12L-55.17,61.22ZM-57.98,61.91L-57.74,61.92L-57.64,62.02L-58.15,62.06L-58.18,62.17L-58.47,62.14L-58.56,62.24L-59,62.21L-58.68,62.01L-57.98,61.91ZM-179.97,16.92L-180,16.79L-179.86,16.69L-179.82,16.77L-179.97,16.92ZM154.81,-49.31L154.61,-49.29L154.61,-49.38L154.82,-49.65L154.9,-49.63L154.81,-49.31ZM59.31,-81.31L58.61,-81.34L59.08,-81.4L59.31,-81.31ZM54.42,-80.47L53.81,-80.48L53.9,-80.52L53.88,-80.61L54.41,-80.54L54.42,-80.47ZM61.14,-80.95L60.06,-80.98L61.46,-81.1L61.57,-81.05L61.14,-80.95ZM53.52,-80.19L52.21,-80.26L53.19,-80.41L53.85,-80.27L53.52,-80.19ZM57.08,-80.35L57.12,-80.19L56.99,-80.07L55.72,-80.1L56.01,-80.2L56.02,-80.34L57.08,-80.35ZM59.69,-79.96L58.92,-79.98L59.54,-80.12L59.91,-79.99L59.69,-79.96ZM-75.51,48.76L-75.62,48.76L-75.65,48.59L-75.52,48.33L-75.56,48.07L-75.39,48.02L-75.16,48.43L-75.16,48.62L-75.51,48.76ZM-75.3,50.68L-75.33,50.77L-75.44,50.74L-75.43,50.48L-75.12,50.51L-75.3,50.68ZM-74.39,52.92L-73.65,53.07L-73.14,53.35L-73.57,53.31L-73.87,53.1L-74.27,53.08L-74.71,52.77L-74.39,52.92ZM-69.7,54.92L-68.9,55.02L-68.46,54.96L-68.4,55.04L-68.61,55.16L-68.28,55.26L-68.33,55.33L-68.09,55.48L-68.05,55.64L-68.34,55.51L-68.87,55.45L-68.89,55.24L-69.19,55.17L-69.3,55.17L-69.36,55.3L-69.18,55.47L-69.41,55.44L-69.65,55.32L-69.66,55.23L-69.98,55.15L-69.88,54.88L-69.7,54.92ZM-75.11,48.84L-75.39,49.16L-75.64,49.2L-75.49,49.08L-75.64,48.94L-75.58,48.86L-75.12,48.77L-75.11,48.84ZM53.76,-12.64L54.19,-12.66L54.51,-12.55L54.13,-12.36L53.72,-12.32L53.32,-12.53L53.53,-12.72L53.76,-12.64ZM53.33,-24.26L53.19,-24.29L53.41,-24.41L53.33,-24.26ZM58.72,-20.22L58.64,-20.21L58.64,-20.34L58.88,-20.68L58.95,-20.52L58.72,-20.22ZM56.19,-26.92L55.95,-26.7L55.42,-26.58L55.3,-26.64L55.76,-26.81L55.76,-26.95L56.21,-27L56.28,-26.95L56.19,-26.92ZM53.93,-24.18L53.63,-24.17L53.83,-24.26L53.93,-24.18ZM41.99,-16.72L42.07,-16.71L42.06,-16.8L42.17,-16.71L42.16,-16.57L41.9,-16.68L41.78,-16.85L41.86,-17L41.99,-16.72ZM40.14,-15.7L40.4,-15.58L39.98,-15.61L39.95,-15.7L40.07,-15.68L39.94,-15.74L39.96,-15.89L40.1,-15.84L40.14,-15.7ZM50.61,-25.88L50.57,-25.81L50.47,-25.97L50.47,-26.23L50.59,-26.24L50.61,-25.88ZM48.28,-29.62L48.18,-29.61L48.08,-29.8L48.18,-29.98L48.35,-29.78L48.28,-29.62ZM168.45,16.78L168.18,16.8L168.14,16.64L168.2,16.59L168.45,16.78ZM168.3,16.34L167.93,16.23L168.16,16.08L168.3,16.34ZM168.45,17.54L168.58,17.7L168.52,17.8L168.16,17.71L168.27,17.55L168.45,17.54ZM167.91,15.44L167.67,15.45L168,15.28L167.91,15.44ZM166.75,14.83L166.81,15.16L167.08,14.94L167.2,15.44L167.09,15.58L166.76,15.63L166.63,15.41L166.53,14.76L166.61,14.64L166.75,14.83ZM168.21,15.97L168.16,15.46L168.27,15.89L168.21,15.97ZM168.19,15.33L168.11,14.99L168.19,15.33ZM167.41,16.1L167.84,16.45L167.45,16.55L167.35,16.15L167.15,16.08L167.25,15.88L167.41,16.1ZM159.88,8.53L158.94,8.04L158.46,7.54L158.73,7.6L159.11,7.9L159.43,8.03L159.84,8.33L159.79,8.41L159.88,8.53ZM157.49,7.33L157.44,7.43L157.1,7.32L156.45,6.64L157.03,6.89L157.19,7.16L157.49,7.33ZM121.16,-6.08L121.39,-6L121.29,-5.87L120.88,-5.95L121.04,-6.1L121.16,-6.08ZM-75.11,47.84L-75.26,47.76L-75.2,47.73L-74.93,47.72L-75.11,47.84ZM-73.63,44.82L-73.82,44.65L-73.78,44.56L-73.64,44.61L-73.63,44.82ZM-74.57,48.59L-74.92,48.63L-75.25,48.03L-74.83,47.85L-74.85,48.02L-74.62,48.34L-74.57,48.59ZM-64.55,54.72L-63.82,54.73L-64.64,54.9L-64.76,54.83L-64.55,54.72ZM-61.02,51.79L-60.88,51.79L-60.95,51.95L-61.15,51.84L-61.02,51.79ZM-72.92,53.48L-72.88,53.58L-72.48,53.59L-72.21,53.81L-72.41,54L-72.84,54.13L-72.96,54.07L-72.76,53.86L-73.04,53.83L-73.08,54L-73.21,53.99L-73.3,53.94L-73.31,53.73L-73.85,53.55L-73.69,53.43L-73.45,53.41L-73.1,53.51L-73.05,53.39L-72.92,53.48ZM-67.08,55.15L-67.34,55.29L-67.49,55.18L-67.77,55.26L-68.07,55.22L-68.3,54.98L-67.25,54.98L-67.08,55.15ZM-70.99,54.87L-70.8,54.97L-70.42,54.91L-70.3,55.11L-70.48,55.18L-70.6,55.08L-70.94,55.06L-71.2,54.89L-71.41,54.93L-71.41,54.84L-70.99,54.87ZM-67.29,55.78L-67.56,55.71L-67.37,55.59L-67.29,55.78ZM-74.56,51.28L-74.62,51.4L-75.05,51.4L-75.29,51.63L-75.15,51.28L-74.61,51.21L-74.56,51.28ZM-75.05,50.3L-75.45,50.34L-75.33,50.01L-74.88,50.11L-74.84,50.2L-75.05,50.3ZM-74.82,51.63L-74.78,51.82L-74.54,51.97L-74.69,52.28L-74.85,52.27L-75.11,51.79L-74.82,51.63ZM-73.81,43.83L-73.96,43.92L-74.14,43.87L-73.81,43.83ZM-71.39,54.03L-71.02,54.11L-71,54.25L-71.14,54.37L-71.47,54.23L-71.95,54.3L-72.21,54.05L-72,53.88L-71.39,54.03ZM-74.14,51.93L-74.34,51.9L-74.48,51.73L-74.14,51.93ZM-73.74,44.39L-73.98,44.49L-74,44.59L-73.83,44.84L-73.75,45.27L-74.1,45.33L-74.09,45.2L-74.62,44.65L-74.48,44.58L-74.5,44.47L-74.1,44.39L-74.08,44.19L-73.99,44.14L-73.7,44.27L-73.74,44.39ZM-74.31,45.69L-74.47,45.76L-74.68,45.74L-74.69,45.66L-74.49,45.43L-74.5,45.29L-74.31,45.17L-74.23,45.61L-74.31,45.69ZM-73.57,-45.47L-73.96,-45.44L-73.48,-45.7L-73.57,-45.47ZM-73.7,-45.59L-73.86,-45.57L-73.57,-45.69L-73.7,-45.59ZM-61.91,-47.28L-61.77,-47.26L-62.01,-47.23L-61.92,-47.43L-61.4,-47.64L-61.91,-47.28ZM-71.03,-46.87L-70.83,-47L-71.03,-46.87ZM113.84,7.11L113.13,7.22L112.73,7.07L112.87,6.9L113.97,6.87L114.08,6.99L113.84,7.11ZM158.88,54.71L158.96,54.47L158.88,54.71ZM-157.34,-1.86L-157.18,-1.74L-157.25,-1.73L-157.58,-1.9L-157.44,-1.85L-157.37,-1.95L-157.44,-2.03L-157.32,-1.97L-157.34,-1.86ZM-139.02,9.7L-138.83,9.74L-139.07,9.85L-139.17,9.77L-139.02,9.7ZM-149.32,17.69L-149.18,17.74L-149.18,17.86L-149.34,17.73L-149.58,17.73L-149.64,17.56L-149.38,17.52L-149.32,17.69ZM-172.33,13.47L-172.18,13.68L-172.22,13.8L-172.54,13.79L-172.78,13.52L-172.33,13.47ZM-171.45,14.05L-171.91,14L-172.05,13.86L-171.6,13.88L-171.45,14.05ZM-170.73,14.35L-170.82,14.31L-170.57,14.27L-170.73,14.35ZM134.6,-7.38L134.53,-7.36L134.52,-7.53L134.65,-7.71L134.6,-7.38ZM144.74,-13.26L144.65,-13.43L144.88,-13.61L144.94,-13.57L144.74,-13.26ZM178.49,18.97L177.96,19.12L178.33,18.93L178.49,18.97ZM169.49,19.54L169.44,19.65L169.35,19.62L169.22,19.48L169.25,19.34L169.34,19.33L169.49,19.54ZM169.33,18.94L168.99,18.87L169.02,18.64L169.14,18.63L169.33,18.94ZM168.01,21.43L168.14,21.45L168.12,21.62L167.97,21.64L167.82,21.39L167.99,21.34L168.01,21.43ZM166.55,20.7L166.62,20.42L166.55,20.7ZM167.4,21.16L167.07,21L167.03,20.92L167.19,20.8L167.06,20.72L167.3,20.73L167.4,21.16ZM166.13,10.76L165.9,10.85L165.79,10.78L166.02,10.66L166.16,10.69L166.13,10.76ZM160.58,11.8L160.44,11.81L159.99,11.49L160.58,11.8ZM160.75,8.31L161,8.61L160.94,8.8L161.16,8.96L161.37,9.61L160.77,8.96L160.66,8.62L160.71,8.54L160.59,8.37L160.75,8.31ZM161.72,10.39L162.11,10.45L162.37,10.82L161.91,10.76L161.54,10.57L161.49,10.36L161.29,10.33L161.3,10.2L161.72,10.39ZM161.55,9.63L161.55,9.77L161.41,9.68L161.36,9.35L161.55,9.63ZM160.17,9L160.41,9.14L160.11,9.08L160.17,9ZM157.76,8.24L157.9,8.51L157.82,8.61L157.59,8.45L157.56,8.27L157.3,8.33L157.22,8.26L157.49,7.97L157.6,8.01L157.65,8.22L157.76,8.24ZM158.11,8.68L157.94,8.74L157.91,8.57L158.11,8.54L158.11,8.68ZM157.39,8.71L157.21,8.57L157.38,8.42L157.39,8.71ZM156.69,7.92L156.51,7.71L156.56,7.57L156.81,7.72L156.69,7.92ZM157.17,8.11L157.04,8.12L156.96,8.01L157.02,7.87L157.19,7.94L157.17,8.11ZM175.54,36.28L175.35,36.22L175.39,36.08L175.54,36.28ZM-176.18,43.74L-176.38,43.87L-176.41,43.76L-176.52,43.78L-176.33,44.03L-176.52,44.12L-176.63,44.04L-176.56,43.85L-176.85,43.82L-176.57,43.72L-176.18,43.74ZM166.22,50.76L166.24,50.85L165.89,50.81L166.07,50.68L166.1,50.54L166.27,50.56L166.22,50.76ZM168.14,46.86L168.04,46.93L168.24,46.98L168.24,47.07L167.52,47.26L167.8,46.91L167.78,46.7L167.96,46.69L168.14,46.86ZM132.59,11.3L132.48,11.04L132.58,10.97L132.59,11.3ZM146.28,18.23L146.3,18.48L146.1,18.25L146.28,18.23ZM139.51,16.57L139.16,16.74L139.29,16.47L139.6,16.4L139.7,16.51L139.51,16.57ZM136.71,13.8L136.89,13.79L136.75,14.07L136.95,14.18L136.89,14.29L136.34,14.21L136.43,14.13L136.42,13.86L136.66,13.68L136.71,13.8ZM136.6,11.38L136.52,11.39L136.78,11.01L136.6,11.38ZM136.34,11.6L136.18,11.68L136.27,11.58L136.48,11.47L136.34,11.6ZM130.46,11.68L130.61,11.82L130.04,11.79L130.07,11.68L130.2,11.66L130.15,11.48L130.29,11.34L130.46,11.68ZM130.62,11.38L131.02,11.33L131.27,11.19L131.54,11.44L131.46,11.59L130.95,11.93L130.51,11.62L130.37,11.21L130.62,11.38ZM113.18,26.05L112.96,25.78L112.95,25.53L113.18,26.05ZM147.36,43.4L147.31,43.5L147.1,43.43L147.28,43.28L147.36,43.4ZM143.93,40.12L143.84,39.9L144,39.58L144.09,39.64L144.14,39.95L143.93,40.12ZM148.33,40.31L148.47,40.43L148.4,40.49L148.01,40.38L148.33,40.31ZM148,39.76L148.3,39.99L148.31,40.17L148.11,40.26L147.77,39.87L148,39.76ZM137.6,35.74L137.93,35.73L138.12,35.85L137.67,35.9L137.45,36.07L137.21,35.98L136.76,36.03L136.54,35.89L136.64,35.75L137.33,35.59L137.58,35.62L137.6,35.74ZM153.54,27.44L153.43,27.71L153.44,27.41L153.54,27.44ZM153.44,27.32L153.37,27.14L153.43,27.03L153.44,27.32ZM153.08,25.75L152.98,25.55L153.04,25.19L153.23,25.01L153.14,24.81L153.26,24.73L153.35,25.06L153.08,25.75ZM151.15,23.49L151.24,23.53L151.24,23.78L151.03,23.53L151.15,23.49ZM117.08,-7.88L117.03,-7.81L116.97,-7.89L116.99,-8.05L117.08,-8.07L117.08,-7.88ZM120.1,-12.17L120.23,-12.22L120.31,-12.01L120.01,-12.01L119.89,-12.3L120.1,-12.17ZM120.04,-11.7L119.94,-11.69L119.86,-11.95L120.04,-11.92L120.04,-11.7ZM122.65,-10.47L122.54,-10.42L122.54,-10.61L122.7,-10.74L122.65,-10.47ZM123.37,-9.45L123.39,-9.97L123.71,-10.47L124.04,-11.27L124,-10.4L123.7,-10.13L123.37,-9.45ZM124.59,-9.79L124.12,-9.6L123.94,-9.62L123.82,-9.82L124.17,-10.14L124.34,-10.16L124.58,-10.03L124.59,-9.79ZM120.25,-5.26L119.82,-5.07L120.17,-5.33L120.25,-5.26ZM122.09,-6.43L121.96,-6.42L121.83,-6.66L122.06,-6.74L122.29,-6.64L122.09,-6.43ZM126.06,-9.77L125.99,-9.84L126.07,-10.06L126.17,-9.8L126.06,-9.77ZM125.69,-9.91L125.49,-10.12L125.52,-10.31L125.67,-10.44L125.69,-9.91ZM121.91,-13.54L122.11,-13.46L122,-13.2L121.83,-13.33L121.91,-13.54ZM122.09,-12.35L122.01,-12.11L121.92,-12.33L122,-12.6L122.15,-12.65L122.09,-12.35ZM122.65,-12.31L122.42,-12.46L122.6,-12.49L122.65,-12.31ZM123.28,-12.85L123.37,-12.7L122.96,-13.11L123.28,-12.85ZM123.78,-12.45L123.78,-12.37L123.62,-12.57L123.62,-12.67L123.78,-12.45ZM123.72,-12.29L124.04,-11.97L124.05,-11.75L123.47,-12.22L123.16,-11.93L123.24,-12.58L123.72,-12.29ZM124.35,-13.63L124.18,-13.53L124.04,-13.66L124.22,-14.08L124.42,-13.87L124.35,-13.63ZM122.03,-15.01L121.93,-14.66L121.84,-15.04L122.03,-15.01ZM148.03,5.83L147.78,5.63L147.79,5.49L148.05,5.61L148.03,5.83ZM147.07,1.96L147.44,2.01L147.21,2.18L146.55,2.21L146.66,1.97L147.07,1.96ZM154.65,5.43L154.54,5.11L154.63,5.01L154.73,5.22L154.65,5.43ZM150.44,2.66L150.17,2.66L149.96,2.47L150.23,2.38L150.43,2.47L150.44,2.66ZM151.08,10.02L151.3,9.96L151.23,10.19L150.96,10.09L150.78,9.71L151.08,10.02ZM150.35,9.49L150.11,9.36L150.21,9.21L150.32,9.26L150.35,9.49ZM150.53,9.35L150.79,9.42L150.89,9.67L150.44,9.62L150.51,9.54L150.44,9.36L150.53,9.35ZM151.11,8.73L151,8.52L151.12,8.42L151.11,8.73ZM152.63,8.96L152.95,9.07L152.97,9.21L152.72,9.17L152.52,9.01L152.63,8.96ZM154.28,11.36L154.12,11.43L154.02,11.35L154.28,11.36ZM153.54,11.48L153.76,11.59L153.38,11.56L153.2,11.32L153.54,11.48ZM143.59,8.48L143.32,8.37L143.58,8.39L143.59,8.48ZM143.59,8.63L143.21,8.42L143.59,8.63ZM135.38,0.65L135.89,0.73L136.38,1.09L136.16,1.21L135.92,1.18L135.75,0.82L135.65,0.88L135.38,0.65ZM135.47,1.59L136.89,1.8L136.23,1.89L135.49,1.67L135.47,1.59ZM138.9,8.39L138.56,8.31L138.8,8.17L138.9,8.39ZM133.57,4.25L133.32,4.11L133.57,4.25ZM130.35,1.69L130.42,1.97L130.25,2.05L129.89,1.99L129.74,1.87L130.35,1.69ZM131,1.32L130.78,1.26L130.67,0.96L131.03,0.92L131,1.32ZM130.91,0.78L130.83,0.86L130.4,0.92L130.48,0.83L130.91,0.78ZM130.81,0L131.28,0.15L131.34,0.29L131.26,0.37L130.95,0.34L130.68,0.08L130.64,0.14L130.9,0.42L130.75,0.44L130.69,0.3L130.55,0.37L130.5,0.27L130.24,0.21L130.36,0.07L130.81,0ZM128.45,-2.05L128.3,-2.03L128.22,-2.3L128.33,-2.47L128.6,-2.6L128.69,-2.47L128.62,-2.22L128.45,-2.05ZM127.25,0.5L127.12,0.52L127.13,0.28L127.29,0.28L127.25,0.5ZM127.57,0.32L127.68,0.47L127.6,0.61L127.88,0.81L127.76,0.88L127.62,0.77L127.46,0.81L127.47,0.64L127.3,0.5L127.33,0.34L127.46,0.41L127.57,0.32ZM128.15,1.66L127.56,1.73L127.4,1.59L127.65,1.33L128.15,1.66ZM134.75,5.71L134.71,6.3L134.44,6.33L134.15,6.06L134.3,6.01L134.34,5.83L134.21,5.71L134.34,5.71L134.57,5.43L134.75,5.71ZM134.54,6.44L134.32,6.85L134.2,6.91L134.09,6.83L134.11,6.47L134.19,6.46L134.11,6.19L134.54,6.44ZM132.93,5.9L132.85,5.99L132.94,5.68L133.14,5.32L133.12,5.58L132.93,5.9ZM132.81,5.85L132.68,5.91L132.63,5.61L132.81,5.85ZM128.28,3.67L127.98,3.77L127.92,3.7L128.26,3.51L128.33,3.52L128.28,3.67ZM123.18,4.55L123.2,4.82L123.06,4.75L122.97,5.14L123.19,5.33L122.97,5.41L122.81,5.67L122.65,5.66L122.59,5.49L122.77,5.21L122.85,4.62L123.07,4.39L123.18,4.55ZM122.65,5.27L122.56,5.39L122.28,5.32L122.4,5.07L122.37,4.77L122.7,4.62L122.76,4.93L122.61,5.14L122.65,5.27ZM122.04,5.44L121.81,5.26L121.91,5.07L122.04,5.16L122.04,5.44ZM123.24,4.11L123.08,4.23L122.97,4.03L123.21,4L123.24,4.11ZM126.06,2.45L125.86,2.08L125.92,1.97L126.06,2.45ZM126.02,1.79L126.33,1.82L125.96,1.92L125.43,1.94L125.39,1.84L126.02,1.79ZM124.97,1.71L125.19,1.71L125.31,1.88L124.42,2.01L124.33,1.86L124.42,1.66L124.97,1.71ZM123.21,1.17L123.24,1.39L123.43,1.24L123.55,1.34L123.51,1.45L123.37,1.51L123.27,1.44L123.17,1.62L123.15,1.3L122.89,1.59L122.81,1.43L122.91,1.18L123.21,1.17ZM121.86,0.41L121.88,0.5L121.66,0.53L121.86,0.41ZM126.82,-4.03L126.7,-4.07L126.81,-4.26L126.72,-4.34L126.76,-4.55L126.92,-4.29L126.82,-4.03ZM125.66,-3.44L125.51,-3.46L125.47,-3.73L125.66,-3.44ZM120.53,6.3L120.49,6.46L120.44,6.18L120.48,5.78L120.53,6.3ZM130.86,8.32L131.02,8.09L131.18,8.13L130.86,8.32ZM131.33,8L131.11,8L131.14,7.68L131.64,7.11L131.74,7.2L131.64,7.27L131.62,7.63L131.33,8ZM129.84,7.95L129.71,8.04L129.59,7.92L129.61,7.8L129.81,7.82L129.84,7.95ZM127.82,8.1L128.12,8.17L128.02,8.26L127.82,8.19L127.82,8.1ZM126.8,7.67L126.81,7.74L126.58,7.81L126.47,7.95L126.04,7.89L125.8,7.98L125.98,7.66L126.21,7.71L126.61,7.57L126.8,7.67ZM122.95,10.91L122.83,10.9L122.85,10.76L123.37,10.47L123.42,10.65L122.95,10.91ZM121.88,10.59L121.7,10.56L122,10.45L121.88,10.59ZM124.58,8.14L125.05,8.18L125.13,8.33L124.44,8.44L124.36,8.39L124.39,8.25L124.58,8.14ZM124.29,8.33L124.15,8.53L123.93,8.45L124.24,8.2L124.29,8.33ZM123.92,8.27L123.78,8.3L123.55,8.57L123.23,8.53L123.48,8.32L123.39,8.28L123.78,8.19L123.92,8.27ZM123.32,8.35L123.03,8.4L123.22,8.24L123.34,8.27L123.32,8.35ZM119.46,8.74L119.39,8.74L119.45,8.43L119.56,8.52L119.46,8.74ZM115.38,6.97L115.22,6.95L115.24,6.86L115.52,6.9L115.38,6.97ZM117.92,-4.05L117.74,-4L117.63,-4.12L117.66,-4.25L117.88,-4.19L117.92,-4.05ZM116.3,3.87L116.09,4.05L116.02,3.7L116.12,3.34L116.27,3.25L116.3,3.87ZM109.71,1.18L109.46,1.28L109.48,0.99L109.74,1.04L109.71,1.18ZM108.32,-3.69L108.1,-3.7L108.24,-3.81L108,-3.98L108.25,-4.22L108.39,-3.99L108.32,-3.69ZM101.71,-2.08L101.77,-1.94L101.72,-1.79L101.5,-1.73L101.41,-2.02L101.64,-2.13L101.71,-2.08ZM102.43,-0.99L102.28,-1.08L102.26,-1.4L102.44,-1.23L102.43,-0.99ZM102.49,-1.46L102.5,-1.33L102.08,-1.5L102.02,-1.61L102.49,-1.46ZM103.03,-0.75L102.49,-0.86L102.51,-1.09L103,-0.86L103.03,-0.75ZM103.17,-0.87L102.7,-1.05L102.73,-1.16L103,-1.07L103.17,-0.87ZM104.59,-1.22L104.66,-1.05L104.58,-0.83L104.44,-1.05L104.25,-1.01L104.36,-1.18L104.59,-1.22ZM104.78,0.18L105.01,0.28L104.91,0.32L104.45,0.19L104.54,-0.02L104.78,0.18ZM104.47,0.33L104.59,0.47L104.36,0.66L104.26,0.46L104.47,0.33ZM103.74,0.35L103.46,0.36L103.55,0.23L103.74,0.35ZM108.21,3L108.06,3.23L107.86,3.09L107.61,3.21L107.56,2.92L107.67,2.57L107.84,2.53L108.22,2.7L108.29,2.83L108.21,3ZM97.48,-1.47L97.93,-0.97L97.82,-0.56L97.68,-0.6L97.6,-0.83L97.41,-0.95L97.08,-1.43L97.24,-1.42L97.36,-1.54L97.48,-1.47ZM102.37,5.48L102.11,5.32L102.37,5.37L102.37,5.48ZM100.43,3.18L100.47,3.33L100.35,3.23L100.2,2.99L100.2,2.79L100.45,3L100.43,3.18ZM100.2,2.74L100.01,2.82L99.99,2.53L100.2,2.74ZM99.84,2.34L99.61,2.26L99.57,2.03L99.69,2.06L99.84,2.34ZM99.16,1.78L98.83,1.61L98.6,1.2L98.68,0.97L98.93,0.95L99.27,1.63L99.27,1.74L99.16,1.78ZM98.46,0.53L98.31,0.53L98.43,0.23L98.32,0L98.54,0.26L98.46,0.53ZM96.46,-2.36L95.81,-2.66L95.72,-2.83L95.9,-2.89L96.42,-2.52L96.46,-2.36ZM111.39,-2.42L111.31,-2.44L111.33,-2.77L111.39,-2.42ZM32.01,-46.2L31.56,-46.26L31.51,-46.37L32.01,-46.2ZM22.92,-58.83L22.54,-58.69L22.41,-58.86L22.06,-58.94L22.46,-58.97L22.65,-59.09L22.91,-58.99L23.01,-58.83L22.92,-58.83ZM23.34,-58.55L23.06,-58.61L23.33,-58.65L23.34,-58.55ZM35.82,-65.18L35.86,-65.08L35.78,-64.98L35.53,-65.15L35.82,-65.18ZM42.71,-66.7L42.46,-66.77L42.71,-66.7ZM26.88,-78.65L26.41,-78.78L27.01,-78.7L26.88,-78.65ZM29.05,-78.91L29.65,-78.92L29.31,-78.85L27.89,-78.85L28.51,-78.97L29.05,-78.91ZM50.05,-80.07L49.56,-80.16L50.25,-80.22L50.32,-80.17L50.05,-80.07ZM51.41,-79.94L50.09,-79.98L50.94,-80.09L51.41,-79.94ZM32.53,-80.12L31.48,-80.11L33.63,-80.22L32.53,-80.12ZM57.81,-81.55L58.56,-81.42L57.86,-81.37L58.02,-81.25L57.45,-81.14L56.82,-81.24L55.72,-81.19L55.47,-81.31L56.16,-81.3L57.09,-81.54L57.81,-81.55ZM54.72,-81.12L56.47,-81L57.69,-80.79L56.32,-80.63L54.67,-80.74L54.05,-80.87L54.37,-80.9L54.72,-81.12ZM50.75,-81.05L50.37,-81.12L50.88,-81.15L50.95,-81.11L50.75,-81.05ZM58.62,-81.04L58.93,-80.83L58.64,-80.77L57.94,-80.79L57.21,-81.02L58.05,-81.12L58.62,-81.04ZM63.65,-81.61L62.11,-81.68L63.71,-81.69L63.78,-81.65L63.65,-81.61ZM58.3,-81.72L57.92,-81.71L58.13,-81.83L59.41,-81.83L59.36,-81.76L58.3,-81.72ZM18.74,-80.3L18.16,-80.29L18.29,-80.36L18.74,-80.3ZM11.25,-78.61L11.26,-78.54L11.83,-78.44L12.12,-78.23L11.12,-78.46L10.63,-78.75L10.56,-78.9L10.96,-78.85L11.25,-78.61ZM19.22,-74.39L19.1,-74.35L18.8,-74.49L19.18,-74.52L19.27,-74.46L19.22,-74.39ZM53.14,-71.24L53.21,-71.16L53.05,-71.03L53.12,-70.98L53.02,-70.97L52.74,-71.18L52.24,-71.33L52.78,-71.4L53.14,-71.24ZM74.66,-72.87L74.1,-73.02L74.41,-73.13L74.96,-73.06L74.74,-73.03L74.66,-72.87ZM75.5,-73.46L75.38,-73.48L75.57,-73.54L76.05,-73.55L75.5,-73.46ZM76.76,-73.45L76.08,-73.52L76.76,-73.45ZM77.63,-72.29L76.87,-72.32L77.38,-72.57L77.75,-72.63L78.37,-72.48L77.63,-72.29ZM79.5,-72.72L78.88,-72.75L78.63,-72.85L79.16,-73.09L79.54,-72.92L79.5,-72.72ZM82.71,-74.09L82.33,-74.13L82.71,-74.09ZM83.55,-74.07L82.82,-74.09L83.15,-74.15L83.55,-74.07ZM84.76,-74.46L84.39,-74.45L84.76,-74.46ZM86.65,-74.98L87.12,-74.94L86.93,-74.83L86.39,-74.85L86.26,-74.89L86.33,-74.94L86.65,-74.98ZM82.17,-75.42L82.22,-75.35L81.98,-75.25L81.5,-75.37L81.71,-75.45L81.93,-75.41L81.91,-75.5L82.02,-75.51L82.17,-75.52L82.17,-75.42ZM96.53,-76.28L96.59,-76.22L96.35,-76.21L96.3,-76.12L95.31,-76.21L95.38,-76.29L96.53,-76.28ZM97.59,-76.6L97.31,-76.69L97.59,-76.6ZM96.29,-77.03L95.27,-77.02L96.53,-77.21L96.56,-77.13L96.29,-77.03ZM89.51,-77.19L89.14,-77.23L89.62,-77.31L89.67,-77.25L89.51,-77.19ZM76.25,-79.65L77.59,-79.5L76.65,-79.49L76.15,-79.58L76.05,-79.64L76.25,-79.65ZM80.03,-80.85L78.98,-80.85L79.22,-80.96L79.81,-80.98L80.43,-80.93L80.03,-80.85ZM91.57,-81.14L91.22,-81.06L89.9,-81.17L91.57,-81.14ZM107.7,-78.13L107.48,-78.06L106.42,-78.14L107.7,-78.13ZM106.27,-78.21L106.06,-78.26L106.72,-78.29L106.27,-78.21ZM107.41,-77.24L107.27,-77.29L107.37,-77.35L107.68,-77.27L107.41,-77.24ZM112.48,-76.62L112.66,-76.51L112.53,-76.45L111.97,-76.63L112.48,-76.62ZM120.26,-73.09L119.79,-73.05L119.64,-73.12L119.96,-73.17L120.26,-73.09ZM124.54,-73.85L124.34,-73.93L124.64,-73.9L124.54,-73.85ZM135.95,-75.41L135.45,-75.39L135.7,-75.85L136.17,-75.61L135.98,-75.52L136.02,-75.44L135.95,-75.41ZM149.15,-76.66L148.4,-76.65L149.41,-76.78L149.15,-76.66ZM136.2,-73.91L135.39,-74.25L136.04,-74.09L136.26,-73.98L136.2,-73.91ZM137.96,-71.51L137.71,-71.42L137.06,-71.53L137.82,-71.59L137.96,-71.51ZM160.72,-70.82L160.5,-70.82L160.44,-70.92L160.72,-70.82ZM169.2,-69.58L168.35,-69.66L167.79,-69.84L168.36,-70.02L169.37,-69.88L169.42,-69.78L169.2,-69.58ZM163.64,-58.6L163.47,-58.51L163.43,-58.58L163.73,-58.8L163.76,-59.02L164.57,-59.22L164.62,-58.89L163.64,-58.6ZM168.04,-54.56L167.44,-54.86L168.04,-54.56ZM166.65,-54.84L166.65,-54.69L165.75,-55.29L166.28,-55.31L166.25,-55.17L166.65,-54.84ZM156.41,-50.66L156.17,-50.73L156.46,-50.86L156.41,-50.66ZM155.92,-50.3L155.4,-50.04L155.24,-50.09L155.2,-50.26L155.68,-50.4L155.88,-50.68L156.1,-50.77L156.1,-50.56L155.92,-50.3ZM152,-46.9L151.82,-46.79L151.72,-46.85L152.29,-47.14L152,-46.9ZM149.69,-45.64L149.45,-45.59L149.67,-45.84L150.31,-46.2L150.55,-46.21L149.69,-45.64ZM148.6,-45.32L147.91,-44.99L147.66,-44.98L147.21,-44.55L146.9,-44.4L147.25,-44.86L147.89,-45.23L147.92,-45.38L148.06,-45.26L148.32,-45.28L148.77,-45.53L148.84,-45.36L148.6,-45.32ZM150.59,-59.02L150.47,-59.05L150.71,-59.12L150.59,-59.02ZM137.94,-55.09L138.21,-55.03L137.72,-54.66L137.46,-54.87L137.23,-54.79L137.58,-55.2L137.94,-55.09ZM137.18,-55.1L137.06,-54.93L136.71,-54.96L137.18,-55.1ZM146.71,-43.74L146.61,-43.74L146.62,-43.81L146.9,-43.8L146.71,-43.74ZM146.21,-44.5L146.57,-44.44L146.52,-44.37L145.91,-44.1L145.59,-43.85L145.56,-43.66L145.44,-43.74L145.46,-43.87L146.11,-44.5L146.21,-44.5ZM124.29,-24.52L124.23,-24.36L124.14,-24.35L124.08,-24.44L124.3,-24.59L124.29,-24.52ZM123.89,-24.28L123.68,-24.32L123.77,-24.41L123.93,-24.36L123.89,-24.28ZM128.26,-26.65L127.87,-26.44L127.9,-26.33L127.79,-26.26L127.8,-26.15L127.65,-26.09L127.73,-26.43L127.95,-26.59L127.91,-26.69L128.1,-26.67L128.25,-26.88L128.33,-26.81L128.26,-26.65ZM129.45,-28.21L129.37,-28.13L129.16,-28.25L129.69,-28.52L129.71,-28.43L129.45,-28.21ZM130.62,-30.26L130.45,-30.26L130.39,-30.39L130.5,-30.47L130.64,-30.39L130.62,-30.26ZM130.96,-30.4L130.87,-30.44L131.06,-30.83L130.96,-30.4ZM130.08,-32.23L129.96,-32.24L130.01,-32.52L130.17,-32.54L130.2,-32.34L130.08,-32.23ZM138.34,-37.82L138.23,-37.83L138.32,-37.97L138.25,-38.08L138.5,-38.32L138.45,-38.08L138.58,-38.07L138.34,-37.82ZM134.93,-34.29L134.82,-34.2L134.67,-34.29L135,-34.54L134.93,-34.29ZM129.08,-32.84L129,-32.95L129.11,-33.13L129.18,-32.99L129.08,-32.84ZM129.39,-34.35L129.27,-34.37L129.33,-34.61L129.45,-34.69L129.39,-34.35ZM128.74,-34.8L128.65,-34.74L128.49,-34.87L128.72,-35.01L128.74,-34.8ZM126.33,-33.22L126.17,-33.31L126.34,-33.46L126.9,-33.52L126.87,-33.34L126.33,-33.22ZM126.23,-34.37L126.12,-34.44L126.34,-34.54L126.23,-34.37ZM121.86,-31.49L121.52,-31.55L121.21,-31.81L121.46,-31.76L121.86,-31.49ZM122.3,-29.96L122.02,-30.01L121.97,-30.14L122.28,-30.07L122.3,-29.96ZM110.39,-21.09L110.52,-21.08L110.5,-20.97L110.28,-21L110.39,-21.09ZM104.06,-10.39L104.02,-10.03L103.85,-10.37L104.06,-10.39ZM103.97,-1.33L103.82,-1.27L103.65,-1.33L103.82,-1.45L103.97,-1.33ZM99.85,-6.47L99.92,-6.36L99.74,-6.26L99.65,-6.42L99.85,-6.47ZM98.41,-7.9L98.3,-7.78L98.32,-8.17L98.43,-8.09L98.41,-7.9ZM93.89,-6.83L93.83,-6.75L93.66,-7.02L93.68,-7.18L93.82,-7.24L93.93,-6.97L93.89,-6.83ZM92.5,-10.55L92.37,-10.55L92.35,-10.75L92.51,-10.9L92.57,-10.7L92.5,-10.55ZM92.72,-11.54L92.53,-11.87L92.68,-12.19L92.79,-12.23L92.72,-12.54L92.86,-13.36L93.06,-13.55L93.07,-13.22L92.89,-12.94L92.99,-12.54L92.86,-12.44L92.72,-11.54ZM98.22,-11.48L98.3,-11.78L98.22,-11.48ZM98.55,-11.74L98.53,-11.54L98.43,-11.57L98.38,-11.79L98.55,-11.74ZM98.41,-12.6L98.46,-12.47L98.31,-12.34L98.31,-12.68L98.41,-12.6ZM98.32,-13.1L98.31,-12.93L98.25,-13.1L98.27,-13.2L98.32,-13.1ZM97.58,-16.25L97.48,-16.31L97.54,-16.51L97.58,-16.25ZM94.48,-15.95L94.41,-15.85L94.39,-15.99L94.6,-16.21L94.48,-15.95ZM93.69,-18.68L93.49,-18.87L93.74,-18.87L93.69,-18.68ZM93.01,-19.92L92.91,-20.09L93.01,-19.92ZM93.71,-19.56L93.95,-19.43L93.9,-19.33L93.76,-19.33L93.64,-19.5L93.71,-19.56ZM91.15,-22.18L91.04,-22.11L91.08,-22.52L91.15,-22.18ZM91.56,-22.38L91.41,-22.48L91.46,-22.62L91.56,-22.38ZM90.78,-22.09L90.52,-22.07L90.68,-22.33L90.5,-22.84L90.6,-22.86L90.87,-22.48L90.78,-22.09ZM-8.95,-70.84L-9.1,-70.85L-8.34,-71.14L-7.98,-71.12L-8,-71.04L-8.95,-70.84ZM-155.58,-19.01L-155.68,-18.97L-155.88,-19.07L-155.89,-19.38L-156.05,-19.75L-155.82,-20.01L-155.89,-20.17L-155.83,-20.28L-155.2,-19.99L-154.8,-19.52L-155.58,-19.01ZM-157.21,-21.22L-156.71,-21.16L-156.86,-21.06L-157.29,-21.11L-157.21,-21.22ZM-156.49,-20.93L-156.28,-20.95L-155.99,-20.76L-156.11,-20.64L-156.41,-20.61L-156.48,-20.8L-156.69,-20.9L-156.66,-21.02L-156.49,-20.93ZM-157.8,-21.46L-157.72,-21.46L-157.69,-21.28L-157.98,-21.38L-158.11,-21.32L-158.27,-21.59L-157.96,-21.7L-157.8,-21.46ZM-159.37,-21.93L-159.61,-21.91L-159.79,-22.04L-159.58,-22.22L-159.35,-22.22L-159.37,-21.93ZM179.45,-51.37L178.65,-51.64L179.45,-51.37ZM179.73,-51.91L179.55,-51.89L179.5,-51.98L179.63,-52.03L179.78,-51.97L179.73,-51.91ZM177.42,-51.88L177.25,-51.9L177.67,-52.1L177.59,-51.95L177.42,-51.88ZM173.72,-52.36L173.4,-52.4L173.78,-52.5L173.72,-52.36ZM172.81,-53.01L173.44,-52.85L172.94,-52.75L172.49,-52.94L172.81,-53.01ZM-172.74,-60.46L-172.23,-60.3L-172.64,-60.33L-173.07,-60.49L-172.92,-60.61L-172.74,-60.46ZM-170.16,-57.18L-170.39,-57.2L-170.12,-57.24L-170.16,-57.18ZM-160.68,-55.31L-160.55,-55.38L-160.49,-55.18L-160.8,-55.15L-160.84,-55.34L-160.72,-55.4L-160.68,-55.31ZM-162.55,-54.4L-162.82,-54.49L-162.55,-54.4ZM-159.87,-55.13L-160.23,-54.92L-160.17,-55.12L-159.89,-55.27L-159.87,-55.13ZM-169.69,-52.85L-169.99,-52.83L-169.69,-52.85ZM-165.84,-54.07L-166.04,-54.05L-166.11,-54.14L-165.89,-54.21L-165.69,-54.1L-165.84,-54.07ZM-167.96,-53.35L-169.09,-52.83L-168.69,-53.23L-168.38,-53.28L-168.4,-53.41L-168.29,-53.5L-167.83,-53.51L-167.96,-53.35ZM-166.62,-53.9L-166.5,-53.88L-166.37,-54L-166.23,-53.93L-166.55,-53.73L-166.35,-53.67L-167.52,-53.28L-167.81,-53.32L-167.14,-53.53L-167.02,-53.7L-166.81,-53.65L-166.74,-53.71L-167.11,-53.81L-167.04,-53.94L-166.67,-54.01L-166.62,-53.9ZM-172.46,-52.27L-172.62,-52.27L-172.47,-52.39L-172.31,-52.33L-172.46,-52.27ZM-173.55,-52.14L-173.02,-52.08L-173.84,-52.05L-173.99,-52.12L-173.55,-52.14ZM-174.68,-52.04L-175.3,-52.02L-174.31,-52.22L-174.26,-52.27L-174.44,-52.32L-174.17,-52.42L-174.02,-52.33L-174.18,-52.2L-174.12,-52.14L-174.68,-52.04ZM-176.59,-51.87L-176.44,-51.82L-176.45,-51.74L-176.96,-51.6L-176.7,-51.99L-176.55,-51.94L-176.59,-51.87ZM-177.15,-51.72L-177.67,-51.7L-177.26,-51.8L-177.13,-51.93L-177.06,-51.9L-177.15,-51.72ZM-177.88,-51.65L-178.06,-51.67L-177.99,-51.76L-178.19,-51.88L-177.95,-51.92L-177.64,-51.83L-177.88,-51.65ZM73.71,53.14L73.47,53.18L73.25,52.98L73.84,53.11L73.71,53.14ZM37.86,46.94L37.59,46.91L37.79,46.84L37.86,46.94ZM27.84,-35.93L27.72,-35.96L27.72,-36.17L27.91,-36.35L28.23,-36.43L28.09,-36.07L27.84,-35.93ZM27.18,-35.47L27.1,-35.46L27.07,-35.6L27.22,-35.82L27.18,-35.47ZM26.95,-36.73L27.21,-36.9L27.35,-36.87L26.95,-36.73ZM25.55,-36.97L25.46,-36.93L25.36,-37.07L25.53,-37.2L25.55,-36.97ZM26.82,-37.81L27.06,-37.71L26.84,-37.64L26.58,-37.72L26.82,-37.81ZM26.03,-37.53L26.09,-37.63L26.35,-37.67L26.03,-37.53ZM25.86,-36.79L25.74,-36.79L26,-36.94L26.06,-36.9L25.86,-36.79ZM24.99,-37.76L24.96,-37.69L24.7,-37.96L24.96,-37.9L24.99,-37.76ZM25.26,-37.6L25.16,-37.55L25,-37.68L25.26,-37.6ZM26.09,-38.22L26,-38.16L25.89,-38.24L25.99,-38.35L25.85,-38.57L26.16,-38.54L26.09,-38.22ZM26.41,-39.33L26.6,-39.05L26.49,-39.07L26.55,-38.99L26.47,-38.97L26.11,-39.08L26.27,-39.2L26.07,-39.1L25.84,-39.2L26.17,-39.37L26.41,-39.33ZM25.44,-39.98L25.36,-39.81L25.25,-39.89L25.06,-39.85L25.06,-40L25.44,-39.98ZM24.77,-40.62L24.65,-40.58L24.52,-40.69L24.72,-40.79L24.77,-40.62ZM25.97,-40.14L25.67,-40.14L25.92,-40.24L25.97,-40.14ZM-16.37,-19.71L-16.44,-19.61L-16.48,-19.71L-16.34,-19.87L-16.37,-19.71ZM-17.19,-32.87L-16.69,-32.76L-16.84,-32.65L-17.02,-32.66L-17.23,-32.77L-17.19,-32.87ZM-16.33,-28.38L-16.42,-28.15L-16.66,-28.01L-16.91,-28.34L-16.12,-28.58L-16.33,-28.38ZM-13.72,-28.91L-13.86,-28.87L-13.82,-29.01L-13.46,-29.24L-13.48,-29.01L-13.72,-28.91ZM-14.2,-28.17L-14.33,-28.06L-14.49,-28.1L-14.23,-28.22L-14,-28.71L-13.86,-28.74L-13.93,-28.25L-14.2,-28.17ZM-12.53,-7.44L-12.95,-7.57L-12.62,-7.64L-12.51,-7.58L-12.53,-7.44ZM-15.4,-28.15L-15.44,-27.81L-15.66,-27.76L-15.81,-27.89L-15.68,-28.15L-15.4,-28.15ZM-25.17,-16.95L-25.31,-16.94L-25.34,-17.09L-25.03,-17.18L-24.98,-17.09L-25.17,-16.95ZM-17.89,-27.81L-17.98,-27.65L-18.16,-27.76L-17.89,-27.81ZM-22.92,-16.24L-22.69,-16.17L-22.71,-16.04L-22.96,-16.05L-22.92,-16.24ZM-17.83,-28.49L-18,-28.76L-17.93,-28.84L-17.8,-28.85L-17.73,-28.72L-17.83,-28.49ZM-24.09,-16.62L-24.03,-16.57L-24.24,-16.6L-24.32,-16.49L-24.4,-16.62L-24.09,-16.62ZM-23.44,-15.01L-23.5,-14.92L-23.71,-14.96L-23.79,-15.08L-23.75,-15.33L-23.44,-15.01ZM44.48,12.08L44.5,12.36L44.22,12.17L44.48,12.08ZM45.18,12.98L45.07,12.9L45.09,12.65L45.22,12.75L45.18,12.98ZM43.47,11.9L43.23,11.75L43.3,11.37L43.39,11.41L43.47,11.9ZM39.71,7.98L39.6,7.94L39.91,7.65L39.71,7.98ZM39.5,6.17L39.57,6.39L39.48,6.45L39.18,6.17L39.31,5.72L39.5,6.17ZM57.65,20.48L57.38,20.5L57.32,20.43L57.42,20.18L57.66,19.99L57.79,20.21L57.65,20.48ZM55.8,21.34L55.36,21.27L55.23,21.06L55.31,20.9L55.66,20.91L55.84,21.14L55.8,21.34ZM49.94,16.9L49.82,17.09L49.86,16.93L50.02,16.7L49.94,16.9ZM39.87,4.91L39.85,5.26L39.75,5.44L39.65,5.37L39.67,4.93L39.87,4.91ZM8.74,-3.76L8.91,-3.76L8.95,-3.63L8.7,-3.22L8.47,-3.26L8.46,-3.45L8.58,-3.48L8.74,-3.76ZM6.66,-0.12L6.52,-0.07L6.47,-0.23L6.69,-0.4L6.75,-0.24L6.66,-0.12ZM-44.13,23.14L-44.36,23.17L-44.24,23.07L-44.13,23.14ZM-48.49,27.77L-48.55,27.81L-48.54,27.57L-48.41,27.4L-48.49,27.77ZM10.96,-33.72L10.72,-33.74L10.75,-33.89L11.02,-33.82L10.96,-33.72ZM-4.41,-54.19L-4.61,-54.06L-4.79,-54.07L-4.42,-54.41L-4.34,-54.27L-4.41,-54.19ZM-5.11,-55.45L-5.33,-55.48L-5.37,-55.67L-5.19,-55.69L-5.11,-55.45ZM-5.78,-56.34L-6.31,-56.29L-6.14,-56.49L-6.32,-56.57L-6.1,-56.65L-5.76,-56.49L-5.78,-56.34ZM-6.13,-55.93L-6.09,-55.66L-6.31,-55.61L-6.3,-55.78L-6.49,-55.7L-6.41,-55.85L-6.13,-55.93ZM-5.97,-55.81L-6.07,-55.89L-5.73,-56.12L-5.97,-55.81ZM-1.31,-60.54L-1.16,-60.42L-1.05,-60.44L-1.3,-59.88L-1.29,-60.15L-1.66,-60.28L-1.37,-60.33L-1.57,-60.49L-1.36,-60.61L-1.31,-60.54ZM-4.2,-53.32L-4.08,-53.26L-4.37,-53.13L-4.55,-53.26L-4.57,-53.39L-4.32,-53.42L-4.2,-53.32ZM-2.55,-59.23L-2.66,-59.23L-2.6,-59.29L-2.41,-59.3L-2.55,-59.23ZM-3.06,-59.03L-2.76,-58.96L-3.2,-58.93L-3.35,-58.99L-3.31,-59.13L-3.05,-59.1L-3.06,-59.03ZM-6.62,-61.81L-6.88,-61.9L-6.62,-61.81ZM-6.7,-61.44L-6.93,-61.63L-6.74,-61.57L-6.7,-61.44ZM-7.19,-62.14L-7.07,-62.07L-7.18,-62.04L-7.42,-62.14L-7.19,-62.14ZM-6.63,-62.23L-6.66,-62.09L-6.84,-62.12L-6.73,-61.95L-7.17,-62.29L-6.63,-62.23ZM-2.73,-59.19L-3.05,-59.32L-2.73,-59.19ZM-6.2,-58.36L-6.33,-58.19L-6.55,-58.09L-6.43,-58.02L-6.96,-57.75L-7.08,-57.81L-6.86,-57.92L-7.06,-58L-6.99,-58.05L-7.09,-58.1L-7.03,-58.22L-6.73,-58.19L-6.78,-58.3L-6.24,-58.5L-6.2,-58.36ZM-6.14,-57.5L-6.14,-57.31L-5.67,-57.25L-5.95,-57.05L-6.03,-57.2L-6.32,-57.2L-6.76,-57.44L-6.36,-57.67L-6.14,-57.5ZM-7.21,-57.68L-7.09,-57.63L-7.18,-57.53L-7.51,-57.6L-7.21,-57.68ZM-7.25,-57.12L-7.38,-57.13L-7.41,-57.38L-7.27,-57.37L-7.25,-57.12ZM-9.95,-53.91L-10.27,-53.98L-10,-54L-9.95,-53.91ZM19.99,-60.35L20.24,-60.28L20.19,-60.19L20.04,-60.18L20.03,-60.09L19.75,-60.1L19.69,-60.27L19.85,-60.22L19.82,-60.39L19.99,-60.35ZM21.22,-63.24L21.42,-63.25L21.25,-63.15L21.08,-63.28L21.22,-63.24ZM19.16,-57.92L19.14,-57.86L19.04,-57.91L19.13,-57.98L19.33,-57.96L19.16,-57.92ZM16.53,-56.29L16.43,-56.24L16.4,-56.31L16.41,-56.57L17,-57.32L17.12,-57.32L16.53,-56.29ZM15.09,-55.02L14.68,-55.1L14.71,-55.24L14.77,-55.3L15.13,-55.14L15.09,-55.02ZM13.71,-54.38L13.71,-54.28L13.48,-54.34L13.36,-54.25L13.16,-54.36L13.18,-54.54L13.42,-54.7L13.66,-54.56L13.58,-54.46L13.71,-54.38ZM12.55,-54.97L12.12,-54.91L12.27,-55.06L12.55,-54.97ZM11.36,-54.89L11.74,-54.81L11.77,-54.68L11.46,-54.63L11.04,-54.77L11.06,-54.94L11.36,-54.89ZM10.48,-54.85L10.2,-54.96L10.48,-54.85ZM10.06,-54.89L9.81,-54.91L9.77,-55.06L10.06,-54.89ZM10.73,-54.75L10.62,-54.85L10.95,-55.16L10.73,-54.75ZM11.28,-54.42L11.01,-54.47L11.08,-54.53L11.28,-54.42ZM11.05,-57.25L10.87,-57.26L11.09,-57.33L11.17,-57.32L11.05,-57.25ZM8.31,-54.79L8.41,-55.06L8.38,-54.9L8.63,-54.89L8.31,-54.79ZM-1.07,-50.69L-1.25,-50.59L-1.56,-50.67L-1.31,-50.77L-1.07,-50.69ZM10.4,-42.86L10.42,-42.71L10.11,-42.79L10.4,-42.86ZM4.29,-39.84L3.87,-39.96L3.85,-40.06L4.23,-40.03L4.29,-39.84ZM1.45,-38.92L1.22,-38.9L1.35,-39.08L1.61,-39.09L1.45,-38.92ZM-27.08,-38.64L-27.3,-38.66L-27.39,-38.77L-27.13,-38.79L-27.04,-38.74L-27.08,-38.64ZM-27.78,-38.56L-28.31,-38.74L-27.78,-38.56ZM-28.15,-38.45L-28.45,-38.41L-28.55,-38.52L-28.15,-38.45ZM-25.65,-37.84L-25.18,-37.84L-25.25,-37.74L-25.44,-37.72L-25.73,-37.76L-25.85,-37.89L-25.65,-37.84ZM14.81,-44.98L14.44,-45.1L14.57,-45.22L14.81,-44.98ZM15.19,-44.34L14.74,-44.7L15.19,-44.34ZM15.19,-43.92L14.87,-44.17L15.19,-43.92ZM14.49,-44.66L14.31,-44.9L14.33,-45.16L14.47,-44.97L14.49,-44.66ZM17.61,-42.77L17.34,-42.79L17.61,-42.77ZM20.61,-38.38L20.76,-38.07L20.52,-38.11L20.45,-38.23L20.35,-38.18L20.56,-38.47L20.61,-38.38ZM20.89,-37.81L20.99,-37.71L20.82,-37.66L20.62,-37.86L20.69,-37.93L20.89,-37.81ZM20.69,-38.61L20.55,-38.58L20.69,-38.84L20.69,-38.61ZM20.08,-39.43L19.88,-39.46L19.65,-39.77L19.93,-39.77L19.85,-39.67L19.96,-39.47L20.08,-39.43ZM3.95,-51.74L4.08,-51.65L3.95,-51.63L3.7,-51.71L3.95,-51.74ZM-51.01,-69.55L-51.23,-69.55L-51.35,-69.85L-51.09,-69.92L-50.68,-69.85L-50.91,-69.76L-51.01,-69.55ZM-37.03,-65.53L-37.19,-65.53L-37.22,-65.7L-36.95,-65.66L-37.03,-65.53ZM-53.54,-71.04L-53.96,-71.13L-53.58,-71.3L-53.43,-71.15L-53.54,-71.04ZM-55.02,-72.79L-55.57,-72.56L-56.21,-72.72L-55.21,-72.84L-55.02,-72.79ZM-51.68,-70.86L-52.15,-70.9L-51.97,-70.98L-51.68,-70.86ZM-46.27,-60.78L-46.38,-60.66L-46.79,-60.78L-46.21,-60.94L-46.27,-60.78ZM-122.57,-48.16L-122.38,-47.92L-122.56,-47.99L-122.75,-48.24L-122.63,-48.38L-122.54,-48.32L-122.7,-48.23L-122.57,-48.16ZM-124.15,-49.53L-124.65,-49.76L-124.42,-49.73L-124.15,-49.53ZM-123.37,-48.89L-123.69,-49.1L-123.37,-48.89ZM-126.64,-49.61L-126.94,-49.72L-126.93,-49.84L-126.74,-49.84L-126.64,-49.61ZM-125.18,-50.1L-125.36,-50.31L-125.3,-50.41L-125.09,-50.27L-125.18,-50.1ZM-118.24,-28.94L-118.4,-29.11L-118.37,-29.19L-118.24,-28.94ZM-120.04,-33.92L-120.25,-34.01L-120.07,-34.03L-119.98,-33.97L-120.04,-33.92ZM-119.88,-34.08L-119.55,-34.03L-119.81,-33.97L-119.88,-34.08ZM-118.35,-33.39L-118.3,-33.31L-118.45,-33.32L-118.57,-33.46L-118.35,-33.39ZM-70.51,-41.38L-70.83,-41.36L-70.62,-41.46L-70.51,-41.38ZM-69.98,-41.27L-70.23,-41.29L-70.04,-41.4L-69.98,-41.27ZM-75.33,-37.89L-75.1,-38.3L-75.33,-37.89ZM-75.54,-35.24L-75.69,-35.22L-75.54,-35.28L-75.5,-35.77L-75.46,-35.45L-75.54,-35.24ZM-76.5,-34.64L-76.21,-34.94L-76.5,-34.64ZM-96.76,-28.15L-96.4,-28.38L-96.76,-28.15ZM-97.35,-27.3L-97.06,-27.82L-97.35,-27.3ZM-95.04,-29.15L-94.77,-29.34L-95.04,-29.15ZM-97.17,-26.16L-97.4,-26.82L-97.39,-27.2L-97.17,-26.16ZM-84.91,-29.64L-85.12,-29.63L-84.74,-29.73L-84.91,-29.64ZM-91.79,-29.5L-92.01,-29.61L-91.88,-29.64L-91.75,-29.57L-91.79,-29.5ZM-88.83,-29.81L-88.87,-30.06L-88.83,-29.81ZM-77.66,-24.25L-77.76,-24.16L-77.68,-24.12L-77.62,-24.22L-77.56,-24.14L-77.57,-23.74L-77.77,-23.75L-78,-24.22L-77.66,-24.25ZM-77.67,-21.95L-77.92,-22.09L-77.63,-22.05L-77.67,-21.95ZM-78.63,-22.55L-78.35,-22.54L-78.28,-22.46L-78.55,-22.46L-78.67,-22.51L-78.63,-22.55ZM-77.23,-25.9L-77.4,-26.02L-77.25,-26.16L-77.24,-26.56L-77.51,-26.85L-77.94,-26.9L-77.53,-26.9L-77.07,-26.53L-77.04,-26.33L-77.17,-26.24L-77.23,-25.9ZM-74.06,-22.72L-74.27,-22.71L-74.31,-22.84L-74.06,-22.72ZM-73.03,-21.19L-73.16,-20.98L-73.68,-20.98L-73.68,-21.1L-73.52,-21.19L-73.24,-21.15L-73.06,-21.31L-73.03,-21.19ZM-74.21,-22.21L-73.91,-22.53L-73.95,-22.72L-73.85,-22.73L-73.84,-22.54L-74.21,-22.21ZM-76.65,-25.49L-76.13,-25.14L-76.17,-24.65L-76.32,-24.82L-76.21,-24.82L-76.16,-25.12L-76.37,-25.31L-76.78,-25.43L-76.71,-25.56L-76.65,-25.49ZM-75.66,-23.45L-76.04,-23.6L-76.01,-23.67L-75.66,-23.45ZM-74.84,-22.89L-74.97,-23.07L-75.22,-23.17L-75.13,-23.27L-75.32,-23.67L-74.84,-22.89ZM-75.31,-24.2L-75.5,-24.14L-75.41,-24.27L-75.73,-24.69L-75.31,-24.2ZM-77.74,-24.71L-77.75,-24.46L-78.04,-24.29L-78.15,-24.49L-78.44,-24.63L-78.24,-24.65L-78.3,-24.75L-78.18,-24.92L-78.16,-25.2L-77.98,-25.08L-77.74,-24.71ZM-80.19,-27.28L-80.44,-27.85L-80.19,-27.28ZM-82.56,-21.57L-82.96,-21.44L-83.18,-21.59L-82.97,-21.59L-83.08,-21.79L-82.99,-21.94L-82.71,-21.89L-82.56,-21.57ZM-79.35,-22.66L-79.63,-22.81L-79.35,-22.66ZM-78.49,-26.73L-77.92,-26.69L-78.74,-26.5L-78.99,-26.69L-78.8,-26.58L-78.63,-26.66L-78.6,-26.8L-78.49,-26.73ZM-80.38,-25.14L-80.58,-24.95L-80.35,-25.3L-80.26,-25.35L-80.38,-25.14ZM-87.85,-17.42L-87.93,-17.28L-87.85,-17.42ZM-91.68,-18.68L-91.82,-18.68L-91.54,-18.76L-91.68,-18.68ZM-81.37,-19.35L-81.11,-19.31L-81.4,-19.28L-81.37,-19.35ZM-86.94,-20.3L-87.02,-20.38L-86.98,-20.49L-86.76,-20.58L-86.94,-20.3ZM-60.9,-13.82L-60.95,-13.72L-61.07,-13.87L-60.91,-14.09L-60.9,-13.82ZM-60.83,-14.49L-60.86,-14.43L-61.06,-14.47L-61.01,-14.6L-61.14,-14.65L-61.21,-14.85L-60.93,-14.76L-60.83,-14.49ZM-61.01,-10.13L-61.91,-10.07L-61.5,-10.27L-61.48,-10.6L-61.65,-10.72L-61.08,-10.83L-60.92,-10.84L-61.03,-10.67L-61.01,-10.13ZM-68.21,-12.14L-68.25,-12.03L-68.37,-12.3L-68.21,-12.14ZM-60.76,-11.18L-60.53,-11.33L-60.76,-11.18ZM-59.49,-13.08L-59.61,-13.1L-59.65,-13.3L-59.43,-13.15L-59.49,-13.08ZM-63.85,-11.13L-63.82,-11L-63.92,-10.89L-64.4,-10.98L-64.21,-11.09L-64.03,-11L-63.85,-11.13ZM-61.28,-15.25L-61.38,-15.23L-61.46,-15.63L-61.28,-15.53L-61.28,-15.25ZM-61.33,-16.23L-61.52,-16.23L-61.47,-16.51L-61.17,-16.26L-61.33,-16.23ZM-61.59,-16.01L-61.67,-15.96L-61.76,-16.06L-61.75,-16.36L-61.55,-16.27L-61.59,-16.01ZM-73.04,-22.43L-72.75,-22.33L-73.16,-22.38L-73.04,-22.43ZM-68.75,-12.06L-69,-12.14L-69.16,-12.38L-68.75,-12.06ZM-160.92,-58.58L-161.07,-58.57L-161.13,-58.67L-160.72,-58.8L-160.92,-58.58ZM-153.01,-57.12L-153.3,-57L-153.37,-57.05L-153.29,-57.19L-153.01,-57.12ZM-152.49,-58.49L-152.64,-58.54L-152.37,-58.61L-152.49,-58.49ZM-153.24,-57.85L-153.52,-57.96L-153.24,-57.85ZM-154.68,-56.44L-154.77,-56.42L-154.73,-56.5L-154.44,-56.57L-154.68,-56.44ZM-146.39,-60.45L-146.1,-60.41L-146.6,-60.27L-146.7,-60.4L-146.39,-60.45ZM-144.57,-59.82L-144.24,-60.02L-144.57,-59.82ZM-147.74,-59.81L-147.85,-59.8L-147.81,-59.9L-147.18,-60.36L-146.96,-60.29L-147.74,-59.81ZM-148.02,-60.07L-148.27,-60.05L-148.08,-60.15L-147.91,-60.09L-148.02,-60.07ZM-147.66,-60.45L-147.82,-60.19L-147.89,-60.3L-147.79,-60.46L-147.66,-60.45ZM-132.86,-54.89L-132.62,-54.89L-132.71,-54.68L-132.81,-54.71L-133.43,-55.3L-133.1,-55.21L-132.86,-54.89ZM-133.99,-56.84L-133.74,-56.65L-133.86,-56.58L-133.95,-56.13L-134.19,-56.08L-134.2,-56.41L-134.08,-56.46L-134.29,-56.58L-134.37,-56.84L-134.14,-56.93L-133.99,-56.84ZM-133.31,-55.54L-133.65,-55.27L-133.64,-55.41L-133.74,-55.5L-133.31,-55.54ZM-131.34,-55.08L-131.23,-54.9L-131.45,-54.91L-131.43,-55L-131.59,-55.03L-131.58,-55.25L-131.4,-55.21L-131.34,-55.08ZM-132.75,-56.53L-132.95,-56.57L-132.84,-56.79L-132.57,-56.58L-132.75,-56.53ZM-132.11,-56.11L-132.13,-55.94L-132.37,-55.94L-132.45,-56.06L-132.66,-56.08L-132.7,-56.2L-132.38,-56.5L-132.07,-56.24L-132.11,-56.11ZM-132.78,-56.25L-133.04,-56.36L-132.9,-56.45L-132.64,-56.44L-132.65,-56.31L-132.78,-56.25ZM-134.31,-58.23L-134.66,-58.29L-134.52,-58.33L-134.31,-58.23ZM-128.94,-52.51L-129.15,-52.61L-129.26,-52.8L-128.99,-52.66L-128.94,-52.51ZM-130.24,-53.96L-130.38,-53.84L-130.62,-53.94L-130.66,-53.85L-130.71,-53.92L-130.45,-54.09L-130.24,-53.96ZM-129.85,-53.17L-130.52,-53.54L-130.39,-53.62L-129.94,-53.44L-129.75,-53.24L-129.85,-53.17ZM-127.92,-51.47L-128.09,-51.51L-128.14,-51.65L-128,-51.7L-127.92,-51.47ZM-128.37,-52.4L-128.45,-52.39L-128.44,-52.7L-128.25,-52.78L-128.37,-52.4ZM-139.04,-69.58L-139.29,-69.6L-139.07,-69.65L-138.88,-69.59L-139.04,-69.58ZM-80.13,2.97L-80.27,3L-80.22,2.75L-80.08,2.67L-79.91,2.73L-80.13,2.97ZM-51.83,1.43L-51.94,1.45L-51.68,1.09L-51.68,0.86L-51.55,0.65L-51.25,0.54L-51.16,0.67L-51.28,1.02L-51.83,1.43ZM-44.5,2.94L-44.6,3.04L-44.48,2.72L-44.5,2.94ZM-49.74,-0.27L-49.7,-0.22L-49.92,0.02L-50.34,-0.04L-50.27,-0.23L-49.74,-0.27ZM-50.3,-1.94L-50.46,-1.91L-50.49,-2.13L-50.34,-2.14L-50.3,-1.94ZM-50.65,0.13L-50.93,0.33L-51.04,0.23L-51,0.11L-50.84,0.05L-50.67,0.06L-50.65,0.13ZM-49.44,0.11L-49.83,0.09L-49.5,-0.08L-49.37,-0L-49.44,0.11ZM-50.43,-0.14L-50.44,0.01L-50.62,-0.05L-50.61,-0.2L-50.45,-0.33L-50.37,-0.59L-50.33,-0.26L-50.43,-0.14ZM-50.15,-0.39L-50.26,-0.36L-50.28,-0.52L-50.06,-0.64L-50.15,-0.39ZM-90.33,0.77L-90.54,0.68L-90.53,0.58L-90.27,0.48L-90.19,0.66L-90.33,0.77ZM-89.42,0.91L-89.61,0.89L-89.29,0.69L-89.42,0.91ZM-81.6,-7.33L-81.85,-7.45L-81.81,-7.59L-81.73,-7.62L-81.6,-7.33ZM-91.43,0.46L-91.61,0.44L-91.65,0.28L-91.46,0.26L-91.43,0.46ZM-91.27,-0.03L-90.8,0.75L-90.91,0.94L-91.13,1.02L-91.42,1L-91.5,0.86L-91.12,0.56L-91.37,0.29L-91.43,0.02L-91.6,-0L-91.36,-0.13L-91.27,-0.03ZM-90.57,0.33L-90.87,0.27L-90.78,0.16L-90.57,0.33ZM-113.16,-29.05L-113.5,-29.31L-113.59,-29.57L-113.42,-29.49L-113.37,-29.34L-113.2,-29.3L-113.16,-29.05ZM-115.17,-28.07L-115.35,-28.1L-115.23,-28.37L-115.17,-28.07ZM-111.7,-24.39L-112.01,-24.53L-111.86,-24.54L-111.7,-24.39ZM-112.2,-29.01L-112.28,-28.77L-112.51,-28.85L-112.42,-29.2L-112.29,-29.24L-112.2,-29.01ZM-112.06,-24.55L-112.3,-24.79L-112.16,-25.29L-112.2,-24.84L-112.06,-24.55ZM125.78,-6.96L125.68,-7.07L125.71,-7.19L125.78,-6.96ZM124.61,-11.49L124.48,-11.49L124.36,-11.67L124.51,-11.69L124.61,-11.49ZM122.98,8.55L122.95,8.6L122.9,8.53L123.01,8.45L123.15,8.48L122.98,8.55ZM70.02,-66.5L69.84,-66.49L69.47,-66.72L70.08,-66.7L70.11,-66.57L70.02,-66.5ZM96.85,-76.2L96.74,-76.21L96.84,-76.34L97.05,-76.3L96.85,-76.2ZM100.14,-79.61L99.92,-79.6L100.07,-79.7L100.3,-79.67L100.14,-79.61ZM161.47,-68.9L161.46,-69L161.14,-69.11L161.16,-69.33L161.08,-69.41L161.51,-69.64L161.62,-69.59L161.61,-69.5L161.35,-69.37L161.39,-69.11L161.52,-68.97L161.47,-68.9ZM-86.59,-71.01L-85.64,-71.15L-85.09,-71.15L-85,-71.14L-85.07,-71.08L-84.99,-71.03L-84.82,-71.03L-84.66,-71.51L-84.7,-71.63L-85.34,-71.7L-85.91,-71.99L-85.32,-72.23L-84.28,-72.04L-84.84,-72.31L-84.62,-72.38L-85.34,-72.42L-85.62,-72.6L-85.65,-72.72L-85.57,-72.86L-85.26,-72.95L-84.26,-72.8L-85.45,-73.11L-85.02,-73.34L-84.42,-73.46L-83.78,-73.42L-83.9,-73.53L-83.41,-73.63L-82.66,-73.73L-81.61,-73.7L-81.34,-73.6L-81.15,-73.31L-80.6,-73.12L-80.59,-72.93L-80.28,-72.77L-81.23,-72.31L-80.61,-72.45L-80.94,-72.21L-80.69,-72.1L-80.92,-72.07L-80.93,-71.91L-80.18,-72.21L-79.88,-72.18L-80.11,-72.33L-79.83,-72.45L-79.58,-72.31L-79.32,-72.39L-79,-72.27L-79.01,-72.04L-78.59,-71.88L-78.86,-72.1L-78.7,-72.35L-77.52,-72.18L-78.29,-72.36L-78.48,-72.47L-78.42,-72.57L-77.75,-72.72L-76.89,-72.72L-75.7,-72.57L-75.12,-72.38L-75.05,-72.23L-75.92,-71.72L-75.15,-72.06L-74.27,-72.04L-74.21,-71.94L-74.32,-71.84L-75.2,-71.71L-74.7,-71.68L-75,-71.22L-74.76,-71.34L-74.49,-71.65L-73.87,-71.77L-73.71,-71.72L-74.2,-71.4L-73.71,-71.59L-73.18,-71.28L-73.28,-71.54L-72.9,-71.68L-71.64,-71.52L-71.26,-71.36L-71.22,-71.24L-71.5,-71.11L-71.94,-71.09L-72.63,-70.83L-72.31,-70.83L-72.01,-71.01L-71.74,-71.05L-71.37,-70.98L-70.83,-71.11L-70.67,-71.05L-70.64,-70.9L-70.76,-70.79L-71.89,-70.43L-71.73,-70.4L-71.43,-70.55L-71.28,-70.5L-71.43,-70.13L-70.98,-70.58L-70.56,-70.74L-69.95,-70.85L-69.17,-70.76L-68.45,-70.59L-68.36,-70.48L-70.06,-70.04L-68.78,-70.2L-68.72,-70.15L-69.01,-69.98L-68.74,-69.94L-68.23,-70.11L-68.33,-70.18L-68.06,-70.32L-67.36,-70.03L-67.17,-69.8L-67.26,-69.72L-68.02,-69.77L-69.25,-69.51L-68.51,-69.58L-67.91,-69.46L-67.24,-69.46L-66.69,-69.29L-66.68,-69.19L-66.8,-69.15L-67.94,-69.25L-69.04,-69.1L-68.42,-69.17L-67.83,-69.07L-67.75,-68.93L-67.88,-68.78L-69.32,-68.86L-68.21,-68.7L-67.94,-68.52L-66.74,-68.46L-67.03,-68.33L-66.83,-68.22L-66.92,-68.07L-66.73,-68.13L-66.66,-68.03L-66.63,-68.21L-66.21,-68.28L-66.27,-68.04L-66.53,-67.86L-66.44,-67.83L-65.94,-68.07L-65.97,-67.96L-65.86,-67.92L-65.51,-67.97L-65.54,-67.77L-65.4,-67.67L-65.42,-67.88L-64.92,-68.03L-64.84,-67.99L-65.03,-67.89L-65.02,-67.79L-64.64,-67.84L-63.85,-67.57L-64.08,-67.5L-64.01,-67.35L-64.7,-67.35L-63.84,-67.26L-63.59,-67.38L-63.04,-67.24L-63.26,-67.02L-63.7,-66.82L-62.96,-66.95L-62.38,-66.91L-62.12,-67.05L-61.3,-66.65L-61.53,-66.56L-61.9,-66.68L-62.12,-66.64L-61.58,-66.41L-61.86,-66.31L-62.55,-66.41L-62.41,-66.32L-62.53,-66.23L-61.99,-66.04L-62.62,-66.02L-62.38,-65.83L-62.66,-65.64L-63.17,-65.66L-63.46,-65.85L-63.42,-65.71L-63.65,-65.66L-63.34,-65.62L-63.36,-65.23L-63.61,-64.93L-63.9,-65.11L-64.15,-65.07L-64.35,-65.17L-64.27,-65.4L-64.56,-65.12L-65.11,-65.46L-65.4,-65.76L-64.45,-66.32L-65,-66.08L-65.83,-66L-65.86,-66.09L-65.66,-66.2L-66.06,-66.13L-66.48,-66.28L-66.99,-66.63L-66.97,-66.55L-67.08,-66.53L-67.31,-66.57L-67.19,-66.43L-67.23,-66.31L-67.88,-66.47L-67.7,-66.27L-67.18,-66.03L-67.35,-65.93L-67.83,-65.97L-68.46,-66.25L-68.75,-66.2L-68.22,-66.08L-68.19,-65.87L-67.87,-65.77L-67.94,-65.56L-67.57,-65.64L-67.12,-65.44L-67.34,-65.35L-66.83,-65.07L-66.7,-64.82L-66.64,-65L-66.22,-64.85L-66.3,-64.78L-66.21,-64.72L-65.94,-64.89L-65.43,-64.73L-65.27,-64.63L-65.53,-64.5L-65.07,-64.44L-65.21,-64.3L-65.58,-64.29L-65.35,-64.23L-65.17,-64.03L-64.68,-64.03L-64.8,-63.92L-64.58,-63.9L-64.41,-63.71L-64.56,-63.68L-64.51,-63.26L-64.66,-63.25L-64.93,-63.6L-65.19,-63.76L-65,-63.33L-65.07,-63.26L-64.67,-62.92L-65.16,-62.93L-65.05,-62.7L-65.11,-62.63L-66.22,-63.11L-66.23,-62.99L-66.41,-63.03L-66.65,-63.26L-66.7,-63.07L-67.02,-63.32L-67.26,-63.34L-67.89,-63.73L-67.76,-63.42L-68.49,-63.73L-68.91,-63.7L-68.14,-63.17L-67.68,-63.09L-67.74,-63.01L-66.64,-62.6L-66.28,-62.3L-65.98,-62.21L-66.13,-62.1L-66.06,-61.91L-66.32,-61.87L-67.44,-62.15L-68.63,-62.28L-69.13,-62.42L-69.6,-62.77L-70.24,-62.76L-71.11,-63L-70.95,-63.12L-71.35,-63.07L-71.99,-63.42L-71.61,-63.44L-71.38,-63.58L-71.84,-63.72L-72.29,-63.73L-72.17,-63.89L-72.5,-63.82L-72.68,-64.02L-73.45,-64.4L-73.27,-64.58L-73.91,-64.58L-74.06,-64.42L-74.13,-64.61L-74.46,-64.64L-74.68,-64.83L-74.92,-64.77L-74.64,-64.56L-74.69,-64.5L-75.72,-64.52L-75.77,-64.39L-76.86,-64.24L-77.76,-64.36L-78.05,-64.5L-78.2,-64.66L-78.1,-64.94L-77.36,-65.2L-77.46,-65.36L-77.33,-65.45L-75.83,-65.23L-75.52,-65.06L-75.59,-64.91L-75.45,-64.84L-75.36,-65.01L-75.8,-65.3L-75.17,-65.28L-73.99,-65.52L-73.55,-65.49L-73.75,-65.77L-74.28,-66.01L-74.42,-66.17L-73.03,-66.73L-72.79,-67.03L-72.22,-67.25L-72.73,-67.81L-73.33,-68.27L-73.28,-68.36L-73.64,-68.29L-73.82,-68.36L-73.82,-68.69L-74.12,-68.7L-73.99,-68.55L-74.27,-68.54L-74.7,-68.81L-74.89,-68.81L-74.74,-68.91L-74.95,-68.96L-74.72,-69.05L-76.59,-68.7L-76.56,-69.01L-75.95,-69.03L-75.65,-69.21L-76.46,-69.47L-76.52,-69.59L-76.23,-69.66L-76.51,-69.68L-76.74,-69.57L-77.09,-69.64L-76.86,-69.78L-77.59,-69.85L-77.77,-70.24L-78.28,-70.23L-79.07,-70.6L-79.41,-70.4L-78.93,-70.29L-78.77,-70.1L-78.82,-70.01L-79.52,-69.89L-81.56,-70.11L-80.92,-69.85L-80.84,-69.77L-80.92,-69.73L-81.56,-69.94L-82.29,-69.84L-83.15,-70.01L-83.86,-69.96L-85.43,-70.11L-85.78,-70.04L-86.32,-70.15L-86.5,-70.35L-86.4,-70.47L-87.84,-70.25L-88.85,-70.52L-89.21,-70.76L-89.46,-71.06L-87.84,-70.94L-87.14,-71.01L-87.87,-71.21L-89.08,-71.29L-89.85,-71.49L-90.03,-71.95L-89.66,-72.18L-89.86,-72.25L-89.86,-72.41L-89.36,-72.8L-89.23,-73.11L-88.71,-73.4L-87.72,-73.72L-86.41,-73.85L-85.01,-73.78L-84.97,-73.69L-86.09,-73.26L-86.67,-72.76L-86.32,-72.46L-86.34,-72.12L-86.22,-71.9L-85.02,-71.35L-86.59,-71.01ZM-69.49,-83.02L-66.42,-82.93L-68.47,-82.65L-65.73,-82.84L-65.3,-82.8L-64.98,-82.9L-64.5,-82.78L-63.64,-82.81L-63.47,-82.77L-63.64,-82.71L-63.09,-82.57L-63.25,-82.45L-61.7,-82.49L-61.3,-82.4L-61.21,-82.34L-61.27,-82.28L-62.18,-82.04L-63.59,-81.85L-66.63,-81.62L-66.91,-81.49L-68.69,-81.29L-65.74,-81.49L-64.83,-81.44L-68.63,-80.68L-69.55,-80.38L-70.14,-80.4L-70.71,-80.54L-70.21,-80.28L-70.26,-80.23L-72.06,-80.12L-70.57,-80.09L-71.36,-79.91L-71.11,-79.85L-71.39,-79.76L-72.44,-79.69L-74.39,-79.87L-74.66,-79.84L-74.54,-79.82L-73.47,-79.76L-73.2,-79.6L-73.36,-79.5L-75.5,-79.41L-76.9,-79.51L-75.6,-79.24L-74.48,-79.23L-74.53,-79.05L-78.58,-79.08L-77.88,-78.94L-76.26,-79.01L-74.43,-78.72L-74.88,-78.54L-76.42,-78.51L-75.19,-78.33L-75.97,-77.99L-78.01,-77.95L-78.08,-77.52L-78.49,-77.37L-80.57,-77.31L-81.66,-77.53L-81.28,-77.37L-82.06,-77.3L-81.84,-77.21L-81.12,-77.27L-80.22,-77.15L-79.5,-77.2L-79.34,-77.16L-79.32,-76.98L-79.22,-76.94L-78.79,-76.88L-78.29,-76.98L-78,-76.85L-77.98,-76.75L-78.28,-76.57L-80.69,-76.18L-81,-76.21L-80.83,-76.37L-80.97,-76.47L-81.72,-76.49L-82.53,-76.72L-82.26,-76.57L-82.23,-76.47L-83.89,-76.45L-84.22,-76.68L-84.28,-76.36L-85.14,-76.3L-86.12,-76.43L-86.45,-76.58L-86.68,-76.38L-87.35,-76.45L-87.49,-76.59L-87.5,-76.39L-88.4,-76.41L-88.5,-76.77L-88.61,-76.65L-88.55,-76.42L-89.57,-76.49L-89.5,-76.83L-88.4,-77.1L-86.81,-77.18L-87.59,-77.39L-87.94,-77.6L-88.09,-77.72L-87.76,-77.84L-87.02,-77.89L-86.39,-77.81L-85.59,-77.46L-84.74,-77.36L-83.61,-77.44L-82.66,-77.89L-82.6,-77.99L-82.7,-77.96L-83.78,-77.53L-84.86,-77.5L-85.29,-77.56L-85.29,-77.76L-85.55,-77.93L-84.62,-78.2L-84.22,-78.18L-84.91,-78.24L-84.78,-78.53L-85.02,-78.31L-85.59,-78.11L-86.22,-78.08L-85.92,-78.34L-86.91,-78.13L-87.55,-78.18L-87.49,-78.42L-86.81,-78.77L-85,-78.91L-83.27,-78.77L-81.75,-78.98L-82.44,-78.9L-84.41,-79L-84.57,-79.07L-84.38,-79.12L-83.58,-79.05L-85.27,-79.66L-86.03,-79.72L-86.42,-79.85L-86.61,-80.12L-86.5,-80.26L-86.31,-80.32L-83.72,-80.23L-81.69,-79.69L-80.48,-79.61L-80.12,-79.67L-81.01,-79.69L-82.99,-80.32L-76.86,-80.86L-78.72,-80.95L-78.29,-81.17L-76.89,-81.43L-79.2,-81.12L-79.76,-80.84L-81.01,-80.65L-82.88,-80.58L-82.22,-80.77L-83.4,-80.71L-84.22,-80.54L-85.15,-80.52L-86.53,-80.6L-86.6,-80.66L-86.44,-80.73L-85.25,-80.99L-83.29,-81.15L-85.78,-81.04L-87.33,-80.67L-87.71,-80.66L-89.06,-80.83L-89.26,-80.91L-89.17,-80.94L-86.48,-81.04L-84.94,-81.29L-87.28,-81.08L-89.62,-81.03L-89.95,-81.17L-89.21,-81.25L-89.67,-81.33L-88.62,-81.5L-87.6,-81.53L-88.48,-81.56L-90.3,-81.4L-90.55,-81.46L-89.82,-81.63L-91.29,-81.57L-91.68,-81.64L-90.94,-81.83L-88.06,-82.1L-87.02,-81.96L-86.63,-82.05L-85.04,-81.98L-86.62,-82.22L-84.9,-82.45L-83.59,-82.33L-82.63,-82.08L-82.33,-82.09L-82.75,-82.2L-82.54,-82.25L-79.42,-81.85L-82.45,-82.4L-81.68,-82.52L-82.12,-82.63L-80.86,-82.57L-81.18,-82.74L-81.01,-82.78L-78.75,-82.68L-79.83,-82.82L-80.15,-82.91L-79.89,-82.94L-77.48,-82.88L-76.01,-82.54L-75.64,-82.64L-77.12,-83.01L-74.41,-83.01L-72.66,-82.72L-73.44,-82.9L-73.33,-83L-72.81,-83.08L-71.98,-83.1L-70.94,-82.9L-71.42,-83.02L-71.08,-83.08L-69.97,-83.12L-69.49,-83.02ZM-94.31,-71.76L-93.81,-71.77L-93.76,-71.64L-93.03,-71.34L-92.88,-71.07L-92.98,-70.85L-92.36,-70.63L-92.05,-70.3L-91.76,-70.33L-91.56,-70.18L-91.86,-70.13L-92.32,-70.24L-92.51,-70.1L-91.98,-70.04L-92.89,-69.67L-92.31,-69.67L-91.91,-69.53L-91.2,-69.64L-91.44,-69.53L-90.42,-69.46L-90.68,-69.43L-90.89,-69.27L-91.24,-69.29L-90.74,-69.11L-90.48,-68.88L-90.57,-68.47L-90.25,-68.27L-89.9,-68.49L-89.67,-69.01L-89.28,-69.26L-89.06,-69.27L-88.04,-68.81L-87.83,-68.3L-88.35,-68.29L-88.31,-67.95L-88.2,-67.77L-87.5,-67.36L-87.36,-67.18L-86.56,-67.48L-86.4,-67.8L-85.95,-68.07L-85.69,-68.67L-85.49,-68.77L-84.87,-68.77L-85.11,-68.84L-84.86,-69.07L-85.39,-69.23L-85.51,-69.85L-84.32,-69.84L-83.67,-69.7L-82.37,-69.64L-82.75,-69.49L-82.31,-69.41L-82.23,-69.25L-81.38,-69.19L-81.33,-69.12L-81.96,-68.88L-81.38,-68.85L-81.25,-68.74L-81.28,-68.66L-81.91,-68.46L-82.55,-68.45L-82.22,-68.15L-82.01,-68.19L-82.06,-67.93L-81.29,-67.5L-81.47,-67.07L-81.93,-66.97L-82.26,-66.74L-83.41,-66.37L-83.59,-66.39L-84,-66.73L-84.32,-66.78L-84.27,-66.84L-84.54,-66.97L-84.85,-67.03L-85.11,-66.91L-84.74,-66.93L-84.22,-66.68L-83.83,-66.29L-83.87,-66.21L-84.29,-66.29L-84.48,-66.18L-84.63,-66.21L-85.6,-66.57L-86.71,-66.52L-86.69,-66.36L-85.96,-66.12L-87.08,-65.44L-87.45,-65.34L-87.97,-65.35L-88.74,-65.68L-89.75,-65.94L-89.94,-65.93L-89.89,-65.87L-91.41,-65.96L-91.04,-65.83L-90.98,-65.92L-89.92,-65.78L-88.97,-65.35L-87.03,-65.2L-87.03,-65.06L-87.28,-64.83L-88.11,-64.18L-88.82,-63.99L-89.2,-64.11L-89.13,-63.97L-89.62,-64.03L-89.81,-64.18L-90.04,-64.14L-89.86,-63.96L-90.17,-63.98L-90.01,-63.8L-90.15,-63.69L-90.81,-63.58L-91.98,-63.82L-92.34,-63.79L-93.7,-64.15L-93.6,-64.04L-93.66,-63.94L-93.56,-63.87L-93.27,-63.84L-93.38,-63.95L-92.16,-63.69L-92.47,-63.56L-91.84,-63.7L-90.71,-63.3L-90.78,-62.97L-91.45,-62.8L-92.36,-62.82L-92.31,-62.71L-91.94,-62.59L-92.55,-62.55L-92.77,-62.38L-92.53,-62.17L-93.21,-62.36L-92.91,-62.22L-93.07,-62.15L-93.07,-62.06L-93.35,-62.03L-93.27,-61.96L-93.33,-61.93L-93.58,-61.94L-93.31,-61.77L-93.91,-61.48L-93.89,-61.34L-94.08,-61.3L-94.07,-61.14L-94.51,-60.6L-94.76,-60.5L-94.65,-60.42L-94.79,-59.95L-94.79,-59.27L-94.96,-59.07L-94.29,-58.72L-94.33,-58.3L-94.12,-58.74L-93.18,-58.73L-92.43,-57.32L-92.8,-56.92L-91.11,-57.24L-90.59,-57.22L-88.83,-56.81L-88.08,-56.47L-87.48,-56.02L-85.68,-55.6L-85.22,-55.35L-85.37,-55.08L-85.06,-55.29L-83.91,-55.31L-82.99,-55.23L-82.39,-55.07L-82.22,-54.81L-82.42,-54.24L-82.14,-53.82L-82.16,-53.26L-82.29,-53.03L-81.6,-52.43L-81.61,-52.32L-81.83,-52.22L-81.47,-52.2L-80.66,-51.76L-80.44,-51.39L-80.85,-51.12L-80.48,-51.31L-80.1,-51.28L-79.84,-51.17L-79.35,-50.76L-79.71,-51.12L-79.69,-51.35L-79.5,-51.57L-79.3,-51.62L-79.04,-51.46L-78.9,-51.2L-78.73,-51.5L-78.98,-51.77L-78.45,-52.26L-78.74,-52.66L-78.72,-52.86L-78.9,-53.04L-79.1,-53.66L-79.04,-53.82L-78.95,-53.83L-79.08,-53.93L-79,-54L-79.24,-54.1L-79.15,-54.17L-79.36,-54.26L-79.71,-54.67L-77.78,-55.29L-76.76,-56L-76.53,-56.5L-76.57,-57.18L-76.89,-57.76L-77.55,-58.24L-78.51,-58.65L-78.43,-58.9L-77.76,-59.38L-77.86,-59.48L-77.73,-59.68L-77.35,-59.58L-77.49,-59.68L-77.33,-59.8L-77.37,-59.93L-77.29,-60.02L-77.59,-60.09L-77.45,-60.15L-77.68,-60.43L-77.5,-60.54L-77.79,-60.64L-77.6,-60.83L-78.18,-60.82L-77.77,-61.16L-77.74,-61.44L-77.51,-61.56L-78.02,-61.83L-78.13,-62.28L-77.37,-62.57L-75.82,-62.32L-75.68,-62.25L-75.79,-62.18L-75.34,-62.31L-74.63,-62.12L-74.65,-62.21L-73.71,-62.47L-72.88,-62.13L-72.69,-62.12L-72.63,-62.03L-72.77,-61.84L-72.51,-61.92L-72.23,-61.83L-72.04,-61.68L-72.22,-61.59L-71.87,-61.69L-71.64,-61.62L-71.85,-61.44L-71.65,-61.41L-71.74,-61.34L-71.42,-61.16L-70.28,-61.07L-69.99,-60.86L-69.71,-60.91L-69.62,-61.05L-69.47,-61.01L-69.4,-60.85L-69.64,-60.69L-69.75,-60.49L-69.63,-60.2L-69.67,-60.08L-70.65,-60.03L-69.73,-59.92L-69.58,-59.68L-69.68,-59.34L-69.34,-59.3L-69.53,-58.87L-69.65,-58.82L-69.78,-58.96L-70.15,-58.76L-69.79,-58.69L-69.27,-58.88L-68.7,-58.9L-68.38,-58.74L-68.23,-58.48L-68.36,-58.16L-69.04,-57.9L-68.41,-58.05L-68.02,-58.49L-67.89,-58.3L-68.06,-58.14L-67.76,-58.4L-67.68,-57.99L-67.57,-58.21L-66.72,-58.49L-66.36,-58.79L-66.09,-58.66L-66,-58.43L-65.92,-58.57L-66.04,-58.82L-65.85,-58.85L-65.92,-58.91L-65.72,-59.02L-65.38,-59.06L-65.7,-59.21L-65.51,-59.35L-65.41,-59.31L-65.48,-59.47L-65.04,-59.39L-65.41,-59.54L-65.49,-59.65L-65.43,-59.78L-65.03,-59.77L-65.17,-59.91L-64.82,-60.33L-64.5,-60.27L-64.42,-60.17L-64.77,-60.01L-64.28,-60.06L-64.18,-59.97L-64.23,-59.74L-64.06,-59.82L-63.75,-59.51L-63.95,-59.38L-63.78,-59.28L-63.54,-59.33L-63.42,-59.19L-63.97,-59.05L-63.25,-59.07L-63.28,-58.87L-63.05,-58.88L-62.87,-58.67L-63.54,-58.33L-63.21,-58.47L-62.59,-58.47L-62.81,-58.2L-63.26,-58.01L-62.49,-58.15L-62.31,-57.97L-61.96,-57.91L-61.9,-57.86L-61.99,-57.77L-61.97,-57.61L-62.5,-57.49L-61.92,-57.42L-61.85,-57.37L-61.98,-57.25L-61.33,-57.01L-61.37,-56.68L-62.5,-56.8L-61.74,-56.53L-61.94,-56.42L-61.43,-56.36L-61.71,-56.23L-61.36,-56.22L-61.3,-56.05L-61.45,-56L-61.09,-55.87L-60.74,-55.94L-60.56,-55.73L-60.34,-55.78L-60.41,-55.65L-60.19,-55.48L-60.62,-55.06L-59.76,-55.31L-59.69,-55.2L-59.44,-55.18L-59.84,-54.81L-59.26,-55.2L-59,-55.15L-58.78,-54.84L-58.4,-54.77L-57.96,-54.88L-57.83,-54.72L-57.4,-54.59L-57.7,-54.39L-58.44,-54.23L-58.63,-54.05L-59.82,-53.83L-60.14,-53.6L-60.4,-53.65L-60.1,-53.49L-60.29,-53.39L-60.33,-53.27L-58.65,-53.98L-57.94,-54.09L-58.32,-54.11L-58.31,-54.2L-57.42,-54.16L-57.13,-53.79L-57.52,-53.61L-57.33,-53.47L-56.84,-53.74L-56.52,-53.77L-55.97,-53.47L-55.8,-53.21L-55.89,-53L-55.8,-52.64L-56.32,-52.54L-55.75,-52.47L-55.78,-52.36L-56.01,-52.39L-55.67,-52.19L-56.98,-51.46L-57.46,-51.47L-58.51,-51.3L-59.17,-50.78L-60.08,-50.25L-60.81,-50.25L-61.72,-50.1L-61.92,-50.23L-62.72,-50.3L-63.24,-50.24L-65.27,-50.32L-66.5,-50.21L-66.94,-49.99L-67.37,-49.35L-68.28,-49.2L-68.22,-49.15L-68.93,-48.83L-69.67,-48.2L-71.02,-48.46L-69.87,-48.17L-69.78,-48.1L-69.99,-47.74L-71.27,-46.8L-72.2,-46.56L-72.98,-46.21L-73.48,-45.74L-73.71,-45.71L-74.04,-45.5L-74.32,-45.53L-74,-45.43L-73.97,-45.35L-74.71,-45L-73.56,-45.43L-73.16,-46.01L-71.9,-46.63L-70.52,-47.03L-69.47,-47.97L-68.24,-48.63L-66.6,-49.13L-65.52,-49.27L-64.84,-49.19L-64.26,-48.92L-64.21,-48.81L-64.51,-48.84L-64.25,-48.69L-64.35,-48.42L-65.26,-48.02L-65.93,-48.19L-66.7,-48.02L-66.36,-48.06L-65.85,-47.91L-65.61,-47.67L-65,-47.85L-65.05,-47.79L-64.7,-47.72L-64.91,-47.37L-65.32,-47.1L-64.83,-47.06L-64.91,-46.89L-64.54,-46.24L-63.92,-46.17L-63.83,-46.11L-64.06,-46.02L-63.7,-45.86L-62.7,-45.74L-62.75,-45.65L-62.48,-45.62L-61.96,-45.87L-61.78,-45.66L-61.49,-45.69L-61.35,-45.57L-61.28,-45.44L-61.46,-45.37L-61.03,-45.29L-63.31,-44.64L-63.6,-44.68L-63.54,-44.54L-63.61,-44.48L-64,-44.64L-64.1,-44.49L-64.17,-44.59L-64.29,-44.55L-64.28,-44.33L-65.48,-43.52L-65.74,-43.56L-65.89,-43.8L-66.04,-43.74L-66.13,-43.81L-66.19,-44.14L-66.1,-44.37L-65.87,-44.57L-66.09,-44.5L-65.62,-44.68L-65.5,-44.76L-65.73,-44.7L-65.66,-44.76L-64.9,-45.12L-64.45,-45.26L-64.45,-45.34L-64.33,-45.31L-64.35,-45.14L-64.14,-45.02L-64.18,-45.15L-64.09,-45.22L-63.37,-45.36L-64.87,-45.35L-64.83,-45.48L-64.31,-45.84L-64.48,-45.81L-64.63,-45.95L-64.59,-45.81L-64.78,-45.64L-65.88,-45.22L-66.11,-45.32L-66.03,-45.42L-66.18,-45.34L-66.14,-45.23L-66.44,-45.1L-66.87,-45.07L-67.12,-45.17L-67.11,-44.89L-66.99,-44.83L-67.19,-44.68L-67.84,-44.58L-68.06,-44.38L-68.15,-44.5L-68.37,-44.45L-68.45,-44.51L-68.53,-44.26L-68.81,-44.34L-68.71,-44.44L-68.79,-44.45L-68.76,-44.57L-68.96,-44.43L-69.07,-44.1L-69.23,-43.99L-69.52,-43.9L-69.56,-43.98L-69.62,-43.88L-69.65,-43.99L-69.73,-43.85L-69.8,-43.91L-69.81,-43.77L-69.97,-43.79L-69.97,-43.86L-70.18,-43.77L-70.27,-43.67L-70.2,-43.63L-70.73,-43.07L-70.83,-42.83L-70.61,-42.62L-70.83,-42.55L-71.05,-42.33L-70.74,-42.23L-70.66,-41.99L-70.43,-41.76L-70,-41.83L-70.11,-42.03L-70.24,-42.07L-70.11,-42.08L-69.98,-41.96L-69.95,-41.68L-70.66,-41.53L-70.7,-41.71L-71.17,-41.49L-71.15,-41.75L-71.27,-41.68L-71.39,-41.8L-71.52,-41.38L-72.92,-41.29L-73.58,-41.02L-73.99,-40.75L-73.87,-41.06L-73.97,-41.25L-73.93,-40.91L-74.26,-40.53L-73.97,-40.4L-74.08,-39.79L-74.1,-39.98L-74.26,-39.61L-74.41,-39.55L-74.43,-39.39L-74.92,-38.94L-74.9,-39.15L-75.14,-39.21L-75.52,-39.49L-75.42,-39.79L-75.07,-39.98L-75.46,-39.78L-75.59,-39.64L-75.57,-39.48L-75.31,-38.97L-75.09,-38.78L-75.19,-38.59L-75.07,-38.58L-75.04,-38.43L-75.93,-37.15L-75.98,-37.4L-75.66,-37.95L-75.85,-37.97L-75.8,-38.09L-75.93,-38.17L-75.86,-38.36L-76.05,-38.28L-76.26,-38.44L-76.26,-38.6L-76.02,-38.63L-76.21,-38.76L-76.34,-38.71L-76.17,-38.85L-76.24,-38.94L-76.33,-38.91L-76.31,-39.01L-76.19,-38.99L-76.14,-39.08L-76.22,-39.06L-76.24,-39.19L-76.07,-39.37L-75.88,-39.38L-76,-39.41L-75.87,-39.51L-76.06,-39.56L-76.1,-39.43L-76.25,-39.44L-76.28,-39.32L-76.33,-39.4L-76.42,-39.23L-76.57,-39.27L-76.43,-39.13L-76.47,-39.03L-76.56,-39.07L-76.5,-38.53L-76.39,-38.37L-76.67,-38.54L-76.34,-38.09L-76.77,-38.26L-76.87,-38.39L-76.89,-38.29L-77,-38.45L-77.23,-38.41L-77.03,-38.89L-77.31,-38.4L-77.05,-38.36L-76.91,-38.2L-76.26,-37.89L-76.34,-37.68L-76.49,-37.68L-77.11,-38.17L-76.55,-37.67L-76.31,-37.57L-76.37,-37.53L-76.27,-37.5L-76.26,-37.36L-76.4,-37.39L-76.45,-37.27L-76.76,-37.51L-76.28,-37.05L-76.4,-36.99L-76.63,-37.22L-77.25,-37.33L-76.67,-37.17L-76.49,-36.9L-76,-36.91L-75.53,-35.82L-75.95,-36.66L-75.99,-36.47L-75.82,-36.11L-76.15,-36.28L-76.15,-36.15L-76.27,-36.19L-76.23,-36.12L-76.38,-36.13L-76.56,-36.02L-76.73,-36.23L-76.73,-35.96L-76.07,-35.97L-76.08,-35.69L-75.85,-35.96L-75.76,-35.84L-75.77,-35.65L-76.17,-35.35L-76.49,-35.4L-76.58,-35.53L-76.74,-35.43L-77.04,-35.53L-76.51,-35.27L-76.78,-34.99L-77.07,-35.15L-76.97,-35.03L-76.74,-34.94L-76.46,-34.99L-76.36,-34.94L-76.44,-34.84L-77.3,-34.6L-77.41,-34.73L-77.38,-34.53L-77.75,-34.28L-77.93,-33.94L-77.95,-34.17L-78.01,-33.91L-78.41,-33.92L-78.84,-33.72L-79.19,-33.24L-79.23,-33.4L-79.28,-33.14L-79.8,-32.79L-79.93,-32.81L-79.94,-32.67L-80.36,-32.5L-80.63,-32.51L-80.47,-32.42L-80.58,-32.29L-80.8,-32.45L-80.69,-32.22L-80.92,-31.94L-81.11,-31.88L-81.07,-31.79L-81.26,-31.54L-81.18,-31.53L-81.38,-31.35L-81.29,-31.26L-81.46,-31.13L-81.52,-30.8L-81.25,-29.79L-80.52,-28.49L-80.58,-28.27L-80.46,-27.9L-80.61,-28.18L-80.61,-28.52L-80.69,-28.34L-80.69,-28.58L-80.84,-28.76L-80.75,-28.38L-80.05,-26.81L-80.13,-25.83L-80.48,-25.23L-81.11,-25.14L-81.14,-25.31L-80.94,-25.26L-81.11,-25.37L-81.36,-25.83L-81.72,-25.98L-81.96,-26.49L-81.83,-26.69L-82.04,-26.55L-82.01,-26.96L-82.18,-26.94L-82.18,-26.84L-82.29,-26.87L-82.71,-27.5L-82.4,-27.84L-82.64,-27.98L-82.66,-27.72L-82.84,-27.85L-82.66,-28.49L-82.65,-28.89L-83.69,-29.93L-84.04,-30.1L-84.31,-30.06L-84.38,-29.91L-85.32,-29.68L-85.41,-29.77L-85.41,-29.84L-85.31,-29.76L-85.35,-29.88L-85.68,-30.12L-85.6,-30.29L-85.79,-30.17L-86.45,-30.4L-86.12,-30.41L-86.26,-30.49L-87.2,-30.34L-86.99,-30.43L-87,-30.57L-87.17,-30.54L-87.28,-30.34L-87.48,-30.29L-87.45,-30.39L-87.62,-30.26L-88.01,-30.23L-87.79,-30.29L-88.01,-30.69L-88.14,-30.37L-88.91,-30.42L-89.32,-30.35L-89.59,-30.17L-90.13,-30.37L-90.33,-30.28L-90.41,-30.14L-90.18,-30.03L-89.74,-30.17L-89.67,-30.12L-89.82,-30.01L-89.63,-29.9L-89.4,-30.05L-89.35,-29.82L-89.72,-29.62L-89.51,-29.42L-89.02,-29.2L-89.16,-29.02L-89.24,-29.08L-89.38,-28.98L-89.44,-29.19L-90.16,-29.54L-90.05,-29.43L-90.14,-29.14L-90.5,-29.3L-90.75,-29.13L-91.29,-29.29L-91.15,-29.32L-91.25,-29.56L-91.51,-29.56L-91.89,-29.84L-92.14,-29.7L-92.08,-29.59L-92.26,-29.56L-93.18,-29.78L-93.83,-29.73L-93.88,-29.81L-93.77,-29.95L-93.84,-29.98L-93.95,-29.81L-93.89,-29.69L-94.76,-29.38L-94.53,-29.55L-94.78,-29.55L-94.74,-29.75L-95.02,-29.7L-94.89,-29.37L-95.27,-28.96L-95.85,-28.64L-96.23,-28.49L-96.01,-28.63L-96.45,-28.59L-96.64,-28.71L-96.42,-28.46L-96.68,-28.34L-96.77,-28.42L-96.84,-28.19L-97.16,-28.14L-97.14,-28.06L-97.03,-28.09L-97.07,-27.99L-97.17,-27.88L-97.43,-27.84L-97.29,-27.67L-97.44,-27.33L-97.77,-27.46L-97.69,-27.29L-97.49,-27.24L-97.55,-26.97L-97.44,-26.49L-97.14,-26.03L-97.16,-25.75L-97.51,-25.01L-97.67,-24.39L-97.75,-22.94L-97.86,-22.62L-97.76,-22.11L-97.31,-21.56L-97.41,-21.27L-97.38,-21.57L-97.75,-22.03L-97.64,-21.6L-97.19,-20.72L-96.46,-19.87L-96.29,-19.34L-95.78,-18.81L-95.92,-18.82L-95.63,-18.69L-95.7,-18.77L-95.18,-18.7L-94.8,-18.51L-94.46,-18.17L-93.55,-18.43L-92.88,-18.47L-92.44,-18.68L-91.97,-18.72L-91.88,-18.64L-91.91,-18.53L-91.53,-18.46L-91.28,-18.62L-91.34,-18.9L-91.44,-18.89L-90.74,-19.35L-90.69,-19.73L-90.49,-19.95L-90.48,-20.56L-90.35,-21.01L-89.82,-21.27L-88.88,-21.41L-88.47,-21.57L-88.01,-21.6L-87.25,-21.45L-87.19,-21.55L-87.37,-21.57L-87.03,-21.59L-86.82,-21.42L-86.82,-21.01L-87.42,-20.23L-87.44,-19.86L-87.69,-19.64L-87.65,-19.55L-87.42,-19.58L-87.66,-19.35L-87.66,-19.26L-87.5,-19.29L-87.85,-18.27L-88.06,-18.52L-88.03,-18.84L-88.2,-18.72L-88.35,-18.36L-88.13,-18.35L-88.09,-18.23L-88.27,-17.61L-88.2,-17.52L-88.31,-16.63L-88.88,-16.02L-88.89,-15.89L-88.6,-15.76L-88.54,-15.85L-88.59,-15.95L-88.13,-15.7L-87.7,-15.91L-87.49,-15.79L-86.91,-15.76L-86.36,-15.78L-85.94,-15.95L-85.99,-16.02L-85.48,-15.9L-84.97,-15.99L-84.56,-15.8L-84.43,-15.83L-84.52,-15.87L-84.26,-15.82L-83.78,-15.44L-84.08,-15.51L-84.1,-15.4L-83.93,-15.39L-83.76,-15.22L-83.5,-15.22L-83.65,-15.37L-83.37,-15.24L-83.16,-14.99L-83.28,-14.81L-83.34,-14.9L-83.41,-14.83L-83.3,-14.75L-83.19,-14.34L-83.49,-13.74L-83.57,-13.32L-83.51,-12.41L-83.63,-12.46L-83.59,-12.71L-83.75,-12.5L-83.65,-12.29L-83.68,-12.02L-83.77,-12.06L-83.83,-11.86L-83.7,-11.82L-83.65,-11.64L-83.87,-11.3L-83.35,-10.32L-82.78,-9.67L-82.37,-9.43L-82.34,-9.21L-82.19,-9.19L-82.24,-9.03L-82.08,-8.93L-81.78,-8.96L-81.89,-9.14L-81.55,-8.83L-81.06,-8.81L-80.13,-9.21L-79.58,-9.6L-79.11,-9.54L-78.93,-9.43L-78.5,-9.41L-77.83,-9.07L-76.85,-8.09L-76.9,-7.94L-76.79,-7.93L-76.77,-8.31L-76.92,-8.57L-76.28,-8.99L-76.03,-9.37L-75.64,-9.45L-75.68,-9.73L-75.54,-10.21L-75.71,-10.14L-75.45,-10.61L-75.25,-10.78L-74.84,-11.11L-74.33,-11L-74.52,-10.86L-74.4,-10.77L-74.14,-11.32L-73.31,-11.3L-72.72,-11.71L-72.28,-11.89L-72.14,-12.19L-71.6,-12.43L-71.26,-12.34L-71.14,-12.05L-71.41,-11.76L-71.96,-11.57L-71.84,-11.19L-71.64,-11.01L-71.73,-10.99L-71.59,-10.66L-72.11,-9.82L-71.62,-9.05L-71.24,-9.16L-71.09,-9.35L-71.05,-9.71L-71.49,-10.53L-71.54,-10.78L-71.47,-10.96L-70.23,-11.37L-70.1,-11.52L-69.8,-11.47L-69.82,-11.67L-70.19,-11.62L-70.29,-11.89L-70.2,-12.1L-70,-12.18L-69.86,-12.05L-69.63,-11.48L-69.23,-11.52L-68.83,-11.43L-68.4,-11.16L-68.27,-10.88L-68.3,-10.69L-68.14,-10.49L-66.25,-10.63L-65.85,-10.26L-65.13,-10.07L-64.85,-10.1L-64.19,-10.46L-63.73,-10.5L-64.25,-10.54L-64.3,-10.64L-61.88,-10.74L-62.38,-10.55L-62.91,-10.53L-62.69,-10.29L-62.74,-10.06L-62.55,-10.2L-62.32,-9.78L-62.22,-9.88L-62.15,-9.82L-62.16,-9.98L-62.08,-9.98L-61.74,-9.63L-61.77,-9.81L-61.59,-9.89L-61.31,-9.63L-61.01,-9.56L-60.79,-9.36L-61.02,-9.15L-61.25,-8.6L-61.62,-8.6L-61.3,-8.41L-60.8,-8.59L-60.17,-8.62L-59.2,-8.07L-58.81,-7.74L-58.48,-7.33L-58.67,-6.39L-58.41,-6.85L-57.98,-6.79L-57.54,-6.33L-57.23,-6.18L-57.18,-5.53L-56.97,-5.99L-56.24,-5.89L-55.94,-5.8L-55.9,-5.7L-55.91,-5.89L-55.83,-5.96L-54.83,-5.99L-54.36,-5.91L-54.05,-5.81L-54.16,-5.36L-53.85,-5.78L-53.45,-5.56L-52.9,-5.43L-52.29,-4.94L-52.32,-4.77L-52.22,-4.86L-52.06,-4.72L-51.96,-4.51L-52,-4.35L-51.83,-4.64L-51.65,-4.06L-51.55,-4.31L-51.22,-4.09L-50.71,-2.13L-50.61,-2.1L-50.46,-1.83L-49.96,-1.66L-49.9,-1.16L-50.29,-0.84L-50.76,-0.22L-51.28,0.09L-51.7,0.76L-51.72,1.02L-51.92,1.18L-51.98,1.37L-52.23,1.36L-52.66,1.55L-52.2,1.64L-51.95,1.59L-50.89,0.94L-50.84,1.04L-50.92,1.12L-50.69,1.76L-50.4,2.02L-50,1.83L-49.72,1.93L-49.31,1.73L-49.64,2.66L-49.46,2.5L-49.21,1.92L-48.99,1.83L-48.71,1.49L-48.46,1.61L-48.35,1.48L-48.47,1.39L-48.45,1.15L-48.12,0.74L-47.56,0.67L-47.42,0.77L-47.4,0.63L-46.81,0.78L-46.62,0.97L-46.22,1.03L-45.64,1.35L-45.46,1.36L-45.33,1.72L-45.08,1.47L-44.72,1.73L-44.78,1.8L-44.65,1.75L-44.54,2.05L-44.76,2.27L-44.66,2.37L-44.44,2.17L-44.38,2.37L-44.52,2.41L-44.59,2.57L-44.72,3.2L-44.44,2.94L-44.23,2.47L-44.11,2.49L-44.19,2.81L-43.93,2.58L-43.46,2.5L-43.38,2.38L-42.94,2.47L-42.25,2.79L-41.88,2.75L-41.48,2.92L-40.47,2.8L-39.96,2.86L-38.48,3.72L-38.05,4.22L-37.63,4.59L-37.3,4.71L-37.17,4.91L-36.59,5.1L-35.98,5.05L-35.48,5.17L-35.24,5.57L-34.83,7.02L-34.83,7.97L-35.34,9.23L-35.76,9.7L-35.89,9.69L-35.89,9.85L-36.4,10.48L-36.94,10.82L-37.18,11.07L-37.32,11.38L-37.36,11.25L-37.69,12.1L-38.24,12.84L-38.5,12.96L-38.52,12.76L-38.69,12.62L-38.85,12.79L-38.76,12.91L-39.09,13.59L-38.99,13.62L-39.05,14.04L-39.01,14.1L-38.94,14.03L-39.06,14.65L-38.88,15.86L-39.2,17.18L-39.15,17.7L-39.65,18.25L-39.78,19.57L-40,19.74L-40.4,20.57L-40.79,20.91L-40.95,21.24L-41.05,21.51L-41,22L-41.71,22.31L-41.98,22.58L-41.94,22.79L-42.04,22.95L-42.96,22.97L-43.15,22.73L-43.24,22.8L-43.22,22.99L-43.9,23.1L-43.97,23.06L-43.68,23.01L-43.87,22.91L-44.64,23.06L-44.67,23.21L-44.57,23.27L-45.33,23.6L-45.46,23.8L-45.97,23.8L-46.87,24.24L-47.99,25.04L-47.91,25.07L-47.93,25.17L-48.2,25.42L-48.19,25.31L-48.4,25.27L-48.48,25.44L-48.73,25.37L-48.69,25.49L-48.4,25.6L-48.55,25.82L-48.67,25.84L-48.58,25.94L-48.62,26.18L-48.75,26.27L-48.65,26.41L-48.68,26.7L-48.55,27.2L-48.64,27.56L-48.62,28.08L-48.8,28.58L-49.27,28.87L-49.75,29.36L-50.3,30.43L-50.92,31.26L-52.04,32.11L-52.06,31.83L-51.89,31.87L-51.68,31.77L-51.27,31.48L-51.16,31.12L-50.98,31.09L-50.94,30.9L-50.69,30.7L-50.72,30.43L-50.58,30.44L-50.56,30.25L-51.02,30.37L-51.3,30.03L-51.28,30.24L-51.16,30.36L-51.28,30.75L-51.36,30.67L-51.51,31.1L-51.97,31.38L-52.19,31.89L-52.13,32.17L-52.65,33.14L-53.42,33.78L-53.79,34.38L-54.17,34.67L-54.9,34.93L-55.67,34.78L-56.19,34.91L-56.86,34.68L-57.17,34.45L-57.83,34.48L-58.4,33.91L-58.44,33.72L-58.36,33.18L-58.09,32.97L-58.2,32.47L-58.17,32.96L-58.25,33.08L-58.42,33.11L-58.55,33.66L-58.39,34.19L-58.53,34.3L-58.28,34.68L-57.55,35.02L-57.17,35.36L-57.16,35.51L-57.35,35.72L-57.38,35.9L-57.08,36.3L-56.72,36.39L-56.73,36.96L-57.4,37.74L-57.55,38.09L-58.18,38.44L-59.83,38.84L-61.11,38.99L-61.85,38.96L-62.33,38.8L-62.3,39.24L-62.05,39.37L-62.18,39.38L-62.08,39.46L-62.13,39.83L-62.29,39.9L-62.4,40.2L-62.39,40.46L-62.25,40.67L-62.4,40.89L-62.96,41.11L-63.62,41.16L-64.85,40.81L-64.87,40.74L-65.07,40.81L-65.15,41.11L-64.99,42.1L-64.54,42.25L-64.57,42.42L-64.42,42.43L-64.1,42.4L-64.06,42.27L-64.23,42.22L-63.8,42.11L-63.63,42.28L-63.62,42.7L-63.69,42.81L-64.03,42.88L-64.49,42.51L-64.97,42.67L-65.03,42.76L-64.32,42.97L-64.84,43.19L-65.25,43.57L-65.27,44.28L-65.36,44.48L-65.65,44.66L-65.64,45.01L-66.19,44.96L-66.94,45.26L-67.6,46.05L-67.51,46.44L-66.78,47.01L-65.85,47.16L-65.74,47.34L-65.78,47.57L-65.89,47.7L-66.23,47.83L-65.93,47.83L-65.81,47.94L-67.47,48.95L-67.68,49.25L-67.78,49.86L-67.91,49.98L-68.26,50.1L-68.67,49.75L-68.66,49.94L-68.98,50L-68.6,50.01L-68.42,50.16L-68.94,50.38L-69.15,50.86L-69.36,51.03L-69.2,50.99L-69.06,51.55L-69.47,51.58L-68.97,51.68L-68.39,52.31L-69.24,52.21L-69.45,52.27L-69.62,52.46L-70.8,52.77L-70.98,53.37L-71,53.78L-71.3,53.88L-72.17,53.63L-72.41,53.35L-72.31,53.25L-71.94,53.23L-71.83,53.4L-71.89,53.52L-71.79,53.48L-71.74,53.23L-71.29,53.03L-71.16,52.89L-71.23,52.81L-71.39,52.76L-72.28,53.13L-72.49,53.29L-72.55,53.46L-73.05,53.24L-72.92,53.12L-72.89,52.87L-72.73,52.76L-72.45,52.81L-72.12,52.65L-71.51,52.61L-72.23,52.52L-72.44,52.63L-72.71,52.54L-73.12,53.07L-73.34,53.05L-73.65,52.84L-73.24,52.71L-73.07,52.54L-73.12,52.49L-73.24,52.62L-73.59,52.69L-74.01,52.64L-74.04,52.4L-74.15,52.38L-74.26,52.1L-73.83,52.23L-73.7,52.2L-73.68,52.08L-73.26,52.16L-72.8,51.95L-72.57,52.2L-72.71,52.36L-72.52,52.26L-72.62,52.01L-72.49,51.85L-72.54,51.71L-73.17,51.45L-72.65,51.7L-72.6,51.8L-73.38,52.07L-73.52,52.04L-73.75,51.8L-74.2,51.68L-74.07,51.58L-73.93,51.62L-73.94,51.27L-74.81,51.06L-75.09,50.68L-74.69,50.66L-74.78,50.47L-74.64,50.36L-74.37,50.49L-74.14,50.82L-73.81,50.94L-73.74,50.7L-73.62,50.65L-73.65,50.49L-73.98,50.83L-74.2,50.61L-74.19,50.49L-73.95,50.51L-74.63,50.19L-74.33,49.97L-73.96,49.99L-74.32,49.78L-74.29,49.6L-73.84,49.61L-74.09,49.43L-73.93,49.02L-74.03,49.03L-74.22,49.5L-74.37,49.4L-74.34,48.6L-74.01,48.48L-74.47,48.46L-74.58,48L-73.85,48.04L-73.53,48.2L-73.39,48.15L-73.61,47.99L-73.72,47.66L-73.94,47.93L-74.23,47.97L-74.65,47.7L-74.53,47.57L-74.24,47.68L-74.13,47.59L-74.48,47.43L-74.16,47.18L-74.15,46.97L-74.31,46.79L-74.45,46.77L-74.51,46.89L-75.01,46.74L-74.98,46.51L-75.54,46.7L-75.39,46.86L-75.43,46.93L-75.64,46.86L-75.71,46.71L-74.92,46.16L-75.07,46L-75.07,45.87L-74.16,45.77L-74.08,45.68L-74.12,45.5L-73.96,45.4L-73.83,45.45L-74.06,45.95L-74.02,46.06L-74.39,46.22L-73.97,46.15L-73.88,45.85L-73.74,45.81L-73.71,46.07L-73.95,46.53L-73.85,46.57L-73.66,46.3L-73.59,45.9L-73.59,45.78L-73.76,45.7L-73.73,45.48L-73.27,45.35L-72.93,45.45L-73.23,45.26L-73.44,45.24L-73.4,45.1L-73.36,44.98L-72.74,44.73L-72.68,44.59L-72.66,44.44L-73.27,44.17L-73.22,43.9L-73.07,43.86L-73,43.63L-73.08,43.32L-72.88,43.05L-72.76,43.04L-72.85,42.67L-72.77,42.51L-72.63,42.51L-72.77,42.26L-72.63,42.2L-72.41,42.39L-72.5,41.98L-72.74,41.99L-72.82,41.91L-72.66,41.74L-72.36,41.65L-72.32,41.5L-72.54,41.69L-72.95,41.51L-73.24,41.78L-73.62,41.77L-73.74,41.74L-73.62,41.58L-73.81,41.52L-73.97,41.12L-73.67,39.96L-73.41,39.79L-73.23,39.22L-73.52,38.51L-73.46,38.04L-73.66,37.7L-73.66,37.34L-73.6,37.19L-73.22,37.17L-73.12,36.69L-73.01,36.64L-72.78,35.98L-72.59,35.76L-72.62,35.59L-72.22,35.1L-72,34.17L-71.66,33.65L-71.74,33.1L-71.45,32.66L-71.42,32.39L-71.51,32.21L-71.71,30.63L-71.67,30.33L-71.4,30.14L-71.32,29.65L-71.52,28.93L-71.19,28.38L-70.65,26.33L-70.71,25.78L-70.45,25.25L-70.57,24.64L-70.51,23.89L-70.39,23.57L-70.59,23.26L-70.56,23.06L-70.33,22.85L-70.09,21.49L-70.2,20.73L-70.15,19.81L-70.36,18.4L-71.34,17.68L-71.4,17.42L-71.53,17.29L-72.11,17L-72.47,16.71L-73.73,16.2L-75.1,15.41L-75.53,14.9L-75.93,14.63L-76.38,13.86L-76.26,13.8L-76.22,13.37L-76.83,12.35L-77.15,12.06L-77.22,11.66L-77.63,11.29L-77.74,10.84L-78.19,10.09L-78.76,8.62L-79.38,7.84L-79.62,7.3L-79.99,6.77L-81.14,6.06L-81.16,5.88L-80.93,5.84L-80.88,5.64L-81.34,4.67L-81.23,4.23L-80.8,3.73L-80.03,3.23L-79.73,2.58L-79.84,2.07L-79.93,2.55L-80.03,2.56L-80.01,2.35L-80.28,2.71L-80.96,2.19L-80.77,2.08L-80.76,1.93L-80.9,1.08L-80.55,0.85L-80.46,0.59L-80.28,0.62L-80.48,0.37L-80.05,-0.16L-80.09,-0.78L-79.74,-0.98L-78.9,-1.21L-78.86,-1.46L-79.03,-1.62L-78.79,-1.85L-78.58,-1.77L-78.59,-2.36L-78.42,-2.48L-78.07,-2.51L-77.81,-2.72L-77.67,-2.88L-77.69,-3.04L-77.56,-3.08L-77.36,-3.35L-77.08,-3.91L-77.26,-3.89L-77.28,-4.06L-77.36,-3.94L-77.41,-4.25L-77.52,-4.21L-77.35,-4.4L-77.29,-4.72L-77.37,-5.32L-77.53,-5.54L-77.25,-5.78L-77.47,-6.18L-77.37,-6.58L-78.17,-7.54L-78.42,-8.06L-78.29,-8.09L-78.28,-8.25L-78.14,-8.39L-77.76,-8.13L-78.1,-8.5L-78.22,-8.4L-78.4,-8.51L-78.41,-8.36L-78.51,-8.63L-78.96,-8.93L-79.44,-9.01L-79.69,-8.85L-79.82,-8.64L-79.75,-8.6L-80.46,-8.21L-80.46,-8.08L-80.01,-7.5L-80.29,-7.43L-80.44,-7.27L-80.85,-7.22L-81.06,-7.9L-81.27,-7.63L-81.5,-7.72L-81.73,-8.14L-82.16,-8.19L-82.24,-8.31L-82.68,-8.32L-82.87,-8.25L-82.88,-8.07L-83.29,-8.66L-83.47,-8.71L-83.29,-8.41L-83.6,-8.48L-83.73,-8.61L-83.61,-8.8L-83.74,-9.15L-84.22,-9.46L-84.58,-9.57L-84.71,-9.9L-85.24,-10.24L-85.24,-10.11L-84.89,-9.82L-85.08,-9.6L-85.31,-9.81L-85.62,-9.9L-85.85,-10.29L-85.66,-10.64L-85.67,-10.75L-85.91,-10.9L-85.75,-10.99L-85.75,-11.09L-86.47,-11.74L-86.85,-12.25L-87.67,-12.9L-87.59,-13.04L-87.34,-12.95L-87.49,-13.35L-87.81,-13.4L-87.82,-13.29L-88.02,-13.17L-88.69,-13.28L-88.51,-13.18L-89.28,-13.48L-89.8,-13.56L-90.48,-13.9L-91.38,-13.99L-92.26,-14.57L-92.81,-15.14L-93.92,-16.05L-94.37,-16.28L-94.43,-16.23L-94,-16.02L-94.66,-16.2L-94.62,-16.35L-94.79,-16.29L-94.9,-16.42L-95.02,-16.28L-94.8,-16.21L-95.13,-16.18L-95.46,-15.97L-96.51,-15.65L-97.18,-15.91L-97.75,-15.97L-98.14,-16.21L-98.52,-16.3L-98.76,-16.53L-99.69,-16.72L-100.85,-17.2L-101.6,-17.65L-101.92,-17.96L-102.7,-18.06L-103.44,-18.33L-103.91,-18.83L-104.94,-19.31L-105.48,-19.98L-105.67,-20.39L-105.26,-20.58L-105.33,-20.75L-105.51,-20.81L-105.24,-21.12L-105.21,-21.49L-105.43,-21.62L-105.65,-21.99L-105.65,-22.33L-105.79,-22.63L-106.4,-23.2L-106.94,-23.88L-107.76,-24.47L-107.53,-24.36L-107.51,-24.49L-107.95,-24.61L-108.28,-25.08L-108.05,-25.07L-108.7,-25.38L-108.79,-25.54L-109.03,-25.48L-109.07,-25.55L-108.89,-25.73L-109.08,-25.62L-109.3,-25.63L-109.43,-26.03L-109.2,-26.31L-109.12,-26.25L-109.28,-26.53L-109.48,-26.71L-109.75,-26.7L-109.94,-27.08L-110.28,-27.16L-110.48,-27.32L-110.62,-27.65L-110.53,-27.86L-111.12,-27.97L-111.47,-28.38L-111.68,-28.47L-112.16,-29.02L-112.22,-29.27L-112.38,-29.35L-112.41,-29.54L-112.74,-29.99L-113.11,-30.79L-113.05,-31.18L-113.62,-31.35L-113.76,-31.56L-113.95,-31.63L-114,-31.53L-114.15,-31.51L-114.93,-31.9L-114.79,-31.65L-114.88,-31.16L-114.63,-30.51L-114.63,-30.16L-114.37,-29.83L-113.76,-29.37L-113.5,-28.93L-113.38,-28.95L-113.32,-28.81L-113.21,-28.8L-113.09,-28.51L-112.87,-28.42L-112.73,-27.83L-112.33,-27.52L-112.19,-27.19L-112,-27.08L-111.86,-26.68L-111.7,-26.58L-111.8,-26.88L-111.57,-26.71L-111.29,-25.79L-111.03,-25.53L-110.69,-24.87L-110.73,-24.59L-110.66,-24.34L-110.37,-24.1L-110.26,-24.34L-109.42,-23.48L-109.5,-23.16L-110.01,-22.89L-110.36,-23.6L-111.68,-24.56L-111.8,-24.54L-112.07,-24.84L-112.07,-25.57L-112.38,-26.21L-113.02,-26.58L-113.16,-26.95L-113.27,-26.79L-113.6,-26.72L-113.84,-26.97L-114.45,-27.22L-114.54,-27.43L-114.99,-27.74L-115.04,-27.84L-114.57,-27.78L-114.3,-27.87L-114.3,-27.78L-114.07,-27.68L-114.16,-27.92L-114.27,-27.93L-114.05,-28.43L-114.94,-29.35L-115.67,-29.76L-115.81,-29.96L-115.82,-30.3L-116,-30.41L-116.06,-30.8L-116.3,-30.97L-116.33,-31.2L-116.66,-31.56L-116.72,-31.73L-116.62,-31.85L-116.85,-32L-117.06,-32.34L-117.14,-32.65L-117.24,-32.66L-117.32,-33.1L-117.47,-33.3L-118.08,-33.72L-118.41,-33.74L-118.51,-34.02L-119.14,-34.11L-119.61,-34.42L-120.48,-34.47L-120.64,-34.58L-120.66,-35.12L-120.86,-35.21L-120.9,-35.43L-121.28,-35.68L-121.88,-36.33L-121.92,-36.57L-121.79,-36.73L-121.81,-36.85L-122.16,-36.99L-122.39,-37.21L-122.5,-37.54L-122.51,-37.77L-122.45,-37.8L-122.3,-37.59L-122.07,-37.48L-122.39,-37.96L-122.31,-38.01L-121.53,-38.06L-122.39,-38.14L-122.48,-38.11L-122.52,-37.83L-122.93,-38.06L-123,-37.99L-122.98,-38.23L-122.91,-38.2L-123.7,-38.91L-123.83,-39.78L-124.36,-40.37L-124.13,-40.97L-124.07,-41.46L-124.54,-42.81L-124.35,-43.34L-124.2,-43.42L-124.29,-43.41L-124.15,-43.69L-123.93,-45.58L-123.99,-46.22L-123.22,-46.15L-123.46,-46.27L-124.07,-46.28L-124.04,-46.61L-123.95,-46.43L-123.89,-46.66L-124.11,-46.86L-123.84,-46.96L-124.11,-47.04L-124.14,-46.95L-124.38,-47.66L-124.66,-47.97L-124.71,-48.38L-123.98,-48.17L-123.16,-48.15L-122.97,-48.07L-122.78,-48.14L-122.66,-47.88L-123.05,-47.55L-123.14,-47.36L-122.92,-47.41L-123.07,-47.4L-123.05,-47.48L-122.53,-47.92L-122.52,-47.77L-122.68,-47.61L-122.56,-47.46L-122.58,-47.29L-122.71,-47.32L-122.77,-47.22L-122.83,-47.34L-123.03,-47.14L-122.63,-47.14L-122.35,-47.37L-122.4,-47.78L-122.24,-48.01L-122.42,-48.18L-122.39,-48.08L-122.49,-48.13L-122.52,-48.23L-122.41,-48.29L-122.66,-48.45L-122.5,-48.51L-122.55,-48.76L-122.69,-48.79L-122.83,-49.03L-122.96,-49.07L-123.08,-48.98L-123.08,-49.13L-123.2,-49.15L-123.23,-49.26L-122.95,-49.29L-122.88,-49.4L-123.28,-49.34L-123.19,-49.68L-123.34,-49.46L-123.53,-49.4L-123.95,-49.53L-124.05,-49.66L-123.99,-49.74L-123.82,-49.59L-123.58,-49.68L-123.87,-49.74L-123.9,-49.98L-123.78,-50.09L-123.88,-50.17L-123.95,-50.18L-123.87,-50.07L-123.97,-49.89L-124.14,-49.79L-124.41,-49.78L-124.7,-49.96L-125.06,-50.42L-124.86,-50.64L-124.86,-50.87L-125.06,-50.51L-125.48,-50.5L-125.54,-50.65L-125.64,-50.47L-126.09,-50.5L-126.45,-50.59L-125.9,-50.7L-126.51,-50.68L-126.37,-50.84L-126.52,-50.87L-126.52,-51.06L-126.63,-50.92L-127.06,-50.87L-127.71,-51.15L-127.69,-51.34L-127.42,-51.61L-126.69,-51.7L-127.34,-51.71L-127.67,-51.48L-127.85,-51.67L-127.86,-51.82L-127.73,-51.99L-127.86,-51.99L-127.8,-52.19L-127.44,-52.36L-127.24,-52.4L-126.71,-52.06L-127.19,-52.46L-126.95,-52.72L-127.01,-52.84L-127.07,-52.65L-127.83,-52.25L-128.1,-51.79L-128.36,-52.16L-128.04,-52.32L-128.05,-52.45L-127.94,-52.55L-128.27,-52.36L-128.05,-52.91L-128.37,-52.83L-128.52,-53.14L-129.08,-53.37L-129.17,-53.53L-129.02,-53.69L-128.85,-53.7L-128.91,-53.56L-128.54,-53.42L-128.13,-53.42L-127.93,-53.27L-128.21,-53.48L-128.68,-53.55L-128.76,-53.75L-128.53,-53.86L-128.7,-53.92L-128.96,-53.84L-129.21,-53.64L-129.26,-53.42L-129.56,-53.25L-129.91,-53.55L-130.34,-53.72L-130.04,-54.13L-129.63,-54.23L-130.08,-54.18L-130.43,-54.42L-130.35,-54.66L-129.56,-55.46L-129.7,-55.44L-129.8,-55.56L-129.84,-55.32L-130.05,-55.06L-129.99,-55.36L-130.09,-55.69L-130.03,-55.89L-130.15,-55.65L-130.04,-55.3L-130.22,-55.06L-130.2,-54.95L-130.54,-54.75L-130.85,-54.81L-131.05,-55.16L-130.75,-55.32L-130.86,-55.36L-130.92,-55.74L-131.13,-55.96L-131.03,-56.09L-131.78,-55.88L-131.95,-55.55L-132.12,-55.57L-132.21,-55.75L-131.84,-56.16L-131.55,-56.21L-131.89,-56.24L-132.18,-56.42L-132.48,-56.65L-132.49,-56.77L-132.8,-56.9L-132.82,-57.06L-133.47,-57.17L-133.44,-57.34L-133.65,-57.64L-133.55,-57.7L-133.12,-57.57L-133.54,-57.83L-133.19,-57.88L-133.56,-57.92L-133.72,-57.84L-134.03,-58.07L-134.05,-58.29L-133.88,-58.52L-134.21,-58.23L-134.66,-58.38L-135.13,-58.84L-135.36,-59.42L-135.48,-59.31L-135.4,-59.21L-135.5,-59.2L-135.06,-58.34L-135.09,-58.25L-135.57,-58.41L-135.9,-58.4L-135.86,-58.58L-136.04,-58.82L-135.83,-58.9L-136.02,-58.87L-136.15,-59.05L-136.12,-58.82L-136.23,-58.77L-136.57,-58.94L-137,-59.02L-136.95,-58.93L-137.06,-58.87L-136.61,-58.81L-136.41,-58.7L-136.48,-58.62L-136.22,-58.6L-136.06,-58.45L-136.08,-58.36L-136.61,-58.24L-137.54,-58.58L-138.51,-59.17L-139.77,-59.53L-139.51,-59.7L-139.58,-59.85L-139.51,-59.95L-139.33,-59.88L-139.29,-59.61L-139.22,-59.82L-138.99,-59.84L-139.43,-60.01L-140.42,-59.71L-141.41,-59.9L-141.29,-60L-141.41,-60.12L-141.45,-60.02L-141.67,-59.97L-142.95,-60.1L-144.15,-60.02L-144.09,-60.08L-144.19,-60.15L-144.9,-60.34L-144.69,-60.67L-145.25,-60.38L-145.9,-60.48L-145.67,-60.65L-146.57,-60.73L-146.39,-60.81L-146.64,-60.9L-146.6,-61.05L-146.28,-61.11L-147.89,-60.89L-148.01,-60.97L-147.75,-61.22L-148.34,-61.06L-148.4,-61.01L-148.21,-61.03L-148.34,-60.85L-148.56,-60.83L-148.26,-60.68L-148.3,-60.58L-148.64,-60.49L-148.12,-60.58L-147.96,-60.48L-148.18,-60.39L-148.2,-60.17L-148.43,-59.99L-149.27,-60L-149.4,-60.11L-149.6,-59.77L-149.71,-59.92L-149.78,-59.75L-150.01,-59.78L-149.97,-59.69L-150.2,-59.57L-150.61,-59.56L-150.93,-59.25L-151.18,-59.3L-151.17,-59.24L-151.74,-59.19L-151.95,-59.27L-151.88,-59.39L-151.4,-59.52L-151.05,-59.77L-151.45,-59.65L-151.85,-59.78L-151.4,-60.27L-151.31,-60.47L-151.36,-60.72L-150.44,-61.02L-149.08,-60.88L-150.05,-61.17L-149.33,-61.5L-149.63,-61.49L-149.98,-61.28L-150.61,-61.3L-151.59,-60.98L-151.78,-60.86L-151.75,-60.75L-152.27,-60.53L-152.26,-60.41L-152.54,-60.27L-153.03,-60.3L-152.66,-60.13L-152.66,-60L-153.21,-59.84L-153.02,-59.79L-153.09,-59.71L-153.36,-59.66L-153.41,-59.74L-153.65,-59.65L-153.75,-59.51L-154.09,-59.36L-154.18,-59.16L-153.42,-58.96L-153.33,-58.88L-153.44,-58.75L-154.29,-58.3L-154.21,-58.29L-154.25,-58.16L-155.01,-58.02L-155.78,-57.57L-156.44,-57.36L-156.4,-57.2L-156.63,-57.01L-157.44,-56.79L-157.58,-56.63L-158.03,-56.59L-158.08,-56.55L-157.93,-56.52L-158.41,-56.44L-158.55,-56.31L-158.28,-56.2L-158.48,-56.08L-158.59,-56.18L-158.79,-55.99L-159.52,-55.81L-159.66,-55.63L-159.68,-55.82L-159.77,-55.84L-160.5,-55.54L-160.9,-55.51L-161.18,-55.39L-161.46,-55.38L-161.41,-55.54L-161.2,-55.54L-161.52,-55.62L-162.07,-55.14L-162.39,-55.05L-162.63,-55.25L-162.67,-55L-162.87,-54.95L-163.12,-55.06L-163.13,-54.92L-163.34,-54.84L-163.28,-55.12L-162.91,-55.2L-162.16,-55.72L-161.7,-55.91L-161.22,-56.02L-161.19,-55.95L-160.9,-55.99L-161.01,-55.89L-160.8,-55.75L-160.71,-55.87L-160.29,-55.81L-160.54,-56.01L-160.3,-56.31L-158.92,-56.88L-158.68,-56.79L-158.66,-57.04L-158.32,-57.3L-157.85,-57.53L-157.46,-57.51L-157.7,-57.68L-157.61,-58.05L-157.56,-58.14L-157.19,-58.19L-157.49,-58.25L-157.52,-58.42L-156.97,-58.74L-157.04,-58.77L-156.81,-59.13L-157.14,-58.88L-158.19,-58.61L-158.5,-58.85L-158.43,-59L-158.08,-58.98L-158.42,-59.09L-158.68,-58.93L-158.81,-58.97L-158.86,-58.72L-158.79,-58.44L-158.95,-58.4L-159.67,-58.91L-159.92,-58.82L-160.36,-59.05L-161.25,-58.8L-161.36,-58.67L-162.14,-58.64L-161.72,-58.79L-161.79,-59.02L-161.64,-59.11L-161.98,-59.15L-162.02,-59.28L-161.83,-59.59L-162.24,-60.18L-162.42,-60.28L-162.14,-60.61L-161.95,-60.68L-162.14,-60.69L-162.68,-60.27L-162.53,-60.2L-162.57,-59.99L-163.91,-59.81L-164.66,-60.3L-165.06,-60.41L-165.03,-60.5L-165.35,-60.54L-164.81,-60.89L-164.32,-60.77L-164.27,-60.72L-164.37,-60.59L-164,-60.77L-163.73,-60.59L-163.42,-60.76L-163.91,-60.85L-163.59,-60.9L-163.75,-60.97L-163.99,-60.86L-165.11,-60.93L-165.18,-60.97L-164.87,-61.11L-165.28,-61.17L-165.34,-61.2L-165.27,-61.27L-165.39,-61.21L-165.38,-61.11L-165.57,-61.1L-165.69,-61.3L-165.86,-61.34L-165.85,-61.54L-166.09,-61.51L-166.17,-61.65L-165.81,-61.7L-166.08,-61.8L-165.61,-61.87L-165.73,-61.96L-165.71,-62.1L-165.19,-62.47L-164.76,-62.5L-164.84,-62.58L-164.59,-62.71L-164.79,-62.62L-164.8,-62.92L-164.68,-63.02L-164.38,-63.03L-164.53,-63.13L-164.41,-63.22L-163.94,-63.25L-163.62,-63.13L-163.74,-63.02L-163.5,-63.11L-163.29,-63.05L-162.62,-63.27L-162.28,-63.53L-161.51,-63.47L-160.93,-63.66L-160.78,-63.82L-160.99,-64.25L-161.49,-64.43L-161.41,-64.53L-160.93,-64.58L-160.84,-64.68L-160.89,-64.8L-161.13,-64.93L-161.47,-64.79L-161.76,-64.82L-162.71,-64.38L-163.2,-64.65L-163.3,-64.61L-163.05,-64.52L-163.14,-64.42L-163.71,-64.59L-164.98,-64.45L-166.14,-64.58L-166.48,-64.73L-166.42,-64.93L-166.93,-65.16L-166.53,-65.15L-166.45,-65.25L-166.16,-65.29L-167.4,-65.42L-168.09,-65.66L-167.07,-65.88L-166.4,-66.14L-165.63,-66.13L-165.56,-66.17L-165.84,-66.25L-165.78,-66.32L-164.46,-66.59L-163.64,-66.57L-163.89,-66.58L-163.78,-66.53L-163.89,-66.29L-164.03,-66.22L-163.7,-66.08L-161.93,-66.04L-161.46,-66.28L-161.03,-66.19L-161.12,-66.33L-161.92,-66.41L-161.89,-66.49L-162.19,-66.69L-162.54,-66.81L-162.61,-66.89L-162.36,-66.95L-162.02,-66.78L-162.05,-66.67L-161.91,-66.56L-161.59,-66.46L-160.23,-66.42L-160.36,-66.61L-160.86,-66.67L-161.4,-66.55L-161.86,-66.7L-161.88,-66.8L-161.62,-66.98L-161.72,-67.02L-163.53,-67.1L-164.13,-67.61L-165.39,-68.05L-166.79,-68.36L-166.38,-68.43L-166.21,-68.89L-164.3,-68.94L-163.54,-69.17L-163.16,-69.39L-162.95,-69.76L-161.88,-70.33L-161.76,-70.26L-162.07,-70.16L-161,-70.3L-160.12,-70.59L-159.96,-70.57L-160.11,-70.47L-160.01,-70.45L-160.1,-70.33L-159.87,-70.28L-159.81,-70.5L-159.39,-70.52L-160.08,-70.63L-159.68,-70.79L-159.31,-70.88L-159.19,-70.86L-159.34,-70.78L-159.25,-70.75L-157.91,-70.86L-156.47,-71.41L-156.57,-71.34L-156.47,-71.29L-155.58,-71.12L-156.15,-70.93L-155.97,-70.84L-155.58,-70.89L-155.17,-71.1L-154.67,-70.99L-154.79,-70.89L-154.2,-70.8L-153.23,-70.93L-152.3,-70.85L-152.23,-70.81L-152.47,-70.65L-151.77,-70.56L-151.94,-70.45L-149.27,-70.5L-147.71,-70.22L-145.82,-70.16L-144.62,-69.98L-143.22,-70.12L-141.41,-69.65L-139.18,-69.52L-137.87,-69.09L-136.72,-68.89L-136.12,-68.88L-135.26,-68.68L-135.43,-68.84L-135.89,-68.93L-135.92,-68.99L-135.58,-69.03L-135.91,-69.11L-135.69,-69.31L-135.29,-69.31L-135.14,-69.47L-134.46,-69.48L-134.41,-69.68L-133.88,-69.51L-134.17,-69.25L-133.16,-69.43L-132.92,-69.63L-132.4,-69.66L-132.57,-69.7L-132.49,-69.74L-132.16,-69.7L-131.44,-69.92L-131.14,-69.91L-130.67,-70.13L-129.94,-70.09L-129.62,-70.17L-129.54,-70.07L-129.65,-70L-130.83,-69.65L-131.94,-69.53L-132.33,-69.31L-132.69,-69.26L-133.42,-68.84L-133.14,-68.75L-133.34,-68.84L-132.58,-68.85L-132.74,-68.92L-132.72,-69.08L-131.92,-69.29L-131.79,-69.43L-131.34,-69.44L-131.32,-69.36L-131.06,-69.45L-130.97,-69.21L-130.52,-69.57L-130.12,-69.72L-128.9,-69.97L-129.16,-69.8L-129.05,-69.7L-128.85,-69.75L-128.39,-69.96L-128.28,-70.11L-127.68,-70.26L-128.17,-70.42L-127.99,-70.57L-127.23,-70.3L-126.68,-69.78L-126.25,-69.55L-125.52,-69.35L-125.17,-69.43L-125.36,-69.63L-125.2,-69.83L-124.77,-69.99L-124.99,-70.03L-124.56,-70.15L-124.44,-70.11L-124.41,-69.77L-124.12,-69.69L-124.48,-69.43L-124.34,-69.36L-123.53,-69.39L-123.21,-69.54L-123.03,-69.81L-122.07,-69.82L-120.96,-69.66L-120.14,-69.38L-118.87,-69.26L-117.23,-68.91L-116.06,-68.84L-116.24,-68.97L-115.81,-68.99L-114.99,-68.85L-113.96,-68.4L-114.1,-68.27L-114.77,-68.27L-115.13,-68.13L-115.17,-68.02L-115.43,-67.9L-115.13,-67.82L-112.5,-67.68L-110.99,-67.79L-110.07,-67.99L-109.63,-67.73L-109.04,-67.69L-108.85,-67.42L-108.61,-67.6L-107.99,-67.26L-107.91,-67.16L-107.99,-67.1L-108.5,-67.09L-107.26,-66.4L-107.71,-66.74L-107.75,-66.96L-107.16,-66.88L-107.35,-67.05L-107.28,-67.1L-107.57,-67.27L-107.65,-67.51L-107.95,-67.7L-107.96,-67.82L-107.76,-67.91L-107.8,-68.04L-106.42,-68.2L-106.4,-68.32L-105.93,-68.44L-105.75,-68.59L-105.93,-68.64L-106.46,-68.52L-106.61,-68.36L-107.62,-68.33L-107.74,-68.29L-107.73,-68.17L-108.26,-68.15L-108.72,-68.3L-108.31,-68.61L-106.16,-68.92L-105.69,-68.83L-105.38,-68.41L-104.65,-68.23L-104.66,-68.15L-104.49,-68.06L-103.47,-68.12L-102.32,-67.74L-101.55,-67.69L-100.46,-67.84L-98.92,-67.73L-98.41,-67.81L-98.7,-67.97L-98.63,-68.07L-97.93,-67.71L-97.45,-67.62L-97.16,-67.73L-97.21,-67.86L-97.74,-67.98L-98.19,-67.92L-98.5,-68.12L-98.38,-68.13L-98.65,-68.36L-97.79,-68.39L-97.94,-68.51L-97.83,-68.53L-97.34,-68.48L-96.98,-68.26L-96.43,-68.31L-96.72,-68.04L-95.97,-68.25L-96.37,-67.51L-96.14,-67.27L-95.72,-67.32L-95.78,-67.18L-95.42,-67.16L-95.42,-67.01L-96.42,-67.05L-95.79,-66.62L-95.74,-66.69L-96.04,-66.94L-95.4,-66.95L-95.26,-67.26L-95.46,-67.61L-95.65,-67.74L-95.46,-68.02L-94.74,-68.07L-93.45,-68.62L-93.64,-68.63L-93.68,-68.89L-93.85,-69L-94.06,-68.78L-94.6,-68.8L-94.56,-68.91L-94.08,-69.12L-94.26,-69.15L-94.25,-69.31L-93.62,-69.42L-93.82,-69.25L-93.75,-69.23L-93.43,-69.38L-93.65,-69.52L-94.27,-69.46L-94.63,-69.65L-94.82,-69.58L-96.05,-69.83L-96.49,-70.12L-96.55,-70.33L-96.23,-70.54L-95.88,-70.55L-95.99,-70.62L-95.89,-70.69L-96.36,-70.68L-96.55,-70.81L-96.52,-71.13L-96.41,-71.27L-96.06,-71.41L-95.56,-71.34L-95.41,-71.49L-95.87,-71.57L-95.2,-71.9L-94.56,-71.98L-94.31,-71.76ZM-80.73,-52.75L-82.04,-53.05L-81.85,-53.19L-81.14,-53.21L-80.77,-52.92L-80.73,-52.75ZM-73.62,-67.78L-74.48,-67.8L-74.75,-68.02L-74.38,-68.09L-73.49,-68L-73.41,-67.79L-73.62,-67.78ZM-77.88,-63.47L-77.7,-63.43L-77.53,-63.23L-77.94,-63.11L-78.54,-63.42L-77.88,-63.47ZM-82,-62.95L-81.96,-62.83L-82.11,-62.65L-83.02,-62.21L-83.7,-62.16L-83.91,-62.43L-83.38,-62.9L-82,-62.95ZM-79.55,-62.41L-79.27,-62.19L-79.67,-61.64L-79.82,-61.59L-80.27,-61.82L-80.26,-62.11L-80.02,-62.34L-79.55,-62.41ZM-104.56,-77.14L-105.22,-77.18L-106.07,-77.73L-105.59,-77.74L-105.29,-77.64L-104.96,-77.42L-104.54,-77.34L-104.45,-77.25L-104.56,-77.14ZM-95.48,-77.79L-93.58,-77.77L-93.13,-77.66L-93.34,-77.63L-93.54,-77.47L-95.99,-77.48L-96.26,-77.59L-96.19,-77.7L-95.48,-77.79ZM-98.79,-79.98L-98.79,-79.79L-98.95,-79.72L-99.52,-79.89L-100,-79.88L-100.13,-80L-100.05,-80.09L-99.73,-80.14L-99.02,-80.11L-98.79,-79.98ZM-89.83,-77.27L-90.23,-77.21L-90.99,-77.33L-91.15,-77.39L-91.18,-77.56L-90.84,-77.65L-90.17,-77.59L-89.72,-77.44L-89.71,-77.31L-89.83,-77.27ZM-93.54,-75.03L-93.46,-74.86L-93.57,-74.67L-94.53,-74.64L-96.6,-75.03L-95.95,-75.44L-94.88,-75.63L-93.91,-75.42L-93.5,-75.14L-93.54,-75.03ZM-109.82,-78.65L-109.36,-78.49L-109.35,-78.37L-109.48,-78.32L-110.42,-78.29L-111.17,-78.39L-111.52,-78.27L-112.13,-78.37L-113.29,-78.33L-110.88,-78.74L-109.82,-78.65ZM-118.33,-75.58L-118.82,-75.52L-119.39,-75.62L-118.63,-75.91L-117.63,-76.12L-117.5,-76.08L-117.63,-75.97L-118.33,-75.58ZM-105.29,-72.92L-106.18,-73.3L-106.95,-73.51L-106.61,-73.7L-105.51,-73.77L-104.65,-73.61L-104.56,-73.54L-104.62,-73.31L-105.29,-72.92ZM-100,-73.95L-99.16,-73.73L-97.67,-73.89L-97.11,-73.79L-97,-73.67L-97.63,-73.5L-97.35,-73.48L-97.27,-73.39L-97.8,-73.29L-98.43,-72.96L-97.64,-73.03L-97.08,-72.76L-97.13,-72.63L-96.54,-72.7L-96.47,-72.43L-96.8,-72.32L-96.59,-72.2L-96.77,-72.05L-96.62,-71.97L-96.61,-71.83L-97.58,-71.63L-98.18,-71.66L-98.32,-71.85L-98.46,-71.77L-98.2,-71.44L-98.66,-71.3L-99.17,-71.37L-99.73,-71.76L-100.59,-72.15L-101.21,-72.32L-101.72,-72.31L-102.66,-72.72L-102.71,-72.78L-102.55,-72.98L-102.2,-73.08L-101.92,-73.06L-101.27,-72.72L-100.48,-72.77L-100.4,-72.98L-100.13,-72.91L-100.24,-73.1L-100.54,-73.2L-100.34,-73.27L-99.83,-73.21L-100.37,-73.36L-100.89,-73.28L-101.52,-73.49L-100.98,-73.6L-100.52,-73.45L-100.61,-73.58L-100.95,-73.69L-100.96,-73.79L-99.99,-73.8L-99.91,-73.85L-100.23,-73.89L-100,-73.95ZM-84.92,-65.26L-84.5,-65.46L-84.08,-65.22L-83.49,-65.13L-83.2,-64.96L-82.05,-64.64L-81.68,-64.21L-81.89,-64.02L-80.83,-64.09L-80.57,-63.93L-80.67,-63.9L-80.26,-63.8L-81.05,-63.46L-82.38,-63.71L-82.47,-63.93L-83.03,-64.02L-83.07,-64.16L-83.3,-64.14L-83.58,-64.06L-83.73,-63.81L-84.31,-63.59L-84.63,-63.31L-85.39,-63.12L-85.5,-63.14L-85.77,-63.7L-87.15,-63.59L-87.19,-63.67L-86.93,-63.9L-86.25,-64.14L-86.37,-64.57L-86.07,-65.53L-85.81,-65.83L-85.55,-65.92L-85.24,-65.8L-85.11,-65.62L-85.24,-65.51L-84.92,-65.26ZM-75.68,-68.32L-75.08,-68.17L-75.09,-67.63L-75.2,-67.46L-75.78,-67.28L-76.69,-67.24L-77,-67.27L-77.22,-67.51L-77.31,-67.71L-77.23,-67.85L-76.74,-68.23L-75.68,-68.32ZM-79.54,-73.65L-78.29,-73.67L-77.21,-73.5L-76.29,-73.08L-76.31,-73L-76.09,-72.88L-76.4,-72.82L-78.31,-72.88L-79.32,-72.76L-79.82,-72.83L-79.98,-72.89L-80.18,-73.22L-80.78,-73.33L-80.82,-73.43L-80.74,-73.48L-80.86,-73.59L-80.85,-73.72L-80.41,-73.77L-79.54,-73.65ZM-97.7,-76.47L-97.74,-76.34L-97.53,-76.11L-97.65,-75.98L-97.6,-75.85L-97.89,-75.76L-97.41,-75.67L-97.34,-75.42L-97.65,-75.51L-97.88,-75.42L-97.85,-75.26L-97.66,-75.15L-98.07,-75.2L-97.99,-75.05L-100.29,-75.03L-100.48,-75.19L-100.15,-75.25L-100.73,-75.35L-100.71,-75.41L-99.19,-75.7L-102.54,-75.51L-102.8,-75.6L-102.14,-75.88L-100.97,-75.8L-101.29,-75.79L-101.51,-75.92L-101.43,-75.99L-101.82,-76.04L-101.86,-76.1L-101.56,-76.24L-102.14,-76.28L-101.79,-76.45L-101.34,-76.41L-101.06,-76.25L-99.87,-75.92L-99.69,-75.96L-100.11,-76.12L-99.54,-76.15L-100.41,-76.24L-99.98,-76.31L-100.82,-76.44L-100.89,-76.48L-100.83,-76.52L-99.81,-76.63L-99.17,-76.45L-98.89,-76.47L-99.02,-76.61L-98.71,-76.69L-97.7,-76.47ZM-103.43,-79.32L-102.91,-79.23L-102.65,-79.1L-102.73,-78.97L-102.58,-78.88L-102.39,-79.01L-101.7,-79.08L-101.04,-78.94L-101.13,-78.8L-100.44,-78.82L-100.01,-78.73L-99.58,-78.56L-99.85,-78.44L-99.75,-78.3L-99.13,-78.12L-99,-78L-99.17,-77.86L-99.96,-77.79L-100.59,-77.89L-101.07,-78.19L-102.61,-78.25L-102.77,-78.31L-102.73,-78.37L-103.95,-78.26L-104.76,-78.35L-104.99,-78.47L-104.91,-78.55L-103.57,-78.54L-103.48,-78.59L-103.59,-78.62L-104.02,-78.63L-103.37,-78.74L-104.19,-78.78L-103.88,-78.9L-104.15,-78.99L-104.9,-78.81L-104.97,-78.86L-104.75,-79.03L-105.57,-79.06L-105.44,-79.3L-103.43,-79.32ZM-91.89,-81.13L-90.68,-80.69L-90.64,-80.59L-89.24,-80.51L-89.13,-80.44L-89.2,-80.26L-88.86,-80.17L-88.2,-80.11L-88.61,-80.26L-88.64,-80.39L-88.52,-80.42L-87.67,-80.37L-87.63,-80.19L-87.92,-80.1L-87.2,-80.04L-86.98,-79.89L-87.3,-79.58L-86.34,-79.63L-86.01,-79.48L-85.65,-79.61L-85.04,-79.28L-86.96,-78.97L-87.62,-78.68L-87.92,-78.75L-87.95,-78.92L-87.82,-79.04L-88.04,-79L-88.16,-78.93L-88.25,-78.67L-88,-78.62L-87.98,-78.54L-88.15,-78.48L-88.74,-78.58L-88.61,-78.39L-88.82,-78.19L-89.1,-78.21L-90.04,-78.61L-90.08,-78.55L-89.53,-78.16L-90.3,-78.33L-90.65,-78.31L-90.33,-78.18L-90.61,-78.15L-91.9,-78.24L-92.68,-78.39L-92.85,-78.46L-92.73,-78.49L-91.87,-78.54L-93.27,-78.61L-93.63,-78.75L-93.16,-78.78L-93.9,-78.87L-94.16,-78.99L-92.84,-79.16L-92.55,-79.28L-91.3,-79.37L-92.82,-79.45L-93.93,-79.29L-94.11,-79.32L-93.94,-79.39L-94.11,-79.4L-95.1,-79.29L-95.73,-79.42L-95.66,-79.53L-94.4,-79.74L-95.86,-79.67L-96.46,-79.85L-96.77,-80.14L-94.65,-80.05L-94.58,-80.14L-94.26,-80.19L-95.41,-80.14L-96.39,-80.32L-95.55,-80.37L-96.15,-80.55L-96.13,-80.69L-95.93,-80.72L-95.23,-80.69L-94.89,-80.57L-93.93,-80.56L-95.51,-80.84L-95.27,-81L-94.98,-81.05L-93.29,-81.1L-93.24,-81.16L-93.41,-81.21L-94.19,-81.24L-94.18,-81.34L-93.03,-81.35L-91.89,-81.13ZM-94.29,-76.91L-93.81,-76.91L-93.23,-76.77L-93.2,-76.67L-93.53,-76.45L-93,-76.62L-91.31,-76.68L-90.54,-76.5L-91.42,-76.46L-89.28,-76.3L-89.24,-76.24L-89.41,-76.19L-91.41,-76.22L-90.25,-76.05L-89.28,-75.8L-89.2,-75.76L-89.26,-75.7L-89.65,-75.57L-88.92,-75.45L-88.8,-75.5L-88.85,-75.62L-88.64,-75.66L-88.2,-75.51L-87.73,-75.58L-87.54,-75.48L-87.26,-75.62L-85.95,-75.4L-85.9,-75.44L-86.07,-75.5L-85.97,-75.53L-84.6,-75.65L-83.93,-75.82L-83.24,-75.75L-82.15,-75.83L-81.27,-75.76L-81,-75.64L-80.32,-75.63L-80.12,-75.56L-80.26,-75.48L-79.66,-75.45L-79.51,-75.26L-80.38,-75.03L-79.66,-75.02L-79.4,-74.92L-79.94,-74.83L-80.35,-74.9L-80.15,-74.8L-80.28,-74.58L-81.94,-74.47L-82.93,-74.57L-83.12,-74.69L-83.1,-74.82L-83.52,-74.9L-83.34,-74.76L-83.53,-74.59L-84.43,-74.51L-85.06,-74.61L-85.13,-74.52L-85.44,-74.6L-85.81,-74.5L-88.42,-74.49L-88.56,-74.57L-88.34,-74.78L-88.53,-74.83L-88.85,-74.69L-88.94,-74.79L-89.19,-74.74L-89.2,-74.64L-89.56,-74.55L-90.55,-74.61L-90.97,-74.72L-90.88,-74.82L-91.13,-74.74L-91.13,-74.65L-91.55,-74.66L-91.96,-74.79L-92.17,-75.05L-92.08,-75.12L-92.41,-75.3L-92.41,-75.41L-92.07,-75.66L-92.19,-75.85L-93.09,-76.35L-95.27,-76.26L-96.04,-76.49L-95.65,-76.58L-96.88,-76.74L-96.88,-76.8L-96.4,-76.8L-96.77,-76.89L-96.76,-76.97L-95.85,-77.07L-94.29,-76.91ZM-96.2,-78.53L-94.92,-78.39L-95.33,-78.23L-94.93,-78.08L-95.2,-77.97L-96.99,-77.81L-97.02,-77.91L-97.66,-78.09L-96.94,-78.15L-98.05,-78.33L-98.32,-78.48L-98.06,-78.56L-98.34,-78.75L-97.38,-78.78L-96.48,-78.67L-96.2,-78.53ZM-110.46,-78.1L-109.62,-78.06L-109.77,-77.96L-110.87,-77.83L-110.12,-77.72L-110.2,-77.52L-110.68,-77.45L-112.37,-77.36L-113.16,-77.53L-113.21,-77.58L-113.12,-77.63L-113.28,-77.81L-113.19,-77.91L-112.3,-78.01L-110.46,-78.1ZM-115.55,-77.36L-115.51,-77.29L-116.33,-77.14L-115.81,-76.94L-116.25,-76.9L-115.95,-76.71L-117,-76.53L-117.04,-76.37L-117.23,-76.28L-117.99,-76.41L-117.78,-76.78L-117.88,-76.81L-118.3,-76.74L-118.47,-76.55L-118.79,-76.51L-118.62,-76.37L-118.99,-76.14L-119.17,-76.13L-119.58,-76.33L-119.74,-76.12L-119.53,-76L-119.91,-75.86L-120.41,-75.83L-120.85,-76.18L-121.02,-76.02L-121.21,-75.98L-121.91,-76.03L-122.4,-75.94L-122.64,-76.01L-122.55,-76.08L-122.59,-76.16L-122.9,-76.13L-122.42,-76.39L-121.56,-76.45L-119.09,-77.31L-116.84,-77.34L-116.7,-77.38L-117.04,-77.47L-116.51,-77.55L-115.55,-77.36ZM-108.29,-76.06L-107.72,-76L-108.02,-75.8L-107.22,-75.89L-106.91,-75.68L-106.89,-75.78L-106.69,-75.81L-106.86,-75.93L-106.68,-76.02L-105.63,-75.95L-105.48,-75.7L-105.97,-75.13L-107.06,-74.93L-107.82,-75L-108.47,-74.95L-108.83,-75.06L-109.5,-74.88L-110.39,-74.81L-110.94,-74.64L-112.52,-74.42L-113.67,-74.45L-114.27,-74.6L-114.38,-74.67L-114.31,-74.72L-112.84,-74.98L-111.67,-75.02L-111.08,-75.2L-111.09,-75.26L-112.21,-75.13L-112.6,-75.21L-113.71,-75.07L-113.84,-75.11L-113.85,-75.26L-113.47,-75.42L-114.02,-75.43L-114.17,-75.24L-114.51,-75.28L-114.36,-75.17L-114.45,-75.09L-115.02,-74.98L-115.41,-75.11L-115.73,-74.97L-116.48,-75.17L-117,-75.16L-117.6,-75.27L-117.26,-75.46L-116.08,-75.49L-115.14,-75.68L-116.43,-75.59L-117.16,-75.64L-116.8,-75.77L-114.99,-75.9L-116.34,-75.88L-116.66,-75.96L-116.55,-76.02L-116.59,-76.1L-116.21,-76.19L-114.78,-76.17L-115.82,-76.27L-115.58,-76.44L-115,-76.5L-114.19,-76.45L-113.82,-76.21L-112.7,-76.2L-111.87,-75.94L-112.06,-75.83L-111.55,-75.82L-111.05,-75.55L-109.09,-75.51L-108.91,-75.59L-108.94,-75.7L-109.87,-75.93L-109.45,-76.02L-109.43,-76.11L-110.2,-76.29L-110.31,-76.4L-109.34,-76.76L-108.83,-76.82L-108.47,-76.74L-108.63,-76.59L-108.12,-76.23L-108.38,-76.12L-108.29,-76.06ZM-93.17,-74.16L-92.22,-73.97L-91.09,-74.01L-90.46,-73.91L-90.38,-73.82L-91.25,-73.3L-91.55,-73.24L-91.46,-73.15L-92.12,-72.75L-94.21,-72.76L-93.77,-72.67L-93.53,-72.5L-94.04,-72.03L-95.19,-72.03L-95.25,-72.5L-95.6,-72.88L-95.63,-73.7L-95.39,-73.76L-94.7,-73.66L-95.13,-73.88L-95.12,-73.99L-94.97,-74.04L-93.17,-74.16ZM-97.44,-69.64L-97.24,-69.67L-96.3,-69.34L-95.75,-68.9L-95.27,-68.83L-96.6,-68.46L-97.47,-68.54L-98.24,-68.74L-98.32,-68.84L-98.7,-68.8L-98.9,-68.93L-99.09,-68.86L-99.44,-68.92L-99.56,-69.03L-99.46,-69.13L-98.91,-69.17L-98.46,-69.33L-98.55,-69.57L-98.04,-69.46L-98.29,-69.63L-98.2,-69.8L-97.79,-69.86L-97.41,-69.74L-97.44,-69.64ZM-114.52,-72.59L-113.58,-72.65L-113.29,-72.95L-112.75,-72.99L-111.27,-72.71L-111.36,-72.57L-111.9,-72.36L-111.68,-72.3L-111.31,-72.45L-111.27,-72.36L-111.14,-72.37L-110.21,-72.66L-110.2,-72.76L-110.55,-72.86L-110.69,-72.94L-110.66,-73.01L-110.01,-72.98L-108.75,-72.55L-108.19,-71.72L-107.81,-71.63L-107.31,-71.89L-107.7,-72.15L-108.24,-73.15L-107.94,-73.22L-108.08,-73.28L-108.03,-73.35L-107.11,-73.19L-106.95,-73.28L-106.48,-73.2L-105.81,-73.01L-105.42,-72.79L-104.88,-71.98L-104.39,-71.58L-104.36,-71.38L-104.56,-71.13L-104.51,-71.06L-103.58,-70.63L-103.08,-70.51L-103,-70.54L-103.05,-70.66L-101.99,-70.29L-101.68,-70.28L-101.56,-70.14L-101.09,-70.14L-100.91,-69.81L-101.04,-69.67L-101.34,-69.71L-101.48,-69.85L-101.65,-69.7L-102.23,-69.84L-102.6,-69.72L-102.53,-69.62L-102.62,-69.55L-103.43,-69.67L-103.05,-69.47L-103.12,-69.2L-102.45,-69.48L-102.15,-69.49L-101.98,-69.43L-102.05,-69.26L-101.79,-69.18L-101.86,-69.02L-102.9,-68.82L-105.11,-68.92L-105.17,-68.96L-105.02,-69.08L-106.14,-69.16L-106.34,-69.22L-106.42,-69.41L-106.66,-69.44L-107.44,-69L-108.36,-68.93L-109.47,-68.68L-113.13,-68.49L-113.62,-68.84L-113.69,-69.2L-115.62,-69.28L-116.51,-69.42L-117.1,-69.8L-117.2,-70.05L-114.59,-70.31L-112.64,-70.23L-111.63,-70.31L-113.76,-70.69L-115.99,-70.59L-117.59,-70.63L-118.26,-70.89L-118.38,-70.97L-118.27,-71.03L-115.89,-71.38L-116.05,-71.42L-115.98,-71.47L-115.3,-71.49L-115.59,-71.55L-117.94,-71.39L-118.23,-71.47L-117.74,-71.66L-118.58,-71.65L-118.99,-71.76L-118.94,-71.99L-118.21,-72.26L-118.48,-72.43L-118.37,-72.53L-116.57,-73.05L-114.64,-73.37L-114.3,-73.33L-114.13,-73.23L-114.05,-72.96L-114.52,-72.59ZM-119.74,-74.11L-119.21,-74.2L-119.12,-74.02L-118.54,-74.24L-117.51,-74.23L-115.63,-73.67L-115.39,-73.5L-119.08,-72.64L-119.51,-72.3L-120.18,-72.21L-120.44,-71.63L-120.62,-71.51L-121.47,-71.39L-121.75,-71.44L-122.16,-71.27L-123.1,-71.09L-124.01,-71.68L-125.3,-71.97L-125.85,-71.98L-125.76,-72.14L-125.58,-72.18L-125.63,-72.25L-124.99,-72.59L-124.97,-72.84L-124.56,-72.94L-124.82,-73.06L-124.8,-73.13L-123.8,-73.77L-124.19,-73.9L-124.7,-74.35L-121.5,-74.55L-119.56,-74.23L-119.74,-74.11ZM-94.53,-75.75L-94.75,-75.77L-94.9,-75.93L-94.5,-75.99L-94.3,-75.79L-94.53,-75.75ZM-79.38,-51.95L-79.64,-52.01L-79.27,-52.09L-79.38,-51.95ZM-78.83,-56.15L-78.91,-56.13L-78.8,-56.38L-78.67,-56.44L-78.67,-56.26L-78.83,-56.15ZM-78.94,-56.27L-79.18,-55.89L-79.27,-55.92L-79.14,-56.14L-79.18,-56.21L-79.5,-55.87L-79.76,-55.81L-79.54,-56.13L-79.9,-55.87L-80.01,-55.91L-79.52,-56.33L-79.46,-56.54L-79.54,-56.18L-79.39,-56.28L-79.27,-56.6L-78.96,-56.42L-78.94,-56.27ZM-79.98,-56.21L-80.09,-56.21L-80.06,-56.29L-79.58,-56.47L-79.98,-56.21ZM-80.06,-59.77L-80.17,-59.76L-80.08,-59.85L-79.9,-59.85L-80.06,-59.77ZM-96.78,-72.94L-97.09,-73L-97.07,-73.13L-96.86,-73.19L-96.6,-73.07L-96.78,-72.94ZM-97.36,-74.53L-97.75,-74.51L-97.42,-74.63L-97.29,-74.58L-97.36,-74.53ZM-98.27,-73.87L-98.97,-73.81L-99.42,-73.9L-97.8,-74.11L-97.66,-74.07L-97.75,-74.01L-98.27,-73.87ZM-90.2,-69.42L-90.3,-69.26L-90.49,-69.37L-90.2,-69.42ZM-90.49,-69.22L-90.77,-69.34L-90.6,-69.37L-90.49,-69.22ZM-74,-62.62L-74.63,-62.71L-74,-62.62ZM-74.88,-68.35L-75.31,-68.47L-75.4,-68.59L-75.29,-68.69L-74.98,-68.65L-74.8,-68.46L-74.88,-68.35ZM-78.53,-60.73L-78.67,-60.72L-78.61,-60.77L-78.24,-60.82L-78.53,-60.73ZM-78.98,-68.19L-79.17,-68.23L-79.15,-68.34L-78.87,-68.31L-78.98,-68.19ZM-76.68,-63.39L-77.36,-63.59L-77.13,-63.68L-76.65,-63.5L-76.68,-63.39ZM-64.82,-62.56L-64.42,-62.49L-64.55,-62.39L-64.84,-62.41L-64.96,-62.46L-64.82,-62.56ZM-62.68,-67.06L-62.87,-67.06L-62.63,-67.18L-62.4,-67.18L-62.68,-67.06ZM-68.23,-60.24L-68.37,-60.31L-68.14,-60.56L-67.98,-60.57L-67.82,-60.45L-68.23,-60.24ZM-70.34,-62.55L-70.77,-62.6L-71.22,-62.87L-70.44,-62.73L-70.27,-62.58L-70.34,-62.55ZM-64.83,-61.37L-65.39,-61.56L-65.43,-61.65L-64.79,-61.66L-64.67,-61.59L-64.83,-61.37ZM-67.91,-69.54L-68.22,-69.62L-67.83,-69.67L-67.75,-69.63L-67.91,-69.54ZM-79.43,-69.79L-79.36,-69.71L-79.55,-69.63L-80.05,-69.63L-79.98,-69.51L-80.79,-69.69L-80.42,-69.8L-79.43,-69.79ZM-78.03,-69.71L-77.97,-69.64L-78.04,-69.61L-78.85,-69.48L-78.58,-69.64L-78.03,-69.71ZM-77.64,-63.99L-77.97,-63.99L-77.64,-63.99ZM-83.12,-66.28L-82.93,-66.26L-83.06,-66.2L-83.21,-66.28L-83.12,-66.28ZM-79.21,-68.85L-79.39,-68.94L-78.66,-69.26L-78.65,-69.35L-78.33,-69.39L-78.23,-69.3L-78.85,-68.92L-79.21,-68.85ZM-77,-69.14L-77.32,-69.19L-77.34,-69.4L-76.68,-69.38L-77,-69.14ZM-65.03,-61.88L-64.85,-61.76L-65.17,-61.8L-65.21,-61.93L-65.03,-61.88ZM-86.91,-70.11L-86.56,-70.08L-86.52,-70.02L-86.73,-69.98L-87.32,-70.08L-86.91,-70.11ZM-83.73,-65.8L-83.23,-65.72L-83.33,-65.63L-83.79,-65.67L-83.7,-65.76L-83.81,-65.79L-84.12,-65.77L-84.14,-65.92L-84.47,-66.09L-83.79,-65.97L-83.7,-65.92L-83.73,-65.8ZM-86.6,-67.74L-86.89,-67.84L-86.85,-68.01L-86.96,-68.1L-86.7,-68.31L-86.42,-68.18L-86.4,-67.89L-86.6,-67.74ZM-84.67,-65.58L-85.1,-65.76L-85.15,-66.02L-84.94,-66.01L-84.76,-65.86L-84.6,-65.66L-84.67,-65.58ZM-102.23,-76.01L-102.01,-75.94L-102.58,-75.78L-103.31,-75.76L-103.04,-75.92L-103.77,-75.89L-103.99,-75.93L-103.8,-76.04L-104.41,-76.11L-104.01,-76.22L-102.73,-76.31L-102.58,-76.28L-102.49,-76.1L-102.23,-76.01ZM-101.23,-76.58L-101.61,-76.6L-100.96,-76.73L-100.27,-76.73L-101.23,-76.58ZM-104.02,-76.58L-103.72,-76.6L-103.03,-76.43L-103.47,-76.33L-104.36,-76.33L-104.59,-76.61L-104.07,-76.67L-103.96,-76.64L-104.02,-76.58ZM-103,-78.15L-103.27,-78.17L-102.89,-78.27L-102.79,-78.22L-103,-78.15ZM-101.69,-77.7L-102.38,-77.73L-102.47,-77.87L-101.19,-77.83L-101,-77.74L-101.69,-77.7ZM-89.73,-76.51L-90.16,-76.52L-90.56,-76.75L-89.95,-76.84L-89.7,-76.74L-89.82,-76.63L-89.73,-76.51ZM-96.08,-75.51L-96.86,-75.37L-97.02,-75.47L-96.37,-75.65L-95.96,-75.55L-96.08,-75.51ZM-95.31,-74.51L-95.85,-74.58L-95.51,-74.64L-95.31,-74.51ZM-113.83,-77.75L-114.61,-77.77L-115.03,-77.97L-114.33,-78.08L-113.62,-77.83L-113.83,-77.75ZM-121.08,-75.75L-121.22,-75.78L-120.89,-75.93L-121.08,-75.75ZM-113.56,-76.74L-114.84,-76.79L-113.89,-76.89L-113.52,-76.83L-113.56,-76.74ZM-104.12,-75.04L-104.89,-75.15L-104.47,-75.41L-104.07,-75.42L-103.8,-75.35L-103.64,-75.16L-104.12,-75.04ZM-55.46,-51.54L-55.58,-51.39L-56.03,-51.33L-56,-51.2L-55.82,-51.19L-55.8,-51.03L-56.73,-50.01L-56.82,-49.61L-56.18,-50.11L-56.16,-49.94L-55.93,-50.02L-55.5,-49.98L-56.14,-49.62L-55.87,-49.67L-56.09,-49.45L-55.38,-49.49L-55.34,-49.37L-55.23,-49.51L-55.35,-49.08L-55.18,-49.24L-54.5,-49.53L-54.45,-49.33L-54.32,-49.42L-53.96,-49.44L-53.62,-49.32L-53.57,-49.14L-54.16,-48.79L-53.85,-48.81L-53.97,-48.71L-53.71,-48.66L-53.79,-48.53L-54.11,-48.39L-53.03,-48.63L-53.14,-48.4L-53.61,-48.21L-53.57,-48.09L-53.87,-48.02L-53.64,-48.01L-53.86,-47.79L-53.67,-47.65L-53.28,-48L-52.87,-48.11L-53.15,-47.73L-53.17,-47.51L-53.12,-47.46L-52.95,-47.55L-52.78,-47.77L-52.65,-47.55L-53.07,-46.68L-53.59,-46.64L-53.6,-47.15L-54.01,-46.84L-54.17,-46.88L-53.85,-47.44L-53.99,-47.76L-54.19,-47.86L-54.49,-47.4L-54.56,-47.38L-54.47,-47.55L-54.86,-47.39L-55.32,-46.91L-55.79,-46.87L-55.95,-46.93L-55.92,-47.02L-55.49,-47.16L-55.19,-47.45L-54.78,-47.66L-55.37,-47.66L-55.43,-47.5L-55.58,-47.47L-56.13,-47.5L-55.87,-47.59L-55.86,-47.82L-56.77,-47.56L-58.34,-47.73L-58.94,-47.58L-59.26,-47.63L-59.34,-47.93L-58.33,-48.52L-59.17,-48.56L-58.84,-48.75L-58.91,-48.65L-58.72,-48.6L-58.4,-49.08L-57.99,-48.99L-58.1,-49.08L-57.98,-49.23L-58.19,-49.26L-58.21,-49.39L-58.02,-49.54L-57.79,-49.49L-57.93,-49.7L-57.43,-50.51L-57.18,-50.61L-57.3,-50.7L-57.05,-50.86L-57.04,-51.01L-56.68,-51.33L-56.03,-51.57L-55.69,-51.47L-55.67,-51.58L-55.46,-51.54ZM-54.55,-49.59L-54.79,-49.5L-54.86,-49.58L-54.55,-49.59ZM-54.09,-49.74L-53.98,-49.66L-54.29,-49.6L-54.28,-49.71L-54.09,-49.74ZM-56.27,-46.84L-56.38,-46.82L-56.36,-47.1L-56.29,-47.07L-56.27,-46.84ZM-100.22,-68.81L-100.4,-68.72L-100.6,-68.77L-100.61,-68.99L-100.33,-69L-100.18,-68.9L-100.22,-68.81ZM-99.99,-69.01L-100.14,-68.97L-100.25,-69.05L-100.15,-69.13L-99.99,-69.01ZM-100.31,-70.5L-100.62,-70.55L-100.68,-70.65L-100.28,-70.59L-100.31,-70.5ZM-95.51,-69.57L-95.38,-69.51L-95.5,-69.35L-95.73,-69.35L-95.67,-69.44L-95.76,-69.56L-95.89,-69.35L-95.99,-69.39L-95.88,-69.61L-95.51,-69.57ZM-101.17,-69.4L-101.27,-69.39L-101.21,-69.48L-101.35,-69.56L-101.03,-69.5L-101.17,-69.4ZM-101.85,-68.59L-102.31,-68.68L-102.01,-68.83L-101.83,-68.8L-101.72,-68.72L-101.85,-68.59ZM-104.54,-68.41L-105.05,-68.56L-104.6,-68.56L-104.44,-68.47L-104.54,-68.41ZM-107.9,-67.4L-107.95,-67.32L-108.15,-67.43L-108.13,-67.63L-107.99,-67.62L-107.9,-67.4ZM-109.17,-67.98L-108.89,-67.9L-109.17,-67.98ZM-108.09,-67.01L-107.81,-67L-107.94,-66.86L-108.09,-67.01ZM-61.74,-57.55L-61.64,-57.42L-62.01,-57.55L-61.74,-57.55ZM22.18,-60.37L22.42,-60.3L22.31,-60.27L22.36,-60.17L22.08,-60.29L22.18,-60.37ZM-64.41,-60.37L-64.44,-60.3L-64.74,-60.38L-64.84,-60.5L-64.65,-60.51L-64.41,-60.37ZM24.85,-64.99L24.58,-64.98L24.58,-65.04L24.97,-65.06L24.85,-64.99ZM29.96,-69.8L29.74,-69.79L29.84,-69.91L30.06,-69.84L29.96,-69.8ZM8.1,-63.34L7.8,-63.41L8.07,-63.47L8.1,-63.34ZM8.47,-63.67L8.29,-63.69L8.81,-63.77L8.47,-63.67ZM12.51,-65.9L12.43,-65.94L12.55,-66L12.78,-65.99L12.51,-65.9ZM12.42,-66.04L12.33,-66.04L12.46,-66.19L12.62,-66.18L12.58,-66.07L12.42,-66.04ZM19.77,-70.22L20.09,-70.1L19.78,-70.08L19.6,-70.27L19.77,-70.22ZM23.44,-70.82L22.83,-70.54L22.36,-70.51L21.99,-70.66L23.44,-70.82ZM20.78,-70.09L20.41,-70.12L20.65,-70.23L20.82,-70.21L20.78,-70.09ZM25.59,-71.14L26.15,-71.04L25.58,-70.96L25.32,-71.05L25.59,-71.14ZM23.62,-70.55L23.64,-70.46L23.27,-70.3L22.92,-70.38L23.55,-70.62L23.62,-70.55ZM24.02,-70.57L23.83,-70.53L23.66,-70.68L23.78,-70.75L23.96,-70.7L24.08,-70.65L24.02,-70.57ZM13.87,-68.27L14.12,-68.25L14.03,-68.19L13.23,-68L13.2,-68.09L13.3,-68.16L13.87,-68.27ZM12.97,-67.87L12.82,-67.82L12.96,-68.02L13.12,-68.05L12.97,-67.87ZM17.5,-69.6L18,-69.5L18.08,-69.4L17.94,-69.33L17.95,-69.2L17.49,-69.2L17.08,-69.01L16.81,-69.07L16.97,-69.14L17,-69.36L17.36,-69.38L17.23,-69.48L17.5,-69.6ZM19.26,-70.07L19.59,-69.97L19.01,-69.76L18.78,-69.58L18.06,-69.6L18.35,-69.77L18.67,-69.78L18.69,-69.89L19.05,-70.04L19.13,-70.24L19.21,-70.25L19.26,-70.07ZM15.76,-68.56L16.06,-68.68L16.15,-68.84L16.48,-68.8L16.52,-68.63L15.98,-68.4L14.26,-68.19L14.59,-68.4L15.1,-68.44L15.41,-68.62L15.56,-68.87L15.44,-68.92L15.48,-69.04L15.97,-69.3L16.11,-69.22L15.81,-69.02L15.93,-68.73L15.76,-68.56ZM15.21,-68.94L15.4,-68.78L15.22,-68.62L14.52,-68.63L14.37,-68.71L14.55,-68.82L14.8,-68.79L14.87,-68.91L15.04,-68.89L15.04,-69L15.21,-68.94ZM11.23,-64.87L10.74,-64.87L11.02,-64.98L11.23,-64.87ZM5.09,-60.31L5.09,-60.19L5,-60.2L4.96,-60.45L5.09,-60.31ZM-79.06,-75.93L-79.36,-75.83L-79.7,-75.88L-79.01,-76.15L-78.85,-76.11L-79.06,-75.93ZM-71.67,-77.33L-72.49,-77.39L-71.98,-77.46L-71.43,-77.39L-71.67,-77.33ZM-44.86,-82.08L-46.75,-82.35L-47.35,-82.6L-46.4,-82.69L-44.92,-82.48L-44.75,-82.4L-44.86,-82.08ZM-18.66,-81.85L-19.03,-81.83L-19.59,-81.99L-19.61,-82.08L-19.31,-82.12L-18.66,-81.85ZM-17.61,-79.83L-18.04,-79.71L-18.66,-79.72L-19.14,-79.85L-19,-79.94L-17.98,-80.06L-17.47,-80.03L-17.4,-79.94L-17.61,-79.83ZM-19,-77.97L-19.13,-77.94L-19.31,-78.34L-18.94,-78.42L-18.88,-78.11L-19,-77.97ZM-18.58,-76.04L-18.7,-76.02L-19.09,-76.43L-19.06,-76.69L-18.73,-76.64L-18.58,-76.04ZM-18,-75.41L-17.89,-75.2L-17.5,-75.15L-17.39,-75.04L-18.67,-75L-18.89,-75.07L-18.86,-75.32L-18,-75.41ZM-17.95,-77.64L-18.15,-77.64L-18.17,-77.71L-17.9,-77.86L-17.68,-77.86L-17.64,-77.78L-17.73,-77.71L-17.95,-77.64ZM-29.95,-83.56L-25.8,-83.26L-31.99,-83.09L-32.03,-82.98L-29.96,-83.11L-27,-83.07L-25.12,-83.16L-24.47,-82.88L-21.69,-82.68L-21.52,-82.6L-21.62,-82.55L-23.12,-82.32L-29.58,-82.16L-29.89,-82.05L-29.81,-81.96L-29.54,-81.94L-27.84,-82.05L-25.15,-82L-24.59,-81.88L-24.29,-81.7L-23.5,-81.77L-23.1,-82.01L-21.34,-82.07L-21.13,-81.93L-21.23,-81.6L-21.72,-81.35L-23.07,-80.93L-23.2,-80.85L-23.12,-80.78L-22.83,-80.91L-20.89,-81.28L-19.63,-81.64L-19.22,-81.64L-19.15,-81.51L-17.46,-81.4L-16.12,-81.78L-14.24,-81.81L-12.43,-81.68L-11.43,-81.46L-13.13,-81.09L-14.45,-80.99L-14.23,-80.87L-14.5,-80.76L-16.76,-80.57L-15.94,-80.43L-16.49,-80.25L-18.07,-80.17L-19.43,-80.26L-20.15,-80.01L-20.18,-79.86L-20.07,-79.77L-19.35,-79.73L-19.28,-79.68L-19.41,-79.35L-19.15,-79.33L-18.99,-79.18L-19.72,-79.07L-20.05,-78.84L-21.13,-78.66L-20.96,-78.56L-21.75,-77.79L-21.73,-77.71L-21.38,-77.7L-20.86,-77.91L-19.49,-77.72L-19.3,-77.62L-19.47,-77.57L-20.16,-77.69L-20.68,-77.62L-20.46,-77.45L-19.3,-77.22L-18.44,-77.26L-18.29,-77.13L-18.34,-76.92L-18.61,-76.76L-20.49,-76.92L-21.61,-76.69L-22.33,-76.79L-22.61,-76.68L-21.88,-76.57L-21.76,-76.4L-21.49,-76.27L-20.89,-76.3L-19.86,-76.12L-19.96,-76L-19.51,-75.76L-19.4,-75.49L-19.38,-75.3L-19.53,-75.18L-19.8,-75.16L-20.48,-75.31L-21.65,-75.02L-22.23,-75.12L-21.7,-74.96L-20.99,-75.07L-20.8,-74.81L-21.04,-74.65L-20.86,-74.64L-20.61,-74.73L-20.42,-74.98L-19.98,-74.98L-19.54,-74.62L-19.29,-74.55L-19.27,-74.34L-19.65,-74.26L-20.26,-74.28L-20.23,-74.2L-21.13,-74.11L-21.95,-74.24L-21.76,-74.48L-21.98,-74.57L-21.97,-74.39L-22.33,-74.29L-22.2,-74.21L-22.34,-74.06L-20.37,-73.85L-20.51,-73.49L-20.64,-73.46L-21.55,-73.43L-22.35,-73.27L-23.23,-73.4L-24.16,-73.76L-24.68,-73.6L-25.52,-73.85L-24.79,-73.51L-26.06,-73.25L-27.27,-73.44L-26.54,-73.25L-27.56,-73.14L-27.35,-73.07L-25.4,-73.28L-25.06,-73.4L-24.13,-73.41L-22.04,-72.92L-22.07,-72.4L-22.28,-72.34L-22.29,-72.12L-24.07,-72.5L-24.36,-72.69L-24.63,-73.04L-26.66,-72.72L-26.39,-72.67L-24.81,-72.9L-24.65,-72.58L-25.2,-72.39L-25.12,-72.35L-24.57,-72.42L-22.5,-71.91L-22.37,-71.77L-21.96,-71.74L-22.5,-71.5L-22.48,-71.38L-22.42,-71.25L-22.3,-71.43L-21.75,-71.48L-21.67,-70.86L-21.52,-70.53L-22.38,-70.46L-22.44,-70.86L-22.69,-70.44L-23.33,-70.45L-23.97,-70.65L-24.27,-71.05L-24.56,-71.22L-25.89,-71.57L-27.09,-71.63L-27.16,-71.6L-27.11,-71.53L-25.84,-71.48L-25.7,-71.37L-25.74,-71.18L-26.72,-70.95L-28.4,-70.99L-27.99,-70.9L-28.07,-70.7L-29.07,-70.44L-26.62,-70.46L-26.51,-70.4L-26.58,-70.36L-27.56,-70.12L-27.63,-70.03L-27.38,-69.99L-27.03,-70.2L-25.53,-70.35L-23.67,-70.14L-22.28,-70.13L-22.21,-70.11L-22.29,-70.03L-23.03,-69.9L-23.05,-69.79L-23.87,-69.74L-23.74,-69.59L-24.3,-69.59L-24.22,-69.48L-24.3,-69.44L-25.19,-69.26L-25.09,-69.17L-25.54,-69.05L-25.7,-68.89L-26.48,-68.68L-29.25,-68.3L-29.87,-68.31L-30.2,-68.2L-30.72,-68.25L-30.61,-68.12L-30.98,-68.06L-32.33,-68.44L-32.18,-68.26L-32.37,-68.21L-32.16,-67.99L-33.11,-67.66L-33.5,-67.38L-33.53,-67.26L-34.1,-66.73L-34.42,-66.63L-34.63,-66.43L-35.19,-66.25L-35.87,-66.44L-35.63,-66.14L-36.38,-65.83L-36.39,-65.96L-36.53,-66.01L-36.67,-65.79L-36.93,-65.78L-37.06,-65.87L-37.32,-65.79L-37.41,-65.66L-37.75,-65.59L-38,-65.71L-37.8,-65.86L-37.79,-65.98L-37.28,-66.3L-38.16,-66.39L-37.75,-66.26L-38.14,-65.9L-38.52,-66.01L-38.22,-65.84L-38.2,-65.71L-40.17,-65.56L-39.58,-65.34L-39.65,-65.29L-40.25,-65.05L-40.67,-65.11L-41.08,-65.1L-41.09,-65.04L-40.97,-64.87L-40.66,-64.92L-40.18,-64.48L-40.7,-64.33L-40.78,-64.22L-41.58,-64.3L-41.03,-64.12L-40.62,-64.13L-40.65,-63.93L-40.55,-63.73L-40.77,-63.63L-40.78,-63.53L-41.05,-63.51L-41.15,-63.35L-41.11,-63.27L-41.39,-63.06L-41.84,-63.07L-42.17,-63.21L-41.63,-62.97L-41.91,-62.74L-42.94,-62.72L-42.15,-62.57L-42.32,-62.15L-42.14,-62.01L-42.11,-61.86L-42.59,-61.72L-42.32,-61.68L-42.35,-61.62L-42.72,-60.77L-43.04,-60.52L-43.92,-60.6L-43.21,-60.39L-43.12,-60.06L-43.32,-59.93L-43.96,-60.03L-43.66,-59.86L-43.91,-59.82L-44.12,-59.83L-44.07,-59.92L-44.41,-59.92L-44.45,-60.01L-44.22,-60.27L-44.61,-60.02L-45.38,-60.2L-45.37,-60.37L-44.97,-60.46L-44.76,-60.66L-45.38,-60.44L-46.05,-60.62L-46.14,-60.78L-45.87,-61.22L-46.01,-61.1L-46.87,-60.82L-48.18,-60.77L-48.21,-60.86L-47.77,-61L-48.39,-61L-48.43,-61.19L-48.92,-61.28L-49.05,-61.52L-49.29,-61.59L-49.19,-61.69L-49.38,-61.89L-48.83,-62.08L-49.12,-62.11L-49.62,-62L-49.67,-62.15L-49.55,-62.23L-50.32,-62.47L-50.3,-62.72L-49.79,-63.04L-50.39,-62.82L-51.47,-63.64L-51.54,-63.76L-51.45,-63.9L-51.55,-64.01L-50.26,-64.21L-50.49,-64.21L-50.44,-64.31L-51.54,-64.1L-51.71,-64.21L-51.23,-64.56L-50.83,-64.56L-50.85,-64.64L-50.68,-64.68L-50.36,-64.68L-50.01,-64.45L-50.12,-64.7L-50.52,-64.77L-50.96,-65.2L-50.72,-64.8L-51.22,-64.63L-51.14,-64.79L-51.26,-64.76L-51.92,-64.22L-52.09,-64.42L-52.09,-64.68L-52.26,-65.15L-52.54,-65.33L-51.62,-65.71L-51.09,-65.78L-51.72,-65.72L-52.35,-65.46L-52.55,-65.46L-52.76,-65.59L-53.2,-65.59L-53.23,-65.77L-53.11,-65.98L-53.39,-66.05L-51.23,-66.88L-53.04,-66.2L-53.61,-66.15L-53.63,-66.41L-53.42,-66.65L-53.04,-66.83L-52.39,-66.88L-53.69,-66.99L-53.88,-67.14L-53.8,-67.42L-52.51,-67.76L-50.61,-67.53L-51.17,-67.69L-50.89,-67.78L-50.97,-67.81L-51.77,-67.74L-52.34,-67.84L-53.74,-67.55L-53.58,-67.84L-53.15,-68.21L-51.6,-68.05L-51.21,-68.33L-51.21,-68.42L-51.63,-68.27L-52.2,-68.22L-53.38,-68.3L-53.04,-68.61L-52.6,-68.71L-51.62,-68.53L-51.13,-68.6L-50.8,-68.79L-51.25,-68.74L-51.08,-69.13L-50.3,-69.17L-50.54,-69.25L-51.08,-69.21L-50.8,-69.66L-50.35,-69.8L-50.5,-69.94L-50.32,-70.03L-52.25,-70.06L-53.02,-70.3L-54.01,-70.42L-54.53,-70.7L-54.17,-70.82L-52.8,-70.75L-51.52,-70.44L-50.68,-70.4L-51.32,-70.59L-51.26,-70.85L-51.77,-71.01L-51.02,-71L-51.38,-71.12L-53.01,-71.18L-53.12,-71.31L-52.89,-71.46L-51.78,-71.68L-53.44,-71.58L-53.48,-71.64L-53.14,-71.81L-53.33,-71.79L-53.42,-72L-53.69,-72.16L-53.81,-72.29L-53.65,-72.36L-53.93,-72.32L-53.46,-71.89L-53.78,-71.68L-54.02,-71.66L-53.91,-71.53L-53.96,-71.46L-54.69,-71.37L-55.34,-71.43L-55.59,-71.55L-55.67,-71.69L-55.32,-72.11L-54.84,-72.36L-55.58,-72.18L-55.64,-72.3L-55.3,-72.35L-55.6,-72.45L-54.92,-72.57L-54.74,-72.7L-54.74,-72.87L-55.07,-73.02L-55.29,-72.93L-55.67,-73.01L-55.69,-73.11L-55.36,-73.2L-55.29,-73.33L-55.45,-73.46L-55.74,-73.38L-56.1,-73.56L-55.97,-73.76L-55.84,-73.76L-56.23,-74.13L-57.23,-74.13L-56.71,-74.22L-56.64,-74.28L-56.72,-74.43L-56.26,-74.53L-58.57,-75.35L-58.25,-75.51L-58.52,-75.69L-61.19,-76.16L-63.29,-76.35L-63.84,-76.22L-64.31,-76.32L-65.37,-76.13L-65.88,-76.24L-66.47,-76.14L-66.99,-76.21L-67.05,-76.15L-66.67,-75.98L-66.83,-75.97L-68.32,-76.09L-69.48,-76.4L-68.11,-76.65L-69.67,-76.74L-69.89,-76.83L-69.69,-76.99L-70.61,-76.82L-71.15,-77.07L-70.6,-77.19L-68.98,-77.2L-68.59,-77.34L-68.14,-77.38L-66.39,-77.28L-66.45,-77.39L-66.27,-77.52L-66.31,-77.56L-66.82,-77.69L-67.69,-77.52L-68.62,-77.6L-69.35,-77.47L-70.54,-77.7L-70.11,-77.84L-71.27,-77.81L-72.16,-77.96L-72.82,-78.19L-72.58,-78.28L-72.71,-78.36L-72.47,-78.48L-71.65,-78.62L-68.99,-78.86L-68.92,-78.88L-69.03,-78.94L-68.38,-79.04L-65.83,-79.17L-65.29,-79.44L-64.79,-80L-64.18,-80.1L-65.81,-80.02L-66.84,-80.08L-67.2,-80.22L-67,-80.41L-64.52,-81L-63.72,-81.06L-63.03,-80.89L-63.24,-81.08L-62.99,-81.21L-61.44,-81.13L-61.1,-81.4L-61.2,-81.75L-60.43,-81.92L-59.28,-81.88L-56.62,-81.36L-59.26,-82.01L-54.55,-82.35L-53.67,-82.16L-53.58,-82.06L-53.56,-81.65L-53.04,-81.87L-52.93,-82.04L-53.1,-82.12L-53.02,-82.32L-50.89,-81.9L-49.54,-81.92L-50.39,-82.12L-50.94,-82.38L-50.99,-82.46L-50.04,-82.47L-48.86,-82.41L-44.73,-81.78L-44.53,-81.85L-44.64,-82.1L-44.55,-82.26L-44.24,-82.37L-44.33,-82.47L-45.56,-82.75L-41.88,-82.68L-41.37,-82.75L-46.14,-82.86L-46.48,-82.95L-46.17,-83.06L-45.41,-83.02L-43.01,-83.26L-41.3,-83.1L-40.36,-83.33L-38.16,-83L-37.93,-83.16L-38.75,-83.37L-37.72,-83.5L-32.98,-83.6L-29.95,-83.56ZM171.1,-7.14L171.39,-7.11L171.1,-7.14ZM-145.49,16.33L-145.61,16.08L-145.49,16.33ZM-169.76,-56.64L-169.47,-56.59L-169.63,-56.55L-169.76,-56.64ZM-72.66,-20.04L-72.96,-20.06L-72.66,-20.04ZM178.86,-70.83L178.65,-71L178.68,-71.11L180,-71.54L180,-70.99L178.86,-70.83ZM17.98,-59.33L18.56,-59.39L18.62,-59.33L18.41,-59.29L18.29,-59.11L16.98,-58.65L16.21,-58.64L16.79,-58.59L16.92,-58.49L16.65,-58.43L16.77,-58.21L16.69,-57.92L16.56,-57.81L16.65,-57.5L16.48,-57.27L16.53,-57.07L16,-56.22L15.83,-56.12L14.71,-56.13L14.75,-56.03L14.56,-56.05L14.22,-55.83L14.34,-55.53L14.17,-55.4L12.89,-55.41L12.97,-55.75L12.47,-56.29L12.8,-56.26L12.66,-56.44L12.86,-56.45L12.88,-56.62L12.42,-56.91L12.05,-57.45L11.96,-57.43L11.88,-57.68L11.73,-57.72L11.7,-57.97L11.45,-58.12L11.43,-58.34L11.25,-58.37L11.15,-58.99L11.2,-59.08L11.39,-59.07L10.83,-59.18L10.64,-59.39L10.6,-59.76L10.57,-59.59L10.4,-59.52L10.43,-59.28L10.18,-59.01L9.84,-58.96L9.56,-59.11L9.66,-58.97L9.31,-58.86L9.4,-58.81L9.32,-58.75L8.17,-58.15L7.47,-58.02L7,-58.02L6.88,-58.15L6.73,-58.07L6.56,-58.12L6.66,-58.26L6.05,-58.38L5.59,-58.62L5.52,-58.82L5.61,-59.01L6.1,-58.87L6.36,-59L6.1,-58.95L5.89,-59.1L5.95,-59.3L6.42,-59.55L5.17,-59.16L5.24,-59.56L5.47,-59.71L5.77,-59.66L6.22,-59.82L5.73,-59.86L6.07,-60.08L6.14,-60.23L6.52,-60.41L6.53,-60.15L6.72,-60.42L7,-60.51L6.15,-60.35L5.88,-60.07L5.15,-59.64L5.21,-60.09L5.69,-60.12L5.29,-60.21L5.14,-60.45L5.65,-60.69L5.24,-60.57L5.12,-60.64L5.01,-61.04L6.78,-61.14L7.04,-60.95L7.04,-61.09L7.6,-61.21L7.35,-61.3L7.44,-61.43L7.28,-61.18L6.94,-61.16L6.6,-61.29L6.38,-61.13L5.32,-61.11L5.02,-61.25L5,-61.43L5.34,-61.49L4.93,-61.71L4.93,-61.88L5.47,-61.9L6.02,-61.79L6.73,-61.87L5.27,-61.94L5.1,-62.03L5.14,-62.16L5.36,-62.15L5.53,-62.31L5.91,-62.42L6.08,-62.35L6.58,-62.41L6.69,-62.47L6.14,-62.41L6.35,-62.61L7.57,-62.55L7.69,-62.59L7.54,-62.67L8.1,-62.73L6.73,-62.72L6.94,-62.93L7.57,-63.1L8.1,-63.09L8.62,-62.85L8.16,-63.16L8.27,-63.29L8.64,-63.34L8.36,-63.5L8.58,-63.6L9.14,-63.59L9.08,-63.5L9.16,-63.46L9.7,-63.62L10.02,-63.39L10.76,-63.46L10.67,-63.56L10.73,-63.62L11.37,-63.8L11.18,-63.9L11.46,-64L11.21,-64.03L10.91,-63.92L11.05,-63.85L10.93,-63.77L10.06,-63.51L9.92,-63.52L9.77,-63.7L9.59,-63.68L9.61,-63.79L10.57,-64.42L11.52,-64.74L11.63,-64.81L11.56,-64.82L11.3,-64.75L11.49,-64.98L12.16,-65.18L12.31,-65.09L12.74,-65.21L12.92,-65.34L12.42,-65.18L12.13,-65.28L12.12,-65.36L12.69,-65.9L13.03,-65.96L12.78,-66.1L13.67,-66.18L14.03,-66.3L13.12,-66.23L13.07,-66.43L13.21,-66.64L13.62,-66.79L13.96,-66.79L13.65,-66.91L14.11,-67.12L15.42,-67.2L14.44,-67.27L14.96,-67.57L15.59,-67.35L15.58,-67.44L15.69,-67.52L15.25,-67.6L15.3,-67.77L14.85,-67.66L14.78,-67.67L14.8,-67.81L15.13,-67.97L15.62,-67.95L15.32,-68.07L16.01,-68.23L16.31,-67.88L16.26,-68L16.39,-68.09L16.26,-68.14L16.2,-68.32L17.55,-68.43L16.51,-68.53L17.39,-68.8L17.7,-69.1L18.1,-69.16L18.08,-69.33L18.26,-69.47L18.86,-69.31L18.61,-69.49L18.99,-69.56L19.2,-69.75L19.69,-69.8L19.64,-69.42L19.96,-69.82L20.32,-69.95L20.34,-69.62L20.11,-69.34L20.49,-69.54L20.74,-69.52L20.53,-69.69L20.62,-69.91L21.16,-69.89L21.25,-70L21.43,-70.01L21.97,-69.83L21.8,-70.07L21.36,-70.23L22.32,-70.26L22.68,-70.37L22.94,-70.3L23.05,-70.1L23.35,-69.98L23.29,-70.1L23.38,-70.25L24.42,-70.7L24.26,-70.83L24.66,-71L25.26,-70.84L25.44,-70.91L25.77,-70.85L25.21,-70.49L24.99,-70.22L25.04,-70.11L25.42,-70.24L25.47,-70.34L26.51,-70.91L26.66,-70.94L26.73,-70.85L26.56,-70.67L26.64,-70.64L26.59,-70.41L26.99,-70.51L27.31,-70.8L27.55,-70.8L27.27,-70.91L27.33,-71L27.6,-71.09L28.14,-71.04L28.39,-70.98L28.38,-70.87L27.9,-70.68L28.27,-70.67L28.19,-70.25L28.61,-70.76L28.83,-70.86L29.74,-70.65L30.07,-70.7L30.24,-70.62L30.21,-70.54L30.93,-70.4L30.94,-70.27L30.26,-70.12L28.78,-70.15L29.6,-69.98L29.69,-69.74L30.09,-69.72L30.24,-69.86L30.43,-69.72L30.71,-69.8L31.55,-69.7L32,-69.81L31.98,-69.95L33.01,-69.72L32.92,-69.6L32.18,-69.67L32.09,-69.63L32.38,-69.48L33,-69.47L32.98,-69.37L33.45,-69.43L33.33,-69.15L33.14,-69.07L33.44,-69.13L33.68,-69.31L35.86,-69.19L37.73,-68.69L38.43,-68.36L38.83,-68.32L39.57,-68.07L39.82,-68.06L39.75,-68.16L39.81,-68.15L40.38,-67.83L40.97,-67.71L41.13,-67.27L41.36,-67.21L41.19,-66.83L40.1,-66.3L38.65,-66.07L35.51,-66.4L34.82,-66.61L34.48,-66.55L34.4,-66.61L34.45,-66.65L33.15,-66.84L32.85,-67.02L32.93,-67.09L31.9,-67.16L32.5,-67L32.46,-66.92L32.86,-66.72L33.18,-66.68L33.22,-66.53L33.66,-66.44L33.36,-66.33L34.11,-66.23L34.69,-65.95L34.78,-65.77L34.62,-65.51L34.41,-65.4L34.8,-64.99L34.83,-64.8L34.95,-64.76L34.86,-64.71L34.87,-64.56L35.04,-64.44L35.65,-64.38L36.15,-64.19L36.36,-64L37.44,-63.81L37.97,-63.95L38.06,-64.09L37.95,-64.32L37.18,-64.41L36.58,-64.79L36.53,-64.94L36.79,-64.99L36.88,-65.17L37.14,-65.19L38.01,-64.88L39.76,-64.58L40.06,-64.77L40.44,-64.78L39.8,-65.35L39.82,-65.6L40.69,-65.96L41.48,-66.12L42.21,-66.52L43.23,-66.42L43.65,-66.25L43.54,-66.12L43.84,-66.14L44.1,-66.01L44.1,-66.24L44.49,-66.67L44.43,-66.94L44.29,-67.1L43.78,-67.25L44.23,-68L44.2,-68.25L43.33,-68.67L44.05,-68.55L45.08,-68.58L45.89,-68.48L46.68,-67.97L46.69,-67.85L45.53,-67.76L44.9,-67.41L45.56,-67.19L45.89,-66.89L46.49,-66.8L47.66,-66.98L47.91,-67.45L47.87,-67.58L48.83,-67.68L48.88,-67.73L48.7,-67.87L48.75,-67.9L49.16,-67.87L50.7,-68.32L51.99,-68.54L52.29,-68.46L52.18,-68.37L52.4,-68.35L52.72,-68.48L52.34,-68.61L53.8,-69L54.49,-68.99L53.8,-68.91L53.97,-68.84L53.76,-68.63L53.93,-68.44L53.26,-68.27L54.48,-68.29L54.86,-68.2L54.92,-68.37L55.42,-68.57L56.04,-68.65L57.13,-68.55L58.17,-68.89L58.24,-68.83L59.06,-69.01L59.37,-68.74L59.11,-68.62L59.1,-68.44L59.73,-68.35L59.92,-68.47L59.9,-68.71L60.49,-68.73L60.93,-68.99L60.86,-69.15L60.66,-69.11L60.17,-69.59L60.91,-69.85L63.36,-69.68L64.19,-69.53L64.93,-69.33L64.9,-69.25L67,-68.87L67.73,-68.51L68.37,-68.31L68.5,-68.35L68.83,-68.57L69.14,-68.95L68.54,-68.97L68.12,-69.24L68.01,-69.48L67.62,-69.58L67.06,-69.69L66.9,-69.55L66.8,-69.74L66.93,-70.01L67.24,-70.11L67.15,-70.22L67.28,-70.74L67.14,-70.84L66.7,-70.82L66.67,-70.9L66.85,-71.06L66.64,-71.08L66.92,-71.28L68.27,-71.68L68.61,-72.01L69.04,-72.67L69.39,-72.96L69.69,-72.98L69.65,-72.9L69.74,-72.88L71.62,-72.9L72.81,-72.69L72.57,-72.01L72.28,-71.7L71.87,-71.46L72.58,-71.15L72.7,-70.96L72.7,-70.46L72.47,-70.27L72.6,-69.79L72.58,-68.97L73.55,-68.57L73.59,-68.48L73.14,-68.18L73.17,-67.97L73.07,-67.77L72.59,-67.59L71.85,-67.01L71.37,-66.96L71.54,-66.68L70.72,-66.52L70.38,-66.6L70.69,-66.75L70.28,-66.69L69.88,-66.85L69.01,-66.79L69.19,-66.58L69.98,-66.4L72.07,-66.25L72.32,-66.33L72.42,-66.56L73.79,-67L74.07,-67.41L74.77,-67.77L74.74,-68.07L74.39,-68.42L74.58,-68.75L75.12,-68.86L76.46,-68.98L77.24,-68.47L77.17,-67.78L77.77,-67.57L78.92,-67.59L77.59,-67.75L77.54,-68.01L77.66,-68.19L78,-68.26L77.65,-68.9L76,-69.24L75.42,-69.24L74.81,-69.09L73.98,-69.11L73.78,-69.2L73.89,-69.42L73.56,-69.71L73.58,-69.8L73.83,-70.18L74.34,-70.58L73.58,-71.22L73.09,-71.44L73.67,-71.85L74.99,-72.14L75.09,-72.26L75.06,-72.55L74.79,-72.81L75.37,-72.8L75.6,-72.58L75.59,-72.46L75.74,-72.3L75.27,-71.96L75.25,-71.81L75.5,-71.65L75.47,-71.53L75.28,-71.43L75.33,-71.34L75.73,-71.27L76.93,-71.13L77.59,-71.17L78.32,-70.93L79.02,-70.95L79.08,-71L78.49,-71.03L78.21,-71.27L77.48,-71.31L76.43,-71.55L76.03,-71.91L76.87,-72.03L77.55,-71.84L78.19,-71.91L78.23,-71.95L78.02,-72.09L77.49,-72.07L77.44,-72.16L78.48,-72.39L79.42,-72.38L80.76,-72.09L80.86,-71.97L81.66,-71.72L83.11,-71.72L83.23,-71.67L82.98,-71.45L82.32,-71.26L82.24,-71L82.34,-70.81L82.16,-70.6L82.22,-70.4L82.59,-70.89L82.87,-70.95L83.01,-70.9L83.03,-70.58L82.68,-70.22L83.08,-70.09L83.07,-70.28L83.5,-70.35L83.74,-70.55L83.15,-71.1L83.55,-71.54L83.53,-71.68L83.2,-71.87L82.65,-71.93L82.09,-72.27L80.83,-72.49L80.66,-72.71L80.84,-72.95L80.51,-73.09L80.42,-73.23L80.4,-73.36L80.6,-73.47L80.58,-73.57L85.2,-73.72L86.89,-73.89L87.03,-73.82L85.79,-73.44L85.82,-73.33L86.68,-73.11L85.97,-73.35L85.94,-73.46L87.12,-73.62L87.57,-73.81L87.21,-73.88L86.57,-74.24L86,-74.32L86.4,-74.45L86.9,-74.33L87.23,-74.36L86.43,-74.59L85.79,-74.65L86.2,-74.82L86.65,-74.68L86.86,-74.72L87.42,-74.94L87.47,-75.01L86.94,-75.07L87.01,-75.17L87.67,-75.13L90.18,-75.59L94.08,-75.91L92.89,-75.91L92.97,-76.08L93.1,-76.03L93.26,-76.1L95.58,-76.14L96.08,-76.08L95.65,-75.89L96.51,-76.01L96.6,-75.99L96.5,-75.89L97.35,-76.03L97.5,-75.98L98.66,-76.24L99.77,-76.03L99.44,-75.8L99.54,-75.8L99.85,-75.93L99.83,-76.14L98.87,-76.51L100.84,-76.53L101.6,-76.44L101.68,-76.49L100.93,-76.56L101.1,-76.7L100.92,-76.82L100.99,-76.99L102.61,-77.51L104.01,-77.73L105.71,-77.53L106.06,-77.39L104.2,-77.1L105.65,-77.1L105.82,-77L106.94,-77.03L107.43,-76.93L106.64,-76.57L106.38,-76.59L106.41,-76.51L107.72,-76.52L108.18,-76.74L111.11,-76.72L111.94,-76.55L112.09,-76.48L111.94,-76.38L112.62,-76.38L112.8,-76.13L112.66,-76.05L113.09,-76.13L113.15,-76.17L112.99,-76.24L113.27,-76.25L113.56,-75.89L113.86,-75.92L113.57,-75.57L113.39,-75.68L112.47,-75.84L112.96,-75.57L113.24,-75.61L113.73,-75.45L113.61,-75.29L112.92,-75.02L109.84,-74.32L109.91,-74.26L109.81,-74.17L109.08,-74.03L108.2,-73.69L107.27,-73.62L106.68,-73.33L106.19,-73.31L105.68,-72.96L105.14,-72.78L105.71,-72.84L106.48,-73.14L107.75,-73.17L110.77,-73.69L110.87,-73.73L110.72,-73.78L109.71,-73.74L109.67,-73.8L109.87,-73.93L110.26,-74.02L111.06,-73.94L111.13,-74.05L111.55,-74.03L111.23,-73.97L111.4,-73.83L112.15,-73.71L112.8,-73.75L112.94,-73.84L112.84,-73.96L113.03,-73.91L113.42,-73.65L113.16,-73.46L113.49,-73.35L113.47,-73.05L113.13,-72.83L113.31,-72.66L113.66,-72.63L113.22,-72.81L113.54,-73.05L113.56,-73.23L113.89,-73.35L113.51,-73.5L114.06,-73.58L115.34,-73.7L118.45,-73.59L118.94,-73.48L118.46,-73.46L118.38,-73.37L118.43,-73.25L119.75,-72.98L121.75,-72.97L122.54,-72.88L122.75,-72.91L122.53,-73.02L123.16,-72.95L123.62,-73.19L123.32,-73.43L123.42,-73.64L124.54,-73.75L125.62,-73.52L125.6,-73.45L126.25,-73.55L126.34,-73.51L126.29,-73.39L126.55,-73.33L127.03,-73.55L127.74,-73.48L128.28,-73.33L128.26,-73.27L129.1,-73.11L128.6,-72.9L129.02,-72.87L129.25,-72.71L128.42,-72.54L129.28,-72.44L129.41,-72.32L129.41,-72.17L129.28,-72.09L128.93,-72.08L127.73,-72.41L128.91,-71.76L129.12,-71.82L129.12,-71.95L129.21,-71.92L129.46,-71.74L128.84,-71.66L129.13,-71.59L129.76,-71.12L130.54,-70.89L130.76,-70.96L131.02,-70.75L131.56,-70.9L132.04,-71.24L132,-71.35L132.23,-71.64L132.65,-71.93L133.13,-71.61L133.69,-71.43L134.7,-71.39L135.56,-71.61L136.09,-71.62L137.12,-71.42L137.94,-71.13L137.84,-71.23L138.31,-71.33L137.92,-71.38L138.23,-71.6L138.78,-71.63L139.21,-71.44L139.98,-71.49L139.7,-71.7L139.72,-71.88L139.36,-71.95L140.19,-72.19L139.18,-72.16L139.14,-72.33L139.6,-72.5L141.08,-72.59L140.65,-72.84L140.81,-72.89L142.06,-72.72L143.52,-72.7L146.25,-72.44L146.23,-72.35L144.78,-72.38L144.17,-72.26L144.47,-72.17L146.83,-72.3L146.11,-71.94L146.01,-71.95L146.23,-72.14L145.76,-72.23L145.66,-72.07L145.76,-71.94L145.06,-71.93L144.99,-71.75L145.19,-71.7L146.07,-71.81L147.26,-72.33L148.4,-72.31L149.5,-72.16L149.96,-71.99L150.02,-71.9L149.05,-71.8L148.97,-71.69L150.06,-71.51L150.6,-71.52L150.67,-71.46L150.1,-71.23L150.97,-71.38L151.58,-71.29L152.09,-71.02L151.76,-70.98L152.51,-70.83L155.9,-71.1L157.45,-71.07L158.7,-70.94L159.35,-70.79L159.91,-70.51L160.01,-70.31L159.73,-69.87L159.83,-69.78L160.91,-69.61L161.04,-69.1L161.34,-68.91L161.13,-68.65L160.86,-68.54L161.1,-68.56L161.57,-68.91L161.48,-69.2L161.54,-69.38L162.17,-69.61L163.2,-69.71L163.95,-69.74L164.51,-69.61L166.82,-69.5L167.63,-69.74L167.86,-69.73L168.15,-69.58L168.3,-69.27L169.31,-69.08L169.61,-68.79L170.54,-68.83L171,-69.05L171,-69.13L170.58,-69.58L170.16,-69.63L170.5,-69.86L170.49,-70.11L172.56,-69.97L173.28,-69.82L173.44,-69.95L174.79,-69.86L175.92,-69.9L176.92,-69.65L178.85,-69.39L180,-68.98L180,-65.07L179.45,-64.82L178.52,-64.6L177.75,-64.72L176.88,-65.08L176.34,-65.05L177.04,-65L177.22,-64.86L177.07,-64.79L176.06,-64.96L175.78,-64.84L174.55,-64.68L175.68,-64.78L176.06,-64.9L176.35,-64.71L176.14,-64.59L177.39,-64.77L177.47,-64.74L177.43,-64.44L177.69,-64.3L178.04,-64.22L178.23,-64.36L178.48,-64.13L178.45,-64.01L178.65,-63.97L178.69,-63.84L178.73,-63.67L178.47,-63.57L178.65,-63.56L178.74,-63.39L178.79,-63.54L178.92,-63.35L179.33,-63.19L179.41,-63.08L179.26,-63.01L179.57,-62.77L179.48,-62.61L179.18,-62.47L179.12,-62.32L177.29,-62.6L177.34,-62.78L177.02,-62.78L176.96,-62.66L177.16,-62.56L176.7,-62.51L174.51,-61.82L173.82,-61.68L173.62,-61.72L173.13,-61.41L172.86,-61.47L172.91,-61.31L172.4,-61.17L172.39,-61.06L170.61,-60.43L170.35,-59.97L169.98,-60.07L169.62,-60.44L169.23,-60.6L168.14,-60.57L167.23,-60.41L166.27,-59.86L166.19,-59.85L166.14,-59.98L166.35,-60.48L165.08,-60.1L165.07,-59.95L164.95,-59.84L164.53,-60.06L164.11,-59.9L164.14,-59.98L163.74,-60.03L163.36,-59.78L163.27,-59.3L162.94,-59.11L162.97,-58.99L162.14,-58.45L161.96,-58.08L162.04,-57.92L162.41,-57.78L162.39,-57.72L162.65,-57.95L163.23,-57.79L163.19,-57.64L162.78,-57.36L162.76,-57.24L162.8,-56.81L163.26,-56.69L163.34,-56.23L163.05,-56.04L162.84,-56.07L162.63,-56.23L163.04,-56.52L162.67,-56.49L162.49,-56.4L162.53,-56.26L162.08,-56.09L161.72,-55.5L161.78,-55.21L162.11,-54.75L161.62,-54.52L161.13,-54.6L160.77,-54.54L160.07,-54.19L159.84,-53.78L160.03,-53.13L159.59,-53.24L158.75,-52.91L158.47,-53.03L158.43,-52.96L158.61,-52.87L158.48,-52.63L158.49,-52.38L158.1,-51.81L156.75,-50.97L156.52,-51.38L156.36,-52.51L156.11,-52.87L155.56,-55.2L155.72,-56.07L155.98,-56.7L156.85,-57.29L156.98,-57.47L156.79,-57.75L156.87,-57.8L157.45,-57.8L157.67,-58.02L158.28,-58.01L159.21,-58.52L159.85,-59.13L161.75,-60.15L162.07,-60.47L162.97,-60.78L163.71,-60.92L163.55,-61.03L164.01,-61.34L163.8,-61.46L164.02,-61.71L164.21,-62.29L164.6,-62.47L165.21,-62.37L165.21,-62.45L165.42,-62.45L164.42,-62.7L163.33,-62.55L163.02,-61.89L163.01,-61.79L163.26,-61.7L163.09,-61.57L162.99,-61.54L162.86,-61.71L162.39,-61.66L160.77,-60.75L160.17,-60.64L160.38,-61.03L159.79,-60.96L159.95,-61.13L159.88,-61.29L160.25,-61.65L160.31,-61.89L159.55,-61.72L159.19,-61.93L158.07,-61.75L157.47,-61.8L157.08,-61.68L156.68,-61.48L156.63,-61.27L156.06,-61L155.72,-60.68L154.97,-60.38L154.29,-59.83L154.15,-59.53L154.97,-59.45L155.17,-59.36L155.16,-59.19L154.7,-59.14L154.46,-59.22L154.01,-59.08L153.7,-59.22L153.36,-59.21L153.27,-59.09L152.82,-58.93L152.32,-59.03L152.09,-58.91L151.33,-58.88L151.12,-59.08L151.99,-59.16L152.26,-59.22L152.17,-59.28L151.8,-59.32L151.35,-59.56L150.48,-59.49L150.67,-59.56L149.64,-59.77L149.07,-59.63L149.2,-59.49L148.8,-59.53L148.74,-59.37L148.96,-59.37L148.73,-59.26L148.49,-59.26L148.26,-59.41L147.51,-59.27L146.54,-59.46L146.27,-59.22L146.05,-59.17L145.55,-59.41L143.87,-59.41L142.58,-59.24L142.03,-59L141.6,-58.65L140.79,-58.3L140.45,-57.81L140,-57.69L138.66,-56.97L137.69,-56.14L135.26,-54.94L135.26,-54.73L135.85,-54.58L136.8,-54.62L136.72,-53.8L137.16,-53.82L137.26,-54.03L137.1,-54.13L137.14,-54.18L137.67,-54.28L137.34,-54.1L137.83,-53.95L137.25,-53.55L137.95,-53.6L138.53,-53.96L138.57,-53.82L138.25,-53.52L138.45,-53.54L138.66,-53.74L138.7,-54.32L139.32,-54.19L139.8,-54.26L140.18,-54.05L140.35,-53.81L140.69,-53.6L141.37,-53.29L141.4,-53.18L141.18,-53.02L140.84,-53.09L141.26,-52.84L141.25,-52.55L141.13,-52.44L141.49,-52.18L141.37,-51.92L140.93,-51.62L140.52,-50.8L140.54,-50.13L140.62,-50.08L140.46,-49.91L140.52,-49.6L140.31,-49.05L140.38,-48.96L140.11,-48.42L139.37,-47.89L139,-47.38L138.59,-47.06L138.34,-46.54L137.69,-45.82L136.8,-45.17L136.14,-44.49L135.87,-44.37L135.48,-43.84L135.13,-43.53L134.01,-42.95L133.16,-42.7L132.71,-42.88L132.3,-42.88L132.31,-43.31L131.95,-43.1L131.87,-43.1L132.01,-43.28L131.79,-43.26L131.16,-42.63L130.71,-42.66L130.83,-42.52L130.73,-42.33L130.24,-42.18L129.76,-41.71L129.69,-41.59L129.77,-41.3L129.71,-40.86L129.34,-40.73L128.51,-40.13L127.97,-40L127.57,-39.78L127.55,-39.46L127.42,-39.37L127.39,-39.21L127.79,-39.08L128.33,-38.68L129.42,-37.06L129.4,-36.05L129.57,-36.05L129.56,-35.95L129.21,-35.18L128.51,-35.1L128.42,-35.02L128.44,-34.87L128.09,-34.93L128.04,-35.02L127.71,-34.95L127.64,-34.89L127.72,-34.72L127.4,-34.82L127.48,-34.63L127.32,-34.46L127.17,-34.55L127.25,-34.76L126.9,-34.44L126.75,-34.51L126.53,-34.31L126.48,-34.49L126.26,-34.67L126.52,-34.7L126.47,-34.76L126.59,-34.82L126.42,-34.82L126.29,-35.15L126.61,-35.57L126.49,-35.65L126.75,-35.87L126.54,-36.17L126.49,-36.69L126.18,-36.69L126.16,-36.77L126.49,-37.01L126.78,-36.95L126.87,-36.82L126.98,-36.94L126.75,-37.19L126.79,-37.29L126.56,-37.72L126.63,-37.78L126.37,-37.88L126.12,-37.74L126.05,-37.87L125.77,-37.99L125.36,-37.72L125.31,-37.84L124.99,-37.93L125.21,-38.08L124.69,-38.13L124.87,-38.23L125.07,-38.56L125.55,-38.69L125.17,-38.81L125.41,-39.29L125.36,-39.53L124.78,-39.76L124.64,-39.62L124.56,-39.79L124.35,-39.91L124.35,-40.01L124.11,-39.84L123.65,-39.88L123.58,-39.79L122.84,-39.6L122.33,-39.37L121.98,-39.05L121.68,-39L121.65,-38.87L121.16,-38.73L121.11,-38.92L121.68,-39.11L121.63,-39.22L121.82,-39.39L121.28,-39.38L121.27,-39.54L121.52,-39.64L121.52,-39.84L121.8,-39.95L122.26,-40.5L122.14,-40.69L121.86,-40.84L121.83,-40.97L121.73,-40.85L121.17,-40.9L120.48,-40.23L119.39,-39.75L119.22,-39.41L118.98,-39.18L118.3,-39.07L118.04,-39.23L117.78,-39.13L117.55,-38.69L117.66,-38.42L118.01,-38.18L118.8,-38.13L118.94,-38.04L119.09,-37.7L118.99,-37.64L118.95,-37.33L119.29,-37.14L119.76,-37.16L119.88,-37.35L120.31,-37.62L120.26,-37.68L120.75,-37.83L121.64,-37.46L121.96,-37.45L122.06,-37.53L122.34,-37.41L122.67,-37.4L122.45,-37.07L122.52,-36.95L122.34,-36.83L122.16,-36.96L121.93,-36.96L121.05,-36.61L120.81,-36.63L120.9,-36.44L120.71,-36.41L120.64,-36.13L120.39,-36.05L120.33,-36.23L120.18,-36.2L120.09,-36.12L120.28,-35.98L119.43,-35.3L119.17,-34.85L119.2,-34.75L119.35,-34.75L120.27,-34.27L120.5,-33.64L120.87,-33.02L120.85,-32.66L121.34,-32.43L121.4,-32.21L121.75,-31.99L121.86,-31.82L121.87,-31.7L121.68,-31.71L121.35,-31.86L120.97,-31.87L120.52,-32.11L120.04,-31.94L120.72,-31.98L120.79,-31.82L121.66,-31.32L121.88,-30.92L121.42,-30.79L121,-30.56L120.82,-30.35L120.45,-30.39L120.19,-30.24L120.49,-30.3L120.63,-30.13L121.26,-30.3L121.68,-29.98L122.08,-29.87L121.51,-29.48L121.89,-29.63L121.97,-29.49L121.92,-29.14L121.72,-29.26L121.45,-29.13L121.68,-28.95L121.54,-28.93L121.66,-28.85L121.48,-28.64L121.61,-28.29L121.27,-28.22L121.22,-28.35L121.15,-28.33L120.96,-28.04L120.75,-28.01L120.83,-27.89L120.59,-27.58L120.61,-27.41L120.28,-27.1L120.09,-26.67L119.88,-26.61L119.82,-26.85L119.71,-26.73L119.59,-26.78L119.88,-26.33L119.46,-26.05L119.14,-26.12L119.33,-25.95L119.62,-26L119.54,-25.59L119.62,-25.39L119.18,-25.45L119.29,-25.23L118.98,-25.21L118.91,-24.93L118.64,-24.84L118.72,-24.75L118.66,-24.62L118.09,-24.63L118.01,-24.48L117.84,-24.47L118.02,-24.38L118.06,-24.25L117.63,-23.84L117.47,-23.84L117.37,-23.59L117.29,-23.71L117.08,-23.58L116.91,-23.65L116.86,-23.45L116.63,-23.35L116.7,-23.28L116.54,-23.18L116.47,-22.95L116.25,-22.98L115.85,-22.8L115.64,-22.85L115.5,-22.72L115.2,-22.82L114.85,-22.62L114.65,-22.76L114.55,-22.53L114.27,-22.54L114.34,-22.4L114.27,-22.3L113.9,-22.4L114.02,-22.51L113.62,-22.86L113.62,-23.13L113.52,-23.1L113.33,-22.91L113.55,-22.59L113.55,-22.22L113.15,-22.07L113.09,-22.21L112.95,-21.91L112.81,-21.94L112.59,-21.78L112.36,-21.98L112.39,-21.8L112.3,-21.74L111.94,-21.85L111.6,-21.56L111.02,-21.51L110.57,-21.21L110.41,-21.34L110.37,-21.17L110.15,-20.94L110.18,-20.86L110.37,-20.84L110.31,-20.67L110.51,-20.52L110.34,-20.29L109.94,-20.3L109.89,-20.41L109.97,-20.45L109.66,-20.92L109.68,-21.13L109.93,-21.48L109.69,-21.52L109.52,-21.69L109.54,-21.54L109.08,-21.44L109.1,-21.59L108.77,-21.63L108.59,-21.9L108.48,-21.9L108.5,-21.63L108.32,-21.69L108.25,-21.56L107.81,-21.5L107.41,-21.28L107.35,-21.06L107.16,-20.95L106.68,-21L106.75,-20.74L106.55,-20.53L106.52,-20.29L105.98,-19.94L105.62,-18.97L105.89,-18.5L106.5,-17.95L106.48,-17.72L106.37,-17.75L107.83,-16.32L108.03,-16.33L108.82,-15.38L109.3,-13.86L109.27,-13.28L109.42,-12.96L109.44,-12.6L109.34,-12.75L109.22,-12.65L109.3,-12.39L109.21,-12.42L109.26,-11.95L109.2,-12L109.2,-11.72L109.04,-11.59L108.99,-11.34L108.09,-10.9L108,-10.72L107.26,-10.4L107.01,-10.66L106.95,-10.4L106.73,-10.54L106.61,-10.46L106.74,-10.44L106.76,-10.3L106.46,-10.3L106.79,-10.12L106.6,-9.86L106.14,-10.22L106.57,-9.64L106.38,-9.56L105.83,-10L106.16,-9.59L106.17,-9.4L105.5,-9.09L105.11,-8.63L104.77,-8.6L104.9,-8.75L104.82,-8.8L104.85,-9.61L104.9,-9.82L105.09,-9.9L105.03,-10.07L104.8,-10.2L104.66,-10.17L104.26,-10.54L103.87,-10.66L103.66,-10.51L103.59,-10.55L103.54,-10.67L103.72,-10.89L103.53,-11.15L103.35,-10.92L103.15,-10.91L103.13,-11.46L102.59,-12.2L102.54,-12.11L102.26,-12.39L102.23,-12.33L101.72,-12.69L100.9,-12.65L100.96,-13.43L100.6,-13.57L100.02,-13.35L100.09,-13.05L99.96,-12.69L99.99,-12.17L99.63,-11.46L99.49,-10.89L99.17,-10.32L99.25,-9.27L99.84,-9.29L99.99,-8.59L100.13,-8.43L100.16,-8.51L100.28,-8.27L100.55,-7.23L100.44,-7.28L100.38,-7.54L100.28,-7.55L100.26,-7.77L100.16,-7.73L100.16,-7.6L100.42,-7.19L100.59,-7.18L101.02,-6.86L101.5,-6.87L101.8,-6.47L102.34,-6.17L102.53,-5.86L103.2,-5.26L103.45,-4.67L103.36,-3.77L103.45,-3.52L103.44,-2.93L103.81,-2.58L103.97,-2.26L104.29,-1.48L104.18,-1.36L103.98,-1.62L103.99,-1.45L103.69,-1.45L103.48,-1.33L103.36,-1.55L102.73,-1.86L101.3,-2.89L101.3,-3.25L100.72,-3.97L100.8,-4.02L100.61,-4.37L100.34,-5.98L100.12,-6.44L99.7,-6.88L99.72,-7.11L99.55,-7.22L99.6,-7.36L99.36,-7.37L99.26,-7.62L99.08,-7.72L99.05,-7.89L98.79,-8.06L98.7,-8.26L98.58,-8.34L98.42,-8.18L98.31,-8.23L98.24,-8.77L98.7,-10.19L98.56,-10.03L98.52,-10.11L98.46,-10.68L98.68,-10.99L98.74,-11.59L98.88,-11.72L98.64,-11.74L98.7,-12.23L98.6,-12.25L98.68,-12.35L98.58,-13.16L98.25,-13.73L98.2,-13.98L98.11,-13.71L98.1,-14.16L97.91,-14.65L98.02,-14.65L97.81,-14.86L97.71,-15.88L97.58,-16.02L97.63,-16.46L97.73,-16.57L97.38,-16.52L97.2,-17.1L96.85,-17.4L96.91,-17.03L96.77,-16.71L96.43,-16.5L96.19,-16.77L96.32,-16.44L95.76,-16.17L95.39,-15.72L95.3,-15.76L95.35,-16.1L95.18,-15.83L94.94,-15.82L94.89,-16.18L94.8,-15.97L94.66,-15.9L94.7,-16.51L94.67,-16.34L94.44,-16.09L94.22,-16.02L94.27,-16.52L94.59,-17.57L94.43,-18.2L94.17,-18.73L94.25,-18.74L94.07,-18.89L94.04,-19.29L93.93,-18.9L93.71,-19.03L93.49,-19.37L93.58,-19.4L93.82,-19.24L94,-19.44L93.61,-19.78L93.71,-19.91L93.25,-20.07L93.16,-20.04L93.2,-19.9L93.13,-19.86L93,-20.07L93.1,-20.18L93.02,-20.19L93.07,-20.38L92.83,-20.18L92.89,-20.34L92.74,-20.56L92.72,-20.3L92.31,-20.79L92.06,-21.17L91.86,-22.35L91.8,-22.3L91.48,-22.88L91.22,-22.64L90.95,-22.6L90.66,-23.03L90.6,-23.59L90.56,-23.42L90.27,-23.46L90.59,-23.27L90.6,-23.13L90.47,-23.05L90.55,-22.9L90.44,-22.75L90.62,-22.36L90.23,-21.83L90.07,-21.89L90.21,-22.16L89.95,-22.02L89.92,-22.12L89.99,-22.47L89.88,-22.39L89.81,-21.98L89.57,-21.77L89.48,-22.28L89.5,-21.91L89.35,-21.72L89.09,-21.87L89.05,-22.09L89.03,-21.94L88.95,-21.94L89.05,-21.65L88.91,-21.65L88.86,-21.74L88.75,-21.58L88.74,-22.01L88.64,-22.12L88.58,-21.66L88.45,-21.61L88.29,-21.76L88.25,-21.62L88.12,-21.64L88.06,-21.69L88.2,-22.14L87.94,-22.37L87.96,-22.26L88.16,-22.12L87.95,-21.83L87.68,-21.65L87.1,-21.5L86.86,-21.24L86.98,-20.7L86.75,-20.31L86.38,-20.01L86.25,-20.05L86.31,-19.99L86.22,-19.9L85.58,-19.69L85.5,-19.7L85.56,-19.75L85.5,-19.89L85.25,-19.76L85.18,-19.59L85.37,-19.68L85.44,-19.63L84.77,-19.13L84.1,-18.29L83.65,-18.07L83.2,-17.61L82.36,-17.1L82.26,-16.56L81.76,-16.33L81.29,-16.34L80.98,-15.76L80.65,-15.9L80.29,-15.71L80.05,-15.07L80.18,-14.48L80.11,-14.21L80.31,-13.49L80.16,-13.71L80.06,-13.61L80.34,-13.36L80.23,-12.69L79.86,-11.99L79.79,-11.45L79.69,-11.31L79.8,-11.34L79.85,-11.2L79.84,-10.32L79.31,-10.26L78.94,-9.57L79.02,-9.33L79.41,-9.19L78.98,-9.27L78.42,-9.11L78.19,-8.89L78.06,-8.38L77.52,-8.08L77.07,-8.32L76.55,-8.9L76.32,-9.45L76.24,-9.93L76.34,-9.83L76.38,-9.54L76.46,-9.54L76.35,-9.92L76.2,-10.09L75.72,-11.36L75.2,-12.06L74.95,-12.56L74.38,-14.49L73.95,-15.07L73.8,-15.4L73.93,-15.4L73.77,-15.57L73.83,-15.66L73.68,-15.71L73.34,-16.46L73.16,-17.62L72.88,-18.64L73.01,-19.02L72.97,-19.15L72.83,-18.98L72.8,-19.08L72.81,-19.3L72.99,-19.28L72.79,-19.36L72.67,-19.83L72.89,-20.67L72.81,-21.12L72.69,-21.18L72.62,-21.37L72.73,-21.47L72.61,-21.46L73.11,-21.75L72.54,-21.7L72.7,-21.97L72.52,-21.98L72.55,-22.16L72.81,-22.23L72.18,-22.27L72.31,-22.19L72.27,-22.09L72.04,-21.82L72.21,-21.73L72.25,-21.53L72.02,-21.16L71.02,-20.74L70.49,-20.84L70.03,-21.18L68.97,-22.29L69.05,-22.44L69.28,-22.29L70.18,-22.57L70.51,-23L70.49,-23.09L70.34,-22.94L70.12,-22.95L69.66,-22.76L68.82,-23.05L68.42,-23.57L68.78,-23.85L68.23,-23.6L68.17,-23.86L68.12,-23.75L67.86,-23.9L67.67,-23.81L67.65,-23.92L67.56,-23.88L67.31,-24.17L67.17,-24.76L66.7,-24.86L66.7,-25.23L66.43,-25.58L66.22,-25.59L66.13,-25.49L66.47,-25.45L64.78,-25.31L64.66,-25.18L64.06,-25.4L63.56,-25.35L63.49,-25.21L62.66,-25.26L62.32,-25.13L62.2,-25.22L61.91,-25.13L61.53,-25.2L61.41,-25.1L60.66,-25.28L60.51,-25.44L60.4,-25.31L59.46,-25.48L59.05,-25.42L58.8,-25.55L57.8,-25.65L57.33,-25.79L57.04,-26.8L56.73,-27.13L56.36,-27.2L56.12,-27.14L55.65,-26.98L55.42,-26.77L54.64,-26.51L54.25,-26.7L53.71,-26.73L53.45,-26.94L52.69,-27.32L52.48,-27.62L52.03,-27.82L51.59,-27.86L51.28,-28.13L51.06,-28.73L50.87,-28.87L50.88,-29.06L50.68,-29.15L50.65,-29.42L50.17,-29.92L50.07,-30.2L49.55,-30.03L49.03,-30.33L49.25,-30.41L49.22,-30.47L49,-30.51L48.83,-30.04L48.45,-29.94L47.98,-30.01L48.14,-29.57L47.97,-29.62L47.72,-29.39L48.05,-29.36L48.81,-27.9L48.8,-27.72L49.24,-27.49L49.18,-27.44L49.41,-27.18L50.15,-26.66L50.01,-26.68L50.21,-26.31L50.16,-26.1L50.03,-26.11L50.73,-24.87L50.8,-24.79L50.85,-24.89L50.75,-25.4L51,-25.98L51.26,-26.15L51.54,-25.9L51.49,-25.52L51.61,-25.05L51.43,-24.67L51.27,-24.61L51.42,-24.53L51.31,-24.34L51.61,-24.34L51.77,-24.25L51.84,-24.01L52.12,-23.97L52.65,-24.15L53.8,-24.07L54.15,-24.17L54.4,-24.28L54.75,-24.81L55.94,-25.79L56.16,-26.21L56.41,-26.35L56.3,-25.65L56.37,-25.02L56.64,-24.47L57.22,-23.92L58.32,-23.62L58.58,-23.64L58.77,-23.52L59.43,-22.66L59.82,-22.51L59.82,-22.31L59.37,-21.5L58.9,-21.11L58.47,-20.41L58.21,-20.42L58.25,-20.6L58.17,-20.59L57.86,-20.24L57.71,-19.68L57.81,-19.02L56.83,-18.75L56.66,-18.59L56.55,-18.17L56.38,-17.99L55.48,-17.84L55.26,-17.59L55.28,-17.32L55.06,-17.04L54.77,-16.96L54.07,-17.01L53.61,-16.76L52.58,-16.47L52.24,-16.17L52.22,-15.66L51.32,-15.23L49.35,-14.64L48.67,-14.05L47.99,-14.05L47.41,-13.66L46.79,-13.47L45.66,-13.34L45.04,-12.82L44.62,-12.82L44.36,-12.67L43.93,-12.62L43.63,-12.74L43.49,-12.7L43.23,-13.27L43.28,-13.69L43.09,-14.01L42.94,-14.94L42.86,-15.13L42.66,-15.23L42.8,-15.33L42.72,-15.65L42.84,-16.03L42.79,-16.45L42.7,-16.74L42.38,-17.12L42.29,-17.43L41.66,-18.01L41.23,-18.68L40.76,-19.76L40.08,-20.27L39.73,-20.39L39.28,-20.97L39.09,-21.31L39.15,-21.52L38.99,-21.88L39.06,-22.59L38.46,-23.71L37.92,-24.19L37.54,-24.29L37.18,-24.82L37.27,-24.96L37.15,-25.29L35.18,-28.03L34.72,-28.13L34.62,-28.06L34.97,-29.56L34.74,-29.27L34.4,-28.02L34.22,-27.76L33.76,-28.05L33.25,-28.57L33.13,-28.98L32.72,-29.52L32.57,-29.97L32.47,-29.93L32.36,-29.63L32.6,-29.32L32.66,-28.93L33.55,-27.9L33.55,-27.61L33.85,-27.18L33.96,-26.65L35.19,-24.48L35.78,-23.94L35.54,-23.92L35.5,-23.78L35.7,-22.95L35.91,-22.74L36.23,-22.63L36.87,-22.02L36.93,-21.59L37.26,-21.11L37.26,-21.04L37.15,-21.1L37.14,-20.98L37.23,-20.56L37.19,-20.12L37.47,-18.82L37.92,-18.56L38.2,-18.25L38.28,-18.29L38.57,-18.07L38.91,-17.43L39.3,-15.92L39.51,-15.53L39.79,-15.12L39.86,-15.47L40.04,-15.33L40.2,-15.01L41.18,-14.62L41.66,-13.98L42.25,-13.59L42.4,-13.21L42.52,-13.22L42.8,-12.86L42.97,-12.81L43,-12.9L43.08,-12.82L43.35,-12.37L43.41,-12.19L43.34,-12.03L42.8,-11.74L42.64,-11.56L42.52,-11.57L42.54,-11.5L43.16,-11.57L43.44,-11.35L43.85,-10.78L44.28,-10.47L44.94,-10.44L45.82,-10.84L46.57,-10.75L47.4,-11.17L47.71,-11.11L48.57,-11.32L49.06,-11.27L50.11,-11.53L50.79,-11.98L51.25,-11.83L51.08,-11.34L51.14,-10.66L51.03,-10.44L51.19,-10.55L51.38,-10.39L51.21,-10.43L50.93,-10.34L50.83,-9.43L50.1,-8.2L49.85,-7.96L49.67,-7.47L49.23,-6.78L49.05,-6.17L47.98,-4.5L46.05,-2.48L44.92,-1.81L43.72,-0.86L41.98,0.97L41.39,1.87L41,1.95L40.95,2.06L40.89,2.02L40.92,2.19L40.81,2.39L40.64,2.54L40.28,2.63L40.12,3.25L39.86,3.58L39.49,4.48L39.23,4.67L38.8,6.07L38.87,6.33L39.55,7.02L39.29,7.52L39.29,7.79L39.43,7.81L39.44,8.01L39.3,8.44L39.45,8.94L39.64,9.19L39.78,9.91L39.73,10L40.39,10.35L40.61,10.66L40.49,10.77L40.6,10.83L40.4,11.33L40.53,12L40.49,12.49L40.58,12.64L40.44,12.98L40.57,12.98L40.6,14.12L40.72,14.21L40.65,14.54L40.73,14.42L40.82,14.47L40.84,14.79L40.62,15.12L40.56,15.47L39.98,16.23L39.79,16.29L39.84,16.44L39.08,16.97L38.14,17.24L37.51,17.57L36.94,17.99L36.4,18.77L36.26,18.72L36.24,18.86L35.85,18.99L34.95,19.81L34.65,19.7L34.76,19.82L34.71,20.47L34.98,20.81L35.27,21.65L35.32,22.4L35.38,22.45L35.46,22.12L35.54,22.3L35.49,22.66L35.58,22.96L35.37,23.8L35.54,23.82L35.44,24.17L34.99,24.65L33.35,25.26L32.79,25.64L32.59,26L32.85,26.27L32.95,26.08L32.89,26.83L32.53,28.2L32.38,28.5L31.34,29.38L30.47,30.71L29.97,31.32L27.86,33.05L26.61,33.71L25.81,33.74L25.57,34.04L25,33.97L24.83,34.17L24.6,34.17L23.7,33.99L23.27,34.08L22.55,34.01L22.25,34.07L21.79,34.37L20.99,34.37L20.53,34.46L20.02,34.79L19.3,34.62L19.33,34.49L19.1,34.35L18.83,34.36L18.75,34.08L18.5,34.11L18.46,34.35L18.35,34.19L18.35,33.94L18.47,33.89L18.43,33.72L17.85,32.83L17.97,32.71L18.12,32.75L18.33,32.5L18.21,31.74L17.35,30.44L16.74,29.01L16.48,28.64L15.72,27.97L15.34,27.39L15.13,26.79L15.14,26.51L14.97,26.32L14.85,25.73L14.84,25.03L14.5,24.2L14.4,22.97L14.52,22.81L14.46,22.45L13.45,20.92L13.17,20.18L12.46,18.93L12.04,18.47L11.78,18L11.72,17.47L11.82,16.5L11.75,15.83L12.02,15.51L12.55,13.44L12.9,13.03L12.98,12.78L13.42,12.52L13.69,12.12L13.85,11.05L13.72,10.63L13.33,10L13,9.05L13.36,8.69L13.38,8.37L12.86,7.23L12.82,6.95L12.28,6.12L13.07,5.86L12.45,6L12.24,5.81L12.16,5.63L12.18,5.32L11.78,4.57L10.35,3.01L9.76,2.52L10.06,2.55L9.62,2.37L9.3,1.9L9.48,1.96L9.48,1.89L9.27,1.83L9.04,1.31L9.32,1.63L9.5,1.56L9.3,1.52L9.35,1.32L9.2,1.38L9.06,1.3L8.7,0.59L8.82,0.71L8.95,0.69L9.3,0.35L9.35,-0.34L9.47,-0.16L9.8,-0.04L10,-0.19L9.55,-0.3L9.32,-0.55L9.5,-0.66L9.62,-0.58L9.6,-1.05L9.39,-1.14L9.81,-1.93L9.95,-3.08L9.67,-3.54L9.77,-3.62L9.64,-3.61L9.56,-3.8L9.74,-3.85L9.64,-3.97L9.69,-4.06L9.48,-4.07L9.43,-3.92L9,-4.09L8.92,-4.55L8.66,-4.67L8.69,-4.55L8.57,-4.53L8.57,-4.75L8.43,-4.75L8.25,-4.92L8.29,-4.56L7.64,-4.53L7.53,-4.66L7.46,-4.56L7.28,-4.55L7.08,-4.72L7.15,-4.51L6.92,-4.39L6.77,-4.72L6.86,-4.37L6.63,-4.34L6.58,-4.48L6.55,-4.34L6.26,-4.31L6.27,-4.43L6.21,-4.29L6.08,-4.29L5.59,-4.65L5.49,-4.84L5.37,-5.34L5.55,-5.47L5.39,-5.4L5.2,-5.53L5.46,-5.61L5.33,-5.71L5.11,-5.64L4.86,-6.03L4.43,-6.35L3.45,-6.43L3.72,-6.6L3.43,-6.53L3.34,-6.4L2.29,-6.33L1.31,-6.15L1.11,-6.05L0.95,-5.81L0.26,-5.76L-2,-4.76L-3.25,-5.11L-3.02,-5.13L-3.17,-5.2L-3.2,-5.35L-3.35,-5.13L-4.12,-5.31L-4.61,-5.24L-4.04,-5.23L-4.9,-5.14L-5.28,-5.21L-5.37,-5.15L-5.06,-5.13L-5.91,-5.01L-7.54,-4.35L-8.26,-4.59L-9.13,-5.05L-10.28,-6.08L-10.79,-6.31L-10.85,-6.47L-11.29,-6.69L-11.73,-7.09L-12.49,-7.39L-12.48,-7.75L-12.7,-7.72L-12.85,-7.82L-12.96,-8.15L-13.15,-8.21L-13.27,-8.43L-13.09,-8.42L-12.89,-8.63L-13.18,-8.58L-13.21,-8.84L-13.06,-8.88L-13.27,-8.99L-13.27,-9.17L-13.44,-9.42L-13.69,-9.54L-13.69,-9.93L-13.82,-9.89L-14.05,-10.14L-14.43,-10.25L-14.61,-10.55L-14.59,-10.77L-14.68,-10.69L-14.78,-10.93L-14.89,-10.97L-15.01,-10.8L-15.05,-11.14L-15.22,-11.03L-15.22,-11.16L-15.39,-11.22L-15.35,-11.38L-15.48,-11.41L-15.43,-11.5L-15.07,-11.6L-15.23,-11.69L-15.41,-11.62L-15.5,-11.78L-15.08,-11.97L-15.94,-11.79L-15.92,-11.94L-16.14,-11.92L-16.33,-12.05L-16.24,-12.24L-16.44,-12.2L-16.78,-12.47L-16.44,-12.61L-16.6,-12.72L-16.77,-12.63L-16.82,-13.34L-16.75,-13.43L-16.67,-13.47L-16.56,-13.3L-16.41,-13.27L-16.19,-13.28L-16.16,-13.38L-15.43,-13.47L-16.44,-13.35L-16.77,-13.9L-16.62,-14.04L-16.79,-14L-17.17,-14.64L-17.35,-14.73L-17.45,-14.65L-17.54,-14.76L-17.15,-14.92L-16.57,-15.73L-16.46,-16.6L-16.08,-17.55L-16.08,-18.52L-16.21,-19L-16.51,-19.36L-16.31,-19.51L-16.44,-19.47L-16.28,-19.79L-16.21,-20.23L-16.43,-20.65L-16.53,-20.71L-16.56,-20.6L-16.62,-20.63L-16.88,-21.09L-17,-21.04L-17.05,-20.81L-17.1,-20.86L-16.93,-21.9L-16.36,-22.59L-16.21,-23.1L-15.79,-23.79L-15.98,-23.67L-15.9,-23.84L-14.9,-24.72L-14.79,-25.4L-14.47,-26.16L-13.58,-26.74L-13.18,-27.66L-12.95,-27.91L-11.55,-28.31L-10.49,-29.06L-10.2,-29.38L-9.67,-30.11L-9.65,-30.45L-9.88,-30.72L-9.81,-31.42L-9.35,-32.09L-9.25,-32.57L-8.51,-33.25L-6.9,-33.97L-6.35,-34.78L-5.92,-35.79L-5.28,-35.9L-5.34,-35.75L-5.25,-35.61L-4.63,-35.21L-4.33,-35.16L-3.69,-35.28L-3.39,-35.21L-2.97,-35.41L-2.84,-35.13L-1.91,-35.09L-0.92,-35.67L-0.43,-35.86L-0.05,-35.83L0.31,-36.16L1.26,-36.52L2.59,-36.6L2.97,-36.78L3.52,-36.8L3.78,-36.9L4.76,-36.9L5.3,-36.65L6.06,-36.86L6.49,-37.09L6.93,-36.92L7.24,-36.97L7.2,-37.09L7.43,-37.06L7.91,-36.86L8.82,-37L9.14,-37.19L9.69,-37.34L9.84,-37.31L9.83,-37.14L9.88,-37.25L10.2,-37.21L10.29,-36.78L10.41,-36.73L10.95,-37.06L11.05,-37.07L11.13,-36.87L10.49,-36.25L10.59,-35.89L11,-35.63L11.12,-35.24L10.69,-34.68L10.06,-34.21L10.05,-34.06L10.31,-33.73L10.71,-33.69L10.72,-33.51L10.96,-33.63L11.26,-33.31L11.2,-33.25L11.81,-33.09L12.28,-32.86L12.75,-32.8L13.28,-32.91L14.16,-32.71L14.51,-32.51L15.18,-32.39L15.36,-32.16L15.5,-31.66L15.71,-31.43L16.12,-31.26L16.78,-31.21L17.83,-30.93L18.94,-30.29L19.29,-30.29L19.59,-30.41L20.01,-30.8L20.14,-31.2L19.93,-31.82L20.12,-32.22L20.62,-32.58L21.06,-32.78L21.42,-32.8L21.64,-32.94L22.19,-32.92L23.09,-32.62L23.11,-32.33L23.29,-32.21L23.8,-32.16L24.13,-32.01L24.88,-31.98L25.23,-31.53L25.89,-31.62L26.77,-31.47L27.97,-31.1L28.51,-31.05L29.07,-30.83L29.43,-30.93L29.93,-31.23L30.22,-31.26L30.4,-31.46L30.92,-31.57L30.56,-31.42L31,-31.46L31.08,-31.6L31.52,-31.46L31.89,-31.54L32.14,-31.34L31.89,-31.48L31.77,-31.29L32.01,-31.22L32.1,-31.09L32.28,-31.2L32.25,-31.29L32.6,-31.07L33.9,-31.18L34.48,-31.59L35.65,-34.25L35.98,-34.55L35.9,-35.42L35.76,-35.57L35.96,-36L35.81,-36.31L36.19,-36.66L36.18,-36.81L36.05,-36.91L35.39,-36.58L34.7,-36.82L33.69,-36.18L32.79,-36.04L32.38,-36.18L32.02,-36.54L31.24,-36.82L30.64,-36.87L30.45,-36.27L30.23,-36.31L29.69,-36.16L29.22,-36.32L28.97,-36.72L28.82,-36.68L28.3,-36.81L28.11,-36.65L28.02,-36.63L28.08,-36.75L27.54,-36.68L27.47,-36.75L28.01,-36.83L28.24,-37.03L27.26,-36.98L27.3,-37.13L27.54,-37.16L27.52,-37.25L27.22,-37.39L27.07,-37.66L27.22,-37.73L27.23,-37.98L26.29,-38.28L26.42,-38.37L26.38,-38.62L26.44,-38.64L26.59,-38.56L26.67,-38.34L26.73,-38.42L27.14,-38.45L26.91,-38.48L26.76,-38.71L27.01,-38.89L26.81,-38.96L26.85,-39.12L26.68,-39.29L26.9,-39.55L26.11,-39.47L26.18,-39.99L26.74,-40.4L27.28,-40.46L27.48,-40.32L27.73,-40.33L27.85,-40.38L27.73,-40.48L27.87,-40.51L27.99,-40.49L27.96,-40.37L29.01,-40.39L28.79,-40.53L28.96,-40.63L29.85,-40.76L29.36,-40.81L29.11,-40.94L29.05,-41.01L29.15,-41.22L31.25,-41.11L31.46,-41.32L32.31,-41.73L33.38,-42.02L34.75,-41.96L35.01,-42.06L35.15,-42.03L35.12,-41.89L35.3,-41.73L35.56,-41.63L36.05,-41.68L36.18,-41.43L36.41,-41.27L36.78,-41.36L37.07,-41.18L38.38,-40.92L39.43,-41.11L40.27,-40.96L41.41,-41.42L41.7,-41.71L41.76,-41.97L41.42,-42.74L39.87,-43.47L38.72,-44.29L38.18,-44.42L37.85,-44.7L37.5,-44.7L37.2,-44.97L36.63,-45.15L36.94,-45.29L36.72,-45.37L36.87,-45.43L37.21,-45.27L37.65,-45.38L37.61,-45.56L37.93,-46L38.01,-46.05L38.08,-45.93L38.18,-46.09L38.49,-46.09L38.08,-46.39L37.91,-46.41L37.77,-46.64L38.5,-46.66L38.44,-46.81L39.27,-47.04L39.2,-47.27L38.67,-47.14L38.55,-47.15L38.76,-47.26L38.58,-47.24L38.18,-47.08L37.54,-47.07L36.79,-46.71L36.56,-46.76L35.83,-46.62L35.06,-46.1L35.28,-46.28L35.23,-46.44L34.85,-46.19L34.86,-45.99L35.02,-45.7L35.46,-45.32L36.17,-45.45L36.58,-45.39L36.39,-45.07L35.87,-45.01L35.47,-45.1L35.09,-44.8L34.47,-44.72L34.28,-44.54L33.91,-44.39L33.45,-44.55L33.61,-44.91L33.56,-45.1L32.92,-45.35L32.61,-45.33L32.51,-45.4L33.66,-45.95L33.59,-46.1L33.43,-46.06L33.2,-46.18L32.48,-46.08L31.83,-46.28L31.78,-46.32L32.01,-46.43L31.55,-46.55L32.36,-46.47L32.58,-46.62L32.35,-46.56L32.04,-46.64L31.76,-47.21L31.91,-46.93L31.87,-46.65L31.53,-46.66L31.56,-46.78L31.4,-46.63L30.8,-46.55L30.66,-46.27L30.22,-45.87L29.63,-45.72L29.73,-45.34L29.56,-44.84L29.05,-44.76L29.1,-44.98L28.93,-44.97L28.81,-44.57L28.89,-44.57L28.65,-44.3L28.56,-43.5L28.47,-43.39L28.13,-43.4L27.93,-43.19L27.89,-42.75L27.48,-42.47L27.98,-42.05L27.99,-41.85L28.2,-41.55L29.06,-41.23L28.96,-41.01L28.17,-41.08L27.5,-40.97L27.26,-40.69L26.77,-40.5L26.2,-40.08L26.25,-40.31L26.79,-40.63L26.11,-40.61L25.86,-40.84L25.1,-40.99L24.79,-40.86L24.48,-40.95L24.08,-40.72L23.76,-40.75L23.87,-40.42L24.21,-40.33L24.34,-40.15L23.91,-40.36L23.73,-40.33L23.97,-40.11L23.95,-39.97L23.66,-40.22L23.43,-40.26L23.43,-40.12L23.67,-39.96L23.4,-39.99L23.31,-40.22L22.9,-40.4L22.92,-40.59L22.63,-40.5L22.59,-40.04L23.33,-39.17L23.15,-39.1L23.16,-39.26L22.92,-39.31L22.84,-39.26L22.89,-39.17L22.97,-39.03L23.07,-39.04L22.57,-38.87L23.25,-38.66L23.68,-38.35L23.97,-38.27L24.02,-38.14L24.02,-37.68L23.5,-38.03L23.04,-37.88L23.2,-37.62L23.4,-37.58L23.49,-37.44L23.16,-37.33L23.02,-37.48L22.73,-37.54L23.16,-36.45L22.72,-36.79L22.61,-36.78L22.49,-36.45L22.43,-36.48L22.38,-36.7L22.08,-37.03L21.96,-36.99L21.89,-36.74L21.58,-37.08L21.68,-37.39L21.12,-37.89L21.4,-38.2L21.66,-38.18L21.82,-38.33L22.92,-37.96L22.89,-38.05L23.12,-38.07L23.15,-38.18L22.42,-38.44L22.32,-38.36L21.97,-38.41L21.47,-38.32L21.33,-38.49L21.3,-38.37L21.18,-38.35L20.77,-38.87L21.11,-38.9L21.12,-39.03L20.78,-39.01L20.3,-39.33L19.85,-40.04L19.4,-40.28L19.32,-40.41L19.46,-40.41L19.34,-40.66L19.46,-40.93L19.44,-41.42L19.58,-41.79L19.19,-41.95L18.65,-42.44L17.05,-43.01L17.72,-42.85L16.9,-43.39L16.39,-43.54L15.99,-43.52L15.94,-43.66L15.19,-44.17L15.12,-44.26L15.47,-44.27L14.98,-44.6L14.85,-45.08L14.55,-45.3L14.31,-45.34L13.97,-44.84L13.86,-44.84L13.63,-45.11L13.52,-45.48L13.78,-45.63L13.63,-45.77L13.47,-45.71L13.21,-45.77L13.03,-45.64L12.27,-45.45L12.23,-45.24L12.52,-44.97L12.38,-44.8L12.28,-44.83L12.25,-44.72L12.4,-44.22L13.56,-43.57L14.01,-42.69L14.54,-42.24L15.17,-41.93L16.16,-41.9L16.15,-41.76L15.91,-41.62L15.9,-41.51L17.95,-40.66L18.46,-40.22L18.34,-39.82L18.08,-39.94L17.87,-40.28L17.4,-40.34L17.18,-40.5L16.93,-40.46L16.67,-40.14L16.52,-39.75L17.11,-39.38L17.17,-39L16.62,-38.8L16.55,-38.41L16.28,-38.25L16.06,-37.94L15.72,-37.94L15.65,-38.03L15.64,-38.18L15.9,-38.48L15.88,-38.61L16.2,-38.76L16.21,-38.94L15.69,-39.99L14.95,-40.24L14.95,-40.47L14.77,-40.67L14.34,-40.6L14.46,-40.73L14.04,-40.81L13.73,-41.24L13.09,-41.24L12.63,-41.47L11.64,-42.29L11.3,-42.42L11.14,-42.39L11.17,-42.54L10.71,-42.94L10.51,-42.97L10.52,-43.2L10.19,-43.95L9.29,-44.32L8.77,-44.42L8.55,-44.35L8,-43.88L7.26,-43.7L6.57,-43.2L6.12,-43.07L5.41,-43.23L5.06,-43.44L4.71,-43.37L4.05,-43.59L3.26,-43.19L3.04,-42.84L3.09,-42.59L3.31,-42.29L3.17,-42.26L3.15,-42.16L3.25,-41.94L2.08,-41.29L1.03,-41.06L0.71,-40.82L0.89,-40.72L0.6,-40.61L-0.33,-39.52L-0.2,-39.06L0.2,-38.76L-0.52,-38.32L-0.81,-37.77L-0.72,-37.63L-1.33,-37.56L-1.64,-37.39L-2.11,-36.78L-2.45,-36.83L-2.79,-36.71L-4.37,-36.72L-4.67,-36.51L-5.17,-36.42L-5.36,-36.13L-5.63,-36.03L-6.04,-36.19L-6.27,-36.6L-6.38,-36.64L-6.41,-36.73L-6.22,-36.91L-6.4,-36.83L-6.88,-37.19L-6.86,-37.28L-6.97,-37.2L-7.49,-37.17L-7.83,-37.01L-8.6,-37.12L-9,-37.03L-8.81,-37.43L-8.88,-37.96L-8.8,-38.18L-8.88,-38.45L-8.67,-38.42L-8.8,-38.52L-9.21,-38.45L-9.25,-38.66L-9.02,-38.75L-8.94,-39L-8.79,-39.08L-8.95,-39.02L-9.14,-38.74L-9.36,-38.7L-9.48,-38.8L-9.37,-39.34L-9.15,-39.54L-8.84,-40.12L-8.87,-40.26L-8.68,-40.75L-8.66,-41.09L-8.81,-41.56L-8.76,-41.7L-8.89,-41.76L-8.78,-41.94L-8.88,-41.95L-8.89,-42.11L-8.69,-42.27L-8.82,-42.29L-8.73,-42.41L-8.81,-42.64L-9.03,-42.59L-8.93,-42.8L-9.24,-42.98L-9.18,-43.17L-8.87,-43.33L-8.36,-43.4L-8.25,-43.44L-8.26,-43.58L-7.7,-43.76L-7.06,-43.55L-5.85,-43.65L-4.52,-43.42L-3.6,-43.52L-3.05,-43.37L-2.88,-43.45L-1.99,-43.35L-1.48,-43.56L-1.25,-44.56L-1.08,-44.69L-1.15,-44.76L-1.25,-44.67L-1.08,-45.53L-0.83,-45.38L-0.69,-45.09L-0.55,-45L-0.79,-45.47L-1.2,-45.71L-1.03,-45.74L-1.15,-46.31L-1.79,-46.51L-2.09,-46.87L-2.02,-47.04L-2.2,-47.16L-2.15,-47.22L-1.74,-47.22L-1.98,-47.31L-2.5,-47.31L-2.43,-47.47L-2.77,-47.51L-2.79,-47.63L-3.9,-47.84L-4.31,-47.82L-4.43,-47.97L-4.68,-48.04L-4.33,-48.17L-4.58,-48.29L-4.24,-48.3L-4.72,-48.36L-4.72,-48.54L-3.23,-48.84L-3,-48.79L-2.69,-48.54L-2.45,-48.65L-2,-48.58L-1.91,-48.7L-1.38,-48.65L-1.57,-48.81L-1.58,-49.2L-1.86,-49.68L-1.26,-49.68L-1.14,-49.39L-0.16,-49.3L0.42,-49.45L0.13,-49.51L0.19,-49.7L1.41,-50.09L1.59,-50.25L1.58,-50.74L1.77,-50.94L3.43,-51.39L4.23,-51.39L3.45,-51.54L3.74,-51.6L4.27,-51.47L4,-51.6L4.18,-51.61L3.95,-51.81L4.03,-51.93L4.48,-52.31L4.77,-52.94L5.06,-52.96L5.53,-53.27L6.06,-53.41L6.82,-53.44L7.2,-53.28L7.05,-53.38L7.21,-53.65L7.63,-53.7L8.01,-53.69L8.2,-53.43L8.33,-53.61L8.49,-53.51L8.5,-53.39L8.53,-53.78L8.62,-53.88L9.21,-53.86L9.78,-53.55L9.31,-53.86L8.98,-53.93L8.91,-54.26L8.64,-54.29L8.65,-54.4L8.95,-54.47L8.96,-54.54L8.68,-54.79L8.57,-55.13L8.67,-55.16L8.62,-55.42L8.13,-55.6L8.16,-56.61L8.67,-56.5L8.89,-56.74L9.07,-56.79L9.2,-56.7L9.25,-57.01L9.11,-57.04L8.99,-57.02L8.77,-56.73L8.47,-56.66L8.27,-56.75L8.62,-57.11L9.43,-57.17L9.96,-57.58L10.61,-57.74L10.44,-57.56L10.54,-57.45L10.52,-57.24L10.3,-57L10.28,-56.62L10.93,-56.44L10.75,-56.24L10.32,-56.21L10.18,-55.87L9.9,-55.84L10.02,-55.76L9.59,-55.49L9.67,-55.27L9.45,-55.04L9.69,-55L9.75,-54.81L10.02,-54.67L10.03,-54.58L9.87,-54.47L10.14,-54.49L10.73,-54.32L11.01,-54.38L11.06,-54.28L10.81,-54.08L10.85,-54.01L11.4,-53.94L11.8,-54.15L12.11,-54.17L12.58,-54.47L13.03,-54.41L13.45,-54.14L13.72,-54.15L13.95,-53.8L14.58,-53.64L14.56,-53.82L13.93,-53.88L13.83,-54.13L14.38,-53.92L16.19,-54.29L16.56,-54.55L17.26,-54.73L18.09,-54.84L18.76,-54.68L18.44,-54.74L18.67,-54.43L18.84,-54.37L19.41,-54.39L19.86,-54.63L19.97,-54.92L20.4,-54.95L20.68,-55.1L21.01,-55.4L21.11,-55.62L21.03,-55.35L20.59,-54.98L21.19,-54.94L21.24,-55.46L21.06,-55.81L21.03,-56.64L21.07,-56.82L21.35,-57.02L21.46,-57.32L21.73,-57.57L22.55,-57.72L23.14,-57.32L23.29,-57.09L23.65,-56.97L23.93,-57.01L24.38,-57.25L24.3,-57.78L24.53,-58.35L24.34,-58.38L24.11,-58.27L23.77,-58.36L23.51,-58.66L23.68,-58.79L23.5,-58.79L23.43,-58.92L23.52,-59L23.49,-59.2L24.08,-59.29L24.05,-59.37L24.38,-59.47L25.44,-59.52L25.51,-59.64L27.89,-59.41L28.06,-59.55L28.06,-59.78L28.33,-59.69L28.52,-59.85L28.95,-59.83L29.15,-60L30.12,-59.87L30.17,-59.96L29.72,-60.2L29.07,-60.19L28.64,-60.38L28.49,-60.54L28.62,-60.49L28.65,-60.61L28.51,-60.68L27.46,-60.46L27.21,-60.54L26.53,-60.41L26.57,-60.62L26.38,-60.42L25.96,-60.47L26.04,-60.34L25.76,-60.27L25.66,-60.33L24.45,-60.02L23.46,-59.99L23.02,-59.82L23.2,-60.02L22.91,-60.21L22.75,-60.06L22.46,-60.03L22.44,-60.16L22.59,-60.23L22.51,-60.28L22.58,-60.38L21.85,-60.51L21.81,-60.59L21.61,-60.53L21.44,-60.6L21.36,-60.97L21.57,-61.48L21.5,-61.55L21.61,-61.59L21.26,-61.99L21.34,-62.28L21.17,-62.41L21.1,-62.62L21.47,-63.03L21.65,-63.04L21.55,-63.2L22.32,-63.31L22.24,-63.44L22.53,-63.65L23.6,-64.04L24.56,-64.8L25.29,-64.86L25.23,-64.95L25.37,-65.01L25.26,-65.14L25.35,-65.48L24.67,-65.67L24.58,-65.76L24.63,-65.86L24.4,-65.78L23.69,-65.83L23.1,-65.74L22.75,-65.87L22.54,-65.79L22.4,-65.86L22.25,-65.6L22.09,-65.61L22.15,-65.55L21.92,-65.53L21.88,-65.42L21.57,-65.41L21.61,-65.26L21.41,-65.32L21.57,-65.13L21.14,-64.81L21.52,-64.46L21.02,-64.18L20.76,-63.87L19.91,-63.61L19.72,-63.46L19.35,-63.48L19.03,-63.24L18.61,-63.18L18.31,-63L18.5,-62.99L18.46,-62.9L18.17,-62.79L17.88,-62.87L17.97,-62.72L17.9,-62.66L18.04,-62.6L17.65,-62.45L17.38,-62.46L17.43,-62.33L17.63,-62.23L17.51,-62.17L17.37,-61.87L17.47,-61.68L17.2,-61.72L17.13,-61.58L17.25,-60.7L17.59,-60.63L17.66,-60.54L17.96,-60.59L18.56,-60.25L18.54,-60.15L18.79,-60.08L18.99,-59.83L17.98,-59.33ZM50.68,-46.94L49.89,-46.6L49.35,-46.52L49.36,-46.41L49.21,-46.39L49.25,-46.29L48.68,-46.09L48.73,-45.9L48.49,-45.93L48.16,-45.74L47.7,-45.69L47.63,-45.58L47.46,-45.68L47.53,-45.53L47.35,-45.22L47.08,-44.82L47,-44.88L46.76,-44.66L46.72,-44.45L47.02,-44.34L47.31,-44.1L47.46,-43.56L47.65,-43.88L47.46,-43.04L47.71,-42.81L47.73,-42.68L48.38,-41.95L48.82,-41.63L49.46,-40.8L49.78,-40.58L50.18,-40.5L50.37,-40.28L49.92,-40.32L49.55,-40.19L49.32,-39.61L49.36,-39.35L49.17,-39.03L49.01,-39.13L48.96,-39.08L48.85,-38.82L48.87,-38.39L49.08,-37.67L49.37,-37.52L50.13,-37.41L50.34,-37.15L50.93,-36.81L51.76,-36.61L53.77,-36.93L53.92,-36.93L53.68,-36.85L53.97,-36.82L54.02,-36.95L53.82,-37.93L53.87,-38.95L53.7,-39.21L53.34,-39.34L53.16,-39.26L53.12,-39.43L53.24,-39.61L53.6,-39.55L53.47,-39.67L53.49,-39.91L52.99,-39.99L53.04,-39.77L52.8,-40.05L52.73,-40.4L52.94,-41.04L53.15,-40.82L53.62,-40.82L53.87,-40.65L54.38,-40.69L54.32,-40.83L54.69,-40.87L54.7,-41.07L54.09,-41.52L53.85,-42.09L53.75,-42.13L53.16,-42.09L52.97,-41.98L52.81,-41.71L52.88,-41.65L52.85,-41.2L52.47,-41.89L52.64,-42.56L52.6,-42.76L51.9,-42.87L51.62,-43.16L51.3,-43.17L51.3,-43.48L50.83,-44.19L50.25,-44.41L50.3,-44.58L50.41,-44.62L51.54,-44.53L51.31,-44.62L51.01,-44.92L51.42,-45.36L52.43,-45.4L53.2,-45.33L52.77,-45.57L53.14,-46.19L53.06,-46.48L53.17,-46.67L52.92,-46.95L52.48,-46.99L52.14,-46.83L51.18,-47.11L50.68,-46.94ZM-166.11,-66.23L-165.82,-66.33L-166.11,-66.23Z"/><path class="borders" d="M47.98,-8L48.94,-9.45L48.94,-11.26M47.98,-8L44.94,-4.91L43.99,-4.95L43.58,-4.85L43.13,-4.64L42.86,-4.32L42.02,-4.14L41.88,-3.98M34.25,-31.21L34.53,-31.53L34.48,-31.58M35.55,-32.4L35.19,-32.53L35.07,-32.46L34.96,-32.16L34.96,-31.82L35.2,-31.75L34.95,-31.6L34.88,-31.37L35.45,-31.48M35.11,-33.08L35.41,-33.08L35.6,-33.24M35.79,-32.73L35.89,-32.94L35.79,-33.29L35.84,-33.42M34,-35.07L33.48,-35L33.38,-35.16L32.92,-35.09L32.71,-35.17M77.8,-35.5L78.04,-35.48L78.01,-35.25L78.33,-34.61L78.67,-34.52L78.97,-34.3L78.73,-34.01L78.8,-33.5L78.92,-33.39M77.05,-35.11L77,-34.99L76.59,-34.74L76.04,-34.67L75.71,-34.5L75.32,-34.58M91.63,-27.76L91.98,-27.73L92.55,-27.88L92.69,-27.99L92.7,-28.15L93.17,-28.36L93.36,-28.65L93.9,-28.74L93.97,-28.86L94.27,-28.97L94.29,-29.14L94.62,-29.31L94.77,-29.18L95.39,-29.04L95.77,-29.34L96.13,-29.38L96.23,-29.25L96.36,-29.25L96.18,-29.12L96.2,-28.96L96.44,-29.05L96.58,-28.76L96.28,-28.41L96.6,-28.46L97.08,-28.37L97.32,-28.22M128.37,-38.62L128.04,-38.31L127.09,-38.28L126.67,-37.92L126.63,-37.78M-8.68,-27.66L-8.82,-27.66L-8.79,-27.12L-9.41,-27.09L-9.82,-26.85L-10.25,-26.86L-10.76,-27.02L-11.39,-26.88L-11.34,-26.63L-11.72,-26.1L-12.06,-25.99L-12.43,-24.83L-12.99,-24.47L-13.31,-23.98L-13.89,-23.69L-14.1,-23.1L-14.22,-22.31L-14.63,-21.86L-14.75,-21.5L-17,-21.42M35.92,-4.62L35.76,-4.81L35.75,-5.34L35.47,-5.42L35.33,-5.36L35.27,-5.49M-124.76,-48.49L-123.86,-48.26L-123.39,-48.25L-123.14,-48.4L-123.24,-48.64L-123.01,-48.79L-123.31,-48.99M91.63,-27.76L91.64,-27.92L91.27,-28.08L91.02,-27.97L90.33,-28.12M23.61,-51.52L23.71,-51.64L23.98,-51.59L24.36,-51.87L25.79,-51.92L27.14,-51.75L27.3,-51.6L27.69,-51.57L27.7,-51.48L27.86,-51.59L28.18,-51.61L28.6,-51.54L28.73,-51.43L29.1,-51.63L29.35,-51.38L30.16,-51.48L30.54,-51.27L30.63,-51.36L30.53,-51.6L30.76,-51.9L31.08,-52.08L31.76,-52.1M35.84,-33.42L35.6,-33.24M35.84,-33.42L36.03,-33.59L35.94,-33.67L35.99,-33.75L36.37,-33.84L36.28,-33.93L36.58,-34.22L36.5,-34.43L36.33,-34.5L36.43,-34.61L36.38,-34.66L35.98,-34.63M34.68,12.01L34.68,12.01M80.21,-42.19L80.2,-42.73L80.54,-42.87L80.39,-43.04L80.79,-43.16L80.36,-44.1L80.36,-44.55L80.48,-44.71L79.87,-44.88L80.06,-45.01L81.69,-45.35L81.94,-45.16L82.27,-45.22L82.52,-45.13L82.61,-45.42L82.32,-45.59L83.03,-47.19L84.02,-46.97L84.67,-46.97L84.79,-46.83L85.48,-47.06L85.66,-47.25L85.53,-47.92L85.75,-48.39L86.55,-48.53L86.72,-48.7L86.81,-49.05L87.32,-49.09M23.48,-53.94L24.32,-53.89L24.77,-53.97L24.87,-54.15L25.46,-54.29L25.51,-54.16L25.75,-54.16L25.75,-54.26L25.55,-54.33L25.86,-54.92L26.18,-55L26.29,-55.14L26.6,-55.13L26.78,-55.27L26.46,-55.34L26.59,-55.67M-53.37,33.74L-53.53,33.66L-53.53,33.17L-53.16,32.68L-53.6,32.4L-53.76,32.06L-54.22,31.86L-54.59,31.49L-55.17,31.28L-55.56,30.88L-55.81,31.03M116.68,-49.82L115.82,-48.58L115.79,-48.25L115.53,-48.13L115.62,-47.87L115.9,-47.69L116.23,-47.86L116.76,-47.87L117.35,-47.65L117.77,-47.99L118.5,-47.98L119.71,-47.15L119.9,-46.86L119.87,-46.67L119.33,-46.61L118.84,-46.76L118.07,-46.67L117.74,-46.52L117.44,-46.59L117.33,-46.36L116.86,-46.39L116.56,-46.29L116.21,-45.89L116.2,-45.74L115.68,-45.46L114.56,-45.39L114.08,-44.97L113.59,-44.75L112.71,-44.88L112.41,-45.06L111.9,-45.06L111.62,-44.83L111.4,-44.37L111.84,-43.93L111.93,-43.71L111.01,-43.34L110.4,-42.77L109.34,-42.44L108.17,-42.45L106.77,-42.29L104.98,-41.6L104.5,-41.66L104.5,-41.88L103.71,-41.75L103.07,-42.01L102.16,-42.16L101.5,-42.54L99.98,-42.68L99.47,-42.57L97.21,-42.79L96.39,-42.72L96.3,-42.93L95.86,-43.28L95.53,-43.95L95.33,-44.04L95.35,-44.28L94.71,-44.35L93.52,-44.94L90.88,-45.2L90.66,-45.53L90.71,-45.73L91,-46.04L90.91,-46.27L91.03,-46.57L90.87,-46.95L90.72,-47L90.5,-47.29L90.33,-47.66L90.1,-47.75L90.03,-47.88L89.78,-47.83L89.48,-48.03L89.05,-48L88.58,-48.22L88.52,-48.38L87.98,-48.56L88.06,-48.71L87.74,-48.88L87.87,-49L87.81,-49.16M13.81,-48.77L12.68,-49.41L12.39,-49.74L12.51,-49.9L12.21,-50.1L12.09,-50.3L12.28,-50.18L12.55,-50.39L12.94,-50.41L13.56,-50.7L14.37,-50.9L14.26,-51L14.32,-51.04L14.55,-50.99L14.66,-50.83L14.81,-50.86M27.35,-57.53L26.97,-57.61L26.46,-57.54L25.99,-57.84L25.28,-58.05L24.32,-57.87M27.35,-57.53L27.83,-57.29L27.64,-56.85L27.85,-56.85L28.1,-56.55L28.2,-56.26L28.15,-56.14M21.05,-56.07L22.08,-56.41L24.12,-56.26L24.84,-56.41L25.07,-56.2L25.66,-56.1L26.59,-55.67M20.62,-69.04L20.12,-69.02L20.35,-68.85L20.24,-68.67L19.97,-68.54L20.24,-68.48L19.97,-68.36L18.3,-68.56L18.16,-68.53L18.18,-68.2L17.92,-67.96L17.32,-68.1L16.78,-67.9L16.57,-67.62L16.13,-67.43L16.43,-67.16L16.4,-67.05L15.42,-66.49L15.48,-66.31L14.54,-66.13L14.63,-65.79L14.48,-65.3L13.65,-64.58L14.08,-64.46L14.14,-64.17L13.96,-64.01L13.2,-64.08L12.79,-64L12.18,-63.6L12.21,-63.49L12,-63.29L12.22,-63L12.11,-62.92L12.11,-62.59L12.3,-62.29L12.16,-61.72L12.88,-61.35L12.71,-61.06L12.29,-61L12.59,-60.45L12.49,-60.11L11.93,-59.86L11.68,-59.59L11.8,-59.29L11.64,-58.93L11.47,-58.91L11.24,-59.1L10.91,-58.95M20.62,-69.04L21.07,-69.04L21.13,-69.08L21.07,-69.21L21.59,-69.27L22.41,-68.72L23.32,-68.65L23.85,-68.81L24.94,-68.59L25.25,-68.82L25.75,-68.99L25.77,-69.28L26.07,-69.69L26.53,-69.92L27.13,-69.91L27.75,-70.06L29.14,-69.67L29.33,-69.47L28.85,-69.18L28.97,-69.02M104.43,-10.41L104.56,-10.52L104.85,-10.53L105.05,-10.7L105.05,-10.91L105.31,-10.85L105.41,-10.95L105.76,-10.99L105.85,-10.86L106.16,-10.79L106.16,-11.04L105.86,-11.29L105.85,-11.64L106.01,-11.76L106.4,-11.69L106.41,-11.95L106.7,-11.98L107.21,-12.3L107.39,-12.26L107.51,-12.36L107.48,-13.03L107.61,-13.44L107.33,-14.13L107.52,-14.71M-69.51,17.5L-69.31,17.94L-69.09,18.05L-69.15,18.14L-68.97,18.97L-68.46,19.43L-68.7,19.72L-68.56,19.97L-68.76,20.09L-68.69,20.31L-68.76,20.42L-68.48,20.63L-68.56,20.9L-68.2,21.3L-68.19,21.62L-67.88,22.49L-67.88,22.82L-67.58,22.89L-67.19,22.82M-69.51,17.51L-69.85,17.7L-69.8,17.99L-69.93,18.21L-70.42,18.35M6.34,-49.45L6.49,-49.8L6.2,-49.92L6.12,-50.12M2.52,-51.1L2.6,-50.88L2.76,-50.75L3.11,-50.78L3.27,-50.53L3.6,-50.48L3.69,-50.31L3.95,-50.34L4.17,-50.25L4.15,-49.97L4.55,-49.96L4.82,-50.15L4.87,-49.79L5.28,-49.68L5.51,-49.51L5.79,-49.54M6.12,-50.12L5.98,-50.17L5.74,-49.92L5.72,-49.81L5.88,-49.64L5.79,-49.54M46.43,-41.89L45.64,-42.21L45.71,-42.5L45.34,-42.53L44.87,-42.76L44.77,-42.62L44.51,-42.75L43.83,-42.57L43.74,-42.62L43.78,-42.75L42.76,-43.17L41.58,-43.22L40.65,-43.53L40.15,-43.57L39.98,-43.42M20.96,-40.85L20.71,-40.93L20.49,-41.27L20.45,-41.52L20.57,-41.87M20.57,-41.87L20.49,-42.22L20.06,-42.55M41.51,-41.52L42.47,-41.44L42.61,-41.58L42.75,-41.58L43.44,-41.11M101.14,-21.57L101.25,-21.2L101.8,-21.21L101.72,-21.31L101.74,-21.83L101.52,-22.25L101.74,-22.5L101.84,-22.39L102.13,-22.38M73.63,-39.45L73.91,-39.58L73.84,-39.8L73.99,-40.04L74.83,-40.33L74.84,-40.48L75.11,-40.45L75.56,-40.63L75.68,-40.31L76.26,-40.43L76.32,-40.35L76.91,-41.02L78.12,-41.08L78.44,-41.42L79.77,-41.9L79.84,-42L80.22,-42.03L80.21,-42.19M43.44,-41.11L44.84,-41.21L45,-41.29M80.21,-42.19L79.92,-42.41L79.43,-42.48L79.13,-42.78L76.99,-42.97L75.84,-42.94L75.64,-42.81L75.37,-42.84L74.21,-43.24L73.56,-43L73.42,-42.59L73.49,-42.41L71.76,-42.82L71.26,-42.73L70.89,-42.34L70.95,-42.25M-56.48,-1.94L-56.84,-1.88L-57.12,-2.01L-57.32,-1.96L-57.55,-1.73L-57.98,-1.65L-58.03,-1.52L-58.34,-1.59L-58.51,-1.44L-58.51,-1.28L-58.82,-1.2L-59.23,-1.38L-59.67,-1.75L-59.76,-1.9L-59.76,-2.27L-59.89,-2.36L-59.99,-2.69L-59.85,-3.59L-59.55,-3.93L-59.74,-4.23L-59.7,-4.38L-60.15,-4.53L-59.99,-5.08L-60.14,-5.24L-60.74,-5.2M8.39,-55.1L8.59,-54.92L9.74,-54.83M9.52,-30.23L9.9,-30.39L10.22,-30.78L10.26,-30.94L10.11,-31.46L10.27,-31.68L11.51,-32.41L11.5,-33.18M45,-41.29L45.19,-41.15L45.07,-41.08L45.59,-40.85L45.38,-40.67L45.45,-40.53L45.96,-40.23L45.89,-40.02L45.58,-39.98L46.2,-39.59L46.48,-39.56L46.37,-39.4L46.58,-39.22L46.4,-39.19L46.49,-38.91M44.77,-39.7L45.03,-39.77L45.17,-39.57L45.46,-39.49L45.78,-39.55L45.77,-39.38L45.98,-39.24L46.11,-38.88M20.24,-46.11L21.12,-46.28L22,-47.4L22,-47.51L22.29,-47.73L22.61,-47.77L22.88,-47.95M70.96,-40.24L71.3,-40.29L71.69,-40.15L72.13,-40.44L72.36,-40.4L72.4,-40.58L72.6,-40.53L73.14,-40.81L72.19,-41.03L72.16,-41.17L71.88,-41.2L71.66,-41.54L71.59,-41.33L71.42,-41.34L71.39,-41.12L70.86,-41.22L70.69,-41.45L70.47,-41.41L70.2,-41.51L70.86,-42.03L71.23,-42.16L71.04,-42.28L70.95,-42.25M18.83,-49.51L18.97,-49.4L19.15,-49.4L19.44,-49.6L19.77,-49.37L19.76,-49.2L20.06,-49.18L20.36,-49.39L20.87,-49.31L21.08,-49.42L21.64,-49.41L22.54,-49.07M-7.22,-55.09L-7.38,-55.03L-7.55,-54.77L-7.91,-54.7L-7.75,-54.59L-8.12,-54.41L-7.61,-54.14L-7.32,-54.13L-7.01,-54.41L-6.65,-54.16L-6.65,-54.06L-6.22,-54.09M18.83,-49.51L18.56,-49.88L18.03,-50.04L17.87,-49.97L17.63,-50.12L17.7,-50.31L17.42,-50.25L16.88,-50.43L16.99,-50.24L16.64,-50.1L16.21,-50.42L16.42,-50.57L16.28,-50.66L16.01,-50.61L14.99,-51.01L14.98,-50.89L14.81,-50.86M70.96,-40.24L70.52,-39.95L70.45,-40.05L69.97,-40.2L69.53,-40.1L69.48,-39.92L69.28,-39.92L69.3,-39.52L70.5,-39.59L70.8,-39.39L71.47,-39.6L71.5,-39.48L71.73,-39.42L71.78,-39.28L72.04,-39.35L72.23,-39.21L72.56,-39.38L73.63,-39.45M20,-39.71L20.25,-39.68L20.38,-39.8L20.31,-39.98L20.66,-40.12L20.81,-40.45L21.03,-40.62L20.96,-40.85M33.2,14.01L33.15,13.94L32.99,14.02L32.67,13.59L32.97,13.22L33.02,12.63L33.4,12.49L33.51,12.35L33.34,12.31L33.25,12.11L33.3,11.69L33.23,11.42L33.38,11.16L33.26,10.89L33.66,10.55L33.53,10.23L33.31,10.04L33.35,9.86L33.2,9.63L33,9.62L32.92,9.41M22.13,-48.41L22.14,-48.57L22.54,-49.07M-11.51,-6.91L-11.27,-7.23L-10.65,-7.76L-10.57,-8.07L-10.36,-8.19L-10.28,-8.49M24.15,-8.67L24.29,-8.29L24.85,-8.14L25.2,-7.81L25.18,-7.56L25.28,-7.43L25.89,-7.06L26.36,-6.64L26.31,-6.46L26.51,-6.07L27.14,-5.72L27.33,-5.19M42.92,-11L43.25,-11.5M42.92,-11L42.56,-11.08L41.8,-10.98L41.79,-11.69L42.38,-12.47M29.4,4.45L29.32,4.9L29.61,5.72L29.48,6.03L29.54,6.31L29.71,6.62L30.21,7.04L30.75,8.19M42.38,-12.47L42.48,-12.51L42.7,-12.38L42.87,-12.62L43.12,-12.71M13.81,-48.77L14.05,-48.6L14.69,-48.6L15.07,-49L16.06,-48.75L16.54,-48.8L16.88,-48.7L16.95,-48.6M42.36,-37.11L42.77,-37.37L43.68,-37.23L44.11,-37.3L44.28,-36.98L44.61,-37.18L44.77,-37.14M16.09,-46.86L16.45,-47.01L16.44,-47.4L16.68,-47.54L16.42,-47.67L16.59,-47.75L17.07,-47.71L17.03,-47.84L17.15,-48.01M7.02,-45.93L7.79,-45.92L8.13,-46.16L8.1,-46.27L8.42,-46.45L8.46,-46.25L8.82,-46.08L8.78,-46L9.02,-45.85L9,-46.01L9.25,-46.29L9.26,-46.48L9.43,-46.48L9.53,-46.31L9.94,-46.36L10.13,-46.24L10.04,-46.48L10.09,-46.6L10.43,-46.55L10.45,-46.86M10.45,-46.86L10.35,-46.98L10.13,-46.85L9.58,-47.06M44.77,-37.14L44.79,-37.29L44.57,-37.44L44.59,-37.71L44.21,-37.91L44.45,-38.33L44.3,-38.39L44.27,-38.84L44.02,-39.38L44.39,-39.42L44.46,-39.67L44.59,-39.77L44.82,-39.65M23.48,-53.94L23.37,-54.2L22.89,-54.39L22.77,-54.36M30.75,8.19L31.03,8.6L31.35,8.61L31.67,8.91L31.92,8.94L31.94,9.05L32.43,9.16L32.92,9.41M7.2,-53.28L7.19,-53L7.03,-52.65L6.71,-52.62L6.75,-52.46L7.04,-52.38L6.98,-52.21L6.72,-52.08L6.8,-51.97L5.95,-51.8L6.2,-51.45L6.08,-51.22L6.13,-51.15L5.86,-51.03L6.05,-50.9L5.99,-50.75M9.58,-47.06L9.53,-47.27M-8.49,-7.56L-8.23,-7.56L-8.01,-8.08L-8.26,-8.25L-8.24,-8.46L-7.68,-8.41L-7.72,-8.64L-7.95,-8.79L-7.94,-8.98L-7.78,-9.08L-7.92,-9.19L-7.9,-9.42L-8.14,-9.5L-8.16,-9.97L-7.99,-10.16M7.49,-43.77L7.68,-44.08L7.64,-44.16L7.32,-44.14L6.9,-44.34L6.84,-44.51L7.03,-44.72L6.99,-44.83L6.74,-44.92L6.63,-45.07L7.08,-45.24L7.15,-45.38L6.79,-45.74L7.02,-45.93M28.97,-69.02L28.41,-68.9L28.77,-68.84L28.48,-68.54L28.56,-68.35L28.69,-68.19L29.34,-68.06L29.99,-67.67L29.94,-67.55L29.07,-66.89L29.9,-66.09L30.09,-65.79L30.1,-65.68L29.72,-65.62L29.82,-65.57L29.61,-65.25L29.83,-65.15L29.6,-64.97L29.78,-64.8L30.11,-64.73L29.99,-64.52L30.11,-64.37L30.49,-64.24L30.53,-64.08L30.21,-63.8L29.99,-63.74L31.18,-63.21L31.53,-62.89L31.19,-62.48L27.73,-60.46M30.87,-69.78L30.86,-69.54L30.18,-69.64L30.09,-69.43L29.39,-69.3L29.21,-69.1L28.97,-69.02M55.19,-22.7L55.2,-23.03L55.53,-23.82L55.47,-23.94L55.99,-24.06L55.93,-24.22L55.76,-24.24L55.8,-24.87L56,-24.95L56.06,-24.74L56.39,-24.98M48.57,-41.84L48.39,-41.6L48.06,-41.46L47.79,-41.2L47.32,-41.28L46.75,-41.81L46.43,-41.89M-54.62,-2.33L-54.98,-2.6L-55.73,-2.41L-55.96,-2.52L-56.14,-2.26L-55.92,-2.04L-55.93,-1.89L-56.48,-1.94M46.43,-41.89L46.18,-41.66L46.67,-41.29L46.53,-41.09L45.92,-41.19L45.72,-41.34L45.28,-41.45L45,-41.29M-11.39,-12.4L-11.45,-12.56L-11.39,-12.94L-11.63,-13.37L-11.83,-13.32L-12.05,-13.63L-11.96,-13.88L-12.02,-14.21L-12.23,-14.46L-12.19,-14.65L-12.28,-14.81M-54.62,-2.33L-54.13,-2.12L-53.77,-2.35L-52.9,-2.21L-52.58,-2.53L-52.33,-3.18L-51.65,-4.06M2.71,-6.37L2.77,-9.05L3.04,-9.08L3.14,-9.45L3.35,-9.81L3.56,-9.91L3.65,-10.16L3.58,-10.29L3.65,-10.41L3.77,-10.42L3.83,-10.61L3.72,-11.08L3.49,-11.4L3.6,-11.7M13.07,4.63L12.8,4.43L12.38,4.62L12.02,5M16.52,-46.5L16.32,-46.53L16.23,-46.37L15.64,-46.2L15.65,-45.86L15.28,-45.73L15.34,-45.47L14.79,-45.48L14.57,-45.66L14.37,-45.48L13.99,-45.51L13.88,-45.43L13.58,-45.52M18.91,-45.93L18.36,-45.75L17.81,-45.79L16.52,-46.5M20.24,-46.11L19.61,-46.17L18.91,-45.93M16.52,-46.5L16.28,-46.86L16.09,-46.86M51.27,-24.61L50.97,-24.57L50.8,-24.79M25.26,17.79L25.24,17.97L25.94,18.94L26.17,19.54L26.68,19.89L27.18,20.1L27.28,20.48L27.68,20.5L27.67,21.06L28.01,21.55L29.03,21.8L29.04,22.02L29.36,22.19M77.8,-35.5L77.45,-35.48L76.77,-35.66M28.01,-41.97L27.53,-41.92L27.24,-42.09L27.01,-42.06L26.58,-41.95L26.32,-41.72M102.93,-11.71L102.74,-12.09L102.76,-12.43L102.5,-12.67L102.34,-13.56L102.55,-13.59L102.91,-14.14L103.2,-14.33L103.6,-14.42L103.98,-14.36L104.78,-14.43L105.07,-14.23L105.18,-14.35M88.89,-27.32L88.74,-27.18L88.86,-26.96L89.61,-26.72L90.12,-26.75L90.35,-26.89L90.74,-26.77L91.43,-26.87L91.67,-26.8L92.05,-26.87L91.99,-27.1L92.08,-27.29L91.99,-27.45L91.74,-27.44L91.59,-27.56L91.63,-27.76M104.07,-1.28L104.06,-1.4L103.82,-1.46L103.7,-1.44L103.6,-1.21M100.12,-6.44L100.18,-6.67L100.26,-6.68L100.35,-6.55L100.75,-6.46L100.87,-6.25L101.05,-6.24L101.08,-5.96L100.98,-5.77L101.11,-5.64L101.56,-5.91L101.68,-5.78L101.87,-5.83L102.1,-6.24M5.99,-50.75L6.34,-50.45L6.36,-50.32L6.12,-50.12M-71.78,-19.72L-71.75,-19.29L-71.65,-19.16L-71.81,-18.99L-71.74,-18.73L-72,-18.6L-71.76,-18.34L-71.77,-18.04M14.06,-13.08L13.61,-13.7M46.53,-29.1L46.91,-29.54L47.15,-30L47.64,-30.1L47.98,-29.98M88.11,-27.87L88.58,-28.09L88.8,-28.01L88.85,-27.87L88.75,-27.52L88.89,-27.32M-90.1,-13.74L-90.05,-13.9L-89.55,-14.24L-89.57,-14.39L-89.36,-14.42M124.04,9.34L124.28,9.43L124.44,9.19M124.92,8.94L124.94,9.05L125.15,9.04L125.1,9.19L124.96,9.21L125.07,9.51M115.14,-4.9L115.33,-4.38L115.25,-4.35L115.11,-4.39L115.03,-4.9M109.63,-2.03L109.54,-1.9L109.65,-1.61L110.51,-0.86L111.1,-1.05L111.81,-1.01L112.08,-1.14L112.19,-1.44L112.48,-1.56L112.94,-1.57L113.01,-1.43L113.62,-1.24L113.9,-1.43L114.51,-1.45L114.83,-1.98L114.79,-2.25L115.18,-2.52L115.08,-2.63L115.12,-2.89L115.25,-3.03L115.45,-3.03L115.57,-3.94L115.84,-4.33L117.1,-4.34L117.54,-4.17L117.88,-4.19M10.45,-46.86L10.99,-46.78L11.24,-46.98L12.17,-47.08L12.15,-46.94L12.39,-46.7L13.7,-46.52M13.7,-46.52L13.38,-46.26L13.63,-46.18L13.48,-46.01L13.61,-45.96L13.58,-45.81L13.87,-45.61L13.72,-45.59M29.01,2.72L29.1,2.6L29.39,2.81L29.7,2.79L29.87,2.72L29.93,2.34L30.12,2.42L30.41,2.31L30.55,2.4M92.57,-21.98L92.63,-21.31L92.57,-21.26L92.33,-21.44L92.18,-21.29L92.32,-20.79M1.43,-42.6L1.29,-42.71L0.7,-42.85L0.63,-42.69L-0.04,-42.69L-0.3,-42.83L-0.59,-42.8L-0.76,-42.94L-1.3,-43.1L-1.46,-43.05L-1.41,-43.24L-1.79,-43.41M1.43,-42.6L1.71,-42.6L1.71,-42.5M1.71,-42.5L2.03,-42.35L3.21,-42.43M1.43,-42.6L1.45,-42.44L1.71,-42.5M74.89,-37.23L75.12,-37.39L74.89,-37.6L74.94,-37.77L74.78,-38.19L74.81,-38.46L74.28,-38.66L74.13,-38.66L74.03,-38.54L73.8,-38.61L73.7,-38.85L73.81,-38.97L73.61,-39.23L73.63,-39.45M74.89,-37.23L74.73,-37.29L74.37,-37.16L74.54,-37.02M20.96,-40.85L21.58,-40.87L21.99,-41.13L22.6,-41.14L22.72,-41.18L22.78,-41.33L22.92,-41.34M21.56,-42.25L21.29,-42.1L21.06,-42.17L20.78,-42.07L20.72,-41.87L20.57,-41.87M22.34,-42.31L21.56,-42.25M22.34,-42.31L22.52,-42.44L22.44,-42.63L22.47,-42.84L22.71,-42.88L22.98,-43.19L22.55,-43.45L22.37,-43.78L22.42,-44.01L22.71,-44.24M22.92,-41.34L23,-41.74L22.84,-41.99L22.34,-42.31M18.44,-42.56L18.52,-42.43M18.44,-42.56L17.67,-42.9M78.92,-33.39L79.12,-33.23M20.34,-42.83L20.62,-43.03L20.62,-43.2L20.8,-43.26L21.4,-42.83L21.39,-42.75L21.75,-42.67L21.52,-42.33L21.56,-42.25M20.34,-42.83L20.05,-42.76L20.06,-42.55M19.19,-43.53L19.61,-43.17L20.27,-42.94L20.34,-42.83M-89.36,-14.42L-89.12,-14.37L-88.71,-14.03L-88.51,-13.98L-88.48,-13.85L-88.15,-13.99L-87.99,-13.88L-87.8,-13.89L-87.72,-13.81L-87.74,-13.45L-87.81,-13.4M-87.34,-12.98L-87.01,-13.01L-86.92,-13.22L-86.73,-13.28L-86.76,-13.75L-86.33,-13.77L-86.04,-14.05L-85.73,-13.86L-85.18,-14.34L-85.16,-14.53L-84.99,-14.75L-84.86,-14.81L-84.45,-14.64L-83.64,-14.88L-83.54,-14.98L-83.16,-14.99M-75.28,0.11L-75.78,-0.09L-76.27,-0.44L-76.49,-0.24L-77.4,-0.39L-77.47,-0.64L-77.7,-0.84L-78.18,-0.97L-78.86,-1.46M-57.6,-3.37L-58.03,-4L-58.05,-4.17L-57.85,-4.67L-57.88,-4.88L-57.71,-4.99L-57.33,-5.02L-57.21,-5.2L-57.32,-5.34L-57.19,-5.55M-54.08,-3.33L-53.99,-3.59L-54.35,-4.05L-54.48,-4.84L-54.45,-5.01L-54.16,-5.36M-58.41,33.94L-58.48,33.65L-58.38,33.14L-58.13,32.98L-58.2,32.47M-57.61,30.19L-57.87,30.59L-57.81,30.86L-58.05,31.49L-58.01,31.68L-58.19,31.92L-58.12,32.25L-58.2,32.47M-54.62,25.58L-54.44,25.62L-54.15,25.52L-53.89,25.67L-53.67,26.29L-53.72,26.88L-53.84,27.12L-54.33,27.42L-54.83,27.55L-55.1,27.87L-55.73,28.2L-55.69,28.38L-55.89,28.37L-56.94,29.59L-57.61,30.19M20.62,-69.04L22,-68.52L22.85,-68.37L23.64,-67.95L23.5,-67.88L23.54,-67.61L23.45,-67.46L23.73,-67.42L23.77,-67.33L23.63,-67.23L23.64,-67.13L23.99,-66.81L23.67,-66.38L23.72,-66.22L23.91,-66.15L24.16,-65.81L24.12,-65.51M4.23,-51.39L3.9,-51.21L3.43,-51.25L3.35,-51.38M5.99,-50.75L5.64,-50.84L5.8,-51.15L5.48,-51.29L5.21,-51.28L5.03,-51.47L4.23,-51.39M6.34,-49.45L6.53,-49.39L6.74,-49.16L7.45,-49.15L8.13,-48.97L8.14,-48.89L7.84,-48.64L7.62,-48.16L7.53,-47.67L7.62,-47.59M9.52,-47.52L8.57,-47.78L8.4,-47.69L8.57,-47.65L8.45,-47.6L7.62,-47.59M9.53,-47.27L9.63,-47.47L9.52,-47.52M9.58,-47.06L9.49,-47.06L9.53,-47.27M7.02,-45.93L6.77,-46.17L6.76,-46.42L6.43,-46.43L6.23,-46.33L6.2,-46.19L6.01,-46.14L5.97,-46.21L6.1,-46.28L6.07,-46.46L6.41,-46.76L6.46,-46.95L7,-47.32L6.9,-47.39L6.97,-47.45L7.34,-47.43L7.62,-47.59M-7.41,-37.18L-7.5,-37.59L-7.44,-37.73L-6.96,-38.19L-7.11,-38.18L-7.34,-38.46L-7.28,-38.71L-7,-39.06L-7.17,-39.14L-7.54,-39.66L-7.12,-39.68L-6.98,-39.8L-6.9,-40.02L-7.03,-40.17L-6.81,-40.34L-6.93,-41.01L-6.21,-41.53L-6.31,-41.64L-6.54,-41.67L-6.62,-41.94L-7.15,-41.98L-7.4,-41.83L-7.92,-41.88L-8.15,-41.81L-8.22,-41.9L-8.13,-42.02L-8.27,-42.14L-8.78,-41.94M13.81,-48.77L13.72,-48.54L13.49,-48.58L13.37,-48.36L12.76,-48.11L12.95,-47.89L12.9,-47.72L13.05,-47.66L13.01,-47.48L12.69,-47.67L12.21,-47.72L12.19,-47.62L11.04,-47.39L10.87,-47.52L10.44,-47.55L10.37,-47.37L10.18,-47.28L10.2,-47.36L9.97,-47.51L9.75,-47.58L9.52,-47.52M16.09,-46.86L15.96,-46.68L14.89,-46.61L14.55,-46.4L13.7,-46.52M18.44,-42.56L18.55,-42.64L18.46,-43L18.62,-43.03L18.67,-43.23L18.85,-43.35L19.03,-43.29L18.95,-43.53L19.19,-43.53M19.19,-43.53L19.45,-43.56L19.5,-43.64L19.25,-43.97L19.58,-44.01L19.12,-44.36L19.35,-44.88L18.84,-44.88L18.66,-45.08L18,-45.14L17.81,-45.08L16.92,-45.28L16.53,-45.22L16.29,-45.01L16.03,-45.19L15.82,-45.2L15.74,-44.77L16.1,-44.52L16.3,-44.12L17.27,-43.45L17.29,-43.31L17.65,-43.01L17.59,-42.94M19.01,-44.87L19.1,-44.97L19.06,-45.14L19.4,-45.21L19,-45.4L19.06,-45.52L18.92,-45.6L18.84,-45.84L18.91,-45.93M16.95,-48.6L17.14,-48.84L17.76,-48.89L18.09,-49.07L18.16,-49.26L18.6,-49.49L18.83,-49.51M17.15,-48.01L16.87,-48.39L16.95,-48.6M17.15,-48.01L17.76,-47.77L18.72,-47.79L18.79,-48L19.47,-48.11L19.63,-48.22L19.95,-48.15L20.33,-48.3L20.49,-48.53L21.45,-48.55L21.72,-48.35L22.13,-48.41M14.81,-50.86L15.02,-51.25L14.91,-51.46L14.72,-51.52L14.6,-51.83L14.75,-52.08L14.55,-52.36L14.62,-52.53L14.13,-52.88L14.41,-53.22L14.21,-53.95M22.88,-47.95L22.77,-48.11L22.13,-48.41M28.59,-43.74L28.22,-43.77L27.88,-43.99L27.43,-44.02L27.09,-44.17L26.22,-44.01L25.5,-43.67L22.92,-43.83L22.87,-43.95L23.03,-44.08L22.71,-44.24M20.24,-46.11L20.77,-45.75L20.79,-45.47L21.49,-45.15L21.35,-45.01L21.53,-44.9L21.36,-44.83M22.92,-41.34L24.49,-41.56L24.77,-41.36L25.25,-41.24L25.92,-41.31L26.14,-41.39L26.07,-41.67L26.2,-41.74L26.58,-41.6L26.62,-41.4L26.33,-41.24L26.33,-40.95L26.04,-40.73M20.06,-42.55L19.79,-42.48L19.65,-42.63L19.28,-42.17L19.34,-41.87M26.62,-48.26L26.98,-48.16L27.61,-47.34L28.07,-46.98L28.24,-46.64L28.1,-45.97L28.16,-45.65L28.07,-45.6L28.21,-45.45M22.88,-47.95L23.2,-48.08L23.41,-47.99L24.58,-47.93L24.98,-47.72L25.46,-47.91L26.16,-47.99L26.31,-48.2L26.62,-48.26M22.54,-49.07L22.85,-49.06L22.71,-49.17L22.71,-49.61L23.71,-50.38L23.97,-50.41L24.09,-50.53L23.98,-50.79L24.1,-50.87L23.66,-51.31L23.61,-51.52M20.9,-55.29L21.39,-55.28L22.07,-55.06L22.57,-55.06L22.82,-54.87L22.68,-54.56L22.77,-54.36M31.76,-52.1L31.58,-52.31L31.56,-52.76L31.26,-53.02L31.42,-53.2L32.14,-53.09L32.7,-53.34L32.71,-53.42L32.47,-53.55L32.45,-53.69L31.75,-53.81L31.83,-54.03L31.4,-54.2L31.07,-54.49L31.15,-54.63L30.8,-54.78L30.98,-55.05L30.81,-55.31L30.91,-55.57L30.23,-55.85L29.94,-55.85L29.48,-55.68L29.35,-55.78L29.38,-55.94L29.03,-56.02L28.79,-55.94L28.56,-56.09L28.28,-56.06L28.15,-56.14M31.76,-52.1L32.12,-52.05L32.44,-52.31L32.81,-52.25L33.74,-52.34L34.4,-51.78L34.12,-51.68L34.27,-51.34L34.21,-51.26L35.06,-51.2L35.16,-51.06L35.31,-51.04L35.44,-50.73L35.41,-50.54L35.59,-50.37L36.12,-50.41L36.62,-50.21L37.42,-50.41L37.7,-50.11L38.05,-49.92L38.26,-50.05L38.92,-49.82L39.17,-49.86L39.78,-49.57L40.08,-49.58L40.11,-49.25L39.69,-49.01L40,-48.82L39.79,-48.81L39.64,-48.59L39.84,-48.54L39.85,-48.3L39.96,-48.27L39.78,-47.89L38.9,-47.86L38.64,-47.67L38.37,-47.61L38.2,-47.32L38.28,-47.28L38.21,-47.09M43.44,-41.11L43.72,-40.72L43.57,-40.48L43.67,-40.13L44.01,-40.01L44.29,-40.04L44.78,-39.68M87.82,-49.16L88.12,-49.26L88.19,-49.45L89.11,-49.5L89.24,-49.63L89.65,-49.72L89.64,-49.9L89.98,-49.98L90.05,-50.09L91.42,-50.47L91.8,-50.69L92.19,-50.7L92.35,-50.86L92.63,-50.69L92.94,-50.78L93.1,-50.6L94.25,-50.56L94.35,-50.22L94.61,-50.02L95.52,-49.91L96.07,-50L96.32,-49.9L96.99,-49.88L97.21,-49.73L97.36,-49.74L97.59,-49.91L98,-50.01L98.25,-50.3L98.28,-50.53L98.03,-50.64L97.84,-51.05L98.04,-51.45L98.22,-51.51L98.35,-51.72L98.64,-51.8L98.89,-52.12L99.92,-51.76L100.47,-51.73L101.38,-51.45L102.11,-51.35L102.29,-50.59L103.3,-50.2L104.08,-50.15L105.38,-50.47L106.22,-50.3L106.71,-50.31L107.23,-49.99L107.92,-49.95L107.97,-49.65L108.61,-49.32L109.24,-49.33L110.71,-49.14L111.34,-49.36L112.81,-49.52L113.57,-50.01L114.3,-50.27L114.74,-50.23L115.43,-49.9L116.22,-50.01L116.68,-49.82M116.68,-49.82L117.87,-49.51L118.45,-49.84L119.26,-50.07L119.35,-50.28L119.16,-50.41L120.07,-51.6L120.51,-51.85L120.75,-52.1L120.66,-52.57L120.17,-52.6L120.04,-52.72L120.99,-53.28L122.34,-53.49L123.61,-53.55L124.81,-53.13L125.08,-53.2L125.65,-53.04L125.73,-52.89L126.05,-52.74L126.02,-52.61L126.34,-52.36L126.81,-51.51L126.92,-51.1L127.31,-50.71L127.34,-50.35L127.59,-50.21L127.49,-49.98L127.55,-49.8L128,-49.57L128.7,-49.6L129.07,-49.37L129.5,-49.39L130.2,-48.89L130.55,-48.86L130.62,-48.77L130.55,-48.6L130.8,-48.34L130.73,-48.02L130.96,-47.71L132.48,-47.71L132.71,-47.95L133.14,-48.11L133.47,-48.1L134.29,-48.37L134.67,-48.25L134.57,-48.02L134.75,-47.72L134.54,-47.49L134.17,-47.3L134.2,-47.13L133.87,-46.5L133.86,-46.25L133.51,-45.88L133.44,-45.6L133.19,-45.49L133.11,-45.13L132.94,-45.03L131.85,-45.33L131.45,-44.98L130.98,-44.84L131.26,-44.07L131.17,-43.7L131.26,-43.38L131.07,-42.9L130.42,-42.73L130.58,-42.62L130.53,-42.54M130.53,-42.54L130.25,-42.74L130.24,-42.89L129.9,-43L129.7,-42.45L129.31,-42.41L128.92,-42.04L128.05,-41.99L128.29,-41.61L128.15,-41.39L127.18,-41.53L126.95,-41.77L126.72,-41.72L126.6,-41.64L126.49,-41.36L125.99,-40.9L125.73,-40.87L124.89,-40.46L124.36,-40M130.53,-42.54L130.69,-42.3M70.96,-40.24L70.65,-40.2L70.37,-40.38L70.75,-40.72L70.4,-41.04L70.29,-40.89L69.71,-40.66L69.36,-40.77L69.21,-40.57L69.27,-40.2L68.63,-40.17L68.97,-40.09L68.8,-40.05L68.87,-39.91L68.64,-39.84L68.46,-39.54L67.72,-39.62L67.43,-39.47L67.36,-39.22L67.65,-39.13L67.69,-38.99L68.13,-38.93L68.09,-38.47L68.35,-38.21L68.29,-38.03L67.81,-37.49L67.76,-37.17M35.89,-35.92L36.15,-35.83L36.35,-36L36.38,-36.17L36.64,-36.23L36.54,-36.46L36.66,-36.8L37.07,-36.65L37.44,-36.64L38.19,-36.9L38.77,-36.69L39.36,-36.68L40.71,-37.1L41.52,-37.09L42.2,-37.3L42.36,-37.11M35.45,-31.48L35.44,-31.13L35.14,-30.42L34.97,-29.56M35.55,-32.4L35.56,-31.77L35.45,-31.48M35.61,-32.68L35.55,-32.4M88.11,-27.87L87.14,-27.84L86.61,-28.1L86.41,-27.93L86.14,-28.11L85.99,-27.91L85.68,-28.28L85.12,-28.32L85.16,-28.59L84.8,-28.56L84.23,-28.91L84.1,-29.22L83.94,-29.28L83.58,-29.18L83.16,-29.61L82.85,-29.68L82.22,-30.06L82.04,-30.33L81.42,-30.34L81.18,-30.04L81.01,-30.16M97.32,-28.22L97.34,-27.94L96.88,-27.59L97.1,-27.12L96.73,-27.33L96.19,-27.26L95.13,-26.6L95.05,-26.35L95.13,-26.04L94.58,-25.32L94.55,-25.22L94.71,-25.05L94.13,-23.88L93.33,-24.06L93.39,-23.34L93.35,-23.08L93.16,-23.03L93.08,-22.72L93.15,-22.23L92.96,-22L92.69,-22.13L92.57,-21.98M100.12,-20.32L99.89,-20.42L99.72,-20.33L99.46,-20.36L99.49,-20.15L99.07,-20.1L98.92,-19.77L98.37,-19.69L98.02,-19.75L97.82,-19.46L97.71,-18.93L97.75,-18.59L97.37,-18.52L97.45,-18.36L97.63,-18.29L97.71,-17.8L98.44,-16.98L98.66,-16.33L98.84,-16.42L98.89,-16.35L98.82,-16.18L98.59,-16.05L98.56,-15.37L98.19,-15.2L98.2,-14.98L98.57,-14.36L98.93,-14.05L99.14,-13.72L99.12,-13.03L99.22,-12.74L99.41,-12.55L99.61,-11.78L99.19,-11.11L98.76,-10.66L98.7,-10.19M103.09,-18.14L103.29,-18.41L103.95,-18.32L104.43,-17.7L104.74,-17.46L104.82,-17.3L104.74,-16.88L104.82,-16.47L105.05,-16.16L105.41,-15.99L105.4,-15.83L105.64,-15.66L105.49,-15.26L105.5,-14.59L105.18,-14.35M100.12,-20.32L100.14,-20.25L100.32,-20.39L100.52,-20.18L100.4,-19.76L100.51,-19.55L100.74,-19.51L100.97,-19.61L101.21,-19.55L101.29,-18.98L101.05,-18.44L101.14,-18.14L100.96,-17.54L101.17,-17.5L102.1,-18.21L102.66,-17.82L103.05,-18.03L103.09,-18.14M101.14,-21.57L100.7,-21.25L100.54,-20.99L100.62,-20.86L100.25,-20.73L100.12,-20.32M97.32,-28.22L97.6,-28.52L98.06,-28.19L98.3,-27.55L98.45,-27.66L98.65,-27.57L98.74,-26.79L98.69,-26.19L98.56,-26.07L98.66,-25.86L98.47,-25.79L98.33,-25.59L98.14,-25.57L98.01,-25.29L97.82,-25.25L97.74,-24.87L97.58,-24.77L97.53,-24.49L97.71,-24.23L97.56,-23.91L98.21,-24.11L98.84,-24.12L98.68,-23.91L98.83,-23.62L98.86,-23.19L99.42,-23.07L99.51,-22.96L99.39,-22.83L99.19,-22.13L99.92,-22.03L99.94,-21.76L100.1,-21.66L100.15,-21.48L100.6,-21.47L101.08,-21.76L101.14,-21.57M102.13,-22.38L102.58,-21.9L102.66,-21.68L102.82,-21.81L102.95,-21.68L102.85,-21.27L103.1,-20.89L103.64,-20.7L104.1,-20.95L104.58,-20.65L104.37,-20.44L104.62,-20.37L104.7,-20.21L104.85,-20.2L104.93,-20.02L104.59,-19.62L104.03,-19.68L104.06,-19.48L103.89,-19.3L104.72,-18.8L105.15,-18.65L105.11,-18.41L105.46,-18.15L105.69,-17.74L106.5,-16.95L106.66,-16.49L106.85,-16.52L106.93,-16.35L107.4,-16.04L107.39,-15.95L107.17,-15.8L107.65,-15.26L107.48,-14.98L107.52,-14.71M27.4,-5.11L27.07,-5.2L26.82,-5.06L25.53,-5.31L25.25,-5.02L25.07,-4.97L24.32,-4.99L23.42,-4.66L22.86,-4.72L22.42,-4.13L20.56,-4.46L20.23,-4.83L19.81,-5.09L19.5,-5.13L19.07,-4.89L18.83,-4.52L18.59,-4.35L18.61,-3.48M30.55,2.4L30.42,2.64L30.43,2.87L30.78,2.98L30.79,3.27L30.43,3.59L29.95,4.31L29.72,4.46L29.4,4.45M29.01,2.72L29.22,3.05L29.21,3.83L29.4,4.45M29.58,1.39L29.2,1.72L29.13,2.2L28.88,2.4L28.89,2.64L29.01,2.72M35.27,-5.49L34.98,-5.86L34.71,-6.66L34.06,-7.23L33.9,-7.51L33,-7.9L33.28,-8.44L33.95,-8.44L34.07,-8.55L34.08,-9.46M22.86,-10.92L22.49,-11L21.77,-10.64L21.68,-10.29L21.26,-9.97L20.77,-9.41L20.34,-9.13L18.96,-8.94L18.89,-8.84L19.11,-8.66L18.56,-8.05L17.65,-7.98L16.78,-7.55L16.55,-7.87L16.38,-7.68L15.96,-7.51L15.48,-7.52M13.29,-2.16L13.22,-2.26L11.56,-2.3L11.35,-2.3L11.33,-2.17M11.13,3.92L11.23,3.69L11.5,3.52L11.69,3.68L11.88,3.67L11.83,3.53L11.93,3.32L11.72,3.18L11.76,2.98L11.54,2.84L11.61,2.34L12.06,2.41L12.45,2.33L12.43,1.93L12.59,1.83L12.79,1.93L12.99,2.31L13.46,2.4L13.73,2.14L13.89,2.47L13.99,2.49L14.2,2.35L14.16,2.22L14.38,1.89L14.47,0.57L13.86,0.2L13.95,-0.35L14.09,-0.54L14.32,-0.62L14.43,-0.9L14.18,-1.37L13.85,-1.42L13.22,-1.25L13.17,-1.79L13.29,-2.16M15.48,-7.52L15.55,-7.79L15.44,-7.85L15.12,-8.56L14.33,-9.2L13.98,-9.69L14.24,-9.98L15.65,-10.01L15.28,-10.36L15.13,-10.65L15.03,-11.11L15.12,-11.54L15.08,-11.85L14.85,-12.5L14.46,-13.02L14.06,-13.08M14.06,-13.08L14.2,-12.38L14.52,-12.3L14.62,-12.15L14.58,-11.53L13.98,-11.21L13.7,-10.87L13.41,-10.17L13.27,-10.04L13.2,-9.56L12.93,-9.43L12.78,-8.82L12.58,-8.62L12.4,-8.6L12.23,-8.28L12.02,-7.59L11.77,-7.27L11.86,-7.12L11.58,-6.89L11.48,-6.6L11.24,-6.45L11.11,-6.46L11.01,-6.74L10.61,-7.06L10.48,-6.89L10.21,-6.89L10.14,-7L9.78,-6.76L9.66,-6.53L9,-5.92L8.8,-5.2L8.56,-4.76M3.6,-11.7L3.66,-11.76L3.65,-12.53L4.04,-12.93L4.15,-13.46L4.66,-13.73L5.24,-13.76L5.49,-13.87L6.3,-13.66L7.01,-13L7.83,-13.34L8.1,-13.29L8.75,-12.91L9.62,-12.81L10.05,-13.21L10.48,-13.33L11.41,-13.35L12.12,-13.09L12.46,-13.09L12.87,-13.45L13.32,-13.67L13.61,-13.7M1.19,-6.09L0.74,-6.45L0.53,-6.85L0.63,-7.35L0.5,-7.55L0.61,-7.73L0.58,-8.15L0.69,-8.35L0.37,-8.76L0.49,-8.85L0.53,-9.4L0.41,-9.49L0.23,-9.46L0.34,-9.6L0.26,-9.64L0.38,-10.29L-0.09,-10.67L0.01,-11.02L-0.07,-11.12M-2.7,-9.48L-2.75,-9.05L-2.6,-8.8L-2.51,-8.21L-2.79,-7.93L-3.24,-6.65L-3,-5.71L-2.79,-5.6L-2.76,-5.36L-2.82,-5.15L-3.11,-5.09M-5.52,-10.43L-5.49,-11.04L-5.35,-11.13L-5.25,-11.38L-5.29,-11.83L-4.7,-12.08L-4.43,-12.34L-4.48,-12.67L-4.23,-12.79L-4.33,-13.12L-4.15,-13.31L-3.95,-13.4L-3.53,-13.18L-3.3,-13.28L-3.25,-13.66L-2.95,-13.65L-2.87,-13.95L-2.59,-14.23L-2.46,-14.27L-2.11,-14.17L-1.97,-14.46L-1.05,-14.82L-0.76,-15.05L-0.24,-15.06L0.22,-14.91M-2.7,-9.48L-2.82,-9.43L-3.22,-9.9L-3.79,-9.92L-4.33,-9.65L-4.63,-9.71L-4.97,-9.93L-5.1,-10.24L-5.52,-10.43M-8.49,-7.56L-8.3,-6.98L-8.33,-6.8L-8.6,-6.51L-8.29,-6.32L-7.89,-6.23L-7.8,-5.98L-7.45,-5.84L-7.43,-5.32L-7.59,-4.82L-7.54,-4.35M-8.49,-7.56L-8.66,-7.69L-8.89,-7.26L-9.12,-7.22L-9.26,-7.38L-9.46,-7.42L-9.37,-7.7L-9.52,-8.35L-9.78,-8.54L-10.06,-8.43L-10.15,-8.52L-10.28,-8.49M-5.52,-10.43L-5.84,-10.39L-6.03,-10.19L-6.2,-10.23L-6.26,-10.72L-6.43,-10.67L-6.42,-10.56L-6.65,-10.66L-6.69,-10.35L-6.95,-10.34L-7.02,-10.14L-7.36,-10.26L-7.5,-10.44L-7.66,-10.43L-7.99,-10.16M-15.04,-10.94L-14.68,-11.51L-13.73,-11.74L-13.74,-12.01L-13.95,-12.18L-13.71,-12.31L-13.73,-12.67M-11.39,-12.4L-11.5,-12.2L-11.31,-12.02L-10.93,-12.21L-10.71,-11.9L-10.27,-12.21L-9.75,-12.03L-9.36,-12.26L-9.4,-12.46L-9.04,-12.4L-8.82,-11.92L-8.82,-11.67L-8.4,-11.37L-8.67,-11.01L-8.34,-10.99L-8.27,-10.49L-8.01,-10.32L-7.99,-10.16M107.52,-14.71L107.41,-14.56L107.29,-14.59L106.94,-14.33L106.78,-14.34L106.5,-14.58L106.35,-14.45L106.23,-14.48L106.17,-14.37L105.98,-14.34L106.12,-14.05L106.07,-13.92L105.9,-13.92L105.53,-14.16L105.35,-14.11L105.18,-14.35M114.06,-4.6L114.32,-4.26L114.65,-4.04L114.84,-4.39L114.75,-4.72L115.03,-4.9M-88.23,-15.73L-89.14,-15.07L-89.22,-14.87L-89.17,-14.61L-89.36,-14.42M-77.37,-8.66L-77.48,-8.5L-77.2,-7.97L-77.54,-7.57L-77.76,-7.7L-77.74,-7.54L-77.9,-7.23M-60.74,-5.2L-61.39,-5.94L-61.13,-6.21L-61.2,-6.59L-61.15,-6.69L-60.72,-6.77L-60.35,-7L-60.35,-7.15L-60.63,-7.21L-60.72,-7.54L-60.51,-7.81L-60.03,-8.05L-59.85,-8.25L-60.02,-8.55M-60.74,-5.2L-60.6,-4.95L-61,-4.54L-61.28,-4.52L-61.82,-4.2L-62.15,-4.1L-62.41,-4.16L-62.71,-4.02L-62.76,-3.67L-62.86,-3.59L-62.97,-3.59L-63.34,-3.94L-64.02,-3.93L-64.19,-4.13L-64.58,-4.14L-64.79,-4.28L-64.67,-4.01L-64.22,-3.59L-64.22,-3.2L-64.01,-2.67L-64.05,-2.5L-63.39,-2.41L-63.43,-2.16L-64.01,-1.93L-64.21,-1.53L-65.1,-1.11L-65.47,-0.69L-65.56,-0.69L-65.52,-0.84L-65.68,-0.98L-66.06,-0.79L-66.35,-0.77L-66.88,-1.22M52.49,-41.78L53.06,-42.15L54.12,-42.34L54.85,-41.97L55.43,-41.3L55.98,-41.32M55.98,-41.32L57.02,-41.26L57.12,-41.35L57.02,-41.45L56.96,-41.86L57.29,-42.12L57.81,-42.19L58.03,-42.49L58.47,-42.3L58.15,-42.63L58.48,-42.66L58.59,-42.78L58.88,-42.56L59.16,-42.51L59.35,-42.32L59.86,-42.3L59.99,-42.21L59.94,-41.97L60.2,-41.8L60.08,-41.76L60.09,-41.4L60.45,-41.22L61.24,-41.19L61.5,-41.28L61.9,-41.09L62.38,-40.33L62.48,-39.98L63.76,-39.16L64.16,-38.95L64.31,-38.98L65.61,-38.24L65.97,-38.24L66.57,-38.01L66.63,-37.93L66.53,-37.79L66.52,-37.35M49.23,-46.34L48.54,-46.61L48.56,-46.76L48.88,-46.71L48.96,-46.77L48.17,-47.71L47.48,-47.8L47.29,-47.74L47.09,-47.95L47.06,-48.23L46.66,-48.41L46.61,-48.57L46.7,-48.81L47.03,-49.15L46.8,-49.37L46.89,-49.7L47.25,-50L47.33,-50.27L47.5,-50.4L47.71,-50.38L48.33,-49.86L48.76,-49.93L48.84,-50.01L48.63,-50.61L48.81,-50.6L49.32,-50.85L49.5,-51.08L50.31,-51.32L50.79,-51.73L51.16,-51.65L51.34,-51.48L51.61,-51.48L52.22,-51.71L52.57,-51.48L53.34,-51.48L54.14,-51.04L54.56,-50.54L54.65,-50.66L54.55,-50.95L54.64,-51.01L55.69,-50.58L56.49,-51.02L57.01,-51.07L57.44,-50.89L57.65,-50.93L57.84,-51.09L58.36,-51.06L58.88,-50.69L59.45,-50.62L59.52,-50.49L59.81,-50.58L60.06,-50.85L60.42,-50.68L60.94,-50.7L61.39,-50.86L61.59,-51.23L61.55,-51.32L60.46,-51.65L60.39,-51.77L60.03,-51.93L60.99,-52.34L60.77,-52.68L61.05,-52.97L62.08,-53.01L61.66,-53.23L61.2,-53.29L61.23,-53.45L61.53,-53.52L60.98,-53.62L61.23,-54.02L61.93,-53.95L64.46,-54.38L65.09,-54.34L65.48,-54.62L68.16,-54.98L68.24,-55.05L68.21,-55.16L68.98,-55.39L69.49,-55.36L70.18,-55.16L70.74,-55.31L71.19,-54.6L71.09,-54.21L72,-54.21L72.19,-54.33L72.45,-53.94L72.59,-54L72.62,-54.13L73.23,-53.96L73.67,-54.06L73.68,-53.93L73.31,-53.71L73.41,-53.45L73.86,-53.62L74.35,-53.49L74.45,-53.65L75.22,-53.89L75.44,-54.09L76.84,-54.44L76.65,-54.15L76.42,-54.15L76.48,-54.02L77.86,-53.27L79.47,-51.49L79.99,-50.77L80.42,-50.95L80.45,-51.18L80.74,-51.29L81.13,-51.19L81.07,-50.97L81.39,-50.96L81.47,-50.74L82.49,-50.73L82.76,-50.89L83.36,-50.99L83.95,-50.77L84.32,-50.24L84.99,-50.06L85,-49.89L85.23,-49.62L86.18,-49.5L86.68,-49.78L86.73,-49.7L86.63,-49.56L87.32,-49.09M34.2,-31.32L34.9,-29.48M33.98,-4.22L34.38,-4.62M41.88,-3.98L41.14,-3.96L40.77,-4.27L39.84,-3.85L39.54,-3.47L39.23,-3.48L38.09,-3.65L36.91,-4.41L36.08,-4.45L35.92,-4.62M23.38,17.64L21.42,18L20.75,18.02L20.39,17.89L18.96,17.8L18.4,17.4L14.02,17.41L13.48,17.04L13.1,16.97L12.55,17.21L12.01,17.17L11.74,17.25M25.26,17.79L26,17.97L26.33,17.93L26.78,18.04L27.02,17.96L27.93,16.9L28.76,16.53L28.91,15.99L29.49,15.7L30.4,15.64M23.38,17.64L24.27,17.48L24.73,17.52L25,17.57L25.26,17.79M31.29,22.4L32.43,21.3L32.35,21.14L32.48,20.95L32.49,20.66L32.99,19.98L32.78,19.39L32.85,19.1L32.7,18.94L32.88,18.73L32.99,18.36L32.97,17.25L32.88,16.88L32.95,16.71L32.24,16.45L31.94,16.43L31.69,16.21L31.24,16.02L30.44,16L30.4,15.64M12.28,6L12.42,6.05L13.18,5.86L16.43,5.9L16.7,6.16L16.74,6.62L16.98,7.26L17.58,8.1L18.01,8.11L18.56,7.94L19.34,7.97L19.53,7.14L19.88,6.99L20.59,6.92L20.54,7.18L20.61,7.28L21.78,7.31L21.91,8.69L21.81,9.47L22.27,10.26L22.31,10.69L22.18,10.89L22.23,11.12L22.31,11.2L22.56,11.06L23.83,11.01L23.97,10.87M-16.56,-13.59L-15.51,-13.59L-15.43,-13.73L-15.02,-13.81L-14.41,-13.5L-13.98,-13.54L-13.85,-13.48L-13.85,-13.34L-14.25,-13.24L-15.15,-13.56L-15.29,-13.4L-15.81,-13.33L-15.83,-13.16L-16.65,-13.15L-16.76,-13.06M0.22,-14.91L0.16,-14.5L0.38,-14.25L0.43,-13.97L0.62,-13.7L0.9,-13.61L1.2,-13.36L0.99,-13.36L0.99,-13.04L1.56,-12.64L2.1,-12.7L2.23,-12.47L2.07,-12.31L2.39,-11.9M18.61,-3.48L18.47,-3.62L18.16,-3.5L17.49,-3.69L16.61,-3.51L16.48,-3.17L16.47,-2.83L16.18,-2.27M16.18,-2.26L16.08,-2.11L16.14,-1.72L16.06,-1.68L15.74,-1.92L14.9,-2.01L14.58,-2.2L13.29,-2.16M15.48,-7.52L15.21,-7.21L14.74,-6.28L14.43,-6.04L14.62,-5.87L14.56,-5.28L14.73,-4.6L15.06,-4.28L15.14,-4.04L15.03,-4.02L15.13,-3.83L16.06,-2.91L16.18,-2.26M33.98,-4.22L33.49,-3.76L33.15,-3.77L33,-3.88L32.34,-3.71L32.14,-3.52L31.8,-3.8L31.55,-3.68L31.15,-3.79L30.84,-3.49M13.07,4.63L12.45,5.07L12.52,5.15L12.5,5.7L12.21,5.76M31.95,25.96L31.99,24.46L31.8,23.89L31.55,23.48L31.29,22.4M33.2,14.01L30.23,14.99L30.4,15.64M34.96,11.58L34.62,11.62L34.36,12.16L34.56,13.36L34.66,13.49L34.91,13.55L35.25,13.9L35.85,14.67L35.89,14.89L35.76,16.06L35.36,16.16L35.17,16.56L35.29,17.1L35.06,17.08L35.08,16.83L34.42,16.25L34.25,15.89L34.54,15.3L34.51,14.6L34.33,14.41L33.64,14.57L33.2,14.01M29.58,1.39L29.72,-0.1L29.93,-0.5L29.94,-0.82L31.25,-2.04L31.18,-2.27L30.73,-2.46L30.85,-2.89L30.75,-3.04L30.91,-3.41L30.84,-3.49M36.52,-14.26L36.43,-15.13L36.91,-16.3L36.89,-16.62L37.01,-17.06L37.41,-17.06L37.55,-17.32L38.25,-17.58L38.61,-18.01M42.38,-12.47L40.82,-14.11L40.14,-14.46L39.53,-14.54L39.2,-14.48L39.02,-14.63L38.81,-14.48L38.43,-14.43L37.88,-14.85L37.57,-14.15L37.26,-14.45L37.02,-14.27L36.52,-14.26M27.35,-57.53L27.54,-57.8L27.78,-57.87L27.5,-58.22L27.43,-58.79L27.9,-59.28L28.15,-59.37L28.01,-59.48M74.31,-32.81L74.66,-32.76L74.69,-32.49L75.3,-32.32M-84.35,-10.98L-84.7,-11.05L-84.91,-10.95L-85.58,-11.19L-85.74,-11.06M-82.88,-8.07L-83.03,-8.34L-82.86,-8.45L-82.92,-8.74L-82.73,-8.92L-82.94,-9.06L-82.94,-9.45L-82.8,-9.59L-82.64,-9.51L-82.56,-9.58M-66.88,-1.22L-67.21,-2.39L-67.62,-2.79L-67.86,-2.79L-67.31,-3.42L-67.66,-3.86L-67.86,-4.51L-67.82,-5.27L-67.47,-5.93L-67.48,-6.18L-67.86,-6.29L-68.47,-6.16L-69.43,-6.12L-70.13,-6.95L-70.74,-7.09L-71.13,-6.99L-72.01,-7.03L-72.21,-7.37L-72.47,-7.52L-72.39,-8.29L-72.67,-8.63L-72.8,-9.11L-73.06,-9.26L-73.37,-9.19L-73.01,-9.79L-72.87,-10.49L-72.69,-10.84L-72.45,-11.11L-72.25,-11.2L-71.96,-11.67L-71.32,-11.86M-68.44,52.36L-68.46,52.29L-69.96,52.01L-71.97,51.96L-71.95,51.88L-72.41,51.54L-72.3,51.3L-72.38,51.1L-72.28,50.91L-72.34,50.68L-72.51,50.61L-73.15,50.74L-73.5,50.13L-73.48,49.77M-68.63,52.65L-68.65,54.92L-67.35,54.93L-66.48,55.11M22.77,-54.36L19.6,-54.46M48.44,-28.54L47.67,-28.53L47.43,-28.99L46.53,-29.1M44.77,-37.14L45.36,-36.02L45.78,-35.82L46.27,-35.77L46,-35.61L46.13,-35.13L45.68,-34.8L45.64,-34.57L45.5,-34.58L45.44,-34.42L45.54,-34.22L45.4,-33.97L46.02,-33.42L46.15,-33.23L46.11,-32.96L46.38,-32.93L47.12,-32.47L47.37,-32.42L47.83,-31.79L47.68,-31.4L47.68,-31L48.01,-30.99L48.01,-30.47L48.33,-30.29L48.55,-29.96M61.26,-35.62L61.12,-36.64L60.34,-36.64L60.06,-36.96L59.45,-37.25L59.3,-37.51L58.82,-37.68L58.26,-37.67L57.98,-37.83L57.35,-37.97L57.19,-38.22L56.44,-38.25L56.27,-38.08L55.38,-38.05L54.9,-37.78L54.7,-37.47L53.91,-37.34M140.97,2.6L140.97,6.35L140.86,6.74L140.98,6.91L140.98,9.12M9.52,-30.23L9.31,-30.12L9.64,-29.64L9.81,-29.18L9.92,-27.79L9.75,-27.33L9.88,-26.63L9.49,-26.33L9.45,-26.07L10,-25.33L10.03,-25.05L10.26,-24.59L10.4,-24.49L10.69,-24.55L11.51,-24.31L11.97,-23.52M-13.73,-12.67L-15.2,-12.68L-15.57,-12.49L-16.71,-12.35M-11.39,-12.4L-12.4,-12.34L-12.93,-12.53L-13.06,-12.49L-13.08,-12.63L-13.73,-12.67M0.9,-10.99L0.49,-10.95L-0.07,-11.12M-139.06,-60L-139.19,-60.08L-139.08,-60.34L-139.68,-60.33L-139.97,-60.18L-140.45,-60.3L-140.53,-60.22L-141,-60.3L-141,-69.65M-130.62,-54.71L-130.02,-55.28L-130.12,-55.69L-130.03,-55.89L-130.06,-56.07L-130.41,-56.12L-130.74,-56.34L-131.58,-56.6L-131.82,-56.59L-131.87,-56.79L-132.1,-56.86L-132.03,-57.03L-132.34,-57.08L-132.23,-57.2L-133.42,-58.34L-133.4,-58.41L-134.3,-58.9L-134.44,-59.09L-134.94,-59.29L-135.07,-59.44L-135.05,-59.58L-135.48,-59.79L-136.32,-59.6L-136.25,-59.53L-136.47,-59.46L-136.47,-59.28L-136.58,-59.15L-136.81,-59.15L-137.44,-58.9L-137.52,-58.92L-137.59,-59.23L-138.63,-59.78L-138.71,-59.9L-139.06,-60M-123.31,-48.99L-122.69,-48.99M-88.89,-15.89L-89.24,-15.89L-89.16,-17.81M-75.28,0.11L-75.63,0.12L-75.26,0.59L-75.25,0.95L-75.41,0.92L-75.57,1.53L-76.09,2.13L-76.68,2.56L-77.86,2.98L-78.18,3.35L-78.16,3.47L-78.35,3.4L-78.68,4.33L-78.69,4.56L-78.91,4.71L-79.03,4.97L-79.33,4.93L-79.64,4.45L-79.8,4.48L-80.14,4.3L-80.38,4.46L-80.48,4.43L-80.35,4.21L-80.49,4.17L-80.49,4.01L-80.3,4.01L-80.18,3.88L-80.32,3.39M-69.97,4.24L-70.34,3.81L-70.53,3.87L-70.74,3.78L-70.07,2.75L-70.1,2.66L-70.97,2.21L-71.4,2.33L-71.75,2.15L-72.22,2.4L-72.94,2.39L-73.15,2.28L-73.2,1.83L-73.5,1.69L-73.52,1.45L-73.66,1.25L-74.25,0.97L-74.42,0.58L-74.8,0.2L-75.14,0.05L-75.28,0.11M-66.88,-1.22L-67.08,-1.19L-67.12,-1.7L-67.4,-2.12L-67.94,-1.75L-68.19,-1.99L-68.26,-1.85L-68.18,-1.72L-69.54,-1.77L-69.85,-1.71L-69.85,-1.06L-69.31,-1.05L-69.16,-0.86L-69.15,-0.66L-69.47,-0.73L-70.05,-0.58L-70.07,0.14L-69.63,0.51L-69.61,0.76L-69.4,1.19L-69.97,4.24M-69.58,10.95L-68.69,12.5L-68.98,12.88L-68.98,13.5L-69.07,13.68L-68.87,14.17L-69.36,14.8L-69.37,14.96L-69.17,15.24L-69.42,15.64L-69.22,16.15L-68.84,16.34L-69.03,16.48L-69.02,16.64L-69.62,17.2L-69.51,17.5M-69.58,10.95L-68.85,11.01L-68.62,11.11L-68.31,10.98L-68.07,10.7L-67.72,10.68L-67.42,10.39L-66.58,9.9L-65.4,9.71L-65.3,10.15L-65.45,10.51L-65.32,11.02L-65.39,11.25L-65.19,11.75L-65.09,11.74L-64.99,11.98L-64.51,12.25L-64.42,12.44L-63.94,12.53L-63.69,12.48L-63.35,12.68L-63.07,12.67L-62.77,13L-62.12,13.16L-61.79,13.53L-61.08,13.49L-60.51,13.79L-60.27,15.09L-60.58,15.1L-60.24,15.48L-60.18,16.27L-58.35,16.28L-58.48,16.7L-58.4,17.23L-57.99,17.51L-57.83,17.51L-57.5,18.21L-57.78,18.91L-57.72,19.04L-58.13,19.74L-57.86,19.98L-58.16,20.16M-69.97,4.24L-70.05,4.33L-70.4,4.15L-70.8,4.17L-70.97,4.35L-71.84,4.5L-72.89,5.12L-72.98,5.63L-73.24,6.1L-73.14,6.47L-73.76,6.91L-73.8,7.08L-73.72,7.31L-73.96,7.38L-74,7.56L-73.72,7.78L-73.78,7.94L-73.55,8.35L-72.97,8.99L-72.97,9.12L-73.21,9.41L-72.38,9.51L-72.14,10.01L-71.24,9.97L-70.54,9.44L-70.64,9.82L-70.64,11.01L-70.53,10.95L-70.29,11.06L-69.96,10.93L-69.58,10.95M-62.65,22.23L-62.28,21.07L-62.28,20.56L-61.92,20.06L-61.76,19.65L-60.01,19.3L-59.09,19.29L-58.18,19.82L-58.16,20.16M-17.05,-20.81L-16.96,-21.33L-13.02,-21.33L-13.15,-22.82L-12.62,-23.27L-12.02,-23.47L-12.02,-26L-8.68,-26L-8.68,-27.29M-8.68,-27.29L-4.82,-25M-8.68,-27.66L-8.66,-28.72L-7.16,-29.61L-6.64,-29.57L-6.48,-29.82L-5.45,-29.96L-4.97,-30.47L-3.99,-30.91L-3.67,-30.96L-3.62,-31.07L-3.83,-31.2L-3.83,-31.66L-3.02,-31.83L-2.86,-32.07L-1.28,-32.09M-8.68,-27.29L-8.68,-27.66M-12.28,-14.81L-13.21,-15.62L-13.41,-16.06L-13.87,-16.15L-14.09,-16.42L-14.53,-16.66L-14.99,-16.68L-15.77,-16.49L-16.24,-16.53L-16.54,-15.84M-4.82,-25L-6.59,-24.99L-5.63,-16.57L-5.36,-16.28L-5.51,-15.5L-9.18,-15.5L-9.34,-15.53L-9.35,-15.68L-9.45,-15.46L-9.94,-15.37L-10.7,-15.42L-10.95,-15.15L-11.5,-15.64L-11.76,-15.43L-11.94,-14.89L-12.1,-14.75L-12.28,-14.81M4.23,-19.14L3.26,-19.01L3.11,-19.15L3.26,-19.41L3.13,-19.85L2.41,-20.06L2.22,-20.25L1.75,-20.33L1.61,-20.56L1.17,-20.82L1.15,-21.1L-4.82,-25M4.23,-19.14L5.84,-19.48L7.48,-20.87L11.97,-23.52M9.52,-30.23L9.04,-32.07L8.33,-32.54L8.11,-33.06L7.73,-33.27L7.5,-33.83L7.51,-34.08L8.25,-34.73L8.39,-35.2L8.25,-35.8L8.35,-36.37L8.21,-36.52L8.6,-36.83L8.58,-36.94M23.98,-19.5L15.98,-23.45L14.98,-23M24.98,-22L24.98,-20L23.98,-20L23.98,-19.5M25.15,-31.65L24.85,-31.33L24.96,-30.68L24.7,-30.2L24.98,-29.18L24.98,-22M22.86,-10.92L22.92,-11.34L22.59,-11.58L22.58,-11.99L22.47,-12.07L22.35,-12.66L21.93,-12.68L21.83,-12.79L21.99,-13.11L22.23,-13.33L22.11,-13.8L22.54,-14.16L22.38,-14.55L22.67,-14.72L22.76,-15L22.93,-15.16L22.93,-15.53L23.11,-15.7L23.97,-15.72L23.98,-19.5M24.98,-22L31.21,-21.99L31.4,-22.2L31.49,-22.15L31.43,-22L36.87,-22M41.88,-3.98L40.96,-2.81L40.98,0.87L41.53,1.7M42.92,-11L42.66,-10.6L42.84,-10.2L43.18,-9.88L43.48,-9.38L43.98,-9.01L46.98,-8L47.98,-8M30.75,8.19L28.9,8.49L28.87,8.79L28.4,9.22L28.6,9.68L28.65,10.55L28.38,11.57L28.48,11.81L29.06,12.35L29.49,12.42L29.51,12.23L29.8,12.16L29.78,13.44L29.65,13.41L29.55,13.25L29.2,13.4L29.01,13.37L28.73,12.93L28.55,12.84L28.41,12.52L27.57,12.23L27.16,11.58L27.05,11.62L26.95,11.9L26.82,11.97L26.03,11.89L25.51,11.75L25.35,11.62L25.29,11.21L24.38,11.42L24.37,11.13L23.97,10.87M23.38,17.64L22.15,16.6L22.04,16.26L21.98,13L23.96,12.99L23.88,12.8L23.99,12.42L23.97,11.64L24.05,11.41L23.97,10.87M33.9,1L33.94,-0.17L34.48,-1.04L34.8,-1.24L34.98,-1.77L34.91,-2.48L34.45,-3.16L34.44,-3.65L34.17,-3.81L33.98,-4.22M33.9,1L37.64,3.05L37.62,3.51L39.22,4.69M11.33,-2.17L9.98,-2.17L9.8,-2.3M11.33,-2.17L11.34,-1L9.91,-0.96L9.76,-1.07L9.59,-1.03M25.26,17.79L24.91,17.82L24.53,18.05L24.24,18.02L23.6,18.46L23.22,18L20.97,18.32L20.98,21.96L19.98,22L19.98,24.75M19.98,24.78L19.98,28.45L19.54,28.57L19.16,28.94L18.1,28.87L17.45,28.7L17.36,28.27L17.06,28.03L16.88,28.13L16.76,28.45L16.45,28.62M0.9,-10.99L0.76,-10.39L1.33,-10L1.39,-9.36L1.6,-9.05L1.62,-7L1.53,-6.99L1.6,-6.61L1.78,-6.29L1.62,-6.22M42.8,-16.37L43.17,-16.69L43.19,-17.36L43.42,-17.52L43.92,-17.32L45.15,-17.43L45.54,-17.3L46.73,-17.27L46.98,-16.95L47.14,-16.95L47.44,-17.11L47.58,-17.45L48.17,-18.16L49.04,-18.58L51.98,-19M51.98,-19L53.09,-16.65M55.19,-22.7L55.64,-22L54.98,-20L51.98,-19M55.19,-22.7L55.1,-22.62L52.56,-22.93L51.59,-24.08L51.57,-24.29M42.36,-37.11L41.79,-36.6L41.42,-36.51L41.3,-36.38L41.25,-36.07L41.35,-35.64L41.22,-35.29L41.19,-34.77L40.99,-34.43L38.77,-33.37M35.79,-32.73L36.37,-32.39L36.82,-32.32L38.77,-33.37M35.61,-32.68L35.79,-32.73M39.15,-32.12L39.29,-32.24L39.25,-32.35L39.04,-32.31L38.98,-32.47L39.06,-32.49L38.77,-33.37M34.95,-29.35L36.07,-29.2L36.48,-29.5L36.76,-29.87L37.47,-30L37.65,-30.33L37.98,-30.5L36.96,-31.49L38.96,-31.99L39.15,-32.12M46.53,-29.1L44.69,-29.2L42.07,-31.08L40.37,-31.94L39.15,-32.12M61.59,-25.2L61.66,-25.75L61.84,-26.23L62.24,-26.36L62.44,-26.56L63.16,-26.65L63.3,-27.15L63.17,-27.25L62.76,-27.25L62.76,-28.24L62.56,-28.24L62.35,-28.41L61.89,-28.55L61.62,-28.79L61.32,-29.37L60.84,-29.86M60.84,-29.86L61.81,-30.91L61.76,-31.29L61.66,-31.38L60.82,-31.5L60.83,-32.25L60.56,-33.06L60.92,-33.51L60.51,-33.64L60.49,-34.09L60.64,-34.31L60.89,-34.32L60.73,-34.52L61.08,-34.86L61.1,-35.27L61.19,-35.31L61.26,-35.62M73.73,-36.89L74.04,-36.83L74.54,-37.02M60.84,-29.86L62.48,-29.41L63.57,-29.5L64.1,-29.39L64.39,-29.54L65.1,-29.56L66.18,-29.84L66.31,-29.97L66.24,-30.11L66.35,-30.8L66.83,-31.26L67.45,-31.23L67.74,-31.34L67.58,-31.51L68.16,-31.8L68.6,-31.8L68.87,-31.63L69.28,-31.94L69.24,-32.43L69.5,-33.02L70.26,-33.29L70.13,-33.62L69.87,-33.9L69.89,-34.01L70.65,-33.95L71.05,-34.05L71.1,-34.37L70.97,-34.53L71.62,-35.18L71.55,-35.29L71.57,-35.55L71.4,-35.88L71.19,-36.04L71.23,-36.12L71.62,-36.44L71.77,-36.43L72.25,-36.73L73.73,-36.89M70.95,-42.25L70.58,-42.04L70.42,-42.08L70.1,-41.82L69.15,-41.43L68.58,-40.88L68.57,-40.62L68.42,-40.62L68.05,-40.81L68.11,-41.03L67.94,-41.2L66.71,-41.18L66.5,-41.99L66.01,-42L66.1,-42.99L65.8,-42.88L65.5,-43.31L64.91,-43.71L64.44,-43.55L63.21,-43.63L61.99,-43.49L61.16,-44.17L61.01,-44.39L58.56,-45.56L55.98,-44.99L55.98,-41.32M13.61,-13.7L13.45,-14.38L14.37,-15.75L15.47,-16.91L15.74,-19.9L15.96,-20.35L15.59,-20.73L15.61,-20.95L15.18,-21.52L14.98,-23M11.97,-23.52L13.48,-23.18L14.22,-22.62L14.98,-23M0.22,-14.91L0.29,-14.98L0.95,-14.98L1.3,-15.27L3,-15.34L3.06,-15.43L3.5,-15.36L3.52,-15.48L3.84,-15.7L4.12,-16.36L4.23,-17L4.23,-19.14M-0.07,-11.12L-0.3,-11.17L-0.63,-10.93L-1.04,-11.01L-2.83,-11L-2.91,-10.59L-2.79,-10.43L-2.7,-9.48M-13.29,-9.05L-13.03,-9.1L-12.43,-9.9L-11.27,-10L-10.69,-9.31L-10.75,-9.1L-10.62,-9.06L-10.5,-8.69L-10.71,-8.34L-10.56,-8.32L-10.28,-8.49M5.79,-49.54L6.34,-49.45M56.08,-26.06L56.17,-26.05L56.14,-25.69L56.3,-25.65M30.51,1.07L30.36,1.07L29.93,1.47L29.83,1.34L29.58,1.39M30.51,1.07L30.51,1.21L30.81,1.56L30.88,2.14L30.83,2.34L30.55,2.4M33.9,1L30.81,0.99L30.51,1.07M34.59,11.97L34.59,11.97M87.32,-49.09L87.82,-49.16M12.44,-43.98L12.44,-43.98M70.57,-41.02L70.57,-41.02M-117.13,-32.53L-114.72,-32.72L-114.84,-32.51L-111.04,-31.32L-108.21,-31.33L-108.21,-31.78L-106.45,-31.77L-106.15,-31.45L-104.92,-30.58L-104.62,-29.85L-104.4,-29.57L-103.26,-29L-102.89,-29.22L-102.73,-29.64L-102.34,-29.86L-101.38,-29.74L-100.75,-29.18L-100.3,-28.33L-99.51,-27.55L-99.46,-27.06L-99.11,-26.45L-97.38,-25.87L-97.15,-25.96M-92.24,-14.55L-92.07,-15.07L-92.2,-15.28L-91.74,-16.07L-90.45,-16.07L-90.42,-16.39L-91.41,-17.26L-90.99,-17.25L-90.99,-17.82L-89.16,-17.81L-89.13,-17.97L-88.81,-17.97L-88.46,-18.48L-88.04,-18.42L-88.04,-18.2L-87.83,-18.18M-54.62,25.58L-54.44,25.12L-54.32,24.13L-54.24,24.05L-54.63,23.81L-55.19,24.02L-55.42,23.95L-55.65,22.89L-55.62,22.67L-55.85,22.31L-56.25,22.26L-56.45,22.08L-56.63,22.23L-56.94,22.27L-57.96,22.11L-57.83,21L-58.16,20.16M-62.65,22.23L-62.21,22.61L-61.8,23.18L-61.03,23.76L-59.89,24.09L-59.19,24.56L-58.37,24.96L-57.96,25.05L-57.64,25.33L-57.57,25.53L-58.11,26.18L-58.19,26.63L-58.62,27.13L-58.6,27.31L-58.17,27.27L-56.44,27.55L-56.16,27.32L-55.71,27.41L-55.43,27.01L-55.14,26.93L-54.83,26.65L-54.68,26.31L-54.62,25.58M-62.65,22.23L-62.84,22L-63.92,22.03L-64.33,22.83L-64.61,22.23L-64.99,22.11L-65.77,22.1L-66.22,21.8L-66.37,22.11L-66.71,22.22L-67.19,22.82M26.62,-48.26L26.85,-48.39L27.23,-48.37L27.55,-48.48L28.29,-48.24L28.46,-48.09L28.77,-48.12L28.92,-47.95L29.13,-47.96L29.21,-47.78L29.13,-47.49L29.54,-47.27L29.57,-46.96L29.88,-46.83L29.92,-46.54L30.13,-46.42L29.84,-46.35L29.71,-46.45L29.3,-46.47L29.2,-46.38L29.19,-46.52L28.96,-46.46L28.95,-46.05L28.49,-45.67L28.5,-45.52L28.21,-45.45M67.76,-37.17L68.07,-36.95L68.91,-37.33L69.3,-37.12L69.41,-37.21L69.49,-37.55L70.19,-37.58L70.21,-37.92L70.62,-38.33L70.88,-38.46L71.26,-38.31L71.33,-38.17L71.28,-37.92L71.58,-37.91L71.43,-37.13L71.67,-36.7L72.66,-37.03L72.9,-37.27L73.38,-37.46L73.72,-37.42L73.65,-37.24L74.35,-37.42L74.66,-37.39L74.89,-37.23M66.52,-37.35L66.83,-37.37L67.76,-37.17M61.26,-35.62L61.62,-35.43L61.98,-35.44L62.31,-35.17L62.69,-35.26L63.06,-35.45L63.17,-35.68L63.13,-35.85L64.01,-36.01L64.51,-36.34L64.82,-37.13L65.09,-37.24L65.55,-37.25L65.77,-37.57L66.52,-37.35M92.57,-21.98L92.25,-23.68L91.93,-23.69L91.94,-23.5L91.75,-23.29L91.75,-23.05L91.62,-22.98L91.44,-23.2L91.32,-23.1L91.16,-23.66L91.37,-24.09L91.88,-24.2L91.95,-24.36L92.1,-24.41L92.23,-24.88L92.44,-24.85L92.47,-24.94L92.05,-25.17L90.44,-25.16L89.83,-25.29L89.82,-25.94L89.67,-26.21L89.55,-26.01L89.37,-26.01L89.19,-26.11L89.02,-26.41L88.92,-26.38L88.97,-26.25L88.83,-26.25L88.42,-26.57L88.35,-26.5L88.44,-26.37L88.15,-26.09L88.08,-25.89L88.5,-25.54L88.77,-25.49L88.95,-25.26L88.82,-25.18L88.46,-25.19L88.31,-24.88L88.15,-24.91L88.02,-24.63L88.15,-24.49L88.72,-24.27L88.57,-23.67L88.74,-23.44L88.72,-23.25L88.93,-23.19L88.85,-23.04L89.05,-22.09M2.39,-11.9L2.37,-12.22L2.81,-12.38L3.6,-11.7M18.61,-3.48L18.49,-2.92L18.07,-2.01L18.06,-1.53L17.9,-1.12L17.89,-0.23L17.72,0.28L17.75,0.55L17.28,1L16.88,1.23L16.54,1.84L16.22,2.18L16.22,3.03L16.15,3.46L15.99,3.77L15.87,3.93L15.6,4.03L15.27,4.31L14.71,4.88L14.41,4.83L14.37,4.59L14.45,4.45L14.36,4.3L13.94,4.48L13.72,4.45L13.66,4.72L13.41,4.84L13.07,4.63M28.98,30L28.98,30M29.36,22.19L29.66,22.15L30.19,22.29L30.92,22.29L31.29,22.4M19.98,24.78L20.43,25.15L20.79,25.92L20.82,26.16L20.63,26.44L20.69,26.82L21.69,26.84L22.6,26.13L22.88,25.46L23.06,25.31L23.39,25.29L23.89,25.6L24.75,25.82L25.44,25.71L25.58,25.61L25.91,24.75L26.4,24.61L26.84,24.24L27.09,23.58L27.76,23.2L28.21,22.69L28.84,22.48L29.13,22.21L29.36,22.19M34.96,11.58L35.56,11.6L35.91,11.45L36.31,11.71L36.98,11.57L37.37,11.71L37.72,11.58L37.92,11.29L38.18,11.28L38.49,11.41L38.79,11.23L39.32,11.12L39.99,10.82L40.46,10.46M-84.35,-10.98L-84.17,-10.78L-83.92,-10.74L-83.71,-10.79L-83.64,-10.92M28.15,-56.14L27.9,-56.08L27.58,-55.8L27.05,-55.83L26.59,-55.67M28.21,-45.45L28.76,-45.23L28.78,-45.31L29.4,-45.42L29.71,-45.26M21.36,-44.83L22.09,-44.54L22.5,-44.71L22.64,-44.65L22.73,-44.57L22.55,-44.54L22.49,-44.44L22.71,-44.24M32.11,26.84L32.89,26.85M71.74,-39.98L71.74,-39.98M-122.69,-48.99L-95.16,-48.99L-95.16,-49.37L-94.85,-49.3L-94.8,-49L-94.62,-48.74L-93.71,-48.53L-93,-48.61L-92.5,-48.44L-92.41,-48.28L-92.01,-48.3L-91.52,-48.06L-90.92,-48.21L-90.74,-48.1L-90.09,-48.12L-89.9,-48L-89.46,-48L-88.38,-48.3L-84.88,-46.9L-84.78,-46.64L-84.56,-46.46L-84.15,-46.54L-83.98,-46.08L-83.62,-46.12L-83.47,-45.99L-83.59,-45.82L-82.55,-45.35L-82.14,-43.57L-82.55,-42.62L-83.07,-42.3L-83.15,-42.14L-83.03,-41.83L-82.69,-41.68L-82.44,-41.67L-81.28,-42.21L-80.25,-42.37L-79.04,-42.8L-78.92,-42.91L-79.17,-43.47L-78.85,-43.58L-76.82,-43.63L-76.15,-44.3L-75,-44.97L-71.52,-45.01L-71.33,-45.29L-71,-45.34L-70.87,-45.27L-70.69,-45.43L-70.7,-45.55L-70.3,-45.91L-70.25,-46.25L-70.07,-46.44L-70.01,-46.71L-69.24,-47.46L-69.05,-47.43L-69.05,-47.27L-68.94,-47.21L-68.24,-47.35L-67.81,-47.08L-67.8,-45.73L-67.43,-45.6L-67.47,-45.28L-67.37,-45.17L-67.12,-45.17M34.96,11.58L34.61,11.08L34.66,10.71L34.52,10.03L34.09,9.54L34,9.5L33.89,9.67M107.97,-21.51L107.76,-21.66L107.35,-21.61L106.97,-21.92L106.66,-21.98L106.55,-22.5L106.78,-22.78L106.54,-22.91L106.28,-22.86L106.15,-22.97L105.84,-22.92L105.28,-23.35L104.86,-23.14L104.69,-22.82L104.37,-22.7L104.14,-22.8L103.94,-22.54L103.62,-22.78L103.49,-22.59L103.33,-22.77L102.98,-22.45L102.47,-22.75L102.13,-22.38M114.02,-22.51L114.27,-22.54M70.61,-39.79L70.61,-39.79M71.22,-39.91L71.22,-39.91M145.94,-43.1L145.78,-43.48L145.54,-43.51L145.24,-43.78L145.62,-44.29L145.58,-44.79M-1.28,-32.09L-1.24,-32.34L-1.07,-32.47L-1.45,-32.78L-1.68,-33.32L-1.63,-33.57L-1.79,-34.37L-1.73,-34.47L-1.85,-34.61L-1.8,-34.75L-2.22,-35.1M29,-9.61L29.47,-9.77L29.61,-10.07L30,-10.28L30.76,-9.73L31.22,-9.8L31.79,-10.38L31.93,-10.66L32.42,-11.09L32.34,-11.72L32.07,-12.01L32.74,-12.01L32.72,-12.22L33.2,-12.22L33.07,-11.59L33.13,-10.76L33.91,-10.18L33.96,-9.86L33.87,-9.51L34.08,-9.46M24.15,-8.67L24.53,-8.89L24.78,-9.53L24.79,-9.81L25.1,-10.31L25.86,-10.41L25.92,-10.17L26.66,-9.48L27.07,-9.61L27.88,-9.6M27.88,-9.6L28.05,-9.33L28.84,-9.33L28.84,-9.46L29,-9.61M-56.48,-1.94L-56.7,-2.04L-57.2,-2.85L-57.3,-3.38L-57.6,-3.37M-54.62,-2.33L-54.4,-2.46L-54.2,-2.82L-54.2,-3.14L-54.08,-3.33M33.89,9.67L33.42,9.61L32.92,9.41M33.59,-46.1L33.66,-46.22L34.22,-46.1L34.45,-45.97L34.69,-45.98L34.8,-45.79L35,-45.73M77.05,-35.11L76.77,-35.66M77.05,-35.11L77.8,-35.5M79.12,-33.23L79.38,-33.15L79.33,-32.98L79.5,-32.73L79.22,-32.5M79.22,-32.5L78.92,-32.36L78.7,-32.6L78.41,-32.56L78.49,-32.23M78.49,-32.23L78.73,-31.98L78.72,-31.88M78.72,-31.88L78.69,-31.74L78.8,-31.62L78.74,-31.32L78.84,-31.3M78.84,-31.3L79.11,-31.4L79.37,-31.08M79.37,-31.08L79.57,-30.95L79.91,-30.9M79.91,-30.9L80.19,-30.76L80.19,-30.57M80.19,-30.57L80.68,-30.41L81.01,-30.16M90.33,-28.12L90.35,-28.24L90.22,-28.28L89.8,-28.24M89.8,-28.24L89.48,-28.06L89.12,-27.62M89.12,-27.62L89.02,-27.51M89.02,-27.51L88.89,-27.32M75.3,-32.32L75.25,-32.14L74.56,-31.82L74.52,-31.19L74.63,-31.03L74.34,-30.89L73.9,-30.44L73.93,-30.22L73.81,-30.09L73.38,-29.93L72.9,-29.03L72.34,-28.75L71.87,-27.96L70.8,-27.71L70.63,-27.94L70.4,-28.03L70.14,-27.85L69.54,-27.12L69.51,-26.74L70.15,-26.51L70.1,-25.91L70.26,-25.71L70.65,-25.67L70.65,-25.42L71.05,-24.69L70.97,-24.57L71.04,-24.4L70.72,-24.24L70.49,-24.41L69.81,-24.17L69.56,-24.27L68.78,-24.31L68.72,-23.96L68.17,-23.86M36.69,-45.62L36.64,-45.26L36.51,-45.2L36.61,-44.95M-55.81,31.03L-56,31.08L-56,30.85M-56,30.85L-56.83,30.11L-57.12,30.14L-57.21,30.28L-57.61,30.19M-73.48,49.77L-73.58,49.58L-73.46,49.31L-73.14,49.3M-73.14,49.3L-73.03,49.01L-72.65,48.84L-72.58,48.48L-72.35,48.37L-72.29,48.23L-72.52,47.88L-72.35,47.49L-71.9,47.2L-71.94,46.83L-71.7,46.65L-71.88,46.16L-71.63,45.95L-71.75,45.84L-71.75,45.58L-71.51,45.51L-71.35,45.33L-71.6,44.98L-72.04,44.9L-72.06,44.77L-71.26,44.76L-71.16,44.56L-71.21,44.44L-71.82,44.38L-71.81,44.11L-71.68,43.93L-71.9,43.35L-71.75,43.24L-72.1,43.07L-72.14,42.58L-72.05,42.47L-72.11,42.25L-71.75,42.05L-71.91,41.65L-71.87,40.89L-71.94,40.79L-71.7,40.34L-71.82,40.18L-71.66,40.02L-71.72,39.64L-71.54,39.6L-71.4,38.94L-70.95,38.74L-70.85,38.54L-70.97,38.45L-71.17,37.76L-71.2,37.3L-71.12,37.11L-71.19,36.84L-71.06,36.52L-70.75,36.39L-70.4,36.06L-70.42,35.52L-70.56,35.25L-70.39,35.15L-70.05,34.3L-69.85,34.22L-69.82,33.28L-70.08,33.2L-70.02,32.88L-70.36,32.08L-70.25,31.96L-70.45,31.84L-70.59,31.57L-70.52,31.15L-70.31,31.02L-70.35,30.9L-70.15,30.36L-69.96,30.36L-69.84,30.18L-69.96,30.08L-70.03,29.32L-69.83,29.1L-69.66,28.41L-69.17,27.92L-68.85,27.15L-68.59,27.14L-68.32,26.97L-68.59,26.47L-68.41,26.15L-68.59,25.42L-68.38,25.09L-68.56,24.75L-68.25,24.39L-67.36,24.03L-67.01,23L-67.19,22.82M75.32,-34.58L74.3,-34.77L73.96,-34.65L73.81,-34.42L73.81,-34.33L73.97,-34.24L73.92,-34.04L74.25,-33.99L73.98,-33.72L74.15,-33.51L73.99,-33.22L74.3,-32.99L74.31,-32.81M23.61,-51.52L23.54,-51.71L23.65,-52.04L23.18,-52.29L23.41,-52.52L23.84,-52.66L23.92,-52.77L23.86,-53.11L23.48,-53.94M34.08,-9.46L34.31,-10.19L34.34,-10.66L34.57,-10.88L34.77,-10.75L34.93,-10.86L35.11,-11.82L35.67,-12.62L36.13,-12.76L36.52,-14.26M2.39,-11.9L1.98,-11.42L1.43,-11.45L0.9,-10.99M31.95,25.96L31.42,25.75L31.21,25.84L30.8,26.41L30.79,26.76L31.06,27.11L31.47,27.3L31.96,27.31L31.99,26.82L32.11,26.84M32.11,26.84L32.06,26.02L31.95,25.96M76.77,-35.66L76.56,-35.77L76.55,-35.89L76.15,-35.83L75.91,-36.05L75.97,-36.38M27.33,-5.19L27.79,-4.64L28.19,-4.35L28.43,-4.32L28.73,-4.5L29.22,-4.39L29.47,-4.61L29.68,-4.59L30.19,-3.98L30.51,-3.84L30.59,-3.62L30.76,-3.62L30.84,-3.49M22.86,-10.92L23.65,-9.82L23.62,-9.34L23.47,-9.11L23.54,-8.82L24.15,-8.67M46.11,-38.88L46.49,-38.91M44.78,-39.68L45.48,-39.01L46.11,-38.88M46.49,-38.91L47.48,-39.5L48,-39.68L48.32,-39.4L48.1,-39.24L48.29,-39.02L48,-38.85L48.59,-38.41L48.87,-38.44M81.01,-30.16L80.85,-30.14L80.4,-29.73L80.07,-28.83L80.42,-28.61L80.59,-28.65L81.85,-27.87L81.99,-27.91L82.45,-27.67L82.68,-27.67L82.73,-27.52L83.29,-27.37L83.45,-27.47L83.83,-27.38L84.09,-27.49L84.61,-27.3L84.69,-27.04L85.24,-26.75L85.57,-26.84L85.79,-26.6L86.01,-26.65L86.7,-26.44L87.02,-26.56L87.29,-26.36L88,-26.38L88.16,-26.72L87.98,-27.13L88.11,-27.87M75.97,-36.38L75.84,-36.65L75.42,-36.74L75.35,-36.91L74.54,-37.02"/><path class="lakes" d="M17.98,-59.33L17.88,-59.27L17.3,-59.27L16.91,-59.45L16.04,-59.48L16.47,-59.52L16.57,-59.61L16.75,-59.54L16.84,-59.59L17.37,-59.5L17.39,-59.58L17.69,-59.54L17.67,-59.59L17.76,-59.62L17.81,-59.55L17.77,-59.41L17.98,-59.33ZM29.84,-61.23L29.89,-61.29L30.08,-61.24L30.19,-61.33L30.24,-61.51L30.47,-61.49L30.61,-61.54L30.59,-61.61L30.85,-61.78L31.03,-61.71L31.1,-61.62L31.36,-61.63L31.6,-61.42L31.64,-61.46L32.53,-61.12L32.94,-60.64L32.82,-60.48L32.6,-60.53L32.68,-60.39L32.59,-60.35L32.58,-60.21L32.36,-60.15L31.7,-60.24L31.6,-60.17L31.51,-59.92L31.11,-59.93L31.04,-59.95L31.15,-60.01L31.11,-60.15L30.72,-60.56L30.53,-60.63L30.5,-60.84L29.84,-61.23ZM31.47,-2.39L31.38,-2.26L31.4,-1.9L31.27,-1.69L30.97,-1.53L30.59,-1.04L30.51,-1.04L30.49,-1.23L30.39,-1.3L30.48,-1.47L31.47,-2.39ZM-83.1,-42.29L-83.11,-42.07L-82.83,-42L-82.65,-42.04L-82.51,-41.93L-82.41,-42.1L-81.87,-42.32L-81.87,-42.26L-81.73,-42.45L-81.4,-42.63L-81.04,-42.66L-80.09,-42.55L-80.45,-42.61L-80.22,-42.77L-79.75,-42.86L-79.06,-42.86L-78.92,-42.92L-79.07,-43.11L-78.89,-43.06L-78.88,-42.8L-79.21,-42.56L-80.33,-42.04L-81.23,-41.77L-81.72,-41.51L-82.12,-41.49L-82.48,-41.4L-82.64,-41.47L-83.03,-41.45L-82.7,-41.53L-82.83,-41.58L-82.96,-41.54L-83.46,-41.74L-83.18,-42.05L-83.1,-42.29ZM14.74,-13.08L14.66,-12.98L14.52,-12.98L14.35,-12.88L14.28,-12.9L14.26,-13L14.41,-13.21L14.65,-13.21L14.74,-13.08ZM35.26,14.28L35.24,14.4L34.88,14.01L34.82,14.22L34.71,14.26L34.55,14.05L34.61,13.67L34.41,13.53L34.32,13.38L34.33,12.94L34.2,12.64L34.18,12.42L34.07,12.35L34.03,12.21L34.06,12.05L34.32,11.65L34.19,10.59L34.26,10.45L34.02,10.1L33.91,9.8L34,9.5L34.32,9.73L34.52,10.03L34.66,10.71L34.61,11.08L34.77,11.34L34.94,11.46L34.93,11.87L34.7,12.2L34.69,12.42L34.79,12.64L34.77,12.96L34.87,13.7L35.06,13.74L35.26,14.28ZM34.72,0.09L34.8,0.3L34.48,0.35L34.46,0.5L34.22,0.44L34.08,0.58L34.07,0.72L34.16,0.88L33.9,1.25L33.94,1.34L33.83,1.36L33.92,1.51L33.69,1.49L33.59,1.76L33.37,1.83L33.3,1.92L33.45,1.92L33.52,2L33.3,2.02L33.23,2.1L33.58,2.17L33.75,2.11L33.81,2.16L33.77,2.24L33.43,2.46L33.42,2.53L32.94,2.42L32.88,2.66L32.96,2.85L32.76,2.98L32.76,2.87L32.86,2.76L32.81,2.52L32.64,2.44L32.55,2.51L32.28,2.28L32.1,2.39L32.15,2.52L31.99,2.55L32,2.76L31.92,2.67L31.8,2.79L31.81,2.62L31.74,2.53L31.78,2.44L31.68,2.28L31.66,1.93L31.87,1.09L31.72,0.79L31.99,0.32L31.95,0.13L32.21,-0.01L32.35,-0.01L32.41,-0.09L32.53,-0.07L32.65,-0.25L32.71,-0.18L32.67,-0.12L32.88,-0.17L32.96,-0.11L33.14,-0.25L33.19,-0.43L33.36,-0.47L33.33,-0.37L33.48,-0.31L33.44,-0.27L33.48,-0.22L33.68,-0.32L33.74,-0.21L33.97,-0.21L34,0.02L34.13,0.09L34.12,0.16L34.28,0.35L34.42,0.2L34.72,0.09ZM33.17,2.16L33.1,1.97L32.97,1.97L32.95,1.9L32.83,1.94L32.85,2.06L33.17,2.16ZM109.86,-55.54L109.75,-55.19L109.76,-55.04L109.52,-54.56L109.54,-54.12L109.21,-53.83L109.18,-53.64L109.03,-53.64L109.06,-53.83L108.94,-53.86L108.53,-53.51L108.92,-53.57L108.99,-53.45L108.93,-53.34L108.66,-53.3L108.39,-53.16L108.3,-53.11L108.33,-53.04L108.29,-52.99L107.95,-52.78L107.1,-52.54L106.94,-52.47L106.81,-52.33L106.5,-52.38L106.31,-52.32L106.19,-51.96L105.8,-51.7L104.66,-51.48L104.16,-51.54L103.71,-51.69L105.17,-51.91L105.57,-52.11L106.06,-52.51L106.54,-52.71L106.88,-52.97L106.87,-53.03L106.77,-53.02L106.85,-53.1L107.53,-53.44L107.63,-53.61L108.22,-53.98L108.79,-54.67L108.92,-54.95L109.17,-55.19L109.24,-55.57L109.58,-55.77L109.76,-55.77L109.96,-55.67L109.86,-55.54ZM107.77,-53.27L107.8,-53.39L107.74,-53.4L107.58,-53.28L107,-53.11L106.96,-53.02L107.44,-53.1L107.77,-53.27ZM-96.37,-50.73L-96.29,-50.62L-96.54,-50.73L-96.61,-50.55L-96.58,-50.47L-96.68,-50.4L-96.93,-50.46L-96.98,-50.68L-96.94,-51.06L-96.63,-51.32L-96.73,-51.37L-96.98,-51.2L-96.74,-51.55L-96.83,-51.71L-97.11,-51.64L-97.14,-51.5L-97.25,-51.44L-97.25,-51.87L-97.36,-52.04L-97.57,-51.92L-97.6,-51.99L-97.5,-52.13L-97.74,-52.14L-97.79,-51.91L-97.96,-51.93L-98.19,-52.28L-98.43,-52.38L-98.47,-52.49L-98.81,-52.72L-98.9,-52.92L-98.46,-53.04L-98.99,-53.05L-99.23,-53.19L-99.2,-53.35L-99.04,-53.56L-98.93,-53.87L-98.3,-53.83L-97.91,-53.7L-98.26,-53.91L-98.3,-54.02L-98.02,-54.41L-97.93,-54.38L-97.98,-54.32L-97.82,-54.3L-98.08,-54.2L-98.21,-54.03L-98.06,-53.93L-97.73,-54.08L-97.76,-54.01L-97.98,-53.97L-97.83,-53.64L-97.35,-53.03L-97.42,-52.96L-97.4,-52.88L-97.2,-52.67L-96.84,-51.87L-96.71,-51.81L-96.76,-51.76L-96.72,-51.7L-96.29,-51.25L-96.39,-51.09L-96.37,-50.73ZM-109.02,-62.81L-108.92,-62.79L-109.01,-62.69L-109.25,-62.6L-109.3,-62.72L-109.4,-62.74L-110.28,-62.83L-110.66,-62.83L-111.27,-62.66L-111.27,-62.62L-110.41,-62.69L-109.73,-62.65L-110.1,-62.56L-110.76,-62.55L-110.65,-62.48L-110.7,-62.4L-110.95,-62.4L-111.29,-62.28L-111.59,-62.13L-111.64,-62.06L-111.5,-62.05L-111.62,-61.95L-112.09,-61.74L-112.21,-61.62L-112.97,-61.39L-113.09,-61.48L-113.36,-61.44L-113.68,-61.3L-113.73,-61.17L-113.63,-61.11L-113.83,-61L-114.17,-61.01L-115.33,-60.84L-115.88,-60.85L-116.42,-60.95L-116.53,-61.03L-117.23,-61.07L-117.67,-61.31L-117.07,-61.15L-116.74,-61.22L-116.76,-61.33L-115.95,-61.18L-115.98,-61.24L-115.86,-61.3L-116.04,-61.38L-115.72,-61.44L-115.75,-61.51L-115.56,-61.74L-114.85,-61.77L-114.65,-61.86L-114.67,-61.93L-115.03,-62.1L-115.04,-62.17L-115.29,-62.24L-115.29,-62.48L-115.7,-62.49L-115.99,-62.68L-116,-62.77L-115.76,-62.72L-115.72,-62.66L-115.29,-62.61L-114.71,-62.38L-114.28,-62.41L-114.22,-62.31L-114.02,-62.27L-113.57,-62.02L-113.31,-62L-112.3,-62.13L-111.78,-62.37L-111.39,-62.72L-110.67,-62.93L-110.06,-62.95L-109.02,-62.81ZM-111.75,-62.08L-111.67,-62.12L-111.83,-62.11L-112.07,-61.97L-113.01,-61.81L-112.75,-61.76L-112.69,-61.61L-112.45,-61.61L-111.79,-62L-111.75,-62.08ZM-75.79,-44.48L-75.83,-44.4L-76.35,-44.11L-76.31,-44.04L-76.17,-44.08L-76.19,-44L-76.07,-44L-76.2,-43.87L-76.28,-43.87L-76.2,-43.57L-76.96,-43.26L-77.53,-43.27L-78.17,-43.39L-78.69,-43.36L-79.34,-43.2L-79.77,-43.3L-79.57,-43.58L-79.06,-43.84L-77.68,-44.04L-77.5,-43.96L-77.19,-43.95L-77.21,-43.88L-77.05,-43.88L-76.88,-43.94L-77.04,-43.95L-76.86,-44.1L-77.1,-44.05L-77.12,-44.17L-77.3,-44.1L-77.33,-44.15L-77.55,-44.12L-76.91,-44.2L-77.06,-44.11L-76.99,-44.07L-75.79,-44.48ZM-117.84,-66.42L-117.51,-66.46L-117.67,-66.34L-117.68,-66.25L-117.99,-66.11L-117.92,-66.04L-118.07,-66.04L-118.2,-65.91L-118.16,-65.83L-117.85,-65.84L-117.94,-65.72L-118.57,-65.64L-118.94,-65.78L-119.62,-65.78L-119.99,-65.59L-119.51,-65.37L-119.89,-65.32L-120.16,-65.18L-121.23,-64.83L-121.37,-64.83L-121.48,-64.93L-121.09,-65L-120.55,-65.29L-120.37,-65.51L-120.47,-65.58L-120.98,-65.55L-121.55,-65.36L-121.62,-65.09L-122.04,-64.96L-123.47,-65.15L-122.85,-65.28L-122.77,-65.41L-122.89,-65.49L-122.21,-65.75L-122.16,-65.82L-122.55,-65.99L-121.47,-65.96L-121.29,-66L-121.28,-66.09L-122.11,-66.23L-123.02,-66.26L-122.99,-66.17L-123.12,-66.05L-123.4,-66.14L-124.5,-66.15L-124.59,-66.11L-124.59,-66.02L-124.73,-66.04L-124.82,-65.94L-125.09,-66.16L-125.06,-66.25L-121.98,-66.64L-121.23,-66.83L-119.88,-67.03L-119.1,-66.91L-119.57,-66.75L-120.08,-66.65L-120.33,-66.54L-120.33,-66.47L-120.45,-66.4L-119.72,-66.31L-118.76,-66.33L-118.34,-66.4L-118,-66.6L-117.73,-66.66L-117.69,-66.6L-117.86,-66.46L-117.84,-66.42ZM-83.08,-42.28L-82.9,-42.39L-82.73,-42.69L-82.65,-42.69L-82.61,-42.52L-82.42,-42.47L-82.43,-42.37L-82.52,-42.32L-82.97,-42.33L-83.08,-42.28ZM14.04,-59.08L14.09,-59.08L13.99,-58.99L13.98,-58.87L13.8,-58.72L13.36,-58.62L13.24,-58.51L13.04,-58.6L12.62,-58.38L12.55,-58.38L12.57,-58.43L12.31,-58.4L12.61,-58.62L12.43,-58.8L12.47,-58.93L12.58,-58.83L12.71,-59.04L12.82,-59.08L13.24,-58.91L13.1,-59.25L13.15,-59.35L13.25,-59.31L13.28,-59.36L13.68,-59.39L13.75,-59.33L14.03,-59.32L14.05,-59.24L13.93,-59.09L14.04,-59.08ZM-80.63,-26.89L-80.78,-26.69L-81.08,-26.96L-80.76,-27.18L-80.65,-27.05L-80.63,-26.89ZM-84.81,-11.26L-84.77,-11.12L-84.9,-11.04L-85.41,-11.17L-85.68,-11.32L-85.9,-11.7L-85.87,-12.1L-85.68,-12.06L-85.26,-11.78L-84.81,-11.26ZM37.29,-11.79L37.06,-11.83L37,-11.91L37.03,-12.16L37.1,-12.27L37.27,-12.22L37.46,-12.3L37.56,-12.22L37.58,-12.02L37.39,-11.63L37.3,-11.67L37.29,-11.79ZM-69.37,16.22L-69.48,16.18L-69.45,16.03L-69.83,15.82L-69.85,15.92L-70.01,15.83L-69.96,15.65L-69.8,15.69L-69.94,15.4L-69.83,15.31L-69.69,15.26L-69.54,15.37L-69.04,15.8L-69.01,15.91L-68.8,15.97L-68.89,16.08L-68.83,16.19L-68.59,16.24L-68.59,16.3L-68.93,16.45L-68.86,16.52L-68.9,16.59L-69.1,16.48L-69.04,16.28L-68.89,16.21L-69.08,16.08L-69.14,16.23L-69.37,16.22ZM-99.35,-53.2L-99.46,-53.05L-99.64,-53.19L-99.97,-53.1L-100.89,-53.47L-100.6,-53.5L-100.63,-53.57L-100.32,-53.59L-100.43,-53.79L-100.35,-53.9L-100.51,-53.92L-100.3,-53.97L-100.35,-54.21L-100.12,-54.25L-99.87,-54.19L-100.23,-54.01L-100.11,-53.97L-100.14,-53.85L-99.6,-54.01L-99.78,-53.84L-99.91,-53.83L-99.93,-53.76L-100.22,-53.63L-99.98,-53.49L-99.89,-53.25L-99.44,-53.34L-99.35,-53.2ZM36.42,-61.39L36.36,-61.16L35.88,-60.95L35.91,-60.9L35.86,-60.87L35.55,-60.94L35.4,-61.04L35.13,-61.01L34.94,-61.07L34.85,-61.03L34.8,-61.12L34.89,-61.21L35.16,-61.19L35.23,-61.17L35.05,-61.14L35.11,-61.09L35.53,-61.02L35.63,-61.11L35.61,-61.2L35.4,-61.39L34.63,-61.65L34.39,-61.8L34.31,-61.87L34.53,-61.81L34.59,-61.94L34.26,-62.17L34.26,-62.26L34.16,-62.34L33.98,-62.41L33.94,-62.5L34.05,-62.49L34.34,-62.2L34.64,-62.1L34.61,-62.34L34.7,-62.36L34.56,-62.54L34.84,-62.31L34.89,-62.19L35.11,-62.05L35.17,-62.1L35.05,-62.23L35.39,-62.16L35.55,-62.24L35.54,-62.35L35.35,-62.52L34.94,-62.64L34.84,-62.59L34.74,-62.62L34.49,-62.9L35.74,-62.52L35.82,-62.35L35.69,-62.04L36.11,-61.61L36.42,-61.39ZM-111.97,-41L-111.96,-40.94L-112.37,-40.7L-112.48,-40.94L-112.58,-40.85L-112.73,-41.02L-112.96,-41.38L-113.01,-41.6L-112.74,-41.66L-112.74,-41.54L-112.53,-41.42L-112.44,-41.22L-112.37,-41.25L-112.37,-41.46L-112.06,-41.4L-112.08,-41.35L-112.24,-41.35L-112.3,-41.28L-111.97,-41ZM-84.76,-45.79L-84.98,-45.77L-85.09,-45.61L-85.09,-45.51L-84.93,-45.41L-85.38,-45.28L-85.39,-45.03L-85.55,-44.77L-85.49,-44.99L-85.59,-44.82L-85.65,-44.84L-85.57,-45.21L-85.86,-44.96L-86.06,-44.92L-86.13,-44.75L-86.26,-44.7L-86.3,-44.33L-86.52,-44.05L-86.44,-43.81L-86.54,-43.64L-86.22,-42.9L-86.26,-42.53L-86.41,-42.22L-86.63,-41.91L-86.8,-41.79L-87.16,-41.65L-87.36,-41.64L-87.51,-41.72L-87.8,-42.21L-87.78,-42.75L-87.89,-43.01L-87.9,-43.24L-87.7,-43.72L-87.7,-43.98L-87.53,-44.17L-87.53,-44.39L-87.34,-44.78L-87.42,-44.87L-87.6,-44.85L-87.97,-44.55L-88.03,-44.62L-87.95,-44.76L-87.83,-44.94L-87.63,-45.03L-87.59,-45.18L-87.11,-45.69L-86.98,-45.92L-86.94,-45.7L-86.75,-45.86L-86.56,-45.88L-86.56,-45.81L-86.69,-45.7L-86.62,-45.62L-86.27,-45.94L-85.91,-45.94L-85.39,-46.11L-84.97,-45.99L-84.76,-45.86L-84.76,-45.79ZM-87.05,-45.3L-87.4,-44.95L-87.35,-44.84L-87.28,-44.83L-87.06,-45.1L-87.08,-45.15L-86.99,-45.28L-87.05,-45.3ZM-84.43,-46.52L-84.36,-46.5L-84.53,-46.44L-85.03,-46.51L-84.97,-46.77L-85.01,-46.78L-85.62,-46.69L-86.13,-46.69L-86.64,-46.45L-87.03,-46.54L-87.36,-46.52L-87.64,-46.83L-87.78,-46.89L-88.22,-46.95L-88.45,-46.8L-88.47,-47.01L-88.65,-47.23L-89.35,-46.88L-89.7,-46.84L-90.47,-46.58L-90.74,-46.69L-90.94,-46.62L-90.77,-46.91L-90.84,-46.96L-91.84,-46.7L-92.11,-46.76L-90.85,-47.59L-89.83,-47.9L-89.35,-48.12L-89.2,-48.45L-88.77,-48.58L-88.93,-48.34L-88.73,-48.38L-88.5,-48.83L-88.4,-48.84L-88.32,-48.74L-88.57,-48.53L-88.56,-48.45L-88.44,-48.56L-88.23,-48.6L-88.11,-48.78L-88.26,-48.97L-88.07,-49L-87.22,-48.78L-86.69,-48.81L-86.43,-48.76L-86.28,-48.6L-86.1,-48.21L-85.91,-48.03L-85.61,-47.94L-84.85,-47.95L-85.01,-47.64L-84.59,-47.32L-84.78,-47L-84.62,-46.92L-84.39,-46.91L-84.38,-46.85L-84.55,-46.81L-84.54,-46.7L-84.44,-46.72L-84.57,-46.54L-84.5,-46.48L-84.43,-46.52ZM-88.06,-48.84L-88.06,-48.72L-87.82,-48.77L-87.77,-48.84L-88.06,-48.84ZM-88.91,-47.94L-88.62,-48.04L-88.48,-48.17L-89.19,-47.93L-89.16,-47.84L-88.91,-47.94ZM-87.79,-47.41L-87.74,-47.43L-87.88,-47.48L-88.32,-47.42L-88.56,-47.27L-88.62,-47.17L-88.43,-47.12L-88.42,-47.19L-88.47,-47.05L-88.4,-47.02L-87.97,-47.35L-88.02,-47.39L-87.79,-47.41ZM-85.61,-47.74L-85.77,-47.81L-85.95,-47.75L-85.61,-47.74ZM-84.34,-46.53L-84.17,-46.56L-84.09,-46.51L-84.09,-46.36L-83.46,-46.24L-82.35,-46.19L-81.77,-46.1L-81.77,-46.06L-81.62,-46.12L-81.54,-46.07L-81.64,-46.04L-81.6,-45.97L-81.17,-46.02L-81.1,-45.94L-80.82,-45.95L-80.51,-45.59L-80.41,-45.62L-80.35,-45.4L-80.18,-45.34L-80.18,-45.4L-80.06,-45.37L-80.12,-45.22L-80.01,-45.15L-80.09,-45.11L-79.83,-44.94L-79.77,-44.82L-79.7,-44.88L-79.68,-44.77L-79.83,-44.77L-79.93,-44.86L-80.11,-44.81L-80,-44.65L-80.08,-44.49L-80.46,-44.58L-80.67,-44.73L-80.91,-44.62L-80.9,-44.78L-81.13,-44.77L-80.97,-44.97L-81.13,-44.92L-81.26,-45.03L-81.29,-45.24L-81.7,-45.25L-81.36,-44.98L-81.28,-44.64L-81.71,-44.13L-81.71,-43.47L-81.78,-43.33L-82.18,-43.09L-82.42,-43.02L-82.66,-43.85L-82.88,-44.05L-82.99,-44.06L-83.38,-43.92L-83.35,-43.88L-83.47,-43.73L-83.67,-43.62L-83.94,-43.74L-83.88,-43.96L-83.61,-44.06L-83.51,-44.27L-83.33,-44.38L-83.3,-44.79L-83.45,-44.99L-83.43,-45.06L-83.28,-45.05L-83.48,-45.34L-84.76,-45.79L-84.72,-45.96L-84.63,-46.05L-84.52,-45.99L-83.9,-45.98L-84.05,-46.16L-84.25,-46.2L-84.2,-46.28L-84.34,-46.53ZM-83.53,-46.02L-83.68,-46.11L-83.71,-46.04L-83.88,-45.99L-83.59,-45.94L-83.49,-45.99L-83.53,-46.02ZM-83.83,-46.15L-83.82,-46.25L-84.1,-46.29L-83.98,-46.11L-83.83,-46.15ZM-82.96,-45.83L-82.32,-45.68L-82.06,-45.56L-81.76,-45.7L-81.98,-45.57L-81.88,-45.54L-81.75,-45.59L-81.59,-45.79L-81.69,-45.8L-81.7,-45.89L-81.8,-45.74L-81.94,-45.98L-82.14,-45.87L-82.33,-45.98L-82.53,-45.94L-82.58,-45.9L-82.53,-45.81L-82.76,-45.86L-82.85,-45.99L-83.18,-45.97L-83.22,-45.9L-82.96,-45.83ZM-97.43,-25.35L-97.69,-24.48L-97.76,-23.91L-97.74,-24.39L-97.83,-24.52L-97.73,-24.5L-97.7,-24.84L-97.64,-24.91L-97.73,-24.99L-97.7,-25.2L-97.75,-25.26L-97.65,-25.36L-97.54,-25.31L-97.51,-25.45L-97.43,-25.35ZM-102.84,-58.33L-102.98,-58.27L-102.94,-58.17L-103.26,-58.05L-103.28,-57.9L-103.21,-57.83L-103.33,-57.7L-103.36,-57.86L-103.56,-57.87L-103.83,-57.78L-103.66,-57.92L-103.8,-57.95L-103.67,-58.04L-103.71,-58.13L-103.61,-58.27L-103.66,-58.28L-103.55,-58.46L-103.38,-58.43L-103.24,-58.47L-103.18,-58.55L-102.95,-58.53L-102.8,-58.41L-102.84,-58.33ZM-109.23,-59.13L-110.07,-58.95L-110.4,-58.77L-110.44,-58.72L-110.38,-58.64L-110.75,-58.61L-110.84,-58.51L-110.9,-58.63L-111.07,-58.5L-111.1,-58.62L-111.3,-58.73L-111.28,-58.79L-111.02,-58.76L-110.48,-59.11L-109.88,-59.36L-109.62,-59.54L-109.4,-59.6L-109.17,-59.59L-109.04,-59.5L-108.8,-59.5L-108.86,-59.39L-108.22,-59.47L-106.02,-59.27L-107.59,-59.29L-107.71,-59.34L-107.84,-59.22L-108.21,-59.16L-109.23,-59.13ZM-72.9,-51.15L-73.46,-50.79L-73.13,-51.09L-73.17,-51.16L-73.63,-50.82L-73.8,-50.6L-73.82,-50.21L-74.08,-50.04L-74.22,-50.06L-73.83,-50.25L-73.9,-50.35L-73.84,-50.64L-73.93,-50.46L-74.13,-50.4L-73.85,-50.89L-73.91,-50.9L-73.89,-50.98L-73.07,-51.39L-72.99,-51.4L-73.04,-51.31L-72.79,-51.35L-73.07,-51.16L-72.69,-51.24L-72.9,-51.15ZM5.87,-52.56L5.87,-52.49L5.5,-52.25L5.04,-52.34L5.07,-52.62L5.24,-52.67L5.25,-52.73L5.07,-52.92L5.38,-53.06L5.42,-52.87L5.66,-52.85L5.62,-52.66L5.87,-52.56ZM5.8,-52.47L5.8,-52.56L5.66,-52.59L5.17,-52.38L5.5,-52.3L5.8,-52.47ZM38.68,-58.11L38.38,-58.12L38.44,-58.02L38.28,-58.05L38.22,-58.24L37.9,-58.29L37.42,-58.61L37.16,-58.69L37.15,-58.85L37.42,-58.73L37.41,-58.67L37.56,-58.55L37.66,-58.56L37.63,-58.64L38.07,-58.54L38.1,-58.63L37.95,-58.72L38.02,-58.75L38,-58.86L37.71,-58.93L37.5,-58.84L37.48,-58.93L37.67,-59.03L37.64,-59.16L37.99,-59.18L38.16,-59.1L38.14,-59.21L38.41,-59.17L38.24,-59.06L37.86,-59.08L38.75,-58.55L38.99,-58.5L39.01,-58.36L38.83,-58.3L38.81,-58.12L38.62,-58.2L38.68,-58.11ZM78.3,-42.59L77.87,-42.43L77.72,-42.24L77.51,-42.18L76.92,-42.19L76.26,-42.33L76.22,-42.44L76.97,-42.61L77.68,-42.7L78.25,-42.73L78.12,-42.64L78.3,-42.59ZM-94.05,-49.37L-94.05,-49.27L-94.12,-49.21L-94.11,-49.26L-94.28,-49.41L-94.25,-49.47L-94.65,-49.44L-94.78,-49.34L-94.64,-49.35L-94.46,-49.23L-94.35,-49.27L-94.07,-49.16L-94.31,-49.1L-94.71,-48.86L-95,-48.96L-95.18,-48.9L-95.31,-48.93L-95.26,-49.14L-94.98,-49.2L-94.94,-49.32L-95.01,-49.37L-94.65,-49.6L-94.74,-49.62L-95.11,-49.46L-95.15,-49.62L-95.01,-49.64L-94.93,-49.58L-94.82,-49.69L-94.59,-49.72L-94.58,-49.81L-94.68,-49.95L-94.61,-49.99L-94.45,-49.74L-94.31,-49.69L-94.37,-49.56L-94.17,-49.5L-94.05,-49.37ZM-94.7,-49.19L-94.79,-49.19L-94.73,-49.09L-94.59,-49.04L-94.53,-49.04L-94.45,-49.18L-94.7,-49.19ZM-88.03,-49.96L-88.14,-49.91L-88.11,-49.71L-88.18,-49.47L-88.41,-49.39L-88.54,-49.55L-88.62,-49.43L-88.77,-49.46L-88.61,-49.65L-88.96,-49.5L-89.02,-49.57L-88.91,-49.58L-88.93,-49.75L-89.01,-49.71L-89.09,-49.78L-89.07,-49.82L-88.95,-49.81L-88.89,-50.06L-88.64,-50.28L-88.31,-50.15L-88.42,-50.29L-88.34,-50.27L-88.17,-50.13L-88.23,-49.99L-88.13,-50.04L-88.03,-49.96ZM-101.72,-57.91L-101.54,-57.92L-101.54,-57.82L-102.11,-57.43L-102.09,-57.37L-101.84,-57.27L-102.03,-57.19L-102.05,-57.11L-101.96,-57.02L-102.18,-56.86L-102.31,-56.84L-102.47,-56.61L-102.89,-56.47L-102.98,-56.37L-103.14,-56.41L-103.27,-56.28L-103.29,-56.54L-103.19,-56.56L-103.11,-56.85L-103.05,-56.57L-102.98,-56.56L-102.57,-56.83L-102.58,-57.05L-102.74,-57.1L-102.69,-57.21L-102.92,-57.3L-102.93,-57.36L-102.69,-57.56L-102.69,-57.69L-102.21,-57.93L-102.05,-58.11L-101.99,-58.09L-101.97,-57.96L-101.82,-58.06L-101.82,-57.84L-101.72,-57.91ZM-75.75,-43.23L-75.96,-43.18L-76.1,-43.25L-75.75,-43.23ZM-153.97,-59.77L-154.53,-59.63L-154.61,-59.45L-155.74,-59.33L-155.88,-59.38L-155.91,-59.46L-155.85,-59.54L-154.99,-59.71L-154.33,-59.79L-153.97,-59.77ZM-155.96,-57.87L-156.02,-57.84L-156.04,-57.71L-156.16,-57.63L-156.11,-57.75L-156.16,-57.8L-156.68,-57.89L-156.88,-58L-156.82,-58.07L-156.64,-58.09L-155.96,-57.87ZM-119.94,-39.03L-120.03,-38.95L-120.14,-39.09L-120.06,-39.22L-119.96,-39.25L-119.94,-39.03ZM84.52,-47.93L84.36,-47.73L84.24,-47.71L83.62,-48.01L83.03,-48.21L83.5,-48.3L83.53,-48.38L83.39,-48.55L83.47,-48.86L83.75,-49.04L84.12,-49.16L84.1,-49.24L83.85,-49.42L83.66,-49.44L83.36,-49.64L83.61,-49.61L83.96,-49.73L83.73,-49.54L84.36,-49.16L83.61,-48.91L83.51,-48.81L83.49,-48.72L83.61,-48.44L83.92,-48.4L83.68,-48.35L83.58,-48.27L84.52,-47.93ZM-88.33,-44.07L-88.33,-43.94L-88.46,-43.81L-88.48,-44.11L-88.36,-44.2L-88.33,-44.07ZM-71.44,-66.6L-71.21,-66.86L-71.23,-67L-71,-67.02L-70.83,-66.99L-70.46,-66.75L-69.49,-66.58L-69.47,-66.55L-69.65,-66.44L-69.25,-66.45L-69.22,-66.41L-69.59,-66.2L-69.98,-66.26L-70.38,-66.19L-70.62,-66.28L-71.23,-65.95L-71.32,-65.99L-71.18,-66.08L-71.13,-66.33L-71.44,-66.6ZM36.68,-2.54L36.63,-2.42L36.53,-2.45L36.42,-2.73L36.15,-3.04L35.87,-3.6L35.95,-4.55L36.04,-4.54L36.13,-4.65L36.2,-4.43L36.22,-3.47L36.43,-3.01L36.65,-2.86L36.68,-2.54ZM-101.93,-63.22L-101.55,-63.46L-101.32,-63.39L-101.33,-63.47L-101.28,-63.49L-101.14,-63.43L-100.71,-63.55L-100.64,-63.47L-100.77,-63.32L-101.04,-63.29L-101.1,-63.1L-100.88,-63.01L-100.88,-62.96L-101.06,-62.86L-101.03,-62.76L-101.29,-62.67L-101.38,-62.68L-101.32,-62.83L-101.38,-62.93L-101.53,-62.66L-101.59,-62.78L-102.03,-62.92L-102.16,-63.16L-101.93,-63.22ZM-94.63,-64.16L-94.25,-64.12L-94.22,-64.08L-94.31,-64.01L-94.45,-64L-94.86,-64.07L-95.78,-64.06L-96.23,-64.19L-96.27,-64.3L-95.25,-64.27L-94.63,-64.16ZM19.76,-54.43L19.72,-54.48L19.99,-54.71L20.4,-54.68L19.76,-54.43ZM19.72,-54.48L19.74,-54.41L19.48,-54.3L19.25,-54.31L19.72,-54.48ZM-73.37,-44.15L-73.37,-43.76L-73.45,-44.08L-73.44,-44.19L-73.35,-44.28L-73.44,-44.64L-73.38,-44.94L-73.32,-45.03L-73.29,-44.91L-73.1,-45.08L-73.19,-44.96L-73.21,-44.59L-73.26,-44.54L-73.23,-44.44L-73.37,-44.15ZM-115.61,-33.27L-115.7,-33.14L-115.79,-33.15L-116.06,-33.43L-116.05,-33.5L-115.95,-33.52L-115.61,-33.27ZM-117.32,-63.21L-117.36,-63.15L-117.74,-63.11L-118.63,-63.38L-118.1,-63.57L-117.58,-63.37L-117.32,-63.21ZM-72.97,41.29L-72.97,41.09L-72.85,40.97L-72.7,41.03L-72.6,41.18L-72.97,41.29ZM118.6,-33.17L118.49,-33L118.18,-32.88L118.18,-32.97L118.05,-32.96L118.13,-33.03L118.24,-33.01L118.18,-33.14L117.98,-33.14L117.81,-33.05L117.91,-33.18L118.11,-33.21L118.34,-32.99L118.41,-33.01L118.45,-33.16L118.25,-33.22L118.23,-33.29L118.32,-33.27L118.45,-33.41L118.61,-33.38L118.49,-33.54L118.54,-33.64L118.66,-33.46L118.86,-33.36L118.72,-33.09L118.6,-33.17ZM100.79,-51.4L100.69,-50.98L100.51,-50.81L100.47,-50.6L100.19,-50.49L100.28,-51.25L100.4,-51.39L100.38,-51.47L100.56,-51.61L100.79,-51.4ZM92.32,-50.3L92.24,-50.41L92.89,-50.66L92.99,-50.61L92.98,-50.54L93.08,-50.43L93.36,-50.28L93.1,-50.2L92.91,-50.06L92.6,-50.01L92.38,-50.14L92.32,-50.3ZM29.13,8.66L28.7,9.4L28.52,9.4L28.51,9.48L28.38,9.5L28.32,9.36L28.37,9.1L28.87,8.51L29.13,8.66ZM132.81,-45.05L132.61,-44.71L132.37,-44.53L132.07,-44.74L132.11,-44.97L132.02,-45.07L132,-45.21L132.23,-45.33L132.58,-45.3L132.81,-45.15L132.81,-45.05ZM104.57,-12.43L104.26,-12.56L104.1,-12.79L103.81,-12.95L103.7,-13.21L103.73,-13.25L103.98,-13.18L104.23,-12.76L104.44,-12.72L104.57,-12.43ZM100.75,-36.81L100.7,-36.59L100.63,-36.56L100.43,-36.64L99.96,-36.68L99.65,-36.91L99.82,-36.96L99.79,-37.15L99.96,-37.22L100.27,-37.15L100.75,-36.81ZM71.24,-67.99L70.97,-68.01L70.93,-68.06L71.09,-68.1L71.28,-68.06L71.38,-68L71.24,-67.99ZM43.26,-33.73L43.11,-33.92L43.07,-34.26L43.12,-34.33L43.49,-33.89L43.48,-33.73L43.26,-33.73ZM43.88,-32.69L43.79,-32.54L43.48,-32.64L43.42,-32.81L43.51,-33.06L43.55,-33.08L43.72,-32.81L43.88,-32.69ZM35.59,-31.72L35.55,-31.36L35.42,-31.33L35.42,-31.62L35.52,-31.76L35.59,-31.72ZM27.5,-58.18L27.97,-58.13L28.17,-57.91L28.1,-57.86L27.91,-57.9L27.8,-57.99L27.62,-58.01L27.5,-58.18ZM-72.05,-48.45L-72.31,-48.62L-72.29,-48.73L-72,-48.72L-71.78,-48.61L-71.82,-48.48L-72.05,-48.45ZM-76.88,-42.42L-76.97,-42.88L-76.88,-42.68L-76.88,-42.42ZM-76.52,-42.5L-76.67,-42.6L-76.77,-42.78L-76.73,-42.94L-76.67,-42.67L-76.52,-42.5ZM4.69,-10.37L4.6,-10.2L4.66,-9.88L4.59,-9.87L4.47,-10.07L4.51,-10.17L4.4,-10.4L4.49,-10.64L4.68,-10.58L4.69,-10.37ZM45.67,-37.74L45.75,-37.7L45.86,-37.43L45.83,-37.34L45.66,-37.29L45.54,-37.13L45.45,-37.15L45.36,-37.23L45.23,-37.76L45.09,-37.89L45.08,-37.99L45.19,-38.11L45.02,-38.14L45.03,-38.19L45.11,-38.26L45.36,-38.26L45.49,-38.07L45.44,-37.81L45.67,-37.74ZM-106.26,-57.7L-106.11,-57.65L-106.14,-57.41L-106.54,-57.33L-106.8,-57.36L-107.09,-57.24L-107.03,-57.43L-107.07,-57.48L-106.92,-57.46L-106.26,-57.7ZM-99.61,-62.96L-99.3,-63.19L-99.3,-63.05L-99.14,-62.93L-99.39,-62.82L-99.57,-62.81L-99.76,-62.85L-99.61,-62.96ZM-102.55,-60.32L-102.32,-60.42L-102.44,-60.5L-102.43,-60.58L-102.26,-60.65L-101.89,-60.24L-101.88,-59.98L-101.98,-60.01L-102.02,-59.93L-102.27,-60.21L-102.59,-60.25L-102.55,-60.32ZM57.87,-41.77L57.68,-41.64L57.35,-41.57L57.05,-41.77L57.18,-42.19L57.27,-42.3L57.39,-42.33L57.55,-42.26L57.7,-41.91L57.87,-41.77ZM76.75,-54.83L77.13,-54.92L77.25,-54.86L77.33,-54.97L77.57,-55.05L78.03,-54.98L78.05,-54.93L77.64,-54.8L77.74,-54.66L77.6,-54.61L77.25,-54.72L76.73,-54.72L76.75,-54.83ZM82.13,-45.76L81.75,-45.87L81.43,-46.06L81.44,-46.39L81.65,-46.46L81.91,-46.35L82.03,-46.18L82.13,-45.76ZM-73.99,-56.03L-74.25,-55.94L-74.23,-55.98L-74.34,-56.02L-74.73,-56.09L-74.8,-56.14L-74.82,-56.27L-74.66,-56.34L-74.48,-56.32L-74.31,-56.26L-74.25,-56.16L-73.99,-56.1L-73.99,-56.03ZM-80.45,-46.28L-80.15,-46.26L-80.05,-46.35L-79.65,-46.36L-79.44,-46.24L-79.57,-46.17L-79.77,-46.21L-79.99,-46.16L-80.01,-46.23L-80.45,-46.28ZM117.23,-48.59L117.09,-48.58L117.1,-48.7L116.99,-48.84L117.64,-49.34L117.71,-49.32L117.72,-49.18L118.03,-49.07L117.77,-49.06L117.23,-48.59ZM29.99,11.09L29.92,11.3L29.75,11.42L29.59,11.39L29.5,11.19L29.85,10.89L30,10.94L29.99,11.09ZM28.45,-69.33L28.76,-69.42L28.55,-69.3L28.57,-69.22L28.4,-69.08L28.09,-69.01L28.34,-68.86L27.99,-68.88L27.89,-68.86L27.99,-68.79L27.87,-68.74L27.78,-68.79L27.65,-68.73L27.28,-68.71L27.42,-68.84L27.16,-68.92L27.75,-69.13L28.09,-69.16L27.99,-69.25L28.03,-69.29L28.14,-69.24L28.45,-69.33ZM26.78,-64.39L26.87,-64.53L27.21,-64.5L27.22,-64.41L27.37,-64.33L27.93,-64.38L27.93,-64.31L27.74,-64.28L27.76,-64.24L28.19,-64.13L27.93,-64.14L27.56,-64.27L27.32,-64.21L27.26,-64.12L26.94,-64.24L26.78,-64.39ZM27.57,-58.21L27.5,-58.18L27.24,-58.45L27.16,-58.65L26.97,-58.81L26.97,-58.88L27.52,-59.01L27.75,-58.91L27.82,-58.48L27.58,-58.31L27.57,-58.21ZM29.2,1.64L29.36,2.02L29.08,2.34L28.85,2.45L28.92,2.29L28.87,2.19L28.91,2.01L29.03,1.65L29.07,1.61L29.2,1.64ZM29.42,0.63L29.37,0.64L29.33,0.53L29.5,0.18L29.64,0.12L29.89,0.17L29.87,0.3L29.42,0.63ZM120.6,-31.09L120.39,-30.97L120.1,-30.97L119.98,-31.09L119.94,-31.25L119.99,-31.39L120.22,-31.53L120.27,-31.44L120.38,-31.43L120.33,-31.32L120.43,-31.2L120.39,-31.1L120.6,-31.09ZM-76.55,-56.16L-76.4,-56.35L-76.37,-56.55L-76.25,-56.42L-76.28,-56.38L-75.94,-56.17L-76.15,-56.13L-76.55,-56.16ZM-62.23,30.78L-62.73,30.92L-62.98,30.69L-62.64,30.52L-62.41,30.54L-62.29,30.59L-62.23,30.78ZM33.17,-49.02L32.77,-49.12L31.89,-49.55L32.63,-49.38L32.71,-49.56L33.19,-49.12L33.17,-49.02ZM-76.09,-53.67L-76.1,-53.74L-75.93,-53.77L-75.85,-53.86L-75.29,-53.9L-75.18,-53.82L-74.8,-53.89L-74.72,-53.86L-75.27,-53.68L-74.43,-53.68L-74.94,-53.58L-75.03,-53.58L-75.03,-53.64L-75.63,-53.64L-75.63,-53.54L-75.93,-53.47L-76.12,-53.52L-75.91,-53.65L-76.09,-53.67ZM-76.1,-53.74L-76.09,-53.67L-76.84,-53.5L-77.4,-53.52L-77.49,-53.56L-77.46,-53.64L-77.69,-53.68L-77.42,-53.8L-76.9,-53.85L-76.73,-53.98L-76.87,-54.07L-76.51,-54.05L-76.47,-54.08L-76.56,-54.16L-76.37,-54.19L-76.11,-54.12L-76.26,-54.07L-76.3,-53.96L-76.75,-53.72L-76.1,-53.74ZM-156.55,-57.77L-156.83,-57.44L-157.04,-57.55L-156.89,-57.58L-156.68,-57.76L-156.55,-57.77ZM-159.67,-66.47L-159.66,-66.43L-159.95,-66.44L-160.13,-66.52L-159.67,-66.47ZM-115.06,-60.33L-115.29,-60.11L-115.9,-60.2L-115.06,-60.33ZM-76.64,-53.26L-76.84,-53.09L-76.8,-52.98L-76.9,-52.99L-76.94,-53.12L-76.84,-53.39L-76.72,-53.47L-76.66,-53.42L-76.51,-53.47L-76.52,-53.38L-76.67,-53.34L-76.59,-53.29L-76.64,-53.26ZM-71.98,50.22L-72.27,50.3L-72.79,50.29L-72.97,50.36L-72.96,50.47L-72.78,50.48L-72.95,50.62L-73.11,50.37L-73.29,50.33L-73.21,50.27L-73.03,50.29L-72.98,50.23L-73.16,50.15L-73.3,50.18L-73.29,50.07L-73.19,49.98L-72.95,50.18L-72.12,50.13L-71.98,50.22ZM90.35,-30.52L90.29,-30.85L91.01,-30.89L90.71,-30.64L90.35,-30.52ZM33.46,-38.85L33.67,-38.71L33.53,-38.52L33.24,-38.67L33.16,-38.77L33.29,-38.97L33.31,-39.13L33.42,-39.06L33.46,-38.85ZM-105.96,-60L-106.07,-59.96L-106.06,-59.84L-106.1,-59.81L-106.24,-59.86L-106.34,-59.8L-106.33,-60.02L-106.41,-60.06L-106.31,-60.1L-106.19,-60.02L-106.12,-60.14L-105.87,-60.23L-105.7,-60.18L-106.07,-60.08L-105.88,-60.04L-105.96,-60ZM27.54,-60.94L27.34,-61L27.37,-61.03L27.58,-60.98L27.72,-61.08L27.85,-60.98L27.54,-60.94ZM29.47,-62.87L29.56,-62.83L29.58,-62.89L29.52,-63.05L29.82,-62.79L29.81,-62.73L29.67,-62.68L29.47,-62.87ZM29.23,-62.71L29.22,-62.77L29.29,-62.8L29.52,-62.71L29.45,-62.64L29.22,-62.65L29.23,-62.71ZM160.48,-69.25L160.26,-69.24L159.81,-69.35L160.48,-69.25ZM71.36,-67.87L71.3,-67.91L71.55,-68L71.71,-68.04L71.79,-67.99L71.65,-67.9L71.36,-67.87ZM70.49,-70.09L70.51,-70.06L70.37,-70.01L70.13,-70.08L70.17,-70.14L70.49,-70.09ZM70.85,-69.97L70.75,-70.03L70.84,-70.14L70.94,-70.14L70.94,-70.05L71.06,-69.99L70.85,-69.97ZM70.56,-70.12L70.34,-70.2L70.82,-70.19L70.56,-70.12ZM35.01,-63.51L35.41,-63.45L35.17,-63.38L34.83,-63.43L34.96,-63.12L34.86,-62.92L34.9,-63.05L34.8,-63.33L34.52,-63.48L34.36,-63.7L34.22,-63.61L34.21,-63.68L34.35,-63.85L34.43,-63.85L34.86,-63.72L35.01,-63.51ZM33.44,-63.44L33.59,-63.49L33.7,-63.41L33.93,-63.42L34.07,-63.23L33.5,-63.22L33.27,-63.32L33.26,-63.42L33.44,-63.44ZM30.6,-62.88L30.61,-62.97L30.75,-63.05L30.83,-63.03L30.85,-62.95L30.66,-62.77L30.48,-62.79L30.6,-62.88ZM29.99,-63.29L29.99,-63.14L30.33,-62.83L30.09,-62.73L30.22,-62.87L30.14,-62.93L29.81,-63.15L29.39,-63.18L29.04,-63.47L29.09,-63.57L29.78,-63.29L29.99,-63.29ZM31.17,-66.11L31.33,-65.92L31.29,-65.91L30.65,-66.05L30.72,-66.19L30.9,-66.26L31.1,-66.25L31.17,-66.11ZM32.52,-65.53L32.66,-65.48L32.71,-65.42L32.67,-65.39L32,-65.57L31.51,-65.8L32.05,-65.88L32.33,-65.7L32.43,-65.54L32.52,-65.53ZM-72.84,-81.68L-68.97,-81.94L-72.84,-81.68ZM-89.52,-52.88L-89.28,-53.01L-88.95,-52.99L-89.04,-52.87L-89.52,-52.88ZM87.38,-41.85L87.1,-41.9L86.73,-41.85L86.89,-42.11L87.32,-42.02L87.38,-41.85ZM31.53,-58.23L31.39,-58.14L30.86,-58.24L31.17,-58.36L31.3,-58.48L31.52,-58.37L31.64,-58.39L31.69,-58.2L31.53,-58.23ZM116.71,-29.14L116.5,-29.12L116.51,-28.8L116.1,-29.11L115.97,-29.31L116.09,-29.56L116.08,-29.7L116.2,-29.75L116.23,-29.7L116.11,-29.43L116.2,-29.36L116.15,-29.25L116.37,-29.22L116.36,-29.15L116.47,-29.25L116.64,-29.24L116.71,-29.14ZM89.32,-31.79L89.14,-31.6L89.06,-31.6L88.95,-31.62L88.93,-31.73L88.68,-31.73L88.57,-31.84L88.79,-31.83L88.97,-31.92L89.12,-31.91L89.27,-31.87L89.32,-31.79ZM92.79,-48.18L92.44,-48.03L92.2,-47.77L91.99,-47.93L91.98,-48.01L92.25,-48.13L92.29,-48.35L92.48,-48.34L92.4,-48.16L92.64,-48.19L92.64,-48.33L92.8,-48.25L92.79,-48.18ZM176.07,38.81L175.76,38.94L175.81,38.68L176.06,38.72L176.07,38.81ZM6.87,-46.43L6.85,-46.38L6.34,-46.36L6.13,-46.2L6.16,-46.3L6.34,-46.46L6.59,-46.53L6.87,-46.43ZM-6.49,-54.72L-6.27,-54.66L-6.35,-54.5L-6.56,-54.51L-6.49,-54.72ZM14.93,-58.78L14.89,-58.59L14.95,-58.51L14.69,-58.39L14.5,-58.09L14.25,-57.81L14.16,-57.8L14.12,-57.92L14.21,-58.15L14.51,-58.56L14.93,-58.85L14.93,-58.78ZM42.99,-38.35L42.86,-38.48L42.35,-38.5L42.46,-38.69L43.08,-38.81L43.16,-38.85L43.08,-38.92L43.15,-38.95L43.44,-38.99L43.61,-38.95L43.29,-38.81L43.21,-38.72L43.19,-38.6L43.32,-38.49L43.23,-38.41L43.15,-38.34L42.99,-38.35ZM-110.2,-44.34L-110.56,-44.45L-110.33,-44.57L-110.2,-44.34ZM-152.94,-70.57L-153.79,-70.49L-154.26,-70.66L-153.61,-70.74L-152.94,-70.57ZM-114.16,-47.93L-114.19,-48.07L-114.13,-48.09L-114.05,-48.02L-114,-47.78L-114.06,-47.71L-114.15,-47.71L-114.15,-47.81L-114.25,-47.84L-114.16,-47.93ZM-113.64,-35.83L-113.99,-36.16L-114.21,-36.01L-114.5,-36.11L-114.64,-36.11L-114.74,-36.01L-114.82,-36.12L-114.43,-36.24L-114.34,-36.52L-114.37,-36.21L-114.3,-36.11L-114.23,-36.05L-114.16,-36.08L-114,-36.24L-113.64,-35.83ZM-111.82,-58.56L-111.84,-58.43L-111.79,-58.33L-111.9,-58.31L-112.19,-58.41L-112.26,-58.58L-112.45,-58.62L-112.34,-58.78L-112.04,-58.82L-112.12,-58.74L-111.73,-58.69L-111.82,-58.56ZM-63.18,-54.13L-63.2,-54.07L-63.1,-54L-63.14,-53.97L-63.56,-54.01L-63.53,-53.93L-63.83,-53.86L-64.12,-53.9L-64.18,-54.01L-64.65,-54.11L-64.69,-53.96L-65.3,-53.76L-65.19,-53.67L-65.13,-53.5L-64.97,-53.46L-65.02,-53.42L-65.53,-53.49L-65.58,-53.54L-65.32,-53.6L-65.38,-53.72L-65.34,-53.88L-66.44,-54.56L-66.35,-54.42L-66.41,-54.34L-66.32,-54.15L-66.38,-54.16L-66.62,-54.52L-66.62,-54.62L-66.51,-54.65L-66.6,-55.03L-66.53,-55.1L-66.34,-54.98L-66.43,-54.81L-66.2,-54.58L-66.19,-54.48L-65.94,-54.27L-65.4,-54.01L-65.1,-54.01L-65.18,-54.07L-65.13,-54.08L-64.82,-54.08L-65.16,-54.44L-65.3,-54.46L-65.22,-54.65L-65.14,-54.64L-65.22,-54.56L-64.88,-54.15L-64.22,-54.18L-64.32,-54.27L-64.48,-54.27L-64.37,-54.62L-64.4,-54.74L-64.3,-54.66L-64.32,-54.52L-63.75,-54.1L-63.18,-54.13ZM101.02,-73.86L100.95,-73.89L101.1,-73.99L100.9,-74.26L99.51,-74.4L100.17,-74.44L100.49,-74.58L100.43,-74.72L100.1,-74.86L100.46,-75.01L100.04,-75.1L100.03,-75.15L100.54,-75.07L100.61,-75.04L100.54,-74.93L100.57,-74.82L101.06,-74.68L103.25,-74.68L104.23,-74.81L103.88,-74.93L104.15,-75.11L104.26,-75.12L105.33,-74.81L103.57,-74.59L102.04,-74.5L101.99,-74.41L102.16,-74.23L101.43,-74.36L101.31,-74.4L101.37,-74.48L100.86,-74.46L101.1,-74.39L101.16,-74.25L101.44,-74.04L101.55,-73.88L101.02,-73.86ZM-88.88,-15.71L-89.08,-15.44L-89.3,-15.38L-89.39,-15.49L-88.86,-15.76L-88.88,-15.71ZM149.32,-72.04L149.11,-71.91L149.01,-71.92L148.92,-72.03L149.02,-72.16L149.22,-72.13L149.32,-72.04ZM89.61,-37.5L89.08,-37.59L89.49,-37.63L89.64,-37.58L89.61,-37.5ZM14.08,-63.26L14.06,-63.33L14.51,-63.27L14.67,-63.14L14.43,-63.13L14.47,-62.89L14.43,-62.83L14.35,-62.93L14.43,-62.98L14.36,-63.09L14.06,-63.19L13.97,-63.26L14.08,-63.26ZM-91.35,-50.97L-91.27,-51.07L-90.98,-51.01L-90.6,-51.21L-90.43,-51.12L-90.94,-50.95L-91.32,-50.92L-91.35,-50.97ZM32.51,8.04L32.52,8.09L32.17,7.96L31.96,7.99L31.8,7.65L31.9,7.58L32.03,7.63L32.51,8.04ZM102.88,-18.53L102.65,-18.45L102.51,-18.75L102.88,-18.53ZM-74.53,-48.46L-74.69,-48.36L-74.95,-48.58L-74.96,-48.36L-75.14,-48.29L-75.02,-48.61L-75.16,-48.53L-75.17,-48.41L-75.41,-48.44L-75.28,-48.6L-75.18,-48.6L-75.06,-48.71L-74.63,-48.8L-74.52,-48.76L-74.55,-48.61L-74.41,-48.59L-74.37,-48.49L-74.1,-48.37L-74.24,-48.35L-74.53,-48.46ZM119.41,-32.79L119.17,-32.69L119.08,-32.85L119.24,-32.9L119.24,-33.01L119.31,-33.05L119.24,-33.15L119.1,-33.03L118.88,-33.08L119.1,-33.07L119.17,-33.19L119.25,-33.2L119.35,-33.08L119.41,-32.79ZM88.16,-69.5L87.73,-69.51L87.61,-69.81L87.35,-69.89L87.41,-70L87.81,-70.1L87.97,-70.06L87.66,-69.92L87.93,-69.76L88.01,-69.59L88.16,-69.5ZM27.04,-61.66L26.74,-61.69L26.88,-61.63L26.89,-61.57L26.8,-61.56L26.55,-61.76L26.28,-61.87L26.41,-61.98L26.38,-61.87L26.53,-61.94L26.8,-61.87L26.59,-62.04L26.82,-61.95L26.9,-61.75L27.04,-61.66ZM16.4,-59.31L15.82,-59.15L15.34,-59.27L16.4,-59.31ZM26.63,-63.11L26.59,-63.09L26.65,-62.96L26.54,-62.98L26.23,-63.26L26.49,-63.17L26.59,-63.23L26.42,-63.35L26.7,-63.32L26.65,-63.29L26.74,-63.23L26.63,-63.11ZM-73.18,-55.1L-72.23,-55.28L-72.36,-55.13L-72.71,-55.01L-73.56,-54.9L-73.6,-54.93L-73.41,-54.99L-73.51,-55.05L-73.18,-55.1ZM37.23,-60.16L37.4,-60.29L37.74,-60.33L37.9,-60.3L38,-60.16L37.97,-60.09L37.72,-60.08L37.23,-60.16ZM-54.89,-4.78L-54.94,-4.73L-54.87,-4.6L-55.01,-4.6L-55.12,-4.46L-55.33,-4.53L-55.13,-5L-54.81,-4.91L-54.84,-4.79L-54.89,-4.78ZM35.74,3.64L35.87,3.42L35.84,3.7L35.75,3.75L35.74,3.64ZM38.06,-6.58L38.14,-6.58L38.11,-6.45L37.84,-6.07L37.7,-6.01L37.89,-6.26L37.87,-6.49L38.06,-6.58ZM18.18,-67.48L17.25,-67.67L17.13,-67.79L18.12,-67.56L18.4,-67.46L18.43,-67.42L18.18,-67.48ZM17.59,-46.77L17.48,-46.72L17.27,-46.76L17.67,-46.85L18.08,-47.05L18.16,-47.01L17.59,-46.77ZM-163.47,-60.41L-163.58,-60.34L-163.56,-60.27L-163.77,-60.17L-163.79,-60.3L-164.05,-60.29L-163.85,-60.35L-163.94,-60.39L-163.85,-60.43L-163.47,-60.41ZM-111.74,-40.19L-111.89,-40.06L-111.88,-40.38L-111.76,-40.34L-111.68,-40.23L-111.74,-40.19ZM-94.25,-47.19L-94.39,-47.07L-94.52,-47.14L-94.58,-47.06L-94.62,-47.17L-94.3,-47.28L-94.31,-47.18L-94.25,-47.19ZM-90.29,-48.93L-90.34,-48.82L-90.44,-48.78L-90.63,-48.83L-90.69,-48.94L-90.63,-48.97L-90.48,-48.88L-90.29,-48.93ZM-75.69,-46.9L-75.75,-46.72L-76.03,-46.76L-75.95,-46.87L-75.74,-47L-75.69,-46.9ZM-121.26,-60.45L-121.41,-60.4L-121.59,-60.44L-121.32,-60.59L-121.34,-60.77L-121.11,-60.66L-121.09,-60.59L-121.26,-60.45ZM-72.31,49.76L-72.62,49.64L-73.03,49.67L-72.97,49.59L-73.02,49.51L-72.88,49.44L-72.21,49.63L-72.11,49.76L-72.31,49.76ZM18.04,0.96L17.81,0.67L18.04,0.66L18.11,0.71L18.13,0.98L18.04,0.96ZM30.77,-63.83L30.8,-63.92L31.2,-63.79L31.08,-63.78L31.13,-63.61L30.77,-63.83ZM117.58,-47.69L117.53,-47.74L117.57,-47.84L117.8,-47.95L117.86,-47.83L117.58,-47.69ZM83.23,-31.46L82.84,-31.56L83.1,-31.65L83.34,-31.46L83.23,-31.46ZM86.78,-31.17L86.63,-31.08L86.49,-30.81L86.42,-30.81L86.4,-30.87L86.65,-31.37L86.74,-31.34L86.78,-31.17ZM79.77,-52.97L79.73,-52.84L79.6,-52.84L79.45,-52.9L79.39,-53.01L79.59,-53.14L79.74,-53.09L79.81,-53L79.77,-52.97ZM73.39,-53.07L73.09,-53.27L72.92,-53.28L73.03,-53.38L73.4,-53.36L73.39,-53.07ZM80.33,-55.54L80.1,-55.41L79.82,-55.42L80.09,-55.55L80.33,-55.54ZM28.87,-66.31L29.09,-66.3L28.63,-66.06L28.07,-66.03L28.02,-66.12L27.89,-66.17L28.09,-66.14L28.18,-66.07L28.83,-66.23L28.73,-66.33L28.87,-66.31ZM34.19,-67.87L34.33,-67.86L34.58,-67.59L34.32,-67.54L34.32,-67.7L34.19,-67.87ZM32.32,-66.5L32.4,-66.45L32.35,-66.43L31.99,-66.47L32.13,-66.54L31.96,-66.7L31.55,-66.78L31.76,-66.84L31.68,-66.88L31.75,-66.91L32.22,-66.84L32.18,-66.76L32.34,-66.67L32.22,-66.6L32.32,-66.5ZM170.66,43.66L170.51,44L170.52,43.53L170.56,43.71L170.66,43.66ZM142.19,-72.56L141.69,-72.46L141.59,-72.57L141.96,-72.61L142.19,-72.56ZM90.93,-28.92L90.81,-28.94L90.53,-28.79L90.45,-28.88L90.59,-28.9L90.67,-29.01L90.65,-29.13L90.53,-29.16L90.39,-29.11L90.56,-29.21L90.63,-29.19L90.79,-28.99L90.99,-28.98L90.99,-28.89L90.93,-28.92ZM72,-56.2L71.95,-56.11L71.72,-56.06L71.62,-56.18L72,-56.2ZM67.68,-55.8L67.5,-55.71L67.3,-55.75L67.35,-55.87L67.68,-55.8ZM32.91,-65.97L33.09,-65.91L33.07,-65.83L32.74,-65.77L32.7,-65.83L32.85,-65.89L32.75,-65.97L32.84,-66.04L32.9,-66.04L32.86,-66L32.91,-65.97ZM158.93,-70.09L158.79,-69.99L158.55,-70.1L158.71,-70.14L158.93,-70.09ZM160.03,-69.46L160.1,-69.54L160.45,-69.43L160.21,-69.41L160.25,-69.35L160.06,-69.39L160.03,-69.46ZM117.94,-31.52L117.78,-31.58L117.56,-31.45L117.47,-31.47L117.3,-31.65L117.37,-31.71L117.54,-31.59L117.73,-31.66L117.94,-31.52ZM12.9,-63.65L13.01,-63.71L13.27,-63.71L13.11,-63.67L13.1,-63.61L13.21,-63.49L13.36,-63.45L13.11,-63.5L12.9,-63.65ZM-120.32,-41.99L-120.44,-41.79L-120.48,-42.06L-120.37,-42.09L-120.32,-41.99ZM-119.43,-39.9L-119.49,-39.88L-119.64,-40.03L-119.7,-40.12L-119.64,-40.19L-119.53,-40.18L-119.43,-39.9ZM44.99,-40.51L45.01,-40.61L45.37,-40.48L45.6,-40.32L45.65,-40.19L45.28,-40.16L45.18,-40.39L44.99,-40.51ZM-119.87,-68.56L-119.83,-68.66L-119.67,-68.75L-119.47,-68.61L-119.59,-68.57L-119.65,-68.47L-119.53,-68.33L-119.85,-68.25L-119.87,-68.56ZM-70.08,-49.44L-70.16,-49.59L-70.28,-49.64L-70.35,-49.5L-70.47,-49.53L-70.52,-49.41L-70.57,-49.47L-70.74,-49.44L-70.82,-49.54L-70.96,-49.41L-70.83,-49.63L-70.72,-49.52L-70.44,-49.68L-70.34,-49.67L-70.31,-49.75L-70.38,-49.89L-70.24,-49.7L-70.1,-49.69L-69.84,-49.47L-69.78,-49.34L-69.86,-49.34L-69.95,-49.52L-70.08,-49.44ZM-57.03,-49.26L-56.96,-49.34L-56.97,-49.23L-57.13,-49.17L-57.76,-48.67L-58.01,-48.66L-57.37,-49.01L-57.26,-49.18L-57.03,-49.26ZM-126.36,-67.27L-126.49,-67.26L-126.61,-67.52L-126.76,-67.56L-126.49,-67.55L-126.21,-67.42L-126.21,-67.3L-126.36,-67.27ZM-125.75,-67.31L-125.83,-67.12L-125.92,-67.08L-126.22,-67.09L-126.18,-67.14L-126.24,-67.22L-125.75,-67.31ZM-118.67,-65L-118.83,-65.22L-118.44,-65.29L-118.26,-65.2L-118.24,-64.99L-118.32,-64.87L-118.16,-64.85L-118.15,-64.79L-118.49,-64.84L-118.67,-65ZM-90.36,-53.77L-90.29,-53.87L-90,-53.89L-89.61,-53.77L-89.94,-53.68L-90.36,-53.77ZM-93.16,-51.07L-93.32,-51.07L-93.48,-51.24L-93.37,-51.3L-93.17,-51.29L-93.07,-51.17L-93.16,-51.07ZM-94.24,-53.73L-94.68,-53.73L-94.93,-53.83L-94.93,-53.93L-94.63,-53.99L-94.69,-53.9L-94.59,-53.86L-94.05,-53.88L-94.01,-53.8L-94.24,-53.73ZM-70.51,-53L-70.4,-52.97L-70.48,-52.87L-70.43,-52.61L-70.52,-52.68L-70.54,-52.8L-70.64,-52.74L-70.76,-52.79L-70.82,-52.91L-70.98,-52.84L-70.92,-52.94L-70.75,-52.96L-70.82,-53.06L-70.51,-53ZM-104.4,-55.16L-104.64,-55.15L-104.82,-54.99L-105.13,-54.92L-105.24,-54.96L-105.26,-55.07L-105.24,-55.22L-105.08,-55.3L-104.59,-55.3L-104.4,-55.25L-104.4,-55.16ZM-79.45,-44.31L-79.5,-44.23L-79.58,-44.41L-79.45,-44.51L-79.37,-44.7L-79.16,-44.45L-79.2,-44.38L-79.45,-44.31ZM-93.92,-54.83L-93.65,-54.78L-94.41,-54.59L-94.76,-54.41L-94.74,-54.5L-94.51,-54.67L-94.48,-54.8L-93.92,-54.83ZM91.32,-35.6L91.27,-35.53L90.95,-35.63L91.22,-35.65L91.32,-35.6ZM47.61,-30.69L46.82,-30.73L46.71,-30.87L46.86,-30.92L47.29,-30.77L47.5,-30.81L47.61,-30.69ZM-118.68,-43.29L-118.82,-43.24L-118.95,-43.39L-118.66,-43.41L-118.61,-43.3L-118.68,-43.29ZM-95.6,-55.61L-95.77,-55.44L-95.92,-55.42L-95.8,-55.57L-95.6,-55.61ZM-165.38,-65.21L-165.71,-65.08L-165.9,-65.17L-165.38,-65.21ZM-163.8,-61.14L-163.84,-61.06L-163.94,-61.15L-163.89,-61.2L-163.55,-61.23L-163.8,-61.14ZM-158.22,-59.94L-159.02,-59.9L-159.13,-59.95L-158.54,-60.02L-158.22,-59.94ZM-159.16,-60.2L-158.85,-60.28L-158.77,-60.22L-159.16,-60.2ZM-158.71,-59.56L-158.83,-59.52L-158.58,-59.42L-158.81,-59.44L-159.05,-59.55L-159.13,-59.65L-158.94,-59.59L-158.65,-59.6L-158.71,-59.56ZM93.8,-49.13L93.4,-48.99L92.83,-49.28L93.26,-49.29L93.47,-49.2L93.65,-49.21L93.8,-49.13ZM85.89,-30.93L85.78,-30.76L85.69,-30.87L85.51,-30.85L85.35,-30.94L85.48,-31.05L85.81,-31L85.89,-30.93ZM-92.92,-48.43L-93.06,-48.51L-92.79,-48.45L-92.7,-48.52L-93.34,-48.6L-93.4,-48.68L-93.36,-48.75L-93.61,-48.83L-93.43,-48.85L-93.46,-48.9L-93.32,-48.93L-93.2,-48.79L-93.26,-48.67L-93.12,-48.73L-93.12,-48.67L-92.79,-48.7L-92.87,-48.62L-92.65,-48.6L-92.44,-48.36L-92.6,-48.42L-92.92,-48.43ZM-122.5,-56.08L-122.92,-56.06L-123.14,-55.97L-123.78,-56L-123.77,-55.89L-123.66,-55.75L-123.17,-55.39L-123.14,-55.18L-123.41,-55.53L-124.04,-55.91L-124.03,-56L-124.51,-56.11L-124.16,-56.09L-124.35,-56.21L-124.84,-56.76L-124.25,-56.26L-124.07,-56.25L-124.07,-56.15L-123.97,-56.06L-123.24,-56.03L-122.64,-56.16L-122.26,-56.08L-122.22,-56.02L-122.5,-56.08ZM-96.05,-56.14L-96.09,-56.08L-96.57,-56.09L-96.5,-56.15L-95.91,-56.3L-95.87,-56.26L-96.11,-56.2L-96.05,-56.14ZM-106.22,-47.59L-106.27,-47.55L-106.25,-47.64L-106.45,-47.88L-106.56,-47.75L-106.81,-47.72L-106.86,-47.63L-107.31,-47.68L-107.61,-47.62L-107.91,-47.39L-107.95,-47.56L-108.2,-47.6L-107.96,-47.6L-107.84,-47.53L-107.69,-47.65L-107.71,-47.69L-106.93,-47.73L-106.6,-47.86L-106.59,-47.96L-106.43,-48.03L-106.33,-47.99L-106.36,-47.93L-106.25,-47.81L-106.22,-47.59ZM-102.15,-47.57L-102.43,-47.56L-102.3,-47.66L-102.34,-47.76L-102.62,-47.82L-102.61,-47.99L-102.76,-48.08L-103.06,-48.13L-103.46,-48.02L-103.58,-48.1L-103.75,-48.02L-103.76,-48.07L-103.58,-48.15L-103.45,-48.07L-102.92,-48.17L-102.6,-48.05L-102.53,-47.82L-102.41,-47.81L-102.42,-47.94L-102.26,-47.98L-102.29,-47.91L-102.16,-47.62L-101.88,-47.56L-101.16,-47.63L-101.4,-47.51L-101.92,-47.46L-102.15,-47.57ZM-132.1,-59.61L-132.4,-59.92L-132.96,-60.2L-133.24,-60.45L-132.36,-59.99L-132.1,-59.61ZM-117.91,-49.34L-118.14,-49.52L-118.09,-49.8L-118.09,-49.52L-117.91,-49.34ZM-116.21,-48.16L-116.41,-48.11L-116.46,-47.98L-116.55,-47.97L-116.5,-48.11L-116.37,-48.21L-116.57,-48.25L-116.5,-48.3L-116.36,-48.28L-116.21,-48.16ZM-120.01,-47.85L-120.17,-47.91L-120.63,-48.28L-120.01,-47.85ZM-105.39,-59.13L-105.66,-59.05L-105.78,-58.92L-105.87,-58.94L-105.81,-59.03L-105.22,-59.3L-104.95,-59.24L-105.01,-59.17L-105.39,-59.13ZM-94.97,-48.03L-94.78,-47.97L-94.79,-47.91L-95.11,-47.89L-95.27,-47.94L-95.09,-48.07L-94.97,-48.03ZM-95.02,-48.12L-94.69,-48.2L-94.56,-48.14L-94.75,-48.07L-95.01,-48.07L-95.02,-48.12ZM-97.97,-62.55L-98.21,-62.69L-98.35,-62.62L-98.46,-62.83L-97.76,-62.86L-97.63,-62.98L-97.61,-62.66L-97.43,-62.5L-97.31,-62.49L-97.44,-62.42L-97.7,-62.51L-97.91,-62.46L-98.05,-62.53L-97.97,-62.55ZM-70.65,-64.69L-70.8,-64.77L-71,-64.79L-71.22,-64.64L-71.56,-64.61L-71.9,-64.73L-72.05,-64.91L-71.82,-64.91L-71.87,-64.84L-71.75,-64.82L-71.51,-64.91L-71.64,-64.98L-71.55,-65.08L-71.69,-65.24L-71.67,-65.31L-71.74,-65.41L-70.69,-65.02L-70.38,-64.71L-70.48,-64.66L-70.42,-64.58L-70.72,-64.62L-70.65,-64.69ZM-100.92,-29.5L-101.1,-29.46L-101.27,-29.5L-101.31,-29.62L-101.07,-29.51L-100.95,-29.61L-100.92,-29.5ZM-76.48,-47.14L-76.33,-47.1L-76.39,-47.06L-76.5,-47.09L-76.65,-47.28L-76.67,-47.2L-76.82,-47.5L-76.52,-47.69L-76.72,-47.54L-76.61,-47.57L-76.63,-47.51L-76.41,-47.45L-76.52,-47.2L-76.48,-47.14ZM-102.71,-20.19L-102.79,-20.12L-103.37,-20.26L-102.89,-20.32L-102.71,-20.19ZM-86.1,-12.31L-86.1,-12.21L-86.31,-12.18L-86.3,-12.27L-86.47,-12.27L-86.59,-12.41L-86.29,-12.47L-86.1,-12.31ZM-54.18,24.71L-54.31,24.78L-54.22,24.92L-54.36,24.89L-54.39,24.95L-54.32,25.08L-54.38,25.18L-54.2,25.24L-54.61,25.43L-54.63,25.3L-54.53,25.15L-54.75,25.06L-54.53,25.05L-54.51,24.97L-54.79,24.88L-54.47,24.85L-54.52,24.75L-54.4,24.69L-54.4,24.45L-54.31,24.37L-54.35,24.12L-54.27,24.07L-54.26,24.64L-54.18,24.71ZM-79.67,-9.14L-79.85,-9.05L-79.81,-9.11L-79.9,-9.15L-79.96,-9.02L-80.01,-9.06L-80.08,-9.02L-79.92,-9.27L-79.82,-9.32L-79.84,-9.21L-79.67,-9.14ZM28.99,16.61L28.76,16.81L28.65,16.7L28.51,16.76L28.46,16.87L28.34,16.79L28.12,16.86L28.08,17.05L27.96,17.04L27.7,17.21L27.58,17.45L27.02,17.96L27.11,17.77L27.37,17.5L27.43,17.3L27.61,17.07L27.69,17.07L27.71,16.94L27.83,16.9L27.79,16.82L27.9,16.77L28.04,16.82L28.29,16.54L28.39,16.59L28.62,16.49L28.99,16.61ZM33.49,-1.64L33.13,-1.5L33.26,-1.47L33.2,-1.4L33.32,-1.42L33.26,-1.22L32.9,-1.43L32.89,-1.31L32.79,-1.4L32.74,-1.34L32.58,-1.41L32.54,-1.5L32.8,-1.58L33,-1.55L33.41,-1.73L33.49,-1.64ZM39.27,-59.78L39.78,-59.64L39.72,-59.58L39.8,-59.53L39.73,-59.48L39.55,-59.55L39.05,-59.84L39.27,-59.78ZM9.73,-47.53L9.45,-47.51L9.25,-47.6L9.11,-47.77L9.73,-47.53ZM23.24,-61.42L22.58,-61.21L23.05,-61.43L23.26,-61.46L23.24,-61.42ZM129.03,16.14L128.89,16.42L128.8,16.45L128.73,16.79L128.53,16.51L128.68,16.22L128.64,16.16L128.8,16.08L128.79,16.17L129.03,16.14ZM97.89,-34.84L97.65,-34.79L97.55,-34.88L97.76,-35.09L97.89,-34.84ZM97.47,-34.98L97.23,-34.83L97.06,-34.98L97.23,-35.02L97.47,-34.98ZM73.29,-41.76L72.64,-41.69L72.71,-41.77L72.69,-41.9L73.29,-41.76ZM0.27,-6.67L0.15,-6.61L0.1,-6.34L0.07,-6.4L-0.01,-6.38L-0.1,-6.49L-0.67,-6.8L-0.55,-6.81L-0.47,-6.72L-0.39,-6.83L-0.34,-6.72L-0.19,-6.74L-0.14,-6.65L-0.06,-6.63L-0.02,-6.73L-0.07,-6.83L0.11,-6.9L0.04,-6.95L0.12,-6.98L0.08,-7.15L0.01,-7.21L0.1,-7.19L0.18,-7.29L0.05,-7.48L-0.06,-7.51L-0.07,-7.44L-0.24,-7.52L0.01,-7.54L-0.06,-7.64L-0.65,-7.55L-0.1,-7.76L-0.16,-7.78L-0.19,-7.96L-0.32,-8.04L-0.42,-7.97L-0.38,-8.05L-0.53,-8.06L-0.54,-8.15L-0.62,-8.08L-0.76,-8.1L-0.6,-8.17L-0.8,-8.32L-1,-8.63L-1.13,-8.63L-1.15,-8.55L-1.22,-8.66L-1.4,-8.74L-1.71,-8.63L-1.38,-8.8L-1.27,-8.73L-1.06,-8.72L-1.17,-8.94L-1.15,-9.12L-1.11,-8.9L-0.87,-8.59L-0.82,-8.6L-0.79,-8.76L-0.81,-8.69L-0.71,-8.64L-0.8,-8.52L-0.78,-8.47L-0.48,-8.21L-0.29,-8.25L-0.2,-8.21L-0.33,-8.16L-0.13,-8.01L-0.02,-7.79L0.07,-7.82L0.07,-8.08L0.17,-8.09L0.11,-8.24L0.22,-8.36L0.09,-8.4L0.09,-8.55L0.2,-8.74L0.1,-8.43L0.29,-8.33L0.21,-8.31L0.18,-8.21L0.27,-8.09L0.16,-8.06L0.11,-7.94L0.17,-7.86L0.26,-7.9L0.28,-7.58L0.23,-7.54L0.25,-7.49L0.32,-7.54L0.24,-6.9L0.27,-6.67ZM58.31,-45.06L58.42,-45.29L58.55,-45.41L58.71,-45.83L58.84,-45.83L58.85,-45.92L59.06,-45.89L59.3,-46L59.24,-45.89L59.1,-45.9L58.91,-45.79L58.87,-45.6L58.67,-45.46L58.63,-45.26L58.68,-45.13L58.55,-45.01L58.62,-44.82L58.48,-44.5L58.36,-44.42L58.24,-44.46L58.32,-44.6L58.22,-44.85L58.31,-45.06ZM60.78,-46.09L60.82,-46.2L60.72,-46.37L60.58,-46.29L60.35,-46.4L60.13,-46.36L59.99,-46.44L60,-46.57L60.29,-46.7L60.41,-46.5L60.46,-46.62L60.58,-46.56L60.75,-46.64L60.53,-46.75L60.58,-46.78L60.81,-46.75L60.78,-46.58L60.89,-46.47L61.13,-46.45L61.26,-46.5L61.2,-46.58L61.31,-46.65L61.53,-46.68L61.28,-46.45L61.22,-46.24L60.78,-46.09ZM59.73,-46.08L59.5,-46.32L59.78,-46.28L59.81,-46.12L59.73,-46.08ZM78.99,-46.75L79.08,-46.81L79.24,-46.68L79.22,-46.61L79.09,-46.58L79.02,-46.45L78.89,-46.37L78.47,-46.39L78.45,-46.3L78.32,-46.35L78.08,-46.33L77.87,-46.43L77.65,-46.42L77.43,-46.5L77.1,-46.45L76.24,-46.55L75.61,-46.51L75.49,-46.6L75.55,-46.67L75.46,-46.67L75.4,-46.61L75.45,-46.5L75.41,-46.47L75.3,-46.52L75.21,-46.43L75.09,-46.46L74.91,-46.4L74.77,-46.11L74.55,-46.01L74.28,-46L74.3,-45.79L74.24,-45.75L74.31,-45.67L74.09,-45.51L74.08,-45.35L74.16,-45.27L74.1,-44.99L74.02,-45.01L74,-45.19L73.44,-45.61L73.53,-45.73L73.44,-45.81L73.56,-45.82L73.74,-46.01L73.66,-46.06L73.68,-46.18L74.02,-46.2L73.95,-46.29L74.09,-46.43L74.37,-46.52L74.63,-46.75L74.94,-46.82L75.34,-46.73L75.83,-46.82L76.2,-46.78L76.45,-46.64L76.67,-46.67L77.08,-46.62L77.17,-46.56L77.27,-46.61L77.86,-46.65L78.14,-46.59L78.3,-46.47L78.4,-46.66L78.48,-46.62L78.58,-46.72L78.76,-46.72L78.82,-46.79L78.99,-46.75ZM30.81,8.58L30.67,8.5L30.53,8.58L30.57,8.51L30.46,8.5L30.46,8.38L30.57,8.26L30.57,8.12L30.28,7.85L30.15,7.3L29.54,6.75L29.48,6.51L29.19,6.04L29.19,5.92L29.33,5.8L29.37,5.62L29.1,5.05L29.12,4.59L29.2,4.51L29.25,4.1L29.15,4.33L29.06,4.29L29.14,3.41L29.2,3.34L29.33,3.39L29.36,3.86L29.65,4.42L29.6,4.9L29.79,5.04L29.76,5.47L29.95,5.86L29.75,6.03L29.72,6.24L29.95,6.5L30.17,6.48L30.53,6.92L30.6,7.54L30.96,8.12L30.96,8.24L31.14,8.45L31.18,8.74L31.02,8.79L30.81,8.58ZM-52.6,32.59L-52.81,32.91L-52.89,32.91L-53.02,32.8L-53.13,32.85L-53.23,33.06L-53.41,33.16L-53.45,33.53L-53.54,33.54L-53.62,33.14L-53.47,32.96L-53.35,32.93L-53.3,32.76L-52.81,32.39L-52.72,32.2L-52.6,32.59ZM-97.96,-50.36L-98.24,-50.21L-98.52,-50.24L-98.61,-50.57L-99.01,-51.11L-98.99,-51.15L-98.85,-51.04L-98.9,-51.19L-99.03,-51.27L-99.16,-51.54L-99.37,-51.64L-99.53,-51.55L-99.55,-51.71L-99.39,-51.78L-99.22,-51.64L-99.17,-51.78L-98.92,-51.4L-98.97,-51.68L-98.83,-51.68L-98.76,-51.59L-98.75,-51.36L-98.57,-51.24L-98.72,-51.09L-98.74,-50.93L-98.24,-50.72L-97.97,-50.47L-97.96,-50.36ZM-99.67,-51.61L-99.77,-51.59L-99.94,-51.72L-99.9,-51.84L-99.98,-52.04L-100,-51.74L-100.11,-51.89L-100.17,-52.25L-99.99,-52.57L-100.06,-52.76L-100.29,-52.86L-100.34,-52.81L-100.28,-52.78L-100.28,-52.62L-100.42,-52.77L-100.45,-52.95L-100.6,-53L-100.67,-52.98L-100.62,-52.89L-100.68,-52.78L-100.82,-52.75L-100.83,-52.81L-100.99,-52.88L-100.99,-52.99L-101.09,-53.1L-100.96,-53.15L-100.73,-53.1L-100.51,-53.17L-99.68,-52.91L-99.68,-52.47L-99.84,-52.24L-99.74,-52L-99.78,-51.76L-99.65,-51.84L-99.62,-51.65L-99.67,-51.61ZM-68.26,-51.4L-68.22,-51.27L-68.64,-50.99L-68.74,-50.72L-68.78,-51L-69.18,-51.32L-69.13,-51.52L-69.25,-51.68L-69.12,-51.66L-69.06,-51.84L-69.01,-51.63L-68.86,-51.72L-68.7,-51.69L-68.53,-51.76L-68.46,-51.88L-68.46,-51.67L-68.32,-51.64L-68.2,-51.69L-68.29,-51.54L-68.26,-51.4ZM-68.54,-51.39L-68.56,-51.48L-68.39,-51.37L-68.4,-51.53L-68.61,-51.63L-68.84,-51.6L-69.1,-51.41L-69.01,-51.28L-68.68,-51.16L-68.4,-51.26L-68.54,-51.39ZM35.4,-45.26L35.06,-45.38L35.02,-45.6L34.74,-45.79L34.64,-45.84L34.5,-45.79L34.61,-45.94L34.39,-45.89L34.36,-46L34.19,-46.03L34.16,-45.94L34.07,-46.06L33.92,-46.04L33.7,-46.21L33.85,-46.23L34.11,-46.14L34.17,-46.27L34.3,-46.18L34.54,-46.16L34.43,-46.02L34.48,-45.98L34.72,-46.16L34.71,-46.05L34.79,-46.02L34.84,-45.84L35.43,-45.29L35.4,-45.26ZM29.52,-62.12L29.49,-62.05L29.76,-61.95L29.73,-61.85L29.1,-61.58L28.73,-61.67L28.63,-61.64L28.79,-61.59L28.68,-61.56L28.69,-61.48L28.35,-61.35L28.71,-61.35L28.87,-61.25L28.79,-61.2L28.29,-61.08L27.95,-61.07L27.88,-61.16L28.2,-61.16L28.07,-61.23L27.63,-61.21L27.27,-61.32L27.28,-61.65L27.33,-61.69L27.36,-61.53L27.46,-61.52L27.49,-61.62L27.66,-61.61L27.77,-61.69L27.63,-61.8L27.87,-61.7L28.05,-61.51L28.18,-61.54L28.26,-61.74L28.84,-61.86L28.4,-62.07L27.93,-62.13L27.8,-62.43L27.55,-62.41L27.18,-62.55L27.34,-62.52L27.4,-62.58L27.67,-62.51L27.61,-62.6L27.68,-62.91L27.49,-62.86L27.18,-63.08L27.24,-63.33L27.13,-63.5L26.9,-63.58L27.18,-63.52L27.21,-63.42L27.36,-63.32L27.26,-63.15L27.44,-63.02L27.77,-62.95L27.77,-63.1L27.89,-63.02L28.35,-63.04L28.15,-62.93L28.15,-62.8L28.26,-62.66L28.9,-62.39L28.66,-62.42L28.37,-62.59L28.1,-62.44L28.14,-62.54L28.06,-62.69L27.85,-62.72L27.77,-62.68L27.76,-62.58L27.92,-62.43L28.04,-62.41L27.97,-62.26L28.32,-62.29L28.57,-62.22L28.7,-62.33L28.67,-62.39L28.87,-62.24L28.79,-62.18L28.83,-62.13L29.33,-62.17L29.28,-62.6L29.63,-62.42L29.59,-62.53L29.7,-62.61L29.93,-62.43L29.6,-62.27L29.98,-62.13L29.52,-62.12ZM27.64,-61.27L27.68,-61.31L27.63,-61.38L27.42,-61.44L27.33,-61.4L27.64,-61.27ZM27.96,-61.48L27.95,-61.53L27.73,-61.55L27.7,-61.49L27.52,-61.49L27.75,-61.4L27.96,-61.48ZM28.5,-61.48L28.44,-61.52L28.54,-61.62L28.52,-61.7L28.28,-61.71L28.31,-61.58L28.24,-61.54L28.24,-61.39L28.5,-61.48ZM29.48,-61.97L29.32,-62.13L28.7,-62.08L28.69,-62.04L28.99,-61.8L29.14,-61.78L29.25,-61.81L29.34,-61.97L29.48,-61.97ZM84.52,-47.93L84.36,-47.73L84.24,-47.71L83.62,-48.01L83.03,-48.21L83.5,-48.3L83.53,-48.38L83.39,-48.55L83.47,-48.86L83.75,-49.04L84.12,-49.16L84.1,-49.24L83.85,-49.42L83.66,-49.44L83.36,-49.64L83.61,-49.61L83.96,-49.73L83.73,-49.54L84.36,-49.16L83.61,-48.91L83.51,-48.81L83.49,-48.72L83.61,-48.44L83.92,-48.4L83.68,-48.35L83.58,-48.27L84.52,-47.93ZM-108.56,-56.51L-108.69,-56.49L-108.74,-56.67L-108.86,-56.71L-108.76,-56.81L-108.42,-56.63L-108.41,-56.46L-108.07,-56.38L-108.19,-56.27L-108.14,-56.04L-108.3,-55.86L-108.57,-55.7L-108.63,-55.55L-108.76,-55.9L-109.03,-55.93L-109.16,-56.07L-109.09,-56.12L-108.87,-56.08L-108.67,-55.98L-108.6,-55.85L-108.52,-55.88L-108.43,-56.1L-108.27,-56.24L-108.54,-56.37L-108.56,-56.51ZM-71.17,46.53L-71.38,46.58L-71.78,46.5L-72.26,46.59L-72.77,46.87L-72.9,47.01L-72.66,46.66L-72.69,46.5L-72.58,46.61L-72.48,46.6L-71.99,46.44L-71.87,46.38L-71.87,46.32L-71.63,46.3L-71.17,46.53ZM26.95,-62.85L27.09,-62.84L26.88,-62.8L27,-62.61L26.82,-62.56L26.91,-62.46L26.74,-62.49L26.69,-62.6L26.58,-62.41L26.42,-62.32L26.41,-62.42L26.56,-62.49L26.53,-62.54L26.27,-62.55L26.24,-62.48L26.31,-62.37L26.17,-62.36L26.13,-62.28L25.96,-62.36L26,-62.28L25.95,-62.14L25.88,-62.21L25.83,-62.15L25.88,-62.02L25.64,-61.95L25.7,-61.89L25.59,-61.79L25.72,-61.81L25.71,-61.6L25.59,-61.59L25.57,-61.49L25.64,-61.47L25.54,-61.42L25.55,-61.33L26.08,-61.2L26.28,-61.37L26.26,-61.25L26.15,-61.26L26.24,-61.1L26.03,-60.96L26.1,-61.1L26.03,-61.17L25.87,-61.17L25.67,-61.27L25.53,-61.11L25.59,-61.02L25.36,-61.08L25.5,-61.23L25.27,-61.35L25.19,-61.47L25.19,-61.53L25.42,-61.63L25.21,-61.79L25.39,-61.79L25.44,-61.84L25.32,-61.9L25.51,-61.93L25.67,-62.06L25.47,-62.14L25.67,-62.14L25.92,-62.39L25.63,-62.63L25.89,-62.72L25.82,-62.79L25.93,-62.91L25.83,-63.01L25.62,-63.07L25.52,-62.97L25.44,-62.97L25.37,-63.01L25.44,-63.05L25.44,-63.13L25.62,-63.22L25.79,-63.09L25.9,-63.11L26.08,-62.99L26.01,-62.97L26.36,-62.77L26.3,-62.73L26.07,-62.82L25.98,-62.71L26.03,-62.63L25.82,-62.61L25.94,-62.46L26.1,-62.52L26.08,-62.42L26.16,-62.39L26.18,-62.55L26.45,-62.63L26.47,-62.7L26.36,-62.85L26.79,-62.61L26.82,-62.7L26.57,-62.9L26.73,-62.84L26.73,-62.96L27,-63.03L26.95,-62.92L26.89,-62.92L26.95,-62.85ZM30.36,-65.15L30.65,-65.07L30.97,-65.18L31.35,-65.18L31.58,-65.14L31.95,-64.86L31.66,-64.94L31.37,-65.12L30.91,-65.07L30.74,-64.94L30.54,-64.93L30.71,-65.02L30.36,-65.15ZM35.3,-47.49L34.96,-47.41L34.59,-47.52L34.19,-47.42L34.17,-47.32L33.9,-47.16L33.69,-46.86L33.54,-46.83L33.63,-47.03L33.96,-47.33L33.94,-47.54L35,-47.59L35.09,-47.68L35.11,-47.84L35.3,-47.49ZM48.39,-54.17L48.42,-54.6L48.75,-54.68L48.86,-54.87L48.86,-55.01L49.16,-55.16L49.17,-55.29L49.06,-55.48L49.3,-55.32L49.36,-55.34L49.37,-55.54L49.45,-55.4L49.79,-55.38L50.09,-55.46L51.41,-55.49L51.47,-55.51L51.41,-55.77L51.48,-55.83L51.46,-55.7L51.52,-55.63L51.76,-55.72L51.94,-55.7L51.75,-55.68L51.71,-55.59L51.55,-55.56L51.41,-55.44L51.21,-55.49L51.18,-55.36L50.88,-55.45L49.89,-55.29L49.46,-55.11L49.4,-55.02L49.01,-54.97L48.94,-54.9L48.97,-54.83L49.1,-54.8L48.99,-54.73L48.86,-54.46L48.53,-54.39L48.55,-54.24L48.8,-54.13L48.85,-54.05L49.02,-54.02L49.73,-54.23L49.22,-53.93L49.37,-53.69L49.13,-53.82L49.06,-53.61L49.09,-53.53L49.88,-53.49L49.85,-53.43L49.49,-53.44L49.32,-53.4L49.23,-53.28L48.8,-53.28L48.76,-53.32L49.14,-53.31L49.2,-53.37L48.99,-53.44L48.87,-53.65L48.9,-53.83L48.81,-53.94L48.39,-54.17ZM-113.64,-35.83L-113.99,-36.16L-114.21,-36.01L-114.5,-36.11L-114.64,-36.11L-114.74,-36.01L-114.82,-36.12L-114.43,-36.24L-114.34,-36.52L-114.37,-36.21L-114.3,-36.11L-114.23,-36.05L-114.16,-36.08L-114,-36.24L-113.64,-35.83ZM-110.37,-37.9L-110.43,-37.71L-110.84,-37.22L-110.68,-37.18L-111.47,-36.93L-111.53,-37.03L-111.34,-37.06L-111.26,-37.15L-110.96,-37.15L-110.74,-37.43L-110.76,-37.53L-110.55,-37.63L-110.44,-37.87L-110.37,-37.9ZM-98.29,-57.49L-98.2,-57.41L-97.99,-57.39L-98.25,-57.11L-98.56,-57.06L-98.85,-56.84L-99,-56.86L-99.22,-56.74L-99.55,-56.71L-99.57,-56.64L-99.69,-56.73L-99.55,-56.78L-99.33,-56.99L-99.16,-56.96L-99.01,-57.08L-99.01,-56.93L-98.87,-56.95L-98.86,-57.06L-98.7,-57.12L-98.67,-57.26L-98.51,-57.3L-98.59,-57.53L-98.56,-57.61L-98.47,-57.55L-98.21,-57.65L-98.29,-57.49ZM-40.92,9.26L-40.82,9.44L-41.1,9.5L-41.19,9.7L-41.65,9.82L-41.87,9.77L-42.08,9.89L-42.17,10.08L-41.99,10.15L-41.87,10.3L-41.99,10.2L-42.34,10.1L-42.36,10.19L-42.16,10.67L-42.34,11L-42.24,10.66L-42.26,10.55L-42.41,10.41L-42.73,10.84L-42.83,11.25L-42.93,11.24L-43.07,11.11L-43.15,11.14L-43.09,10.94L-42.89,10.77L-42.99,10.62L-42.95,10.59L-42.78,10.74L-42.75,10.61L-42.85,10.46L-42.67,10.54L-42.61,10.48L-42.67,10.29L-42.5,10.33L-42.6,10.09L-42.82,9.96L-42.73,9.92L-42.55,10.08L-42.48,10.04L-42.51,9.95L-42.36,9.98L-42.29,9.83L-42.35,9.71L-42.22,9.7L-42.05,9.51L-41.92,9.62L-41.74,9.56L-41.26,9.59L-41.22,9.51L-41.26,9.36L-41.19,9.37L-41.18,9.28L-41.06,9.28L-41.03,9L-40.93,9.06L-40.92,9.26ZM-42.8,10.96L-42.85,10.94L-42.78,10.83L-42.99,10.94L-42.88,10.98L-42.93,11.08L-42.88,11.15L-42.81,11.08L-42.8,10.96ZM99.14,-2.41L98.85,-2.35L98.69,-2.56L98.88,-2.48L98.95,-2.5L98.92,-2.56L98.76,-2.73L98.64,-2.65L98.53,-2.86L98.79,-2.8L99.14,-2.41ZM26.57,-61.62L26.18,-61.73L26.08,-61.7L26.18,-61.63L26.11,-61.54L25.89,-61.68L25.95,-61.72L25.94,-61.8L26.13,-61.77L26.24,-61.84L26.29,-61.72L26.47,-61.74L26.57,-61.62ZM170.25,44.12L170.18,44.17L170.13,43.81L170.2,43.7L170.25,44.12ZM170,44.29L169.86,44.22L169.88,43.97L169.91,44.05L169.98,43.97L169.91,44.17L170,44.29ZM-80.18,-48.81L-80.11,-48.91L-79.89,-48.92L-79.83,-48.73L-79.7,-48.72L-79.58,-48.8L-79.26,-48.69L-79.23,-48.47L-79.31,-48.45L-79.32,-48.63L-79.87,-48.63L-80.18,-48.81ZM-106.22,-47.59L-106.27,-47.55L-106.25,-47.64L-106.45,-47.88L-106.56,-47.75L-106.81,-47.72L-106.86,-47.63L-107.31,-47.68L-107.61,-47.62L-107.91,-47.39L-107.95,-47.56L-108.2,-47.6L-107.96,-47.6L-107.84,-47.53L-107.69,-47.65L-107.71,-47.69L-106.93,-47.73L-106.6,-47.86L-106.59,-47.96L-106.43,-48.03L-106.33,-47.99L-106.36,-47.93L-106.25,-47.81L-106.22,-47.59ZM-100.29,-45.02L-100.37,-44.99L-100.48,-44.79L-100.64,-44.75L-100.6,-44.6L-100.49,-44.57L-100.41,-44.42L-100.61,-44.47L-100.72,-44.73L-101.19,-44.73L-100.78,-44.88L-100.56,-44.81L-100.46,-44.87L-100.45,-45L-100.33,-45.16L-100.35,-45.3L-100.61,-45.35L-100.34,-45.39L-100.64,-45.66L-100.45,-45.64L-100.39,-45.71L-100.66,-46.12L-100.61,-46.49L-100.78,-46.71L-100.59,-46.62L-100.53,-46.39L-100.56,-46.1L-100.35,-45.85L-100.41,-45.56L-100.28,-45.43L-100.29,-45.02ZM-132.1,-59.61L-132.4,-59.92L-132.96,-60.2L-133.24,-60.45L-132.36,-59.99L-132.1,-59.61ZM-117.91,-49.34L-118.14,-49.52L-118.09,-49.8L-118.09,-49.52L-117.91,-49.34ZM32.23,-22.67L32.06,-22.66L31.83,-22.35L31.65,-22.31L31.44,-22.1L31.32,-21.81L31.09,-21.61L31.45,-22.21L31.78,-22.48L31.68,-22.63L31.82,-22.57L32.13,-22.78L32.34,-22.69L32.5,-22.76L32.74,-23.23L32.86,-23.34L32.84,-23.48L32.6,-23.5L32.71,-23.57L32.62,-23.59L32.65,-23.63L32.83,-23.62L32.87,-23.79L32.82,-23.91L32.88,-23.99L32.99,-23.7L32.91,-23.61L33,-23.51L32.92,-23.48L33.01,-23.24L32.92,-23.25L32.86,-23.12L32.99,-22.96L32.74,-23.03L32.59,-22.78L32.33,-22.55L32.25,-22.54L32.3,-22.59L32.23,-22.67ZM24.61,-61.65L24.46,-61.59L24.51,-61.55L24.47,-61.53L24.19,-61.46L24.13,-61.34L24.28,-61.29L24.01,-61.23L24.36,-61.16L24.44,-61.03L23.78,-61.21L23.77,-61.28L23.95,-61.22L24.04,-61.42L24.36,-61.59L24.32,-61.63L24.69,-61.72L24.61,-61.65ZM23.51,-61.42L23.72,-61.26L23.35,-61.39L23.71,-61.51L23.57,-61.64L23.63,-61.65L23.71,-61.86L24.03,-61.97L24,-62.08L23.68,-62.12L23.64,-62.22L23.85,-62.14L24,-62.23L23.95,-62.16L24.18,-62.16L24.13,-62.06L24.22,-62.05L24.3,-62.12L24.3,-62.04L24.38,-62.03L24.57,-62.05L24.36,-62.16L24.59,-62.09L24.61,-62.25L24.72,-62.2L24.63,-62.04L24.71,-61.92L24.55,-61.99L24.09,-62.02L24.1,-61.95L23.76,-61.79L23.74,-61.65L23.83,-61.64L23.77,-61.62L23.78,-61.52L23.51,-61.42ZM0.27,-6.67L0.15,-6.61L0.1,-6.34L0.07,-6.4L-0.01,-6.38L-0.1,-6.49L-0.67,-6.8L-0.55,-6.81L-0.47,-6.72L-0.39,-6.83L-0.34,-6.72L-0.19,-6.74L-0.14,-6.65L-0.06,-6.63L-0.02,-6.73L-0.07,-6.83L0.11,-6.9L0.04,-6.95L0.12,-6.98L0.08,-7.15L0.01,-7.21L0.1,-7.19L0.18,-7.29L0.05,-7.48L-0.06,-7.51L-0.07,-7.44L-0.24,-7.52L0.01,-7.54L-0.06,-7.64L-0.65,-7.55L-0.1,-7.76L-0.16,-7.78L-0.19,-7.96L-0.32,-8.04L-0.42,-7.97L-0.38,-8.05L-0.53,-8.06L-0.54,-8.15L-0.62,-8.08L-0.76,-8.1L-0.6,-8.17L-0.8,-8.32L-1,-8.63L-1.13,-8.63L-1.15,-8.55L-1.22,-8.66L-1.4,-8.74L-1.71,-8.63L-1.38,-8.8L-1.27,-8.73L-1.06,-8.72L-1.17,-8.94L-1.15,-9.12L-1.11,-8.9L-0.87,-8.59L-0.82,-8.6L-0.79,-8.76L-0.81,-8.69L-0.71,-8.64L-0.8,-8.52L-0.78,-8.47L-0.48,-8.21L-0.29,-8.25L-0.2,-8.21L-0.33,-8.16L-0.13,-8.01L-0.02,-7.79L0.07,-7.82L0.07,-8.08L0.17,-8.09L0.11,-8.24L0.22,-8.36L0.09,-8.4L0.09,-8.55L0.2,-8.74L0.1,-8.43L0.29,-8.33L0.21,-8.31L0.18,-8.21L0.27,-8.09L0.16,-8.06L0.11,-7.94L0.17,-7.86L0.26,-7.9L0.28,-7.58L0.23,-7.54L0.25,-7.49L0.32,-7.54L0.24,-6.9L0.27,-6.67ZM103.53,-53.64L103.73,-53.6L103.74,-53.5L103.49,-53.56L103.44,-53.52L103.44,-53.22L103.37,-53.11L103.34,-53.57L103.27,-53.68L102.87,-53.79L103.21,-53.81L102.99,-54.16L103.11,-54.42L103.22,-54.49L103.19,-54.63L103.03,-54.78L103.07,-54.92L103.28,-55.16L103.14,-55.68L102.99,-55.85L102.92,-56.06L102.53,-56.16L102.44,-56.09L102.24,-56.1L101.99,-56.03L101.91,-55.78L102.08,-55.72L102.05,-55.66L102.1,-55.63L102.39,-55.54L102.31,-55.4L102.43,-55.29L102.12,-55.05L102.33,-55.27L102.26,-55.41L102.3,-55.53L101.79,-55.41L101.76,-55.47L101.98,-55.52L101.81,-55.65L101.79,-55.77L101.27,-55.98L101.71,-55.97L101.73,-56.07L101.67,-56.13L101.77,-56.29L101.96,-56.23L101.95,-56.12L102.26,-56.25L102.46,-56.25L102.52,-56.35L102.63,-56.25L103.02,-56.21L103.06,-55.92L103.25,-55.71L103.23,-55.56L103.36,-55.22L103.15,-54.8L103.46,-54.16L103.26,-54.34L103.1,-54.15L103.33,-53.78L103.53,-53.64ZM91.94,-68.49L92.1,-68.51L92.33,-68.43L89.94,-68.24L89.31,-68.34L89.31,-68.39L90.23,-68.37L91.94,-68.49ZM91.31,-68.79L90.05,-68.7L89.55,-68.82L89.74,-68.86L90.45,-68.76L91.71,-68.86L91.31,-68.79ZM89.47,-69.38L88.96,-69.32L88.85,-69.37L90.21,-69.63L91.08,-69.49L91.44,-69.51L91.56,-69.42L90.1,-69.54L89.47,-69.38ZM17.97,-65.85L17.74,-65.86L17.69,-65.88L17.72,-65.98L17.35,-66.08L17.67,-66.07L17.72,-66.12L17.62,-66.19L17.78,-66.19L18.01,-66.05L17.95,-66L17.97,-65.85ZM18,-65.88L18.51,-65.66L18.09,-65.63L17.97,-65.85L18,-65.88ZM15.76,-63.76L15.64,-63.81L15.54,-63.76L15.52,-63.85L15.26,-63.96L15.42,-63.94L15.32,-64.03L15.32,-64.11L15.04,-64.28L14.33,-64.39L13.71,-64.64L13.8,-64.66L14.36,-64.42L15.21,-64.32L15.42,-64.08L15.4,-64.02L15.58,-63.87L15.74,-63.83L15.82,-63.75L15.76,-63.76ZM13.29,-64.74L13.4,-64.79L13.63,-64.69L13.23,-64.67L13.29,-64.74ZM19.29,-42.26L19.36,-42.29L19.47,-42.08L19.22,-42.16L19.1,-42.28L19.29,-42.26ZM-107.93,-64.04L-108.16,-64.04L-108.46,-63.95L-108.86,-64.07L-109.64,-64.05L-108.63,-64.17L-108.6,-64.33L-108.47,-64.41L-108.42,-64.27L-108.25,-64.32L-108.34,-64.16L-108.19,-64.18L-107.94,-64.09L-107.93,-64.04ZM-107.94,-64.09L-107.32,-64.13L-107.24,-64.1L-107.27,-63.98L-107.22,-63.93L-107.09,-63.91L-107.27,-63.78L-107.5,-63.79L-107.63,-63.88L-107.62,-63.97L-107.81,-63.96L-107.94,-64.09ZM-99.15,-43.43L-98.56,-43.06L-98.9,-43.16L-99.32,-43.47L-99.47,-43.67L-99.37,-43.84L-99.36,-43.99L-99.3,-43.9L-99.41,-43.7L-99.15,-43.43ZM-99.18,-26.76L-99.11,-26.73L-99.15,-26.59L-99.24,-26.58L-99.28,-26.76L-99.39,-26.79L-99.37,-26.89L-99.46,-27.06L-99.22,-26.91L-99.18,-26.76ZM-107.79,-55.21L-108.04,-55.51L-107.99,-55.57L-107.81,-55.55L-107.86,-55.66L-107.77,-55.7L-107.74,-55.92L-107.67,-55.74L-107.79,-55.21ZM-103.84,-60.55L-103.95,-60.42L-104.19,-60.34L-104.13,-60.53L-104.49,-60.73L-104.34,-60.87L-104.59,-60.81L-104.64,-60.86L-104.53,-60.86L-104.45,-61L-104.33,-61.03L-104.21,-60.94L-104.22,-60.81L-104.14,-60.83L-104.22,-60.74L-103.85,-60.82L-103.72,-60.95L-103.65,-60.9L-103.67,-60.83L-104.14,-60.67L-104.04,-60.6L-103.75,-60.7L-103.84,-60.55ZM-95.25,-65L-95.46,-64.92L-95.49,-64.77L-95.8,-64.92L-95.88,-64.85L-96.03,-64.92L-95.93,-65L-95.63,-65.04L-95.25,-65ZM-69.35,-54.08L-69.27,-54.05L-69.32,-54.02L-69.83,-53.95L-69.71,-54.07L-70.14,-54.13L-69.87,-54.29L-70.08,-54.34L-69.9,-54.38L-69.68,-54.27L-69.7,-54.15L-69.35,-54.08ZM-68.68,-53.8L-68.72,-53.58L-68.85,-53.59L-68.9,-53.48L-69.06,-53.43L-68.95,-53.61L-68.83,-53.68L-68.87,-53.74L-68.77,-53.8L-69.01,-53.94L-69.24,-53.96L-69.15,-54.04L-69,-54.04L-68.68,-53.8ZM-70.23,-54.44L-70.42,-54.36L-70.52,-54.44L-69.97,-54.49L-69.91,-54.62L-70.03,-54.68L-69.98,-54.74L-69.9,-54.7L-69.77,-54.47L-70.23,-54.44ZM-88.06,-36.67L-87.91,-36.19L-87.98,-35.95L-88.04,-35.95L-87.99,-36.23L-88.04,-36.31L-88.12,-36.29L-88.08,-36.55L-88.28,-37.02L-88.06,-36.67ZM-82.41,-33.95L-82.21,-33.66L-82.57,-33.64L-82.28,-33.73L-82.49,-33.9L-82.58,-33.87L-82.59,-34.02L-82.41,-33.95ZM-118.4,-52.17L-118.18,-52.18L-118.5,-52.07L-118.55,-52.24L-119.13,-52.74L-118.4,-52.17ZM-81.68,-29.37L-81.68,-29.51L-81.53,-29.22L-81.6,-29.2L-81.68,-29.37ZM-114.36,-34.44L-114.38,-34.54L-114.08,-34.32L-114.16,-34.25L-114.36,-34.44ZM-122.23,-40.87L-122.23,-40.79L-122.1,-40.77L-122.41,-40.72L-122.4,-40.83L-122.35,-40.78L-122.23,-40.87ZM-114.1,-65.38L-114.18,-65.45L-114.44,-65.48L-114.4,-65.66L-114.23,-65.68L-114.18,-65.61L-114.3,-65.6L-114.29,-65.56L-113.84,-65.37L-113.27,-65.4L-113.12,-65.36L-113.31,-65.32L-112.68,-65.2L-112.22,-65.23L-112.35,-65.13L-112.24,-64.97L-112.32,-64.96L-112.46,-65.15L-113.32,-65.26L-113.79,-65.24L-114.1,-65.38ZM-121.94,-42.6L-121.95,-42.5L-121.83,-42.41L-121.81,-42.25L-122.06,-42.47L-121.94,-42.6ZM-67.71,-45.69L-67.6,-45.64L-67.48,-45.68L-67.45,-45.61L-67.63,-45.6L-67.86,-45.74L-67.79,-45.76L-67.71,-45.69ZM-49.71,4.42L-49.81,4.41L-49.87,4.32L-49.72,4.03L-49.71,3.86L-49.63,3.85L-49.43,4.49L-49.3,4.68L-49.29,4.84L-49.35,4.88L-49.28,5.16L-49.18,5.28L-48.96,5.28L-48.97,5.33L-49.17,5.39L-49.28,5.3L-49.59,4.65L-49.71,4.59L-49.65,4.48L-49.71,4.42ZM-44.97,18.78L-44.92,18.86L-45.13,18.85L-45.09,19.05L-45.16,18.95L-45.4,19.01L-45.39,18.92L-45.25,18.91L-45.19,18.83L-45.21,18.75L-45.25,18.84L-45.34,18.83L-45.26,18.68L-45.26,18.62L-45.37,18.64L-45.32,18.5L-45.52,18.59L-45.48,18.47L-45.35,18.39L-45.36,18.24L-45.23,18.23L-45.28,18.41L-45.13,18.61L-45.15,18.73L-45.1,18.77L-45.02,18.72L-44.97,18.78ZM-51.42,20.43L-51.43,20.26L-51.18,20.26L-51.15,20.15L-51.08,20.17L-51,19.67L-50.95,19.98L-50.58,19.82L-50.67,19.95L-50.94,20.09L-50.99,20.17L-50.91,20.32L-51.25,20.39L-51.07,20.53L-51.42,20.43ZM-68.68,45.42L-68.57,45.61L-68.85,45.64L-68.97,45.45L-68.97,45.28L-68.88,45.29L-68.84,45.41L-68.77,45.37L-68.68,45.42ZM38.91,-60.59L38.84,-60.73L38.94,-60.77L39.17,-60.68L39.19,-60.5L39.03,-60.4L39.05,-60.52L38.91,-60.59ZM31.55,-64.44L31.35,-64.47L31.37,-64.5L31.74,-64.48L31.79,-64.5L31.76,-64.56L32.04,-64.46L32,-64.41L31.55,-64.44ZM32.41,-67.46L32.25,-67.41L31.9,-67.51L32.22,-67.54L32.41,-67.46ZM35.16,-67.81L35.08,-67.71L35,-67.8L35.16,-67.91L35.1,-67.98L35.25,-68.1L35.3,-68.01L35.26,-67.88L35.16,-67.81ZM67.99,-41.25L68.46,-41.11L68.14,-41.05L67.93,-41.22L67.99,-41.25ZM111.12,-62.62L111.19,-62.71L111.14,-62.85L110.43,-62.99L110.48,-63.14L110.04,-63.21L110.37,-63.24L110.39,-63.35L110.16,-63.44L109.85,-63.38L109.59,-63.46L109.9,-63.46L110.14,-63.62L110.13,-63.54L110.61,-63.39L110.47,-63.25L110.55,-63.2L110.74,-63.24L110.92,-63.18L110.72,-63.06L110.94,-63L111.09,-63.09L111.04,-63.31L111.14,-63.42L111.16,-63.18L111.27,-63.12L111.56,-63.17L111.54,-63.29L111.9,-63.22L111.99,-63.1L111.83,-62.96L112,-62.9L112.15,-62.97L112.12,-63.13L112.05,-63.31L111.82,-63.38L112.13,-63.43L112.17,-63.42L112.15,-63.25L112.23,-63.13L112.48,-63.02L112.4,-63L112.37,-62.84L112.17,-62.76L111.85,-62.87L111.58,-62.86L111.4,-62.92L111.77,-63.07L111.84,-63.16L111.79,-63.2L111.52,-63.05L111.21,-63.01L111.19,-62.94L111.34,-62.85L111.42,-62.65L111.29,-62.43L111.6,-62.39L111.67,-62.33L111.39,-62.33L111.37,-62.28L111.6,-62.21L111.29,-62.19L111.4,-62.06L111.05,-61.99L110.16,-62.12L109.67,-61.91L109.6,-61.78L109.56,-61.8L109.63,-62.05L109.82,-62.06L110.15,-62.2L111.09,-62.05L111.16,-62.11L111.12,-62.22L111.24,-62.31L111.21,-62.43L110.78,-62.53L111.05,-62.54L111.12,-62.62ZM174.43,-64.57L174.58,-64.58L174.61,-64.65L174.8,-64.65L174.67,-64.48L174.54,-64.43L174.34,-64.44L174.21,-64.51L174.37,-64.7L174.35,-64.59L174.43,-64.57ZM136.06,-35.39L136.14,-35.47L136.27,-35.35L135.89,-35L136.06,-35.39ZM-137.15,-61.5L-137,-61.23L-137.17,-61.45L-137.52,-61.64L-137.44,-61.65L-137.15,-61.5ZM-155.45,-58.64L-155.65,-58.6L-155.47,-58.53L-155.65,-58.52L-155.84,-58.6L-156.32,-58.63L-156.41,-58.69L-156.15,-58.73L-155.45,-58.64ZM-162.84,-61.04L-163.03,-61.08L-162.71,-61.08L-162.84,-61.04ZM-154.47,-60.22L-153.63,-60.44L-154.72,-60.04L-154.75,-60.07L-154.47,-60.22ZM-151.17,-60.23L-151.06,-60.3L-150.89,-60.27L-150.65,-60.12L-150.72,-60.05L-151.17,-60.23ZM-163.71,-61.56L-163.64,-61.52L-163.7,-61.47L-163.97,-61.65L-163.71,-61.56ZM-87.66,-34.81L-87.38,-34.85L-87.01,-34.68L-86.9,-34.57L-87.32,-34.77L-87.7,-34.77L-87.66,-34.81ZM90.4,-33.53L90.39,-33.44L90.25,-33.33L90.01,-33.44L90.19,-33.42L90.29,-33.47L90.32,-33.7L90.4,-33.53ZM78.44,-33.94L78.49,-33.97L78.76,-33.75L78.98,-33.72L78.73,-33.68L78.44,-33.94ZM69.29,-50.69L69.62,-50.68L69.61,-50.61L69.27,-50.59L69.05,-50.43L69.06,-50.36L69.24,-50.35L69.26,-50.25L68.94,-50.18L68.69,-50.27L68.78,-50.51L68.86,-50.57L69.09,-50.56L69.29,-50.69ZM64.57,-52.6L64.98,-52.88L64.97,-52.73L64.89,-52.67L64.52,-52.52L64.57,-52.6ZM11.85,-62.21L11.89,-62.4L11.97,-62.41L11.89,-62.09L11.93,-61.93L11.72,-62.1L11.85,-62.21ZM-76.68,-51.37L-76.56,-51.34L-76.75,-51.29L-77.03,-51.33L-76.82,-51.42L-76.68,-51.37ZM-77.27,-47.59L-76.93,-47.49L-76.97,-47.44L-77.18,-47.46L-77.16,-47.39L-77.26,-47.35L-77.32,-47.57L-77.27,-47.59ZM-108.19,-64.65L-108.53,-64.56L-108.24,-64.68L-108.19,-64.65ZM-78.87,-71.16L-78.67,-71.11L-78.9,-71.09L-79.37,-71.15L-78.87,-71.16ZM-104.51,-69.72L-104.86,-69.86L-104.36,-69.82L-104.51,-69.72ZM-98.38,-67.38L-98.23,-67.33L-98.27,-67.29L-98.42,-67.19L-98.55,-67.24L-98.49,-67.42L-98.38,-67.38ZM-96.28,-55.24L-95.79,-55.4L-95.68,-55.36L-96.11,-55.22L-96.28,-55.24ZM-105.81,-54.23L-105.71,-54.49L-105.57,-54.46L-105.57,-54.33L-105.71,-54.09L-105.8,-54.08L-105.81,-54.23ZM-60.9,-52.55L-60.72,-52.44L-60.6,-52.33L-60.65,-52.32L-60.97,-52.52L-61.3,-52.6L-60.9,-52.55ZM-112,-64.66L-112.34,-64.9L-112.11,-64.85L-111.89,-64.7L-112,-64.66ZM-83.61,-48.38L-83.93,-48.31L-83.43,-48.51L-83.61,-48.38ZM-102.6,-62.66L-102.58,-62.45L-102.74,-62.41L-102.68,-62.56L-102.77,-62.7L-102.66,-62.76L-102.6,-62.66ZM-103.45,-61.37L-103.46,-61.51L-103.21,-61.68L-103.14,-61.65L-103.45,-61.37ZM-69.15,-56.51L-69.08,-56.27L-68.8,-56.05L-69.19,-56.33L-69.27,-56.5L-69.13,-56.65L-69.15,-56.51ZM-88.2,-66.63L-88.09,-66.6L-88.21,-66.58L-88.4,-66.66L-88.71,-66.6L-88.61,-66.71L-88.34,-66.71L-88.2,-66.63ZM122.82,23.68L122.61,23.47L122.7,23.27L122.88,23.25L122.93,23.28L122.93,23.59L122.82,23.68ZM128.6,22.65L128.38,22.6L128.32,22.49L128.34,22.4L128.79,22.22L129,22.01L129.22,22.04L129.07,22.17L129.06,22.27L129.22,22.42L128.9,22.65L128.6,22.65ZM135.9,32.33L136.05,31.9L135.79,31.62L135.64,31.59L135.64,31.4L135.44,31.23L135.43,31.06L135.61,31.19L135.96,31.22L136.11,31.3L136.31,31.93L136.26,32.21L135.97,32.23L135.9,32.33ZM137.83,31.72L137.75,31.9L137.6,31.78L137.7,31.66L137.73,31.33L137.53,31.11L137.66,31.03L137.63,30.67L137.43,30.63L137.23,30.18L137.48,30.38L137.75,30.49L138,30.87L138.13,31.26L138.11,31.39L137.83,31.72ZM119.8,29.51L119.79,29.58L119.64,29.55L119.69,29.45L119.64,29.34L119.67,29.21L119.58,29.19L119.52,29.51L119.38,29.54L119.44,29.24L119.33,29.24L119.2,29.35L119.13,29.11L119.4,28.99L119.55,29.06L119.76,28.89L119.94,28.88L119.99,28.98L119.88,28.94L119.68,29.12L119.82,29.41L119.8,29.51ZM139.94,30.96L139.8,31.12L139.49,30.88L139.95,30.32L140.04,30.42L139.94,30.96ZM137.66,29.35L137.37,29.45L137.11,29.45L137.2,29.25L137.7,29.13L137.66,29.35ZM137.91,29.1L137.78,29.04L137.34,29.03L137.24,28.89L137.15,28.89L137.07,29.01L136.95,28.95L136.88,28.45L136.99,28.31L136.8,27.97L137.03,27.86L137.45,28.09L137.7,28.14L137.77,28.35L137.68,28.65L137.91,28.99L138.01,29.05L137.91,29.1Z"/></g>
        <g id="mapSubdivisions" aria-hidden="true"></g>
        <g id="mapCities" aria-hidden="true"></g>
        <g id="mapPins"></g>
      </svg>
      <div class="mapctl">
        <div class="tabs small" role="tablist" aria-label="Map region">
          <button type="button" role="tab" data-region="na">North America</button>
          <button type="button" role="tab" data-region="eu">Europe</button>
          <button type="button" role="tab" data-region="world">World</button>
        </div>
        <span class="zoombtns"><button type="button" class="iconbtn round" id="mapIn" aria-label="Zoom in">+</button><button type="button" class="iconbtn round" id="mapOut" aria-label="Zoom out">−</button></span>
      </div>
      <p class="mapcredit">Capital labels reveal as you zoom · Map data: <a href="https://www.naturalearthdata.com/" target="_blank" rel="noopener noreferrer">Natural Earth</a></p>
    </div>
    <div class="numrow"><button class="btn" id="mpGo" type="button" disabled>Tap the map to place a pin</button></div>
    <div class="chips" id="mpHist"></div>
    <p class="hint" id="mpLeft"></p>
    <div class="slot"></div>
    <p class="nodata" hidden>This game needs birthplace info. Rebuild the site to load it.</p>
  </section>

  <section class="view" id="view-conn" hidden>
    <p class="intro">Find four groups of four players who have something in common.</p>
    <div id="cnSolved"></div>
    <div class="cngrid" id="cnGrid"></div>
    <p class="hint" id="cnMistakes"></p>
    <div class="cnctl" id="cnControls">
      <button type="button" class="btn ghost" id="cnShuffle">Shuffle</button>
      <button type="button" class="btn ghost" id="cnClear">Deselect</button>
      <button type="button" class="btn" id="cnSubmit" disabled>Submit</button>
    </div>
    <div class="slot"></div>
    <p class="nodata" hidden>This game isn't available right now.</p>
  </section>

  <section class="view" id="view-rank" hidden>
    <p class="intro" id="rkIntro"></p>
    <ol class="rklist" id="rkList"></ol>
    <div class="numrow"><button class="btn" id="rkGo" type="button">Lock it in</button></div>
    <div class="chips" id="rkHist"></div>
    <p class="hint" id="rkLeft"></p>
    <div class="slot"></div>
    <p class="nodata" hidden>This game needs career stats. Rebuild the site to load them.</p>
  </section>

  <section class="view" id="view-puck" hidden>
    <p class="pkrule">Tap every player who fits: <b id="pkRule"></b></p>
    <div class="hlscore"><span>Score<b id="pkScore">0</b></span><span>Caught<b id="pkCaught">0</b></span></div>
    <div class="rinklane" id="pkLane"></div>
    <div class="numrow"><button class="btn" id="pkStart" type="button">Drop the puck</button></div>
    <p class="hint" id="pkLeft"></p>
    <div class="slot"></div>
    <p class="nodata" hidden>This game isn't available right now.</p>
  </section>

  <section class="view" id="view-shoot" hidden>
    <div class="shdots" id="shDots"></div>
    <svg class="shnet" id="shNet" viewBox="0 0 300 204" role="img" aria-label="Hockey net with a goalie">
      <defs>
        <linearGradient id="gJersey" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#2d63c4"/><stop offset="1" stop-color="#173f86"/></linearGradient>
        <linearGradient id="gPad" x1="0" x2="1"><stop offset="0" stop-color="#ffffff"/><stop offset=".7" stop-color="#eef1f6"/><stop offset="1" stop-color="#cfd7e3"/></linearGradient>
        <radialGradient id="gHelmet" cx=".35" cy=".3" r=".85"><stop offset="0" stop-color="#ffffff"/><stop offset="1" stop-color="#c3cddb"/></radialGradient>
        <linearGradient id="gPost" x1="0" x2="1"><stop offset="0" stop-color="#b3201d"/><stop offset=".45" stop-color="#ef4b45"/><stop offset="1" stop-color="#b3201d"/></linearGradient>
        <pattern id="gMesh" width="10" height="10" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <path d="M0 0 H10 M0 0 V10" class="meshline"/>
        </pattern>
      </defs>
      <rect x="0" y="190" width="300" height="14" class="ice"/>
      <circle class="lamp" cx="150" cy="9" r="5"/>
      <rect x="24" y="24" width="252" height="166" class="netback"/>
      <rect x="24" y="24" width="252" height="166" fill="url(#gMesh)" class="mesh"/>
      <path d="M78 190 A72 30 0 0 1 222 190 Z" class="crease"/>
      <path d="M22 190 V22 H278 V190" class="posts"/>
      <path d="M24 190 V24 H276 V190" class="postshine"/>

      <g id="shGoalie" class="goalie" data-pose="ready">
       <g class="posewrap">
        <g class="pose pose-ready">
        <!-- skates -->
        <rect x="116" y="182" width="30" height="7" rx="3" class="skate"/>
        <rect x="154" y="182" width="30" height="7" rx="3" class="skate"/>
        <!-- leg pads -->
        <g class="pad"><rect x="115" y="124" width="32" height="62" rx="10"/><rect x="117" y="124" width="28" height="13" rx="6" class="knee"/>
          <rect x="115" y="150" width="32" height="5" class="trim"/><rect x="115" y="164" width="32" height="3" class="trim"/><path d="M121 140 V182 M141 140 V182" class="seam"/></g>
        <g class="pad"><rect x="153" y="124" width="32" height="62" rx="10"/><rect x="155" y="124" width="28" height="13" rx="6" class="knee"/>
          <rect x="153" y="150" width="32" height="5" class="trim"/><rect x="153" y="164" width="32" height="3" class="trim"/><path d="M159 140 V182 M179 140 V182" class="seam"/></g>
        <!-- pants -->
        <path d="M118 110 H182 L187 132 Q150 138 113 132 Z" class="pants"/>
        <!-- stick -->
        <path d="M100 128 L138 162" class="shaft"/>
        <path d="M134 156 L145 156 L149 183 L139 183 Z" class="paddle"/>
        <rect x="138" y="181" width="48" height="6" rx="2" class="blade"/>
        <rect x="160" y="181" width="14" height="6" class="tape"/>
        <!-- arms -->
        <path d="M114 84 L100 118" class="arm"/>
        <path d="M186 84 L202 110" class="arm"/>
        <path d="M109 96 L104 108" class="armstripe"/>
        <path d="M191 94 L197 105" class="armstripe"/>
        <!-- body -->
        <path d="M110 80 Q150 68 190 80 L194 100 Q186 104 182 102 L181 118 Q150 122 119 118 L118 102 Q114 104 106 100 Z" class="jersey"/>
        <path d="M119 106 Q150 110 181 106 L181 113 Q150 117 119 113 Z" class="stripe"/>
        <circle cx="150" cy="92" r="8.5" class="crest"/>
        <text x="150" y="95.6" class="crestS">S</text>
        <!-- blocker -->
        <rect x="84" y="104" width="24" height="34" rx="4" class="blocker"/>
        <rect x="87" y="108" width="18" height="26" rx="2" class="blockertrim"/>
        <!-- catching glove -->
        <path d="M192 100 C192 88 216 86 222 97 L226 117 C227 129 208 134 197 126 Z" class="glove"/>
        <path d="M198 104 C204 99 214 99 219 106 M199 113 C206 109 214 110 221 115" class="pocket"/>
        <rect x="190" y="118" width="14" height="10" rx="3" class="cuff"/>
        <!-- helmet and cage -->
        <rect x="145" y="74" width="10" height="7" rx="2" class="throat"/>
        <circle cx="150" cy="61" r="16" class="helmet"/>
        <path d="M136 52 Q150 38 164 52" class="helmetstripe"/>
        <path d="M139 59 Q150 55 161 59 L160 72 Q150 80 140 72 Z" class="face"/>
        <path d="M143 58 V76 M147 57 V78 M153 57 V78 M157 58 V76 M139 63 H161 M140 68 H160 M141 73 H159" class="cage"/>
        </g>

        <g class="pose pose-stretch">
          <path d="M92 138 L96 172" class="shaft"/>
          <path d="M90 168 L101 168 L103 185 L92 185 Z" class="paddle"/>
          <rect x="92" y="182" width="34" height="6" rx="2" class="blade"/>
          <rect x="108" y="182" width="11" height="6" class="tape"/>
          <g transform="translate(138 120) rotate(42)">
            <g class="pad"><rect x="-15" y="0" width="30" height="64" rx="10"/><rect x="-13" y="0" width="26" height="12" rx="6" class="knee"/>
              <rect x="-15" y="26" width="30" height="5" class="trim"/><rect x="-15" y="40" width="30" height="3" class="trim"/><path d="M-9 16 V60 M9 16 V60" class="seam"/></g>
            <rect x="-10" y="61" width="20" height="6" rx="3" class="skate"/>
          </g>
          <g transform="translate(166 120) rotate(-60)">
            <g class="pad"><rect x="-15" y="0" width="30" height="64" rx="10"/><rect x="-13" y="0" width="26" height="12" rx="6" class="knee"/>
              <rect x="-15" y="26" width="30" height="5" class="trim"/><rect x="-15" y="40" width="30" height="3" class="trim"/><path d="M-9 16 V60 M9 16 V60" class="seam"/></g>
            <rect x="-10" y="61" width="20" height="6" rx="3" class="skate"/>
          </g>
          <path d="M128 106 Q156 98 182 108 L184 128 Q156 138 126 128 Z" class="pants"/>
          <g transform="rotate(-8 156 96)">
            <path d="M130 84 L100 124" class="arm"/>
            <path d="M122 95 L115 105" class="armstripe"/>
            <path d="M184 82 L220 58" class="arm"/>
            <path d="M198 73 L206 67" class="armstripe"/>
            <path d="M112 80 Q152 68 192 80 L196 100 Q188 104 184 102 L183 118 Q152 122 121 118 L120 102 Q116 104 108 100 Z" class="jersey"/>
            <path d="M121 106 Q152 110 183 106 L183 113 Q152 117 121 113 Z" class="stripe"/>
            <circle cx="152" cy="92" r="8.5" class="crest"/>
            <text x="152" y="95.6" class="crestS">S</text>
            <rect x="80" y="116" width="24" height="34" rx="4" class="blocker"/>
            <rect x="83" y="120" width="18" height="26" rx="2" class="blockertrim"/>
            <path d="M214 58 C208 42 228 30 242 38 L250 56 C254 70 236 78 224 72 Z" class="glove"/>
            <path d="M220 52 C226 44 236 42 242 48 M222 62 C230 56 238 56 246 60" class="pocket"/>
            <rect x="210" y="58" width="12" height="12" rx="3" transform="rotate(-35 216 64)" class="cuff"/>
            <rect x="152" y="73" width="10" height="7" rx="2" class="throat"/>
            <circle cx="160" cy="60" r="16" class="helmet"/>
            <path d="M146 51 Q160 37 174 51" class="helmetstripe"/>
            <path d="M151 58 Q162 54 172 58 L171 71 Q162 79 152 71 Z" class="face"/>
            <path d="M155 57 V75 M159 56 V77 M165 56 V77 M169 57 V75 M151 62 H172 M152 67 H171 M153 72 H170" class="cage"/>
          </g>
        </g>

        <g class="pose pose-split">
          <path d="M92 138 L94 172" class="shaft"/>
          <path d="M88 168 L99 168 L101 185 L90 185 Z" class="paddle"/>
          <rect x="68" y="182" width="32" height="6" rx="2" class="blade"/>
          <g transform="translate(140 128) rotate(22)">
            <g class="pad"><rect x="-15" y="0" width="30" height="58" rx="10"/><rect x="-13" y="0" width="26" height="12" rx="6" class="knee"/>
              <rect x="-15" y="24" width="30" height="5" class="trim"/><rect x="-15" y="36" width="30" height="3" class="trim"/></g>
            <rect x="-10" y="55" width="20" height="6" rx="3" class="skate"/>
          </g>
          <g transform="translate(166 134) rotate(-80)">
            <g class="pad"><rect x="-15" y="0" width="30" height="66" rx="10"/><rect x="-13" y="0" width="26" height="12" rx="6" class="knee"/>
              <rect x="-15" y="26" width="30" height="5" class="trim"/><rect x="-15" y="40" width="30" height="3" class="trim"/><path d="M-9 16 V62 M9 16 V62" class="seam"/></g>
            <rect x="-10" y="63" width="20" height="6" rx="3" class="skate"/>
          </g>
          <path d="M128 116 Q154 108 180 118 L182 138 Q154 146 126 138 Z" class="pants"/>
          <g transform="translate(0 14) rotate(-8 152 100)">
            <path d="M128 86 L98 116" class="arm"/>
            <path d="M120 96 L112 104" class="armstripe"/>
            <path d="M178 84 L204 104" class="arm"/>
            <path d="M188 90 L195 97" class="armstripe"/>
            <path d="M112 80 Q152 68 192 80 L196 100 Q188 104 184 102 L183 118 Q152 122 121 118 L120 102 Q116 104 108 100 Z" class="jersey"/>
            <path d="M121 106 Q152 110 183 106 L183 113 Q152 117 121 113 Z" class="stripe"/>
            <circle cx="152" cy="92" r="8.5" class="crest"/>
            <text x="152" y="95.6" class="crestS">S</text>
            <rect x="80" y="104" width="24" height="34" rx="4" class="blocker"/>
            <rect x="83" y="108" width="18" height="26" rx="2" class="blockertrim"/>
            <path d="M196 96 C196 84 220 82 226 93 L230 113 C231 125 212 130 201 122 Z" class="glove"/>
            <path d="M202 100 C208 95 218 95 223 102 M203 109 C210 105 218 106 225 111" class="pocket"/>
            <rect x="148" y="73" width="10" height="7" rx="2" class="throat"/>
            <circle cx="156" cy="60" r="16" class="helmet"/>
            <path d="M142 51 Q156 37 170 51" class="helmetstripe"/>
            <path d="M146 58 Q157 54 167 58 L166 71 Q157 79 147 71 Z" class="face"/>
            <path d="M150 57 V75 M154 56 V77 M160 56 V77 M164 57 V75 M146 62 H167 M147 67 H166 M148 72 H165" class="cage"/>
          </g>
        </g>
       </g>
      </g>

      <g class="zones">
        <g class="zone" data-z="0"><circle cx="62" cy="52" r="17"/><circle cx="62" cy="52" r="3" class="dot"/></g>
        <g class="zone" data-z="1"><circle cx="238" cy="52" r="17"/><circle cx="238" cy="52" r="3" class="dot"/></g>
        <g class="zone" data-z="2"><circle cx="62" cy="140" r="17"/><circle cx="62" cy="140" r="3" class="dot"/></g>
        <g class="zone" data-z="3"><circle cx="238" cy="140" r="17"/><circle cx="238" cy="140" r="3" class="dot"/></g>
        <g class="zone" data-z="4"><circle cx="150" cy="172" r="12"/><circle cx="150" cy="172" r="2.5" class="dot"/></g>
      </g>

      <g id="shPuck" class="shpuck">
        <ellipse cx="150" cy="197" rx="11" ry="3.8" class="puckside"/>
        <rect x="139" y="192" width="22" height="5" class="puckside"/>
        <ellipse cx="150" cy="192" rx="11" ry="3.8" class="pucktop"/>
        <ellipse cx="146.5" cy="191.2" rx="4.5" ry="1.1" class="puckshine"/>
      </g>
    </svg>
    <p class="ttq" id="shQ"></p>
    <div class="shopts" id="shOpts"></div>
    <p class="hint" id="shMsg"></p>
    <div class="numrow"><button class="btn" id="shNext" type="button" hidden>Next shooter</button></div>
    <div class="slot"></div>
    <p class="nodata" hidden>This game isn't available right now.</p>
  </section>

  <section class="view" id="view-goalie" hidden>
    <div class="arc-hud"><div><small>Score</small><strong id="glScore">0</strong></div><div><small>Save streak</small><strong id="glStreak">0</strong></div><div><small>Goals allowed</small><strong id="glLives">0 / 3</strong></div></div>
    <div class="goalie-rink" id="glRink" aria-label="Defend the five areas of the net">
      <div class="goalie-net" aria-hidden="true"></div><div class="goalie-crease" aria-hidden="true"></div>
      <button type="button" class="goalie-zone" data-save="0" aria-label="Save top left" disabled><span>Top left</span><kbd>Q</kbd></button>
      <button type="button" class="goalie-zone" data-save="1" aria-label="Save top right" disabled><span>Top right</span><kbd>E</kbd></button>
      <button type="button" class="goalie-zone" data-save="2" aria-label="Save bottom left" disabled><span>Bottom left</span><kbd>Z</kbd></button>
      <button type="button" class="goalie-zone" data-save="3" aria-label="Save bottom right" disabled><span>Bottom right</span><kbd>C</kbd></button>
      <button type="button" class="goalie-zone" data-save="4" aria-label="Save five-hole" disabled><span>Five-hole</span><kbd>Space</kbd></button>
      <div class="goalie-status" id="glStatus" role="status">Own the crease.</div><div class="goalie-puck" id="glPuck" hidden></div>
      <div class="goalie-glove" id="glGlove" aria-hidden="true" hidden><svg viewBox="0 0 64 64" width="100%" height="100%"><path d="M18 53 8 31Q5 19 15 17L22 26 19 13Q18 5 25 5L33 7Q50 11 55 28L52 46 39 57Z" fill="currentColor" stroke="var(--bg)" stroke-width="2"/><path d="m25 18 18 5-2 17-12 5-7-12Z" fill="var(--bg)" opacity=".8"/><path d="m26 22 12 15m4-11-15 13M19 48l20 4" fill="none" stroke="var(--bg)" stroke-width="2"/></svg></div>
    </div>
    <div class="arc-controls"><button type="button" class="btn" id="glStart">Take the net</button><button type="button" class="btn ghost" id="glEnd" hidden>End run</button></div>
    <p class="arc-note">Watch the puck, then tap an area of the net to commit to a save. Three goals end your run. Every five consecutive saves builds your multiplier, up to 5×.</p>
    <p class="arc-note">Keyboard: Q / E for high shots, Z / C for low shots, Space for five-hole. Leaving or hiding the game ends a started run.</p>
    <div class="slot"></div><p class="nodata" hidden>This game is not available yet.</p>
  </section>
  <section class="view" id="view-overtime" hidden>
    <div class="arc-hud"><div><small>Time left</small><strong class="ot-time" id="otTime">0:30</strong></div><div><small>Right answers</small><strong id="otScore">0</strong></div><div><small>Streak</small><strong id="otStreak">0</strong></div></div>
    <div class="ot-meter" aria-hidden="true"><i id="otMeter"></i></div>
    <div class="ot-question" id="otQuestion"><small id="otRound">Sudden-death trivia</small><h3 id="otQ">Keep the clock alive.</h3></div>
    <div class="ot-answers" id="otAnswers"></div>
    <div class="arc-controls"><button type="button" class="btn" id="otStart">Start overtime</button><button type="button" class="btn ghost" id="otEnd" hidden>End run</button></div>
    <p class="arc-note" id="otFeedback" role="status">Start with 30 seconds. Right answers add 3 seconds; wrong answers cost 5.</p>
    <p class="arc-note">Keep up to 60 seconds on the clock. Clear all 100 questions for a perfect run. Use keys 1–4 or tap an answer. Leaving or hiding the game ends a started run.</p>
    <div class="slot"></div><p class="nodata" hidden>This game needs player data. Rebuild the site to load it.</p>
  </section>

  <section class="view" id="view-zam" hidden>
    <p class="intro">Drag across the ice to reveal the player, then guess who it is.</p>
    <div class="zambox"><img id="zmImg" alt="" draggable="false"><canvas id="zmIce" aria-label="Ice covering the photo. Drag to clear it."></canvas></div>
    <div class="search narrow">
      <input id="zmGuess" autocomplete="off" role="combobox" aria-expanded="false" aria-controls="zmOpts" placeholder="Guess 1 of 3">
      <ul class="list" id="zmOpts" role="listbox" hidden></ul>
    </div>
    <p class="hint" id="zmLeft"></p>
    <div class="slot"></div>
    <p class="nodata" hidden>This game isn't available right now.</p>
    <ul class="wrong" id="zmWrong"></ul>
  </section>

  <section class="view" id="view-party" hidden>
    <div id="ptBody"></div>
  </section>

  <section class="view" id="view-truths" hidden>
    <div class="shdots" id="twDots"></div>
    <div class="ttcard"><img id="twImg" alt=""><div><p class="pname" id="twName"></p><p class="pmeta">Two of these are true</p></div></div>
    <p class="ttq" id="twQ"></p>
    <div class="twlist" id="twList"></div>
    <p class="hint" id="twMsg"></p>
    <div class="numrow"><button class="btn" id="twNext" type="button" hidden>Next player</button></div>
    <div class="slot"></div>
    <p class="nodata" hidden>This game isn't available right now.</p>
  </section>

  <section class="view" id="view-hlt" hidden>
    <p class="intro" id="htIntro"></p>
    <div class="hlscore"><span>Streak<b id="htStreak">0</b></span><span>Best<b id="htBest">0</b></span></div>
    <div class="slot"></div>
    <p class="nodata" hidden>This game isn't available right now.</p>
    <div class="hlpair" id="htPair"><div id="htA"></div><div class="hlvs">VS</div><div id="htB"></div></div>
    <p class="hint" id="htLeft"></p>
  </section>

  <section class="view" id="view-season" hidden>
    <div class="ttcard"><img id="seImg" alt=""><div><p class="pname" id="seName"></p><p class="pmeta tmeta" id="seMeta"></p></div></div>
    <p class="ttq">Which season is this?</p>
    <div class="chips" id="seStats"></div>
    <div class="selist" id="seList"></div>
    <p class="hint" id="seLeft"></p>
    <div class="slot"></div>
    <p class="nodata" hidden>This game needs career stats. Rebuild the site to load them.</p>
  </section>

  <section class="view" id="view-playoff" hidden>
    <p class="intro" id="phIntro"></p>
    <p class="slhint" id="phHint" hidden></p>
    <div class="search narrow">
      <input id="phGuess" autocomplete="off" role="combobox" aria-expanded="false" aria-controls="phOpts" placeholder="Guess 1 of 6">
      <ul class="list" id="phOpts" role="listbox" hidden></ul>
    </div>
    <div class="slot"></div>
    <p class="nodata" hidden>This game needs playoff stats. Rebuild the site to load them.</p>
    <table class="seasons"><thead><tr id="phHead"></tr></thead><tbody id="phRows"></tbody></table>
    <p class="hint" id="phLeft"></p>
    <ul class="wrong" id="phWrong"></ul>
  </section>

  <section class="view" id="view-trophy" hidden>
    <div class="optrow"><label class="pickstat">Trophy
      <select id="trTrophy" aria-label="Trophy category"></select>
    </label><label class="pickstat">Questions
      <select id="trRounds" aria-label="Number of questions">
        <option value="5">5</option><option value="10">10</option><option value="15">15</option><option value="20">20</option>
      </select></label></div>
    <div class="shdots" id="trDots"></div>
    <p class="ttq" id="trQ"></p>
    <div class="shopts" id="trOpts"></div>
    <p class="hint" id="trMsg"></p>
    <div class="numrow"><button class="btn" id="trNext" type="button" hidden>Next trophy</button></div>
    <div class="slot"></div>
    <p class="nodata" hidden>This game needs trophy info. Rebuild the site to load it.</p>
  </section>

  <section class="view" id="view-mroster" hidden>
    <p class="intro">Which team do these players belong to?</p>
    <ul class="mrlist" id="mrList"></ul>
    <p class="hint" id="mrLeft"></p>
    <div class="slot"></div>
    <p class="nodata" hidden>This game isn't available right now.</p>
    <div class="divs" id="mrGrid"></div>
  </section>

  <section class="view" id="view-cups" hidden>
    <div class="cups-controls">
      <p class="intro">Stanley Cup winners, runners-up and Conn Smythe winners from 1980–81 through the latest Final. A team name or nickname works; players need a surname.</p>
      <div class="hlscore"><span>Time<b id="cuTime">10:00</b></span><span>Squares<b id="cuCount">0/0</b></span></div>
      <div class="numrow wide">
        <input id="cuInput" autocomplete="off" autocorrect="off" autocapitalize="words" spellcheck="false" enterkeyhint="send"
               placeholder="Press Start to begin" aria-label="Team or player name">
        <button class="btn" id="cuStart" type="button">Start</button>
      </div>
      <p class="hint romsg" id="cuMsg" aria-live="polite"></p>
    </div>
    <div class="cudecades" id="cuDecades" aria-label="Playoff History progress by decade"></div>
    <div class="slot"></div>
    <p class="nodata" hidden>This game needs playoff history. Rebuild the site to load it.</p>
    <div class="board cuboard">
      <table class="cutable">
        <thead><tr id="cuHead"></tr></thead>
        <tbody id="cuRows"></tbody>
      </table>
    </div>
  </section>

  <section class="view" id="view-team" hidden>
    <div class="ttcard">
      <img id="ttImg" alt="">
      <div><p class="pname" id="ttName"></p><p class="pmeta" id="ttMeta"></p></div>
    </div>
    <p class="ttq">Which team did he play for in <b id="ttSeason"></b>?</p>
    <div class="chips" id="ttStats"></div>
    <p class="hint" id="ttLeft"></p>
    <div class="slot"></div>
    <p class="nodata" hidden>This game needs career stats. Rebuild the site to load them.</p>
    <div class="divs" id="ttGrid"></div>
  </section>

  <footer class="foot"><span id="foot"></span>
    <small>Sweater is a fan-made game and is not affiliated with or endorsed by the NHL or its teams. NHL, team names, logos and player images are the property of the NHL and its teams.</small>
  </footer>
</main>

<div class="modal" id="modal" role="dialog" aria-modal="true" aria-labelledby="mTitle">
  <div class="card">
    <h2 id="mTitle">Who's this player?</h2>
    <div class="silbox"><img id="silImg" alt="Silhouette of the mystery player" draggable="false"></div>
  </div>
</div>

<div class="modal" id="statsModal" role="dialog" aria-modal="true" aria-labelledby="sTitle">
  <div class="card wide">
    <button class="xbtn" data-close aria-label="Close">×</button>
    <h2 id="sTitle">Statistics</h2>
    <select class="gamesel" id="stGameSel" aria-label="Game"></select>
    <div class="statgrid">
      <div><b id="stPlayed">0</b><span id="stL1">Played</span></div>
      <div><b id="stWin">0</b><span id="stL2">Win %</span></div>
      <div><b id="stStreak">0</b><span id="stL3">Current streak</span></div>
      <div><b id="stMax">0</b><span id="stL4">Max streak</span></div>
    </div>
    <h3 id="distTitle">Guess distribution</h3>
    <div id="dist"></div>
    <div class="statfoot">
      <div><small>Next player</small><b id="stNext">--:--:--</b></div>
      <button class="btn" id="shareBtn" type="button">Share</button>
    </div>
    <p class="stlb" id="stLb" hidden><span id="stLbText"></span> <button class="linkbtn" id="stLbBtn" type="button">See the leaderboard</button></p>
  </div>
</div>

<div class="modal" id="lbModal" role="dialog" aria-modal="true" aria-labelledby="lbTitle">
  <div class="card wide lbcard">
    <button class="xbtn" data-close aria-label="Close">×</button>
    <h2 id="lbTitle">Leaderboard</h2>
    <select class="gamesel" id="lbGameSel" aria-label="Game"></select>
    <div class="tabs small lbtabs" role="tablist" aria-label="Period">
      <button type="button" role="tab" data-period="today">Today</button>
      <button type="button" role="tab" data-period="week">This week</button>
      <button type="button" role="tab" data-period="all">All time</button>
    </div>
    <ol class="lb" id="lbList"></ol>
    <p class="hint" id="lbYou"></p>
    <div class="lbname" id="lbNameBox"></div>
    <p class="lbrules" id="lbRules"></p>
  </div>
</div>

<div class="modal" id="archiveModal" role="dialog" aria-modal="true" aria-labelledby="arTitle">
  <div class="card wide">
    <button class="xbtn" data-close aria-label="Close">×</button>
    <h2 id="arTitle">Archive</h2>
    <select class="gamesel" id="arGameSel" aria-label="Game"></select>
    <p class="hint">Replay past daily puzzles. Archive games don't count toward your stats or the leaderboard.</p>
    <ol class="arlist" id="arList"></ol>
  </div>
</div>

<div class="modal" id="helpModal" role="dialog" aria-modal="true" aria-labelledby="hTitle">
  <div class="card wide help">
    <button class="xbtn" data-close aria-label="Close">×</button>
    <h2 id="hTitle">How to play</h2>
    <p class="helpintro">Pick a game on the home screen. Every game has a new daily puzzle at midnight Eastern, the same for everyone.</p>

    <ul class="helpkeys">
      <li><span aria-hidden="true">📊</span>Your stats, and share today's result</li>
      <li class="lbhelp" hidden><span aria-hidden="true">🏆</span>Leaderboards and how each game scores</li>
      <li><span aria-hidden="true">📅</span>Replay past daily puzzles</li>
      <li><span class="keyswitch" aria-hidden="true"></span>Unlimited: play as many puzzles as you like</li>
      <li><span aria-hidden="true">🖌️</span>Choose your interface colour and appearance</li>
    </ul>

    <p class="colourkey">
      <span><i class="swatch" style="background:var(--hit)"></i>Right</span>
      <span><i class="swatch" style="background:var(--near)"></i>Close</span>
      <span><i class="swatch" style="background:var(--cell);box-shadow:inset 0 0 0 1px var(--line)"></i>No match</span>
    </p>

    <h3>Game rules</h3>
    <p class="helplead" id="helpLead" hidden></p>
    <div id="helpGames"></div>

    <p class="helpfoot"><b>Party Mode</b>: host on a screen everyone can see, and friends join on their phones with the 4-letter code. Questions are timed, and faster right answers score more.</p>
    <p class="helpfoot">Only daily puzzles count toward your stats and the leaderboard. Archive and Unlimited games are just for fun.</p>
    <p class="helpfoot">Inspired by Bradley Connolly with <a href="https://www.hertl.app/" target="_blank" rel="noopener">hertl.app</a> and the people at <a href="https://poeltl.nbpa.com/" target="_blank" rel="noopener">Poeltl</a>. Player data and headshots come from NHL.com, and trophy winners from <a href="https://en.wikipedia.org/" target="_blank" rel="noopener">Wikipedia</a>.</p>
  </div>
</div>

<div class="modal" id="settingsModal" role="dialog" aria-modal="true" aria-labelledby="setTitle">
  <div class="card settingscard">
    <button class="xbtn" data-close aria-label="Close">×</button>
    <p class="settingskicker">Appearance</p>
    <h2 id="setTitle">Make it yours</h2>
    <p class="settingsintro">Choose an interface colour. Answer feedback always stays green for right and red for wrong.</p>
    <div class="appearancechoice" id="appearanceChoice" role="group" aria-label="Appearance">
      <button type="button" data-theme-choice="dark"><span>●</span> Dark</button>
      <button type="button" data-theme-choice="light"><span>○</span> Light</button>
    </div>
    <div class="accentgrid" id="accentGrid" role="group" aria-label="Interface colour">
      <button type="button" class="accentchoice" data-accent="#242424"><i style="--swatch:#242424"></i><span>Neutral</span></button>
      <button type="button" class="accentchoice" data-accent="#2878d4"><i style="--swatch:#2878d4"></i><span>Blue</span></button>
      <button type="button" class="accentchoice" data-accent="#d04747"><i style="--swatch:#d04747"></i><span>Red</span></button>
      <button type="button" class="accentchoice" data-accent="#26875d"><i style="--swatch:#26875d"></i><span>Green</span></button>
      <button type="button" class="accentchoice" data-accent="#c99b24"><i style="--swatch:#c99b24"></i><span>Yellow</span></button>
      <button type="button" class="accentchoice" data-accent="#7950f2"><i style="--swatch:#7950f2"></i><span>Purple</span></button>
      <button type="button" class="accentchoice" data-accent="#d66b25"><i style="--swatch:#d66b25"></i><span>Orange</span></button>
      <button type="button" class="accentchoice" data-accent="#d35b91"><i style="--swatch:#d35b91"></i><span>Pink</span></button>
    </div>
    <label class="customaccent"><span><b>Custom colour</b><small>Choose any shade</small></span><input id="accentPicker" type="color" value="#7950f2" aria-label="Custom interface colour"></label>
  </div>
</div>

<div class="modal" id="profileModal" role="dialog" aria-modal="true" aria-labelledby="profileTitle">
  <div class="card wide lockercard">
    <button class="xbtn" data-close aria-label="Close">×</button>
    <p class="settingskicker">Your locker</p>
    <h2 id="profileTitle">Rink Rat</h2>
    <div id="profileHero"></div>
    <h3>Achievements</h3>
    <div class="achievementgrid" id="achievementGrid"></div>
    <h3>Keep going</h3>
    <p class="lockerhint" id="lockerHint"></p>
    <h3>Your bench</h3>
    <div class="lockerbench" id="lockerBench"></div>
  </div>
</div>

<div class="modal" id="welcomeModal" role="dialog" aria-modal="true" aria-labelledby="welcomeTitle">
  <div class="card wide welcomecard">
    <p class="settingskicker">Welcome to Sweater</p>
    <h2 id="welcomeTitle">Your daily hockey brain workout.</h2>
    <p class="settingsintro">Play the daily puzzles, build your level, unlock badges, and see how deep your hockey knowledge goes.</p>
    <div class="welcomeactions">
      <button type="button" class="btn" data-welcome-open="classic">Play today's Classic</button>
      <button type="button" class="btn ghost" data-welcome-library>Browse all games</button>
    </div>
    <button type="button" class="linkbtn welcomeskip" data-close>I'll explore on my own</button>
  </div>
</div>

<div class="toast" id="toast" role="status"></div>

<script>
// ======================= data (filled in by build_sweater.py) =======================
const PLAYERS = /*__PLAYERS__*/[].sort((a, b) => a.id - b.id);
const BUILT = "/*__BUILT__*/";
const SITE = "/*__SITE__*/";
const API = "/*__API__*/".replace(/\/+$/, "");
const API_ON = /^https?:\/\//.test(API);
const DAILY = /*__DAILY_ALL__*/{};   // game -> { "YYYY-MM-DD" (Eastern) -> puzzle }
const DAILY_HL = /*__DAILY_HL__*/{};
const CUP_ROWS = /*__CUPS__*/[];   // [year, champion, runner-up, Conn Smythe winner, Conn Smythe team]
const TROPHY_WINNERS = /*__TROPHIES__*/[];   // [trophy, season start year, winner, team at the time]
const START = /*__START_ALL__*/{};   // game -> date of Daily #1

// abbr: [conference, division]
const TEAMS = {
  BOS:["East","A"],BUF:["East","A"],DET:["East","A"],FLA:["East","A"],MTL:["East","A"],OTT:["East","A"],TBL:["East","A"],TOR:["East","A"],
  CAR:["East","M"],CBJ:["East","M"],NJD:["East","M"],NYI:["East","M"],NYR:["East","M"],PHI:["East","M"],PIT:["East","M"],WSH:["East","M"],
  CHI:["West","C"],COL:["West","C"],DAL:["West","C"],MIN:["West","C"],NSH:["West","C"],STL:["West","C"],UTA:["West","C"],WPG:["West","C"],
  ANA:["West","P"],CGY:["West","P"],EDM:["West","P"],LAK:["West","P"],SEA:["West","P"],SJS:["West","P"],VAN:["West","P"],VGK:["West","P"]
};
const TEAM_NAMES = {
  ANA:"Anaheim", BOS:"Boston", BUF:"Buffalo", CGY:"Calgary", CAR:"Carolina", CHI:"Chicago", COL:"Colorado",
  CBJ:"Columbus", DAL:"Dallas", DET:"Detroit", EDM:"Edmonton", FLA:"Florida", LAK:"Los Angeles", MIN:"Minnesota",
  MTL:"Montréal", NSH:"Nashville", NJD:"New Jersey", NYI:"NY Islanders", NYR:"NY Rangers", OTT:"Ottawa",
  PHI:"Philadelphia", PIT:"Pittsburgh", SJS:"San Jose", SEA:"Seattle", STL:"St. Louis", TBL:"Tampa Bay",
  TOR:"Toronto", UTA:"Utah", VAN:"Vancouver", VGK:"Vegas", WSH:"Washington", WPG:"Winnipeg"
};
const DIV_NAMES = { A: "Atlantic", M: "Metropolitan", C: "Central", P: "Pacific" };
const BYID = new Map(PLAYERS.map(p => [p.id, p]));
// NHL's current logo CDN deliberately omits retired franchise codes. Keep a
// focused archive map so historic trivia shows the proper mark instead of an
// empty image. These are rendered PNG previews of the corresponding crest.
const HISTORIC_LOGOS = Object.freeze({
  MNS: "https://thumb.wikimedia.org/wikipedia/en/thumb/5/56/Minnesota_North_Stars_Logo_2.svg/250px-Minnesota_North_Stars_Logo_2.svg.png",
  ATL: "https://thumb.wikimedia.org/wikipedia/en/thumb/0/02/Atlanta_Thrashers.svg/250px-Atlanta_Thrashers.svg.png",
  HFD: "https://thumb.wikimedia.org/wikipedia/commons/thumb/d/da/Hartford_Whalers_1992.svg/250px-Hartford_Whalers_1992.svg.png",
  QUE: "https://thumb.wikimedia.org/wikipedia/en/thumb/9/96/Quebec_Nordiques_Logo.svg/250px-Quebec_Nordiques_Logo.svg.png",
  AFM: "https://thumb.wikimedia.org/wikipedia/en/thumb/4/45/Atlanta_Flames_Logo.svg/250px-Atlanta_Flames_Logo.svg.png",
  CLR: "https://thumb.wikimedia.org/wikipedia/en/thumb/2/24/Colorado_Rockies_%28NHL%29_logo.svg/250px-Colorado_Rockies_%28NHL%29_logo.svg.png",
  ARI: "https://thumb.wikimedia.org/wikipedia/en/thumb/9/9e/Arizona_Coyotes_logo_%282021%29.svg/250px-Arizona_Coyotes_logo_%282021%29.svg.png",
  PHX: "https://thumb.wikimedia.org/wikipedia/en/thumb/9/9e/Arizona_Coyotes_logo_%282021%29.svg/250px-Arizona_Coyotes_logo_%282021%29.svg.png",
  KCS: "https://thumb.wikimedia.org/wikipedia/en/thumb/7/74/Kansas_City_Scouts_logo.svg/250px-Kansas_City_Scouts_logo.svg.png",
  CGS: "https://thumb.wikimedia.org/wikipedia/en/thumb/1/17/California_Golden_Seals_Logo.svg/250px-California_Golden_Seals_Logo.svg.png",
  OAK: "https://thumb.wikimedia.org/wikipedia/en/thumb/1/17/California_Golden_Seals_Logo.svg/250px-California_Golden_Seals_Logo.svg.png",
  CLE: "https://thumb.wikimedia.org/wikipedia/en/thumb/7/7b/Cleveland_Barons_%28NHL%29_logo.svg/250px-Cleveland_Barons_%28NHL%29_logo.svg.png",
});
const logo = t => HISTORIC_LOGOS[t] || `https://assets.nhle.com/logos/nhl/svg/${t}_light.svg`;
// Navy/royal crests need a little more lift on the contrast theme's black surfaces.
const BLUE_LOGO_TEAMS = new Set(["ATL", "BUF", "CBJ", "COL", "EDM", "HFD", "MTL", "NYI", "NYR", "QUE", "SEA", "STL", "TBL", "TOR", "UTA", "VAN", "WPG"]);
const logoToneClass = t => BLUE_LOGO_TEAMS.has(t) ? " logo-blue" : "";
const FALLBACK = "data:image/svg+xml," + encodeURIComponent(
  `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><circle cx='50' cy='38' r='20'/><path d='M12 100c2-26 18-38 38-38s36 12 38 38z'/></svg>`);

// ======================= helpers =======================
const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
// One stroke-based icon family keeps navigation and game identities consistent.
const UI_ICONS = {
  chart: '<path d="M5 20V13M12 20V4M19 20V9"/>',
  trophy: '<path d="M8 3h8v6a4 4 0 0 1-8 0V3ZM8 5H4v3a4 4 0 0 0 4 4m8-7h4v3a4 4 0 0 1-4 4M12 13v6m-4 2h8m-6-2h4"/>',
  calendar: '<rect x="3" y="5" width="18" height="16" rx="3"/><path d="M7 3v4m10-4v4M3 11h18m-14 4h2m6 0h2m-10 3h2"/>',
  help: '<circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.5 2.5 0 1 1 4 2c-1 .7-1.5 1-1.5 2M12 16h.01"/>',
  star: '<path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2-5.6-3-5.6 3 1.1-6.2L3 9.6l6.2-.9L12 3Z"/>',
  brush: '<path d="m14 12 6-6a2.1 2.1 0 0 0-3-3l-6 6 3 3ZM11 9l-2 3 3 3 2-3M9 12c-4 0-2 6-6 7 5 2 10-1 9-4"/>',
  stick: '<path d="m17 3-7 14H4a2 2 0 0 0 0 4h8L21 3m-6 4 4 2"/>',
  route: '<circle cx="5" cy="5" r="2"/><circle cx="19" cy="19" r="2"/><path d="M7 5h9a4 4 0 0 1 0 8H8a3 3 0 0 0 0 6h9"/>',
  search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
  ice: '<path d="m12 3 9 5v8l-9 5-9-5V8l9-5Zm0 10 9-5m-9 5L3 8m9 5v8"/>',
  shield: '<path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6l8-3Z"/>',
  shirt: '<path d="m8 3-5 3-2 5 5 2v8h12v-8l5-2-2-5-5-3c0 4-8 4-8 0Z"/>',
  draft: '<rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 3h6v4H9V3Zm0 8h6m-6 4h6"/>',
  pin: '<path d="M19 10c0 5-7 11-7 11S5 15 5 10a7 7 0 0 1 14 0Z"/><circle cx="12" cy="10" r="2"/>',
  arrows: '<path d="M8 20V4L4 8m4-4 4 4m4-4v16l-4-4m4 4 4-4"/>',
  rank: '<path d="M3 20v-7h6v7m0 0V5h6v15m0 0V9h6v11M2 20h20"/>',
  clock: '<circle cx="12" cy="13" r="8"/><path d="M12 9v4l3 2M9 2h6m-3 0v3"/>',
  grid: '<rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/>',
  target: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',
  net: '<path d="M3 20V6a3 3 0 0 1 3-3h12a3 3 0 0 1 3 3v14M3 9h18M3 15h18M9 3v17m6-17v17M3 20h18"/>',
  people: '<circle cx="9" cy="7" r="3"/><path d="M3 21v-3a6 6 0 0 1 12 0v3M16 4a3 3 0 0 1 0 6m2 5a5 5 0 0 1 3 5"/>',
};
const uiIcon = name => `<svg class="ui-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${UI_ICONS[name] || UI_ICONS.stick}</svg>`;
const MODE_ICONS = { classic: "stick", statline: "chart", playoff: "trophy", journey: "route", blur: "search", zam: "ice", team: "shield", number: "shirt", draft: "draft", season: "calendar", trophy: "trophy", cups: "trophy", mroster: "people", map: "pin", hl: "arrows", rank: "rank", hlt: "shield", truths: "search", roster: "clock", conn: "grid", puck: "target", shoot: "net" };
MODE_ICONS.goalie = "shield";
MODE_ICONS.overtime = "clock";
const modeIcon = id => uiIcon(MODE_ICONS[id.startsWith("hl_") ? "hl" : id]);
Object.entries({ statsBtn: "chart", lbBtn: "trophy", archiveBtn: "calendar", helpBtn: "help", profileBtn: "star", settingsBtn: "brush" }).forEach(([id, name]) => { $(id).innerHTML = uiIcon(name); });
const norm = s => s.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
const pick = arr => arr[Math.floor(Math.random() * arr.length)];
const ageOf = bd => {
  const b = new Date(bd), n = new Date();
  let a = n.getFullYear() - b.getFullYear();
  if (n.getMonth() < b.getMonth() || (n.getMonth() === b.getMonth() && n.getDate() < b.getDate())) a--;
  return a;
};
const store = {
  get(k) { try { return JSON.parse(localStorage.getItem(k)); } catch { return null; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch {} }
};
const posName = p => p.pos === "G" ? "Goalie" : p.pos === "D" ? "Defenceman" : "Forward";
const seasonLabel = y => `${y}–${String((y + 1) % 100).padStart(2, "0")}`;
function hash(str) { // FNV-1a
  let h = 2166136261;
  for (const c of str) { h ^= c.charCodeAt(0); h = Math.imul(h, 16777619); }
  return h >>> 0;
}

// ---- dates: everyone switches at midnight Eastern ----
const ET_FMT = new Intl.DateTimeFormat("en-CA", { timeZone: "America/New_York", year: "numeric",
  month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23" });
function etParts(d = new Date()) {
  const o = {};
  for (const part of ET_FMT.formatToParts(d)) o[part.type] = part.value;
  return o;
}
const dayKey = (d = new Date()) => { const o = etParts(d); return `${o.year}-${o.month}-${o.day}`; };
const keyUTC = k => { const [y, m, d] = k.split("-").map(Number); return Date.UTC(y, m - 1, d); };
const shiftKey = (k, n) => new Date(keyUTC(k) + n * 864e5).toISOString().slice(0, 10);
const prevDayKey = k => shiftKey(k, -1);
const secondsToEtMidnight = () => {
  const o = etParts();
  return Math.max(0, 86400 - (Number(o.hour) * 3600 + Number(o.minute) * 60 + Number(o.second)));
};
const validStart = s => typeof s === "string" && /^\d{4}-\d\d-\d\d$/.test(s);
const startOf = g => START[g.startsWith("hl_") ? "hl" : g];
["classic", "statline", "team", "journey", "blur", "number", "roster", "draft", "map", "conn", "rank", "puck",
 "shoot", "goalie", "overtime", "zam", "truths", "hlt", "season", "playoff", "trophy", "mroster", "cups"].forEach(g => { DAILY[g] = DAILY[g] || {}; });
const dailyNumber = (g, k) => Math.round((keyUTC(k) - keyUTC(validStart(startOf(g)) ? startOf(g) : k)) / 864e5) + 1;

// ---- career stats: rows are [season start year, team, GP, G|W, A|GAA, PTS|SV%] ----
const seasonCache = new Map();
function seasonsOf(p) {
  if (seasonCache.has(p.id)) return seasonCache.get(p.id);
  const goalie = p.pos === "G", bySeason = new Map();
  for (const [y, t, gp, a, b, c, d = 0, e = 0] of (p.car || [])) {
    const r = bySeason.get(y) || { y, teams: [], gp: 0, a: 0, b: 0, c: 0, d: 0, e: 0 };
    r.teams.push(t);
    const total = r.gp + gp;
    if (goalie) {   // wins add up; GAA and SV% are weighted by games played
      r.b = total ? (r.b * r.gp + b * gp) / total : 0;
      r.c = total ? (r.c * r.gp + c * gp) / total : 0;
      r.a += a; r.d += d;   // wins, shutouts
    } else { r.a += a; r.b += b; r.c += c; r.d += d; r.e += e; }
    r.gp = total;
    bySeason.set(y, r);
  }
  const rows = [...bySeason.values()].sort((x, y) => x.y - y.y);
  seasonCache.set(p.id, rows);
  return rows;
}
// seasons for "guess the team": one team all season, not his current team, 10+ games
const teamSeasonsOf = p => seasonsOf(p).filter(r =>
  r.teams.length === 1 && TEAMS[r.teams[0]] && r.teams[0] !== p.team && r.gp >= 10);
const signed = v => v > 0 ? `+${v}` : v < 0 ? `−${Math.abs(v)}` : "0";
const statCells = (p, r) => p.pos === "G"
  ? [r.gp, r.a, r.b.toFixed(2), r.c.toFixed(3).replace(/^0/, ""), r.d]
  : [r.gp, r.a, r.b, r.c, signed(r.e)];
const statHeads = p => p.pos === "G" ? ["GP", "W", "GAA", "SV%", "SO"] : ["GP", "G", "A", "PTS", "+/−"];
const HINT_AT = 4;   // wrong guesses before the team-logo hint in "guess the player"

const SL_POOL = PLAYERS.filter(p => seasonsOf(p).length >= 3);
const TT_POOL = PLAYERS.filter(p => teamSeasonsOf(p).length);

// ======================= the three games =======================
const CLOSE = 2; // age / number within this many counts as close (yellow)
const numState = (g, t) => g === t ? true : Math.abs(g - t) <= CLOSE ? "near" : false;
const sq = v => v === true ? "🟩" : v === "near" ? "🟨" : "⬛";

const G = {
  classic: {
    title: "Classic", share: "Sweater", view: "view-classic", max: 8, next: "Next player",
    cheers: ["Top shelf, first try! 🥅", "Snipe! 🎯", "Hat trick! 🎩", "Nice dangle! 🏒",
             "Five-hole! 🙌", "Solid shift! 💪", "Clutch! ⏱️", "Buzzer beater! 🚨"],
    pool: () => PLAYERS,
    daily: k => BYID.get(DAILY.classic[k]) || PLAYERS[hash("sweater-" + k) % PLAYERS.length],
    random: () => pick(PLAYERS),
    tid: t => t.id,
    player: t => t,
    meta: t => `${t.team} · #${t.number} · ${t.pos}`,
    isWin: (t, id) => id === t.id,
    reset(t) {
      $("rows").innerHTML = "";
      $("silImg").onerror = function () { this.onerror = null; this.src = FALLBACK; };
      $("silImg").src = t.headshot || FALLBACK;
    },
    guess(t, id) {
      const p = BYID.get(id);
      if (!p) return null;
      addClassicRow(p, t);
      return p.id === t.id;
    },
    squares(t, id) {
      const p = BYID.get(id); if (!p) return "";
      const [pc, pd] = TEAMS[p.team] || [], [tc, td] = TEAMS[t.team] || [];
      return [
        p.team === t.team ? true : (t.past || []).includes(p.team) ? "near" : false,
        pc === tc, pd === td, p.pos === t.pos, p.shoots === t.shoots,
        numState(ageOf(p.birth), ageOf(t.birth)), p.nation === t.nation, numState(p.number, t.number)
      ].map(sq).join("") + "\n";
    }
  },

  statline: {
    title: "Stat Line", share: "Sweater Stat Line", view: "view-statline", max: 8, next: "Next player",
    cheers: ["Stat nerd, first try! 🤓", "Snipe! 🎯", "Hat trick! 🎩", "Nice read! 🧠",
             "Got there! 🙌", "Solid shift! 💪", "Clutch! ⏱️", "Buzzer beater! 🚨"],
    pool: () => SL_POOL,
    daily(k) {
      const p = BYID.get(DAILY.statline[k]);
      return p && seasonsOf(p).length >= 3 ? p : SL_POOL[hash("sweater-sl-" + k) % SL_POOL.length];
    },
    random: () => pick(SL_POOL),
    tid: t => t.id,
    player: t => t,
    meta: t => `${t.team} · #${t.number} · ${posName(t)}`,
    isWin: (t, id) => id === t.id,
    reset() { $("slWrong").innerHTML = ""; this.shown = 0; },
    guess(t, id) {
      const p = BYID.get(id);
      if (!p) return null;
      if (p.id !== t.id) {
        const li = document.createElement("li");
        li.className = "newrow";
        li.innerHTML = `<span class="x">✕</span><span></span><small>${esc(p.team)} · ${esc(p.pos)}</small>`;
        li.children[1].textContent = p.name;
        $("slWrong").prepend(li);
      }
      return p.id === t.id;
    },
    render(t, st) {
      const all = seasonsOf(t), newest = (st.opts || {}).order === "newest";
      const rows = newest ? all.slice().reverse() : all;
      const wrong = st.guesses.filter(id => id !== t.id).length;
      const shown = st.over ? rows.length : Math.min(rows.length, 1 + wrong);
      $("slIntro").textContent =
        `${posName(t)} · ${all.length} NHL seasons · ${seasonLabel(all[0].y)} to ${seasonLabel(all[all.length - 1].y)}`;
      const hint = !st.over && wrong >= HINT_AT;
      $("slHint").hidden = !hint;
      if (hint) $("slHint").innerHTML = `Hint: he plays for <img src="${logo(t.team)}" alt="" onerror="this.remove()"><b>${esc(TEAM_NAMES[t.team] || t.team)}</b> now`;
      $("slHead").innerHTML = `<th>Season</th>${statHeads(t).map(h => `<th>${h}</th>`).join("")}` +
        (st.over ? "<th>Team</th>" : "");
      $("slRows").innerHTML = rows.map((r, i) => {
        if (i >= shown) return `<tr class="locked"><td>${seasonLabel(r.y)}</td><td colspan="${statHeads(t).length}">🔒 Locked</td></tr>`;
        const cls = i >= (this.shown || 0) && this.shown ? ' class="newrow"' : "";
        return `<tr${cls}><td>${seasonLabel(r.y)}</td>${statCells(t, r).map(v => `<td>${v}</td>`).join("")}` +
          (st.over ? `<td>${r.teams.map(esc).join(" / ")}</td>` : "") + "</tr>";
      }).join("");
      $("slLeft").textContent = st.over ? "" :
        (shown < rows.length ? `Each wrong guess unlocks the next ${newest ? "older" : ""} season.`.replace("  ", " ") : "Every season is unlocked.")
        + (wrong < HINT_AT ? ` A team hint unlocks after ${HINT_AT} wrong guesses.` : "");
      this.shown = shown;
    },
    squares: (t, id) => id === t.id ? "🟩" : "⬛"
  },

  team: {
    title: "Guess the team", share: "Sweater Team", view: "view-team", max: 5, next: "Next puzzle",
    cheers: ["Bang on! 🎯", "Nice read! 🧠", "Solid work! 🏒", "Got there! 💪", "Last chance, nailed it! 🚨"],
    pool: () => TT_POOL,
    daily(k) {
      const [id, y] = DAILY.team[k] || [];
      const p = BYID.get(id), r = p && seasonsOf(p).find(s => s.y === y && s.teams.length === 1 && TEAMS[s.teams[0]]);
      if (r) return { p, r, team: r.teams[0] };
      const q = TT_POOL[hash("sweater-tt-" + k) % TT_POOL.length], opts = teamSeasonsOf(q);
      const s = opts[hash("season-" + k) % opts.length];
      return { p: q, r: s, team: s.teams[0] };
    },
    random() { const p = pick(TT_POOL), r = pick(teamSeasonsOf(p)); return { p, r, team: r.teams[0] }; },
    tid: t => `${t.p.id}:${t.r.y}`,
    player: t => t.p,
    meta: t => `Played for ${TEAM_NAMES[t.team]} (${t.team}) in ${seasonLabel(t.r.y)}`,
    isWin: (t, abbr) => abbr === t.team,
    reset(t) {
      const p = t.p;
      $("ttImg").onerror = function () { this.onerror = null; this.src = FALLBACK; };
      $("ttImg").src = p.headshot || FALLBACK;
      $("ttImg").alt = p.name;
      $("ttName").textContent = p.name;
      $("ttMeta").textContent = `${posName(p)} · born ${p.nation}`;
      $("ttSeason").textContent = seasonLabel(t.r.y);
      $("ttStats").innerHTML = statHeads(p).map((h, i) =>
        `<span class="chip"><b>${statCells(p, t.r)[i]}</b> ${h}</span>`).join("");
      $("ttGrid").innerHTML = Object.entries(DIV_NAMES).map(([d, name]) =>
        `<div><h4>${name}</h4>${Object.keys(TEAMS).filter(a => TEAMS[a][1] === d)
          .sort((a, b) => TEAM_NAMES[a].localeCompare(TEAM_NAMES[b]))
          .map(a => `<button class="teambtn" type="button" data-team="${a}"><img alt="" src="${logo(a)}" onerror="this.style.visibility='hidden'"><span>${TEAM_NAMES[a]}</span></button>`).join("")}</div>`
      ).join("");
    },
    state: (t, abbr) => abbr === t.team ? true : TEAMS[abbr][1] === TEAMS[t.team][1] ? "near" : false,
    guess(t, abbr) {
      if (!TEAMS[abbr]) return null;
      const b = $("ttGrid").querySelector(`[data-team="${abbr}"]`);
      const s = this.state(t, abbr);
      b.classList.add(s === true ? "hit" : s === "near" ? "near" : "miss");
      return s === true;
    },
    render(t, st) {
      $("ttGrid").querySelectorAll(".teambtn").forEach(b => {
        b.disabled = st.over || st.guesses.includes(b.dataset.team);
        if (st.over && b.dataset.team === t.team) b.classList.add("hit");
      });
      const left = this.max - st.guesses.length;
      $("ttLeft").textContent = st.over ? "" : `${left} ${left === 1 ? "try" : "tries"} left · yellow means same division`;
    },
    squares(t, abbr) { return sq(this.state(t, abbr)); }
  }
};

// ======================= higher or lower =======================
const HL_STATS = {
  goals:   { type: "high", key: "a", name: "Goals",   label: "goals",           one: "goal" },
  assists: { type: "high", key: "b", name: "Assists", label: "assists",         one: "assist" },
  points:  { type: "high", key: "c", name: "Points",  label: "points",          one: "point" },
  pim:     { type: "high", key: "d", name: "PIM",     label: "penalty minutes", one: "penalty minute" },
  gp:      { type: "gp",     name: "Games",  q: "Who has played more NHL regular-season games?", prompt: "career NHL games:", up: "More", down: "Fewer" },
  height:  { type: "height", name: "Height", q: "Who is taller?",  prompt: "height:", up: "Taller",  down: "Shorter" },
  weight:  { type: "weight", name: "Weight", q: "Who is heavier?", prompt: "weight:", up: "Heavier", down: "Lighter" },
  age:     { type: "age",    name: "Age",    q: "Who is older?",   prompt: "age:",    up: "Older",   down: "Younger" },
};
const niceBirth = b => { const [y, m, d] = String(b).split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" }); };
const HL_LEN = 40;   // answers in a daily run
const HL_POOL = PLAYERS.filter(p => p.pos !== "G" && seasonsOf(p).reduce((n, r) => n + r.gp, 0) >= 100);
const highCache = new Map();
// v: the number compared; show/unit/sub: how it's displayed
function hlValue(p, stat) {
  const k = `${p.id}:${stat}`;
  if (highCache.has(k)) return highCache.get(k);
  const info = HL_STATS[stat];
  let out;
  if (info.type === "high") {
    let best = { v: 0, y: null };
    for (const r of seasonsOf(p)) {
      const v = r[info.key] || 0;
      if (best.y === null || v > best.v) best = { v, y: r.y };
    }
    const unit = best.v === 1 ? info.one : info.label;
    out = { v: best.v, show: best.v, num: true, unit: `career-high ${unit}`, sub: best.y ? `in ${seasonLabel(best.y)}` : "",
            meta: `Career high: ${best.v} ${unit}${best.y ? ` in ${seasonLabel(best.y)}` : ""}` };
  } else if (info.type === "gp") {
    const v = seasonsOf(p).reduce((n, r) => n + r.gp, 0);
    out = { v, show: v, num: true, unit: v === 1 ? "career NHL game" : "career NHL games", sub: "regular season", meta: `${v} career NHL games` };
  } else if (info.type === "height") {
    const v = p.ht || 0, show = v ? `${Math.floor(v / 12)}′${v % 12}″` : "?";
    out = { v, show, num: false, unit: "tall", sub: v ? `${Math.round(v * 2.54)} cm` : "", meta: `${show} tall` };
  } else if (info.type === "weight") {
    const v = p.wt || 0;
    out = { v, show: v, num: true, unit: "lbs", sub: v ? `${Math.round(v * 0.4536)} kg` : "", meta: `${v} lbs` };
  } else {
    const a = ageOf(p.birth);   // older = earlier birthday, so compare birth dates
    out = { v: -Number(String(p.birth).replace(/-/g, "")), show: a, num: true, unit: "years old",
            sub: `born ${niceBirth(p.birth)}`, meta: `${a} years old (born ${niceBirth(p.birth)})` };
  }
  highCache.set(k, out);
  return out;
}
function seeded(seed) {   // small deterministic random generator
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6D2B79F5) >>> 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
function hlExtend(seq, stat, rnd = Math.random) {
  const used = new Set(seq.map(p => p.id));
  for (let i = 0; i < 60; i++) {
    const c = HL_POOL[Math.floor(rnd() * HL_POOL.length)];
    if (used.has(c.id) && used.size < HL_POOL.length) continue;
    if (seq.length && i < 59 && hlValue(c, stat).v === hlValue(seq[seq.length - 1], stat).v) continue;
    seq.push(c);
    return;
  }
  seq.push(HL_POOL[Math.floor(rnd() * HL_POOL.length)]);
}

let hlTimer = null;
function makeHL(stat) {
  const info = HL_STATS[stat], id = `hl_${stat}`;
  return {
    kind: "streak", stat, repeat: true,
    title: `Higher or Lower · ${info.name}`, share: "Sweater Higher or Lower",
    view: "view-hl", max: HL_LEN, next: "Play again",
    pool: () => HL_POOL,
    daily(k) {
      const ids = (DAILY_HL[k] || {})[stat] || [];
      const seq = ids.map(i => BYID.get(i)).filter(Boolean);
      if (seq.length >= 2 && seq.length === ids.length) return { seq, fixed: true };
      const rnd = seeded(hash(`sweater-hl-${stat}-${k}`)), s = [];
      while (s.length < HL_LEN + 1) hlExtend(s, stat, rnd);
      return { seq: s, fixed: true };
    },
    random() { const seq = []; hlExtend(seq, stat); hlExtend(seq, stat); return { seq, fixed: false, rid: Math.random() }; },
    tid: t => t.fixed ? `${stat}:${t.seq.slice(0, 4).map(p => p.id).join(",")}` : `${stat}:${t.rid}`,
    limit: t => t.fixed ? t.seq.length - 1 : Infinity,
    correct(t, i, ans) {
      const a = hlValue(t.seq[i], stat).v, b = hlValue(t.seq[i + 1], stat).v;
      return ans === "H" ? b >= a : b <= a;   // ties count either way
    },
    score(t, guesses) { let n = 0; for (const [i, x] of guesses.entries()) { if (!this.correct(t, i, x)) break; n++; } return n; },
    isWin: () => false,
    isDone(t, guesses) { return guesses.some((x, i) => !this.correct(t, i, x)) || guesses.length >= this.limit(t); },
    wonGame(t, guesses) { return guesses.length >= this.limit(t) && this.score(t, guesses) === guesses.length; },
    player(t) { return t.seq[Math.min(S[id].guesses.length, t.seq.length - 1)]; },
    meta(t) { return hlValue(this.player(t), stat).meta; },
    endText(t, guesses, won) {
      const n = this.score(t, guesses);
      return {
        result: won ? `Perfect! All ${n} right` : `Streak: ${n}`,
        cheer: won ? "Flawless run! 🏆" : n >= 20 ? "Legendary run! 🔥" : n >= 10 ? "Hot streak! 🔥"
          : n >= 5 ? "Nice run! 💪" : n >= 1 ? "Good start! 🏒" : "Tough one! This player got you:"
      };
    },
    celebrate(t, guesses, won) { return won || this.score(t, guesses) >= 10; },
    onFinish(st) {
      const n = this.score(st.target, st.guesses), k = `sweater-hl-best-${stat}`;
      if (n > (store.get(k) || 0)) store.set(k, n);
    },
    reset() { clearTimeout(hlTimer); this.pending = false; },
    card(p, side, reveal, state) {
      const h = hlValue(p, stat);
      const other = side === "b" ? S[id].target.seq[Math.min(S[id].guesses.length, S[id].target.seq.length - 2)] : null;
      return `<div class="hlcard ${state || ""}">
        <img class="hlimg" src="${esc(p.headshot || FALLBACK)}" alt="" onerror="this.onerror=null;this.src=FALLBACK">
        <p class="hlname">${esc(p.name)}</p>
        <p class="hlteam"><img src="${logo(p.team)}" alt="" onerror="this.remove()">${esc(p.team)} · ${esc(p.pos)}</p>
        ${reveal
          ? `<p class="hlval"><b${h.num ? ` data-count="${h.show}"` : ""}>${h.show}</b></p><p class="hlunit">${h.unit}</p><p class="hlyr">${esc(h.sub)}</p>`
          : `<p class="hlunit">${info.type === "high" ? `career-high ${info.label}:` : info.prompt}</p>
             <div class="hlbtns"><button class="btn hlbtn" type="button" data-hl="H">▲ ${info.up || "Higher"}</button>
             <button class="btn hlbtn" type="button" data-hl="L">▼ ${info.down || "Lower"}</button></div>
             <p class="hlyr">than ${esc(other ? other.name : "")}</p>`}
      </div>`;
    },
    guess(t, x, fresh) {
      if (x !== "H" && x !== "L") return null;
      const i = S[id].guesses.length;
      if (i + 1 >= t.seq.length) return null;
      const ok = this.correct(t, i, x);
      if (fresh) {
        this.pending = true;
        $("hlB").innerHTML = this.card(t.seq[i + 1], "b", true, ok ? "ok" : "bad");
        countUp($("hlB").querySelector("[data-count]"));
        clearTimeout(hlTimer);
        hlTimer = setTimeout(() => {
          this.pending = false;
          if (game === id) this.render(t, S[id], true);
        }, ok ? 1100 : 1400);
      }
      return ok;
    },
    render(t, st, slide = false) {
      if (this.pending) return;
      $("hlIntro").innerHTML = info.type === "high" ? `Whose career-high <b>${info.label}</b> in a single season is higher?` : esc(info.q);
      $("hlNote").textContent = info.type === "high" ? "Career high means his best single regular season. Ties count as right." : "Ties count as right.";
      $("hlStat").textContent = info.name;
      $("hlStreak").textContent = this.score(t, st.guesses);
      $("hlBest").textContent = Math.max(store.get(`sweater-hl-best-${stat}`) || 0, this.score(t, st.guesses));
      $("hlLeft").textContent = t.fixed ? `${Math.max(0, this.limit(t) - st.guesses.length)} left in today's run` : "";
      let i;
      if (st.over) i = Math.max(0, Math.min(st.guesses.length, t.seq.length - 1) - 1);
      else {
        i = st.guesses.length;
        while (!t.fixed && t.seq.length < i + 2) hlExtend(t.seq, stat);
      }
      const lastOk = st.over && st.guesses.length ? this.correct(t, st.guesses.length - 1, st.guesses[st.guesses.length - 1]) : null;
      $("hlA").innerHTML = this.card(t.seq[i], "a", true, "");
      $("hlB").innerHTML = this.card(t.seq[i + 1], "b", st.over, st.over ? (lastOk ? "ok" : "bad") : "");
      if (slide) { $("hlPair").classList.remove("slide"); void $("hlPair").offsetWidth; $("hlPair").classList.add("slide"); }
    },
    squares(t, x, i) { return this.correct(t, i, x) ? "🟩" : "🟥"; }
  };
}
Object.keys(HL_STATS).forEach(s => { G[`hl_${s}`] = makeHL(s); });

function countUp(el) {
  if (!el) return;
  const end = Number(el.dataset.count);
  if (matchMedia("(prefers-reduced-motion: reduce)").matches || end <= 0) return;
  const t0 = performance.now();
  (function step(t) {
    const k = Math.min(1, (t - t0) / 600);
    el.textContent = Math.round(end * (1 - Math.pow(1 - k, 3)));
    if (k < 1) requestAnimationFrame(step);
  })(t0);
}

// ======================= more games: journey, blur, sweater number, roster =======================
Object.assign(TEAM_NAMES, {
  ARI: "Arizona Coyotes", PHX: "Phoenix Coyotes", ATL: "Atlanta Thrashers", MNS: "Minnesota North Stars",
  HFD: "Hartford Whalers", QUE: "Quebec Nordiques", AFM: "Atlanta Flames", CLR: "Colorado Rockies",
  KCS: "Kansas City Scouts", CGS: "California Golden Seals", OAK: "Oakland Seals", CLE: "Cleveland Barons",
});
const KNOWN_TEAMS = new Set([...Object.keys(TEAMS), "ARI", "PHX", "ATL", "MNS", "HFD", "QUE", "AFM", "CLR", "KCS", "CGS", "OAK", "CLE"]);
const isMoreGame = g => ["journey", "blur", "number", "roster", "draft", "map", "conn", "rank", "puck", "shoot",
                         "zam", "truths", "hlt", "season", "playoff", "trophy", "mroster", "cups"].includes(g);
const spanLabel = (a, b) => `${a}–${String((b + 1) % 100).padStart(2, "0")}`;
const teamName = t => TEAM_NAMES[t] || t;

function addWrong(listId, p) {
  const li = document.createElement("li");
  li.className = "newrow";
  li.innerHTML = `<span class="x">✕</span><span></span><small>${esc(p.team)} · ${esc(p.pos)}</small>`;
  li.children[1].textContent = p.name;
  $(listId).prepend(li);
}
function hintChips(elId, hints, wrong, over) {
  $(elId).innerHTML = over ? "" : hints.filter(h => wrong >= h.at).map(h => `<span class="chip hintchip">${h.html}</span>`).join("");
  const next = hints.find(h => wrong < h.at);
  return over || !next ? "" : ` Next hint after ${next.at - wrong} more wrong ${next.at - wrong === 1 ? "guess" : "guesses"}.`;
}

// ---- Journey: guess the player from his career path ----
const stintCache = new Map();
function stintsOf(p) {
  if (stintCache.has(p.id)) return stintCache.get(p.id);
  const out = [];
  for (const [y, t, gp] of (p.car || [])) {
    const last = out[out.length - 1];
    if (last && last.team === t) { last.to = y; last.gp += gp; }
    else out.push({ team: t, from: y, to: y, gp });
  }
  stintCache.set(p.id, out);
  return out;
}
const journeyOk = p => {
  const s = stintsOf(p);
  return s.length >= 3 && s.every(x => KNOWN_TEAMS.has(x.team)) && new Set(s.map(x => x.team)).size >= 2;
};
const JY_POOL = PLAYERS.filter(journeyOk);

G.journey = {
  title: "Journey", share: "Sweater Journey", view: "view-journey", max: 6, next: "Next player",
  cheers: ["Instant recall! 🧠", "Snipe! 🎯", "Hat trick! 🎩", "Nice read! 🏒", "Got there! 💪", "Buzzer beater! 🚨"],
  pool: () => JY_POOL,
  daily(k) {
    const p = BYID.get((DAILY.journey || {})[k]);
    return p && journeyOk(p) ? p : JY_POOL[hash("sweater-jy-" + k) % JY_POOL.length];
  },
  random: () => pick(JY_POOL),
  tid: t => t.id, player: t => t, isWin: (t, id) => id === t.id,
  meta: t => `${t.team} · #${t.number} · ${posName(t)}`,
  reset(t) {
    $("jyWrong").innerHTML = "";
    $("jyPath").innerHTML = stintsOf(t).map((s, i) => `${i ? '<span class="jyarrow" aria-hidden="true">→</span>' : ""}
      <div class="jystop" style="animation-delay:${i * 70}ms">
        <img src="${logo(s.team)}" alt="" onerror="this.style.visibility='hidden'">
        <b>${esc(teamName(s.team))}</b>
        <small>${s.from === s.to ? seasonLabel(s.from) : spanLabel(s.from, s.to)}</small>
        <small>${s.gp} GP</small>
      </div>`).join("");
  },
  guess(t, id) {
    const p = BYID.get(id);
    if (!p) return null;
    if (p.id !== t.id) addWrong("jyWrong", p);
    return p.id === t.id;
  },
  render(t, st) {
    const wrong = st.guesses.filter(id => id !== t.id).length;
    const next = hintChips("jyHints", [
      { at: 2, html: `Position: <b>${posName(t)}</b>` },
      { at: 4, html: `Born in <b>${esc(t.nation)}</b>` },
      { at: 5, html: `Wears <b>#${t.number}</b> now` },
    ], wrong, st.over);
    $("jyLeft").textContent = st.over ? "" : `${this.max - st.guesses.length} tries left.${next}`;
  },
  squares: (t, id) => id === t.id ? "🟩" : "⬛"
};

// ---- Blur: the headshot gets sharper with every wrong guess ----
const BLUR_STEPS = [28, 20, 14, 9, 5, 2];
const BL_POOL = PLAYERS.filter(p => p.headshot);
G.blur = {
  title: "Blur", share: "Sweater Blur", view: "view-blur", max: 6, next: "Next player",
  cheers: ["Eagle eyes! 🦅", "Snipe! 🎯", "Hat trick! 🎩", "Nice read! 🏒", "Got there! 💪", "Buzzer beater! 🚨"],
  pool: () => BL_POOL,
  daily(k) {
    const p = BYID.get((DAILY.blur || {})[k]);
    return p && p.headshot ? p : BL_POOL[hash("sweater-bl-" + k) % BL_POOL.length];
  },
  random: () => pick(BL_POOL),
  tid: t => t.id, player: t => t, isWin: (t, id) => id === t.id,
  meta: t => `${t.team} · #${t.number} · ${posName(t)}`,
  reset(t) {
    $("blWrong").innerHTML = "";
    $("blImg").style.filter = `blur(${BLUR_STEPS[0]}px)`;
    $("blImg").onerror = function () { this.onerror = null; this.src = FALLBACK; };
    $("blImg").src = t.headshot || FALLBACK;
  },
  guess(t, id) {
    const p = BYID.get(id);
    if (!p) return null;
    if (p.id !== t.id) addWrong("blWrong", p);
    return p.id === t.id;
  },
  render(t, st) {
    const wrong = st.guesses.filter(id => id !== t.id).length;
    $("blImg").style.filter = st.over ? "none" : `blur(${BLUR_STEPS[Math.min(wrong, BLUR_STEPS.length - 1)]}px)`;
    const next = hintChips("blHints", [
      { at: 3, html: `Position: <b>${posName(t)}</b>` },
      { at: 5, html: `Plays for <img src="${logo(t.team)}" alt="" onerror="this.remove()"> <b>${esc(teamName(t.team))}</b>` },
    ], wrong, st.over);
    $("blLeft").textContent = st.over ? "" : `${this.max - st.guesses.length} tries left. Each wrong guess sharpens the photo.${next}`;
  },
  squares: (t, id) => id === t.id ? "🟩" : "⬛"
};

// ---- Sweater #: guess his jersey number ----
const NUM_POOL = PLAYERS.filter(p => p.number > 0);
const NUM_CLOSE = 3;
G.number = {
  title: "Sweater #", share: "Sweater Number", view: "view-number", max: 5, next: "Next player",
  cheers: ["Knew it cold! 🧠", "Snipe! 🎯", "Hat trick! 🎩", "Got there! 💪", "Buzzer beater! 🚨"],
  pool: () => NUM_POOL,
  daily(k) {
    const p = BYID.get((DAILY.number || {})[k]);
    return p && p.number > 0 ? p : NUM_POOL[hash("sweater-num-" + k) % NUM_POOL.length];
  },
  random: () => pick(NUM_POOL),
  tid: t => t.id, player: t => t, isWin: (t, n) => n === t.number,
  meta: t => `Wears #${t.number} for ${teamName(t.team)}`,
  state: (t, n) => n === t.number ? true : Math.abs(n - t.number) <= NUM_CLOSE ? "near" : false,
  reset(t) {
    $("numHist").innerHTML = "";
    $("numGuess").value = "";
    $("numImg").onerror = function () { this.onerror = null; this.src = FALLBACK; };
    $("numImg").src = t.headshot || FALLBACK;
    $("numName").textContent = t.name;
    $("numMeta").innerHTML = `<img src="${logo(t.team)}" alt="" onerror="this.remove()"> ${esc(teamName(t.team))} · ${posName(t)}`;
  },
  guess(t, n) {
    if (!Number.isInteger(n) || n < 0 || n > 99) return null;
    const s = this.state(t, n);
    const chip = document.createElement("span");
    chip.className = `chip numchip newrow ${s === true ? "hit" : s === "near" ? "near" : ""}`;
    chip.textContent = `#${n}${s === true ? " ✓" : n < t.number ? " ↑" : " ↓"}`;
    chip.title = s === true ? "Correct" : n < t.number ? "His number is higher" : "His number is lower";
    $("numHist").appendChild(chip);
    return s === true;
  },
  render(t, st) {
    const left = this.max - st.guesses.length;
    $("numLeft").textContent = st.over ? "" : `${left} ${left === 1 ? "try" : "tries"} left · ↑ means higher, ↓ lower · yellow means within ${NUM_CLOSE}`;
    $("numGuess").disabled = $("numGo").disabled = !!st.over;
  },
  squares(t, n) { return sq(this.state(t, n)); }
};
function submitNumber() {
  const raw = $("numGuess").value.trim(), n = Number(raw);
  if (!/^\d{1,2}$/.test(raw) || n > 99) { toast("Enter a number from 0 to 99"); return; }
  if (S.number.guesses.includes(n)) { toast(`You already tried #${n}`); return; }
  doGuess(n);
  $("numGuess").value = "";
  if (!S.number.over) $("numGuess").focus();
}
$("numGo").onclick = submitNumber;
$("numGuess").addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); submitNumber(); } });

// ---- Roster Recall: name as many players on a roster as you can in 60 seconds ----
const RO_SECONDS = 60;
const rosterOf = team => PLAYERS.filter(p => p.team === team).map(p => p.id).sort((a, b) => a - b);
const RO_TEAMS = Object.keys(TEAMS).filter(t => rosterOf(t).length >= 10);
const nameKey = s => norm(s).replace(/[^a-z0-9 ]/g, "").replace(/\s+/g, " ").trim();
let roTimer = null, roMemory = null;

G.roster = {
  kind: "score", title: "Roster Recall", share: "Sweater Roster", view: "view-roster", max: 99, next: "Next team",
  hideReveal: true,
  pool: () => RO_TEAMS,
  daily(k) {
    const v = (DAILY.roster || {})[k];
    if (v && v.ids && v.ids.length && v.ids.every(i => BYID.has(i))) return { team: v.team, ids: v.ids };
    const team = RO_TEAMS[hash("sweater-ro-" + k) % RO_TEAMS.length];
    return { team, ids: rosterOf(team) };
  },
  random() { const team = pick(RO_TEAMS); return { team, ids: rosterOf(team), rid: Math.random() }; },
  tid: t => t.rid ? `${t.team}:${t.rid}` : `${t.team}:${hash(t.ids.join(","))}`,
  player: t => BYID.get(t.ids[0]),
  score: (t, g) => g.filter(x => x !== "END").length,
  isWin: () => false,
  isDone(t, g) { return g.includes("END") || this.score(t, g) >= t.ids.length; },
  wonGame(t, g) { return this.score(t, g) >= t.ids.length; },
  meta: t => `${teamName(t.team)} · ${t.ids.length} players on the roster`,
  endText(t, g, won) {
    const n = this.score(t, g);
    return {
      result: won ? `All ${n}! Full roster` : `You named ${n} of ${t.ids.length}`,
      cheer: won ? "Hall-of-fame memory! 🏆" : n >= Math.ceil(t.ids.length * 0.6) ? "Front-office material! 🧠"
        : n >= 8 ? "Solid shift! 💪" : n >= 1 ? "Good effort! 🏒" : "Time's up!"
    };
  },
  celebrate(t, g, won) { return won || this.score(t, g) >= Math.ceil(t.ids.length * 0.6); },
  shareText(t, saved, num, link) {
    return `Sweater Roster #${num} · ${teamName(t.team)}\nNamed ${this.score(t, saved.guesses)}/${t.ids.length} in ${RO_SECONDS} seconds${link}`;
  },
  archiveStatus: h => `${h.s} named`,
  clockKey(t) { return `${mode}:${S.roster.day || ""}:${this.tid(t)}`; },
  reset(t) {
    const st = S.roster;
    clearInterval(roTimer);
    st.endsAt = null;
    const saved = mode === "unlimited" ? roMemory : store.get("sweater-roster-clock");
    if (saved && saved.key === this.clockKey(t)) st.endsAt = saved.endsAt;
    $("roLogo").src = logo(t.team);
    $("roTeam").textContent = teamName(t.team);
    $("roTotal").textContent = t.ids.length;
    $("roInput").value = "";
    $("roMsg").textContent = "";
    $("roFound").innerHTML = "";
  },
  guess(t, x) {
    if (x === "END") return false;
    return t.ids.includes(x) ? false : null;
  },
  render(t, st) {
    const found = st.guesses.filter(x => x !== "END");
    const running = !!st.endsAt && !st.over;
    $("roCount").textContent = found.length;
    $("roStart").hidden = running || st.over;
    $("roInput").disabled = !running;
    $("roInput").placeholder = running ? "Type a player's name and press Enter"
      : st.over ? "Time's up" : "Press Start to begin";
    $("roTime").textContent = st.over ? 0 : running ? Math.max(0, Math.ceil((st.endsAt - Date.now()) / 1000)) : RO_SECONDS;
    const chip = (id, cls) => { const p = BYID.get(id); return p ? `<span class="chip ${cls}">${esc(p.name)}</span>` : ""; };
    $("roFound").innerHTML = found.slice().reverse().map(id => chip(id, "hit")).join("")
      + (st.over ? t.ids.filter(id => !found.includes(id)).map(id => chip(id, "missed")).join("") : "");
    if (running) {
      if (st.endsAt <= Date.now()) setTimeout(() => { if (game === "roster" && !S.roster.over) doGuess("END"); }, 0);
      else roTick();
    }
  },
};
function roTick() {
  clearInterval(roTimer);
  roTimer = setInterval(() => {
    const st = S.roster;
    if (!st.endsAt || st.over) { clearInterval(roTimer); return; }
    const left = Math.max(0, Math.ceil((st.endsAt - Date.now()) / 1000));
    if (game === "roster") {
      $("roTime").textContent = left;
      $("roTime").parentElement.classList.toggle("urgent", left <= 10);
    }
    if (left <= 0) { clearInterval(roTimer); if (game === "roster") doGuess("END"); }
  }, 200);
}
function roStart() {
  const st = S.roster;
  if (game !== "roster" || !st.target || st.over || st.endsAt) return;
  st.endsAt = Date.now() + RO_SECONDS * 1000;
  const rec = { key: G.roster.clockKey(st.target), endsAt: st.endsAt };
  if (mode === "unlimited") roMemory = rec; else store.set("sweater-roster-clock", rec);
  G.roster.render(st.target, st);
  $("roInput").focus();
}
function roEnter() {
  const st = S.roster, t = st.target;
  if (!t || st.over || !st.endsAt) return;
  const q = nameKey($("roInput").value);
  if (!q) return;
  const players = t.ids.map(i => BYID.get(i)).filter(Boolean);
  let p = players.find(x => nameKey(x.name) === q);
  if (!p) {
    const byLast = players.filter(x => { const parts = nameKey(x.name).split(" ");
      return parts.slice(1).join(" ") === q || parts[parts.length - 1] === q; });
    if (byLast.length > 1) { roSay("More than one player has that last name. Use the full name.", true); return; }
    p = byLast[0];
  }
  if (!p) { roSay("Not on this roster", true); return; }
  if (st.guesses.includes(p.id)) { roSay(`Already named ${p.name}`, true); $("roInput").value = ""; return; }
  $("roInput").value = "";
  roSay(`✓ ${p.name}`);
  doGuess(p.id);
  if (!S.roster.over) $("roInput").focus();
}
function roSay(text, bad = false) {
  $("roMsg").textContent = text;
  $("roMsg").classList.toggle("bad", bad);
  if (bad) { $("roInput").classList.remove("shake"); void $("roInput").offsetWidth; $("roInput").classList.add("shake"); }
}
$("roStart").onclick = roStart;
$("roInput").addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); roEnter(); } });

// ======================= draft day, birthplace, connections =======================
const COUNTRY_NAMES = {
  CAN: "Canada", USA: "the USA", SWE: "Sweden", FIN: "Finland", CZE: "Czechia", RUS: "Russia", SVK: "Slovakia",
  CHE: "Switzerland", DEU: "Germany", AUT: "Austria", DNK: "Denmark", NOR: "Norway", LVA: "Latvia", FRA: "France",
  GBR: "Great Britain", SVN: "Slovenia", BLR: "Belarus", UKR: "Ukraine", KAZ: "Kazakhstan", AUS: "Australia",
  NLD: "the Netherlands", POL: "Poland", ITA: "Italy", JPN: "Japan", KOR: "South Korea", HUN: "Hungary",
  BRA: "Brazil", JAM: "Jamaica", NGA: "Nigeria", ZAF: "South Africa", LTU: "Lithuania", EST: "Estonia",
  BEL: "Belgium", CHN: "China", TWN: "Taiwan", HRV: "Croatia", SRB: "Serbia", BGR: "Bulgaria", ROU: "Romania",
  ISR: "Israel", IRL: "Ireland", MEX: "Mexico", VEN: "Venezuela", KEN: "Kenya", GHA: "Ghana", HTI: "Haiti", THA: "Thailand"
};
const countryName = c => COUNTRY_NAMES[c] || c;
const ordinal = n => { const v = n % 100; return n + (v >= 11 && v <= 13 ? "th" : ({ 1: "st", 2: "nd", 3: "rd" })[n % 10] || "th"); };
function shuffled(arr, rnd = Math.random) {
  const a = arr.slice();
  for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(rnd() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; }
  return a;
}

// ---- Draft Day: guess the year and round he was drafted ----
const hasDraft = p => Array.isArray(p.draft) && p.draft.length >= 2;
const DR_POOL = PLAYERS.filter(hasDraft);
const draftKey = p => `${p.draft[0]}-${p.draft[1]}`;
const DR_MIN_YEAR = 1985, DR_MAX_ROUND = 9;
G.draft = {
  title: "Draft Day", share: "Sweater Draft", view: "view-draft", max: 5, next: "Next player",
  cheers: ["Scouting genius! 🔭", "Snipe! 🎯", "Hat trick! 🎩", "Got there! 💪", "Buzzer beater! 🚨"],
  pool: () => DR_POOL,
  daily(k) {
    const p = BYID.get((DAILY.draft || {})[k]);
    return p && hasDraft(p) ? p : DR_POOL[hash("sweater-dr-" + k) % DR_POOL.length];
  },
  random: () => pick(DR_POOL),
  tid: t => t.id, player: t => t, isWin: (t, x) => x === draftKey(t),
  meta: t => `Drafted ${t.draft[2] ? `${ordinal(t.draft[2])} overall, ` : ""}round ${t.draft[1]}, ${t.draft[0]}${t.draft[3] ? ` by ${teamName(t.draft[3])}` : ""}`,
  states(t, x) {
    const [y, r] = x.split("-").map(Number), [ty, tr] = t.draft;
    return [y === ty ? true : Math.abs(y - ty) <= 2 ? "near" : false, r === tr ? true : Math.abs(r - tr) <= 1 ? "near" : false, y, r];
  },
  reset(t) {
    $("drHist").innerHTML = "";
    $("drImg").onerror = function () { this.onerror = null; this.src = FALLBACK; };
    $("drImg").src = t.headshot || FALLBACK;
    $("drName").textContent = t.name;
    $("drMeta").innerHTML = `<img src="${logo(t.team)}" alt="" onerror="this.remove()"> ${esc(teamName(t.team))} · ${posName(t)} · age ${ageOf(t.birth)}`;
    $("drYear").value = "";
    $("drRound").value = "";
  },
  guess(t, x) {
    if (typeof x !== "string" || !/^\d{4}-\d{1,2}$/.test(x)) return null;
    const [ys, rs, y, r] = this.states(t, x), [ty, tr] = t.draft;
    const cls = s => s === true ? "hit" : s === "near" ? "near" : "";
    const row = document.createElement("div");
    row.className = "drrow newrow";
    row.innerHTML = `<span class="chip ${cls(ys)}">${y}${ys === true ? " ✓" : y < ty ? " ↑" : " ↓"}</span>
      <span class="chip ${cls(rs)}">Round ${r}${rs === true ? " ✓" : r < tr ? " ↑" : " ↓"}</span>`;
    $("drHist").appendChild(row);
    return ys === true && rs === true;
  },
  render(t, st) {
    const wrong = st.guesses.filter(x => x !== draftKey(t)).length;
    const next = hintChips("drHints", t.draft[3] ? [
      { at: 3, html: `Drafted by <img src="${logo(t.draft[3])}" alt="" onerror="this.remove()"> <b>${esc(teamName(t.draft[3]))}</b>` },
    ] : [], wrong, st.over);
    const left = this.max - st.guesses.length;
    $("drLeft").textContent = st.over ? "" : `${left} ${left === 1 ? "try" : "tries"} left. ↑ means later, ↓ earlier. Yellow: year within 2 or round within 1.${next}`;
    ["drYear", "drRound", "drGo"].forEach(id => { $(id).disabled = !!st.over; });
  },
  squares(t, x) { const [a, b] = this.states(t, x); return `${sq(a)}${sq(b)} `; }
};
(() => {
  const now = new Date().getFullYear();
  $("drRound").innerHTML = '<option value="">Round</option>' +
    Array.from({ length: DR_MAX_ROUND }, (_, i) => `<option value="${i + 1}">Round ${i + 1}</option>`).join("");
  $("drYear").placeholder = `Year (${DR_MIN_YEAR}–${now})`;
})();
function submitDraft() {
  const y = Number($("drYear").value.trim()), r = Number($("drRound").value);
  if (!Number.isInteger(y) || y < DR_MIN_YEAR || y > new Date().getFullYear()) { toast("Enter a draft year"); $("drYear").focus(); return; }
  if (!r) { toast("Pick a round"); $("drRound").focus(); return; }
  const key = `${y}-${r}`;
  if (S.draft.guesses.includes(key)) { toast("You already tried that"); return; }
  doGuess(key);
}
$("drGo").onclick = submitDraft;
$("drYear").addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); submitDraft(); } });

// ---- Birthplace: drop pins on the map ----
const MAP_K = 0.72;                     // squash longitude so the map looks natural
const MAP_WIN_KM = 100, MAP_PINS = 3;
// How far in you have to zoom before capital labels appear, measured as the
// width of the view in map units (about 1.4 units per degree of longitude).
// [fading in, fully visible] - lower both numbers to reveal them later still.
const MAP_LABEL_ZOOM = { national: [55, 40], regional: [30, 20] };
// Zoom feel: one mouse-wheel notch is a full zoom step, as in Google Maps,
// while trackpad scrolls and pinches move in proportion to the gesture.
const ZOOM_NOTCH = Math.LN2, ZOOM_TRACKPAD = Math.LN2 / 180, ZOOM_PINCH = Math.LN2 / 110;
const MAP_MIN_W = 3, MAP_MAX_W = 360 * MAP_K * 1.05;
// Embedded map detail: no map service, extra upload, or API key is required.
// Natural Earth 1:50m land, lakes, country and admin-1 lines, 1:10m populated places. Public domain.
const MAP_SUBDIVISIONS = ["M-60.714,-34.988L-60.687,-35.201L-60.668,-35.25L-60.647,-35.261L-60.573,-35.261L-60.525,-35.286L-60.483,-35.414L-60.387,-35.515L-60.344,-35.54L-60.28,-35.56L-60.128,-35.584L-59.965,-35.682L-59.847,-35.775L-59.753,-35.8L-59.724,-35.835L-59.703,-35.879L-59.689,-35.939L-59.679,-35.952L-59.625,-35.947L-59.584,-36L-59.544,-36.03L-59.504,-36.047L-59.48,-36.047L-59.471,-36.032L-59.464,-35.987L-59.455,-35.972L-59.438,-35.971L-59.415,-35.981L-59.384,-36.01L-59.305,-36.1L-59.252,-36.134L-59.171,-36.154L-59.112,-36.107L-59.077,-36.123L-58.974,-36.306L-58.933,-36.34L-58.902,-36.353L-58.849,-36.355L-58.848,-36.406L-58.83,-36.482L-58.827,-36.534L-58.794,-36.611","M-53.783,-41.357L-53.84,-41.325L-53.865,-41.302L-53.886,-41.269L-53.937,-41.155L-54.023,-41.052L-54.089,-40.999L-54.088,-40.972L-54.054,-40.884L-54.054,-40.856L-54.08,-40.802L-54.126,-40.776L-54.134,-40.744L-54.138,-40.69L-54.136,-40.596L-54.123,-40.577L-54.07,-40.543L-54.025,-40.42L-53.983,-40.406L-53.809,-40.155L-53.935,-40.08L-54.017,-40.017L-54.053,-39.983","M-51.493,-45.008L-51.504,-44.988L-51.487,-44.908L-51.567,-44.772L-51.565,-44.728L-51.529,-44.608L-51.531,-44.579L-51.543,-44.565L-51.559,-44.514L-51.58,-44.482L-51.612,-44.45L-51.714,-44.374L-51.745,-44.355L-51.841,-44.329L-51.862,-44.301L-51.885,-44.116L-51.916,-44.013L-51.923,-43.965L-51.965,-43.884L-52,-43.791L-52.054,-43.715L-52.083,-43.622L-52.101,-43.587L-52.117,-43.529L-52.133,-43.332L-52.155,-43.225L-52.181,-43.039L-52.197,-42.992L-52.214,-42.967L-52.236,-42.887L-52.238,-42.856L-52.229,-42.83L-52.188,-42.766L-52.176,-42.73","M-59.464,-38.42L-59.464,-38.42L-59.472,-38.432","M-59.481,-38.448L-59.464,-38.42","M-59.015,-37.54L-59.114,-37.571L-59.242,-37.687L-59.324,-37.828L-59.35,-37.894L-59.38,-37.938L-59.387,-37.984L-59.464,-38.1L-59.485,-38.15L-59.486,-38.182L-59.461,-38.243L-59.456,-38.272L-59.464,-38.42L-59.464,-38.42","M-59.015,-37.54L-59.287,-37.297L-59.412,-37.209L-59.531,-37.138L-59.54,-37.126L-59.567,-37.048L-59.639,-36.979L-59.684,-36.906L-59.792,-36.846L-59.868,-36.762L-60.06,-36.681L-60.168,-36.653L-60.241,-36.605","M-64.609,-31.001L-64.631,-30.886L-64.681,-30.731L-64.683,-30.69L-64.67,-30.64L-64.67,-30.611L-64.652,-30.569L-64.61,-30.527L-64.574,-30.463L-64.541,-30.349L-64.533,-30.296L-64.506,-30.223L-64.492,-30.209L-64.472,-30.201L-64.455,-30.193","M-69.521,-45.943L-69.531,-46.019L-69.524,-46.138L-69.546,-46.228L-69.551,-46.272L-69.565,-46.327L-69.646,-46.473L-69.666,-46.59L-69.686,-46.648L-69.693,-46.797L-69.691,-46.839L-69.674,-46.92L-69.709,-46.974L-69.714,-47.019L-69.73,-47.373L-69.741,-47.424L-69.738,-47.588L-69.801,-47.762L-69.831,-47.82L-69.847,-47.892L-69.845,-47.926L-69.897,-48.043L-69.931,-48.173L-69.928,-48.286L-69.938,-48.371L-69.934,-48.437L-69.944,-48.537L-69.933,-48.593L-69.932,-48.681L-70.003,-48.994","M-67.714,-33.554L-67.751,-33.577L-67.818,-33.589L-67.852,-33.581L-67.892,-33.587L-67.919,-33.565L-67.938,-33.561L-67.952,-33.566L-67.961,-33.586L-67.991,-33.6L-68.029,-33.648","M-54.303,-39.815L-54.368,-39.843L-54.457,-39.839L-54.487,-39.827L-54.511,-39.803L-54.565,-39.722","M-58.383,-35.156L-58.361,-35.146L-58.354,-35.131L-58.357,-35.089L-58.353,-35.066","M-59.6,-35.087L-59.576,-35.084L-59.509,-35.128L-59.374,-35.178L-59.323,-35.211L-59.296,-35.202","M-86.4,-60.001L-86.4,-59.616L-86.4,-59.231L-86.4,-58.847L-86.4,-58.462L-86.4,-58.077L-86.4,-57.692L-86.4,-57.307L-86.4,-56.922L-86.4,-56.538L-86.4,-56.153L-86.401,-55.768L-86.401,-55.383L-86.401,-54.998L-86.401,-54.613L-86.401,-54.229L-86.401,-53.844L-86.38,-53.797L-86.34,-53.77L-86.331,-53.723L-86.317,-53.708L-86.264,-53.699L-86.209,-53.634L-86.215,-53.615L-86.319,-53.615L-86.341,-53.612L-86.343,-53.602L-86.325,-53.567L-86.324,-53.516L-86.296,-53.509L-86.27,-53.491L-86.201,-53.4L-86.17,-53.371L-86.146,-53.363L-86.107,-53.372L-85.993,-53.362L-85.968,-53.353L-85.902,-53.242L-85.868,-53.209L-85.713,-53.144L-85.696,-53.139L-85.692,-53.204L-85.675,-53.236L-85.618,-53.212L-85.539,-53.153L-85.517,-53.122L-85.512,-53.065L-85.487,-53.058L-85.448,-53.026L-85.441,-52.972L-85.414,-52.909L-85.396,-52.895L-85.321,-52.888L-85.303,-52.879L-85.268,-52.836L-85.257,-52.784L-85.218,-52.742L-85.198,-52.709L-85.19,-52.674L-85.212,-52.623L-85.168,-52.562L-85.152,-52.518L-85.122,-52.483L-85.138,-52.441L-85.135,-52.409L-85.119,-52.386L-85.098,-52.384L-85.003,-52.413L-84.992,-52.427L-84.981,-52.466L-84.961,-52.486L-84.876,-52.43L-84.785,-52.395L-84.767,-52.383L-84.769,-52.353L-84.832,-52.272L-84.807,-52.233L-84.78,-52.208L-84.663,-52.142L-84.517,-52.144L-84.49,-52.159L-84.471,-52.156L-84.416,-52.047L-84.295,-51.926L-84.267,-51.886L-84.196,-51.736L-84.177,-51.714L-84.118,-51.715L-84.107,-51.722L-84.102,-51.753L-84.089,-51.771L-84.066,-51.789L-84.037,-51.8L-84.005,-51.791L-83.976,-51.758L-83.928,-51.651L-83.881,-51.615L-83.85,-51.574L-83.816,-51.544L-83.792,-51.497L-83.743,-51.448L-83.721,-51.348L-83.7,-51.323L-83.647,-51.297L-83.617,-51.266L-83.559,-51.237L-83.55,-51.23L-83.545,-51.218L-83.53,-51.151L-83.518,-51.13L-83.477,-51.102L-83.372,-51.07L-83.246,-50.962L-83.229,-50.936L-83.223,-50.909L-83.261,-50.869L-83.256,-50.855L-83.112,-50.756L-83.087,-50.731L-83.078,-50.726L-83.07,-50.727L-83.059,-50.729L-83.049,-50.729L-83.041,-50.72L-83.024,-50.697L-83.015,-50.673L-83.021,-50.656L-83.024,-50.642L-83.02,-50.635L-82.992,-50.594L-82.96,-50.563L-82.948,-50.554L-82.936,-50.557L-82.892,-50.585L-82.866,-50.585L-82.834,-50.577L-82.795,-50.545L-82.648,-50.359L-82.596,-50.129L-82.561,-50.061L-82.549,-50.02L-82.549,-49.985L-82.568,-49.955L-82.573,-49.934L-82.539,-49.797L-82.543,-49.73L-82.574,-49.643L-82.611,-49.604L-82.608,-49.587L-82.596,-49.569L-82.57,-49.556L-82.513,-49.551L-82.496,-49.544L-82.495,-49.519L-82.505,-49.452L-82.503,-49.42L-82.487,-49.394L-82.425,-49.333L-82.387,-49.274L-82.358,-49.252L-82.352,-49.232L-82.335,-49.211L-82.217,-49.168L-82.198,-49.147L-82.175,-49.094L-82.121,-49.038L-82.116,-49.015L-82.125,-48.993","M-89.15,-60.001L-89.166,-60.02L-89.193,-60.04L-89.275,-60.04L-89.288,-60.046L-89.289,-60.06L-89.274,-60.099L-89.278,-60.127L-89.354,-60.225L-89.413,-60.321L-89.427,-60.353L-89.442,-60.453L-89.46,-60.473L-89.57,-60.494L-89.618,-60.567L-89.712,-60.662L-89.72,-60.682L-89.72,-60.701L-89.644,-60.788L-89.645,-60.822L-89.699,-60.953L-89.723,-60.96L-89.861,-60.961L-89.883,-60.948L-89.899,-60.924L-89.914,-60.86L-90.109,-60.844L-90.165,-60.826L-90.232,-60.792L-90.273,-60.792L-90.509,-60.84L-90.622,-60.89L-90.647,-60.89L-90.671,-60.883L-90.689,-60.865L-90.722,-60.809L-90.766,-60.816L-90.791,-60.829L-90.803,-60.863L-90.836,-60.866L-90.88,-60.856L-90.889,-60.844L-90.889,-60.809L-90.904,-60.794L-90.934,-60.785L-90.972,-60.781L-91.094,-60.8L-91.199,-60.762L-91.273,-60.775L-91.319,-60.764L-91.339,-60.769L-91.361,-60.796L-91.359,-60.833L-91.376,-60.86L-91.381,-60.884L-91.374,-60.95L-91.4,-61.052L-91.414,-61.063L-91.479,-61.051L-91.507,-61.071L-91.509,-61.081L-91.499,-61.094L-91.459,-61.126L-91.451,-61.198L-91.455,-61.237L-91.492,-61.37L-91.524,-61.404L-91.56,-61.465L-91.605,-61.494L-91.656,-61.512L-91.777,-61.511L-91.878,-61.533L-91.913,-61.552L-91.953,-61.588L-92.021,-61.619L-92.155,-61.711L-92.174,-61.78L-92.194,-61.813L-92.228,-61.841L-92.309,-61.865L-92.327,-61.884L-92.346,-61.928L-92.424,-61.991L-92.448,-62.034L-92.564,-62.117L-92.603,-62.122L-92.649,-62.112L-92.718,-62.069L-92.746,-62.064L-92.765,-62.073L-92.793,-62.111L-92.813,-62.119L-92.89,-62.132L-92.978,-62.126L-93.03,-62.136L-93.063,-62.153L-93.074,-62.166L-93.068,-62.184L-93.052,-62.202L-93.048,-62.22L-93.056,-62.236L-93.091,-62.294L-93.09,-62.322L-93.052,-62.373L-93.059,-62.389L-93.091,-62.411L-93.093,-62.425L-93.087,-62.441L-93.024,-62.47L-93.016,-62.49L-93.032,-62.513L-93.203,-62.58L-93.233,-62.599L-93.236,-62.619L-93.258,-62.674L-93.272,-62.688L-93.326,-62.712L-93.338,-62.728L-93.343,-62.756L-93.354,-62.776L-93.397,-62.832L-93.405,-62.865L-93.394,-62.895L-93.394,-62.931L-93.325,-63.037L-93.32,-63.059L-93.333,-63.068L-93.409,-63.07L-93.476,-63.092L-93.507,-63.157L-93.532,-63.187L-93.585,-63.216L-93.643,-63.261L-93.696,-63.276L-93.701,-63.293L-93.673,-63.319L-93.563,-63.376L-93.532,-63.406L-93.488,-63.486L-93.496,-63.522L-93.519,-63.555L-93.561,-63.586L-93.583,-63.616L-93.645,-63.636L-93.659,-63.65L-93.67,-63.679L-93.68,-63.695L-93.702,-63.698L-93.775,-63.678L-93.805,-63.686L-93.818,-63.704L-93.815,-63.721L-93.787,-63.737L-93.704,-63.762L-93.687,-63.773L-93.685,-63.793L-93.701,-63.808L-93.803,-63.823L-93.862,-63.85L-93.969,-63.92L-94.076,-63.951L-94.146,-63.993L-94.17,-64.031L-94.21,-64.049L-94.228,-64.081L-94.269,-64.125L-94.278,-64.141L-94.257,-64.168L-94.258,-64.193L-94.27,-64.219L-94.307,-64.259L-94.329,-64.273L-94.339,-64.298L-94.336,-64.324L-94.397,-64.401L-94.511,-64.447L-94.578,-64.458L-94.607,-64.451L-94.644,-64.416L-94.689,-64.393L-94.742,-64.38L-94.87,-64.381L-94.894,-64.388L-94.898,-64.407L-94.889,-64.426L-94.846,-64.489L-94.836,-64.515L-94.845,-64.534L-94.862,-64.545L-94.963,-64.577L-95.078,-64.684L-95.117,-64.702L-95.271,-64.763L-95.329,-64.777L-95.439,-64.78L-95.463,-64.794L-95.472,-64.809L-95.473,-64.826L-95.46,-64.842L-95.403,-64.884L-95.398,-64.913L-95.398,-64.957L-95.386,-64.97L-95.314,-65.022L-95.295,-65.039L-95.294,-65.057L-95.315,-65.075L-95.412,-65.094L-95.428,-65.109L-95.429,-65.17L-95.457,-65.185L-95.479,-65.181L-95.55,-65.167L-95.581,-65.173L-95.593,-65.185L-95.597,-65.203L-95.589,-65.225L-95.47,-65.28L-95.448,-65.3L-95.43,-65.341L-95.289,-65.443L-95.233,-65.538L-95.18,-65.598L-95.181,-65.628L-95.253,-65.716L-95.312,-65.767L-95.392,-65.82L-95.424,-65.834L-95.439,-65.857L-95.428,-65.886L-95.285,-65.955L-95.287,-65.979L-95.307,-65.994L-95.388,-65.989L-95.456,-66.024L-95.482,-66.029L-95.554,-65.998L-95.592,-65.971L-95.631,-65.928L-95.69,-65.914L-95.723,-65.917L-95.737,-65.934L-95.716,-65.976L-95.7,-66.002L-95.701,-66.018L-95.715,-66.029L-95.79,-66.028L-95.925,-66.006L-96.057,-65.956L-96.12,-65.955L-96.184,-65.963L-96.208,-65.975L-96.209,-66.01L-96.225,-66.049L-96.247,-66.074L-96.248,-66.096L-96.235,-66.112L-96.188,-66.15L-96.169,-66.177L-96.168,-66.208L-96.171,-66.249L-96.18,-66.285L-96.201,-66.295L-96.229,-66.3L-96.307,-66.304L-96.329,-66.304L-96.336,-66.326L-96.329,-66.348L-96.307,-66.416L-96.292,-66.44L-96.268,-66.444L-96.246,-66.446L-96.231,-66.453L-96.229,-66.472L-96.234,-66.509L-96.227,-66.536L-96.217,-66.566L-96.229,-66.586L-96.282,-66.631L-96.31,-66.651L-96.313,-66.669L-96.315,-66.684L-96.335,-66.711L-96.34,-66.733L-96.334,-66.752L-96.324,-66.785L-96.332,-66.819L-96.37,-66.862L-96.425,-66.903L-96.503,-66.944L-96.518,-66.973L-96.52,-67.004L-96.565,-67.004L-96.772,-67.004L-96.978,-67.005L-97.185,-67.005L-97.391,-67.005L-97.598,-67.005L-97.804,-67.005L-98.011,-67.005L-98.042,-67.015L-98.06,-67.036L-98.081,-67.088L-98.081,-67.135L-98.079,-67.163L-98.077,-67.181L-98.028,-67.226L-97.998,-67.288L-97.996,-67.304L-98.013,-67.354L-98.021,-67.375L-98.034,-67.394L-98.048,-67.423L-98.048,-67.45L-98.042,-67.514L-98.07,-67.577L-98.088,-67.6L-98.111,-67.616L-98.209,-67.666L-98.233,-67.703L-98.241,-67.747L-98.241,-68.038L-98.241,-68.329L-98.24,-68.62L-98.24,-68.895","M-49.233,-47.589L-49.243,-47.563L-49.269,-47.528L-49.317,-47.48L-49.412,-47.421L-49.719,-47.295","M-48.681,-47.999L-48.679,-47.969L-48.657,-47.94L-48.503,-47.855L-48.461,-47.887L-48.375,-47.894L-48.281,-47.919L-48.205,-47.899L-48.186,-47.964L-48.127,-47.998L-48.027,-48.022","M-86.401,-42.001L-86.59,-42.001L-86.78,-42.001L-86.97,-42.001L-87.16,-42.001L-87.35,-42.001L-87.54,-42.001L-87.729,-42.001L-87.919,-42.001L-88.109,-42.001L-88.299,-42.001L-88.489,-42.001L-88.679,-42.001L-88.868,-42.001L-89.058,-42.001L-89.248,-42.001L-89.444,-42.001","M-79.957,-44.499L-80.004,-44.525L-80.036,-44.556L-80.062,-44.591L-80.111,-44.688L-80.139,-44.723L-80.163,-44.745L-80.188,-44.746L-80.219,-44.734L-80.243,-44.711L-80.251,-44.671L-80.274,-44.624L-80.272,-44.585L-80.262,-44.565L-80.265,-44.554L-80.28,-44.545L-80.395,-44.56L-80.494,-44.54L-80.562,-44.555L-80.693,-44.548L-80.807,-44.561L-80.845,-44.554L-80.87,-44.533L-80.902,-44.48L-80.91,-44.47L-80.923,-44.468L-81.107,-44.497L-81.155,-44.498L-81.207,-44.463L-81.223,-44.438L-81.227,-44.406L-81.239,-44.397L-81.255,-44.398L-81.295,-44.419L-81.338,-44.454L-81.36,-44.48L-81.365,-44.539L-81.399,-44.605L-81.405,-44.665L-81.427,-44.715L-81.461,-44.765L-81.495,-44.799L-81.529,-44.81L-81.591,-44.803L-81.604,-44.808L-81.671,-44.874L-81.692,-44.904L-81.698,-44.93L-81.675,-44.994L-81.682,-45.029L-81.699,-45.073L-81.723,-45.109L-81.761,-45.14L-81.797,-45.209L-81.862,-45.305L-81.88,-45.379L-81.904,-45.441L-81.912,-45.503L-81.936,-45.54L-81.934,-45.588L-81.938,-45.601L-81.945,-45.607L-81.988,-45.634L-82.039,-45.682L-82.064,-45.692L-82.074,-45.693L-82.081,-45.681L-82.085,-45.658L-82.164,-45.579L-82.231,-45.542L-82.264,-45.506L-82.294,-45.488L-82.31,-45.486L-82.332,-45.497L-82.403,-45.551L-82.461,-45.576L-82.467,-45.587L-82.463,-45.633L-82.437,-45.686L-82.464,-45.782L-82.456,-45.815L-82.435,-45.839L-82.372,-45.874L-82.366,-45.891L-82.379,-45.982L-82.415,-46.016L-82.424,-46.036L-82.414,-46.11L-82.429,-46.158L-82.402,-46.199L-82.4,-46.271L-82.377,-46.344L-82.354,-46.453L-82.359,-46.5L-82.329,-46.551L-82.319,-46.601L-82.318,-46.638L-82.323,-46.659L-82.333,-46.668L-82.354,-46.668L-82.453,-46.648L-82.485,-46.65L-82.513,-46.66L-82.529,-46.678L-82.534,-46.719L-82.556,-46.746L-82.568,-46.75L-82.613,-46.734L-82.623,-46.735L-82.628,-46.742L-82.646,-46.777L-82.719,-46.845L-82.754,-46.923L-82.824,-46.991L-82.891,-47.085L-83.021,-47.231L-83.052,-47.261L-83.15,-47.312L-83.227,-47.385L-83.306,-47.438L-83.314,-47.447L-83.314,-47.452L-83.31,-47.457L-83.287,-47.471L-83.282,-47.498L-83.312,-47.553L-83.297,-47.607L-83.317,-47.681L-83.328,-47.706L-83.384,-47.776L-83.421,-47.842L-83.478,-47.904L-83.555,-48.005L-83.555,-48.252L-83.555,-48.499L-83.555,-48.747L-83.555,-48.993","M-79.957,-44.499L-79.957,-44.343L-79.957,-44.187L-79.957,-44.031L-79.957,-43.874L-79.957,-43.718L-79.957,-43.562L-79.957,-43.406L-79.957,-43.25L-79.957,-43.094L-79.957,-42.938L-79.956,-42.782L-79.956,-42.625L-79.956,-42.469L-79.956,-42.313L-79.956,-42.157L-79.956,-42.001","M-79.957,-44.499L-79.957,-44.624L-79.957,-44.75L-79.957,-44.876L-79.957,-45.001L-79.799,-45.001L-79.641,-45.001L-79.483,-45.001L-79.325,-45.001L-79.168,-45.001L-79.01,-45.001L-78.852,-45.001L-78.694,-45.001L-78.536,-45.001L-78.379,-45.001L-78.221,-45.001L-78.063,-45.001L-77.905,-45.001L-77.747,-45.001L-77.59,-45.001L-77.432,-45.001L-77.274,-45.001L-77.116,-45.001L-76.958,-45.001L-76.8,-45.001L-76.643,-45.001L-76.485,-45.001L-76.327,-45.001L-76.169,-45.001L-76.011,-45.001L-75.854,-45.001L-75.696,-45.001L-75.538,-45.001L-75.38,-45.001L-75.222,-45.001L-75.065,-45.001L-74.907,-45.001","M-84.252,-42.001L-84.521,-42.001L-84.789,-42.001L-85.058,-42.001L-85.326,-42.001L-85.595,-42.001L-85.863,-42.001L-86.132,-42.001L-86.401,-42.001","M-84.252,-42.001L-83.984,-42.001L-83.717,-42.001L-83.449,-42.001L-83.181,-42.001L-82.914,-42.001L-82.646,-42.001L-82.378,-42.001L-82.111,-42.001","M-79.956,-42.001L-80.091,-42.001L-80.226,-42.001L-80.36,-42.001L-80.495,-42.001L-80.629,-42.001L-80.764,-42.001L-80.899,-42.001L-81.033,-42.001L-81.168,-42.001L-81.303,-42.001L-81.437,-42.001L-81.572,-42.001L-81.707,-42.001L-81.841,-42.001L-81.976,-42.001L-82.111,-42.001","M-79.956,-42.001L-79.956,-41.876L-79.956,-41.751L-79.956,-41.626L-79.956,-41.501L-79.956,-41.376L-79.956,-41.251L-79.956,-41.126L-79.956,-41.001L-79.776,-41.001L-79.595,-41.001L-79.415,-41.001L-79.235,-41.001L-79.054,-41.001L-78.874,-41.001L-78.694,-41.001L-78.513,-41.001","M-82.111,-42.001L-82.111,-41.845L-82.111,-41.689L-82.111,-41.533L-82.11,-41.376L-82.11,-41.22L-82.11,-41.064L-82.11,-40.908L-82.11,-40.752L-82.11,-40.596L-82.11,-40.44L-82.11,-40.283L-82.11,-40.127L-82.11,-39.971L-82.11,-39.815L-82.11,-39.659L-82.11,-39.503L-82.11,-39.346L-82.11,-39.19L-82.11,-39.034L-82.11,-38.878L-82.11,-38.722L-82.11,-38.566L-82.109,-38.41L-82.109,-38.253L-82.109,-38.097L-82.109,-37.941L-82.109,-37.785L-82.109,-37.629L-82.109,-37.473L-82.109,-37.316L-82.109,-37.16L-82.109,-37.004","M-82.109,-37.004L-81.884,-37.004L-81.66,-37.004L-81.435,-37.004L-81.21,-37.003L-80.985,-37.003L-80.761,-37.003L-80.536,-37.003L-80.311,-37.002L-80.087,-37.002L-79.862,-37.002L-79.637,-37.002L-79.412,-37.002L-79.188,-37.001L-78.963,-37.001L-78.738,-37.001L-78.514,-37.001","M-78.514,-37.001L-78.514,-36.646L-78.514,-36.292L-78.514,-35.937L-78.514,-35.583L-78.514,-35.228L-78.514,-34.874L-78.514,-34.519L-78.514,-34.165L-78.514,-33.81L-78.514,-33.456L-78.514,-33.101L-78.514,-32.747L-78.514,-32.392L-78.514,-32.038L-78.514,-31.683L-78.514,-31.328","M-78.513,-41.001L-78.287,-41.001L-78.061,-41.001L-77.835,-41.001L-77.609,-41.001L-77.383,-41.001L-77.157,-41.001L-76.931,-41.001L-76.705,-41.001L-76.478,-41.001L-76.252,-41.001L-76.026,-41.001L-75.8,-41.001L-75.574,-41.001L-75.348,-41.001L-75.122,-41.001L-74.896,-41.001","M-78.513,-41.001L-78.513,-40.751L-78.513,-40.501L-78.513,-40.251L-78.513,-40.001L-78.513,-39.751L-78.513,-39.501L-78.513,-39.251L-78.514,-39.001L-78.514,-38.751L-78.514,-38.501L-78.514,-38.251L-78.514,-38.001L-78.514,-37.751L-78.514,-37.501L-78.514,-37.251L-78.514,-37.001","M-74.161,-37.001L-74.433,-37.001L-74.705,-37.001L-74.977,-37.001L-75.249,-37.001L-75.521,-37.001L-75.793,-37.001L-76.065,-37.001L-76.337,-37.001L-76.609,-37.001L-76.881,-37.001L-77.153,-37.001L-77.425,-37.001L-77.697,-37.001L-77.969,-37.001L-78.242,-37.001L-78.514,-37.001","M-74.888,-45.943L-74.889,-46.134L-74.89,-46.324L-74.891,-46.515L-74.892,-46.706L-74.893,-46.896L-74.894,-47.087L-74.895,-47.278L-74.896,-47.469L-74.897,-47.659L-74.898,-47.85L-74.899,-48.041L-74.9,-48.231L-74.901,-48.422L-74.902,-48.613L-74.903,-48.803L-74.904,-48.993","M-74.907,-45.001L-74.901,-45.001L-74.895,-45.001L-74.89,-45.001L-74.884,-45.001L-74.884,-45.004L-74.884,-45.007L-74.884,-45.01L-74.883,-45.013L-74.885,-45.246L-74.886,-45.478L-74.887,-45.711L-74.888,-45.943","M-74.901,-43.001L-74.902,-43.251L-74.902,-43.501L-74.903,-43.751L-74.904,-44.001L-74.905,-44.251L-74.905,-44.501L-74.906,-44.751L-74.907,-45.001","M-69.521,-45.943L-69.688,-45.943L-69.856,-45.943L-70.024,-45.943L-70.192,-45.943L-70.359,-45.943L-70.527,-45.943L-70.695,-45.943L-70.862,-45.943L-71.03,-45.943L-71.198,-45.943L-71.366,-45.943L-71.533,-45.943L-71.701,-45.943L-71.869,-45.943L-72.037,-45.943L-72.204,-45.943L-72.372,-45.943L-72.54,-45.943L-72.708,-45.943L-72.875,-45.943L-73.043,-45.943L-73.211,-45.943L-73.378,-45.943L-73.546,-45.943L-73.714,-45.943L-73.882,-45.943L-74.049,-45.943L-74.217,-45.943L-74.385,-45.943L-74.553,-45.943L-74.72,-45.943L-74.888,-45.943","M-74.896,-41.001L-74.896,-41.251L-74.897,-41.501L-74.898,-41.751L-74.898,-42.001L-74.899,-42.251L-74.899,-42.501L-74.9,-42.751L-74.901,-43.001","M-73.458,-40.001L-73.458,-40.126L-73.458,-40.251L-73.458,-40.376L-73.458,-40.501L-73.458,-40.626L-73.458,-40.751L-73.458,-40.876L-73.458,-41.001L-73.638,-41.001L-73.817,-41.001L-73.997,-41.001L-74.177,-41.001L-74.356,-41.001L-74.536,-41.001L-74.716,-41.001L-74.896,-41.001","M-73.449,-37.001L-73.45,-37.188L-73.45,-37.376L-73.451,-37.563L-73.451,-37.751L-73.452,-37.938L-73.452,-38.126L-73.453,-38.313L-73.453,-38.501L-73.454,-38.688L-73.454,-38.876L-73.455,-39.064L-73.456,-39.251L-73.456,-39.439L-73.457,-39.626L-73.457,-39.814L-73.458,-40.001","M-68.65,-40.001L-68.779,-40.001L-68.93,-40.001L-69.081,-40.001L-69.232,-40.001L-69.383,-40.001L-69.534,-40.001L-69.685,-40.001L-69.836,-40.001L-69.987,-40.001L-70.138,-40.001L-70.288,-40.001L-70.439,-40.001L-70.59,-40.001L-70.741,-40.001L-70.892,-40.001L-71.043,-40.001L-71.194,-40.001L-71.345,-40.001L-71.496,-40.001L-71.647,-40.001L-71.798,-40.001L-71.949,-40.001L-72.099,-40.001L-72.25,-40.001L-72.401,-40.001L-72.552,-40.001L-72.703,-40.001L-72.854,-40.001L-73.005,-40.001L-73.156,-40.001L-73.307,-40.001L-73.458,-40.001","M-74.16,-36.501L-74.16,-36.626L-74.16,-36.751L-74.161,-36.876L-74.161,-37.001","M-73.449,-37.001L-73.627,-37.001L-73.805,-37.001L-73.983,-37.001L-74.161,-37.001","M-68.029,-33.648L-68.191,-33.699L-68.231,-33.732L-68.306,-33.768L-68.373,-33.843L-68.505,-33.937L-68.555,-33.959L-68.571,-33.956L-68.599,-33.911L-68.669,-33.874L-68.708,-33.873L-68.777,-33.887L-68.79,-33.898L-68.8,-33.926L-68.828,-33.945L-68.848,-33.93L-68.949,-33.891L-68.964,-33.865L-69.021,-33.863L-69.078,-33.883L-69.22,-33.822L-69.269,-33.774L-69.321,-33.758L-69.347,-33.711L-69.362,-33.718L-69.416,-33.775L-69.471,-33.792L-69.546,-33.849L-69.549,-33.899L-69.557,-33.906L-69.57,-33.911L-69.587,-33.906L-69.62,-33.864L-69.639,-33.853L-69.657,-33.854L-69.73,-33.883L-69.761,-33.935L-69.776,-33.95L-69.793,-33.953L-69.824,-33.938L-69.842,-33.882L-69.856,-33.867L-69.886,-33.857L-69.884,-33.828L-69.911,-33.75L-69.926,-33.735L-69.944,-33.738L-69.964,-33.757L-69.979,-33.785L-69.985,-33.808L-69.974,-33.87L-69.98,-33.891L-69.995,-33.897L-70.031,-33.868L-70.062,-33.869L-70.102,-33.84L-70.127,-33.831L-70.15,-33.839L-70.187,-33.886L-70.251,-33.916L-70.276,-33.972L-70.288,-33.988L-70.301,-33.992L-70.315,-33.99L-70.338,-33.972L-70.413,-33.899L-70.447,-33.876L-70.476,-33.871L-70.504,-33.878L-70.521,-33.897L-70.525,-33.971L-70.541,-33.994L-70.61,-34.04L-70.625,-34.084L-70.631,-34.145L-70.714,-34.135L-70.816,-34.142L-70.863,-34.088L-70.887,-34.078L-70.916,-34.089L-70.998,-34.161L-71.086,-34.147L-71.135,-34.155L-71.258,-34.209L-71.354,-34.213L-71.393,-34.223L-71.414,-34.235L-71.424,-34.318L-71.462,-34.388L-71.475,-34.407L-71.539,-34.456L-71.55,-34.458L-71.557,-34.447L-71.572,-34.392L-71.591,-34.389L-71.666,-34.405L-71.735,-34.388L-71.774,-34.416L-71.904,-34.543L-71.957,-34.576L-72,-34.587L-72,-34.706L-72,-34.826L-72,-34.946L-72,-35.065L-72,-35.185L-72,-35.305L-72,-35.424L-72.001,-35.544L-72.001,-35.663L-72.001,-35.783L-72.001,-35.903L-72.001,-36.022L-72.001,-36.142L-72.001,-36.262L-72.002,-36.381L-72.002,-36.501L-72.137,-36.501L-72.272,-36.501L-72.406,-36.501L-72.541,-36.501L-72.676,-36.501L-72.811,-36.501L-72.946,-36.501L-73.081,-36.501L-73.216,-36.501L-73.351,-36.501L-73.486,-36.501L-73.621,-36.501L-73.756,-36.501L-73.89,-36.501L-74.025,-36.501L-74.16,-36.501","M-68.125,-37.001L-68.291,-37.001L-68.458,-37.001L-68.624,-37.001L-68.791,-37.001L-68.957,-37.001L-69.123,-37.001L-69.29,-37.001L-69.456,-37.001L-69.622,-37.001L-69.789,-37.001L-69.955,-37.001L-70.122,-37.001L-70.288,-37.001L-70.454,-37.001L-70.621,-37.001L-70.787,-37.001L-70.953,-37.001L-71.12,-37.001L-71.286,-37.001L-71.453,-37.001L-71.619,-37.001L-71.785,-37.001L-71.952,-37.001L-72.118,-37.001L-72.285,-37.001L-72.451,-37.001L-72.617,-37.001L-72.784,-37.001L-72.95,-37.001L-73.116,-37.001L-73.283,-37.001L-73.449,-37.001","M-69.447,-43.501L-69.551,-43.498L-69.539,-43.435L-69.51,-43.373L-69.505,-43.338L-69.511,-43.309L-69.53,-43.283L-69.526,-43.243L-69.52,-43.232L-69.473,-43.206L-69.457,-43.17L-69.452,-43.13L-69.453,-43.099L-69.482,-43.043L-69.49,-42.969L-69.525,-42.859L-69.564,-42.791L-69.571,-42.757L-69.568,-42.73L-69.508,-42.659L-69.504,-42.63L-69.485,-42.594L-69.466,-42.511","M-68.13,-39.086L-68.129,-38.956L-68.129,-38.825L-68.129,-38.695L-68.129,-38.565L-68.128,-38.434L-68.128,-38.304L-68.128,-38.174L-68.127,-38.043L-68.127,-37.913L-68.127,-37.783L-68.126,-37.652L-68.126,-37.522L-68.126,-37.392L-68.126,-37.261L-68.125,-37.131L-68.125,-37.001","M-68.128,-39.124L-68.13,-39.086","M-68.125,-37.001L-68.125,-36.876L-68.125,-36.751L-68.125,-36.626L-68.125,-36.501","M-68.951,-40.602L-68.771,-40.603L-68.589,-40.604L-68.408,-40.606L-68.226,-40.607L-68.045,-40.609L-67.863,-40.61L-67.681,-40.612L-67.5,-40.613L-67.318,-40.615L-67.136,-40.616L-66.955,-40.617L-66.773,-40.619L-66.592,-40.62L-66.41,-40.622L-66.228,-40.623L-66.047,-40.625L-66.011,-40.552L-65.972,-40.531L-65.964,-40.507L-65.913,-40.469L-65.902,-40.432L-65.838,-40.379","M-67.71,-33.012L-67.711,-33.148L-67.712,-33.283L-67.713,-33.419L-67.714,-33.554","M-68.125,-36.501L-68.109,-36.362L-68.093,-36.222L-68.077,-36.083L-68.061,-35.944L-68.045,-35.805L-68.028,-35.666L-68.012,-35.526L-67.996,-35.387L-67.998,-35.279L-68,-35.17L-68.002,-35.061L-68.004,-34.953L-68.006,-34.844L-68.008,-34.735L-68.01,-34.627L-68.012,-34.518L-68.014,-34.409L-68.016,-34.3L-68.018,-34.192L-68.02,-34.083L-68.023,-33.974L-68.025,-33.866L-68.027,-33.757L-68.029,-33.648","M-68.125,-36.501L-67.925,-36.501L-67.724,-36.501L-67.524,-36.501L-67.323,-36.501L-67.123,-36.501L-66.922,-36.501L-66.722,-36.501L-66.521,-36.501L-66.32,-36.501L-66.12,-36.501L-65.919,-36.501L-65.719,-36.501L-65.518,-36.501L-65.318,-36.501L-65.117,-36.501L-64.917,-36.501L-64.885,-36.423L-64.854,-36.372L-64.848,-36.334L-64.854,-36.297L-64.907,-36.216L-64.956,-36.178L-64.982,-36.138L-65.018,-36.099L-65.074,-35.993L-64.956,-35.995L-64.838,-35.997L-64.719,-35.999L-64.587,-36.002","M-57.974,-40.647L-57.975,-40.753L-57.975,-40.858L-57.975,-40.962L-57.975,-41.067L-57.975,-41.172L-57.975,-41.277L-57.975,-41.382L-57.975,-41.487L-57.975,-41.591L-57.975,-41.696L-57.975,-41.801L-57.975,-41.906L-57.975,-42.011L-57.975,-42.116L-57.975,-42.22L-57.975,-42.324","M-57.224,-39.723L-57.318,-39.723L-57.411,-39.723L-57.505,-39.723L-57.599,-39.723L-57.693,-39.723L-57.786,-39.723L-57.88,-39.723L-57.974,-39.723L-57.974,-39.838L-57.974,-39.954L-57.974,-40.069L-57.974,-40.185L-57.974,-40.301L-57.974,-40.416L-57.975,-40.532L-57.974,-40.647","M-67.532,-29.977L-67.483,-30.077L-67.472,-30.113L-67.479,-30.283L-67.5,-30.345L-67.498,-30.38L-67.475,-30.473L-67.479,-30.558L-67.439,-30.661L-67.41,-30.714L-67.377,-30.824L-67.369,-30.895L-67.355,-30.948L-67.365,-31.005L-67.342,-31.046L-67.357,-31.104L-67.362,-31.18L-67.39,-31.21L-67.439,-31.323L-67.438,-31.372L-67.49,-31.478L-67.491,-31.514L-67.541,-31.569L-67.551,-31.604L-67.555,-31.75L-67.569,-31.793L-67.612,-31.877L-67.711,-31.999L-67.711,-32.126L-67.711,-32.252L-67.711,-32.379L-67.71,-32.506L-67.71,-32.632L-67.71,-32.759L-67.71,-32.885L-67.71,-33.012","M-67.71,-33.012L-67.58,-33.012L-67.451,-33.012L-67.322,-33.013L-67.192,-33.013L-67.063,-33.013L-66.934,-33.013L-66.804,-33.013L-66.675,-33.014L-66.545,-33.014L-66.416,-33.014L-66.287,-33.014L-66.157,-33.015L-66.028,-33.015L-65.899,-33.015L-65.769,-33.015L-65.628,-33.016","M-65.011,-35.001L-64.828,-35.001L-64.637,-35.001L-64.445,-35L-64.254,-35L-64.063,-35L-63.872,-34.999L-63.68,-34.999L-63.485,-34.999","M-61.205,-31.002L-61.438,-31.001L-61.67,-31.001L-61.903,-31.001L-62.136,-31.001L-62.369,-31.001L-62.602,-31.001L-62.835,-31.001L-63.067,-31.001L-63.077,-30.929L-63.073,-30.861L-63.048,-30.796L-62.944,-30.672L-62.934,-30.641L-62.952,-30.546L-62.949,-30.478L-62.96,-30.443L-62.986,-30.412L-62.992,-30.378","M-59.83,-35.002L-59.829,-35.001","M-60.714,-34.988L-60.948,-34.991L-61.181,-34.994L-61.415,-34.998L-61.649,-35.001","M-59.843,-35.001L-60.06,-34.998L-60.278,-34.995L-60.496,-34.991L-60.714,-34.988","M-59.6,-35.087L-59.715,-35.044L-59.83,-35.002L-59.843,-35.001","M-58.353,-35.066L-58.272,-35.114L-58.235,-35.058L-58.171,-34.963L-58.168,-34.907L-58.165,-34.829L-58.063,-34.825L-57.961,-34.821L-57.859,-34.817L-57.758,-34.813L-57.656,-34.809L-57.554,-34.805L-57.452,-34.801L-57.351,-34.797L-57.253,-34.683L-57.156,-34.569L-57.059,-34.454L-56.962,-34.34L-56.864,-34.226L-56.767,-34.112L-56.67,-33.998L-56.566,-33.877","M-59.296,-35.202L-59.182,-35.196L-59.068,-35.19L-58.954,-35.184L-58.84,-35.179L-58.725,-35.173L-58.611,-35.167L-58.497,-35.161L-58.383,-35.156","M-51.697,-42.012L-51.643,-42.013L-51.569,-42.014L-51.497,-42.015L-51.453,-42.016L-51.399,-42.017L-51.396,-41.972L-51.393,-41.902L-51.363,-41.891L-51.364,-41.835L-51.365,-41.798L-51.339,-41.775L-51.313,-41.751L-51.288,-41.707","M-52.906,-42.056L-52.845,-42.053L-52.785,-42.05L-52.724,-42.048L-52.664,-42.045L-52.603,-42.042L-52.543,-42.039L-52.482,-42.037L-52.422,-42.034L-52.421,-42.008L-52.39,-42.011L-52.385,-42.034L-52.299,-42.033L-52.213,-42.031L-52.127,-42.03L-52.041,-42.028L-51.955,-42.027L-51.869,-42.026L-51.783,-42.024L-51.697,-42.023L-51.697,-42.012","M-51.697,-42.012L-51.696,-41.958L-51.696,-41.883L-51.695,-41.829L-51.695,-41.753L-51.694,-41.668L-51.693,-41.589L-51.693,-41.52L-51.695,-41.479L-51.699,-41.417L-51.718,-41.393L-51.726,-41.336","M-59.015,-37.54L-59.01,-37.508L-59.019,-37.473L-58.996,-37.433L-58.977,-37.369L-58.95,-37.33L-58.917,-37.299L-58.862,-37.271L-58.796,-37.222L-58.744,-37.208L-58.727,-37.21L-58.67,-37.257L-58.622,-37.282L-58.572,-37.334L-58.484,-37.263L-58.448,-37.263L-58.361,-37.294L-58.279,-37.302L-58.259,-37.311L-58.229,-37.341L-58.228,-37.399L-58.221,-37.415L-58.207,-37.422L-58.191,-37.423L-58.154,-37.402L-58.118,-37.401L-57.965,-37.469L-57.954,-37.464L-57.934,-37.433L-57.867,-37.473L-57.828,-37.51L-57.81,-37.566L-57.777,-37.621L-57.784,-37.645L-57.805,-37.677L-57.777,-37.751L-57.735,-37.824L-57.58,-38.046L-57.53,-38.181L-57.465,-38.267L-57.444,-38.336L-57.395,-38.404L-57.361,-38.544L-57.341,-38.572L-57.31,-38.577L-57.28,-38.559L-57.258,-38.533L-57.243,-38.491L-57.165,-38.454L-57.099,-38.45L-57.053,-38.477L-57.026,-38.526L-56.99,-38.618L-56.955,-38.673L-56.933,-38.742L-56.91,-38.79L-56.874,-38.82L-56.785,-38.818L-56.74,-38.86L-56.705,-38.908L-56.684,-38.924L-56.659,-38.922L-56.579,-38.999L-56.473,-39.161L-56.451,-39.263L-56.423,-39.336L-56.413,-39.411L-56.392,-39.452L-56.299,-39.37L-56.245,-39.323L-56.123,-39.216L-56.042,-39.145L-56.01,-39.227L-55.963,-39.346","M-57.224,-39.723L-57.058,-39.723L-56.891,-39.723L-56.725,-39.723L-56.559,-39.723L-56.393,-39.723L-56.227,-39.723L-56.061,-39.723L-55.894,-39.723L-55.728,-39.723L-55.562,-39.723L-55.396,-39.723L-55.23,-39.722L-55.064,-39.722L-54.897,-39.722L-54.731,-39.722L-54.565,-39.722","M-57.224,-39.723L-57.226,-39.595L-57.228,-39.467L-57.229,-39.339L-57.231,-39.211","M-54.565,-39.722L-54.558,-39.564L-54.551,-39.406L-54.544,-39.247L-54.537,-39.089L-54.53,-38.93L-54.523,-38.772L-54.516,-38.613L-54.509,-38.455L-54.507,-38.455L-54.506,-38.455L-54.504,-38.455L-54.502,-38.455L-54.501,-38.455L-54.499,-38.455L-54.497,-38.455L-54.496,-38.455L-54.423,-38.455L-54.264,-38.455L-54.104,-38.455L-54.027,-38.456","M-54.475,-37.954L-54.446,-37.999L-54.338,-38.015L-54.271,-38.025L-54.182,-38.037L-54.161,-38.041","M-55.454,-38.807L-55.39,-38.888L-55.432,-38.952L-55.47,-39.012L-55.528,-38.944","M-53.783,-41.357L-53.799,-41.395L-53.825,-41.424L-53.953,-41.474L-53.987,-41.508L-54.016,-41.553L-54.037,-41.608L-54.048,-41.667L-54.048,-41.713L-54.039,-41.765L-54.068,-41.799L-54.069,-41.832L-54.088,-41.853L-54.172,-41.892L-54.197,-41.947L-54.253,-41.998L-54.352,-41.998L-54.451,-41.999L-54.551,-41.999L-54.65,-41.999L-54.749,-41.999L-54.849,-41.999L-54.948,-41.999L-55.047,-41.999L-55.146,-41.999L-55.246,-41.999L-55.345,-41.999L-55.444,-41.999L-55.543,-41.999L-55.643,-42L-55.742,-42L-55.841,-42L-55.94,-42L-56.04,-42L-56.139,-42L-56.238,-42L-56.337,-42L-56.437,-42L-56.536,-42L-56.635,-42L-56.734,-42L-56.834,-42L-56.933,-42.001L-57.032,-42.001L-57.132,-42.001L-57.231,-42.001L-57.33,-42.001L-57.429,-42.001L-57.429,-42.136L-57.429,-42.27L-57.429,-42.405L-57.429,-42.539","M-52.742,-42.752L-52.765,-42.668L-52.788,-42.584L-52.811,-42.5L-52.834,-42.416L-52.857,-42.332L-52.88,-42.248L-52.902,-42.164L-52.925,-42.08L-52.906,-42.056","M-52.906,-42.056L-52.912,-41.961L-52.918,-41.866L-52.923,-41.771L-52.929,-41.676L-52.935,-41.581L-52.941,-41.486L-52.946,-41.391L-52.952,-41.296L-52.93,-41.257L-52.909,-41.219L-52.936,-41.201L-52.977,-41.173L-53.022,-41.143L-53.081,-41.105L-53.051,-41.055L-53.014,-40.992","M-53.783,-41.357L-53.712,-41.312L-53.641,-41.266L-53.569,-41.22L-53.498,-41.175L-53.427,-41.129L-53.356,-41.083L-53.284,-41.037L-53.215,-40.992","M-52.176,-42.73L-52.247,-42.733L-52.318,-42.736L-52.388,-42.739L-52.459,-42.741L-52.53,-42.744L-52.601,-42.747L-52.672,-42.749L-52.742,-42.752","M-52.742,-42.752L-52.762,-42.813L-52.752,-42.865L-52.75,-42.935L-52.749,-43.027L-52.747,-43.128L-52.744,-43.265L-52.742,-43.357L-52.74,-43.44L-52.738,-43.553L-52.78,-43.616L-52.798,-43.627L-52.811,-43.62L-52.842,-43.579L-52.852,-43.579L-52.859,-43.59L-52.858,-43.628L-52.831,-43.762L-52.83,-43.804L-52.836,-43.876L-52.866,-44.038L-52.867,-44.075L-52.855,-44.131L-52.834,-44.187L-52.799,-44.245L-52.791,-44.269L-52.794,-44.368L-52.783,-44.46L-52.828,-44.597L-52.811,-44.775L-52.823,-44.86L-52.808,-44.939L-52.814,-45.005","M-50.98,-42.877L-51.065,-42.882L-51.101,-42.872L-51.175,-42.825L-51.22,-42.808L-51.294,-42.73L-51.357,-42.702L-51.46,-42.706L-51.562,-42.709L-51.664,-42.713L-51.767,-42.716L-51.869,-42.72L-51.971,-42.723L-52.074,-42.727L-52.176,-42.73","M-50.928,-43.07L-50.985,-43.164L-50.997,-43.239L-51.062,-43.328L-51.088,-43.389L-51.097,-43.458L-51.093,-43.532L-51.098,-43.643L-51.104,-43.754L-51.109,-43.865L-51.115,-43.976L-51.121,-44.086L-51.126,-44.197L-51.132,-44.308L-51.137,-44.419L-51.143,-44.53L-51.148,-44.641L-51.154,-44.751L-51.159,-44.862L-51.165,-44.973L-51.17,-45.084L-51.176,-45.195L-51.181,-45.294","M-69.447,-43.501L-69.447,-43.726L-69.447,-43.95L-69.447,-44.175L-69.447,-44.399L-69.447,-44.624L-69.447,-44.848L-69.447,-45.073L-69.447,-45.297L-69.501,-45.372L-69.621,-45.432L-69.651,-45.468L-69.707,-45.557L-69.729,-45.596L-69.733,-45.626L-69.706,-45.659L-69.597,-45.756L-69.563,-45.8L-69.546,-45.843L-69.521,-45.943","M-65.697,-43.502L-65.934,-43.502L-66.168,-43.502L-66.403,-43.502L-66.637,-43.502L-66.871,-43.502L-67.105,-43.502L-67.339,-43.502L-67.573,-43.502L-67.808,-43.502L-68.042,-43.501L-68.276,-43.501L-68.51,-43.501L-68.744,-43.501L-68.978,-43.501L-69.212,-43.501L-69.447,-43.501","M-61.053,-41.701L-60.813,-41.711L-60.574,-41.72L-60.334,-41.73L-60.094,-41.739L-59.979,-41.838L-59.848,-41.95","M-64.77,-47.287L-64.687,-47.464L-64.604,-47.642L-64.522,-47.819L-64.439,-47.998","M-62.799,-41.761L-62.767,-41.944L-62.734,-42.127L-62.701,-42.31L-62.668,-42.493","M-65.268,-42.513L-64.938,-42.51L-64.613,-42.508L-64.289,-42.505L-63.965,-42.503L-63.641,-42.5L-63.317,-42.498L-62.992,-42.495L-62.668,-42.493","M-61.072,-39.092L-61.071,-39.424L-61.068,-39.749L-61.066,-40.075L-61.063,-40.4L-61.061,-40.725L-61.058,-41.051L-61.056,-41.376L-61.053,-41.701","M-62.799,-41.761L-62.581,-41.761L-62.363,-41.76L-62.145,-41.76L-61.926,-41.76L-61.708,-41.76L-61.49,-41.76L-61.272,-41.76L-61.053,-41.76L-61.053,-41.701","M-62.668,-42.493L-62.697,-42.782L-62.722,-43.031L-62.752,-43.327L-62.745,-43.571L-62.742,-43.658L-62.7,-43.89L-62.663,-44.091L-62.581,-44.362L-62.512,-44.591L-62.435,-44.846L-62.306,-45.041L-62.209,-45.133L-62.11,-45.227L-62.267,-45.323L-62.477,-45.452L-62.598,-45.452L-62.723,-45.452L-62.816,-45.29L-62.942,-45.184L-62.971,-45.068L-63.111,-45.122L-63.14,-45.161L-63.158,-45.201L-63.159,-45.243L-63.117,-45.345L-63.113,-45.362L-63.118,-45.371L-63.141,-45.383L-63.193,-45.364L-63.246,-45.361L-63.263,-45.368L-63.27,-45.385L-63.269,-45.413L-63.259,-45.445L-63.227,-45.506L-63.227,-45.563L-63.212,-45.596L-63.226,-45.657L-63.223,-45.686L-63.245,-45.718L-63.304,-45.76L-63.444,-45.816L-63.429,-45.878L-63.435,-45.905L-63.469,-45.945L-63.615,-45.992L-63.715,-46.014L-63.813,-46.014L-63.884,-46.031L-63.963,-46.037L-64.014,-46.065L-64.064,-46.093L-64.115,-46.121L-64.166,-46.149L-64.256,-46.173L-64.346,-46.197L-64.436,-46.221L-64.526,-46.245L-64.616,-46.269L-64.706,-46.294L-64.795,-46.318L-64.885,-46.342L-64.905,-46.384L-64.926,-46.426L-64.946,-46.468L-64.966,-46.51L-65.007,-46.527L-65.029,-46.537L-65.045,-46.558L-65.082,-46.549L-65.097,-46.585L-65.056,-46.673L-65.015,-46.761L-64.974,-46.848L-64.933,-46.936L-64.892,-47.024L-64.851,-47.112L-64.81,-47.199L-64.77,-47.287","M-65.993,-31.002L-65.82,-31.001L-65.647,-31.001L-65.474,-31.001L-65.301,-31.001L-65.128,-31.001L-64.955,-31.001L-64.782,-31.001L-64.609,-31.001","M-64.431,-36.503L-64.481,-36.501","M-82.52,-34.991L-82.715,-35.203L-82.898,-35.401L-83.081,-35.599L-83.264,-35.797L-83.446,-35.995L-83.629,-36.194L-83.812,-36.392L-83.995,-36.59L-84.127,-36.728L-84.259,-36.866L-84.391,-37.003L-84.523,-37.141L-84.655,-37.279L-84.787,-37.417L-84.919,-37.555L-85.051,-37.692L-85.22,-37.856L-85.388,-38.019L-85.557,-38.183L-85.725,-38.346L-85.894,-38.51L-86.063,-38.673L-86.231,-38.837L-86.4,-39L-86.4,-39.188L-86.4,-39.375L-86.4,-39.563L-86.4,-39.75L-86.4,-39.938L-86.4,-40.125L-86.4,-40.313L-86.4,-40.5L-86.4,-40.688L-86.4,-40.875L-86.4,-41.063L-86.4,-41.251L-86.4,-41.438L-86.401,-41.626L-86.401,-41.813L-86.401,-42.001","M-48.681,-47.999L-48.772,-47.999L-48.898,-47.999L-48.977,-47.999L-49.042,-47.999L-49.042,-47.929L-49.142,-47.929L-49.232,-47.929L-49.232,-47.838L-49.233,-47.765L-49.233,-47.692L-49.233,-47.589","M-89.15,-60.001L-89.835,-60.001L-90.52,-60.001L-91.206,-60.001L-91.891,-60.001L-92.576,-60.001L-93.261,-60.001L-93.947,-60.001L-94.632,-60.001L-95.317,-60.001L-96.002,-60.001L-96.688,-60.001L-97.373,-60.001L-98.058,-60.001L-98.743,-60.001L-99.429,-60.001L-100.121,-60.002","M-86.4,-60.001L-86.744,-60.001L-87.087,-60.001L-87.431,-60.001L-87.775,-60.001L-88.119,-60.001L-88.462,-60.001L-88.806,-60.001L-89.15,-60.001","M-46.102,-46.013L-46.117,-45.978L-46.195,-45.965L-46.236,-45.901L-46.276,-45.85L-46.307,-45.836","M-46.522,-60.306L-46.667,-60.267L-46.69,-60.251L-46.69,-60.238L-46.648,-60.196L-46.544,-60.161L-46.528,-60.141L-46.548,-60.11L-46.592,-60.091L-46.643,-60.064L-46.714,-60.05L-46.719,-60.035L-46.705,-60.009L-46.681,-59.986L-46.571,-59.943L-46.559,-59.933L-46.556,-59.922L-46.559,-59.906L-46.629,-59.864L-46.649,-59.816L-46.669,-59.54L-46.638,-59.488L-46.595,-59.466L-46.4,-59.528L-46.357,-59.515L-46.353,-59.475L-46.387,-59.456L-46.442,-59.399L-46.453,-59.356L-46.454,-59.226L-46.444,-59.166L-46.424,-59.116L-46.398,-59.091L-46.319,-59.044L-46.314,-59.02L-46.338,-59.002L-46.363,-58.998L-46.635,-59.049L-46.657,-59.04L-46.68,-59.02L-46.693,-58.984L-46.691,-58.949L-46.662,-58.929L-46.525,-58.911L-46.292,-58.866L-46.25,-58.786L-46.218,-58.769L-46.192,-58.771L-46.073,-58.811L-45.884,-58.862L-45.839,-58.854L-45.786,-58.83L-45.745,-58.799L-45.723,-58.771L-45.718,-58.753L-45.724,-58.743L-45.758,-58.732L-46.052,-58.684L-46.103,-58.666L-46.131,-58.642L-46.141,-58.621L-46.142,-58.599L-46.125,-58.555L-46.108,-58.545L-45.995,-58.555L-45.965,-58.505L-45.963,-58.483L-45.971,-58.46L-46.096,-58.399L-46.15,-58.359L-46.347,-58.169L-46.364,-58.144L-46.368,-58.121L-46.359,-58.099L-46.243,-58.018L-46.176,-57.875L-46.137,-57.813L-46.113,-57.785L-46.07,-57.803L-46.052,-57.802L-46.023,-57.783L-45.988,-57.731L-45.966,-57.713L-45.931,-57.706L-45.875,-57.696L-45.805,-57.726L-45.793,-57.723L-45.791,-57.692L-45.803,-57.669L-45.895,-57.581L-45.906,-57.553L-45.908,-57.513L-45.894,-57.396L-45.936,-57.319L-45.931,-57.279L-45.907,-57.241L-45.906,-57.228L-45.93,-57.13L-45.962,-57.083L-45.991,-57.023L-46.01,-56.889L-46.044,-56.863L-46.083,-56.821L-46.102,-56.787L-46.152,-56.738L-46.163,-56.707L-46.161,-56.691L-46.048,-56.527L-46.026,-56.475L-46.048,-56.439L-46.118,-56.43L-46.178,-56.395L-46.165,-56.334L-46.167,-56.299L-46.163,-56.289L-46.14,-56.275L-46.017,-56.229L-46.008,-56.212L-46.074,-56.145L-46.083,-56.097L-46.057,-56.095L-45.998,-56.088L-45.962,-56.063L-45.776,-56.026L-45.762,-55.992L-45.782,-55.976L-45.836,-55.948L-45.863,-55.923L-45.87,-55.883L-45.864,-55.861L-45.738,-55.706L-45.659,-55.596L-45.622,-55.565L-45.579,-55.542L-45.471,-55.514L-45.469,-55.484L-45.475,-55.44L-45.469,-55.404L-45.441,-55.34L-45.476,-55.307L-45.669,-55.21L-45.728,-55.168L-45.744,-55.14L-45.757,-55.086L-45.706,-54.987L-45.703,-54.962L-45.714,-54.918L-45.77,-54.776L-45.834,-54.644L-45.863,-54.615L-45.901,-54.612L-46.015,-54.634L-46.326,-54.726L-46.667,-54.734L-46.888,-54.719L-47.287,-54.745L-47.334,-54.769L-47.374,-54.805L-47.425,-54.898L-47.436,-54.907L-47.58,-54.942L-47.633,-54.968L-47.693,-55.008L-47.965,-55.256L-48.048,-55.319L-48.077,-55.328L-48.096,-55.311L-48.094,-55.294L-48.042,-55.213L-48.038,-55.193L-48.058,-55.129L-48.019,-54.998L-48.031,-54.948L-47.993,-54.847L-47.989,-54.799L-48.042,-54.748L-48.144,-54.781L-48.36,-54.937L-48.457,-55.064L-48.484,-55.075L-48.534,-55.072L-48.547,-55.059L-48.555,-55.036L-48.539,-54.984L-48.508,-54.917L-48.449,-54.826L-48.387,-54.699L-48.383,-54.682L-48.346,-54.653L-48.348,-54.617L-48.41,-54.586L-48.446,-54.519L-48.466,-54.517L-48.626,-54.573L-48.657,-54.565L-48.673,-54.553L-48.686,-54.507L-48.679,-54.452L-48.659,-54.392L-48.611,-54.282L-48.606,-54.253L-48.608,-54.236L-48.73,-54.141L-48.767,-54.1L-48.788,-54.061L-48.785,-54.034L-48.622,-53.839L-48.579,-53.796L-48.568,-53.73L-48.583,-53.635L-48.581,-53.613L-48.569,-53.601L-48.359,-53.543L-48.333,-53.503L-48.295,-53.417L-48.259,-53.393L-48.226,-53.384L-48.2,-53.355L-48.195,-53.329L-48.215,-53.183L-48.219,-53.073L-48.26,-52.98L-48.279,-52.92L-48.29,-52.833L-48.289,-52.755L-48.261,-52.72L-48.205,-52.698L-48.166,-52.694L-48.136,-52.698L-48.107,-52.687L-48.016,-52.727L-48.003,-52.749L-47.975,-52.91L-47.963,-52.932L-47.895,-52.958L-47.873,-53.005L-47.857,-53.019L-47.828,-53.011L-47.801,-52.992L-47.756,-52.934L-47.736,-52.897L-47.744,-52.861L-47.766,-52.84L-47.777,-52.806L-47.784,-52.741L-47.82,-52.688L-47.827,-52.661L-47.804,-52.418L-47.809,-52.398L-47.854,-52.341L-47.853,-52.295L-47.836,-52.229L-47.813,-52.184L-47.793,-52.165L-47.769,-52.155L-47.755,-52.189L-47.733,-52.295L-47.721,-52.301L-47.627,-52.23L-47.59,-52.21L-47.546,-52.109L-47.505,-52.081L-47.436,-52.054L-47.395,-52.052L-47.38,-52.064L-47.362,-52.104L-47.297,-52.094L-47.254,-52.073L-47.224,-52.073L-47.197,-52.094L-47.141,-52.196L-47.126,-52.203L-47.087,-52.203L-46.993,-52.185L-46.899,-52.155L-46.826,-52.113L-46.751,-52.055L-46.631,-51.905L-46.554,-51.849L-46.531,-51.825L-46.54,-51.791L-46.579,-51.763L-46.586,-51.745L-46.582,-51.72L-46.511,-51.6L-46.445,-51.609L-46.289,-51.729L-46.288,-51.769L-46.315,-51.811L-46.321,-51.842L-46.311,-51.93L-46.275,-52.083L-46.267,-52.1L-46.195,-52.148L-46.174,-52.187L-46.154,-52.378L-46.212,-52.554L-46.215,-52.626L-46.209,-52.815L-46.18,-52.854L-46.086,-52.878L-46.061,-52.895L-46.021,-53.066L-46.012,-53.077L-45.935,-53.104L-45.88,-53.109L-45.844,-53.101L-45.796,-53.035L-45.759,-52.964L-45.755,-52.94L-45.768,-52.826L-45.766,-52.797L-45.756,-52.774L-45.655,-52.689L-45.664,-52.67L-45.736,-52.649L-45.944,-52.611L-46.007,-52.589L-46.048,-52.566L-46.093,-52.525L-46.123,-52.485L-46.128,-52.466L-46.124,-52.458L-46.045,-52.429L-46.039,-52.418L-46.034,-52.381L-45.996,-52.345L-45.911,-52.298L-45.852,-52.138L-45.841,-52.094L-45.838,-52.06L-45.867,-52.048L-45.926,-52.051L-45.93,-52.044L-45.924,-52.02L-45.905,-52.011L-45.797,-52.001L-45.504,-52.001L-45.211,-52.001L-44.918,-52.001L-44.626,-52.001L-44.333,-52.001L-44.04,-52.001L-43.747,-52.001L-43.455,-52.001L-43.162,-52.001L-42.869,-52.001L-42.577,-52.001L-42.284,-52.001L-41.991,-52.001L-41.698,-52.001L-41.405,-52.001L-41.113,-52.001L-41.113,-51.711L-41.112,-51.443","M-73.441,-60.001L-73.441,-60.242L-73.442,-60.482L-73.442,-60.723L-73.442,-60.963L-73.442,-61.204L-73.442,-61.444L-73.442,-61.685L-73.443,-61.925L-73.443,-62.166L-73.443,-62.406L-73.443,-62.647L-73.443,-62.887L-73.443,-63.128L-73.444,-63.368L-73.444,-63.609L-73.444,-63.849L-73.43,-64.08L-73.439,-64.228L-73.753,-64.263L-74.067,-64.297L-74.381,-64.332L-74.695,-64.366L-75.008,-64.401L-75.322,-64.435L-75.636,-64.469L-75.95,-64.504L-76.264,-64.538L-76.578,-64.573L-76.891,-64.607L-77.205,-64.642L-77.519,-64.676L-77.833,-64.71L-78.147,-64.745L-78.461,-64.779L-78.635,-64.813L-78.852,-64.903L-79.059,-65.051L-79.267,-65.2L-79.474,-65.349L-79.682,-65.497L-80.012,-65.498L-80.342,-65.5L-80.673,-65.501L-81.003,-65.502L-81.187,-65.58L-81.371,-65.659L-81.555,-65.737L-81.738,-65.815L-81.922,-65.893L-82.106,-65.971L-82.29,-66.049L-82.474,-66.127L-82.658,-66.206L-82.842,-66.284L-83.026,-66.362L-83.21,-66.44L-83.394,-66.518L-83.578,-66.596L-83.762,-66.674L-83.945,-66.753L-84.129,-66.831L-84.313,-66.909L-84.497,-66.987L-84.681,-67.065L-84.865,-67.143L-85.049,-67.221L-85.233,-67.3L-85.417,-67.378L-85.601,-67.456L-85.785,-67.534L-85.969,-67.612L-86.152,-67.69L-86.336,-67.768L-86.52,-67.847L-86.704,-67.925L-86.888,-68.003L-86.888,-68.209L-86.889,-68.414L-86.889,-68.62L-86.889,-68.826L-86.889,-69.031L-86.89,-69.237L-86.891,-69.567L-86.89,-69.649L-86.546,-69.649L-86.202,-69.649L-85.857,-69.649L-85.513,-69.649L-85.169,-69.649L-84.825,-69.649L-84.48,-69.649L-84.136,-69.65L-83.988,-69.65L-84.019,-69.695L-84.111,-69.76L-84.203,-69.825L-84.294,-69.889L-84.28,-70.002L-83.949,-70.002L-83.569,-70.002L-83.188,-70.002L-82.808,-70.002L-82.428,-70.002L-82.048,-70.001L-81.667,-70.001L-81.274,-70.001L-81.272,-69.912L-81.27,-69.833L-81.189,-69.834L-81.108,-69.834L-81,-69.912L-81,-70.001L-80.775,-70.001L-80.55,-70.001L-80.325,-70.001L-80.1,-70.001L-79.875,-70.001L-79.65,-70.001L-79.425,-70.001L-79.2,-70.001L-79.2,-70.544L-79.2,-71.087L-79.201,-71.63L-79.201,-72.173L-79.201,-72.716L-79.201,-72.982L-79.201,-73.259L-79.201,-73.802L-79.201,-74.345L-79.202,-74.851L-79.202,-74.888L-79.202,-75.43L-79.202,-75.973L-79.202,-76.244L-79.202,-76.48L-79.202,-76.516L-79.202,-77.059L-79.202,-77.602L-79.203,-77.929L-79.203,-78.09L-79.203,-78.145L-79.203,-78.322L-79.203,-78.687","M-73.441,-60.001L-73.801,-60.001L-74.161,-60.001L-74.521,-60.001L-74.881,-60.001L-75.241,-60.001L-75.601,-60.001L-75.961,-60.001L-76.321,-60.001L-76.681,-60.001L-77.04,-60.001L-77.4,-60.001L-77.76,-60.001L-78.12,-60.001L-78.48,-60.001L-78.84,-60.001L-79.2,-60.001","M-86.4,-60.001L-85.95,-60.001L-85.5,-60.001L-85.05,-60.001L-84.6,-60.001L-84.15,-60.001L-83.7,-60.001L-83.25,-60.001L-82.8,-60.001L-82.35,-60.001L-81.9,-60.001L-81.45,-60.001L-81,-60.001L-80.55,-60.001L-80.1,-60.001L-79.65,-60.001L-79.2,-60.001","M-79.2,-60.001L-79.2,-59.657L-79.2,-59.313L-79.2,-58.969L-79.2,-58.625L-79.2,-58.281L-79.2,-57.937L-79.2,-57.593L-79.2,-57.249L-79.2,-56.905L-79.2,-56.561L-79.2,-56.217L-79.2,-55.873L-79.2,-55.529L-79.2,-55.185L-79.2,-54.842L-79.2,-54.498L-79.2,-54.154L-79.2,-53.81L-79.2,-53.466L-79.2,-53.122L-79.2,-52.778L-79.2,-52.434L-79.2,-52.09L-79.2,-51.746L-79.2,-51.402L-79.2,-51.058L-79.2,-50.714L-79.2,-50.37L-79.2,-50.026L-79.2,-49.682L-79.2,-49.338L-79.2,-48.993","M-64.043,-56.851L-64.228,-56.695L-64.414,-56.535L-64.6,-56.376L-64.786,-56.216L-65.038,-55.991L-65.289,-55.767L-65.541,-55.542L-65.792,-55.317L-66.012,-55.108L-66.232,-54.899L-66.452,-54.69L-66.672,-54.481L-66.856,-54.298L-67.039,-54.114L-67.223,-53.931L-67.407,-53.748L-67.683,-53.517L-67.959,-53.285L-68.235,-53.054L-68.511,-52.822L-68.511,-52.391L-68.512,-51.96L-68.513,-51.528L-68.513,-51.097L-68.514,-50.665L-68.515,-50.234L-68.515,-49.802L-68.512,-49.37","M-73.441,-60.001L-73.117,-60.001L-72.793,-60.001L-72.469,-60.001L-72.145,-60.001L-71.821,-60.001L-71.498,-60.001L-71.174,-60.001L-70.85,-60.001L-70.526,-60.001L-70.202,-60.001L-69.878,-60.001L-69.554,-60.001L-69.23,-60.001L-68.906,-60.001L-68.582,-60.001L-68.236,-60.002","M-73.441,-60.001L-73.441,-59.74L-73.441,-59.478L-73.441,-59.217L-73.441,-58.955L-73.441,-58.694L-73.441,-58.432L-73.441,-58.171L-73.441,-57.909L-73.441,-57.648L-73.441,-57.386L-73.441,-57.125L-73.441,-56.863L-73.441,-56.602L-73.441,-56.34L-73.441,-56.079L-73.441,-55.818L-73.412,-55.391L-73.383,-54.965L-73.355,-54.538L-73.326,-54.112L-73.298,-53.685L-73.269,-53.259L-73.24,-52.832L-73.212,-52.406L-73.183,-51.979L-73.154,-51.553L-73.126,-51.126L-73.097,-50.7L-73.068,-50.273L-73.04,-49.847L-73.011,-49.421L-72.984,-48.993","M-84.165,-46.002L-84.344,-46.002L-84.535,-46.002L-84.726,-46.002L-84.917,-46.002L-85.108,-46.001L-85.3,-46.001L-85.491,-46.001L-85.682,-46.001L-85.694,-46L-85.716,-45.981L-85.808,-45.945L-85.989,-45.934L-86.353,-45.838L-86.512,-45.762L-86.653,-45.725L-86.915,-45.69L-87.153,-45.639L-87.253,-45.644L-87.295,-45.687L-87.41,-45.712L-87.597,-45.718L-87.755,-45.689L-87.901,-45.603L-87.948,-45.594L-87.948,-45.594L-87.986,-45.591L-88.244,-45.625L-88.308,-45.627L-88.363,-45.674L-88.377,-45.75L-88.447,-45.978L-88.518,-46.115L-88.59,-46.16L-88.647,-46.179L-88.719,-46.154","M-84.165,-46.002L-84.19,-46.056L-84.202,-46.124L-84.184,-46.164L-84.199,-46.232L-84.247,-46.33L-84.268,-46.397L-84.263,-46.42L-84.258,-46.429L-84.259,-46.589L-84.259,-46.75L-84.26,-46.91L-84.26,-47.07L-84.261,-47.231L-84.262,-47.391L-84.262,-47.551L-84.263,-47.712L-84.263,-47.872L-84.264,-48.032L-84.265,-48.192L-84.265,-48.353L-84.266,-48.513L-84.266,-48.673L-84.267,-48.834L-84.268,-48.993","M-84.252,-42.001L-84.252,-42.224L-84.253,-42.447L-84.253,-42.67L-84.253,-42.893L-84.254,-43.117L-84.254,-43.34L-84.254,-43.563L-84.255,-43.808L-84.255,-43.813L-84.209,-43.964L-84.2,-44.038L-84.212,-44.079L-84.204,-44.119L-84.176,-44.157L-84.177,-44.199L-84.206,-44.245L-84.261,-44.276L-84.341,-44.29L-84.382,-44.344L-84.385,-44.436L-84.326,-44.578L-84.203,-44.77L-84.136,-44.906L-84.124,-44.985L-84.051,-45.169L-83.915,-45.457L-83.863,-45.641L-83.895,-45.722L-83.964,-45.799L-84.071,-45.873L-84.146,-45.958L-84.165,-46.002","M-82.52,-34.991L-82.52,-34.907L-82.481,-34.795L-82.367,-34.59L-82.353,-34.541L-82.351,-34.54L-82.347,-34.488L-82.302,-34.433L-82.194,-34.355L-82.17,-34.317L-82.17,-34.314L-82.17,-34.287L-82.198,-34.253L-82.317,-34.142L-82.381,-34.051L-82.447,-33.904L-82.436,-33.785L-82.439,-33.686L-82.456,-33.608L-82.48,-33.536L-82.514,-33.47L-82.549,-33.431L-82.585,-33.418L-82.598,-33.331L-82.587,-33.17L-82.547,-33.072L-82.476,-33.037L-82.433,-32.984L-82.418,-32.912L-82.424,-32.842L-82.452,-32.773L-82.499,-32.735L-82.599,-32.724L-82.599,-32.724L-82.602,-32.715","M-82.52,-34.991L-82.52,-34.998L-82.506,-35.353L-82.547,-35.476L-82.557,-35.545L-82.545,-35.631L-82.548,-35.684L-82.567,-35.73L-82.572,-35.814L-82.575,-35.917L-82.607,-35.984L-82.614,-36.014L-82.595,-36.085L-82.562,-36.122L-82.507,-36.148L-82.444,-36.156L-82.372,-36.148L-82.319,-36.116L-82.283,-36.06L-82.247,-36.032L-82.212,-36.03L-82.166,-36.077L-82.125,-36.175L-82.111,-36.182L-82.11,-36.612L-82.109,-37.004","M-74.16,-36.501L-74.19,-36.501L-74.191,-36.219L-74.192,-35.938L-74.194,-35.657L-74.195,-35.376L-74.196,-35.095L-74.197,-34.814L-74.198,-34.533L-74.199,-34.252L-74.2,-33.971L-74.201,-33.689L-74.202,-33.408L-74.203,-33.127L-74.204,-32.846L-74.205,-32.565L-74.206,-32.284L-74.207,-32.003L-74.369,-32.003L-74.531,-32.003L-74.693,-32.002L-74.855,-32.002L-75.016,-32.002L-75.178,-32.002L-75.34,-32.002L-75.502,-32.002L-75.664,-32.002L-75.826,-32.002L-75.988,-32.002L-76.149,-32.002L-76.311,-32.002L-76.473,-32.001L-76.635,-32.001L-76.797,-32.001L-76.801,-32.001L-76.728,-31.82L-76.728,-31.82L-76.641,-31.768","M-68.65,-40.001L-68.484,-39.872L-68.44,-39.871L-68.388,-39.891L-68.35,-39.861L-68.323,-39.782L-68.327,-39.741L-68.361,-39.739L-68.403,-39.692L-68.454,-39.597L-68.442,-39.509L-68.366,-39.426L-68.315,-39.343L-68.29,-39.259L-68.24,-39.194L-68.128,-39.124","M-68.951,-40.602L-68.932,-40.571L-68.893,-40.466L-68.876,-40.363L-68.837,-40.295L-68.775,-40.265L-68.734,-40.198L-68.713,-40.096L-68.661,-40.01L-68.65,-40.001","M-69.466,-42.511L-69.445,-42.506L-69.396,-42.418L-69.376,-42.26L-69.333,-42.133L-69.265,-42.036L-69.231,-41.965L-69.231,-41.92L-69.214,-41.872L-69.182,-41.821L-69.17,-41.734L-69.176,-41.611L-69.162,-41.546L-69.128,-41.538L-69.113,-41.52L-69.118,-41.494L-69.107,-41.474L-69.079,-41.461L-69.072,-41.425L-69.084,-41.367L-69.074,-41.331L-69.042,-41.316L-69.036,-41.288L-69.056,-41.245L-69.053,-41.212L-69.027,-41.188L-69.01,-41.08L-69,-40.889L-69.003,-40.778L-69.018,-40.745L-68.995,-40.676L-68.951,-40.602","M-69.466,-42.511L-69.522,-42.525L-69.576,-42.569L-69.606,-42.638L-69.699,-42.701L-69.854,-42.76L-69.958,-42.813L-70.012,-42.861L-70.14,-42.881L-70.343,-42.875L-70.474,-42.85L-70.535,-42.806L-70.663,-42.852L-70.878,-43.001L-71.163,-43.001L-71.412,-43.001L-71.661,-43.001L-71.91,-43.001L-72.16,-43.001L-72.409,-43.001L-72.658,-43.001L-72.907,-43.001L-73.156,-43.001L-73.406,-43.001L-73.655,-43.001L-73.904,-43.001L-74.153,-43.001L-74.402,-43.001L-74.652,-43.001L-74.901,-43.001","M-65.628,-33.016L-65.624,-32.967L-65.589,-32.938L-65.587,-32.885L-65.618,-32.809L-65.618,-32.756L-65.586,-32.726L-65.588,-32.694L-65.623,-32.661L-65.628,-32.625L-65.604,-32.586L-65.593,-32.541L-65.595,-32.49L-65.563,-32.424L-65.513,-32.381L-65.48,-32.331L-65.477,-32.303L-65.475,-32.277L-65.482,-32.24L-65.523,-32.186L-65.555,-32.146L-65.574,-32.131L-65.584,-32.104L-65.587,-32.046L-65.633,-31.971L-65.726,-31.884L-65.788,-31.774L-65.819,-31.64L-65.851,-31.555L-65.884,-31.519L-65.901,-31.449L-65.901,-31.345L-65.922,-31.288L-65.965,-31.277L-65.974,-31.218L-65.949,-31.11L-65.96,-31.065L-65.99,-31.03L-65.993,-31.002","M-65.011,-35.001L-65.011,-34.97L-65.003,-34.945L-65.03,-34.899L-65.099,-34.852L-65.137,-34.805L-65.142,-34.76L-65.158,-34.738L-65.188,-34.728L-65.206,-34.661L-65.22,-34.504L-65.258,-34.414L-65.317,-34.392L-65.349,-34.356L-65.353,-34.308L-65.388,-34.252L-65.455,-34.189L-65.477,-34.129L-65.454,-34.072L-65.459,-34.049L-65.479,-34.03L-65.551,-34.003L-65.563,-33.989L-65.571,-33.974L-65.556,-33.945L-65.547,-33.901L-65.558,-33.828L-65.576,-33.797L-65.592,-33.767L-65.653,-33.716L-65.669,-33.676L-65.643,-33.647L-65.644,-33.617L-65.674,-33.583L-65.666,-33.547L-65.659,-33.523L-65.631,-33.5L-65.622,-33.439L-65.641,-33.359L-65.638,-33.294L-65.604,-33.241L-65.597,-33.218L-65.63,-33.041L-65.628,-33.016","M-64.587,-36.002L-64.591,-35.983L-64.576,-35.944L-64.576,-35.921L-64.587,-35.907L-64.612,-35.899L-64.63,-35.889L-64.634,-35.872L-64.634,-35.864L-64.633,-35.845L-64.63,-35.828L-64.641,-35.806L-64.724,-35.751L-64.759,-35.679L-64.747,-35.592L-64.776,-35.503L-64.848,-35.414L-64.878,-35.314L-64.867,-35.204L-64.902,-35.114L-64.984,-35.046L-65.012,-35.004L-65.011,-35.001","M-64.481,-36.501L-64.469,-36.427L-64.48,-36.373L-64.515,-36.352L-64.52,-36.322L-64.5,-36.288L-64.5,-36.272L-64.508,-36.259L-64.532,-36.255L-64.551,-36.248L-64.566,-36.221L-64.537,-36.168L-64.542,-36.105L-64.582,-36.03L-64.587,-36.002","M-64.431,-36.503L-64.438,-36.529L-64.454,-36.555L-64.466,-36.555L-64.476,-36.553L-64.48,-36.541L-64.483,-36.513L-64.481,-36.501","M-64.404,-36.5L-64.405,-36.498L-64.419,-36.489L-64.429,-36.498L-64.431,-36.503","M-64.191,-36.992L-64.168,-36.912L-64.173,-36.811L-64.193,-36.716L-64.226,-36.626L-64.264,-36.594L-64.282,-36.6L-64.318,-36.616L-64.333,-36.611L-64.366,-36.588L-64.404,-36.5","M-65.838,-40.379L-65.88,-40.226L-65.881,-40.098L-65.856,-39.943L-65.827,-39.827L-65.793,-39.749L-65.671,-39.603L-65.462,-39.387L-65.331,-39.182L-65.278,-38.987L-65.215,-38.91L-65.144,-38.948L-65.055,-38.93L-64.958,-38.898L-64.908,-38.86L-64.897,-38.847L-64.891,-38.833L-64.895,-38.819L-64.909,-38.781L-65.028,-38.458L-65.069,-38.31L-65.063,-38.254L-65.015,-38.174L-64.925,-38.069L-64.846,-38.001L-64.778,-37.969L-64.673,-37.884L-64.529,-37.747L-64.457,-37.645L-64.457,-37.576L-64.442,-37.506L-64.413,-37.434L-64.413,-37.366L-64.442,-37.301L-64.431,-37.213L-64.378,-37.102L-64.333,-37.036L-64.297,-37.012L-64.289,-37.013L-64.286,-37.023L-64.291,-37.038L-64.293,-37.052L-64.29,-37.071L-64.283,-37.078L-64.276,-37.08L-64.242,-37.053L-64.191,-36.992","M-65.268,-42.513L-65.225,-42.445L-65.149,-42.383L-65.106,-42.326L-65.096,-42.272L-65.05,-42.215L-64.968,-42.154L-64.921,-42.1L-64.908,-42.054L-64.91,-41.982L-64.927,-41.884L-64.957,-41.813L-64.999,-41.77L-65.03,-41.71L-65.05,-41.632L-65.114,-41.56L-65.222,-41.495L-65.343,-41.45L-65.476,-41.426L-65.555,-41.369L-65.579,-41.28L-65.568,-41.206L-65.521,-41.146L-65.494,-41.083L-65.487,-41.016L-65.52,-40.905L-65.594,-40.75L-65.675,-40.65L-65.764,-40.604L-65.804,-40.537L-65.794,-40.448L-65.801,-40.397L-65.838,-40.379","M-65.697,-43.502L-65.692,-43.44L-65.677,-43.395L-65.648,-43.359L-65.604,-43.331L-65.597,-43.278L-65.626,-43.2L-65.636,-43.102L-65.627,-42.986L-65.605,-42.882L-65.57,-42.789L-65.491,-42.72L-65.368,-42.677L-65.295,-42.61L-65.273,-42.521L-65.268,-42.513","M-65.697,-43.502L-65.72,-43.797L-65.75,-43.936L-65.796,-43.991L-65.891,-44.054L-66.036,-44.126L-66.126,-44.194L-66.177,-44.289L-66.28,-44.4L-66.347,-44.445L-66.413,-44.462L-66.465,-44.498L-66.504,-44.552L-66.558,-44.587L-66.627,-44.601L-66.703,-44.645L-66.794,-44.726L-66.796,-44.732L-66.815,-44.79L-66.805,-44.823L-66.79,-44.934L-66.791,-44.969L-66.811,-45.071L-66.787,-45.111L-66.792,-45.236L-66.783,-45.278L-66.734,-45.381L-66.731,-45.433L-66.749,-45.494L-66.785,-45.543L-66.883,-45.595L-66.885,-45.659L-66.87,-45.706L-66.806,-45.796L-66.771,-45.875L-66.74,-45.909L-66.546,-46.028L-66.504,-46.036L-66.474,-46.07L-66.451,-46.084L-66.451,-46.228L-66.45,-46.373L-66.45,-46.517L-66.45,-46.661L-66.401,-46.671L-66.38,-46.707L-66.33,-46.763L-66.307,-46.762L-66.215,-46.73L-66.125,-46.779L-66.036,-46.827L-65.947,-46.876L-65.857,-46.925L-65.711,-47.021L-65.564,-47.117L-65.417,-47.213L-65.271,-47.309L-65.146,-47.304L-65.02,-47.298L-64.895,-47.293L-64.77,-47.287","M-63.39,-37.789L-63.413,-37.771L-63.453,-37.7L-63.461,-37.621L-63.437,-37.534L-63.497,-37.465L-63.64,-37.411L-63.716,-37.364L-63.725,-37.324L-63.715,-37.262L-63.686,-37.178L-63.681,-37.12L-63.7,-37.088L-63.802,-37.11L-63.988,-37.186L-64.113,-37.183L-64.177,-37.102L-64.199,-37.042L-64.191,-36.992","M-61.072,-39.092L-61.083,-39.083L-61.1,-39.04L-61.082,-38.996L-61.082,-38.961L-61.102,-38.933L-61.095,-38.913L-61.061,-38.9L-61.049,-38.868L-61.057,-38.819L-61.129,-38.77L-61.268,-38.714L-61.298,-38.697L-61.322,-38.69L-61.334,-38.694L-61.334,-38.694L-61.352,-38.704L-61.378,-38.727L-61.421,-38.737L-61.492,-38.73L-61.52,-38.683L-61.506,-38.597L-61.53,-38.53L-61.593,-38.484L-61.638,-38.423L-61.665,-38.347L-61.709,-38.301L-61.768,-38.285L-61.816,-38.215L-61.852,-38.091L-61.892,-38.014L-61.935,-37.984L-61.994,-37.992L-62.069,-38.037L-62.113,-38.083L-62.124,-38.13L-62.147,-38.164L-62.167,-38.179L-62.18,-38.179L-62.181,-38.172L-62.176,-38.159L-62.183,-38.145L-62.229,-38.14L-62.249,-38.12L-62.243,-38.086L-62.253,-38.062L-62.28,-38.048L-62.294,-38.015L-62.296,-37.964L-62.315,-37.917L-62.351,-37.875L-62.405,-37.889L-62.475,-37.96L-62.546,-37.976L-62.618,-37.938L-62.672,-37.886L-62.707,-37.821L-62.742,-37.805L-62.791,-37.855L-62.908,-37.923L-62.969,-37.938L-63.013,-37.922L-63.044,-37.929L-63.055,-37.948L-63.063,-37.956L-63.072,-37.946L-63.073,-37.887L-63.083,-37.849L-63.103,-37.833L-63.118,-37.846L-63.129,-37.886L-63.154,-37.9L-63.194,-37.885L-63.234,-37.891L-63.27,-37.916L-63.282,-37.913L-63.292,-37.902L-63.289,-37.855L-63.297,-37.818L-63.315,-37.794L-63.342,-37.788L-63.376,-37.8L-63.39,-37.789","M-59.481,-38.448L-59.487,-38.451L-59.586,-38.541L-59.648,-38.628L-59.674,-38.71L-59.76,-38.714L-59.906,-38.639L-60.017,-38.627L-60.092,-38.68L-60.148,-38.7L-60.204,-38.683L-60.257,-38.65L-60.302,-38.669L-60.356,-38.731L-60.443,-38.774L-60.562,-38.798L-60.644,-38.865L-60.689,-38.975L-60.738,-39.05L-60.79,-39.091L-60.846,-39.103L-60.908,-39.086L-60.956,-39.094L-60.989,-39.129L-61.031,-39.125L-61.072,-39.092","M-57.974,-40.647L-58.059,-40.603L-58.075,-40.563L-58.049,-40.512L-58.035,-40.445L-58.033,-40.364L-58.081,-40.185L-58.179,-39.909L-58.228,-39.736L-58.23,-39.664L-58.294,-39.571L-58.42,-39.456L-58.509,-39.387L-58.56,-39.363L-58.603,-39.365L-58.637,-39.393L-58.675,-39.374L-58.717,-39.308L-58.757,-39.274L-58.793,-39.272L-58.824,-39.229L-58.85,-39.147L-58.875,-39.099L-58.898,-39.086L-58.9,-39.044L-58.88,-38.973L-58.882,-38.947L-58.892,-38.946L-58.903,-38.95L-58.928,-38.934L-58.955,-38.894L-58.966,-38.894L-58.973,-38.9L-58.981,-38.952L-59.004,-38.989L-59.041,-39.011L-59.092,-38.963L-59.158,-38.845L-59.187,-38.768L-59.175,-38.715L-59.17,-38.638L-59.186,-38.606L-59.222,-38.594L-59.249,-38.552L-59.269,-38.48L-59.319,-38.434L-59.398,-38.415L-59.481,-38.448","M-63.39,-37.789L-63.429,-37.876L-63.426,-37.897L-63.403,-37.898L-63.391,-37.937L-63.392,-38.013L-63.379,-38.06L-63.357,-38.074L-63.353,-38.089L-63.364,-38.098L-63.364,-38.113L-63.33,-38.144L-63.323,-38.178L-63.344,-38.214L-63.346,-38.249L-63.329,-38.282L-63.303,-38.298L-63.269,-38.295L-63.236,-38.336L-63.205,-38.419L-63.169,-38.47L-63.13,-38.488L-63.098,-38.543L-63.06,-38.679L-63.021,-38.742L-63.013,-38.812L-63.022,-38.909L-63.049,-39.007L-63.095,-39.107L-63.106,-39.169L-63.083,-39.193L-63.074,-39.234L-63.08,-39.291L-63.057,-39.344L-63.024,-39.375L-63.024,-39.379L-63.023,-39.662L-63.021,-39.962L-63.02,-40.262L-63.019,-40.562L-63.018,-40.861L-63.017,-41.161L-63.016,-41.461L-63.015,-41.761L-62.907,-41.761L-62.799,-41.761","M-63.485,-34.999L-63.421,-34.933L-63.424,-34.909L-63.424,-34.893L-63.429,-34.846L-63.446,-34.661L-63.464,-34.477L-63.482,-34.292L-63.499,-34.107L-63.517,-33.923L-63.534,-33.738L-63.552,-33.553L-63.569,-33.368L-63.587,-33.184L-63.605,-32.999L-63.622,-32.814L-63.64,-32.629L-63.657,-32.445L-63.675,-32.26L-63.692,-32.075L-63.71,-31.891L-63.703,-31.703L-63.695,-31.515L-63.687,-31.327L-63.68,-31.14L-63.672,-30.952L-63.665,-30.764L-63.657,-30.577L-63.648,-30.371","M-61.649,-35.001L-61.765,-35.002L-61.88,-35.004L-61.996,-35.005L-62.111,-35.007L-62.227,-35.008L-62.342,-35.01L-62.458,-35.011L-62.573,-35.013L-62.689,-35.014L-62.804,-35.016L-62.92,-35.017L-63.035,-35.019L-63.151,-35.02L-63.266,-35.022L-63.382,-35.023L-63.497,-35.025L-63.506,-35.024L-63.497,-35.012L-63.485,-34.999","M-60.241,-36.605L-60.246,-36.603L-60.252,-36.6L-60.258,-36.598L-60.263,-36.596L-60.269,-36.594L-60.275,-36.591L-60.28,-36.589L-60.286,-36.587L-60.536,-36.597L-60.786,-36.606L-61.036,-36.616L-61.286,-36.626L-61.536,-36.636L-61.786,-36.645L-62.036,-36.655L-62.285,-36.665L-62.525,-36.66L-62.765,-36.654L-63.005,-36.649L-63.244,-36.644L-63.265,-36.675L-63.329,-36.682L-63.426,-36.693L-63.429,-36.693L-63.401,-36.59L-63.4,-36.501L-63.403,-36.5L-63.515,-36.5L-63.64,-36.5L-63.764,-36.5L-63.888,-36.5L-64.013,-36.5L-64.137,-36.5L-64.261,-36.5L-64.404,-36.5","M-58.794,-36.611L-58.897,-36.615L-58.972,-36.619L-59.006,-36.598L-59.157,-36.599L-59.277,-36.6L-59.48,-36.601L-59.728,-36.602L-60.077,-36.604L-60.241,-36.605","M-54.617,-36.551L-54.64,-36.551L-54.696,-36.551L-54.875,-36.553L-55.135,-36.556L-55.396,-36.559L-55.656,-36.561L-55.917,-36.564L-56.177,-36.567L-56.438,-36.57L-56.698,-36.573L-56.959,-36.575L-57.219,-36.578L-57.48,-36.581L-57.74,-36.584L-58.001,-36.587L-58.261,-36.589L-58.521,-36.592L-58.782,-36.595L-58.794,-36.611","M-61.205,-31.002L-61.176,-30.923L-61.119,-30.759L-61.116,-30.721L-61.049,-30.715L-60.934,-30.706L-60.82,-30.696L-60.705,-30.687L-60.59,-30.678L-60.475,-30.668L-60.36,-30.659L-60.246,-30.65L-60.131,-30.64L-60.016,-30.631L-59.901,-30.622L-59.787,-30.612L-59.672,-30.603L-59.557,-30.594L-59.442,-30.584L-59.327,-30.575L-59.213,-30.566L-59.212,-30.533L-59.193,-30.481L-59.188,-30.422L-59.18,-30.393L-59.157,-30.376L-59.121,-30.371L-59.084,-30.405L-59.061,-30.478L-59.056,-30.56L-59.07,-30.653L-59.067,-30.732L-59.049,-30.778L-59.028,-30.789L-59.009,-30.814L-58.994,-30.82L-58.954,-30.806L-58.805,-30.74L-58.683,-30.731","M-61.205,-31.002L-61.249,-31.118L-61.267,-31.296L-61.24,-31.573L-61.248,-31.635L-61.248,-31.635L-61.29,-31.777L-61.289,-31.881L-61.246,-32.051L-61.246,-32.051L-61.225,-32.147L-61.195,-32.202L-61.149,-32.247L-61.144,-32.286L-61.177,-32.32L-61.19,-32.361L-61.181,-32.409L-61.211,-32.526L-61.313,-32.804L-61.327,-32.898L-61.345,-32.956L-61.364,-33.084L-61.383,-33.212L-61.402,-33.34L-61.421,-33.467L-61.44,-33.595L-61.459,-33.723L-61.478,-33.851L-61.497,-33.979L-61.516,-34.106L-61.535,-34.234L-61.554,-34.362L-61.573,-34.49L-61.592,-34.617L-61.611,-34.745L-61.63,-34.873L-61.649,-35.001","M-59.843,-35.001L-59.847,-35.001L-59.883,-34.933L-59.988,-34.806L-60.016,-34.708L-59.88,-34.6L-59.879,-34.599L-59.798,-34.511L-59.742,-34.476L-59.686,-34.466L-59.65,-34.437L-59.629,-34.366L-59.629,-34.366L-59.464,-34.017L-59.464,-34.018L-59.293,-33.838L-59.225,-33.749L-59.19,-33.664L-59.044,-33.523L-58.994,-33.447L-58.992,-33.39L-58.974,-33.349L-58.942,-33.325L-58.911,-33.274L-58.882,-33.195L-58.824,-33.127L-58.736,-33.069L-58.673,-32.936L-58.632,-32.728L-58.591,-32.607L-58.529,-32.557L-58.443,-32.38L-58.416,-32.275L-58.417,-32.182L-58.374,-32.11L-58.228,-32.03","M-55.528,-38.944L-55.513,-38.936L-55.478,-38.915L-55.462,-38.889L-55.454,-38.807","M-55.963,-39.346L-55.922,-39.31L-55.825,-39.266L-55.785,-39.221L-55.802,-39.175L-55.805,-39.143L-55.786,-39.113L-55.657,-39.053L-55.577,-38.969L-55.528,-38.944","M-57.231,-39.211L-57.139,-39.285L-57.091,-39.312L-56.934,-39.476L-56.914,-39.477L-56.859,-39.454L-56.747,-39.57L-56.733,-39.613L-56.72,-39.627L-56.706,-39.625L-56.697,-39.614L-56.702,-39.59L-56.694,-39.578L-56.648,-39.55L-56.583,-39.534L-56.574,-39.533L-56.517,-39.533L-56.491,-39.556L-56.479,-39.601L-56.453,-39.628L-56.394,-39.639L-56.29,-39.686L-56.23,-39.678L-56.18,-39.631L-56.128,-39.609L-56.076,-39.611L-56.056,-39.6L-56.068,-39.576L-56.054,-39.548L-56.015,-39.517L-56.001,-39.488L-56.014,-39.461L-56.01,-39.442L-55.989,-39.429L-55.976,-39.4L-55.972,-39.354L-55.963,-39.346","M-57.255,-51.545L-57.255,-51.226L-57.255,-50.966L-57.254,-50.919L-57.254,-50.742L-57.254,-50.5L-57.253,-50.258L-57.253,-50.017L-57.253,-49.775L-57.252,-49.533L-57.252,-49.291L-57.251,-49.049L-57.251,-48.807L-57.251,-48.565L-57.25,-48.323L-57.25,-48.082L-57.25,-47.84L-57.249,-47.556L-57.25,-47.551L-57.283,-47.483L-57.274,-47.407L-57.225,-47.319L-57.198,-47.228L-57.193,-47.134L-57.143,-47.022L-56.999,-46.827L-56.89,-46.607L-56.81,-46.486L-56.722,-46.393L-56.492,-46.307L-55.932,-46.187L-55.709,-46.064L-55.707,-46.063L-55.651,-45.977L-55.643,-45.962L-55.632,-45.929L-55.608,-45.904L-55.512,-45.833L-55.462,-45.807L-55.423,-45.798L-55.397,-45.801L-55.386,-45.82L-55.377,-45.876L-55.361,-45.89L-55.348,-45.887L-55.313,-45.88L-55.263,-45.798L-55.2,-45.643L-55.118,-45.542L-55.018,-45.496L-54.914,-45.484L-54.808,-45.505L-54.72,-45.484L-54.651,-45.42L-54.451,-45.451L-54.12,-45.575L-53.902,-45.642L-53.796,-45.651L-53.696,-45.632L-53.566,-45.568L-53.579,-45.509L-53.606,-45.394L-53.624,-45.318L-53.577,-45.269L-53.525,-45.214"];
// [name, latitude, longitude, nationalCapital]; US states and Canadian provinces/territories included.
const MAP_CAPITALS = [["Tokyo",35.687,139.7495,1],["Mexico City",19.4444,-99.1329,1],["Dhaka",23.725,90.4066,1],["Buenos Aires",-34.6006,-58.3995,1],["Cairo",30.0519,31.248,1],["Beijing",39.9308,116.3863,1],["Manila",14.6061,120.9803,1],["Moscow",55.7541,37.6136,1],["Paris",48.8686,2.3314,1],["Seoul",37.5683,126.9978,1],["Jakarta",-6.1725,106.8275,1],["London",51.5019,-0.1187,1],["Lima",-12.0461,-77.052,1],["Tehran",35.6739,51.4224,1],["Kinshasa",-4.3278,15.313,1],["Bogota",4.5984,-74.0853,1],["Taipei",25.0358,121.5683,1],["Bangkok",13.7519,100.5147,1],["Santiago",-33.4481,-70.669,1],["Madrid",40.402,-3.6853,1],["Singapore",1.295,103.8539,1],["Luanda",-8.8363,13.2325,1],["Baghdad",33.3406,44.3919,1],["Khartoum",15.59,32.5322,1],["Riyadh",24.6428,46.7708,1],["Hanoi",21.0353,105.8481,1],["Washington, D.C.",38.9015,-77.0114,1],["Abidjan",5.3219,-4.042,1],["Brasília",-15.7814,-47.918,1],["Ankara",39.9292,32.8624,1],["Berlin",52.5238,13.3996,1],["Algiers",36.765,3.0486,1],["Rome",41.8979,12.4813,1],["Pyongyang",39.0214,125.7527,1],["Kabul",34.5186,69.1813,1],["Athens",37.9853,23.7314,1],["Cape Town",-33.9181,18.433,1],["Addis Ababa",9.0353,38.6981,1],["Nairobi",-1.2814,36.8147,1],["Caracas",10.5029,-66.919,1],["Lisbon",38.7247,-9.1468,1],["Kyiv",50.4353,30.5147,1],["Dakar",14.7178,-17.4751,1],["Damascus",33.502,36.2981,1],["Tunis",36.8028,10.1797,1],["Vienna",48.202,16.3647,1],["Tripoli",32.8925,13.18,1],["Tashkent",41.3136,69.293,1],["Havana",23.1339,-82.3661,1],["Santo Domingo",18.472,-69.902,1],["Baku",40.3972,49.8603,1],["Accra",5.552,-0.2187,1],["Kuwait City",29.3717,47.9764,1],["Sanaa",15.3567,44.2046,1],["Port-au-Prince",18.543,-72.338,1],["Bucharest",44.4353,26.098,1],["Asunción",-25.2945,-57.6435,1],["Beirut",33.8739,35.5078,1],["Minsk",53.9019,27.5647,1],["Brussels",50.8353,4.3314,1],["Warsaw",52.2519,20.9981,1],["Rabat",34.0253,-6.8364,1],["Quito",-0.213,-78.502,1],["Antananarivo",-18.9147,47.5147,1],["Budapest",47.502,19.0814,1],["Yaoundé",3.8686,11.5147,1],["La Paz",-16.496,-68.1519,1],["Abuja",9.0853,7.5314,1],["Harare",-17.8158,31.0428,1],["Montevideo",-34.8561,-56.173,1],["Bamako",12.652,-8.002,1],["Conakry",9.5335,-13.6822,1],["Phnom Penh",11.552,104.9147,1],["Lomé",6.1339,1.2208,1],["Doha",25.2866,51.533,1],["Kuala Lumpur",3.1686,101.698,1],["Maputo",-25.9533,32.5872,1],["San Salvador",13.7119,-89.205,1],["Kampala",0.3186,32.5814,1],["The Hague",52.08,4.27,1],["Brazzaville",-4.2572,15.2827,1],["Pretoria",-25.705,28.2275,1],["Lusaka",-15.4147,28.2814,1],["San José",9.937,-84.086,1],["Panama City",8.97,-79.535,1],["Stockholm",59.3527,18.0954,1],["Sofia",42.6853,23.3147,1],["Prague",50.0853,14.464,1],["Ouagadougou",12.3723,-1.5267,1],["Ottawa",45.4186,-75.702,1],["Helsinki",60.1775,24.9322,1],["Yerevan",40.1831,44.5116,1],["Mogadishu",2.0686,45.3647,1],["Tbilisi",41.727,44.7888,1],["Belgrade",44.8206,20.466,1],["Dushanbe",38.56,68.7739,1],["Copenhagen",55.6805,12.5615,1],["Amman",31.952,35.9314,1],["Dublin",53.335,-6.2509,1],["Monrovia",6.3146,-10.7997,1],["Amsterdam",52.3519,4.9147,1],["Jerusalem",31.7784,35.2066,1],["Guatemala City",14.6231,-90.5289,1],["N'Djamena",12.115,15.0472,1],["Tegucigalpa",14.104,-87.2195,1],["Kingston",17.9771,-76.7674,1],["Naypyidaw",19.7685,96.1167,1],["Djibouti",11.595,43.148,1],["Managua",12.155,-86.2704,1],["Niamey",13.5187,2.1147,1],["Tirana",41.3275,19.8189,1],["Kathmandu",27.7186,85.3147,1],["Ulaanbaatar",47.9186,106.9147,1],["Kigali",-1.9516,30.0586,1],["Valparaíso",-33.0458,-71.623,1],["Bishkek",42.875,74.5833,1],["Oslo",59.9186,10.748,1],["Bangui",4.3666,18.5583,1],["Freetown",8.472,-13.2362,1],["Islamabad",33.7019,73.1647,1],["Cotonou",6.402,2.518,1],["Vientiane",17.9667,102.6,1],["Riga",56.95,24.1,1],["Nouakchott",18.0864,-15.9753,1],["Muscat",23.6133,58.5933,1],["Ashgabat",37.95,58.3833,1],["Zagreb",45.8,16,1],["Sarajevo",43.85,18.383,1],["Chișinău",47.005,28.8577,1],["Lilongwe",-13.9833,33.7833,1],["Asmara",15.3333,38.9333,1],["Abu Dhabi",24.4667,54.3666,1],["Port Louis",-20.1666,57.5,1],["Libreville",0.3854,9.458,1],["Manama",26.2361,50.5831,1],["Vilnius",54.6834,25.3166,1],["Skopje",42,21.4335,1],["Hargeisa",9.56,44.0653,1],["Pristina",42.6667,21.166,1],["Bloemfontein",-29.12,26.2299,1],["Bratislava",48.15,17.117,1],["Bissau",11.865,-15.5984,1],["Tallinn",59.4339,24.728,1],["Wellington",-41.3,174.7833,1],["Valletta",35.8997,14.5147,1],["Maseru",-29.3167,27.4833,1],["Astana",51.1811,71.4278,1],["Canberra",-35.283,149.129,1],["New Delhi",28.6,77.2,1],["Ljubljana",46.0553,14.515,1],["Porto-Novo",6.4833,2.6166,1],["Bandar Seri Begawan",4.8833,114.9333,1],["Port-of-Spain",10.652,-61.517,1],["Port Moresby",-9.4647,147.1925,1],["Bern",46.9167,7.467,1],["Windhoek",-22.57,17.0835,1],["Georgetown",6.802,-58.167,1],["Paramaribo",5.835,-55.167,1],["Dili",-8.5594,125.5795,1],["Nassau",25.0834,-77.35,1],["Sucre",-19.041,-65.2595,1],["Nicosia",35.1667,33.3666,1],["Dodoma",-6.1833,35.75,1],["Colombo",6.932,79.8578,1],["Gaborone",-24.6463,25.9119,1],["Yamoussoukro",6.8184,-5.2755,1],["Bridgetown",13.102,-59.6165,1],["Laayoune",27.15,-13.2,1],["Suva",-18.133,178.4417,1],["Reykjavík",64.15,-21.95,1],["Podgorica",42.466,19.2663,1],["Moroni",-11.7042,43.2402,1],["Sri Jayawardenepura Kotte",6.9,79.95,1],["Praia",14.9167,-23.5167,1],["Malé",4.1667,73.4999,1],["Juba",4.83,31.58,1],["Luxembourg",49.6117,6.13,1],["Thimphu",27.473,89.639,1],["Mbabane",-26.3167,31.1333,1],["São Tomé",0.3334,6.7333,1],["Honiara",-9.438,159.9498,1],["Putrajaya",2.914,101.7019,1],["Apia",-13.8415,-171.7386,1],["Andorra la Vella",42.5,1.5165,1],["Hamilton",32.2942,-64.7839,1],["Kingstown",13.1483,-61.2121,1],["Port Vila",-17.7334,168.3166,1],["Banjul",13.4539,-16.5917,1],["Nuku'alofa",-21.1385,-175.2206,1],["Castries",14.002,-61,1],["Monaco",43.7396,7.4069,1],["Vaduz",47.1337,9.5167,1],["Saint John's",17.118,-61.85,1],["Saint George's",12.0526,-61.7416,1],["Victoria",-4.6166,55.45,1],["San Marino",43.9361,12.4418,1],["Tarawa",1.3382,173.0176,1],["Majuro",7.103,171.38,1],["Roseau",15.301,-61.387,1],["Gitega",-3.426,29.8436,1],["Basseterre",17.302,-62.717,1],["Belmopan",17.252,-88.7671,1],["Lobamba",-26.4667,31.2,1],["Funafuti",-8.5167,179.2166,1],["Palikir",6.9166,158.15,1],["Vatican City",41.9033,12.4534,1],["Bir Lehlou",26.1192,-9.6525,1],["Ciudad de la Paz",1.5889,10.8225,1],["Ngerulmud",7.5006,134.6242,1],["Yaren",-0.5477,166.9209,1],["Toronto",43.7019,-79.422,0],["Atlanta",33.832,-84.4019,0],["Boston",42.3319,-71.072,0],["Phoenix",33.5419,-112.0719,0],["Denver",39.7411,-104.986,0],["Sacramento",38.577,-121.472,0],["Indianapolis",39.7519,-86.172,0],["Providence",41.823,-71.4169,0],["Columbus",39.9819,-82.992,0],["Raleigh",35.8188,-78.6447,0],["Austin",30.2689,-97.7447,0],["Edmonton",53.552,-113.5019,0],["Salt Lake City",40.777,-111.932,0],["Hartford",41.772,-72.6819,0],["Richmond",37.552,-77.4519,0],["Nashville",36.1719,-86.7819,0],["Albany",42.67,-73.8199,0],["Oklahoma City",35.472,-97.5206,0],["Honolulu",21.3088,-157.8599,0],["St. Paul",44.944,-93.085,0],["Winnipeg",49.883,-97.166,0],["Québec",46.84,-71.2456,0],["Harrisburg",40.2736,-76.8847,0],["Baton Rouge",30.4579,-91.1402,0],["Columbia",34.04,-80.9,0],["Des Moines",41.58,-93.62,0],["Trenton",40.217,-74.7434,0],["Halifax",44.65,-63.6,0],["Boise",43.6086,-116.2275,0],["Madison",43.073,-89.4011,0],["Victoria",48.4333,-123.35,0],["Lansing",42.7335,-84.5467,0],["Little Rock",34.7361,-92.3311,0],["Jackson",32.2988,-90.185,0],["Lincoln",40.82,-96.68,0],["Salem",44.9281,-123.0239,0],["Tallahassee",30.45,-84.28,0],["Montgomery",32.3616,-86.2792,0],["Regina",50.45,-104.617,0],["Olympia",47.038,-122.8994,0],["Springfield",39.82,-89.65,0],["Topeka",39.05,-95.67,0],["St. John's",47.585,-52.681,0],["Charleston",38.3497,-81.6327,0],["Santa Fe",35.6869,-105.9372,0],["Annapolis",38.9783,-76.4925,0],["Dover",39.1581,-75.5247,0],["Cheyenne",41.14,-104.8197,0],["Bismarck",46.8083,-100.7833,0],["Carson City",39.1638,-119.7664,0],["Jefferson City",38.5766,-92.1733,0],["Fredericton",45.95,-66.6333,0],["Concord",43.2081,-71.538,0],["Charlottetown",46.2493,-63.1313,0],["Helena",46.5927,-112.0353,0],["Frankfort",38.2008,-84.8734,0],["Juneau",58.3141,-134.42,0],["Augusta",44.3106,-69.78,0],["Whitehorse",60.7167,-135.05,0],["Yellowknife",62.442,-114.397,0],["Pierre",44.3683,-100.3506,0],["Montpelier",44.26,-72.5758,0],["Iqaluit",63.7505,-68.5002,0]];
const MP_POOL = PLAYERS.filter(p => Array.isArray(p.bp) && p.bp.length >= 2);
const MAP_REGIONS = {
  world: [-180, 84, 180, -58],
  na: [-168, 72, -52, 14],
  eu: [-12, 71, 45, 35],
};
function distanceKm([la1, lo1], [la2, lo2]) {
  const r = Math.PI / 180, a = Math.sin((la2 - la1) * r / 2) ** 2
    + Math.cos(la1 * r) * Math.cos(la2 * r) * Math.sin((lo2 - lo1) * r / 2) ** 2;
  return 6371 * 2 * Math.asin(Math.min(1, Math.sqrt(a)));
}
function bearingArrow([la1, lo1], [la2, lo2]) {
  const r = Math.PI / 180, y = Math.sin((lo2 - lo1) * r) * Math.cos(la2 * r);
  const x = Math.cos(la1 * r) * Math.sin(la2 * r) - Math.sin(la1 * r) * Math.cos(la2 * r) * Math.cos((lo2 - lo1) * r);
  const deg = (Math.atan2(y, x) / r + 360) % 360;
  return ["⬆️", "↗️", "➡️", "↘️", "⬇️", "↙️", "⬅️", "↖️"][Math.round(deg / 45) % 8];
}
const fmtKm = d => d < 10 ? `${d.toFixed(1)} km` : `${Math.round(d).toLocaleString()} km`;
const mapPoints = (best, pins) => {
  const tier = [[100, 10], [250, 8], [500, 6], [1000, 4], [2500, 2]].find(([km]) => best <= km);
  return Math.max(0, (tier ? tier[1] : 0) - 2 * (pins - 1));
};
let mapDraftPin = null;
const mapView = { x: 0, y: 0, w: 0, h: 0 };

G.map = {
  kind: "score", title: "Birthplace", share: "Sweater Birthplace", view: "view-map", max: MAP_PINS, next: "Next player",
  pool: () => MP_POOL,
  daily(k) {
    const p = BYID.get((DAILY.map || {})[k]);
    return p && Array.isArray(p.bp) ? p : MP_POOL[hash("sweater-map-" + k) % MP_POOL.length];
  },
  random: () => pick(MP_POOL),
  tid: t => t.id, player: t => t, isWin: () => false,
  dist: (t, g) => distanceKm(g, t.bp),
  score(t, g) { return g.length ? mapPoints(Math.min(...g.map(x => this.dist(t, x))), g.length) : 0; },
  isDone(t, g) { return g.length >= MAP_PINS || (g.length > 0 && this.dist(t, g[g.length - 1]) <= MAP_WIN_KM); },
  wonGame(t, g) { return g.length > 0 && this.dist(t, g[g.length - 1]) <= MAP_WIN_KM; },
  meta: t => `Born in ${t.bp[2] || countryName(t.nation)}`,
  endText(t, g, won) {
    const best = Math.min(...g.map(x => this.dist(t, x))), pts = this.score(t, g);
    return { result: won ? `Nailed it${g.length > 1 ? ` in ${g.length}` : ""}!` : `Closest pin: ${fmtKm(best)} away`,
             cheer: `${pts} ${pts === 1 ? "point" : "points"}${won ? " 🎯" : ""}` };
  },
  celebrate: (t, g, won) => won,
  archiveStatus: h => `${h.s} pts`,
  shareText(t, saved, num, link) {
    const pins = saved.guesses.map((x, i) => { const d = this.dist(t, x); return `📍${i + 1} ${fmtKm(d)} ${d <= MAP_WIN_KM ? "🎯" : bearingArrow(x, t.bp)}`; });
    return `Sweater Birthplace #${num} · ${this.score(t, saved.guesses)} pts\n\n${pins.join("\n")}${link}`;
  },
  reset(t) {
    mapDraftPin = null;
    $("mpImg").onerror = function () { this.onerror = null; this.src = FALLBACK; };
    $("mpImg").src = t.headshot || FALLBACK;
    $("mpName").textContent = t.name;
    $("mpMeta").innerHTML = `<img src="${logo(t.team)}" alt="" onerror="this.remove()"> ${esc(teamName(t.team))} · ${posName(t)}`;
    $("mpHist").innerHTML = "";
    mapRegion(t.nation === "CAN" || t.nation === "USA" ? "na" : ["SWE", "FIN", "CZE", "SVK", "CHE", "DEU", "AUT", "DNK", "NOR", "LVA", "FRA", "GBR", "SVN", "BLR", "UKR", "NLD", "POL", "ITA", "HUN", "LTU", "EST"].includes(t.nation) ? "eu" : "world");
  },
  guess(t, x) {
    if (!Array.isArray(x) || x.length !== 2 || !x.every(Number.isFinite) || Math.abs(x[0]) > 90 || Math.abs(x[1]) > 180) return null;
    const d = this.dist(t, x);
    const chip = document.createElement("span");
    chip.className = `chip newrow ${d <= MAP_WIN_KM ? "hit" : d <= 500 ? "near" : ""}`;
    chip.textContent = `📍${S.map.guesses.length + 1}: ${fmtKm(d)} ${d <= MAP_WIN_KM ? "🎯" : bearingArrow(x, t.bp)}`;
    chip.title = d <= MAP_WIN_KM ? "Right on" : "The arrow points toward his birthplace";
    $("mpHist").appendChild(chip);
    mapDraftPin = null;
    return d <= MAP_WIN_KM;
  },
  render(t, st) {
    const left = MAP_PINS - st.guesses.length;
    $("mpLeft").textContent = st.over ? "" : `${left} ${left === 1 ? "pin" : "pins"} left. Land within ${MAP_WIN_KM} km to win; the arrow shows which way to go.`;
    $("mpGo").disabled = st.over || !mapDraftPin;
    $("mpGo").textContent = mapDraftPin ? "Drop pin here" : "Tap the map to place a pin";
    drawPins(t, st);
  },
};

function mapSize() {
  const r = $("mapSvg").getBoundingClientRect();
  if (r.width > 0 && r.height > 0) return { cw: r.width, ch: r.height };
  // Asked for before the map is on screen: mirror the CSS width and aspect ratio
  // instead of guessing, so labels aren't placed against a phantom viewport.
  const vw = window.innerWidth || 900, cw = Math.min(900, Math.max(280, vw - 32));
  return { cw, ch: cw / (vw > 700 ? 16 / 9 : 4 / 3) };
}
function setView(x, y, w, h) {
  const { cw, ch } = mapSize(), aspect = cw / ch;
  if (w / h > aspect) { const nh = w / aspect; y -= (nh - h) / 2; h = nh; } else { const nw = h * aspect; x -= (nw - w) / 2; w = nw; }
  const maxW = MAP_MAX_W;
  if (w > maxW) { const s = maxW / w; x += (w - maxW) / 2; y += (h - h * s) / 2; w = maxW; h *= s; }
  Object.assign(mapView, { x, y, w, h });
  $("mapSvg").setAttribute("viewBox", `${x} ${y} ${w} ${h}`);
  drawMapCities();
  if (S.map.target) drawPins(S.map.target, S.map);
}
function mapRegion(name) {
  const [lo1, la1, lo2, la2] = MAP_REGIONS[name];
  setView(lo1 * MAP_K, -la1, (lo2 - lo1) * MAP_K, la1 - la2);
  document.querySelectorAll("[data-region]").forEach(b => b.setAttribute("aria-selected", b.dataset.region === name));
}
function mapZoom(f, cx = mapView.x + mapView.w / 2, cy = mapView.y + mapView.h / 2) {
  const w = Math.min(Math.max(mapView.w * f, MAP_MIN_W), MAP_MAX_W), s = w / mapView.w;
  setView(cx - (cx - mapView.x) * s, cy - (cy - mapView.y) * s, w, mapView.h * s);
  document.querySelectorAll("[data-region]").forEach(b => b.setAttribute("aria-selected", false));
}
const toMap = (lat, lon) => [lon * MAP_K, -lat];
function drawMapCities() {
  const { cw, ch } = mapSize();
  // The viewBox is fitted with "meet", so the drawn scale is whichever axis is
  // tighter; letterbox bands shift screen positions and must be added back in.
  const k = Math.max(mapView.w / cw, mapView.h / ch) || 0;
  const ox = (cw - mapView.w / (k || 1)) / 2, oy = (ch - mapView.h / (k || 1)) / 2;
  // Labels stay out of the way until the map is zoomed in past a continent
  // view; the screen-width caps keep the reveal later still on phones.
  const capitalOpacity = national => {
    const [s0, f0] = MAP_LABEL_ZOOM[national ? "national" : "regional"];
    const start = Math.min(s0, cw * s0 / 400), full = Math.min(f0, cw * f0 / 400);
    const t = Math.max(0, Math.min(1, (start - mapView.w) / (start - full)));
    return t * t * (3 - 2 * t);
  };
  // Keep world/continent views quiet, regardless of desktop or phone width.
  // Clear the previous close-up labels again when the player zooms back out.
  if (!k || capitalOpacity(true) <= 0) {
    $("mapCities").innerHTML = "";
    return;
  }
  const boxes = [], dots = [], labels = [];
  // National capitals take priority; smaller capitals are never discarded from
  // the data, just decluttered until there is room for their name on screen.
  for (const [name, lat, lon, national] of MAP_CAPITALS) {
    const opacity = capitalOpacity(national);
    if (opacity <= 0) continue;
    const [x, y] = toMap(lat, lon), px = (x - mapView.x) / k + ox, py = (y - mapView.y) / k + oy;
    if (px < 0 || px > cw || py < 0 || py > ch) continue;
    const width = name.length * 6.8 + 5, height = 15;
    let spot = null;
    for (const [dx, dy] of [[6, -5], [-width - 6, -5], [6, 14], [-width - 6, 14]]) {
      const box = { x: px + dx - 2, y: py + dy - 12, w: width + 4, h: height };
      if (box.x < 1 || box.x + box.w > cw - 1 || box.y < 1 || box.y + box.h > ch - 1) continue;
      if (boxes.some(b => box.x < b.x + b.w + 4 && box.x + box.w + 4 > b.x && box.y < b.y + b.h + 3 && box.y + box.h + 3 > b.y)) continue;
      boxes.push(box); spot = [dx, dy]; break;
    }
    const transform = `translate(${x} ${y}) scale(${k})`, cls = national ? "national" : "regional";
    dots.push(`<g class="${cls}" opacity="${opacity.toFixed(3)}" transform="${transform}"><circle class="capital-dot" r="${national ? 2.6 : 2}"/></g>`);
    if (spot) labels.push(`<g class="${cls}" opacity="${opacity.toFixed(3)}" transform="${transform}"><text class="capital-label" x="${spot[0]}" y="${spot[1]}">${esc(name)}</text></g>`);
  }
  $("mapCities").innerHTML = dots.join("") + labels.join("");
}
function svgPoint(evt) {
  const pt = $("mapSvg").createSVGPoint();
  pt.x = evt.clientX; pt.y = evt.clientY;
  return pt.matrixTransform($("mapSvg").getScreenCTM().inverse());
}
function drawPins(t, st) {
  const r = mapView.w / 110, sw = mapView.w / 700;
  const pin = ([lat, lon], cls, label = "") => { const [x, y] = toMap(lat, lon);
    return `<circle class="${cls}" cx="${x}" cy="${y}" r="${r}" stroke-width="${sw * 2}"/>${label ? `<text x="${x}" y="${y + r * 0.38}" font-size="${r * 1.1}" text-anchor="middle">${label}</text>` : ""}`; };
  let html = "";
  if (st.over) {
    const [ax, ay] = toMap(...t.bp);
    html += st.guesses.map(g => { const [x, y] = toMap(...g); return `<line x1="${x}" y1="${y}" x2="${ax}" y2="${ay}" stroke-width="${sw * 2}" class="pinline"/>`; }).join("");
  }
  html += st.guesses.map((g, i) => pin(g, "pin", i + 1)).join("");
  if (mapDraftPin && !st.over) html += pin(mapDraftPin, "pin draftpin");
  if (st.over) { const [x, y] = toMap(...t.bp); html += `<circle class="answer" cx="${x}" cy="${y}" r="${r * 1.2}" stroke-width="${sw * 2}"/>`; }
  $("mapPins").innerHTML = html;
}
(() => {
  const svg = $("mapSvg"), pointers = new Map();
  $("mapSubdivisions").innerHTML = MAP_SUBDIVISIONS.map(d => `<path class="subdivisions" d="${d}"/>`).join("");
  let wheelFrame = 0, wheelPending = 0, wheelPoint = null, wheelTime = 0;
  const stopWheel = () => {
    cancelAnimationFrame(wheelFrame);
    wheelFrame = 0; wheelPending = 0; wheelTime = 0;
  };
  const animateWheel = now => {
    if (game !== "map" || !svg.getClientRects().length) { stopWheel(); return; }
    const elapsed = wheelTime ? Math.min(32, now - wheelTime) : 16.67;
    wheelTime = now;
    const step = Math.sign(wheelPending) * Math.min(Math.abs(wheelPending) * (1 - Math.exp(-elapsed / 32)), .012 * elapsed);
    wheelPending -= step;
    const p = svgPoint(wheelPoint);
    mapZoom(Math.exp(step), p.x, p.y);
    if (Math.abs(wheelPending) > .0001) wheelFrame = requestAnimationFrame(animateWheel);
    else stopWheel();
  };
  let start = null, moved = false, pinchStart = null;
  svg.addEventListener("pointerdown", e => {
    stopWheel();
    svg.setPointerCapture(e.pointerId);
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pointers.size === 1) { start = { x: e.clientX, y: e.clientY, view: { ...mapView } }; moved = false; }
    if (pointers.size === 2) {
      const [a, b] = [...pointers.values()];
      pinchStart = { d: Math.max(1, Math.hypot(a.x - b.x, a.y - b.y)), view: { ...mapView }, anchor: svgPoint({ clientX: (a.x + b.x) / 2, clientY: (a.y + b.y) / 2 }) };
      moved = true;
    }
  });
  svg.addEventListener("pointermove", e => {
    if (!pointers.has(e.pointerId)) return;
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    const { cw } = mapSize();
    if (pointers.size === 2 && pinchStart) {
      const [a, b] = [...pointers.values()], d = Math.hypot(a.x - b.x, a.y - b.y);
      const v = pinchStart.view, w = Math.min(Math.max(v.w * pinchStart.d / Math.max(1, d), MAP_MIN_W), MAP_MAX_W);
      const rect = svg.getBoundingClientRect(), k = w / cw;
      setView(pinchStart.anchor.x - ((a.x + b.x) / 2 - rect.left) * k,
        pinchStart.anchor.y - ((a.y + b.y) / 2 - rect.top) * k, w, v.h * w / v.w);
      document.querySelectorAll("[data-region]").forEach(b => b.setAttribute("aria-selected", false));
      return;
    }
    if (!start) return;
    const dx = e.clientX - start.x, dy = e.clientY - start.y;
    if (Math.hypot(dx, dy) > 6) moved = true;
    if (moved) { const k = start.view.w / cw; setView(start.view.x - dx * k, start.view.y - dy * k, start.view.w, start.view.h); }
  });
  const end = e => {
    const wasTap = pointers.size === 1 && start && !moved;
    pointers.delete(e.pointerId);
    if (pointers.size < 2) pinchStart = null;
    if (pointers.size === 1 && moved) {
      const p = [...pointers.values()][0];
      start = { x: p.x, y: p.y, view: { ...mapView } };
    }
    if (wasTap && e.type === "pointerup") {
      const st = S.map;
      if (st.target && !st.over && game === "map") {
        const p = svgPoint(e), lat = Math.max(-85, Math.min(85, -p.y)), lon = Math.max(-180, Math.min(180, p.x / MAP_K));
        mapDraftPin = [Math.round(lat * 100) / 100, Math.round(lon * 100) / 100];
        G.map.render(st.target, st);
      }
    }
    if (!pointers.size) start = null;
  };
  svg.addEventListener("pointerup", end);
  svg.addEventListener("pointercancel", end);
  svg.addEventListener("lostpointercapture", end);
  svg.addEventListener("wheel", e => {
    e.preventDefault();
    if (!e.deltaY || pointers.size) return;
    // deltaMode: pixels, lines, or pages. Tiny trackpad events must stay tiny.
    const pixels = e.deltaY * (e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? mapSize().ch : 1);
    // Three gestures arrive through the same event: a browser pinch (ctrlKey),
    // a mouse wheel in coarse notches, and a trackpad scroll as a stream of
    // small deltas. Each gets its own rate so the map keeps up with the hand
    // without running away from it.
    const notch = e.deltaMode !== 0 || Math.abs(pixels) >= 50;
    const delta = e.ctrlKey ? Math.max(-120, Math.min(120, pixels)) * ZOOM_PINCH
      : notch ? Math.sign(pixels) * ZOOM_NOTCH
      : pixels * ZOOM_TRACKPAD;
    if (wheelPending * delta < 0) wheelPending = 0;
    wheelPending = Math.max(-ZOOM_NOTCH * 2, Math.min(ZOOM_NOTCH * 2, wheelPending + delta));
    wheelPoint = { clientX: e.clientX, clientY: e.clientY };
    if (!wheelFrame) wheelFrame = requestAnimationFrame(animateWheel);
  }, { passive: false });
  document.querySelectorAll("[data-region]").forEach(b => b.onclick = () => { stopWheel(); mapRegion(b.dataset.region); });
  $("mapIn").onclick = () => { stopWheel(); mapZoom(.5); };
  $("mapOut").onclick = () => { stopWheel(); mapZoom(2); };
  $("mpGo").onclick = () => { if (mapDraftPin) doGuess(mapDraftPin); };
  window.addEventListener("resize", () => { if (game === "map") setView(mapView.x, mapView.y, mapView.w, mapView.h); });
})();

// ---- Connections: sort 16 players into 4 groups ----
const CONN_MISTAKES = 4;
function connCategories(pool) {
  const cats = [], group = f => {
    const m = new Map();
    for (const p of pool) { const k = f(p); if (k === null || k === undefined || k === "") continue; if (!m.has(k)) m.set(k, []); m.get(k).push(p); }
    return [...m.entries()].filter(([, v]) => v.length >= 4).map(([k]) => k);
  };
  group(p => p.team).forEach(k => cats.push({ tier: 0, label: `Plays for ${teamName(k)}`, test: p => p.team === k }));
  group(p => ["CAN", "USA"].includes(p.nation) ? null : p.nation)
    .forEach(k => cats.push({ tier: 1, label: `Born in ${countryName(k)}`, test: p => p.nation === k }));
  if (pool.filter(p => p.pos === "G").length >= 4) cats.push({ tier: 1, label: "Goalies", test: p => p.pos === "G" });
  group(p => p.number || null).forEach(k => cats.push({ tier: 2, label: `Wears #${k}`, test: p => p.number === k }));
  if (pool.filter(p => p.draft === 0).length >= 4) cats.push({ tier: 2, label: "Went undrafted", test: p => p.draft === 0 });
  group(p => String(p.birth).slice(0, 4)).forEach(k => cats.push({ tier: 3, label: `Born in ${k}`, test: p => String(p.birth).startsWith(k + "-") }));
  group(p => hasDraft(p) ? p.draft[0] : null).forEach(k => cats.push({ tier: 3, label: `Drafted in ${k}`, test: p => hasDraft(p) && p.draft[0] === k }));
  return cats;
}
let connCats = null;
function connGenerate(rnd) {
  connCats = connCats || connCategories(PLAYERS);
  for (let attempt = 0; attempt < 300; attempt++) {
    const chosen = [0, 1, 2, 3].map(tier => { const c = connCats.filter(x => x.tier === tier); return c.length ? c[Math.floor(rnd() * c.length)] : null; });
    if (chosen.some(c => !c)) return null;
    const groups = [];
    for (const [tier, c] of chosen.entries()) {
      const fits = PLAYERS.filter(p => c.test(p) && chosen.every(o => o === c || !o.test(p)));
      if (fits.length < 4) break;
      groups.push({ tier, label: c.label, ids: shuffled(fits, rnd).slice(0, 4).map(p => p.id).sort((a, b) => a - b) });
    }
    if (groups.length === 4) return { groups };
  }
  return null;
}
const CONN_POOL = PLAYERS.length >= 16 && connGenerate(seeded(1)) ? [1] : [];
const connKey = ids => ids.slice().sort((a, b) => a - b).join(",");
let connSel = new Set(), connOrder = [];

G.conn = {
  kind: "score", title: "Connections", share: "Sweater Connections", view: "view-conn", max: 20, next: "New puzzle",
  hideReveal: true,
  pool: () => CONN_POOL,
  daily(k) {
    const v = (DAILY.conn || {})[k];
    if (Array.isArray(v) && v.length === 4 && v.every(g => g.ids.length === 4 && g.ids.every(i => BYID.has(i)))) {
      return { groups: v.map((g, tier) => ({ tier, label: g.label, ids: g.ids })) };
    }
    return connGenerate(seeded(hash("sweater-conn-" + k)));
  },
  random() { return connGenerate(Math.random); },
  tid: t => t.groups.map(g => g.ids.join(".")).join("|"),
  player: () => null,
  progress(t, guesses) {
    const solved = [], keys = t.groups.map(g => connKey(g.ids));
    let mistakes = 0;
    for (const x of guesses) { const i = keys.indexOf(x); if (i >= 0 && !solved.includes(i)) solved.push(i); else mistakes++; }
    return { solved, mistakes };
  },
  score(t, g) { const { solved, mistakes } = this.progress(t, g); return solved.length === 4 ? [10, 8, 6, 4][mistakes] : 0; },
  isWin: () => false,
  isDone(t, g) { const { solved, mistakes } = this.progress(t, g); return solved.length === 4 || mistakes >= CONN_MISTAKES; },
  wonGame(t, g) { return this.progress(t, g).solved.length === 4; },
  meta: () => "",
  endText(t, g, won) {
    const { mistakes } = this.progress(t, g), pts = this.score(t, g);
    return { result: won ? (mistakes ? `Solved with ${mistakes} ${mistakes === 1 ? "mistake" : "mistakes"}` : "Perfect puzzle!") : "Out of mistakes",
             cheer: won ? `${pts} points` : "Here's how they connect" };
  },
  celebrate: (t, g, won) => won,
  archiveStatus: h => h.w ? `✓ ${h.s} pts` : "✗",
  shareText(t, saved, num, link) {
    const colour = ["🟨", "🟩", "🟦", "🟪"];
    const tierOf = id => t.groups.findIndex(g => g.ids.includes(id));
    const rows = saved.guesses.map(x => x.split(",").map(Number).map(id => colour[tierOf(id)]).join(""));
    return `Sweater Connections #${num} · ${this.score(t, saved.guesses)} pts\n\n${rows.join("\n")}${link}`;
  },
  reset(t) {
    connSel = new Set();
    const all = t.groups.flatMap(g => g.ids);
    connOrder = shuffled(all, seeded(hash(this.tid(t))));
  },
  guess(t, x) {
    if (typeof x !== "string") return null;
    const ids = x.split(",").map(Number), all = t.groups.flatMap(g => g.ids);
    if (ids.length !== 4 || new Set(ids).size !== 4 || !ids.every(i => all.includes(i)) || x !== connKey(ids)) return null;
    connSel = new Set();
    return false;
  },
  render(t, st) {
    const { solved, mistakes } = this.progress(t, st.guesses);
    const shownGroups = st.over ? [...solved, ...[0, 1, 2, 3].filter(i => !solved.includes(i))] : solved;
    const done = new Set(shownGroups.flatMap(i => t.groups[i].ids));
    $("cnSolved").innerHTML = shownGroups.map(i => {
      const g = t.groups[i];
      return `<div class="cngroup tier${g.tier}${solved.includes(i) ? "" : " missedgrp"}"><b>${esc(g.label)}</b>
        <span>${g.ids.map(id => esc(BYID.get(id)?.name || "?")).join(", ")}</span></div>`;
    }).join("");
    $("cnGrid").innerHTML = connOrder.filter(id => !done.has(id)).map(id => {
      const p = BYID.get(id), parts = (p?.name || "?").split(" ");
      return `<button type="button" class="cntile${connSel.has(id) ? " sel" : ""}" data-id="${id}">
        <small>${esc(parts.slice(0, -1).join(" "))}</small><b>${esc(parts[parts.length - 1])}</b></button>`;
    }).join("");
    $("cnMistakes").innerHTML = st.over ? "" : `Mistakes left: ${"●".repeat(CONN_MISTAKES - mistakes)}${"○".repeat(mistakes)}`;
    $("cnControls").hidden = !!st.over;
    $("cnSubmit").disabled = connSel.size !== 4;
  }
};
$("cnGrid").addEventListener("click", e => {
  const b = e.target.closest(".cntile"), st = S.conn;
  if (!b || st.over) return;
  const id = Number(b.dataset.id);
  if (connSel.has(id)) connSel.delete(id); else if (connSel.size < 4) connSel.add(id);
  G.conn.render(st.target, st);
});
$("cnShuffle").onclick = () => { const st = S.conn; if (!st.target) return; connOrder = shuffled(connOrder); G.conn.render(st.target, st); };
$("cnClear").onclick = () => { const st = S.conn; if (!st.target) return; connSel = new Set(); G.conn.render(st.target, st); };
$("cnSubmit").onclick = () => {
  const st = S.conn, t = st.target;
  if (!t || st.over || connSel.size !== 4) return;
  const ids = [...connSel], key = connKey(ids);
  if (st.guesses.includes(key)) { toast("You already tried that group"); return; }
  const isRight = t.groups.some(g => connKey(g.ids) === key);
  const oneAway = !isRight && t.groups.some(g => ids.filter(i => g.ids.includes(i)).length === 3);
  const tiles = ids.map(id => $("cnGrid").querySelector(`[data-id="${id}"]`));
  doGuess(key);
  if (!isRight) {
    toast(oneAway ? "One away…" : "Not a group");
    if (!S.conn.over) {
      connSel = new Set(ids);
      G.conn.render(t, S.conn);
      ids.forEach(id => { const el = $("cnGrid").querySelector(`[data-id="${id}"]`); if (el) { el.classList.remove("shake"); void el.offsetWidth; el.classList.add("shake"); } });
    }
  }
};

// ======================= rank 'em, puck drop, shootout, zamboni reveal =======================
const QUIZ_KINDS = ["team", "nation", "number", "oldest", "youngest", "defence", "goalie", "draftYear", "draftTeam",
  "draftRound", "position", "height", "tallest", "mostGames", "mostGoals", "mostPoints", "bornIn", "wears", "city",
  "seasons", "pastTeam", "bestGoals"];
const POS_LABELS = { C: "Centre", L: "Left wing", R: "Right wing", D: "Defence", G: "Goalie" };
// A multiple-choice question {q, o: [4 options], a}. `used` keeps a run from repeating a question type or a player.
function quizQuestion(rnd, pool = PLAYERS, used = {}) {
  const one = arr => arr[Math.floor(rnd() * arr.length)];
  const sample = (arr, n) => shuffled(arr, rnd).slice(0, n);
  const kinds = used.kinds || new Set(), seen = used.players || new Set();
  const freshAll = pool.filter(p => !seen.has(p.id)), fresh = freshAll.length >= 8 ? freshAll : pool;
  const skaters = fresh.filter(p => p.pos !== "G");
  const nm = n => (COUNTRY_NAMES[n] || n).replace(/^the /, "");
  const inches = v => `${Math.floor(v / 12)}′${v % 12}″`;
  const near = (v, step, low = 0) => {
    const out = new Set();
    for (let k = 0; out.size < 3 && k < 60; k++) {
      const d = (1 + Math.floor(rnd() * 4)) * step * (rnd() < .5 ? -1 : 1);
      if (v + d >= low) out.add(v + d);
    }
    return [...out];
  };
  const four = (list, key) => { const f = sample(list, 4); return f.length === 4 && new Set(f.map(key)).size === 4 ? f : null; };
  const best = (list, score) => list.reduce((a, b) => score(a) >= score(b) ? a : b);
  for (let tries = 0; tries < 80; tries++) {
    const left = QUIZ_KINDS.filter(k => !kinds.has(k));
    const kind = one(left.length ? left : QUIZ_KINDS), p = one(fresh);
    let q = null, opts = null, right = null, who = [p];
    if (kind === "team") {
      const o = [...new Set(pool.map(x => x.team))].filter(t => t !== p.team);
      if (o.length >= 3) { opts = sample(o, 3).map(teamName); right = teamName(p.team); q = `Which team does ${p.name} play for?`; }
    } else if (kind === "nation") {
      const o = [...new Set(pool.map(x => x.nation))].filter(n => n !== p.nation);
      if (o.length >= 3) { opts = sample(o, 3).map(nm); right = nm(p.nation); q = `Which country was ${p.name} born in?`; }
    } else if (kind === "number") {
      const o = [...new Set(pool.map(x => x.number).filter(Boolean))].filter(n => n !== p.number);
      if (p.number && o.length >= 3) { opts = sample(o, 3).map(n => `#${n}`); right = `#${p.number}`; q = `What number does ${p.name} wear?`; }
    } else if (kind === "oldest" || kind === "youngest") {
      const f = four(fresh, x => x.birth);
      if (f) {
        const t = best(f, x => kind === "oldest" ? -Number(x.birth.replace(/-/g, "")) : Number(x.birth.replace(/-/g, "")));
        opts = f.filter(x => x !== t).map(x => x.name); right = t.name; who = f; q = `Which of these players is the ${kind}?`;
      }
    } else if (kind === "defence" || kind === "goalie") {
      const want = kind === "defence" ? "D" : "G";
      const yes = fresh.filter(x => x.pos === want), no = fresh.filter(x => ["C", "L", "R"].includes(x.pos));
      if (yes.length && no.length >= 3) {
        const y = one(yes), n3 = sample(no, 3);
        opts = n3.map(x => x.name); right = y.name; who = [y, ...n3];
        q = `Which of these players is a ${kind === "defence" ? "defenceman" : "goalie"}?`;
      }
    } else if (kind === "draftYear") {
      if (hasDraft(p)) { opts = near(p.draft[0], 1, 1980).map(String); right = String(p.draft[0]); q = `What year was ${p.name} drafted?`; }
    } else if (kind === "draftTeam") {
      if (hasDraft(p) && TEAMS[p.draft[3]]) {
        opts = sample(Object.keys(TEAMS).filter(t => t !== p.draft[3]), 3).map(teamName);
        right = teamName(p.draft[3]); q = `Which team drafted ${p.name}?`;
      }
    } else if (kind === "draftRound") {
      if (hasDraft(p) && p.draft[1] <= 7) {
        opts = sample([1, 2, 3, 4, 5, 6, 7].filter(r => r !== p.draft[1]), 3).map(r => `Round ${r}`);
        right = `Round ${p.draft[1]}`; q = `In which round was ${p.name} drafted?`;
      }
    } else if (kind === "position") {
      if (POS_LABELS[p.pos]) {
        opts = sample(Object.keys(POS_LABELS).filter(k => k !== p.pos), 3).map(k => POS_LABELS[k]);
        right = POS_LABELS[p.pos]; q = `What position does ${p.name} play?`;
      }
    } else if (kind === "height") {
      if (p.ht) { opts = near(p.ht, 1, 60).map(inches); right = inches(p.ht); q = `How tall is ${p.name}?`; }
    } else if (kind === "tallest") {
      const f = four(fresh.filter(x => x.ht), x => x.ht);
      if (f) { const t = best(f, x => x.ht); opts = f.filter(x => x !== t).map(x => x.name); right = t.name; who = f; q = "Which of these players is the tallest?"; }
    } else if (kind === "mostGames" || kind === "mostGoals" || kind === "mostPoints") {
      const key = { mostGames: "gp", mostGoals: "goals", mostPoints: "points" }[kind];
      const f = four((kind === "mostGames" ? fresh : skaters).filter(x => x.car), x => rankValue(x, key));
      if (f) {
        const t = best(f, x => rankValue(x, key));
        opts = f.filter(x => x !== t).map(x => x.name); right = t.name; who = f;
        q = `Which of these players has the most career ${key === "gp" ? "NHL games" : key}?`;
      }
    } else if (kind === "bornIn") {
      const no = fresh.filter(x => x.nation !== p.nation);
      if (no.length >= 3) { const n3 = sample(no, 3); opts = n3.map(x => x.name); right = p.name; who = [p, ...n3]; q = `Which of these players was born in ${nm(p.nation)}?`; }
    } else if (kind === "wears") {
      const no = fresh.filter(x => x.number && x.number !== p.number);
      if (p.number && no.length >= 3) { const n3 = sample(no, 3); opts = n3.map(x => x.name); right = p.name; who = [p, ...n3]; q = `Which of these players wears #${p.number}?`; }
    } else if (kind === "city") {
      const cities = [...new Set(pool.filter(x => x.bp && x.bp[2]).map(x => x.bp[2]))].filter(c => !p.bp || c !== p.bp[2]);
      if (p.bp && p.bp[2] && cities.length >= 3) { opts = sample(cities, 3); right = p.bp[2]; q = `Which city was ${p.name} born in?`; }
    } else if (kind === "seasons") {
      const n = seasonsOf(p).length;
      if (n >= 2) { opts = near(n, 1, 1).map(String); right = String(n); q = `How many NHL seasons has ${p.name} played?`; }
    } else if (kind === "pastTeam") {
      const r = teamSeasonsOf(p);
      if (r.length) {
        const s = one(r), t = s.teams[0];
        opts = sample(Object.keys(TEAMS).filter(x => x !== t), 3).map(teamName); right = teamName(t);
        q = `Which team did ${p.name} play for in ${seasonLabel(s.y)}?`;
      }
    } else if (kind === "bestGoals") {
      const v = p.pos === "G" ? 0 : hlValue(p, "goals").v;
      if (v) { opts = near(v, 2, 0).map(String); right = String(v); q = `What's the most goals ${p.name} has scored in one NHL season?`; }
    }
    if (!q || !opts || opts.length !== 3 || opts.includes(right) || new Set(opts).size !== 3) continue;
    kinds.add(kind);
    who.forEach(x => seen.add(x.id));
    const a = Math.floor(rnd() * 4);
    opts.splice(a, 0, right);
    return { q, o: opts, a, kind };
  }
  return null;
}

// ---- Rank 'Em: put 5 players in order ----
const RANK_STATS = {
  goals:  { label: "career goals",  order: "most to fewest" },
  points: { label: "career points", order: "most to fewest" },
  gp:     { label: "career games",  order: "most to fewest" },
  height: { label: "height",        order: "tallest to shortest" },
  weight: { label: "weight",        order: "heaviest to lightest" },
  age:    { label: "age",           order: "oldest to youngest" },
};
function rankValue(p, stat) {
  if (!p) return 0;
  if (stat === "goals") return seasonsOf(p).reduce((n, r) => n + r.a, 0);
  if (stat === "points") return seasonsOf(p).reduce((n, r) => n + r.c, 0);
  if (stat === "gp") return seasonsOf(p).reduce((n, r) => n + r.gp, 0);
  return hlValue(p, stat).v;
}
function rankShow(p, stat) {
  if (stat === "goals") return `${rankValue(p, stat)} G`;
  if (stat === "points") return `${rankValue(p, stat)} PTS`;
  if (stat === "gp") return `${rankValue(p, stat)} GP`;
  if (stat === "weight") return `${p.wt} lbs`;
  if (stat === "age") return `${ageOf(p.birth)} yrs`;
  return hlValue(p, stat).show;
}
function rankRandom(rnd) {
  const stats = Object.keys(RANK_STATS);
  for (let i = 0; i < 100; i++) {
    const stat = stats[Math.floor(rnd() * stats.length)];
    const pool = HL_POOL.filter(p => rankValue(p, stat));
    const five = shuffled(pool, rnd).slice(0, 5);
    if (five.length === 5 && new Set(five.map(p => rankValue(p, stat))).size === 5) return { stat, ids: five.map(p => p.id) };
  }
  return null;
}
let rkOrder = [];
G.rank = {
  title: "Rank 'Em", share: "Sweater Rank 'Em", view: "view-rank", max: 3, next: "Next puzzle", hideReveal: true,
  cheers: ["Perfect order! 🥇", "Sorted! 🙌", "Just in time! 🚨"],
  pool: () => HL_POOL.length >= 5 ? HL_POOL : [],
  daily(k) {
    const v = DAILY.rank[k];
    if (v && RANK_STATS[v.stat] && v.ids.length === 5 && v.ids.every(i => BYID.has(i))) return { stat: v.stat, ids: v.ids };
    return rankRandom(seeded(hash("sweater-rank-" + k)));
  },
  random: () => rankRandom(Math.random),
  tid: t => `${t.stat}:${t.ids.join(".")}`,
  answer: t => t.ids.slice().sort((a, b) => rankValue(BYID.get(b), t.stat) - rankValue(BYID.get(a), t.stat)),
  player: t => BYID.get(t.ids[0]),
  isWin(t, key) { return key === this.answer(t).join(","); },
  meta: t => `Ranked ${RANK_STATS[t.stat].order} by ${RANK_STATS[t.stat].label}`,
  reset(t) { rkOrder = t.ids.slice(); },
  guess(t, key) {
    if (typeof key !== "string") return null;
    const ids = key.split(",").map(Number);
    if (ids.length !== 5 || ids.slice().sort().join() !== t.ids.slice().sort().join()) return null;
    rkOrder = ids;
    return this.isWin(t, key);
  },
  render(t, st) {
    const info = RANK_STATS[t.stat], ans = this.answer(t);
    const last = st.guesses.length ? st.guesses[st.guesses.length - 1].split(",").map(Number) : null;
    if (st.over) rkOrder = ans;
    $("rkIntro").innerHTML = `Put these players in order of <b>${info.label}</b>, ${info.order}.`;
    $("rkList").innerHTML = rkOrder.map((id, i) => {
      const p = BYID.get(id), good = st.over || (last && last.join() === rkOrder.join() && ans[i] === id) ? " good" : "";
      return `<li class="rkrow${good}${st.over ? " done" : ""}" data-id="${id}">
        <span class="rkpos">${i + 1}</span>
        <img src="${esc(p.headshot || FALLBACK)}" alt="" onerror="this.onerror=null;this.src=FALLBACK">
        <span class="rkname"><b>${esc(p.name)}</b><small>${esc(p.team)} · ${esc(p.pos)}</small></span>
        ${st.over ? `<span class="rkval">${esc(rankShow(p, t.stat))}</span>` : `<span class="rkbtns">
          <button type="button" data-mv="-1" aria-label="Move ${esc(p.name)} up"${i === 0 ? " disabled" : ""}>▲</button>
          <button type="button" data-mv="1" aria-label="Move ${esc(p.name)} down"${i === 4 ? " disabled" : ""}>▼</button></span>
          <span class="rkgrip" aria-hidden="true">⠿</span>`}
      </li>`;
    }).join("");
    $("rkHist").innerHTML = st.guesses.map((k, n) => `<span class="chip">Try ${n + 1}: ${this.squares(t, k).trim()}</span>`).join("");
    const left = this.max - st.guesses.length;
    $("rkLeft").textContent = st.over ? "" : `${left} ${left === 1 ? "try" : "tries"} left. Drag the rows or use the arrows. Green rows are in the right spot.`;
    $("rkGo").hidden = !!st.over;
  },
  squares(t, key) { const ans = this.answer(t); return key.split(",").map((id, i) => Number(id) === ans[i] ? "🟩" : "⬛").join("") + "\n"; }
};
function rkMove(from, to) {
  if (to < 0 || to > 4 || from === to) return;
  const [id] = rkOrder.splice(from, 1);
  rkOrder.splice(to, 0, id);
  G.rank.render(S.rank.target, S.rank);
}
$("rkList").addEventListener("click", e => {
  const b = e.target.closest("[data-mv]");
  if (!b || S.rank.over) return;
  const i = rkOrder.indexOf(Number(b.closest(".rkrow").dataset.id));
  rkMove(i, i + Number(b.dataset.mv));
});
(() => {
  let drag = null;
  $("rkList").addEventListener("pointerdown", e => {
    const row = e.target.closest(".rkrow");
    if (!row || S.rank.over || e.target.closest("button")) return;
    drag = { id: Number(row.dataset.id), y: e.clientY };
    $("rkList").setPointerCapture(e.pointerId);
    $("rkList").classList.add("dragging");
    row.classList.add("lifted");
  });
  $("rkList").addEventListener("pointermove", e => {
    if (!drag) return;
    const rows = [...$("rkList").children];
    const from = rkOrder.indexOf(drag.id);
    let to = rows.findIndex(r => e.clientY < r.getBoundingClientRect().top + r.offsetHeight / 2);
    if (to === -1) to = rows.length - 1; else if (to > from) to -= 1;
    if (to !== from) { rkMove(from, to); $("rkList").querySelector(`[data-id="${drag.id}"]`).classList.add("lifted"); }
  });
  const stop = () => { if (!drag) return; drag = null; $("rkList").classList.remove("dragging"); G.rank.render(S.rank.target, S.rank); };
  $("rkList").addEventListener("pointerup", stop);
  $("rkList").addEventListener("pointercancel", stop);
})();
$("rkGo").onclick = () => {
  const key = rkOrder.join(",");
  if (S.rank.guesses.includes(key)) { toast("You already tried that order"); return; }
  const before = S.rank.guesses.length;
  doGuess(key);
  if (!S.rank.over && S.rank.guesses.length > before) toast("Not quite. Green rows are right.");
};

// ---- Puck Drop: tap the players who match the rule ----
const PUCK_LANES = 3, PUCK_GAP = 1150;
function puckMatch(rule, p) {
  if (!p) return false;
  if (rule.kind === "team") return p.team === rule.key;
  if (rule.kind === "nation") return p.nation === rule.key;
  if (rule.kind === "pos") return p.pos === rule.key;
  return hasDraft(p) && p.draft[1] === 1;
}
const PUCK_RULES = (() => {
  const rules = [], count = f => PLAYERS.filter(f).length;
  [...new Set(PLAYERS.map(p => p.team))].forEach(t => { if (count(p => p.team === t) >= 8) rules.push({ kind: "team", key: t, label: `Plays for ${teamName(t)}` }); });
  [...new Set(PLAYERS.map(p => p.nation))].filter(n => n !== "CAN" && n !== "USA")
    .forEach(n => { if (count(p => p.nation === n) >= 8) rules.push({ kind: "nation", key: n, label: `Born in ${countryName(n)}` }); });
  if (count(p => p.pos === "D") >= 10) rules.push({ kind: "pos", key: "D", label: "Plays defence" });
  if (count(p => hasDraft(p) && p.draft[1] === 1) >= 10) rules.push({ kind: "round1", key: "1", label: "First-round draft pick" });
  return rules;
})();
function puckRandom(rnd) {
  if (!PUCK_RULES.length) return null;
  const rule = PUCK_RULES[Math.floor(rnd() * PUCK_RULES.length)];
  const yes = PLAYERS.filter(p => puckMatch(rule, p)).map(p => p.id), no = PLAYERS.filter(p => !puckMatch(rule, p)).map(p => p.id);
  const m = Math.min(13, yes.length);
  return { ...rule, ids: shuffled([...shuffled(yes, rnd).slice(0, m), ...shuffled(no, rnd).slice(0, 36 - m)], rnd) };
}
let puckRun = null;
G.puck = {
  kind: "score", title: "Puck Drop", share: "Sweater Puck Drop", view: "view-puck", max: 99, next: "Play again", hideReveal: true,
  pool: () => PUCK_RULES.length ? PUCK_RULES : [],
  daily(k) {
    const v = DAILY.puck[k];
    if (v && v.ids && v.ids.every(i => BYID.has(i))) return v;
    return puckRandom(seeded(hash("sweater-puck-" + k)));
  },
  random: () => ({ ...puckRandom(Math.random), rid: Math.random() }),
  tid: t => t.rid ? `puck:${t.rid}` : `${t.kind}:${t.key}:${hash(t.ids.join(","))}`,
  player: () => null,
  tally(t, g) {
    const taps = g.filter(x => x !== "END"), right = taps.filter(id => puckMatch(t, BYID.get(id))).length;
    return { right, wrong: taps.length - right, total: t.ids.filter(id => puckMatch(t, BYID.get(id))).length };
  },
  score(t, g) { const { right, wrong } = this.tally(t, g); return Math.max(0, right - wrong); },
  isWin: () => false,
  isDone: (t, g) => g.includes("END"),
  wonGame(t, g) { const { right, wrong, total } = this.tally(t, g); return right === total && wrong === 0; },
  meta: t => t.label,
  endText(t, g, won) {
    const { right, wrong, total } = this.tally(t, g);
    return { result: `${this.score(t, g)} ${this.score(t, g) === 1 ? "point" : "points"}`,
             cheer: won ? "Clean sheet! Every match, no mistakes 🥅" : `${right} of ${total} caught, ${wrong} wrong` };
  },
  celebrate(t, g, won) { const { right, total } = this.tally(t, g); return won || right >= total * 0.8; },
  archiveStatus: h => `${h.s} pts`,
  shareText(t, saved, num, link) {
    const { right, wrong, total } = this.tally(t, saved.guesses);
    return `Sweater Puck Drop #${num} · ${t.label}\n🥅 ${right}/${total} caught · ❌ ${wrong} wrong\nScore: ${this.score(t, saved.guesses)}${link}`;
  },
  clockKey(t) { return `${mode}:${S.puck.day || ""}:${this.tid(t)}`; },
  reset(t) {
    stopPuck();
    $("pkRule").textContent = t.label;
    $("pkLane").innerHTML = "";
    const c = store.get("sweater-puck-clock");
    this.stale = mode !== "unlimited" && c && c.key === this.clockKey(t);
  },
  guess(t, x) { return x === "END" ? false : t.ids.includes(x) ? false : null; },
  render(t, st) {
    const { right, wrong, total } = this.tally(t, st.guesses);
    $("pkScore").textContent = Math.max(0, right - wrong);
    $("pkCaught").textContent = `${right}/${total}`;
    $("pkStart").hidden = !!(puckRun || st.over);
    $("pkLeft").textContent = st.over ? "" : puckRun ? "Tap only the players who match." : "Names slide across the ice. Tap the ones who match the rule. Wrong taps cost a point.";
    if (st.over) {
      stopPuck();
      const taps = st.guesses.filter(x => x !== "END");
      $("pkLane").innerHTML = `<div class="pksummary">${t.ids.filter(id => puckMatch(t, BYID.get(id)) || taps.includes(id)).map(id => {
        const hit = taps.includes(id), ok = puckMatch(t, BYID.get(id));
        return `<span class="chip ${hit && ok ? "hit" : hit ? "bad" : "missed"}">${esc(BYID.get(id).name)}</span>`;
      }).join("")}</div>`;
    } else if (!puckRun && this.stale && st.guesses.length) {
      this.stale = false;
      setTimeout(() => { if (game === "puck" && !S.puck.over) doGuess("END"); }, 0);
    }
  },
};
function stopPuck() { if (puckRun) { cancelAnimationFrame(puckRun.raf); puckRun = null; } }
function startPuck() {
  const st = S.puck, t = st.target;
  if (game !== "puck" || !t || st.over || puckRun) return;
  if (mode !== "unlimited") store.set("sweater-puck-clock", { key: G.puck.clockKey(t) });
  const lane = $("pkLane"), queue = t.ids.filter(id => !st.guesses.includes(id));
  lane.innerHTML = "";
  puckRun = { t0: performance.now(), pucks: [], next: 0, queue };
  const step = now => {
    if (!puckRun) return;
    const run = puckRun, elapsed = now - run.t0;
    while (run.next < run.queue.length && elapsed >= run.next * PUCK_GAP) {
      const id = run.queue[run.next], el = document.createElement("button");
      el.type = "button"; el.className = "puck"; el.dataset.id = id;
      el.textContent = BYID.get(id).name;
      el.style.top = `${(run.next % PUCK_LANES) * (100 / PUCK_LANES) + 4}%`;
      lane.appendChild(el);
      run.pucks.push({ el, born: run.next * PUCK_GAP, dur: 3600 - 1200 * (run.next / Math.max(1, run.queue.length - 1)) });
      run.next++;
    }
    const w = lane.clientWidth;
    run.pucks = run.pucks.filter(pk => {
      const k = (elapsed - pk.born) / pk.dur;
      if (k > 1) { pk.el.remove(); return false; }
      pk.el.style.transform = `translateX(${w - k * (w + pk.el.offsetWidth + 20)}px)`;
      return true;
    });
    if (run.next >= run.queue.length && !run.pucks.length) {
      stopPuck();
      if (game === "puck" && !S.puck.over) doGuess("END");
      return;
    }
    run.raf = requestAnimationFrame(step);
  };
  puckRun.raf = requestAnimationFrame(step);
  G.puck.render(t, st);
}
$("pkStart").onclick = startPuck;
$("pkLane").addEventListener("pointerdown", e => {
  const el = e.target.closest(".puck");
  if (!el || !puckRun || el.classList.contains("tapped")) return;
  const id = Number(el.dataset.id), ok = puckMatch(S.puck.target, BYID.get(id));
  el.classList.add("tapped", ok ? "good" : "bad");
  doGuess(id);
  setTimeout(() => el.remove(), 350);
});

// ---- Shootout: answer to earn a shot, then beat the goalie ----
const NET_ZONES = [[62, 52], [238, 52], [62, 140], [238, 140], [150, 172]];
// how the goalie reacts to each spot: a full stretch up high, a pad-extension split down low,
// and a butterfly for the five-hole. Blocker-side saves use the mirrored pose.
const GOALIE_AT = [
  { pose: "stretch", mirror: true,  move: "translate(-8px, -4px)" },
  { pose: "stretch", mirror: false, move: "translate(8px, -4px)" },
  { pose: "split",   mirror: true,  move: "translate(-10px, 2px)" },
  { pose: "split",   mirror: false, move: "translate(10px, 2px)" },
  { pose: "ready",   mirror: false, move: "translate(0, 12px) scale(1.12, .84)" },
];
function setGoalie(at) {
  const g = $("shGoalie");
  g.dataset.pose = at ? at.pose : "ready";
  g.classList.toggle("mirror", !!(at && at.mirror));
  g.style.transform = at ? at.move : "";
}
function shootRandom(rnd) {
  const rounds = [], used = { kinds: new Set(), players: new Set() };
  for (let i = 0; i < 5; i++) {
    const q = quizQuestion(rnd, PLAYERS, used);
    if (!q) return null;
    q.keep = shuffled([0, 1, 2, 3, 4], rnd).slice(0, 2).sort();
    rounds.push(q);
  }
  return { rounds, rid: rnd === Math.random ? Math.random() : 0 };
}
let shootUI = { phase: "ask", choice: null, zone: null };
G.shoot = {
  kind: "score", title: "Shootout", share: "Sweater Shootout", view: "view-shoot", max: 5, next: "Play again", hideReveal: true,
  repeat: true,   // the same answer and spot can come up in different rounds
  pool: () => PLAYERS.length >= 20 ? PLAYERS : [],
  daily(k) {
    const v = DAILY.shoot[k];
    if (v && v.rounds && v.rounds.length === 5) return v;
    return shootRandom(seeded(hash("sweater-shoot-" + k)));
  },
  random: () => shootRandom(Math.random),
  tid: t => `shoot:${t.rid || hash(t.rounds.map(r => r.q).join("|"))}`,
  player: () => null,
  outcome(t, x, i) {
    const [c, z] = x.split(":").map(Number), r = t.rounds[i];
    return c !== r.a ? "miss" : z >= 0 && !r.keep.includes(z) ? "goal" : "save";
  },
  goals(t, g) { return g.filter((x, i) => this.outcome(t, x, i) === "goal").length; },
  score(t, g) { return this.goals(t, g) * 2; },
  isWin: () => false,
  isDone: (t, g) => g.length >= 5,
  wonGame(t, g) { return this.goals(t, g) >= 3; },
  meta: () => "",
  endText(t, g, won) {
    const n = this.goals(t, g);
    return { result: `${n} for 5`, cheer: n === 5 ? "Perfect shootout! 🚨" : won ? "You win the shootout! 🏆" : "The goalie stole this one. 🧤" };
  },
  celebrate: (t, g, won) => won,
  archiveStatus: h => `${h.s / 2}/5 goals`,
  shareText(t, saved, num, link) {
    const icon = { goal: "🚨", save: "🧤", miss: "❌" };
    return `Sweater Shootout #${num}\n${saved.guesses.map((x, i) => icon[this.outcome(t, x, i)]).join("")}\n${this.goals(t, saved.guesses)}/5 goals${link}`;
  },
  reset() { shootUI = { phase: "ask", choice: null, zone: null }; },
  guess(t, x) { return typeof x === "string" && /^[0-3]:(-1|[0-4])$/.test(x) ? false : null; },
  render(t, st) {
    const i = st.guesses.length, icon = { goal: "🚨", save: "🧤", miss: "❌" };
    $("shDots").innerHTML = [0, 1, 2, 3, 4].map(n => `<span class="shdot${n === i && !st.over ? " now" : ""}">${n < i ? icon[this.outcome(t, st.guesses[n], n)] : n + 1}</span>`).join("");
    const lastI = i - 1, showResult = shootUI.phase === "result" && lastI >= 0;
    const r = t.rounds[showResult ? lastI : Math.min(i, 4)];
    $("shQ").textContent = st.over && !showResult ? "Shootout over" : `Shooter ${(showResult ? lastI : i) + 1}: ${r.q}`;
    const answered = showResult || shootUI.phase === "aim";
    const chosen = showResult ? Number(st.guesses[lastI].split(":")[0]) : shootUI.choice;
    $("shOpts").innerHTML = st.over && !showResult ? "" : r.o.map((o, n) => {
      const cls = answered ? (n === r.a ? " right" : n === chosen ? " wrong" : " dim") : "";
      return `<button type="button" class="shopt${cls}" data-c="${n}"${answered ? " disabled" : ""}>${esc(o)}</button>`;
    }).join("");
    const aiming = shootUI.phase === "aim";
    $("shNet").classList.toggle("aim", aiming);
    $("shNet").querySelectorAll(".zone").forEach(z => z.classList.toggle("off", !aiming));
    let msg = "";
    if (showResult) {
      const out = this.outcome(t, st.guesses[lastI], lastI);
      msg = out === "goal" ? "Goal! 🚨" : out === "save" ? "Saved by the goalie 🧤" : "Wrong answer, so no shot ❌";
    } else if (aiming) msg = "Pick your spot and shoot.";
    else if (!st.over) msg = "Answer right to earn a shot.";
    $("shMsg").textContent = msg;
    $("shNext").hidden = !(showResult && !st.over);
    if (!showResult) { $("shPuck").setAttribute("class", "shpuck"); setGoalie(null); $("shNet").classList.remove("scored", "saved"); }
  },
};
function shootAnimate(zone, keep) {
  const puck = $("shPuck"), net = $("shNet");
  const [x, y] = NET_ZONES[zone], save = keep.includes(zone);
  setGoalie(GOALIE_AT[save ? zone : keep[0]]);
  puck.style.setProperty("--tx", `${x - 150}px`);
  puck.style.setProperty("--ty", `${y - 194}px`);
  puck.setAttribute("class", `shpuck fly${save ? " saved" : ""}`);
  setTimeout(() => net.classList.add(save ? "saved" : "scored"), 380);
}
$("shOpts").addEventListener("click", e => {
  const b = e.target.closest("[data-c]"), st = S.shoot;
  if (!b || st.over || shootUI.phase !== "ask") return;
  const c = Number(b.dataset.c), r = st.target.rounds[st.guesses.length];
  if (c === r.a) { shootUI = { phase: "aim", choice: c }; G.shoot.render(st.target, st); }
  else { shootUI = { phase: "result" }; doGuess(`${c}:-1`); }
});
$("shNet").addEventListener("click", e => {
  const z = e.target.closest("[data-z]"), st = S.shoot;
  if (!z || shootUI.phase !== "aim" || st.over) return;
  const zone = Number(z.dataset.z), r = st.target.rounds[st.guesses.length];
  shootAnimate(zone, r.keep);
  const choice = shootUI.choice;
  shootUI = { phase: "result" };
  setTimeout(() => doGuess(`${choice}:${zone}`), 450);
});
$("shNext").onclick = () => { shootUI = { phase: "ask" }; G.shoot.render(S.shoot.target, S.shoot); };

// ---- Zamboni Reveal: clear the ice to find the player ----
const ZAM_BRUSH = 24;
let zamCtx = null, zamLast = null, zamMax = 0;
function zamPaint(t) {
  const cv = $("zmIce"), dpr = window.devicePixelRatio || 1, size = cv.clientWidth || 300;
  cv.width = cv.height = Math.round(size * dpr);
  zamCtx = cv.getContext("2d");
  zamCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
  const g = zamCtx.createLinearGradient(0, 0, size, size);
  g.addColorStop(0, "#f4f9fc"); g.addColorStop(1, "#cfe1ec");
  zamCtx.globalCompositeOperation = "source-over";
  zamCtx.fillStyle = g; zamCtx.fillRect(0, 0, size, size);
  const rnd = seeded(hash(String(t.id)));
  zamCtx.strokeStyle = "rgba(255,255,255,.75)";
  for (let i = 0; i < 40; i++) {
    zamCtx.lineWidth = .5 + rnd() * 1.5;
    zamCtx.beginPath();
    const x = rnd() * size, y = rnd() * size, a = rnd() * Math.PI;
    zamCtx.moveTo(x, y); zamCtx.lineTo(x + Math.cos(a) * 60 * rnd(), y + Math.sin(a) * 60 * rnd());
    zamCtx.stroke();
  }
  zamCtx.globalCompositeOperation = "destination-out";
  zamCtx.lineCap = "round"; zamCtx.lineWidth = ZAM_BRUSH * 2;
}
function zamPct() {
  if (!zamCtx) return zamMax;
  const cv = $("zmIce"), data = zamCtx.getImageData(0, 0, cv.width, cv.height).data;
  let clear = 0, n = 0;
  for (let i = 3; i < data.length; i += 4 * 7) { n++; if (data[i] < 128) clear++; }
  zamMax = Math.max(zamMax, Math.round(clear / n * 100));
  return zamMax;
}
G.zam = {
  kind: "score", title: "Zamboni Reveal", share: "Sweater Zamboni", view: "view-zam", max: 3, next: "Next player",
  pool: () => BL_POOL,
  daily(k) {
    const p = BYID.get(DAILY.zam[k]);
    return p && p.headshot ? p : BL_POOL[hash("sweater-zam-" + k) % BL_POOL.length];
  },
  random: () => pick(BL_POOL),
  tid: t => t.id, player: t => t,
  parse: x => String(x).split("@").map(Number),
  isWin(t, x) { return this.parse(x)[0] === t.id; },
  isDone(t, g) { return g.some(x => this.isWin(t, x)) || g.length >= 3; },
  wonGame(t, g) { return g.some(x => this.isWin(t, x)); },
  score(t, g) {
    const i = g.findIndex(x => this.isWin(t, x));
    return i < 0 ? 0 : Math.max(1, 10 - Math.floor(this.parse(g[i])[1] / 10) - 2 * i);
  },
  meta: t => `${t.team} · #${t.number} · ${posName(t)}`,
  endText(t, g, won) {
    const pct = won ? this.parse(g[g.length - 1])[1] : 0;
    return won ? { result: `Got him with ${pct}% of the ice cleared`, cheer: `${this.score(t, g)} points` }
               : { result: "Out of guesses", cheer: "The mystery player was" };
  },
  celebrate: (t, g, won) => won,
  archiveStatus: h => h.w ? `${h.s} pts` : "✗",
  shareText(t, saved, num, link) {
    const won = this.wonGame(t, saved.guesses), pct = this.parse(saved.guesses[saved.guesses.length - 1])[1];
    return `Sweater Zamboni #${num} · ${this.score(t, saved.guesses)} pts\n${won ? `🧊 ${pct}% of the ice cleared · ${saved.guesses.length} ${saved.guesses.length === 1 ? "guess" : "guesses"}` : "❌ Missed"}${link}`;
  },
  reset(t) {
    $("zmWrong").innerHTML = "";
    $("zmImg").onerror = function () { this.onerror = null; this.src = FALLBACK; };
    $("zmImg").src = t.headshot || FALLBACK;
    zamMax = 0;
    requestAnimationFrame(() => {
      zamPaint(t);
      const done = S.zam.guesses;
      if (done.length && !S.zam.over) {   // after a reload, clear a matching area in the middle
        const pct = this.parse(done[done.length - 1])[1], size = $("zmIce").clientWidth;
        zamCtx.beginPath(); zamCtx.arc(size / 2, size / 2, Math.sqrt(pct / 100 * size * size / Math.PI), 0, Math.PI * 2);
        zamCtx.fill();
        zamMax = pct;
      }
      this.render(t, S.zam);
    });
  },
  guess(t, x) {
    if (typeof x !== "string" || !/^\d+@\d{1,3}$/.test(x)) return null;
    const [id] = this.parse(x), p = BYID.get(id);
    if (!p) return null;
    if (id !== t.id) addWrong("zmWrong", p);
    return id === t.id;
  },
  render(t, st) {
    if (st.over && zamCtx) { const cv = $("zmIce"); zamCtx.clearRect(0, 0, cv.width, cv.height); }
    const left = this.max - st.guesses.length;
    $("zmLeft").textContent = st.over ? "" : `${left} ${left === 1 ? "guess" : "guesses"} left · ${zamMax}% of the ice cleared. The less you clear, the more points you get.`;
  },
};
(() => {
  const cv = $("zmIce");
  const at = e => { const r = cv.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };
  cv.addEventListener("pointerdown", e => {
    if (S.zam.over || !zamCtx) return;
    cv.setPointerCapture(e.pointerId);
    zamLast = at(e);
    zamCtx.beginPath(); zamCtx.arc(zamLast[0], zamLast[1], ZAM_BRUSH, 0, Math.PI * 2); zamCtx.fill();
  });
  cv.addEventListener("pointermove", e => {
    if (!zamLast || S.zam.over) return;
    const p = at(e);
    zamCtx.beginPath(); zamCtx.moveTo(zamLast[0], zamLast[1]); zamCtx.lineTo(p[0], p[1]); zamCtx.stroke();
    zamLast = p;
  });
  const up = () => { if (!zamLast) return; zamLast = null; zamPct(); G.zam.render(S.zam.target, S.zam); };
  cv.addEventListener("pointerup", up);
  cv.addEventListener("pointercancel", up);
})();

// ---- Goalie Mode and Overtime ----
const GL_SPOTS = [[21,43],[79,43],[21,78],[79,78],[50,78]];
const arcadeAnswers = guesses => guesses.filter(x => x !== "START" && x !== "END");
function goalieShot(t, index) {
  const rnd = seeded(hash(`goalie:${t.seed}:${index}`)), zone = Math.floor(rnd() * 5);
  return { zone, bend: index >= 5 && rnd() < .3 ? Math.floor(rnd() * 5) : zone,
    duration: Math.max(520, 1450 - index * 28) };
}
function goalieTally(t, guesses) {
  let score = 0, streak = 0, best = 0, saves = 0, goals = 0;
  arcadeAnswers(guesses).forEach((x,i) => {
    if (Number(x) === goalieShot(t,i).zone) { streak++; saves++; score += 10 * Math.min(5, 1 + Math.floor((streak - 1) / 5)); best = Math.max(best, streak); }
    else { goals++; streak = 0; }
  });
  return { score, streak, best, saves, goals };
}
let goalieRun = null, overtimeRun = null;
function stopGoalie() {
  if (goalieRun) cancelAnimationFrame(goalieRun.raf);
  goalieRun = null;
  $("glPuck").hidden = true;
  $("glGlove").hidden = true;
  $("glRink").classList.remove("live");
  document.querySelectorAll("[data-save]").forEach(b => b.disabled = true);
}
function stopOvertime() { if (overtimeRun) cancelAnimationFrame(overtimeRun.raf); overtimeRun = null; }
function endArcade(id, quiet = false) {
  if (game !== id || !S[id].target || S[id].over) return;
  const started = S[id].guesses.includes("START");
  if (id === "goalie") stopGoalie(); else stopOvertime();
  if (started) { G[id].quietFinish=quiet; try { doGuess("END"); } finally { G[id].quietFinish=false; } }
}
// START is saved immediately. A reload cannot grant extra lives or reset time.
function recoverArcade(id, st, active) {
  if (!st.over && !active && st.guesses.includes("START")) {
    const target = st.target;
    setTimeout(() => { if (game === id && S[id].target === target && !S[id].over && !(id === "goalie" ? goalieRun : overtimeRun)) endArcade(id); }, 0);
  }
}
function arcadeBest(id, st) {
  const score = G[id].score(st.target, st.guesses), key = `sweater-${id}-best`;
  store.set(key, Math.max(Number(store.get(key)) || 0, score));
}
G.goalie = {
  localOnly: true,
  kind: "score", repeat: true, title: "Goalie Mode", share: "Sweater Goalie", view: "view-goalie", max: 999, next: "Take the net again", hideReveal: true,
  pool: () => [true], daily: k => DAILY.goalie[k] || { seed: hash(`goalie:${k}`) },
  random: () => ({ seed: Math.floor(Math.random() * 2**32) }), tid: t => `goalie-v1:${t.seed}`,
  player: () => null, meta: () => "", isWin: () => false,
  score: (t,g) => goalieTally(t,g).score,
  isDone: (t,g) => g.includes("END") || goalieTally(t,g).goals >= 3,
  wonGame: (t,g) => goalieTally(t,g).saves >= 10,
  endText(t,g) { const n = goalieTally(t,g); return { result: `${n.score} points`, cheer: `${n.saves} saves · Best streak ${n.best}` }; },
  celebrate: (t,g) => goalieTally(t,g).saves >= 10,
  archiveStatus: h => `${h.s} pts`, onFinish: st => arcadeBest("goalie", st),
  shareText(t,s,n,link) { const r=goalieTally(t,s.guesses); return `Sweater Goalie #${n}\n${r.score} points · ${r.saves} saves\nBest save streak: ${r.best}${link}`; },
  reset() { stopGoalie(); document.querySelectorAll("[data-save]").forEach(b => b.className="goalie-zone"); },
  guess(t,x) { return x === "START" || x === "END" || (S.goalie.guesses.includes("START") && /^(-1|[0-4])$/.test(x)) ? false : null; },
  render(t,st) {
    const r=goalieTally(t,st.guesses);
    $("glScore").textContent=r.score; $("glStreak").textContent=r.streak; $("glLives").textContent=`${r.goals} / 3`;
    $("glStart").hidden=!!goalieRun || st.over || st.guesses.includes("START"); $("glEnd").hidden=!goalieRun || st.over;
    if (st.over) { stopGoalie(); $("glStatus").textContent="Final buzzer"; }
    else if (!goalieRun) $("glStatus").textContent="Own the crease.";
    recoverArcade("goalie",st,goalieRun);
  },
};
function startGoalie() {
  const st=S.goalie;
  if (game!=="goalie" || !st.target || st.over || goalieRun || st.guesses.includes("START")) return;
  goalieRun={ next: performance.now()+850, shot:null, choice:null, raf:0 };
  $("glRink").scrollIntoView({block:"center",behavior:"instant"});
  $("glRink").classList.add("live"); $("glStatus").textContent="Get set…";
  $("glGlove").hidden=false;$("glGlove").style.left="50%";$("glGlove").style.top="91%";
  doGuess("START");
  const step=now => {
    const run=goalieRun;
    if (!run || game!=="goalie") return;
    if (!run.shot && now>=run.next) {
      const index=arcadeAnswers(st.guesses).length;
      run.shot={...goalieShot(st.target,index),born:now}; run.choice=null;
      $("glGlove").style.left="50%";$("glGlove").style.top="91%";
      const tally=goalieTally(st.target,st.guesses);
      $("glStatus").textContent=`Shot ${index+1} · ${Math.min(5,1+Math.floor(tally.streak/5))}× multiplier`;
      document.querySelectorAll("[data-save]").forEach(b=>{ b.disabled=false; b.className="goalie-zone"; });
      $("glPuck").hidden=false;
    }
    if (run.shot) {
      const shot=run.shot, p=Math.min(1,(now-shot.born)/shot.duration), [x,y]=GL_SPOTS[shot.zone];
      const control=GL_SPOTS[shot.bend][0], px=(1-p)**2*50+2*(1-p)*p*control+p*p*x;
      $("glPuck").style.left=`${px}%`; $("glPuck").style.top=`${10+(y-10)*p}%`;
      $("glPuck").style.transform=`translate(-50%,-50%) scale(${.4+p*.9})`;
      if (p>=1) {
        const saved=run.choice===shot.zone, before=goalieTally(st.target,st.guesses).score;
        run.shot=null; run.next=now+650;
        document.querySelectorAll("[data-save]").forEach(b=>{ b.disabled=true; if(Number(b.dataset.save)===shot.zone)b.classList.add(saved?"saved":"conceded"); });
        doGuess(String(run.choice ?? -1));
        if (!goalieRun) return;
        $("glStatus").textContent=saved?`Save! +${goalieTally(st.target,st.guesses).score-before}`:"Goal against";
      }
    }
    run.raf=requestAnimationFrame(step);
  };
  goalieRun.raf=requestAnimationFrame(step);
}
function commitSave(zone) {
  const run=goalieRun;
  if(game!=="goalie" || !run?.shot || run.choice!==null || S.goalie.over || performance.now()>=run.shot.born+run.shot.duration) return;
  run.choice=zone;
  $("glGlove").style.left=`${GL_SPOTS[zone][0]}%`;$("glGlove").style.top=`${GL_SPOTS[zone][1]}%`;
  document.querySelectorAll("[data-save]").forEach(b=>{b.disabled=true; b.classList.toggle("chosen",Number(b.dataset.save)===zone);});
}
$("glRink").addEventListener("click",e=>{const b=e.target.closest("[data-save]");if(b)commitSave(Number(b.dataset.save));});
$("glStart").onclick=startGoalie; $("glEnd").onclick=()=>endArcade("goalie");

function overtimeRandom(rnd) {
  const rounds=[], seen=new Set(), used={kinds:new Set(),players:new Set()}, trophies=trophyRandom(rnd)?.rounds || [];
  for(let attempt=0; rounds.length<100 && attempt<1000; attempt++) {
    const trophy=rounds.length%5===4 ? trophies[Math.floor(rounds.length/5)] : null;
    const q=trophy ? {q:`Who won the ${trophy.t} in ${seasonLabel(trophy.y)}?`,o:trophy.names,a:trophy.a,kind:"trophy"} : quizQuestion(rnd,PLAYERS,used);
    if(!q || q.kind==="pastTeam" || seen.has(q.q)) continue;
    seen.add(q.q); rounds.push(q);
  }
  return rounds.length===100?{rounds}:null;
}
function overtimeTally(t, guesses) {
  let right=0, streak=0, best=0;
  for(const x of arcadeAnswers(guesses)) { const [i,c]=x.split(":").map(Number); if(t.rounds[i]?.a===c){right++;streak++;best=Math.max(best,streak);}else streak=0; }
  return {right,streak,best};
}
G.overtime = {
  localOnly: true,
  kind:"score",repeat:true,title:"Overtime",share:"Sweater Overtime",view:"view-overtime",max:100,next:"Play again",hideReveal:true,
  pool:()=>PLAYERS.length>=20?PLAYERS:[], daily:k=>DAILY.overtime[k] || overtimeRandom(seeded(hash(`overtime:${k}`))),
  random:()=>({...overtimeRandom(Math.random),rid:Math.random()}),
  tid:t=>`overtime-v1:${t.rid || hash(JSON.stringify(t.rounds))}`,player:()=>null,meta:()=>"",isWin:()=>false,
  score:(t,g)=>overtimeTally(t,g).right,
  isDone:(t,g)=>g.includes("END") || arcadeAnswers(g).length>=t.rounds.length,
  wonGame:(t,g)=>overtimeTally(t,g).right>=10, celebrate:(t,g)=>overtimeTally(t,g).right>=10,
  archiveStatus:h=>`${h.s} right`,onFinish:st=>arcadeBest("overtime",st),
  endText(t,g){const r=overtimeTally(t,g);return {result:`${r.right} right ${r.right===1?"answer":"answers"}`,cheer:`Best streak: ${r.best}${arcadeAnswers(g).length===100?" · Board cleared!":""}`};},
  shareText(t,s,n,link){const r=overtimeTally(t,s.guesses);return `Sweater Overtime #${n}\n${r.right} right answers · Best streak ${r.best}${link}`;},
  reset(){stopOvertime();$("otTime").textContent="0:30";$("otTime").classList.remove("urgent");$("otMeter").style.width="50%";$("otFeedback").textContent="Start with 30 seconds. Right answers add 3 seconds; wrong answers cost 5.";},
  guess(t,x){
    if(x==="START" || x==="END")return false;
    if(!S.overtime.guesses.includes("START") || !/^\d+:[0-3]$/.test(x))return null;
    const [i]=x.split(":").map(Number);
    return i===arcadeAnswers(S.overtime.guesses).length && i<t.rounds.length?false:null;
  },
  render(t,st){
    const r=overtimeTally(t,st.guesses),run=overtimeRun;
    $("otScore").textContent=r.right;$("otStreak").textContent=r.streak;
    $("otStart").hidden=!!run || st.over || st.guesses.includes("START");$("otEnd").hidden=!run || st.over;
    if(st.over){stopOvertime();$("otTime").textContent="0:00";$("otMeter").style.width="0%";$("otRound").textContent="Final score";$("otQ").textContent="Overtime is over.";$("otAnswers").innerHTML="";$("otFeedback").textContent="";}
    else if(run){
      const q=t.rounds[run.index];
      $("otRound").textContent=`Question ${run.index+1} / ${t.rounds.length}`;$("otQ").textContent=q.q;
      $("otAnswers").innerHTML=q.o.map((o,i)=>`<button type="button" class="ot-answer${run.locked?(i===q.a?" right":i===run.choice?" wrong":""):""}" data-ot="${i}"${run.locked?" disabled":""}>${esc(o)}</button>`).join("");
    }else{$("otRound").textContent="Sudden-death trivia";$("otQ").textContent="Keep the clock alive.";$("otAnswers").innerHTML="";}
    recoverArcade("overtime",st,run);
  },
};
function paintOvertimeClock(now){
  if(!overtimeRun)return;
  const seconds=Math.max(0,Math.ceil((overtimeRun.deadline-now)/1000));
  $("otTime").textContent=`${Math.floor(seconds/60)}:${String(seconds%60).padStart(2,"0")}`;
  $("otTime").classList.toggle("urgent",seconds<=10);$("otMeter").style.width=`${Math.max(0,Math.min(100,(overtimeRun.deadline-now)/600))}%`;
}
function startOvertime(){
  const st=S.overtime;
  if(game!=="overtime" || !st.target || st.over || overtimeRun || st.guesses.includes("START"))return;
  overtimeRun={deadline:performance.now()+30000,index:0,locked:false,ready:0,choice:null,raf:0};
  $("otFeedback").textContent="+3 seconds right · −5 seconds wrong";doGuess("START");
  const step=now=>{
    const run=overtimeRun;if(!run || game!=="overtime")return;
    paintOvertimeClock(now);
    if(now>=run.deadline){endArcade("overtime");return;}
    if(run.locked && now>=run.ready){
      run.index++;run.locked=false;run.choice=null;G.overtime.render(st.target,st);
      $("otQuestion").classList.remove("next-round");void $("otQuestion").offsetWidth;$("otQuestion").classList.add("next-round");
      $("otFeedback").textContent="+3 seconds right · −5 seconds wrong";
    }
    run.raf=requestAnimationFrame(step);
  };
  overtimeRun.raf=requestAnimationFrame(step);
}
function answerOvertime(choice){
  const run=overtimeRun,st=S.overtime,now=performance.now();
  if(game!=="overtime" || !run || run.locked || st.over)return;
  if(now>=run.deadline){endArcade("overtime");return;}
  const right=st.target.rounds[run.index].a===choice;
  run.locked=true;run.choice=choice;run.ready=now+550;
  run.deadline=right?Math.min(now+60000,run.deadline+3000):run.deadline-5000;
  $("otFeedback").textContent=right?"+3 seconds":"−5 seconds";
  paintOvertimeClock(now);doGuess(`${run.index}:${choice}`);
  if(overtimeRun && now>=run.deadline)endArcade("overtime");
}
$("otStart").onclick=startOvertime;$("otEnd").onclick=()=>endArcade("overtime");
$("otAnswers").addEventListener("click",e=>{const b=e.target.closest("[data-ot]");if(b)answerOvertime(Number(b.dataset.ot));});
document.addEventListener("keydown",e=>{
  if(e.repeat || onHub || document.querySelector(".modal.open") || /INPUT|TEXTAREA|SELECT/.test(e.target.tagName))return;
  if(game==="overtime" && /^[1-4]$/.test(e.key)){e.preventDefault();answerOvertime(Number(e.key)-1);}
  if(game==="goalie" && goalieRun?.shot){const zone={q:0,e:1,z:2,c:3," ":4}[e.key.toLowerCase()];if(zone!==undefined){e.preventDefault();commitSave(zone);}}
});
document.addEventListener("visibilitychange",()=>{if(document.hidden){if(goalieRun)endArcade("goalie",true);if(overtimeRun)endArcade("overtime",true);}});
window.addEventListener("pagehide",()=>{if(goalieRun)endArcade("goalie",true);if(overtimeRun)endArcade("overtime",true);});

// finish a running arcade game if the player leaves it
function leaveGame(g) {
  if (g === "goalie" && goalieRun) endArcade("goalie",true);
  if (g === "overtime" && overtimeRun) endArcade("overtime",true);
  if (g === "puck" && puckRun) { stopPuck(); if (!S.puck.over) doGuess("END"); }
  if (g === "shoot" && shootUI.phase === "aim") shootUI = { phase: "ask" };
}

// ======================= two truths, higher or lower: teams, mystery season =======================
const FACT_KINDS = ["team", "position", "nation", "number", "draftYear", "seasons", "height", "bestGoals", "games"];
function factText(p, kind, rnd, wrong = false) {
  const one = arr => arr[Math.floor(rnd() * arr.length)];
  const inches = v => `${Math.floor(v / 12)}′${v % 12}″`;
  const seasons = seasonsOf(p).length, games = seasonsOf(p).reduce((n, r) => n + r.gp, 0);
  if (kind === "team") {
    const t = wrong ? one(Object.keys(TEAMS).filter(x => x !== p.team)) : p.team;
    return `Plays for ${teamName(t)}`;
  }
  if (kind === "position") {
    if (!POS_LABELS[p.pos]) return null;
    const k = wrong ? one(Object.keys(POS_LABELS).filter(x => x !== p.pos)) : p.pos;
    return `Is a ${POS_LABELS[k].toLowerCase()}`;
  }
  if (kind === "nation") {
    const known = Object.keys(COUNTRY_NAMES);
    const n = wrong ? one(known.filter(x => x !== p.nation)) : p.nation;
    return `Was born in ${(COUNTRY_NAMES[n] || n).replace(/^the /, "")}`;
  }
  if (kind === "number") {
    if (!p.number) return null;
    return `Wears #${wrong ? Math.max(1, p.number + one([-9, -7, -5, 5, 7, 9])) : p.number}`;
  }
  if (kind === "draftYear") {
    if (!hasDraft(p)) return null;
    return `Was drafted in ${wrong ? p.draft[0] + one([-4, -3, 3, 4]) : p.draft[0]}`;
  }
  if (kind === "seasons") {
    if (seasons < 2) return null;
    return `Has played ${wrong ? Math.max(1, seasons + one([-3, -2, 2, 3])) : seasons} NHL seasons`;
  }
  if (kind === "height") {
    if (!p.ht) return null;
    return `Is ${inches(wrong ? p.ht + one([-3, -2, 2, 3]) : p.ht)} tall`;
  }
  if (kind === "bestGoals") {
    const v = p.pos === "G" ? 0 : hlValue(p, "goals").v;
    if (!v) return null;
    return `Once scored ${wrong ? Math.max(0, v + one([-12, -8, 8, 12])) : v} goals in a season`;
  }
  if (games < 100) return null;
  const floor = Math.floor(games / 100) * 100;
  return `Has played over ${wrong ? floor + 300 : floor} NHL games`;
}
function truthsRandom(rnd) {
  const rounds = [], seen = new Set();
  for (let i = 0; i < 400 && rounds.length < 5; i++) {
    const p = pick(PLAYERS);
    if (seen.has(p.id)) continue;
    const kinds = shuffled(FACT_KINDS, rnd).filter(k => factText(p, k, rnd) && factText(p, k, rnd, true));
    if (kinds.length < 3) continue;
    const lines = [factText(p, kinds[0], rnd), factText(p, kinds[1], rnd), factText(p, kinds[2], rnd, true)];
    if (new Set(lines).size < 3) continue;
    const order = shuffled([0, 1, 2], rnd);
    rounds.push({ p: p.id, s: order.map(i => lines[i]), f: order.indexOf(2) });
    seen.add(p.id);
  }
  return rounds.length === 5 ? { rounds, rid: Math.random() } : null;
}
G.truths = {
  kind: "score", repeat: true, title: "Two Truths", share: "Sweater Two Truths", view: "view-truths",
  max: 5, next: "Play again", hideReveal: true,
  cheers: ["Lie detector! 🔍", "Sharp! 🧠", "Nice work! 💪", "Good eye! 🏒", "Time's up!"],
  pool: () => PLAYERS.length >= 20 ? PLAYERS : [],
  daily(k) {
    const v = DAILY.truths[k];
    if (v && v.rounds && v.rounds.length === 5 && v.rounds.every(r => BYID.has(r.p))) return v;
    return truthsRandom(seeded(hash("sweater-truths-" + k)));
  },
  random: () => truthsRandom(Math.random),
  tid: t => `truths:${t.rid || hash(t.rounds.map(r => r.s.join("|")).join())}`,
  player: t => BYID.get(t.rounds[Math.min(S.truths.guesses.length, 4)].p),
  right: (t, g, i) => Number(g) === t.rounds[i].f,
  score(t, g) { return g.filter((x, i) => this.right(t, x, i)).length * 2; },
  isWin: () => false,
  isDone: (t, g) => g.length >= 5,
  wonGame(t, g) { return this.score(t, g) === 10; },
  meta: () => "",
  endText(t, g, won) {
    const n = this.score(t, g) / 2;
    return { result: `${n} of 5 right`, cheer: won ? "Perfect! Nothing gets past you 🔍" : n >= 3 ? "Solid detective work 🧠" : "Tricky ones today 🏒" };
  },
  celebrate: (t, g, won) => won,
  archiveStatus: h => `${h.s / 2}/5`,
  shareText(t, saved, num, link) {
    const marks = saved.guesses.map((g, i) => this.right(t, g, i) ? "🟩" : "🟥").join("");
    return `Sweater Two Truths #${num}\n${marks}\n${this.score(t, saved.guesses) / 2}/5 right${link}`;
  },
  reset() { this.showing = false; },
  guess(t, g) { return /^[0-2]$/.test(String(g)) ? false : null; },
  render(t, st) {
    const i = st.guesses.length, last = i - 1;
    const showing = this.showing && last >= 0;
    const r = t.rounds[showing ? last : Math.min(i, 4)], p = BYID.get(r.p);
    $("twDots").innerHTML = [0, 1, 2, 3, 4].map(n =>
      `<span class="shdot${n === i && !st.over ? " now" : ""}">${n < i ? (this.right(t, st.guesses[n], n) ? "✓" : "✗") : n + 1}</span>`).join("");
    $("twImg").onerror = function () { this.onerror = null; this.src = FALLBACK; };
    $("twImg").src = p.headshot || FALLBACK;
    $("twName").textContent = p.name;
    $("twQ").textContent = st.over && !showing ? "That's the game" : "Which one is false?";
    const myPick = showing ? Number(st.guesses[last]) : -1;
    $("twList").innerHTML = st.over && !showing ? "" : r.s.map((line, n) => {
      const isFalse = n === r.f, mine = n === myPick;
      const cls = showing ? (isFalse ? " isfalse" : " istrue") + (mine ? " mine" : "") : "";
      const tag = showing ? `<span class="twtag">${isFalse ? "False" : "True"}${mine ? " · your pick" : ""}</span>` : "";
      return `<button type="button" class="twline${cls}" data-c="${n}"${showing ? " disabled" : ""}>
        <span class="twmark">${showing ? (isFalse ? "✗" : "✓") : String.fromCharCode(65 + n)}</span>
        <span class="twtext">${esc(line)}</span>${tag}</button>`;
    }).join("");
    $("twMsg").innerHTML = showing
      ? (this.right(t, st.guesses[last], last) ? '<b class="good">Right!</b> You found the false statement.'
        : '<b class="bad">Not quite.</b> The false statement is marked ✗.')
      : st.over ? "" : "Two of these are true.";
    $("twNext").hidden = !(showing && !st.over);
  },
};
$("twList").addEventListener("click", e => {
  const b = e.target.closest("[data-c]"), st = S.truths;
  if (!b || st.over || G.truths.showing) return;
  G.truths.showing = true;
  doGuess(b.dataset.c);
});
$("twNext").onclick = () => { G.truths.showing = false; G.truths.render(S.truths.target, S.truths); };

// ---- Higher or Lower: Teams ----
const HLT_METRICS = {
  age:    { name: "Average age",        unit: "years on average",       up: "Older",  down: "Younger", show: v => v.toFixed(1) },
  height: { name: "Average height",     unit: "tall on average",        up: "Taller", down: "Shorter", show: v => `${Math.floor(v / 12)}′${Math.round(v % 12)}″` },
  goals:  { name: "Career goals",       unit: "career goals on the roster", up: "More", down: "Fewer", show: v => v.toLocaleString() },
  games:  { name: "Career games",       unit: "career NHL games on the roster", up: "More", down: "Fewer", show: v => v.toLocaleString() },
  abroad: { name: "Players from abroad", unit: "players born outside Canada and the USA", up: "More", down: "Fewer", show: v => String(v) },
};
function hltValue(team, metric) {
  const roster = PLAYERS.filter(p => p.team === team);
  if (!roster.length) return 0;
  if (metric === "age") return Math.round(roster.reduce((n, p) => n + ageOf(p.birth), 0) / roster.length * 10) / 10;
  if (metric === "height") { const h = roster.filter(p => p.ht); return h.length ? Math.round(h.reduce((n, p) => n + p.ht, 0) / h.length * 10) / 10 : 0; }
  if (metric === "goals") return roster.reduce((n, p) => n + rankValue(p, "goals"), 0);
  if (metric === "games") return roster.reduce((n, p) => n + rankValue(p, "gp"), 0);
  return roster.filter(p => !["CAN", "USA"].includes(p.nation)).length;
}
function hltRandom(rnd) {
  const teams = Object.keys(TEAMS).filter(t => PLAYERS.filter(p => p.team === t).length >= 10);
  if (teams.length < 4) return null;
  const metrics = Object.keys(HLT_METRICS), rounds = [];
  while (rounds.length < HL_LEN) {
    const recent = rounds.slice(-2).flatMap(r => [r[0], r[2]]);
    const metricChoices = metrics.filter(m => m !== rounds.at(-1)?.[4]);
    let pair = null;
    for (let attempt = 0; attempt < 100 && !pair; attempt++) {
      const metric = metricChoices[Math.floor(rnd() * metricChoices.length)];
      const a = teams[Math.floor(rnd() * teams.length)], b = teams[Math.floor(rnd() * teams.length)];
      if (a === b || (attempt < 70 && (recent.includes(a) || recent.includes(b)))) continue;
      const av = hltValue(a, metric), bv = hltValue(b, metric);
      if (av === bv) continue;
      pair = [a, av, b, bv, metric];
    }
    if (!pair) {
      const metric = metricChoices[0], a = teams[rounds.length % teams.length];
      const b = teams[(rounds.length + 1) % teams.length];
      pair = [a, hltValue(a, metric), b, hltValue(b, metric), metric];
    }
    rounds.push(pair);
  }
  return { rounds };
}
G.hlt = {
  kind: "streak", repeat: true, title: "Team Higher or Lower", share: "Sweater Team H/L", view: "view-hlt",
  max: HL_LEN, next: "Play again", hideReveal: true,
  pool: () => Object.keys(TEAMS).filter(t => PLAYERS.filter(p => p.team === t).length >= 10),
  daily(k) {
    const v = DAILY.hlt[k];
    if (v && Array.isArray(v.rounds) && v.rounds.length && v.rounds.every(r => Array.isArray(r) && r.length === 5 && HLT_METRICS[r[4]])) return v;
    return hltRandom(seeded(hash("sweater-hlt-" + k)));
  },
  random: () => hltRandom(Math.random),
  tid: t => t.rid ? `hlt:${t.rid}` : `hlt:${hash(t.rounds.map(r => r.join(":" )).join("|"))}`,
  limit: t => t.rounds.length,
  correct(t, i, ans) { const r = t.rounds[i]; if (!r) return false; const a = Number(r[1]), b = Number(r[3]); return ans === "H" ? b >= a : b <= a; },
  score(t, g) { let n = 0; for (const [i, x] of g.entries()) { if (!this.correct(t, i, x)) break; n++; } return n; },
  isWin: () => false,
  isDone(t, g) { return g.some((x, i) => !this.correct(t, i, x)) || g.length >= this.limit(t); },
  wonGame(t, g) { return g.length >= this.limit(t) && this.score(t, g) === g.length; },
  player: () => null,
  meta(t) {
    // Results are shown after the guess is recorded, so use that final round
    // rather than advancing the small result line to the next comparison.
    const ended = S.hlt.over && S.hlt.guesses.length;
    const i = Math.max(0, Math.min(ended ? S.hlt.guesses.length - 1 : S.hlt.guesses.length, t.rounds.length - 1));
    const r = t.rounds[i], info = HLT_METRICS[r[4]];
    return `${teamName(r[0])}: ${info.show(r[1])} ${info.unit} · ${teamName(r[2])}: ${info.show(r[3])}`;
  },
  endText(t, g, won) {
    const n = this.score(t, g);
    return { result: won ? `Perfect! All ${n} right` : `Streak: ${n}`,
             cheer: won ? "Flawless run! 🏆" : n >= 15 ? "Legendary! 🔥" : n >= 8 ? "Hot streak! 🔥" : n >= 3 ? "Nice run! 💪" : "Tough start! 🏒" };
  },
  celebrate(t, g, won) { return won || this.score(t, g) >= 10; },
  archiveStatus: h => `🔥 ${h.s}`,
  shareText(t, saved, num, link) {
    const marks = saved.guesses.map((x, i) => this.squares(t, x, i)).join("");
    const rows = (marks.match(/(?:🟩|🟥){1,10}/gu) || []).join("\n");
    const won = this.wonGame(t, saved.guesses);
    return `Sweater Team H/L #${num} · Mixed stats\nStreak: ${this.score(t, saved.guesses)}${won ? " (perfect!)" : ""}\n\n${rows}${link}`;
  },
  onFinish(st) { const k = "sweater-hlt-best", n = this.score(st.target, st.guesses);
    if (n > (store.get(k) || 0)) store.set(k, n); },
  reset() { clearTimeout(this.timer); this.pending = false; },
  card(t, i, side, reveal, state) {
    const r = t.rounds[i], right = side === "b";
    const team = r[right ? 2 : 0], value = r[right ? 3 : 1], other = teamName(r[right ? 0 : 2]), info = HLT_METRICS[r[4]];
    return `<div class="hlcard ${state || ""}">
      <img class="hltlogo" src="${logo(team)}" alt="" onerror="this.style.visibility='hidden'">
      <p class="hlname">${esc(teamName(team))}</p>
      ${reveal ? `<p class="hlval"><b>${info.show(value)}</b></p><p class="hlunit">${esc(info.unit)}</p>`
        : `<p class="hlunit">${esc(info.name.toLowerCase())}:</p>
           <div class="hlbtns"><button class="btn hlbtn" type="button" data-hlt="H">▲ ${info.up}</button>
           <button class="btn hlbtn" type="button" data-hlt="L">▼ ${info.down}</button></div>
           <p class="hlyr">than ${esc(other)}</p>`}
    </div>`;
  },
  guess(t, x, fresh) {
    if (x !== "H" && x !== "L") return null;
    const i = S.hlt.guesses.length;
    if (i >= t.rounds.length) return null;
    const ok = this.correct(t, i, x);
    if (fresh) {
      this.pending = true;
      $("htB").innerHTML = this.card(t, i, "b", true, ok ? "ok" : "bad");
      clearTimeout(this.timer);
      this.timer = setTimeout(() => { this.pending = false; if (game === "hlt") this.render(t, S.hlt, true); }, ok ? 1100 : 1400);
    }
    return ok;
  },
  render(t, st, slide = false) {
    if (this.pending) return;
    const i = st.over ? Math.max(0, Math.min(st.guesses.length - 1, t.rounds.length - 1)) : st.guesses.length;
    const info = HLT_METRICS[t.rounds[i][4]];
    $("htIntro").innerHTML = `Which team has the higher <b>${esc(info.name.toLowerCase())}</b>?`;
    $("htStreak").textContent = this.score(t, st.guesses);
    $("htBest").textContent = Math.max(store.get("sweater-hlt-best") || 0, this.score(t, st.guesses));
    $("htLeft").textContent = st.over ? "" : `${Math.max(0, this.limit(t) - st.guesses.length)} left in today's run · ties count as right`;
    const lastOk = st.over && st.guesses.length ? this.correct(t, st.guesses.length - 1, st.guesses[st.guesses.length - 1]) : null;
    $("htA").innerHTML = this.card(t, i, "a", true, "");
    $("htB").innerHTML = this.card(t, i, "b", st.over, st.over ? (lastOk ? "ok" : "bad") : "");
    if (slide) { $("htPair").classList.remove("slide"); void $("htPair").offsetWidth; $("htPair").classList.add("slide"); }
  },
  squares(t, x, i) { return this.correct(t, i, x) ? "🟩" : "🟥"; },
};
$("htPair").addEventListener("click", e => { const b = e.target.closest("[data-hlt]"); if (b) doGuess(b.dataset.hlt); });

// ---- Mystery Season ----
G.season = {
  title: "Mystery Season", share: "Sweater Mystery Season", view: "view-season", max: 3, next: "Next player",
  cheers: ["Spot on! 🎯", "Nice read! 🧠", "Just in time! 🚨"],
  pool: () => PLAYERS.filter(p => seasonsOf(p).length >= 4),
  daily(k) {
    const v = DAILY.season[k], p = v && BYID.get(v.id);
    if (p && seasonsOf(p).some(r => r.y === v.y)) return { p, y: v.y };
    const pool = this.pool();
    const q = pool[hash("sweater-season-" + k) % pool.length], rows = seasonsOf(q);
    return { p: q, y: rows[hash("season-" + k) % rows.length].y };
  },
  random() { const p = pick(this.pool()), rows = seasonsOf(p); return { p, y: pick(rows).y }; },
  tid: t => `${t.p.id}:${t.y}`,
  player: t => t.p,
  isWin: (t, y) => y === t.y,
  meta(t) {
    const row = seasonsOf(t.p).find(r => r.y === t.y) || { teams: [t.p.team] };
    return `${seasonLabel(t.y)} with ${row.teams.map(teamName).join(" and ")}`;
  },
  reset(t) {
    $("seImg").onerror = function () { this.onerror = null; this.src = FALLBACK; };
    $("seImg").src = t.p.headshot || FALLBACK;
    $("seName").textContent = t.p.name;
    $("seMeta").innerHTML = `<img src="${logo(t.p.team)}" alt="" onerror="this.remove()"> ${esc(teamName(t.p.team))} · ${posName(t.p)}`;
    const row = seasonsOf(t.p).find(r => r.y === t.y);
    $("seStats").innerHTML = statHeads(t.p).map((h, i) => `<span class="chip"><b>${statCells(t.p, row)[i]}</b> ${h}</span>`).join("");
  },
  guess(t, y) { return Number.isInteger(y) ? y === t.y : null; },
  render(t, st) {
    const rows = seasonsOf(t.p), left = this.max - st.guesses.length;
    $("seList").innerHTML = rows.map(r => {
      const tried = st.guesses.includes(r.y);
      const cls = st.over && r.y === t.y ? " hit" : tried ? " miss" : "";
      const arrow = tried && r.y !== t.y ? (t.y > r.y ? " ↑" : " ↓") : "";
      return `<button type="button" class="sebtn${cls}" data-y="${r.y}"${tried || st.over ? " disabled" : ""}>${seasonLabel(r.y)}${arrow}</button>`;
    }).join("");
    $("seLeft").textContent = st.over ? "" : `${left} ${left === 1 ? "try" : "tries"} left · arrows point to a later or earlier season`;
  },
  squares: (t, y) => y === t.y ? "🟩" : "⬛",
};
$("seList").addEventListener("click", e => {
  const b = e.target.closest("[data-y]");
  if (b && !b.disabled) doGuess(Number(b.dataset.y));
});

// ======================= playoff hero, trophy case, mystery roster =======================
const poSeasons = p => {
  const by = new Map();
  for (const [y, t, gp, a, b, c] of (p.po || [])) {
    const r = by.get(y) || { y, teams: [], gp: 0, a: 0, b: 0, c: 0 };
    r.teams.push(t); r.gp += gp; r.a += a; r.b += b; r.c += c;
    by.set(y, r);
  }
  return [...by.values()].sort((x, y) => x.y - y.y);
};
const PO_POOL = PLAYERS.filter(p => poSeasons(p).length >= 3);
const poHeads = p => p.pos === "G" ? ["GP", "W", "GAA", "SV%"] : ["GP", "G", "A", "PTS"];
const poCells = (p, r) => p.pos === "G"
  ? [r.gp, r.a, (r.gp ? r.b / r.teams.length : 0).toFixed(2), (r.gp ? r.c / r.teams.length : 0).toFixed(3).replace(/^0/, "")]
  : [r.gp, r.a, r.b, r.c];

G.playoff = {
  title: "Playoff Hero", share: "Sweater Playoff Hero", view: "view-playoff", max: 6, next: "Next player",
  cheers: ["Playoff legend! 🏆", "Snipe! 🎯", "Hat trick! 🎩", "Nice read! 🏒", "Got there! 💪", "Buzzer beater! 🚨"],
  pool: () => PO_POOL,
  daily(k) {
    const p = BYID.get((DAILY.playoff[k] || {}).id);
    return p && poSeasons(p).length >= 3 ? p : PO_POOL[hash("sweater-po-" + k) % PO_POOL.length];
  },
  random: () => pick(PO_POOL),
  tid: t => t.id, player: t => t, isWin: (t, id) => id === t.id,
  meta: t => `${t.team} · #${t.number} · ${posName(t)}`,
  reset() { $("phWrong").innerHTML = ""; this.shown = 0; },
  guess(t, id) {
    const p = BYID.get(id);
    if (!p) return null;
    if (p.id !== t.id) addWrong("phWrong", p);
    return p.id === t.id;
  },
  render(t, st) {
    const rows = poSeasons(t), wrong = st.guesses.filter(id => id !== t.id).length;
    const shown = st.over ? rows.length : Math.min(rows.length, 1 + wrong);
    const runs = rows.reduce((n, r) => n + r.gp, 0), pts = rows.reduce((n, r) => n + (t.pos === "G" ? r.a : r.c), 0);
    $("phIntro").textContent = `${posName(t)} · ${rows.length} playoff runs · ${runs} playoff games · ${pts} career playoff ${t.pos === "G" ? "wins" : "points"}`;
    const hint = !st.over && wrong >= 4;
    $("phHint").hidden = !hint;
    if (hint) $("phHint").innerHTML = `Hint: he plays for <img src="${logo(t.team)}" alt="" onerror="this.remove()"><b>${esc(teamName(t.team))}</b> now`;
    $("phHead").innerHTML = `<th>Playoffs</th>${poHeads(t).map(h => `<th>${h}</th>`).join("")}${st.over ? "<th>Team</th>" : ""}`;
    $("phRows").innerHTML = rows.map((r, i) => {
      if (i >= shown) return `<tr class="locked"><td>${seasonLabel(r.y)}</td><td colspan="${poHeads(t).length}">🔒 Locked</td></tr>`;
      const cls = this.shown && i >= this.shown ? ' class="newrow"' : "";
      return `<tr${cls}><td>${seasonLabel(r.y)}</td>${poCells(t, r).map(v => `<td>${v}</td>`).join("")}` +
        (st.over ? `<td>${r.teams.map(x => esc(x || "?")).join(" / ")}</td>` : "") + "</tr>";
    }).join("");
    $("phLeft").textContent = st.over ? "" :
      `${this.max - st.guesses.length} tries left. Each wrong guess unlocks another playoff run.` +
      (wrong < 4 ? " A team hint unlocks after 4 wrong guesses." : "");
    this.shown = shown;
  },
  squares: (t, id) => id === t.id ? "🟩" : "⬛",
};

// ---- Trophy Case ----
// Every trophy round the page has been given, so unlimited play draws on the same history.
const TROPHY_HISTORY = (() => {
  const winners = new Map();
  for (const [t, y, w, team = ""] of TROPHY_WINNERS) {
    if (!t || !Number.isInteger(y) || !w) continue;
    winners.set(`${t}:${y}`, { t, y, w, team });
  }
  for (const day of Object.values(DAILY.trophy || {})) {
    for (const r of day.rounds || []) {
      const names = r.names || (r.ids || []).map(i => (BYID.get(i) || {}).name);
      if (!names || !names[r.a]) continue;
      const old = winners.get(`${r.t}:${r.y}`);
      winners.set(`${r.t}:${r.y}`, { t: r.t, y: r.y, w: names[r.a],
        team: (r.teams || [])[r.a] || (old && old.team) || "" });
    }
  }
  // Build these after combining the full history and the daily fallback.  This
  // keeps the multiple-choice pools playable even if an award-history fetch
  // only supplied the daily rounds during a particular build.
  const all = [...winners.values()], byTrophy = {};
  for (const e of all) byTrophy[e.t] = [...(byTrophy[e.t] || []), { y: e.y, w: e.w, team: e.team }];
  return { winners: all, byTrophy };
})();
function trophyTeam(trophy, year, winner) {
  const candidates = (TROPHY_HISTORY.byTrophy[trophy] || [])
    .filter(e => e.w === winner && e.team)
    .sort((a, b) => Math.abs(a.y - year) - Math.abs(b.y - year));
  return candidates.length ? candidates[0].team : "";
}
function trophyRandom(rnd, trophy = "all") {
  const entries = trophy === "all" ? TROPHY_HISTORY.winners : TROPHY_HISTORY.winners.filter(e => e.t === trophy);
  if (entries.length < 20) return null;
  const rounds = [], used = new Set();
  for (let i = 0; i < 3000 && rounds.length < 20; i++) {
    const e = entries[Math.floor(rnd() * entries.length)];
    if (used.has(`${e.t}:${e.y}`)) continue;
    const all = (TROPHY_HISTORY.byTrophy[e.t] || []).filter(x => x.w !== e.w);
    let pool = all.filter(x => Math.abs(x.y - e.y) <= 12);
    if (new Set(pool.map(x => x.w)).size < 3) pool = all.filter(x => Math.abs(x.y - e.y) <= 20);
    if (new Set(pool.map(x => x.w)).size < 3) pool = all;
    pool = [...new Map(pool.sort((a, b) => Math.abs(a.y - e.y) - Math.abs(b.y - e.y)).map(x => [x.w, x])).values()];
    if (pool.length < 3) continue;
    const choices = shuffled(pool, rnd).slice(0, 3);
    const a = Math.floor(rnd() * 4);
    choices.splice(a, 0, e);
    rounds.push({ t: e.t, y: e.y, names: choices.map(x => x.w), teams: choices.map(x => x.team || ""), a });
    used.add(`${e.t}:${e.y}`);
  }
  return rounds.length === 20 ? { rounds, rid: Math.random() } : null;
}
G.trophy = {
  kind: "score", repeat: true, title: "Trophy Case", share: "Sweater Trophy Case", view: "view-trophy",
  max: 20, next: "Play again", hideReveal: true,
  length(t) { return Math.min(Number(store.get("sweater-trophy-rounds")) || 5, t.rounds.length); },
  trophy() { return store.get("sweater-trophy-filter") || "all"; },
  trophies() { return Object.keys(TROPHY_HISTORY.byTrophy).filter(t => TROPHY_HISTORY.winners.filter(e => e.t === t).length >= 20).sort(); },
  pool: () => TROPHY_HISTORY.winners.length >= 20 ? PLAYERS : [],
  daily(k) {
    const trophy = this.trophy();
    const v = DAILY.trophy[k];
    if (trophy === "all" && v && v.rounds && v.rounds.length >= 20 && v.rounds.every(r => (r.names || []).length === 4 || (r.ids || []).every(i => BYID.has(i)))) {
      return { rounds: v.rounds.map(r => {
        const names = r.names || r.ids.map(i => (BYID.get(i) || {}).name || "?");
        return { ...r, names, teams: r.teams || names.map(name => trophyTeam(r.t, r.y, name)) };
      }) };
    }
    return trophyRandom(seeded(hash(`sweater-trophy-${trophy}-${k}`)), trophy);
  },
  random() { return trophyRandom(Math.random, this.trophy()); },
  tid(t) { return `trophy:${this.trophy()}:${t.rid || hash(t.rounds.map(r => `${r.t}${r.y}`).join())}`; },
  player: () => null,
  right: (t, g, i) => Number(g) === t.rounds[i].a,
  score(t, g) { return g.filter((x, i) => this.right(t, x, i)).length * 2; },
  isWin: () => false,
  isDone(t, g) { return g.length >= this.length(t); },
  wonGame(t, g) { return this.score(t, g) === this.length(t) * 2; },
  meta: () => "",
  endText(t, g, won) {
    const n = this.score(t, g) / 2, of = this.length(t);
    return { result: `${n} of ${of} right`,
             cheer: won ? "You know your trophies! 🏆" : n >= of * .6 ? "Nicely done 🧠" : "Tough ballot today 🏒" };
  },
  celebrate: (t, g, won) => won,
  archiveStatus: h => `${h.s / 2} right`,
  shareText(t, saved, num, link) {
    const marks = saved.guesses.map((g, i) => this.right(t, g, i) ? "🟩" : "🟥").join("");
    const rows = (marks.match(/(?:🟩|🟥){1,10}/gu) || []).join("\n");
    return `Sweater Trophy Case #${num}\n${rows}\n${this.score(t, saved.guesses) / 2}/${saved.guesses.length} right${link}`;
  },
  reset() { this.showing = false; },
  guess(t, g) { return /^[0-3]$/.test(String(g)) ? false : null; },
  render(t, st) {
    const of = this.length(t), i = st.guesses.length, last = i - 1, showing = this.showing && last >= 0;
    const r = t.rounds[showing ? last : Math.min(i, of - 1)];
    const selectedTrophy = this.trophy();
    $("trTrophy").innerHTML = `<option value="all">All trophies</option>${this.trophies().map(name =>
      `<option value="${esc(name)}">${esc(name)}</option>`).join("")}`;
    $("trTrophy").value = selectedTrophy;
    $("trRounds").value = String(of);
    $("trDots").innerHTML = Array.from({ length: of }, (_, n) =>
      `<span class="shdot${n === i && !st.over ? " now" : ""}">${n < i ? (this.right(t, st.guesses[n], n) ? "✓" : "✗") : n + 1}</span>`).join("");
    $("trQ").innerHTML = st.over && !showing ? "That's the game"
      : `<span class="trophy-prompt">Who won the</span><strong class="trophy-title">${esc(r.t)}</strong><span class="trophy-season">${seasonLabel(r.y)}</span>`;
    $("trOpts").innerHTML = st.over && !showing ? "" : r.names.map((name, n) => {
      const cls = showing ? (n === r.a ? " right" : n === Number(st.guesses[last]) ? " wrong" : " dim") : "";
      const team = (r.teams || [])[n] || trophyTeam(r.t, r.y, name);
      return `<button type="button" class="shopt${cls}" data-c="${n}"${showing ? " disabled" : ""}>` +
        `${team ? `<img class="trlogo${logoToneClass(team)}" data-team="${esc(team)}" src="${logo(team)}" alt="" onerror="this.remove()">` : ""}<span class="trname">${esc(name)}</span></button>`;
    }).join("");
    // Keep each choice self-contained as well as using the delegated handler
    // below. This avoids an interaction dead-end if a browser misses a
    // delegated click while the setup animation is ending.
    $("trOpts").querySelectorAll("[data-c]:not([disabled])").forEach(b => {
      b.onclick = () => {
        if (S.trophy.over || G.trophy.showing) return;
        G.trophy.showing = true;
        doGuess(b.dataset.c);
      };
    });
    // Rules live in How to play; the answer tiles supply round feedback.
    $("trMsg").textContent = "";
    $("trMsg").hidden = true;
    $("trNext").hidden = !(showing && !st.over);
  },
};
$("trOpts").addEventListener("click", e => {
  const b = e.target.closest("[data-c]");
  if (!b || S.trophy.over || G.trophy.showing) return;
  G.trophy.showing = true;
  doGuess(b.dataset.c);
});
$("trNext").onclick = () => { G.trophy.showing = false; G.trophy.render(S.trophy.target, S.trophy); };
let trophySetupTimer = null;
function refreshTrophySetup() {
  const g = G.trophy, st = S.trophy, view = $(g.view);
  if (!g.pool().length) return noData();
  const puzzleDay = mode === "archive" ? archiveDay : dayKey();
  const t = mode === "unlimited" ? g.random() : g.daily(puzzleDay);
  if (!t) return noData();
  g.showing = false;
  st.day = puzzleDay;
  view.classList.remove("setup-change");
  startGame(t);                         // never restore a previous setup's answers
  void view.offsetWidth;                // restart the setup animation
  view.classList.add("setup-change");
  clearTimeout(trophySetupTimer);
  trophySetupTimer = setTimeout(() => view.classList.remove("setup-change"), 300);
}
$("trRounds").addEventListener("change", e => {
  store.set("sweater-trophy-rounds", Number(e.target.value));
  refreshTrophySetup();
});
$("trTrophy").addEventListener("change", e => {
  store.set("sweater-trophy-filter", e.target.value);
  refreshTrophySetup();
});

// ---- Mystery Roster ----
function mrosterRandom(rnd) {
  const teams = Object.keys(TEAMS).filter(t => PLAYERS.filter(p => p.team === t).length >= 6);
  if (!teams.length) return null;
  const team = teams[Math.floor(rnd() * teams.length)];
  return { team, ids: shuffled(PLAYERS.filter(p => p.team === team), rnd).slice(0, 6).map(p => p.id), rid: Math.random() };
}
G.mroster = {
  title: "Mystery Roster", share: "Sweater Mystery Roster", view: "view-mroster", max: 4, next: "Next team",
  cheers: ["Called it! 🎯", "Nice read! 🧠", "Got there! 💪", "Last chance, nailed it! 🚨"],
  hideReveal: true,
  pool: () => Object.keys(TEAMS).filter(t => PLAYERS.filter(p => p.team === t).length >= 6),
  daily(k) {
    const v = DAILY.mroster[k];
    if (v && v.team && TEAMS[v.team] && v.ids && v.ids.every(i => BYID.has(i))) return v;
    return mrosterRandom(seeded(hash("sweater-mroster-" + k)));
  },
  random: () => mrosterRandom(Math.random),
  tid: t => t.rid ? `mroster:${t.rid}` : `${t.team}:${hash(t.ids.join(","))}`,
  player: () => null,
  isWin: (t, abbr) => abbr === t.team,
  meta: t => `${teamName(t.team)} · ${t.ids.length} players shown`,
  state: (t, abbr) => abbr === t.team ? true : TEAMS[abbr] && TEAMS[abbr][1] === TEAMS[t.team][1] ? "near" : false,
  reset(t) {
    $("mrGrid").innerHTML = Object.entries(DIV_NAMES).map(([d, name]) =>
      `<div><h4>${name}</h4>${Object.keys(TEAMS).filter(a => TEAMS[a][1] === d)
        .sort((a, b) => TEAM_NAMES[a].localeCompare(TEAM_NAMES[b]))
        .map(a => `<button class="teambtn" type="button" data-team="${a}"><img alt="" src="${logo(a)}" onerror="this.style.visibility='hidden'"><span>${TEAM_NAMES[a]}</span></button>`).join("")}</div>`).join("");
  },
  guess(t, abbr) {
    if (!TEAMS[abbr]) return null;
    const b = $("mrGrid").querySelector(`[data-team="${abbr}"]`), s = this.state(t, abbr);
    if (b) b.classList.add(s === true ? "hit" : s === "near" ? "near" : "miss");
    return s === true;
  },
  render(t, st) {
    const shown = st.over ? t.ids.length : Math.min(t.ids.length, 1 + st.guesses.length);
    $("mrList").innerHTML = t.ids.slice(0, shown).map((id, i) => {
      const p = BYID.get(id);
      return `<li class="mrrow${i === shown - 1 && shown > 1 ? " newrow" : ""}">
        <span class="mrnum">#${p.number}</span>
        <span><b>${esc(p.name)}</b><small>${esc(posName(p))} · age ${ageOf(p.birth)} · ${esc(p.nation)}</small></span></li>`;
    }).join("");
    $("mrGrid").querySelectorAll(".teambtn").forEach(b => {
      b.disabled = st.over || st.guesses.includes(b.dataset.team);
      if (st.over && b.dataset.team === t.team) b.classList.add("hit");
    });
    const left = this.max - st.guesses.length;
    $("mrLeft").textContent = st.over ? "" :
      `${left} ${left === 1 ? "try" : "tries"} left · each wrong guess shows another player · yellow means same division`;
  },
  squares(t, abbr) { return sq(this.state(t, abbr)); },
};
$("mrGrid").addEventListener("click", e => {
  const b = e.target.closest(".teambtn");
  if (b && !b.disabled) doGuess(b.dataset.team);
});

// ======================= playoff history =======================
const CUPS_SECONDS = 600;
const cupsClock = seconds => `${Math.floor(Math.max(0, seconds) / 60)}:${String(Math.max(0, seconds) % 60).padStart(2, "0")}`;
const cupsNorm = s => norm(s).replace(/[^a-z0-9 ]/g, " ").replace(/\s+/g, " ").trim();
const cupsCols = t => t.mvp === false || !t.rows.some(r => r[3]) ? [1, 2] : [1, 2, 3];
// "penguins", "pittsburgh" and "pittsburgh penguins" all fill a Penguins square.
// Players need the surname, so "crosby" and "sidney crosby" count but "sidney" doesn't.
function cupsMatch(full, isPlayer, guess) {
  if (!full || guess.length < 3) return false;
  if (!(" " + full + " ").includes(" " + guess + " ")) return false;
  return !isPlayer || guess.split(" ").includes(full.split(" ").slice(-1)[0]);
}
const CUP_TEAM_ABBRS = {
  "anaheim ducks":"ANA", "boston bruins":"BOS", "buffalo sabres":"BUF", "calgary flames":"CGY",
  "carolina hurricanes":"CAR", "chicago blackhawks":"CHI", "colorado avalanche":"COL", "dallas stars":"DAL",
  "detroit red wings":"DET", "edmonton oilers":"EDM", "florida panthers":"FLA", "los angeles kings":"LAK",
  "minnesota north stars":"MNS", "hartford whalers":"HFD", "quebec nordiques":"QUE", "atlanta thrashers":"ATL", "atlanta flames":"AFM", "colorado rockies":"CLR", "arizona coyotes":"ARI", "phoenix coyotes":"PHX", "kansas city scouts":"KCS", "california golden seals":"CGS", "oakland seals":"OAK", "cleveland barons":"CLE", "montreal canadiens":"MTL", "mighty ducks of anaheim":"ANA", "nashville predators":"NSH",
  "new jersey devils":"NJD", "new york islanders":"NYI", "new york rangers":"NYR", "ottawa senators":"OTT",
  "philadelphia flyers":"PHI", "pittsburgh penguins":"PIT", "san jose sharks":"SJS", "st louis blues":"STL",
  "tampa bay lightning":"TBL", "vancouver canucks":"VAN", "vegas golden knights":"VGK", "washington capitals":"WSH"
};
const cupsTeamAbbr = value => TEAMS[value] ? value : (CUP_TEAM_ABBRS[cupsNorm(value)] || "");
const cupsAnswer = (name, team) => {
  const abbr = cupsTeamAbbr(team);
  return `<span class="cuanswer">${abbr ? `<img class="culogo${logoToneClass(abbr)}" src="${logo(abbr)}" alt="" onerror="this.remove()">` : ""}<span class="cuname">${esc(name)}</span></span>`;
};
function cupsKeys(rows, cols) {
  const cells = [];
  rows.forEach((r, y) => cols.forEach(c => cells.push({ row: y, col: c, full: cupsNorm(r[c]), player: c === 3 })));
  return cells;
}
function syncCupsStickyHeader() {
  const view = $("view-cups"), controls = view.querySelector(".cups-controls");
  if (!controls || view.hidden) return;
  view.style.setProperty("--cups-header-top", `${Math.ceil(controls.getBoundingClientRect().height)}px`);
}
window.addEventListener("resize", () => { if (game === "cups") syncCupsStickyHeader(); });
let cupsTimer = null, cupsMemory = null;
G.cups = {
  kind: "score", repeat: false, title: "Playoff History", share: "Sweater Playoff History",
  view: "view-cups", max: 999, next: "New grid", hideReveal: true,
  rows: () => CUP_ROWS.filter(r => r[0] >= 1980 && r[1] && r[2] && r[3]),
  pool() { return this.rows().length >= 40 ? [1] : []; },
  daily(k) {
    const rows = this.rows();
    return rows.length >= 40 ? { rows } : null;
  },
  random() {
    const rows = this.rows();
    return rows.length >= 40 ? { rows, rid: Math.random() } : null;
  },
  tid: t => t.rid ? `cups:${t.rid}` : `cups:${t.rows[0][0]}-${t.rows[t.rows.length - 1][0]}`,
  player: () => null,
  cells(t) { this._cells = this._cells && this._cells.t === t ? this._cells : { t, list: cupsKeys(t.rows, cupsCols(t)) }; return this._cells.list; },
  filled(t, g) {
    const typed = g.filter(x => x !== "END").map(cupsNorm);
    return this.cells(t).map(c => typed.some(x => cupsMatch(c.full, c.player, x)));
  },
  score(t, g) { return this.filled(t, g).filter(Boolean).length; },
  isWin: () => false,
  isDone(t, g) { return g.includes("END") || this.score(t, g) >= this.cells(t).length; },
  wonGame(t, g) { return this.score(t, g) >= this.cells(t).length; },
  meta: t => `${seasonLabel(t.rows[0][0])} to ${seasonLabel(t.rows[t.rows.length - 1][0])}`,
  endText(t, g, won) {
    const n = this.score(t, g), total = this.cells(t).length;
    return { result: `${n} of ${total} squares`,
             cheer: won ? "The whole grid! 🏆" : n >= total * .7 ? "Deep run! 🔥" : n >= total * .35 ? "Solid effort 💪" : "Time's up! ⏱️" };
  },
  celebrate(t, g, won) { return won || this.score(t, g) >= this.cells(t).length * 0.7; },
  archiveStatus: h => `${h.s} squares`,
  shareText(t, saved, num, link) {
    const marks = this.filled(t, saved.guesses), n = cupsCols(t).length;
    const rows = t.rows.map((r, i) => marks.slice(i * n, i * n + n).map(x => x ? "🟩" : "⬜").join("")).join("\n");
    return `Sweater Playoff History #${num} · ${this.meta(t)}\n${this.score(t, saved.guesses)}/${marks.length} squares\n\n${rows}${link}`;
  },
  clockKey(t) { return `${mode}:${S.cups.day || ""}:${this.tid(t)}`; },
  reset(t) {
    clearInterval(cupsTimer);
    const st = S.cups;
    st.endsAt = null;
    this._cells = null;
    const saved = mode === "unlimited" ? cupsMemory : store.get("sweater-cups-clock");
    if (saved && saved.key === this.clockKey(t)) st.endsAt = saved.endsAt;
    $("cuInput").value = "";
    $("cuMsg").textContent = "";
  },
  guess(t, x) { return x === "END" || typeof x === "string" ? false : null; },
  render(t, st) {
    const marks = this.filled(t, st.guesses), total = marks.length;
    const running = !!st.endsAt && !st.over;
    $("cuCount").textContent = `${marks.filter(Boolean).length}/${total}`;
    $("cuTime").textContent = cupsClock(st.over ? 0 : running ? Math.max(0, Math.ceil((st.endsAt - Date.now()) / 1000)) : CUPS_SECONDS);
    $("cuStart").hidden = running || !!st.over;
    $("cuInput").disabled = !running;
    $("cuInput").placeholder = running ? "Type a team or player, then press Enter" : st.over ? "Time's up" : "Press Start to begin";
    const cols = cupsCols(t);
    const decades = {};
    t.rows.forEach((r, i) => {
      const key = `${Math.floor(r[0] / 10) * 10}s`;
      const d = decades[key] || (decades[key] = { got: 0, total: 0 });
      const rowMarks = marks.slice(i * cols.length, i * cols.length + cols.length);
      d.got += rowMarks.filter(Boolean).length; d.total += cols.length;
    });
    $("cuDecades").innerHTML = Object.entries(decades).map(([decade, d]) => `<div class="cudecade"><b>${decade}</b><small>${d.got}/${d.total}</small><i><span style="width:${d.got / d.total * 100}%"></span></i></div>`).join("");
    $("cuHead").innerHTML = `<th>Season</th><th>Stanley Cup</th><th>Runner-up</th>` + (cols.length === 3 ? "<th>Conn Smythe</th>" : "");
    $("cuRows").innerHTML = t.rows.map((r, i) => `<tr>
      <td class="cuyear">${seasonLabel(r[0])}</td>
      ${cols.map((c, ci) => {
        const got = marks[i * cols.length + ci];
        const team = c === 3 ? r[4] : r[c];
        const label = c === 1 ? "Cup winner" : c === 2 ? "Runner-up" : "Conn Smythe";
        return `<td data-label="${label}" class="cucell${got ? " got" : st.over ? " miss" : ""}">${got || st.over ? cupsAnswer(r[c], team) : ""}</td>`;
      }).join("")}</tr>`).join("");
    requestAnimationFrame(syncCupsStickyHeader);
    if (running) {
      if (st.endsAt <= Date.now()) setTimeout(() => { if (game === "cups" && !S.cups.over) doGuess("END"); }, 0);
      else cupsTick();
    }
  },
};
function cupsTick() {
  clearInterval(cupsTimer);
  cupsTimer = setInterval(() => {
    const st = S.cups;
    if (!st.endsAt || st.over) { clearInterval(cupsTimer); return; }
    const left = Math.max(0, Math.ceil((st.endsAt - Date.now()) / 1000));
    if (game === "cups") {
      $("cuTime").textContent = cupsClock(left);
      $("cuTime").parentElement.classList.toggle("urgent", left <= 30);
    }
    if (left <= 0) { clearInterval(cupsTimer); if (game === "cups") doGuess("END"); }
  }, 250);
}
function cupsStart() {
  const st = S.cups;
  if (game !== "cups" || !st.target || st.over || st.endsAt) return;
  st.endsAt = Date.now() + CUPS_SECONDS * 1000;
  const rec = { key: G.cups.clockKey(st.target), endsAt: st.endsAt };
  if (mode === "unlimited") cupsMemory = rec; else store.set("sweater-cups-clock", rec);
  G.cups.render(st.target, st);
  $("cuInput").focus({ preventScroll: true });
}
function cupsEnter() {
  const st = S.cups, t = st.target;
  if (!t || st.over || !st.endsAt) return;
  const text = $("cuInput").value.trim();
  const key = cupsNorm(text);
  if (!key) return;
  const before = G.cups.filled(t, st.guesses);
  const hits = G.cups.cells(t).filter((c, i) => !before[i] && cupsMatch(c.full, c.player, key)).length;
  if (!hits) {
    const known = G.cups.cells(t).some(c => cupsMatch(c.full, c.player, key));
    $("cuMsg").textContent = known ? "Already got that one"
      : `No square for "${text}"` + (key.split(" ").length === 1 ? " — players need a surname" : "");
    $("cuMsg").classList.add("bad");
    $("cuInput").classList.remove("shake"); void $("cuInput").offsetWidth; $("cuInput").classList.add("shake");
    return;
  }
  $("cuInput").value = "";
  $("cuMsg").classList.remove("bad");
  $("cuMsg").textContent = `✓ ${text}${hits > 1 ? ` ×${hits}` : ""}`;
  doGuess(text);
  if (!S.cups.over) $("cuInput").focus({ preventScroll: true });
}
$("cuStart").onclick = cupsStart;
$("cuInput").addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); cupsEnter(); } });

// ======================= game engine =======================
const GAME_IDS = Object.keys(G);
const KEYS = Object.fromEntries(Object.keys(G).map(g => [g, g === "classic"
  ? { daily: "sweater-daily", stats: "sweater-stats" }
  : { daily: `sweater-daily-${g}`, stats: `sweater-stats-${g}` }]));
const isScored = g => G[g].kind === "streak" || G[g].kind === "score";
const isStatsGame = g => g === "statline" || g === "team";
const gameTitle = g => G[g].title;
const isDone = (g, t, guesses) => G[g].isDone ? G[g].isDone(t, guesses)
  : guesses.some(x => G[g].isWin(t, x)) || guesses.length >= G[g].max;
let game = GAME_IDS.includes(store.get("sweater-game")) ? store.get("sweater-game") : "classic";
let mode = store.get("sweater-mode") === "unlimited" ? "unlimited" : "daily";
const S = Object.fromEntries(GAME_IDS.map(g => [g, { target: null, guesses: [], over: false, day: null, mode: null }]));

function hideBanner() { $("banner").style.display = "none"; }

// ---- per-game options (hard mode, reveal order); locked while a game is in progress ----
const OPTION_DEFAULTS = { classic: { hard: false }, statline: { order: "oldest" } };
const prefOpts = g => Object.assign({}, OPTION_DEFAULTS[g] || {}, store.get(`sweater-opts-${g}`) || {});
const optsLocked = st => st.guesses.length > 0 && !st.over;

// ---- archive progress and past results ----
const archiveGet = (g, d) => (store.get("sweater-archive") || {})[`${g}:${d}`];
function archiveSet(g, d, rec) {
  const all = store.get("sweater-archive") || {};
  all[`${g}:${d}`] = rec;
  store.set("sweater-archive", all);
}
const historyGet = (g, d) => (store.get("sweater-history") || {})[`${g}:${d}`];
function historySet(g, d, summary) {
  const all = store.get("sweater-history") || {};
  all[`${g}:${d}`] = summary;
  store.set("sweater-history", all);
}
let archiveDay = null;

// ---- player progression (derived from real completed daily puzzles) ----
const HISTORY_KEY = "sweater-history";
const ACHIEVEMENT_KEY = "sweater-achievements";
const shiftDay = (key, days) => {
  const d = new Date(`${key}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
};
const historyEntries = () => Object.entries(store.get(HISTORY_KEY) || {}).map(([key, result]) => {
  const at = key.lastIndexOf(":");
  return { game: key.slice(0, at), day: key.slice(at + 1), ...result };
}).filter(x => x.game && /^\d{4}-\d{2}-\d{2}$/.test(x.day));
const dailyEntries = day => historyEntries().filter(x => x.day === day);
const xpFor = x => x.s != null ? 45 + Math.min(80, Math.round(Number(x.s) || 0) * 3) : (x.w ? 100 : 35);
function progressSummary() {
  const entries = historyEntries();
  const xp = entries.reduce((total, x) => total + xpFor(x), 0);
  const wins = entries.filter(x => x.w).length;
  const days = [...new Set(entries.map(x => x.day))];
  const historic = entries.filter(x => ["trophy", "cups", "playoff"].includes(x.game)).length;
  return { entries, xp, wins, days, historic, level: Math.floor(xp / 500) + 1, intoLevel: xp % 500 };
}
const WEEKLY_THEMES = [
  { icon: "⌛", title: "History Night", copy: "Complete three hockey-history dailies this week.", games: ["trophy", "cups", "playoff"] },
  { icon: "✦", title: "All-Rounder", copy: "Play one player, one detail, and one speed challenge.", games: ["classic", "trophy", "shoot"] },
  { icon: "⚡", title: "Fast Hands", copy: "Take on three quick-thinking dailies this week.", games: ["hl", "rank", "puck"] },
  { icon: "🗺", title: "Hockey IQ", copy: "Go from birthplace to draft day to a mystery season.", games: ["map", "draft", "season"] },
];
function activeWeeklyTheme() {
  const start = new Date("2024-01-01T12:00:00Z");
  const now = new Date(`${dayKey()}T12:00:00Z`);
  return WEEKLY_THEMES[Math.floor((now - start) / 604800000) % WEEKLY_THEMES.length];
}
function weeklyProgress(theme = activeWeeklyTheme()) {
  const day = dayKey();
  const weekday = (new Date(`${day}T12:00:00Z`).getUTCDay() + 6) % 7;
  const days = Array.from({ length: weekday + 1 }, (_, i) => shiftDay(day, -i));
  const entries = historyEntries();
  return theme.games.filter(g => entries.some(x => (g === "hl" ? x.game.startsWith("hl_") : x.game === g) && days.includes(x.day))).length;
}
function achievementList() {
  const p = progressSummary();
  const dailyHatTrick = p.days.some(d => dailyEntries(d).length >= 3);
  const weeklyDone = weeklyProgress() >= 3;
  return [
    { id: "first-shift", icon: "🏒", title: "First Shift", copy: "Finish one daily puzzle.", on: p.entries.length >= 1 },
    { id: "hat-trick", icon: "🎩", title: "Hat Trick", copy: "Finish three dailies in one day.", on: dailyHatTrick },
    { id: "regular", icon: "★", title: "Regular", copy: "Finish 10 daily puzzles.", on: p.entries.length >= 10 },
    { id: "historian", icon: "⌛", title: "Historian", copy: "Finish 5 history puzzles.", on: p.historic >= 5 },
    { id: "on-a-roll", icon: "🔥", title: "On a Roll", copy: "Win 10 daily puzzles.", on: p.wins >= 10 },
    { id: "weekender", icon: "✓", title: "Weekly Win", copy: "Complete this week's challenge.", on: weeklyDone },
  ];
}
function awardProgression() {
  const seen = store.get(ACHIEVEMENT_KEY) || {};
  const unlocked = achievementList().filter(a => a.on && !seen[a.id]);
  if (unlocked.length) {
    unlocked.forEach(a => { seen[a.id] = dayKey(); });
    store.set(ACHIEVEMENT_KEY, seen);
  }
  return unlocked;
}
function renderPlayerProfile() {
  const p = progressSummary(), levelCap = 500;
  const todayDone = dailyEntries(dayKey()).length;
  $("profileHero").innerHTML = `<div class="lockerhero"><div class="levelmark">${p.level}</div><div class="levelcopy"><b>Level ${p.level} · Rink Rat</b><small>${p.xp} XP earned · ${levelCap - p.intoLevel} XP to the next level</small><div class="xpbar"><i style="width:${p.intoLevel / levelCap * 100}%"></i></div></div></div><div class="lockerstats"><div><b>${p.entries.length}</b><span>Daily plays</span></div><div><b>${p.wins}</b><span>Wins</span></div><div><b>${todayDone}/3</b><span>Today's hat trick</span></div></div>`;
  $("achievementGrid").innerHTML = achievementList().map(a => `<div class="achievement${a.on ? "" : " locked"}"><i>${a.icon}</i><span><b>${a.title}</b><small>${a.copy}</small></span></div>`).join("");
  const theme = activeWeeklyTheme(), progress = weeklyProgress(theme);
  $("lockerHint").textContent = `${theme.title}: ${progress}/3 complete. ${progress >= 3 ? "Challenge cleared—nice work." : theme.copy}`;
  const gameRows = (ids, empty) => ids.length ? ids.slice(0, 3).map(id => {
    const card = CARD[id] || { icon: "🏒" }, meta = modeMeta(id);
    return `<button type="button" class="lockerrow" data-locker-open="${id}"><i aria-hidden="true">${modeIcon(id)}</i><span><b>${esc(cardTitle(id))}</b><small>${esc(meta.type)}</small></span><em aria-hidden="true">›</em></button>`;
  }).join("") : `<p class="lockerhint">${esc(empty)}</p>`;
  $("lockerBench").innerHTML = `<section class="lockerbenchsection"><b>Favourites</b><div class="lockerlist">${gameRows(favouriteIds(), "Star modes in the game library to keep them here.")}</div></section>
    <section class="lockerbenchsection"><b>Recently played</b><div class="lockerlist">${gameRows(recentIds(), "Your last few modes will show up here.")}</div></section>`;
}
function renderResultRecap(unlocked = []) {
  const box = $("resultRecap");
  if (mode !== "daily") { box.hidden = true; return; }
  const p = progressSummary(), done = dailyEntries(dayKey()).length;
  const entry = historyEntries().find(x => x.game === game && x.day === S[game].day);
  const achievement = unlocked[0] ? ` · Unlocked ${unlocked[0].title}` : "";
  const info = modeMeta(game.startsWith("hl_") ? "hl" : game);
  const next = info.next && G[info.next] ? info.next : "classic";
  box.hidden = false;
  box.innerHTML = `<div class="recapstats"><i>✦</i><span><b>+${entry ? xpFor(entry) : 0} XP${achievement}</b><small>Level ${p.level} · Daily Hat Trick ${Math.min(done, 3)}/3</small><span class="recapfact"><small>${esc(info.fact)}</small></span></span></div><div class="recapactions"><button type="button" data-result-share>Share</button><button type="button" class="ghost" data-result-next="${next}">Next</button></div>`;
}

function startGame(t, restore = [], opts) {
  const st = S[game], g = G[game];
  Object.assign(st, { target: t, guesses: [], over: false, mode, opts: opts || prefOpts(game) });
  hideBanner();
  $("resultRecap").hidden = true;
  g.reset(t);
  restore.forEach(x => doGuess(x, false));
  g.render && g.render(t, st);
  renderOptions();
  updateLabels();
}

function saveProgress() {
  const st = S[game], g = G[game];
  const rec = { date: st.day, target: g.tid(st.target), guesses: st.guesses, opts: st.opts };
  if (mode === "daily") store.set(KEYS[game].daily, rec);
  if (mode === "archive") archiveSet(game, st.day, rec);
}

function doGuess(x, fresh = true) {
  const st = S[game], g = G[game];
  if (!st.target || st.over || g.pending || (!g.repeat && st.guesses.includes(x))) return;
  const won = g.guess(st.target, x, fresh);
  if (won === null) return;
  st.guesses.push(x);
  if (fresh) saveProgress();
  if (isDone(game, st.target, st.guesses)) finish(g.wonGame ? g.wonGame(st.target, st.guesses) : won, fresh);
  if (fresh) { g.render && g.render(st.target, st); renderOptions(); updateLabels(); }
}

function finish(won, fresh) {
  const st = S[game], g = G[game], p = g.player(st.target), n = st.guesses.length;
  st.over = true;
  $(g.view).querySelector(".slot").appendChild($("banner"));
  $("reveal").src = (p && p.headshot) || FALLBACK;
  $("reveal").alt = p ? p.name : "";
  $("reveal").hidden = $("pname").hidden = $("profile").hidden = !!g.hideReveal;
  const text = g.endText && g.endText(st.target, st.guesses, won);
  $("result").textContent = text ? text.result : won ? `You got it in ${n}!` : "Out of guesses";
  $("cheer").textContent = text ? text.cheer : won ? g.cheers[n - 1] : (game === "team" ? "The answer was" : "The mystery player was");
  $("pname").textContent = p ? p.name : "";
  $("pmeta").textContent = g.meta(st.target);
  if (p) $("profile").href = `https://www.nhl.com/player/${p.id}`;
  $("again").textContent = mode === "archive" ? "Pick another day" : g.next;
  $("again").hidden = mode === "daily";
  $("countdown").hidden = mode !== "daily";
  $("banner").classList.toggle("won", won);
  $("banner").classList.remove("pop");
  tick();
  $("banner").style.display = "block";
  if (mode !== "unlimited" && (fresh || !historyGet(game, st.day))) {
    historySet(game, st.day, isScored(game) ? { s: g.score(st.target, st.guesses), w: won } : { n, w: won });
  }
  let unlocked = [];
  if (mode === "daily" && fresh) {
    recordResult(won);
    unlocked = awardProgression();
  }
  renderResultRecap(unlocked);
  if (fresh) {
    const party = g.celebrate ? g.celebrate(st.target, st.guesses, won) : won;
    void $("banner").offsetWidth; // restart the pop animation
    $("banner").classList.add("pop");
    if (party) confetti();
    if (g.onFinish) g.onFinish(st);
    if (mode === "daily") {
      submitPending();
      if (unlocked.length) setTimeout(() => toast(`Achievement unlocked: ${unlocked[0].title}`), party ? 900 : 350);
      const finishedGame=game, finishedTarget=st.target;
      if (!g.quietFinish) setTimeout(() => { if(game!==finishedGame || onHub || S[game].target!==finishedTarget)return; statsGame = null; openModal("statsModal"); }, party ? 2400 : 1600);
    }
  }
}

function restoreFrom(saved, t) {
  const g = G[game];
  const ok = saved && saved.target === g.tid(t);
  return [ok ? saved.guesses : [], ok && saved.opts ? { ...prefOpts(game), ...saved.opts } : undefined];
}

function loadDaily() {
  const st = S[game], g = G[game];
  if (!g.pool().length) return noData();
  st.day = dayKey();
  const t = g.daily(st.day);
  const saved = store.get(KEYS[game].daily);
  startGame(t, ...restoreFrom(saved && saved.date === st.day ? saved : null, t));
}

function archiveDays(g) {
  const today = dayKey();
  if (g.startsWith("hl_")) {
    return Object.keys(DAILY_HL).filter(k => k < today && (DAILY_HL[k][G[g].stat] || []).length > 1).sort().reverse();
  }
  return Object.keys(DAILY[g]).filter(k => k < today).sort().reverse();
}

function loadArchive(day) {
  const st = S[game], g = G[game];
  if (!g.pool().length) return noData();
  if (!archiveDays(game).includes(day)) {
    toast("That day isn't in this game's archive");
    mode = "daily";
    return loadDaily();
  }
  archiveDay = st.day = day;
  const t = g.daily(day);
  startGame(t, ...restoreFrom(archiveGet(game, day), t));
}

function loadUnlimited(forceNew = false) {
  const st = S[game], g = G[game];
  if (!g.pool().length) return noData();
  if (!forceNew && st.target && st.mode === "unlimited") return startGame(st.target, st.guesses.slice(), st.opts);
  let t, tries = 0;
  do { t = g.random(); } while (st.target && g.tid(t) === g.tid(st.target) && ++tries < 10);
  startGame(t);
}

function loadCurrent() {
  if (mode === "archive") return loadArchive(archiveDay);
  if (mode === "unlimited") return loadUnlimited();
  return loadDaily();
}

function noData() {
  const st = S[game];
  Object.assign(st, { target: null, guesses: [], over: true, mode });
  hideBanner();
  $(G[game].view).querySelector(".nodata").hidden = false;
  renderOptions();
  updateLabels();
}

const niceDay = k => { const [y, m, d] = k.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric", year: "numeric", timeZone: "UTC" }); };

function updateLabels() {
  const st = S[game], g = G[game];
  const text = !st.target ? "Not available yet"
    : st.over ? (mode === "daily" ? "Done for today. Turn on Unlimited (top right) to keep playing"
               : mode === "archive" ? "Done. Pick another day from the archive" : `Game over. Click ${g.next}`)
    : `Guess ${st.guesses.length + 1} of ${g.max}`;
  for (const id of ["guess", "slGuess", "jyGuess", "blGuess", "zmGuess", "phGuess"]) { $(id).placeholder = text; $(id).disabled = !st.target || st.over; }
  const today = new Date().toLocaleDateString(undefined, { month: "short", day: "numeric" });
  $("modeLabel").textContent = mode === "daily" ? `Daily #${dailyNumber(game, dayKey())} · ${today}`
    : mode === "archive" ? `Archive · #${dailyNumber(game, archiveDay)}` : "Unlimited play";
  $("unlimited").checked = mode === "unlimited";
  $("archBar").hidden = mode !== "archive" || onHub;
  if (mode === "archive") $("archText").textContent = `Archive · #${dailyNumber(game, archiveDay)} · ${niceDay(archiveDay)}`;
}

function renderOptions() {
  const st = S[game], locked = optsLocked(st), opts = st.opts || prefOpts(game);
  $("classicOpts").hidden = game !== "classic";
  $("silBtn").hidden = game !== "classic" || !!opts.hard;
  if (game === "classic") {
    $("hardMode").checked = !!opts.hard;
    $("hardMode").disabled = locked;
    $("hardNote").textContent = locked ? "Locked until this game ends" : opts.hard ? "No silhouette" : "";
  }
  if (game === "statline") {
    document.querySelectorAll("[data-order]").forEach(b => {
      b.setAttribute("aria-selected", b.dataset.order === opts.order);
      b.disabled = locked;
    });
    $("slOrderNote").textContent = locked ? "Reveal order is locked until this game ends" : "";
  }
}

function changeOption(key, value) {
  const st = S[game];
  if (optsLocked(st)) return renderOptions();
  store.set(`sweater-opts-${game}`, { ...prefOpts(game), [key]: value });
  st.opts = { ...(st.opts || prefOpts(game)), [key]: value };
  if (st.target && !st.over && st.guesses.length === 0 && mode !== "unlimited") saveProgress();
  if (st.target) G[game].render && G[game].render(st.target, st);
  renderOptions();
}
$("hardMode").addEventListener("change", e => changeOption("hard", e.target.checked));
document.querySelectorAll("[data-order]").forEach(b => b.addEventListener("click", () => changeOption("order", b.dataset.order)));

function setGame(g) {
  if (g !== game) leaveGame(game);
  game = g;
  store.set("sweater-game", g);
  new Set(GAME_IDS.map(id => G[id].view)).forEach(v => { $(v).hidden = v !== G[g].view; });
  document.querySelectorAll(".nodata").forEach(n => n.hidden = true);
  searches.forEach(s => s.close());
  const card = CARD[g.startsWith("hl_") ? "hl" : g] || { icon: "🏒", tone: "green" };
  $("gIcon").innerHTML = modeIcon(g);
  $("gameBar").dataset.game = g;
  $("gameBar").dataset.tone = card.tone;
  $("gTitle").textContent = g.startsWith("hl_") ? `Higher or Lower · ${HL_STATS[G[g].stat].name}` : G[g].title;
  document.title = `${$("gTitle").textContent} · Sweater`;
  if (g.startsWith("hl_")) $("hlStatSel").value = g;
  loadCurrent();
  if (g === "map" && S.map.target) requestAnimationFrame(() => setView(mapView.x, mapView.y, mapView.w, mapView.h));
}

// ---- archive picker ----
let archiveGame = null;
function openArchive() {
  renderArchive(game);
  openModal("archiveModal");
}
function renderArchive(game) {
  archiveGame = game;
  $("arGameSel").innerHTML = gameOptions(game);
  const g = G[game], days = archiveDays(game);
  const status = d => {
    const h = historyGet(game, d);
    if (!h) return archiveGet(game, d)?.guesses?.length ? "In progress" : "Play";
    if (g.archiveStatus) return g.archiveStatus(h);
    if (g.kind === "streak") return `🔥 ${h.s}`;
    return h.w ? `✓ ${h.n}/${g.max}` : "✗";
  };
  $("arList").innerHTML = days.length ? days.map(d => `
    <li><button type="button" class="arbtn${archiveDay === d && mode === "archive" && archiveGame === currentGame() ? " on" : ""}" data-day="${d}">
      <span class="arno">#${dailyNumber(game, d)}</span><span class="ardate">${niceDay(d)}</span>
      <span class="arstat">${status(d)}</span></button></li>`).join("")
    : '<li class="empty">No past puzzles yet for this game. Check back tomorrow.</li>';
}
$("arList").addEventListener("click", e => {
  const b = e.target.closest("[data-day]");
  if (!b) return;
  closeModals();
  mode = "archive";
  archiveDay = b.dataset.day;
  openGame(archiveGame);
});
$("archiveBtn").onclick = openArchive;
$("pickDay").onclick = openArchive;
$("backToday").onclick = () => { mode = "daily"; store.set("sweater-mode", "daily"); loadDaily(); };
$("unlimited").addEventListener("change", () => { if (onHub) renderHub(); });

// ======================= classic board =======================
function cell(text, hit, cls = "") {
  const td = document.createElement("td");
  td.className = cls + (hit === true ? " hit" : hit === "near" ? " near" : "");
  td.textContent = text;
  return td;
}
function numCell(g, t) {
  if (g === t) return cell(g, true);
  const td = cell("", numState(g, t));
  td.innerHTML = `<div class="num"><span>${g}</span><span class="arrow" aria-label="${t > g ? "higher" : "lower"}">${t > g ? "↑" : "↓"}</span></div>`;
  return td;
}
function addClassicRow(p, t) {
  const tr = document.createElement("tr");
  const [pc, pd] = TEAMS[p.team] || ["?", "?"];
  const [tc, td] = TEAMS[t.team] || ["?", "?"];
  tr.appendChild(cell(p.name, false, "name"));
  const teamState = p.team === t.team ? true : (t.past || []).includes(p.team) ? "near" : false;
  const team = cell("", teamState, "team");
  team.innerHTML = `<img alt="" src="${logo(p.team)}" onerror="this.remove()">${esc(p.team)}`;
  tr.appendChild(team);
  tr.appendChild(cell(pc, pc === tc));
  tr.appendChild(cell(pd, pd === td));
  tr.appendChild(cell(p.pos, p.pos === t.pos));
  tr.appendChild(cell(p.shoots, p.shoots === t.shoots));
  tr.appendChild(numCell(ageOf(p.birth), ageOf(t.birth)));
  tr.appendChild(cell(p.nation, p.nation === t.nation));
  tr.appendChild(numCell(p.number, t.number));
  ["", "Team", "Conf", "Div", "Pos", "Shoots", "Age", "Nation", "#"]
    .forEach((label, i) => tr.children[i].dataset.label = label);
  $("rows").prepend(tr);   // newest guess on top
  tr.classList.add("newrow");
}

// ======================= player search (autocomplete) =======================
function makeSearch(inputId, listId, toGuess = id => id) {
  const input = $(inputId), ul = $(listId);
  let idx = -1, found = [];
  function close() { ul.hidden = true; idx = -1; input.setAttribute("aria-expanded", false); }
  function choose(p) { if (!p) return; close(); input.value = ""; doGuess(toGuess(p.id)); }
  function render() {
    const q = norm(input.value.trim());
    if (!q) return close();
    const used = S[game].guesses.map(x => typeof x === "string" && x.includes("@") ? Number(x.split("@")[0]) : x);
    found = PLAYERS.filter(p => !used.includes(p.id) && norm(p.name).includes(q)).slice(0, 30);
    ul.innerHTML = "";
    found.forEach((p, i) => {
      const li = document.createElement("li");
      li.role = "option"; li.id = `${listId}-${i}`;
      li.setAttribute("aria-selected", i === idx);
      li.innerHTML = `<span></span><small>${esc(p.team)} · ${esc(p.pos)}</small>`;
      li.firstChild.textContent = p.name;
      li.onmousedown = e => { e.preventDefault(); choose(p); };
      ul.appendChild(li);
    });
    ul.hidden = found.length === 0;
    input.setAttribute("aria-expanded", !ul.hidden);
  }
  input.addEventListener("input", () => { idx = 0; render(); });
  input.addEventListener("keydown", e => {
    if (ul.hidden) return;
    if (e.key === "ArrowDown") { idx = Math.min(idx + 1, found.length - 1); render(); e.preventDefault(); }
    else if (e.key === "ArrowUp") { idx = Math.max(idx - 1, 0); render(); e.preventDefault(); }
    else if (e.key === "Enter") { choose(found[idx]); e.preventDefault(); }
    else if (e.key === "Escape") close();
    const a = $(`${listId}-${idx}`); if (a) a.scrollIntoView({ block: "nearest" });
  });
  input.addEventListener("blur", close);
  return { close };
}
const searches = [makeSearch("guess", "opts"), makeSearch("slGuess", "slOpts"),
                  makeSearch("jyGuess", "jyOpts"), makeSearch("blGuess", "blOpts"),
                  makeSearch("zmGuess", "zmOpts", id => `${id}@${zamPct()}`), makeSearch("phGuess", "phOpts")];
// kept for easy testing from the console
function submit(p) { if (p) doGuess(p.id); }

$("ttGrid").addEventListener("click", e => {
  const b = e.target.closest(".teambtn");
  if (b && !b.disabled) doGuess(b.dataset.team);
});

// ======================= confetti =======================
function confetti() {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const cv = document.createElement("canvas");
  cv.id = "confetti"; document.body.appendChild(cv);
  const ctx = cv.getContext("2d"), dpr = window.devicePixelRatio || 1;
  const W = cv.width = innerWidth * dpr, H = cv.height = innerHeight * dpr;
  const colors = ["#528f4f", "#e3b83b", "#c8102e", "#1f4e9c", "#f3e9d2", "#ffffff"];
  const bits = Array.from({ length: 90 }, (_, i) => {
    const left = i % 2 === 0;
    return {
      x: left ? 0 : W, y: H * .7,
      vx: (left ? 1 : -1) * (6 + Math.random() * 10) * dpr,
      vy: -(12 + Math.random() * 12) * dpr,
      w: (6 + Math.random() * 6) * dpr, h: (4 + Math.random() * 6) * dpr,
      rot: Math.random() * 6, vr: (Math.random() - .5) * .4,
      c: colors[i % colors.length]
    };
  });
  const start = performance.now();
  (function frame(t) {
    const age = t - start;
    ctx.clearRect(0, 0, W, H);
    ctx.globalAlpha = Math.max(0, 1 - Math.max(0, age - 1800) / 900);
    for (const b of bits) {
      b.vy += .35 * dpr; b.vx *= .985; b.vy *= .985;
      b.x += b.vx; b.y += b.vy; b.rot += b.vr;
      ctx.save(); ctx.translate(b.x, b.y); ctx.rotate(b.rot);
      ctx.fillStyle = b.c; ctx.fillRect(-b.w / 2, -b.h / 2, b.w, b.h * Math.abs(Math.cos(b.rot * 2)));
      ctx.restore();
    }
    if (age < 2700) requestAnimationFrame(frame); else cv.remove();
  })(start);
}

// ======================= stats (daily games only, kept per game) =======================
const blankStats = max => ({ played: 0, wins: 0, streak: 0, maxStreak: 0, dist: Array(max).fill(0), lastDay: null, lastWinDay: null, lastGuesses: 0 });
const currentGame = () => game;
function getStats(g = game) {
  const st = Object.assign(blankStats(G[g].max), store.get(KEYS[g].stats) || {});
  st.dist = Array.from({ length: G[g].max }, (_, i) => st.dist[i] || 0);
  return st;
}

function recordResult(won) {
  const day = S[game].day, st = getStats(), n = S[game].guesses.length;
  if (st.lastDay === day) return;
  if (isScored(game)) {
    const score = G[game].score(S[game].target, S[game].guesses);
    Object.assign(st, { played: st.played + 1, wins: st.wins + (won ? 1 : 0), total: (st.total || 0) + score,
                        best: Math.max(st.best || 0, score), lastDay: day, lastScore: score });
    store.set(KEYS[game].stats, st);
    return;
  }
  st.played++;
  if (won) {
    st.wins++;
    st.streak = st.lastWinDay === prevDayKey(day) ? st.streak + 1 : 1;
    st.maxStreak = Math.max(st.maxStreak, st.streak);
    st.dist[n - 1]++;
    st.lastWinDay = day;
  } else st.streak = 0;
  st.lastDay = day;
  st.lastGuesses = won ? n : 0;
  store.set(KEYS[game].stats, st);
}

function renderStats() {
  const game = statsGame || currentGame();
  $("stGameSel").innerHTML = gameOptions(game);
  const st = getStats(game), today = dayKey();
  const streak = st.lastWinDay === today || st.lastWinDay === prevDayKey(today) ? st.streak : 0;
  $("sTitle").textContent = `Statistics · ${gameTitle(game)}`;
  const streakGame = isScored(game);
  $("distTitle").hidden = $("dist").hidden = streakGame;
  ["Played", streakGame ? (game === "roster" ? "Best" : "Best run") : "Win %", streakGame ? "Average" : "Current streak", streakGame ? "Today" : "Max streak"]
    .forEach((label, i) => { $(`stL${i + 1}`).textContent = label; });
  if (streakGame) {
    $("stPlayed").textContent = st.played;
    $("stWin").textContent = st.best || 0;
    $("stStreak").textContent = st.played ? Math.round((st.total || 0) / st.played * 10) / 10 : 0;
    $("stMax").textContent = st.lastDay === today ? st.lastScore : "–";
    const saved = store.get(KEYS[game].daily);
    $("shareBtn").hidden = !(saved && saved.date === today && st.lastDay === today);
    renderStatsLb(game);
    return;
  }
  $("stPlayed").textContent = st.played;
  $("stWin").textContent = st.played ? Math.round(st.wins / st.played * 100) : 0;
  $("stStreak").textContent = streak;
  $("stMax").textContent = st.maxStreak;
  const most = Math.max(1, ...st.dist);
  $("dist").innerHTML = st.dist.map((n, i) =>
    `<div class="distrow"><span class="k">${i + 1}</span><div class="bar${st.lastDay === today && st.lastGuesses === i + 1 ? " today" : ""}" style="width:0">${n}</div></div>`).join("");
  requestAnimationFrame(() => requestAnimationFrame(() =>
    $("dist").querySelectorAll(".bar").forEach((b, i) => b.style.width = `${Math.max(8, st.dist[i] / most * 100)}%`)));
  const saved = store.get(KEYS[game].daily);
  $("shareBtn").hidden = !(saved && saved.date === today && st.lastDay === today);
  renderStatsLb(game);
}

function shareText() {
  const game = statsGame || currentGame();
  const g = G[game], saved = store.get(KEYS[game].daily);
  const t = g.daily(saved.date);
  if (g.shareText) {
    const link = !SITE || /__SITE__/.test(SITE) ? "" : `\n\n${SITE}#${game}`;
    return g.shareText(t, saved, dailyNumber(game, saved.date), link);
  }
  if (g.kind === "streak") {
    const n = g.score(t, saved.guesses), won = g.wonGame(t, saved.guesses);
    const marks = saved.guesses.map((x, i) => g.squares(t, x, i)).join("");
    const rows = (marks.match(/(?:🟩|🟥){1,10}/gu) || []).join("\n");
    const link = !SITE || /__SITE__/.test(SITE) ? "" : `\n\n${SITE}#${game}`;
    return `${g.share} #${dailyNumber(game, saved.date)} · ${HL_STATS[g.stat].name}\nStreak: ${n}${won ? " (perfect!)" : ""}\n\n${rows}${link}`;
  }
  const won = saved.guesses.some(x => g.isWin(t, x));
  const body = saved.guesses.map(x => g.squares(t, x)).join("").trim();
  const link = !SITE || /__SITE__/.test(SITE) ? "" : `\n\n${SITE}#${game}`;
  const note = saved.opts && saved.opts.hard ? " · Hard mode" : saved.opts && saved.opts.order === "newest" ? " · Newest first" : "";
  return `${g.share} #${dailyNumber(game, saved.date)} ${won ? saved.guesses.length : "X"}/${g.max}${note}\n\n${body}${link}`;
}
function toast(msg) {
  $("toast").textContent = msg; $("toast").classList.add("show");
  clearTimeout(toast.t); toast.t = setTimeout(() => $("toast").classList.remove("show"), 1800);
}
async function copyToClipboard(text, message = "Result copied to clipboard") {
  try { await navigator.clipboard.writeText(text); toast(message); }
  catch {
    const ta = Object.assign(document.createElement("textarea"), { value: text });
    document.body.appendChild(ta); ta.select();
    try { document.execCommand("copy"); toast(message); } catch { toast("Couldn't copy the result"); }
    ta.remove();
  }
}
$("shareBtn").onclick = async () => {
  await copyToClipboard(shareText());
};
$("resultRecap").addEventListener("click", async e => {
  if (e.target.closest("[data-result-share]")) await copyToClipboard(shareText());
  const next = e.target.closest("[data-result-next]");
  if (next) openGame(next.dataset.resultNext);
  if (e.target.closest("[data-result-challenge]")) {
    const base = !SITE || /__SITE__/.test(SITE) ? location.href : `${SITE}#${game}`;
    await copyToClipboard(`Can you beat my ${cardTitle(game)} result on Sweater?\n\n${base}`, "Challenge link copied to clipboard");
  }
});

// ======================= modals =======================
function closeModals() { document.querySelectorAll(".modal.open").forEach(m => m.classList.remove("open")); }
function openModal(id) {
  closeModals();
  if (id === "statsModal") renderStats();
  if (id === "lbModal") renderLeaderboard();
  if (id === "helpModal") renderHelp();
  $(id).classList.add("open");
}
document.querySelectorAll(".modal").forEach(m => m.addEventListener("click", e => {
  if (m.id === "modal" || e.target === m || e.target.closest("[data-close]")) m.classList.remove("open");
}));
$("statsBtn").onclick = () => { statsGame = null; openModal("statsModal"); };
$("profileBtn").onclick = () => { renderPlayerProfile(); openModal("profileModal"); };
$("profileModal").addEventListener("click", e => {
  const b = e.target.closest("[data-locker-open]");
  if (!b) return;
  closeModals();
  openGame(b.dataset.lockerOpen);
});
document.querySelectorAll("[data-welcome-open]").forEach(b => b.onclick = () => {
  $("welcomeModal").classList.remove("open");
  openGame(b.dataset.welcomeOpen);
});
document.querySelectorAll("[data-welcome-library]").forEach(b => b.onclick = () => {
  $("welcomeModal").classList.remove("open");
  store.set("sweater-library-open", true);
  renderHub();
});
$("helpBtn").onclick = () => openModal("helpModal");
$("silBtn").onclick = () => { if (!(S.classic.opts && S.classic.opts.hard)) openModal("modal"); };
$("lbBtn").onclick = () => openLeaderboard();
$("stLbBtn").onclick = () => openLeaderboard(statsGame || game);

// ======================= countdown + midnight rollover =======================
function tick() {
  if (mode === "daily" && S[game].day && S[game].day !== dayKey()) { loadDaily(); return; }
  const s = secondsToEtMidnight();
  const pad = n => String(n).padStart(2, "0");
  const clock = `${pad(Math.floor(s / 3600))}:${pad(Math.floor(s / 60) % 60)}:${pad(s % 60)}`;
  $("countdown").textContent = `New puzzle in ${clock}`;
  $("stNext").textContent = clock;
  $("hubNext").textContent = clock;
  if (onHub && tick.lastDay && tick.lastDay !== dayKey()) renderHub();
  tick.lastDay = dayKey();
}
setInterval(tick, 1000);
document.addEventListener("visibilitychange", () => { if (!document.hidden) tick(); });

// ======================= switches =======================
$("unlimited").addEventListener("change", e => {
  if (game === "goalie" || game === "overtime") leaveGame(game);
  mode = e.target.checked ? "unlimited" : "daily";
  store.set("sweater-mode", mode);
  if (mode === "daily") loadDaily(); else loadUnlimited(true);
});
$("again").onclick = () => mode === "archive" ? openArchive() : loadUnlimited(true);

// ---- appearance controls ----
const isDark = () => {
  const t = document.documentElement.dataset.theme;
  return t ? t === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
};
function paintAppearanceControls() {
  const theme = isDark() ? "dark" : "light";
  document.querySelectorAll("[data-theme-choice]").forEach(b => {
    b.setAttribute("aria-pressed", b.dataset.themeChoice === theme ? "true" : "false");
  });
}

// ---- interface colour ----
const DEFAULT_ACCENT = "#7950f2";
const HEX_COLOUR = /^#[0-9a-f]{6}$/i;
function accentInk(hex) {
  const rgb = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map(c => c <= .04045 ? c / 12.92 : Math.pow((c + .055) / 1.055, 2.4));
  return (.2126 * rgb[0] + .7152 * rgb[1] + .0722 * rgb[2]) > .36 ? "#111111" : "#ffffff";
}
function paintAccentControls() {
  const accent = (store.get("sweater-accent") || DEFAULT_ACCENT).toLowerCase();
  document.querySelectorAll("[data-accent]").forEach(b => {
    const on = b.dataset.accent.toLowerCase() === accent;
    b.setAttribute("aria-pressed", on ? "true" : "false");
  });
  $("accentPicker").value = accent;
}
function applyAccent(value, save = true) {
  if (!HEX_COLOUR.test(value || "")) return;
  const accent = value.toLowerCase(), root = document.documentElement;
  root.style.setProperty("--accent", accent);
  root.style.setProperty("--accent-ink", accentInk(accent));
  if (save) store.set("sweater-accent", accent);
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.content = accent;
  paintAccentControls();
}
$("settingsBtn").onclick = () => { paintAccentControls(); paintAppearanceControls(); openModal("settingsModal"); };
$("accentGrid").addEventListener("click", e => {
  const b = e.target.closest("[data-accent]");
  if (b) applyAccent(b.dataset.accent);
});
$("accentPicker").addEventListener("input", e => applyAccent(e.target.value));
applyAccent(HEX_COLOUR.test(store.get("sweater-accent") || "") ? store.get("sweater-accent") : DEFAULT_ACCENT, false);

$("appearanceChoice").addEventListener("click", e => {
  const b = e.target.closest("[data-theme-choice]");
  if (!b) return;
  document.documentElement.dataset.theme = b.dataset.themeChoice;
  store.set("sweater-theme", b.dataset.themeChoice);
  paintAppearanceControls();
});
paintAppearanceControls();
document.addEventListener("keydown", e => { if (e.key === "Escape") closeModals(); });
document.addEventListener("keydown", e => {
  if (onHub || !game.startsWith("hl_") || document.querySelector(".modal.open") || /INPUT|TEXTAREA/.test(e.target.tagName)) return;
  if (e.key === "ArrowUp") { e.preventDefault(); doGuess("H"); }
  if (e.key === "ArrowDown") { e.preventDefault(); doGuess("L"); }
});
$("hlPair").addEventListener("click", e => {
  const b = e.target.closest("[data-hl]");
  if (b) doGuess(b.dataset.hl);
});

// ======================= global leaderboard =======================
const LB_RULES = {
  journey: "Journey: 10 points for 1 guess, then 8, 6, 4, 2 and 1 for 6 guesses.",
  blur: "Blur: 10 points for 1 guess, then 8, 6, 4, 2 and 1 for 6 guesses.",
  number: "Sweater #: 10 points on the first try, then 7, 5, 3 and 1 on the fifth.",
  roster: "Roster Recall: 1 point for every player you name in 60 seconds.",
  draft: "Draft Day: 10 points on the first try, then 7, 5, 3 and 1 on the fifth.",
  map: "Birthplace: 10 points within 100 km, 8 within 250, 6 within 500, 4 within 1,000, 2 within 2,500, minus 2 for each extra pin.",
  conn: "Connections: 10 points with no mistakes, then 8, 6 and 4. Running out of mistakes scores 0.",
  rank: "Rank 'Em: 10 points on the first try, 6 on the second, 3 on the third.",
  puck: "Puck Drop: 1 point for each right tap, minus 1 for each wrong tap.",
  shoot: "Shootout: 2 points for every goal, up to 10.",
  goalie: "Goalie Mode: 10 points per save, with a multiplier increasing every 5 consecutive saves up to 5×. Three goals end the run.",
  overtime: "Overtime: 1 point per right answer. Start with 30 seconds; right answers add 3 seconds and wrong answers cost 5.",
  playoff: "Playoff Hero: 10 points for 1 guess, then 8, 6, 4, 2 and 1.",
  cups: "Playoff History: 1 point for every square you fill in 10 minutes.",
  trophy: "Trophy Case: 2 points for every round you get right, so 20 questions are worth up to 40.",
  mroster: "Mystery Roster: 10 points on the first try, then 6, 3 and 1.",
  truths: "Two Truths: 2 points for every round you get right, up to 10.",
  hlt: "Team Higher or Lower: 1 point for every right answer in a row, up to 40.",
  season: "Mystery Season: 10 points on the first try, 6 on the second, 3 on the third.",
  zam: "Zamboni Reveal: up to 10 points, minus 1 for every 10% of the ice cleared and 2 for each extra guess.",
  ...Object.fromEntries(Object.entries(HL_STATS).map(([s, i]) =>
    [`hl_${s}`, `Higher or Lower (${i.name}): 1 point for every right answer in a row, up to ${HL_LEN}.`])),
  classic: "Classic: 10 points for 1 guess, 9 for 2, down to 3 for 8. A loss scores 0.",
  statline: "Stat Line: 8 points for 1 guess down to 1 for 8, plus 2 for every season still locked when you get it (up to +10).",
  team: "Guess the team: 10 points on the first try, 6 on the second, 3 on the third, 2 on the fourth, 1 on the fifth.",
};
let lbGame = "classic", lbPeriod = "today", lbEditing = false, lbRequest = 0;

async function api(path, body) {
  const res = await fetch(API + path, body === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body)
  });
  let data = {};
  try { data = await res.json(); } catch {}
  if (!res.ok) throw Object.assign(new Error(data.error || "Something went wrong"), { status: res.status });
  return data;
}

function lbIdentity(create) {
  let me = store.get("sweater-lb-id");
  if (!me && create) {
    const hex = n => [...crypto.getRandomValues(new Uint8Array(n))].map(b => b.toString(16).padStart(2, "0")).join("");
    const h = hex(16);
    me = { uid: `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`, secret: hex(32) };
    store.set("sweater-lb-id", me);
  }
  return me;
}

// send any finished daily results (today or yesterday) that haven't been sent yet
let submitting = null;
function submitPending() {
  if (!API_ON) return Promise.resolve();
  submitting = (submitting || Promise.resolve()).then(async () => {
    const me = lbIdentity(false);
    if (!me || !store.get("sweater-lb-name")) return;
    const sent = store.get("sweater-lb-sent") || {};
    const today = dayKey(), yday = prevDayKey(today);
    for (const g of GAME_IDS) {
      if (G[g].localOnly) continue; // New arcade scoring is local until the server supports it.
      const saved = store.get(KEYS[g].daily);
      if (!saved || (saved.date !== today && saved.date !== yday)) continue;
      const key = `${g}:${saved.date}`;
      if (key in sent || !G[g].pool().length) continue;
      const t = G[g].daily(saved.date);
      const done = isDone(g, t, saved.guesses);
      if (!done) continue;
      try {
        const r = await api("/api/result", { ...me, game: g, day: saved.date, guesses: saved.guesses });
        sent[key] = r.points;
      } catch (e) {
        if (e.status === 400) sent[key] = null;  // can't be scored; don't keep retrying
      }
      store.set("sweater-lb-sent", sent);
    }
  }).then(() => {
    if ($("statsModal").classList.contains("open")) renderStatsLb();
    if ($("lbModal").classList.contains("open")) renderLeaderboard();
  });
  return submitting;
}

function renderStatsLb(game = currentGame()) {
  $("stLb").hidden = !API_ON;
  if (!API_ON) return;
  const pts = (store.get("sweater-lb-sent") || {})[`${game}:${dayKey()}`];
  $("stLbText").textContent = !store.get("sweater-lb-name") ? "Add your name to compete with other players."
    : typeof pts === "number" ? `You scored ${pts} ${pts === 1 ? "point" : "points"} today.` : "";
  $("stLbBtn").textContent = store.get("sweater-lb-name") ? "See the leaderboard" : "Join the leaderboard";
}

function openLeaderboard(g = game) {
  lbGame = g;
  lbEditing = !store.get("sweater-lb-name");
  openModal("lbModal");
}

function renderLbName() {
  const box = $("lbNameBox"), name = store.get("sweater-lb-name");
  if (lbEditing || !name) {
    box.innerHTML = `<input id="lbName" maxlength="16" autocomplete="nickname" placeholder="Pick a leaderboard name">
      <button class="btn" id="lbSave" type="button">${name ? "Save" : "Join"}</button>
      ${name ? '<button class="linkbtn" id="lbCancel" type="button">Cancel</button>' : ""}
      <p class="lberr" id="lbErr"></p>`;
    $("lbName").value = name || "";
    $("lbSave").onclick = saveLbName;
    $("lbName").onkeydown = e => { if (e.key === "Enter") saveLbName(); };
    if (name) $("lbCancel").onclick = () => { lbEditing = false; renderLbName(); };
  } else {
    box.innerHTML = `<span>Playing as <b></b></span><button class="linkbtn" id="lbChange" type="button">Change name</button>`;
    box.querySelector("b").textContent = name;
    $("lbChange").onclick = () => { lbEditing = true; renderLbName(); $("lbName").focus(); };
  }
}

async function saveLbName() {
  const name = $("lbName").value.trim();
  $("lbErr").textContent = "";
  $("lbSave").disabled = true;
  try {
    const r = await api("/api/name", { ...lbIdentity(true), name });
    store.set("sweater-lb-name", r.name);
    lbEditing = false;
    toast(`You're on the leaderboard as ${r.name}`);
    renderLeaderboard();
    submitPending();
  } catch (e) {
    $("lbErr").textContent = e.status ? e.message : "Couldn't reach the leaderboard. Try again in a moment.";
    $("lbSave").disabled = false;
  }
}

async function renderLeaderboard() {
  $("lbGameSel").innerHTML = gameOptions(lbGame);
  document.querySelectorAll("[data-period]").forEach(b => b.setAttribute("aria-selected", b.dataset.period === lbPeriod));
  $("lbRules").textContent = LB_RULES[lbGame];
  renderLbName();
  const req = ++lbRequest, me = lbIdentity(false), name = store.get("sweater-lb-name");
  if (G[lbGame].localOnly) {
    $("lbList").innerHTML='<li class="empty">Scores for this new mode are saved on your device. Global rankings are not available yet.</li>';
    $("lbYou").textContent=`Personal best: ${Number(store.get(`sweater-${lbGame}-best`)) || 0}`;
    return;
  }
  if (!$("lbList").children.length) $("lbList").innerHTML = '<li class="empty">Loading…</li>';
  try {
    const d = await api(`/api/leaderboard?game=${lbGame}&period=${lbPeriod}${me ? `&uid=${me.uid}` : ""}`);
    if (req !== lbRequest) return;
    const medal = r => ["🥇", "🥈", "🥉"][r - 1] || r;
    const hlBoard = lbGame.startsWith("hl_"), rosterBoard = lbGame === "roster";
    $("lbList").innerHTML = d.rows.length ? d.rows.map(r => `
      <li class="${r.me ? "me" : ""}">
        <span class="rk">${medal(r.rank)}</span>
        <span class="nm">${esc(r.name)}${lbPeriod === "today" ? "" : `<small>${r.played} played · ${hlBoard || lbGame === "hlt" ? `best run ${r.top}` : rosterBoard || lbGame === "cups" ? `best ${r.top}` : `${r.wins} won`}</small>`}</span>
        <span class="pt">${r.points} pts${lbPeriod === "today" ? `<small>${hlBoard ? `run of ${r.top}` : rosterBoard ? `named ${r.top}` : lbGame === "cups" ? `${r.top} squares` : lbGame === "truths" || lbGame === "trophy" ? `${r.top}/5 right` : lbGame === "hlt" ? `run of ${r.top}` : lbGame === "puck" ? `${r.top} caught` : lbGame === "shoot" ? `${r.top} ${r.top === 1 ? "goal" : "goals"}` : r.wins ? `${r.best} ${r.best === 1 ? "guess" : "guesses"}` : "missed"}</small>` : ""}</span>
      </li>`).join("")
      : `<li class="empty">No scores yet${lbPeriod === "today" ? " today" : ""}. Finish the daily puzzle to get on the board.</li>`;
    $("lbYou").textContent = d.you ? `You're #${d.you.rank} of ${d.total} with ${d.you.points} points.`
      : name ? "Finish this game's daily puzzle to get on this board." : "";
  } catch (e) {
    if (req !== lbRequest) return;
    $("lbList").innerHTML = '<li class="empty">Couldn\'t load the leaderboard. Try again in a moment.</li>';
    $("lbYou").textContent = "";
  }
}

document.querySelectorAll("[data-period]").forEach(b => b.onclick = () => { lbPeriod = b.dataset.period; $("lbList").innerHTML = ""; renderLeaderboard(); });
$("lbBtn").hidden = !API_ON;
document.querySelectorAll(".lbhelp").forEach(el => el.hidden = !API_ON);

// ======================= home screen and navigation =======================
const HUB = [
  { title: "Name the player", tone: "green", games: [
    ["classic", "🏒", "Guess the player from his team, position, age and more."],
    ["statline", "📈", "Name him from his season-by-season stats."],
    ["playoff", "🏒", "Name him from his playoff runs."],
    ["journey", "🧭", "Name him from the teams he's played for."],
    ["blur", "🔍", "Name him from a blurry photo that sharpens as you guess."],
    ["zam", "🧊", "Clear the ice to reveal him. Guess early for more points."],
  ]},
  { title: "Know the details", tone: "blue", games: [
    ["team", "🛡️", "Which team was he on that season?"],
    ["number", "👕", "What number does he wear?"],
    ["draft", "📋", "When was he drafted, and in which round?"],
    ["season", "📅", "Which season did this stat line come from?"],
    ["trophy", "🏆", "Who won the trophy that year?"],
    ["cups", "🏒", "Fill the grid: Cup winners, runners-up and playoff MVPs."],
    ["mroster", "🧢", "Six players, one team. Name it fast."],
    ["map", "📍", "Find where he was born on the map."],
  ]},
  { title: "Streaks and puzzles", tone: "amber", games: [
    ["hl", "↕️", "Whose number is bigger? Keep the streak alive."],
    ["rank", "🥇", "Put five players in order by a stat."],
    ["hlt", "🛡️", "Team against team: which roster has more?"],
    ["truths", "🔍", "Two true, one false. Spot the fib."],
    ["roster", "⏱️", "Name as much of a team's roster as you can in 60 seconds."],
    ["conn", "🧩", "Sort 16 players into 4 hidden groups."],
  ]},
  { title: "Arcade", tone: "red", games: [
    ["puck", "🎯", "Tap every player who fits the rule before he slides by."],
    ["shoot", "🥅", "Answer right to earn a shot, then beat the goalie."],
    ["goalie", "🧤", "Read the shot. Make the save. Own the crease."],
    ["overtime", "⏱️", "Fast hockey trivia. Keep the clock alive."],
  ]},
];
const HL_IDS = Object.keys(HL_STATS).map(s => `hl_${s}`);
const CARD = {};
HUB.forEach(sec => sec.games.forEach(([id, icon]) => { CARD[id] = { icon, tone: sec.tone }; }));
/* Short, repeatable labels make the game library scannable before a player
   has to read a description. They also power the shelf, Locker, and results. */
const MODE_META = Object.freeze({
  classic:  { type: "Deduction", time: "3–5 min", difficulty: "Medium", fact: "Read the board: team, position, age and more all narrow the field.", next: "statline" },
  statline: { type: "Stats", time: "3–5 min", difficulty: "Hard", fact: "Each wrong guess reveals another season from the player’s career.", next: "playoff" },
  playoff:  { type: "History", time: "3–5 min", difficulty: "Hard", fact: "Use postseason runs to identify the player behind the playoff résumé.", next: "trophy" },
  journey:  { type: "Careers", time: "2–4 min", difficulty: "Medium", fact: "The order of a player’s sweaters can be just as revealing as his stats.", next: "team" },
  blur:     { type: "Visual", time: "1–2 min", difficulty: "Medium", fact: "Every guess sharpens the photo—risk a name early for the best score.", next: "zam" },
  zam:      { type: "Visual", time: "1–2 min", difficulty: "Medium", fact: "Clear the ice quickly, but one early correct guess is worth the gamble.", next: "classic" },
  team:     { type: "Seasons", time: "1–2 min", difficulty: "Medium", fact: "The right answer is the sweater the player wore in that exact season.", next: "season" },
  number:   { type: "Details", time: "1 min", difficulty: "Easy", fact: "A player’s number is a small detail—unless it is the one you miss.", next: "draft" },
  draft:    { type: "Draft", time: "2 min", difficulty: "Hard", fact: "Draft position turns hockey memory into a genuine scouting test.", next: "trophy" },
  season:   { type: "Stats", time: "2 min", difficulty: "Hard", fact: "Find the season hidden behind a player’s stat line and team context.", next: "statline" },
  trophy:   { type: "Awards", time: "2–4 min", difficulty: "Hard", fact: "Wrong choices are winners from nearby seasons, so era knowledge matters.", next: "cups" },
  cups:     { type: "History", time: "10 min", difficulty: "Expert", fact: "Every square spans Cup winners, finalists and Conn Smythe winners from 1980 onward.", next: "trophy" },
  mroster:  { type: "Rosters", time: "2 min", difficulty: "Hard", fact: "Six players share one sweater—name the team before the clock beats you.", next: "roster" },
  map:      { type: "Geography", time: "2 min", difficulty: "Medium", fact: "Hockey’s map gets much bigger once you leave North America.", next: "draft" },
  hl:       { type: "Streak", time: "1–3 min", difficulty: "Medium", fact: "Trust the stat you are given, then keep the streak alive one choice at a time.", next: "rank" },
  rank:     { type: "Ordering", time: "2 min", difficulty: "Hard", fact: "Five players, one stat, and no room for a sloppy order.", next: "hl" },
  hlt:      { type: "Teams", time: "1–3 min", difficulty: "Medium", fact: "Every round changes the stat, so the best roster is not always obvious.", next: "rank" },
  truths:   { type: "Hockey IQ", time: "2 min", difficulty: "Medium", fact: "Two statements are true; slow down and spot the one detail that does not fit.", next: "mroster" },
  roster:   { type: "Speed", time: "1 min", difficulty: "Hard", fact: "Depth knowledge matters here—star names alone will not fill a roster.", next: "puck" },
  conn:     { type: "Puzzle", time: "3–5 min", difficulty: "Hard", fact: "The groups are hidden until you find the shared hockey connection.", next: "truths" },
  puck:     { type: "Arcade", time: "1–2 min", difficulty: "Medium", fact: "Fast answers score, but the wrong tap costs you the run.", next: "shoot" },
  shoot:    { type: "Arcade", time: "2 min", difficulty: "Medium", fact: "Answer the hockey question first—then turn it into a goal.", next: "puck" },
  goalie:   { type: "Arcade", fact: "Read the puck's path before committing. Every five straight saves builds your multiplier.", next: "overtime" },
  overtime: { type: "Arcade", fact: "Accuracy buys time. Keep answering until the buzzer—or clear the whole board.", next: "goalie" },
});
const modeMeta = id => MODE_META[id] || { type: "Daily", time: "2–4 min", difficulty: "Medium", fact: "A fresh hockey puzzle is ready every day.", next: "classic" };
const hubIds = () => HUB.flatMap(sec => sec.games.map(([id]) => id));
const cleanHubIds = ids => [...new Set((Array.isArray(ids) ? ids : []).filter(id => hubIds().includes(id)))];
const favouriteIds = () => cleanHubIds(store.get("sweater-favourites"));
const recentIds = () => cleanHubIds(store.get("sweater-recent-games"));
function toggleFavourite(id) {
  const ids = favouriteIds();
  const next = ids.includes(id) ? ids.filter(x => x !== id) : [id, ...ids];
  store.set("sweater-favourites", next);
  return next.includes(id);
}
function rememberGame(id) {
  const hubId = id.startsWith("hl_") ? "hl" : id;
  if (!hubIds().includes(hubId)) return;
  store.set("sweater-recent-games", [hubId, ...recentIds().filter(x => x !== hubId)].slice(0, 6));
}
const cardTitle = id => id === "hl" ? "Higher or Lower" : G[id].title;
let onHub = true, statsGame = null;

function hubStatus(id) {
  const today = dayKey();
  if (id === "hl") {
    const played = HL_IDS.filter(g => historyGet(g, today));
    const going = HL_IDS.some(g => { const sv = store.get(KEYS[g].daily);
      return sv && sv.date === today && sv.guesses && sv.guesses.length && !historyGet(g, today); });
    if (!played.length) return going ? ["going", "In progress"] : ["", "Play"];
    const best = Math.max(...played.map(g => historyGet(g, today).s));
    return ["done", `${played.length} of ${HL_IDS.length} stats · best run ${best}`];
  }
  const h = historyGet(id, today), g = G[id];
  if (h) {
    if (g.archiveStatus) return ["done", g.archiveStatus(h)];
    if (g.kind === "score") return ["done", `${h.s} pts`];
    return h.w ? ["done", `Solved in ${h.n}`] : ["missed", "Missed today"];
  }
  const saved = store.get(KEYS[id].daily);
  if (saved && saved.date === today && saved.guesses && saved.guesses.length) return ["going", "In progress"];
  return ["", "Play"];
}

const FEATURE_SEQUENCE = ["trophy", "cups", "classic", "shoot", "map", "conn", "journey"];
const gameIsReady = id => id === "hl" ? HL_POOL.length > 1 : G[id] && G[id].pool().length > 0;
const LIBRARY_FILTERS = [
  ["all", "All games"], ["favourites", "Favourites"], ["player", "Name a player"], ["details", "Hockey IQ"], ["puzzles", "Puzzles & streaks"], ["arcade", "Arcade"],
];
const librarySection = { player: "Name the player", details: "Know the details", puzzles: "Streaks and puzzles", arcade: "Arcade" };
function weeklyDoneGames(theme = activeWeeklyTheme()) {
  const day = dayKey(), weekday = (new Date(`${day}T12:00:00Z`).getUTCDay() + 6) % 7;
  const days = Array.from({ length: weekday + 1 }, (_, i) => shiftDay(day, -i));
  const entries = historyEntries();
  return theme.games.filter(g => entries.some(x => (g === "hl" ? x.game.startsWith("hl_") : x.game === g) && days.includes(x.day)));
}
function renderHub() {
  const allCards = HUB.flatMap(sec => sec.games);
  const total = allCards.length;
  const played = allCards.filter(([id]) => ["done", "missed"].includes(hubStatus(id)[0])).length;
  const going = allCards.find(([id]) => hubStatus(id)[0] === "going");
  const dateSeed = Number(dayKey().replaceAll("-", ""));
  const candidate = FEATURE_SEQUENCE[dateSeed % FEATURE_SEQUENCE.length];
  const primary = going ? going[0] : (gameIsReady(candidate) ? candidate : "classic");
  const primaryState = hubStatus(primary);
  const primaryIcon = (CARD[primary] || {}).icon || "🏒";
  const primaryCopy = going ? "Your current run is waiting—pick up where you left off." : HUB.flatMap(s => s.games).find(([id]) => id === primary)?.[2] || "Your next daily puzzle is ready.";
  const hatTrickCount = dailyEntries(dayKey()).length;
  const quickGame = ["classic", "trophy", "shoot"].find(id => hubStatus(id)[0] !== "done" && gameIsReady(id)) || primary;
  const theme = activeWeeklyTheme(), completedThemeGames = weeklyDoneGames(theme);
  const weeklyGame = theme.games.find(id => !completedThemeGames.includes(id) && gameIsReady(id)) || primary;
  $("hubFeatures").innerHTML = `<button type="button" class="hubfeature primary" data-open="${primary}">
      <p class="featureeyebrow">${going ? "Continue playing" : "Today's featured game"}</p>
      <h2 class="featuretitle"><span class="featureicon" aria-hidden="true">${modeIcon(primary)}</span>${esc(cardTitle(primary))}</h2>
      <p class="featurecopy">${esc(primaryCopy)}</p>
      <span class="featurefooter"><span>${primaryState[0] === "done" ? "Daily complete" : primaryState[0] === "going" ? "In progress" : "New daily puzzle"}</span><b>${going ? "Resume" : "Play"} →</b></span>
    </button><div class="queststack">
      <button type="button" class="hubfeature quest" data-open="${quickGame}">
        <span class="questprogress">${Math.min(hatTrickCount, 3)}/3</span><p class="featureeyebrow">Daily Hat Trick</p>
        <h2 class="featuretitle">Play any 3 dailies</h2><p class="featurecopy">Build your daily routine and earn a badge.</p>
      </button>
      <button type="button" class="hubfeature quest" data-open="${weeklyGame}">
        <span class="questprogress">${completedThemeGames.length}/3</span><p class="featureeyebrow">Weekly challenge</p>
        <h2 class="featuretitle">${esc(theme.title)}</h2><p class="featurecopy">${esc(theme.copy)}</p>
      </button>
    </div>`;
  const favourites = favouriteIds(), recents = recentIds();
  const shelfIds = (favourites.length ? favourites : recents).filter(gameIsReady).slice(0, 3);
  const shelfLabel = favourites.length ? "Your favourites" : recents.length ? "Keep playing" : "Start here";
  const shelfHint = favourites.length ? "Your saved modes" : recents.length ? "Your recent modes" : "A few great first shifts";
  $("hubShelf").hidden = !shelfIds.length;
  $("hubShelf").innerHTML = shelfIds.length ? `<div class="shelfhead"><b>${shelfLabel}</b><span>${shelfHint}</span></div><div class="shelfscroll">${shelfIds.map(id => {
    const card = CARD[id] || { icon: "🏒" }, meta = modeMeta(id);
    return `<button type="button" class="shelfcard" data-open="${id}"><span class="shelficon" aria-hidden="true">${modeIcon(id)}</span><b>${esc(cardTitle(id))}</b></button>`;
  }).join("")}</div>` : "";
  const selectedFilter = store.get("sweater-library-filter") || "all";
  $("libraryFilters").innerHTML = LIBRARY_FILTERS.map(([id, label]) => `<button type="button" class="libraryfilter" data-library-filter="${id}" aria-pressed="${selectedFilter === id}">${label}</button>`).join("");
  const librarySections = HUB.map(sec => ({ ...sec, games: sec.games.filter(([id]) =>
    selectedFilter === "all" || (selectedFilter === "favourites" ? favourites.includes(id) : sec.title === librarySection[selectedFilter])
  ) })).filter(sec => sec.games.length);
  $("hubSections").innerHTML = librarySections.length ? librarySections.map(sec => `
    <section class="hubsec tone-${sec.tone}">
      <h2>${sec.title}</h2>
      <div class="glist">${sec.games.map(([id, icon, blurb]) => {
        const [cls, text] = hubStatus(id);
        const ready = gameIsReady(id);
        const meta = modeMeta(id), favourited = favourites.includes(id);
        return `<div class="librarygame ${cls}"><button type="button" class="grow ${cls}" data-open="${id}"${ready ? "" : " disabled"}>
          <span class="gicon" aria-hidden="true">${modeIcon(id)}</span>
          <span class="gtext"><b>${esc(cardTitle(id))}</b><small>${esc(blurb)}</small></span>
          <span class="gstat">${ready ? esc(text) : "Not available"}</span>
          <span class="chev" aria-hidden="true">›</span>
        </button><button type="button" class="favtoggle" data-favorite="${id}" aria-label="${favourited ? "Remove" : "Add"} ${esc(cardTitle(id))} ${favourited ? "from" : "to"} favourites" aria-pressed="${favourited}" title="${favourited ? "Remove from" : "Add to"} favourites">${uiIcon("star")}</button></div>`;
      }).join("")}</div>
    </section>`).join("") : `<p class="lockerhint">No favourites yet. Tap the star beside a game to build your shelf.</p>`;
  const libraryOpen = store.get("sweater-library-open") === true;
  $("hubSections").hidden = !libraryOpen;
  $("libraryToggle").setAttribute("aria-expanded", libraryOpen ? "true" : "false");
  $("libraryToggle").innerHTML = `${libraryOpen ? "Hide game library" : "Browse all games"} <span aria-hidden="true">›</span>`;
  $("hubProgress").textContent = `Daily Hat Trick ${Math.min(hatTrickCount, 3)}/3 · ${played} of ${total} games played today.`;
  $("hubBar").style.width = `${Math.round(played / total * 100)}%`;
  $("hubDate").textContent = new Date().toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" });
  document.querySelector(".partycard").disabled = !API_ON;
  document.querySelector(".partycard .partycta").textContent = API_ON ? "Start a party" : "Not available";
}
$("libraryToggle").onclick = () => { store.set("sweater-library-open", !(store.get("sweater-library-open") === true)); renderHub(); };
$("libraryFilters").addEventListener("click", e => {
  const b = e.target.closest("[data-library-filter]");
  if (!b) return;
  store.set("sweater-library-filter", b.dataset.libraryFilter);
  store.set("sweater-library-open", true);
  renderHub();
});
$("view-hub").addEventListener("click", e => {
  const favourite = e.target.closest("[data-favorite]");
  if (favourite) {
    const on = toggleFavourite(favourite.dataset.favorite);
    toast(on ? `${cardTitle(favourite.dataset.favorite)} added to favourites` : `${cardTitle(favourite.dataset.favorite)} removed from favourites`);
    renderHub();
    return;
  }
  const b = e.target.closest("[data-open]");
  if (!b || b.disabled) return;
  if (b.dataset.open === "party") openParty("");
  else openGame(b.dataset.open);
});

function showHub(push = true) {
  leaveGame(game);
  closeParty();
  onHub = true;
  document.body.classList.add("hubmode");
  if (push && location.hash) history.pushState(null, "", location.pathname + location.search);
  $("view-hub").hidden = false;
  $("gameBar").hidden = true;
  $("archBar").hidden = true;
  new Set(GAME_IDS.map(id => G[id].view)).forEach(v => { $(v).hidden = true; });
  searches.forEach(s => s.close());
  renderHub();
  document.title = "Sweater · NHL player guessing games";
}

function openGame(id, push = true) {
  if (id === "hl") id = game.startsWith("hl_") ? game : (G[store.get("sweater-hl-game")] ? store.get("sweater-hl-game") : "hl_points");
  if (!G[id]) return showHub(push);
  if (id.startsWith("hl_")) store.set("sweater-hl-game", id);
  rememberGame(id);
  if (push && location.hash !== `#${id}`) history.pushState(null, "", `#${id}`);
  closeParty();
  onHub = false;
  document.body.classList.remove("hubmode");
  $("view-hub").hidden = true;
  $("gameBar").hidden = false;
  setGame(id);
  window.scrollTo({ top: 0 });
}

function route() {
  const id = decodeURIComponent(location.hash.slice(1));
  if (id === "party" || id.startsWith("party-")) {
    if ($("view-party").hidden) openParty(id.slice(6).toUpperCase(), false);
    return;
  }
  if (id && (G[id] || id === "hl")) {
    if (!onHub && id === game) return;
    openGame(id, false);
  } else if (!onHub) {
    showHub(false);
  }
}
window.addEventListener("popstate", route);
window.addEventListener("hashchange", route);
$("backHub").onclick = () => showHub();
$("homeLink").onclick = e => { e.preventDefault(); showHub(); };

// game pickers inside the stats, leaderboard and archive windows
function gameOptions(selected) {
  return HUB.map(sec => `<optgroup label="${sec.title}">${sec.games.map(([id]) => id === "hl"
    ? HL_IDS.map(h => `<option value="${h}"${h === selected ? " selected" : ""}>Higher or Lower · ${HL_STATS[G[h].stat].name}</option>`).join("")
    : `<option value="${id}"${id === selected ? " selected" : ""}>${esc(G[id].title)}</option>`).join("")}</optgroup>`).join("");
}
$("hlStatSel").innerHTML = HL_IDS.map(h => `<option value="${h}">${HL_STATS[G[h].stat].name}</option>`).join("");
$("hlStatSel").addEventListener("change", e => openGame(e.target.value));
$("stGameSel").addEventListener("change", e => { statsGame = e.target.value; renderStats(); });
$("lbGameSel").addEventListener("change", e => { lbGame = e.target.value; $("lbList").innerHTML = ""; renderLeaderboard(); });
$("arGameSel").addEventListener("change", e => { renderArchive(e.target.value); });

// ======================= party mode =======================
const PARTY_SHAPES = ["▲", "◆", "●", "■"];
let party = null, partyTimer = null, partyBusy = false;
const partySaved = () => { const p = store.get("sweater-party"); return p && Date.now() - p.at < 6 * 3600e3 ? p : null; };

function openParty(code, push = true) {
  if (push) history.pushState(null, "", code ? `#party-${code}` : "#party");
  leaveGame(game);
  onHub = false;
  document.body.classList.remove("hubmode");
  $("view-hub").hidden = true;
  new Set(GAME_IDS.map(id => G[id].view)).forEach(v => { $(v).hidden = true; });
  $("view-party").hidden = false;
  $("gameBar").hidden = false;
  $("archBar").hidden = true;
  $("gIcon").innerHTML = uiIcon("people");
  $("gameBar").dataset.game = "party";
  $("gameBar").dataset.tone = "blue";
  $("gTitle").textContent = "Party Mode";
  $("modeLabel").textContent = "Live with friends";
  document.title = "Party Mode · Sweater";
  const saved = partySaved();
  party = saved && (!code || saved.code === code) ? { ...saved, state: null } : { role: null, joinCode: code || "" };
  partyRender();
  partyPoll();
  window.scrollTo({ top: 0 });
}
function closeParty() {
  clearInterval(partyTimer);
  partyTimer = null;
  $("view-party").hidden = true;
}
function partyPoll() {
  clearInterval(partyTimer);
  partyTimer = setInterval(partyTick, 1000);
  partyTick();
}
async function partyTick() {
  if (!party || !party.code || partyBusy || $("view-party").hidden || document.hidden) return;
  partyBusy = true;
  try {
    const q = party.role === "player" ? `&pid=${party.pid}&key=${party.key}` : "";
    const st = await api(`/api/party/state?code=${party.code}${q}`);
    party.offset = st.now - Date.now();
    const changed = !party.state || party.state.status !== st.status || party.state.qi !== st.qi;
    party.state = st;
    if (party.role === "host" && st.status === "question" &&
        (partyNow() >= st.endsAt || (st.players.length && st.answered >= st.players.length))) {
      party.state = await api("/api/party/host", { code: party.code, hostKey: party.hostKey, action: "reveal" });
    }
    if (changed) party.picked = null;
    partyRender();
  } catch (e) {
    if (e.status === 404) { store.set("sweater-party", null); party = { role: null, joinCode: "" }; partyRender("That game has ended."); }
  } finally { partyBusy = false; }
}
const partyNow = () => Date.now() + (party.offset || 0);

async function partyHostNew() {
  try {
    const r = await api("/api/party/create", {});
    party = { role: "host", code: r.code, hostKey: r.hostKey, at: Date.now(), state: null, rounds: 10 };
    store.set("sweater-party", party);
    history.replaceState(null, "", "#party");
    partyTick();
  } catch (e) { partyRender(e.status ? e.message : "Couldn't reach the server. Try again."); }
}
async function partyJoin() {
  const code = $("ptCode").value.trim().toUpperCase(), name = $("ptName").value.trim();
  if (!/^[A-Z]{4}$/.test(code)) { partyRender("Enter the 4-letter code from the big screen."); return; }
  try {
    const r = await api("/api/party/join", { code, name });
    party = { role: "player", code: r.code, pid: r.pid, key: r.key, name: r.name, at: Date.now(), state: null };
    store.set("sweater-party", party);
    store.set("sweater-party-name", name);
    partyTick();
  } catch (e) { partyRender(e.status ? e.message : "Couldn't reach the server. Try again."); }
}
async function partyHostAction(action) {
  const body = { code: party.code, hostKey: party.hostKey, action };
  if (action === "start") {
    const qs = [];
    const used = { kinds: new Set(), players: new Set() };
    for (let i = 0; qs.length < party.rounds && i < 200; i++) {
      if (used.kinds.size >= QUIZ_KINDS.length) used.kinds.clear();   // every type used once, so start the cycle again
      const q = quizQuestion(Math.random, PLAYERS, used);
      if (q && !qs.some(x => x.q === q.q)) qs.push({ q: q.q, o: q.o, a: q.a });
    }
    body.questions = qs;
  }
  try { party.state = await api("/api/party/host", body); party.picked = null; partyRender(); }
  catch (e) { toast(e.status ? e.message : "Couldn't reach the server"); }
}
async function partyAnswer(choice) {
  const st = party.state;
  if (!st || st.status !== "question" || party.picked !== null && party.picked !== undefined) return;
  party.picked = choice;
  partyRender();
  try { await api("/api/party/answer", { code: party.code, pid: party.pid, key: party.key, qi: st.qi, choice }); }
  catch (e) { toast(e.status ? e.message : "Couldn't send your answer"); }
}
function partyLeave() {
  store.set("sweater-party", null);
  party = { role: null, joinCode: "" };
  partyRender();
}

function partyTiles(st, host) {
  const q = st.question, reveal = st.status !== "question";
  return `<div class="pttiles${host ? " big" : ""}">${q.o.map((o, i) => {
    const picked = party.picked === i || (st.you && st.you.choice === i);
    const cls = reveal ? (i === q.a ? " right" : " faded") : picked ? " picked" : "";
    return `<button type="button" class="pttile c${i}${cls}" data-choice="${i}"${host || reveal || party.picked != null || st.you ? " disabled" : ""}>
      <span class="shape" aria-hidden="true">${PARTY_SHAPES[i]}</span><span>${esc(o)}</span>
      ${reveal && st.counts ? `<b class="count">${st.counts[i]}</b>` : ""}</button>`;
  }).join("")}</div>`;
}
function partyBoard(st, n = 5) {
  return `<ol class="ptboard">${st.players.slice(0, n).map((p, i) => `<li class="${p.me ? "me" : ""}"><span>${i + 1}</span><b>${esc(p.name)}</b><em>${p.score.toLocaleString()}</em></li>`).join("")}</ol>`;
}
let partySig = "";
function partyRender(message = "") {
  const box = $("ptBody"), st = party && party.state;
  const sig = JSON.stringify([message, party && party.role, party && party.picked, party && party.rounds, st && { ...st, now: 0 }]);
  if (sig === partySig && box.innerHTML) {
    if (st && st.endsAt) {
      const secs = Math.max(0, Math.ceil((st.endsAt - partyNow()) / 1000));
      if ($("ptSecs")) $("ptSecs").textContent = secs;
      if ($("ptBar")) $("ptBar").style.width = `${Math.min(100, secs / st.limit * 100)}%`;
    }
    return;
  }
  partySig = sig;
  const note = message ? `<p class="ptnote">${esc(message)}</p>` : "";
  if (!API_ON) { box.innerHTML = `<p class="ptnote">Party Mode needs the leaderboard server, which isn't set up for this site.</p>`; return; }
  if (!party || !party.role) {
    box.innerHTML = `${note}
      <div class="ptchoice">
        <section class="ptpanel">
          <h3>Host a game</h3>
          <p>Use a TV, laptop or tablet everyone can see. Friends join on their phones.</p>
          <button type="button" class="btn" id="ptHost">Host on this screen</button>
        </section>
        <section class="ptpanel">
          <h3>Join a game</h3>
          <label>Code <input id="ptCode" maxlength="4" autocomplete="off" autocapitalize="characters" placeholder="ABCD" value="${esc(party ? party.joinCode || "" : "")}"></label>
          <label>Your name <input id="ptName" maxlength="14" autocomplete="nickname" placeholder="Name" value="${esc(store.get("sweater-party-name") || "")}"></label>
          <button type="button" class="btn" id="ptJoin">Join</button>
        </section>
      </div>`;
    $("ptHost").onclick = partyHostNew;
    $("ptJoin").onclick = partyJoin;
    [$("ptCode"), $("ptName")].forEach(i => i.addEventListener("keydown", e => { if (e.key === "Enter") partyJoin(); }));
    return;
  }
  if (!st) { box.innerHTML = `${note}<p class="ptnote">Connecting…</p>`; return; }
  const secs = st.endsAt ? Math.max(0, Math.ceil((st.endsAt - partyNow()) / 1000)) : 0;
  const leave = `<button type="button" class="linkbtn ptleave" id="ptLeave">${party.role === "host" ? "End and leave" : "Leave game"}</button>`;
  let html = "";
  if (party.role === "host") {
    const link = `${location.origin}${location.pathname}#party-${st.code}`;
    if (st.status === "lobby") {
      html = `<div class="ptlobby">
          <p class="ptlabel">On your phone, go to <b>${esc(location.host + location.pathname.replace(/index\.html$/, ""))}</b>, choose Party Mode and enter</p>
          <p class="ptcode">${st.code}</p>
          <p class="ptlink">or open ${esc(link)}</p>
        </div>
        <div class="ptplayers">${st.players.length ? st.players.map(p => `<span class="chip">${esc(p.name)}</span>`).join("") : "<p class='ptnote'>Waiting for players to join…</p>"}</div>
        <div class="ptcontrols">
          <label>Questions <select id="ptRounds">${[5, 10, 15].map(n => `<option${n === party.rounds ? " selected" : ""}>${n}</option>`).join("")}</select></label>
          <button type="button" class="btn" id="ptStart"${st.players.length ? "" : " disabled"}>Start game</button>
        </div>`;
    } else if (st.status === "question" || st.status === "reveal") {
      const reveal = st.status === "reveal";
      html = `<div class="pthead"><span>Question ${st.qi + 1} of ${st.total}</span>
          <span>${reveal ? "Answer" : `${st.answered} of ${st.players.length} answered`}</span></div>
        ${reveal ? "" : `<div class="pttimer"><i id="ptBar" style="width:${Math.min(100, secs / st.limit * 100)}%"></i><b id="ptSecs">${secs}</b></div>`}
        <h3 class="ptq">${esc(st.question.q)}</h3>
        ${partyTiles(st, true)}
        ${reveal ? `${partyBoard(st)}<div class="ptcontrols"><button type="button" class="btn" id="ptNext">${st.qi + 1 >= st.total ? "See final results" : "Next question"}</button></div>`
                 : `<div class="ptcontrols"><button type="button" class="btn ghost" id="ptReveal">Show answer now</button></div>`}`;
    } else {
      const podium = st.players.slice(0, 3);
      html = `<h3 class="ptq">Final results</h3>
        <div class="ptpodium">${podium.map((p, i) => `<div class="step s${i}"><span>${["🥇", "🥈", "🥉"][i]}</span><b>${esc(p.name)}</b><em>${p.score.toLocaleString()}</em></div>`).join("")}</div>
        ${partyBoard(st, 30)}
        <div class="ptcontrols"><button type="button" class="btn" id="ptAgain">Host another game</button></div>`;
    }
  } else {
    const me = st.players.find(p => p.me), rank = st.players.findIndex(p => p.me) + 1;
    if (st.status === "lobby") {
      html = `<div class="ptwait"><p class="ptbig">You're in, ${esc(party.name)}!</p><p>Watch the big screen. The game starts soon.</p><p class="ptnote">Game ${st.code} · ${st.players.length} ${st.players.length === 1 ? "player" : "players"}</p></div>`;
    } else if (st.status === "question") {
      const locked = party.picked != null || st.you;
      html = `<div class="pthead"><span>Question ${st.qi + 1} of ${st.total}</span><span><b id="ptSecs">${secs}</b>s</span></div>
        <h3 class="ptq small">${esc(st.question.q)}</h3>
        ${partyTiles(st, false)}
        <p class="ptnote">${locked ? "Locked in. Look at the big screen." : "Tap your answer."}</p>`;
    } else if (st.status === "reveal") {
      const got = st.you && st.you.points > 0;
      html = `<div class="ptwait ${st.you ? (got ? "good" : "bad") : ""}">
          <p class="ptbig">${!st.you ? "Too slow!" : got ? `Correct! +${st.you.points}` : "Not this time"}</p>
          <p>You're ${ordinal(rank)} with ${me ? me.score.toLocaleString() : 0} points.</p></div>`;
    } else {
      html = `<div class="ptwait"><p class="ptbig">You finished ${ordinal(rank)}</p><p>${me ? me.score.toLocaleString() : 0} points · ${st.players.length} ${st.players.length === 1 ? "player" : "players"}</p></div>
        ${partyBoard(st, 10)}`;
    }
  }
  box.innerHTML = note + html + leave;
  const on = (id, f) => { const el = $(id); if (el) el.onclick = f; };
  on("ptStart", () => partyHostAction("start"));
  on("ptReveal", () => partyHostAction("reveal"));
  on("ptNext", () => partyHostAction("next"));
  on("ptAgain", () => { store.set("sweater-party", null); partyHostNew(); });
  on("ptLeave", async () => { if (party.role === "host") await partyHostAction("end"); partyLeave(); });
  const rounds = $("ptRounds");
  if (rounds) rounds.onchange = () => { party.rounds = Number(rounds.value); store.set("sweater-party", party); };
  box.querySelectorAll(".pttile:not([disabled])").forEach(b => b.onclick = () => partyAnswer(Number(b.dataset.choice)));
}

// ======================= help window =======================
const HELP = {
  classic: `<p>Guess the player in 8 tries. Each guess shows how he compares on team, conference, division, position, shooting hand, age, birth country and number.</p>
    <p>Yellow on <b>team</b> means the answer used to play there. Yellow on <b>age</b> or <b>#</b> means within 2, and the arrow points toward the answer.</p>
    <p>Stuck? <b>Show silhouette</b>. <b>Hard mode</b> hides it and locks once you guess.</p>`,
  statline: `<p>Name the player from his regular-season stats. You start with one season, and each miss unlocks another. 8 tries.</p>
    <p>Before your first guess, choose whether his oldest or newest seasons appear first. After 4 misses you'll see his current team.</p>`,
  journey: `<p>Name the player from the teams he's played for, in order, with seasons and games. 6 tries.</p>
    <p>Hints appear after 2, 4 and 5 misses: position, birth country, then sweater number.</p>`,
  blur: `<p>Name the player from a blurry photo. Every miss sharpens it. 6 tries, with hints after 3 and 5 misses.</p>`,
  team: `<p>You see a player and one season of his stats. Pick the team he played for that season. 5 tries.</p>
    <p>Yellow means the right team is in the same division.</p>`,
  number: `<p>Guess the player's sweater number in 5 tries. Arrows say go higher or lower, and yellow means you're within 3.</p>`,
  draft: `<p>Guess the year and round he was drafted, in 5 tries. Arrows point to a later or earlier year and round.</p>
    <p>Yellow means the year is within 2 or the round within 1. After 3 misses you'll see who drafted him.</p>`,
  map: `<p>Tap the map, then <b>Drop pin here</b>. You get 3 pins; each shows how far off you were and which way to go. A pin within 100 km wins.</p>
    <p>Drag to move the map. Pinch, scroll or use + and − to zoom.</p>`,
  hl: `<p>Is the second player's number higher or lower than the first? Pick what to compare from the <b>Stat</b> menu: best-season goals, assists, points or PIM, career games, height, weight or age.</p>
    <p>A right answer keeps your run going and ties count as right. The daily run has 40 matchups. On a keyboard, use ↑ and ↓.</p>`,
  roster: `<p>Press <b>Start</b>, then type as many players on the team's roster as you can in 60 seconds. A last name is enough unless two players share it.</p>`,
  zam: `<p>Drag across the ice to clear it and reveal the player's photo. Guess whenever you're ready. You get 3 guesses.</p>
    <p>The less ice you've cleared when you get it, the more points you score.</p>`,
  rank: `<p>Drag the 5 players into order by the stat shown, or use the arrows, then press <b>Lock it in</b>. You get 3 tries; rows in the right spot turn green.</p>`,
  puck: `<p>Press <b>Drop the puck</b>. Player names slide across the ice. Tap only the ones who fit the rule before they pass. Each right tap is a point and each wrong tap costs one.</p>`,
  shoot: `<p>Five shooters. Answer each question right to earn a shot, then pick a spot on the net. If the goalie guessed the same spot, it's a save. Score 3 or more to win.</p>`,
  goalie: `<p>Press <b>Take the net</b>. Watch the puck and tap the area it is heading for before it reaches the goal. You can commit only once per shot. Use Q/E for top left/right, Z/C for bottom left/right, or Space for five-hole.</p><p>Shots speed up and can curve after the first five. Each save earns 10 points; every five straight saves increases your multiplier, up to 5×. A goal resets the streak, and three goals end your run. Leaving, reloading, or hiding the game ends a started run.</p>`,
  overtime: `<p>Start with <b>30 seconds</b>. Pick an answer or press 1–4: a right answer adds 3 seconds and a wrong answer costs 5. The clock keeps running during the brief answer reveal. Bank up to 60 seconds.</p><p>Each right answer earns one point. Survive until the clock runs out, or clear the 100-question board. Leaving, reloading, or hiding the game ends a started run.</p>`,
  playoff: `<p>Name the player from his playoff stat lines. You start with his first playoff run, and each wrong guess unlocks another. 6 tries, with a team hint after 4 misses.</p>`,
  cups: `<p>A complete grid from 1980–81 through the latest Final, with three squares per season: the Stanley Cup winner, the runner-up and the Conn Smythe winner. Press Start, then type names for 10 minutes.</p>
    <p>One name fills every square it belongs in, and a team nickname or a surname is enough when only one answer matches it.</p>`,
  trophy: `<p>Choose all trophies or one specific trophy, then pick 5, 10, 15 or 20 questions. Each right answer is worth 2 points.</p>
    <p>It covers winners from 1980 onwards, retired players included, and the wrong answers are nearby-era winners of the same trophy.</p>`,
  mroster: `<p>One player from a mystery team is shown, and you pick the team. Each wrong guess reveals another teammate, up to six. 4 tries, and yellow means the right team is in that division.</p>`,
  truths: `<p>You see a player and three statements about him. Two are true and one isn't. Tap the false one. Five rounds, 2 points each.</p>`,
  hlt: `<p>Two teams go head to head on their current rosters: average age, average height, total career goals, total career NHL games, or players born outside Canada and the USA.</p>
    <p>Guess whether the second team's number is higher or lower. A right answer keeps the run going, and ties count as right.</p>`,
  season: `<p>You see a player and one of his season stat lines. Pick which season it came from, in 3 tries. Arrows point to a later or earlier season.</p>`,
  conn: `<p>Find 4 groups of 4 players who share something, like a team, a birth country, a sweater number or a birth year. Select 4, then <b>Submit</b>.</p>
    <p>Groups go from yellow (easiest) to purple (hardest). Your 4th mistake ends the game.</p>`,
};

function renderHelp() {
  const current = onHub ? null : (game.startsWith("hl_") ? "hl" : game);
  $("helpGames").innerHTML = HUB.map(sec => sec.games.map(([id, icon]) => `
    <details class="helpgame tone-${sec.tone}" data-help="${id}"${id === current ? " open" : ""}>
      <summary><span class="hicon" aria-hidden="true">${modeIcon(id)}</span><span>${esc(cardTitle(id))}</span></summary>
      <div class="helpbody">${HELP[id] || ""}</div>
    </details>`).join("")).join("");
  $("helpLead").hidden = !current;
  if (current) {
    $("helpLead").textContent = `You're playing ${cardTitle(current)}. Its rules are open below.`;
    requestAnimationFrame(() => { const el = $("helpGames").querySelector("[open]"); if (el) el.scrollIntoView({ block: "nearest" }); });
  }
}

// ======================= start =======================
$("foot").textContent = `Player data from NHL.com · refreshed ${BUILT.split(" · ")[0]} · ${PLAYERS.length} players`;
if (!store.get("sweater-seen-welcome")) { store.set("sweater-seen-welcome", true); openModal("welcomeModal"); }
// Hosting this site over HTTPS also turns it into an installable, resilient
// phone app. Local file previews deliberately skip service-worker registration.
if ("serviceWorker" in navigator && /^https?:$/.test(location.protocol)) {
  window.addEventListener("load", () => navigator.serviceWorker.register("sw.js").catch(() => {}));
}

if (PLAYERS.length) {
  const start = decodeURIComponent(location.hash.slice(1));
  if (start === "party" || start.startsWith("party-")) openParty(start.slice(6).toUpperCase(), false);
  else if (start && (G[start] || start === "hl")) openGame(start, false);
  else showHub(false);
  tick();
  submitPending();
} else {
  $("guess").disabled = true;
  $("guess").placeholder = "No players in this file";
  $("foot").textContent = /__BUILT__/.test(BUILT)
    ? "This page hasn't been built yet. Run 'Run Sweater.bat' and use the page it opens."
    : `Built ${BUILT}, but no players were included. Run 'Run Sweater.bat' again and send the window's text for help.`;
  $("foot").style.color = "#c0392b";
}
</script>
</body>
</html>
'''


def get_json(url, timeout=30):
    req = urllib.request.Request(url,
                                 headers={"User-Agent": "Mozilla/5.0 (Sweater game builder)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def fetch(team):
    return get_json(API.format(team=team))


# Team nicknames -> current abbreviations (includes older names of the same franchises)
NICKNAMES = [
    ("Golden Knights", "VGK"), ("Maple Leafs", "TOR"), ("Blue Jackets", "CBJ"), ("Red Wings", "DET"),
    ("Blackhawks", "CHI"), ("Black Hawks", "CHI"), ("Utah Hockey Club", "UTA"), ("Mammoth", "UTA"),
    ("Minnesota North Stars", "MNS"), ("Hartford Whalers", "HFD"), ("Quebec Nordiques", "QUE"),
    ("Atlanta Flames", "AFM"), ("Colorado Rockies", "CLR"), ("Phoenix Coyotes", "PHX"),
    ("Kansas City Scouts", "KCS"), ("California Golden Seals", "CGS"), ("Oakland Seals", "OAK"),
    ("Cleveland Barons", "CLE"),
    ("Ducks", "ANA"), ("Bruins", "BOS"), ("Sabres", "BUF"), ("Flames", "CGY"), ("Hurricanes", "CAR"),
    ("Avalanche", "COL"), ("Stars", "DAL"), ("Oilers", "EDM"), ("Panthers", "FLA"), ("Kings", "LAK"),
    ("Wild", "MIN"), ("Canadiens", "MTL"), ("Predators", "NSH"), ("Devils", "NJD"), ("Islanders", "NYI"),
    ("Rangers", "NYR"), ("Senators", "OTT"), ("Flyers", "PHI"), ("Penguins", "PIT"), ("Sharks", "SJS"),
    ("Kraken", "SEA"), ("Blues", "STL"), ("Lightning", "TBL"), ("Canucks", "VAN"), ("Capitals", "WSH"),
    ("Winnipeg Jets", "WPG"), ("Coyotes", "ARI"), ("Thrashers", "ATL"),
]
CURRENT_TEAMS = set(TEAMS)
CACHE = HERE / "career_cache.json"
CACHE_DAYS = 7


SCHEDULE = HERE / "schedule.json"
GAMES_LIST_MIN = 600       # fewer than this means the stats API gave us a broken list
PLAYER_POOL_MIN = 400      # fewer than this means something went wrong upstream; don't plan puzzles
AWARD_HISTORY = []
CUP_HISTORY = []
LOCK_DAYS = 1      # today and tomorrow never change once scheduled
AHEAD = 30         # how many days to plan ahead
EMBED_AHEAD = 10   # how many future days go into the page (covers a missed update or two)
NO_REPEAT_DAYS = 365


def eastern_today():
    """Today's date in US Eastern time (handles daylight saving without extra packages)."""
    now = datetime.now(timezone.utc)
    y = now.year

    def nth_sunday(month, n):
        d = datetime(y, month, 1, tzinfo=timezone.utc)
        d += timedelta(days=(6 - d.weekday()) % 7)
        return d + timedelta(weeks=n - 1)

    dst_start = nth_sunday(3, 2) + timedelta(hours=7)   # 2 am EST = 07:00 UTC
    dst_end = nth_sunday(11, 1) + timedelta(hours=6)    # 2 am EDT = 06:00 UTC
    offset = -4 if dst_start <= now < dst_end else -5
    return (now + timedelta(hours=offset)).date()


def season_groups(p):
    groups = {}
    for row in p.get("car", []):
        groups.setdefault(row[0], []).append(row)
    return groups


def statline_ok(p):
    """'Guess the player': at least 3 NHL seasons."""
    return len(season_groups(p)) >= 3


def team_seasons(p):
    """'Guess the team': seasons with one team all year, not his current team, 10+ games."""
    out = []
    for year, rows in season_groups(p).items():
        if len(rows) == 1 and rows[0][1] in CURRENT_TEAMS and rows[0][1] != p["team"] and rows[0][2] >= 10:
            out.append(year)
    return sorted(out)


HL_STATS = ["goals", "assists", "points", "pim", "gp", "height", "weight", "age"]
HL_COLUMNS = {"goals": 3, "assists": 4, "points": 5, "pim": 6}
HL_LEN = 40


def hl_ok(p):
    """Higher or Lower: skaters with 100+ NHL regular-season games."""
    return p["pos"] != "G" and sum(r[2] for r in p.get("car", [])) >= 100


def hl_value(p, stat):
    """The number compared in Higher or Lower (older players get a bigger 'age' value)."""
    if stat in HL_COLUMNS:
        idx, totals = HL_COLUMNS[stat], {}
        for r in p.get("car", []):
            totals[r[0]] = totals.get(r[0], 0) + (r[idx] if len(r) > idx else 0)
        return max(totals.values()) if totals else 0
    if stat == "gp":
        return sum(r[2] for r in p.get("car", []))
    if stat == "height":
        return p.get("ht") or 0
    if stat == "weight":
        return p.get("wt") or 0
    return -int(str(p.get("birth") or "2000-01-01").replace("-", ""))


def hl_sequence(ids, highs, seed):
    """HL_LEN + 1 players in a row, no repeats, and no two neighbours with the same career high."""
    if len(ids) < 2:
        return []
    rnd = random.Random(seed)
    seq, used = [], set()
    while len(seq) < HL_LEN + 1:
        pick = None
        for attempt in range(60):
            c = rnd.choice(ids)
            if c in used and len(used) < len(ids):
                continue
            if seq and attempt < 59 and highs[c] == highs[seq[-1]]:
                continue
            pick = c
            break
        pick = pick if pick is not None else rnd.choice(ids)
        seq.append(pick)
        used.add(pick)
    return seq


def plan_hl(days, pool, today):
    lock = (today + timedelta(days=LOCK_DAYS)).isoformat()
    # keep only the stats the game still uses
    days = {k: {st: seq for st, seq in d.items() if st in HL_STATS} for k, d in days.items()}
    for k in list(days):
        if k > lock and any(i not in pool for s in days[k].values() for i in s):
            del days[k]
    ids = sorted(i for i, p in pool.items() if hl_ok(p))
    if len(ids) < 2:
        return dict(sorted(days.items()))
    highs = {s: {i: hl_value(pool[i], s) for i in ids} for s in HL_STATS}
    for n in range(AHEAD + 1):
        k = (today + timedelta(days=n)).isoformat()
        day = days.setdefault(k, {})
        for s in HL_STATS:
            if s not in day:
                day[s] = hl_sequence(ids, highs[s], f"sweater-hl-{s}-{k}")
    return dict(sorted(days.items()))


KNOWN_TEAMS = CURRENT_TEAMS | {"ARI", "PHX", "ATL", "MNS", "HFD", "QUE", "AFM", "CLR", "KCS", "CGS", "OAK", "CLE"}


def stints(p):
    out = []
    for r in p.get("car", []):
        if out and out[-1][0] == r[1]:
            continue
        out.append([r[1]])
    return out


def journey_ok(p):
    s = [x[0] for x in stints(p)]
    return len(s) >= 3 and all(t in KNOWN_TEAMS for t in s) and len(set(s)) >= 2


PY_TEAM_NAMES = {
    "ANA": "Anaheim", "BOS": "Boston", "BUF": "Buffalo", "CGY": "Calgary", "CAR": "Carolina", "CHI": "Chicago",
    "COL": "Colorado", "CBJ": "Columbus", "DAL": "Dallas", "DET": "Detroit", "EDM": "Edmonton", "FLA": "Florida",
    "LAK": "Los Angeles", "MIN": "Minnesota", "MTL": "Montréal", "NSH": "Nashville", "NJD": "New Jersey",
    "NYI": "NY Islanders", "NYR": "NY Rangers", "OTT": "Ottawa", "PHI": "Philadelphia", "PIT": "Pittsburgh",
    "SJS": "San Jose", "SEA": "Seattle", "STL": "St. Louis", "TBL": "Tampa Bay", "TOR": "Toronto", "UTA": "Utah",
    "VAN": "Vancouver", "VGK": "Vegas", "WSH": "Washington", "WPG": "Winnipeg",
    "ARI": "Arizona Coyotes", "ATL": "Atlanta Thrashers", "MNS": "Minnesota North Stars",
    "HFD": "Hartford Whalers", "QUE": "Quebec Nordiques", "AFM": "Atlanta Flames", "CLR": "Colorado Rockies",
    "PHX": "Phoenix Coyotes", "KCS": "Kansas City Scouts", "CGS": "California Golden Seals",
    "OAK": "Oakland Seals", "CLE": "Cleveland Barons"}
CONN_COUNTRIES = {"USA": "the USA", "NLD": "the Netherlands"}


def conn_categories(pool):
    """(tier, label, test) for every group that has at least 4 players. Tier 0 is easiest."""
    def keys(f):
        counts = {}
        for p in pool:
            k = f(p)
            if k not in (None, ""):
                counts[k] = counts.get(k, 0) + 1
        return sorted(k for k, n in counts.items() if n >= 4)
    has_draft = lambda p: isinstance(p.get("draft"), list) and len(p["draft"]) >= 2
    cats = []
    for k in keys(lambda p: p["team"]):
        cats.append((0, f"Plays for {PY_TEAM_NAMES.get(k, k)}", lambda p, k=k: p["team"] == k))
    for k in keys(lambda p: None if p["nation"] in ("CAN", "USA") else p["nation"]):
        name = CONN_COUNTRIES.get(k, COUNTRY_LABELS.get(k, k))
        cats.append((1, f"Born in {name}", lambda p, k=k: p["nation"] == k))
    if sum(p["pos"] == "G" for p in pool) >= 4:
        cats.append((1, "Goalies", lambda p: p["pos"] == "G"))
    for k in keys(lambda p: p.get("number") or None):
        cats.append((2, f"Wears #{k}", lambda p, k=k: p.get("number") == k))
    if sum(p.get("draft") == 0 for p in pool) >= 4:
        cats.append((2, "Went undrafted", lambda p: p.get("draft") == 0))
    for k in keys(lambda p: str(p.get("birth", ""))[:4] or None):
        cats.append((3, f"Born in {k}", lambda p, k=k: str(p.get("birth", "")).startswith(k + "-")))
    for k in keys(lambda p: p["draft"][0] if has_draft(p) else None):
        cats.append((3, f"Drafted in {k}", lambda p, k=k: has_draft(p) and p["draft"][0] == k))
    return cats


def conn_puzzle(pool, cats, seed):
    rnd = random.Random(seed)
    tiers = [[c for c in cats if c[0] == t] for t in range(4)]
    if not all(tiers):
        return None
    for _ in range(300):
        chosen = [rnd.choice(t) for t in tiers]
        groups = []
        for c in chosen:
            fits = [p for p in pool if c[2](p) and not any(o[2](p) for o in chosen if o is not c)]
            if len(fits) < 4:
                break
            groups.append({"label": c[1], "ids": sorted(p["id"] for p in rnd.sample(fits, 4))})
        if len(groups) == 4:
            return groups
    return None


def plan_conn(days, pool, today):
    lock = (today + timedelta(days=LOCK_DAYS)).isoformat()
    days = {k: v for k, v in days.items() if k <= lock or all(i in pool for g in v for i in g["ids"])}
    players = [pool[i] for i in sorted(pool)]
    cats = conn_categories(players)
    for n in range(AHEAD + 1):
        k = (today + timedelta(days=n)).isoformat()
        if k not in days:
            puzzle = conn_puzzle(players, cats, f"sweater-conn-{k}")
            if puzzle:
                days[k] = puzzle
    return dict(sorted(days.items()))


# ---- Rank 'Em, Puck Drop, Shootout, Zamboni ----
RANK_STATS = ["goals", "points", "gp", "height", "weight", "age"]


def rank_value(p, stat):
    car = p.get("car", [])
    if stat == "goals":
        return sum(r[3] for r in car)
    if stat == "points":
        return sum(r[5] for r in car)
    if stat == "gp":
        return sum(r[2] for r in car)
    return hl_value(p, stat)


def rank_puzzle(players, rnd):
    stat = rnd.choice(RANK_STATS)
    pool = [p for p in players if hl_ok(p) and rank_value(p, stat)]
    if len(pool) < 5:
        return None
    for _ in range(200):
        picks = rnd.sample(pool, 5)
        if len({rank_value(p, stat) for p in picks}) == 5:
            return {"stat": stat, "ids": [p["id"] for p in picks]}
    return None


def puck_rules(players):
    rules = []
    count = lambda f: sum(1 for p in players if f(p))
    for t in sorted({p["team"] for p in players}):
        if count(lambda p, t=t: p["team"] == t) >= 8:
            rules.append({"kind": "team", "key": t, "label": f"Plays for {PY_TEAM_NAMES.get(t, t)}"})
    for n in sorted({p["nation"] for p in players} - {"CAN", "USA"}):
        if count(lambda p, n=n: p["nation"] == n) >= 8:
            rules.append({"kind": "nation", "key": n, "label": f"Born in {CONN_COUNTRIES.get(n, COUNTRY_LABELS.get(n, n))}"})
    if count(lambda p: p["pos"] == "D") >= 10:
        rules.append({"kind": "pos", "key": "D", "label": "Plays defence"})
    if count(lambda p: isinstance(p.get("draft"), list) and p["draft"][1] == 1) >= 10:
        rules.append({"kind": "round1", "key": "1", "label": "First-round draft pick"})
    return rules


def puck_match(rule, p):
    k = rule["kind"]
    if k == "team":
        return p["team"] == rule["key"]
    if k == "nation":
        return p["nation"] == rule["key"]
    if k == "pos":
        return p["pos"] == rule["key"]
    return isinstance(p.get("draft"), list) and p["draft"][1] == 1


def puck_puzzle(players, rules, rnd):
    if not rules:
        return None
    rule = rnd.choice(rules)
    yes = [p["id"] for p in players if puck_match(rule, p)]
    no = [p["id"] for p in players if not puck_match(rule, p)]
    if len(yes) < 6 or len(no) < 20:
        return None
    ids = rnd.sample(yes, min(13, len(yes))) + rnd.sample(no, 36 - min(13, len(yes)))
    rnd.shuffle(ids)
    return dict(rule, ids=ids)


QUIZ_KINDS = ["team", "nation", "number", "oldest", "youngest", "defence", "goalie", "draftYear", "draftTeam",
              "draftRound", "position", "height", "tallest", "mostGames", "mostGoals", "mostPoints", "bornIn", "wears",
              "city", "seasons", "pastTeam", "bestGoals"]
POS_LABELS = {"C": "Centre", "L": "Left wing", "R": "Right wing", "D": "Defence", "G": "Goalie"}
QUIZ_COUNTRIES = {"USA": "USA", "NLD": "Netherlands"}


def quiz_question(players, rnd, used=None):
    """A multiple-choice question {q, o: [4 options], a}. `used` keeps a run from repeating a type or a player."""
    used = used if used is not None else {"kinds": set(), "players": set()}
    fresh = [p for p in players if p["id"] not in used["players"]]
    fresh = fresh if len(fresh) >= 8 else players
    skaters = [p for p in fresh if p["pos"] != "G"]
    team = lambda t: PY_TEAM_NAMES.get(t, t)
    country = lambda n: QUIZ_COUNTRIES.get(n, COUNTRY_LABELS.get(n, n))
    has_draft = lambda p: isinstance(p.get("draft"), list) and len(p["draft"]) >= 2
    inches = lambda v: f"{v // 12}′{v % 12}″"
    teams = sorted(CURRENT_TEAMS)

    def near(v, step, low=0):
        out = []
        for _ in range(60):
            n = v + rnd.randint(1, 4) * step * rnd.choice((-1, 1))
            if n >= low and n not in out:
                out.append(n)
            if len(out) == 3:
                break
        return out

    def four(lst, key):
        if len(lst) < 4:
            return None
        f = rnd.sample(lst, 4)
        return f if len({key(x) for x in f}) == 4 else None

    for _ in range(80):
        left = [k for k in QUIZ_KINDS if k not in used["kinds"]] or QUIZ_KINDS
        kind, p = rnd.choice(left), rnd.choice(fresh)
        q = opts = right = None
        who = [p]
        if kind == "team":
            o = sorted({x["team"] for x in players} - {p["team"]})
            if len(o) >= 3:
                opts, right, q = [team(t) for t in rnd.sample(o, 3)], team(p["team"]), f"Which team does {p['name']} play for?"
        elif kind == "nation":
            o = sorted({x["nation"] for x in players} - {p["nation"]})
            if len(o) >= 3:
                opts, right, q = [country(n) for n in rnd.sample(o, 3)], country(p["nation"]), f"Which country was {p['name']} born in?"
        elif kind == "number":
            o = sorted({x.get("number") for x in players if x.get("number")} - {p.get("number")})
            if p.get("number") and len(o) >= 3:
                opts, right, q = [f"#{n}" for n in rnd.sample(o, 3)], f"#{p['number']}", f"What number does {p['name']} wear?"
        elif kind in ("oldest", "youngest"):
            f = four(fresh, lambda x: x["birth"])
            if f:
                t = min(f, key=lambda x: x["birth"]) if kind == "oldest" else max(f, key=lambda x: x["birth"])
                opts, right, who = [x["name"] for x in f if x is not t], t["name"], f
                q = f"Which of these players is the {kind}?"
        elif kind in ("defence", "goalie"):
            want = "D" if kind == "defence" else "G"
            yes = [x for x in fresh if x["pos"] == want]
            no = [x for x in fresh if x["pos"] in ("C", "L", "R")]
            if yes and len(no) >= 3:
                y, n3 = rnd.choice(yes), rnd.sample(no, 3)
                opts, right, who = [x["name"] for x in n3], y["name"], [y] + n3
                q = f"Which of these players is a {'defenceman' if kind == 'defence' else 'goalie'}?"
        elif kind == "draftYear":
            if has_draft(p):
                opts, right = [str(v) for v in near(p["draft"][0], 1, 1980)], str(p["draft"][0])
                q = f"What year was {p['name']} drafted?"
        elif kind == "draftTeam":
            if has_draft(p) and p["draft"][3] in CURRENT_TEAMS:
                opts = [team(t) for t in rnd.sample([t for t in teams if t != p["draft"][3]], 3)]
                right, q = team(p["draft"][3]), f"Which team drafted {p['name']}?"
        elif kind == "draftRound":
            if has_draft(p) and p["draft"][1] <= 7:
                opts = [f"Round {r}" for r in rnd.sample([r for r in range(1, 8) if r != p["draft"][1]], 3)]
                right, q = f"Round {p['draft'][1]}", f"In which round was {p['name']} drafted?"
        elif kind == "position":
            if p["pos"] in POS_LABELS:
                opts = [POS_LABELS[k] for k in rnd.sample([k for k in POS_LABELS if k != p["pos"]], 3)]
                right, q = POS_LABELS[p["pos"]], f"What position does {p['name']} play?"
        elif kind == "height":
            if p.get("ht"):
                opts, right, q = [inches(v) for v in near(p["ht"], 1, 60)], inches(p["ht"]), f"How tall is {p['name']}?"
        elif kind == "tallest":
            f = four([x for x in fresh if x.get("ht")], lambda x: x["ht"])
            if f:
                t = max(f, key=lambda x: x["ht"])
                opts, right, who, q = [x["name"] for x in f if x is not t], t["name"], f, "Which of these players is the tallest?"
        elif kind in ("mostGames", "mostGoals", "mostPoints"):
            key = {"mostGames": "gp", "mostGoals": "goals", "mostPoints": "points"}[kind]
            f = four([x for x in (fresh if kind == "mostGames" else skaters) if x.get("car")], lambda x: rank_value(x, key))
            if f:
                t = max(f, key=lambda x: rank_value(x, key))
                opts, right, who = [x["name"] for x in f if x is not t], t["name"], f
                q = f"Which of these players has the most career {'NHL games' if key == 'gp' else key}?"
        elif kind == "bornIn":
            no = [x for x in fresh if x["nation"] != p["nation"]]
            if len(no) >= 3:
                n3 = rnd.sample(no, 3)
                opts, right, who = [x["name"] for x in n3], p["name"], [p] + n3
                q = f"Which of these players was born in {CONN_COUNTRIES.get(p['nation'], COUNTRY_LABELS.get(p['nation'], p['nation']))}?"
        elif kind == "wears":
            no = [x for x in fresh if x.get("number") and x.get("number") != p.get("number")]
            if p.get("number") and len(no) >= 3:
                n3 = rnd.sample(no, 3)
                opts, right, who, q = [x["name"] for x in n3], p["name"], [p] + n3, f"Which of these players wears #{p['number']}?"
        elif kind == "city":
            if p.get("bp") and len(p["bp"]) > 2:
                cities = sorted({x["bp"][2] for x in players if x.get("bp") and len(x["bp"]) > 2} - {p["bp"][2]})
                if len(cities) >= 3:
                    opts, right, q = rnd.sample(cities, 3), p["bp"][2], f"Which city was {p['name']} born in?"
        elif kind == "seasons":
            n = len(season_groups(p))
            if n >= 2:
                opts, right = [str(v) for v in near(n, 1, 1)], str(n)
                q = f"How many NHL seasons has {p['name']} played?"
        elif kind == "pastTeam":
            years = team_seasons(p)
            if years:
                y = rnd.choice(years)
                t = season_groups(p)[y][0][1]
                opts = [team(x) for x in rnd.sample([x for x in teams if x != t], 3)]
                right, q = team(t), f"Which team did {p['name']} play for in {y}–{(y + 1) % 100:02d}?"
        elif kind == "bestGoals":
            v = 0 if p["pos"] == "G" else hl_value(p, "goals")
            if v:
                opts, right = [str(x) for x in near(v, 2, 0)], str(v)
                q = f"What's the most goals {p['name']} has scored in one NHL season?"
        if not q or not opts or len(opts) != 3 or right in opts or len(set(opts)) != 3:
            continue
        used["kinds"].add(kind)
        used["players"].update(x["id"] for x in who)
        a = rnd.randrange(4)
        opts.insert(a, right)
        return {"q": q, "o": opts, "a": a, "kind": kind}
    return None


def shootout_puzzle(players, rnd):
    if len(players) < 12:
        return None
    rounds, used = [], {"kinds": set(), "players": set()}
    for _ in range(5):
        q = quiz_question(players, rnd, used)
        if not q:
            return None
        q["keep"] = sorted(rnd.sample(range(5), 2))   # net zones the goalie covers
        rounds.append(q)
    return {"rounds": rounds}


# ---- Two Truths, Higher or Lower: Teams, Mystery Season ----
def truth_facts(p, rnd):
    """(true statement, false statement) pairs about one player."""
    inches = lambda v: f"{v // 12}′{v % 12}″"
    out = []
    other_team = rnd.choice([t for t in sorted(CURRENT_TEAMS) if t != p["team"]])
    out.append((f"Plays for {PY_TEAM_NAMES.get(p['team'], p['team'])}", f"Plays for {PY_TEAM_NAMES.get(other_team, other_team)}"))
    if p.get("number"):
        wrong = p["number"] + rnd.choice((-9, -7, -5, 5, 7, 9))
        out.append((f"Wears #{p['number']}", f"Wears #{max(1, wrong)}"))
    others = [n for n in COUNTRY_LABELS if n != p["nation"]]
    if others:
        n2 = rnd.choice(others)
        name = lambda n: CONN_COUNTRIES.get(n, COUNTRY_LABELS.get(n, n))
        out.append((f"Was born in {name(p['nation'])}", f"Was born in {name(n2)}"))
    if p["pos"] in POS_LABELS:
        wrong_pos = rnd.choice([k for k in POS_LABELS if k != p["pos"]])
        out.append((f"Is a {POS_LABELS[p['pos']].lower()}", f"Is a {POS_LABELS[wrong_pos].lower()}"))
    if isinstance(p.get("draft"), list) and len(p["draft"]) >= 2:
        y = p["draft"][0]
        out.append((f"Was drafted in {y}", f"Was drafted in {y + rnd.choice((-4, -3, 3, 4))}"))
    seasons = len(season_groups(p))
    if seasons >= 2:
        out.append((f"Has played {seasons} NHL seasons", f"Has played {max(1, seasons + rnd.choice((-3, -2, 2, 3)))} NHL seasons"))
    if p.get("ht"):
        out.append((f"Is {inches(p['ht'])} tall", f"Is {inches(p['ht'] + rnd.choice((-3, -2, 2, 3)))} tall"))
    if p["pos"] != "G":
        high = hl_value(p, "goals")
        if high:
            out.append((f"Once scored {high} goals in a season", f"Once scored {high + rnd.choice((-12, -8, 8, 12))} goals in a season"))
    games = sum(r[2] for r in p.get("car", []))
    if games >= 100:
        out.append((f"Has played over {games // 100 * 100} NHL games", f"Has played over {games // 100 * 100 + 300} NHL games"))
    return [(t, f) for t, f in out if t != f and "-" not in f]


def truths_puzzle(players, rnd):
    if len(players) < 8:
        return None
    rounds, seen = [], set()
    for _ in range(200):
        if len(rounds) == 5:
            return {"rounds": rounds}
        p = rnd.choice(players)
        if p["id"] in seen:
            continue
        facts = truth_facts(p, rnd)
        if len(facts) < 4:
            continue
        picks = rnd.sample(facts, 3)
        lines = [picks[0][0], picks[1][0], picks[2][1]]   # two true, one false
        if len(set(lines)) < 3:
            continue
        order = rnd.sample(range(3), 3)
        rounds.append({"p": p["id"], "s": [lines[i] for i in order], "f": order.index(2)})
        seen.add(p["id"])
    return None


HLT_METRICS = ["age", "height", "goals", "games", "abroad"]


def hlt_value(roster, metric):
    if not roster:
        return 0
    if metric == "age":
        today = eastern_today()
        ages = [(today - date.fromisoformat(p["birth"])).days / 365.25 for p in roster]
        return round(sum(ages) / len(ages), 1)
    if metric == "height":
        hts = [p["ht"] for p in roster if p.get("ht")]
        return round(sum(hts) / len(hts), 1) if hts else 0
    if metric == "goals":
        return sum(rank_value(p, "goals") for p in roster)
    if metric == "games":
        return sum(rank_value(p, "gp") for p in roster)
    return sum(1 for p in roster if p["nation"] not in ("CAN", "USA"))


def hlt_puzzle(players, rnd):
    rosters = {}
    for p in players:
        rosters.setdefault(p["team"], []).append(p)
    teams = sorted(t for t, r in rosters.items() if len(r) >= 10)
    if len(teams) < 4:
        return None
    values = {metric: {t: hlt_value(rosters[t], metric) for t in teams} for metric in HLT_METRICS}
    rounds = []
    while len(rounds) < HL_LEN:
        recent = [team for r in rounds[-2:] for team in (r[0], r[2])]
        metric_choices = [m for m in HLT_METRICS if not rounds or m != rounds[-1][4]]
        pair = None
        for attempt in range(100):
            metric = rnd.choice(metric_choices)
            left, right = rnd.choice(teams), rnd.choice(teams)
            if left == right or (attempt < 70 and (left in recent or right in recent)):
                continue
            if values[metric][left] == values[metric][right]:
                continue
            pair = [left, values[metric][left], right, values[metric][right], metric]
            break
        if pair is None:
            metric = metric_choices[0]
            left, right = teams[len(rounds) % len(teams)], teams[(len(rounds) + 1) % len(teams)]
            pair = [left, values[metric][left], right, values[metric][right], metric]
        rounds.append(pair)
    return {"rounds": rounds}


def season_puzzle(players, rnd):
    pool = [p for p in players if len(season_groups(p)) >= 4]
    if not pool:
        return None
    p = rnd.choice(pool)
    return {"id": p["id"], "y": rnd.choice(sorted(season_groups(p)))}


# ---- Playoff Hero, Trophy Case, Mystery Roster ----
def playoff_seasons(p):
    years = {}
    for r in p.get("po", []):
        years.setdefault(r[0], []).append(r)
    return years


def playoff_ok(p):
    return len(playoff_seasons(p)) >= 3


def playoff_puzzle(players, rnd):
    pool = [p for p in players if playoff_ok(p)]
    return {"id": rnd.choice(pool)["id"]} if pool else None


TROPHY_SKIP = ("Stanley Cup", "Presidents' Trophy", "Prince of Wales", "Clarence S. Campbell")
TROPHY_FIRST_YEAR = 1980          # Trophy Case covers 1980 onwards
TROPHY_URLS = [
    "https://records.nhl.com/site/api/trophy?include=seasons&limit=-1",
    "https://records.nhl.com/site/api/award-winner?limit=-1",
    "https://records.nhl.com/site/api/nhl-award-winner?limit=-1",
    "https://api.nhle.com/stats/rest/en/trophy?limit=-1",
    "https://api.nhle.com/stats/rest/en/award?limit=-1",
]


def dig(obj, *names):
    """Pull a value out of the NHL's JSON, which nests names in a few different ways."""
    for n in names:
        v = obj.get(n)
        if isinstance(v, dict):
            v = v.get("default") or v.get("en")
        if v not in (None, ""):
            return v
    return None


WIKI_API = ("https://en.wikipedia.org/w/api.php?action=query&prop=revisions&rvslots=main&rvprop=content"
            "&format=json&formatversion=2&redirects=1&titles={titles}")
WIKI_TROPHIES = ["Hart Memorial Trophy", "Vezina Trophy", "James Norris Memorial Trophy", "Calder Memorial Trophy",
                 "Art Ross Trophy", "Maurice Richard Trophy", "Conn Smythe Trophy", "Frank J. Selke Trophy",
                 "Lady Byng Memorial Trophy", "Ted Lindsay Award", "Bill Masterton Memorial Trophy",
                 "King Clancy Memorial Trophy"]
NOT_A_PLAYER = re.compile(r"(season|NHL|Trophy|Award|List of|Stanley Cup|Conference|Division|Hockey League"
                          r"|Ducks|Bruins|Sabres|Flames|Hurricanes|Blackhawks|Avalanche|Blue Jackets|Stars|Red Wings"
                          r"|Oilers|Panthers|Kings|Wild|Canadiens|Predators|Devils|Islanders|Rangers|Senators|Flyers"
                          r"|Penguins|Sharks|Kraken|Blues|Lightning|Maple Leafs|Mammoth|Canucks|Golden Knights"
                          r"|Capitals|Jets|Coyotes|Thrashers|Whalers|Nordiques|North Stars)", re.I)
SEASON_RE = re.compile("\\b(19[2-9]\\d|20[0-4]\\d)[\u2013\u2014-](?:\\d{2,4})\\b")
LINK_RE = re.compile(r"\[\[([^\]|#]+)(?:\|[^\]]*)?\]\]")


WIKI_HTML = ("https://en.wikipedia.org/w/api.php?action=parse&prop=text&format=json&formatversion=2"
             "&redirects=1&page={title}")
HREF_RE = re.compile(r'<a[^>]+href="/wiki/([^"#?]+)"')
ROW_RE = re.compile(r"<tr[^>]*>", re.I)
TAG_RE = re.compile(r"<[^>]+>")
NOT_A_NAME = re.compile(r"(season|NHL|Trophy|Award|List_of|Stanley_Cup|Conference|Division|Hockey_League|Category"
                        r"|Canada|United_States|Sweden|Finland|Russia|Soviet_Union|Czech|Slovakia|Switzerland"
                        r"|Germany|Austria|Denmark|Norway|Latvia|France|Ukraine|Belarus|Kazakhstan|File:|Help:)", re.I)


def wiki_html_rows(title):
    """Each row of a Wikipedia page's tables as (plain text, [linked names])."""
    try:
        html = get_json(WIKI_HTML.format(title=urllib.parse.quote(title)), timeout=25)["parse"]["text"]
    except Exception as e:
        print(f"  (couldn't load {title} from Wikipedia: {e})", file=sys.stderr)
        return []
    rows = []
    for row in ROW_RE.split(html)[1:]:
        row = row.split("</tr>")[0]
        names = []
        for href in HREF_RE.findall(row):
            name = urllib.parse.unquote(href).replace("_", " ")
            name = re.sub(r"\s*\([^)]*\)$", "", name).strip()
            if not NOT_A_NAME.search(href) and name not in names:
                names.append(name)
        rows.append((TAG_RE.sub(" ", row), names))
    return rows


def wiki_pages(titles):
    """Raw wikitext for a few Wikipedia pages in one request: {title: text}."""
    out = {}
    for batch in [titles[i:i + 6] for i in range(0, len(titles), 6)]:
        try:
            url = WIKI_API.format(titles=urllib.parse.quote("|".join(batch)))
            pages = get_json(url, timeout=25).get("query", {}).get("pages", [])
        except Exception as e:
            print(f"  (couldn't load Wikipedia pages: {e})", file=sys.stderr)
            continue
        for page in pages:
            text = (((page.get("revisions") or [{}])[0].get("slots") or {}).get("main") or {}).get("content", "")
            if text:
                out[page.get("title", "")] = text
    return out


TEAM_LINK_RE = re.compile(r"(Ducks|Bruins|Sabres|Flames|Hurricanes|Blackhawks|Avalanche|Blue Jackets|Stars"
                          r"|Red Wings|Oilers|Panthers|Kings|Wild|Canadiens|Predators|Devils|Islanders|Rangers"
                          r"|Senators|Flyers|Penguins|Sharks|Kraken|Blues|Lightning|Maple Leafs|Mammoth|Canucks"
                          r"|Golden Knights|Capitals|Jets|Coyotes|Thrashers|Whalers|Nordiques|North Stars|Mighty Ducks"
                          r"|Hockey Club|Metropolitans|Millionaires|Victorias|Wanderers|Shamrocks|Silver Seven"
                          r"|Thistles|Maroons|Eagles|Americans|Pirates|Quakers|Falcons|Cougars|Arenas|St. Patricks)")
CUP_PAGE = "List of Stanley Cup champions"

# The general awards feed is occasionally incomplete (especially during an
# offseason refresh). Keep this small, stable history in the builder so every
# playoff season always has its Conn Smythe answer. Keys are Final years; Cup
# rows use season-start years, so the lookup below uses ``year + 1``.
CONN_SMYTHE_BY_FINAL_YEAR = {
    1981: "Butch Goring", 1982: "Mike Bossy", 1983: "Billy Smith", 1984: "Mark Messier",
    1985: "Wayne Gretzky", 1986: "Patrick Roy", 1987: "Ron Hextall", 1988: "Wayne Gretzky",
    1989: "Al MacInnis", 1990: "Bill Ranford", 1991: "Mario Lemieux", 1992: "Mario Lemieux",
    1993: "Patrick Roy", 1994: "Brian Leetch", 1995: "Claude Lemieux", 1996: "Joe Sakic",
    1997: "Mike Vernon", 1998: "Steve Yzerman", 1999: "Joe Nieuwendyk", 2000: "Scott Stevens",
    2001: "Patrick Roy", 2002: "Nicklas Lidstrom", 2003: "Jean-Sebastien Giguere", 2004: "Brad Richards",
    2006: "Cam Ward", 2007: "Scott Niedermayer", 2008: "Henrik Zetterberg", 2009: "Evgeni Malkin",
    2010: "Jonathan Toews", 2011: "Tim Thomas", 2012: "Jonathan Quick", 2013: "Patrick Kane",
    2014: "Justin Williams", 2015: "Duncan Keith", 2016: "Sidney Crosby", 2017: "Sidney Crosby",
    2018: "Alexander Ovechkin", 2019: "Ryan O'Reilly", 2020: "Victor Hedman", 2021: "Andrei Vasilevskiy",
    2022: "Cale Makar", 2023: "Jonathan Marchessault", 2024: "Connor McDavid", 2025: "Sam Bennett",
    2026: "Jordan Staal",
}
CONN_SMYTHE_TEAM_BY_FINAL_YEAR = {
    1981: "NYI", 1982: "NYI", 1983: "NYI", 1984: "EDM", 1985: "EDM", 1986: "MTL",
    1987: "PHI", 1988: "EDM", 1989: "CGY", 1990: "EDM", 1991: "PIT", 1992: "PIT",
    1993: "MTL", 1994: "NYR", 1995: "NJD", 1996: "COL", 1997: "DET", 1998: "DET",
    1999: "DAL", 2000: "NJD", 2001: "COL", 2002: "DET", 2003: "ANA", 2004: "TBL",
    2006: "CAR", 2007: "ANA", 2008: "DET", 2009: "PIT", 2010: "CHI", 2011: "BOS",
    2012: "LAK", 2013: "CHI", 2014: "LAK", 2015: "CHI", 2016: "PIT", 2017: "PIT",
    2018: "WSH", 2019: "STL", 2020: "TBL", 2021: "TBL", 2022: "COL", 2023: "VGK",
    2024: "EDM", 2025: "FLA", 2026: "CAR",
}

# A local copy keeps Playoff History available when a build machine cannot
# reach Wikipedia or lacks its CA certificate. Years are season-start years.
CUP_FINALS_FALLBACK = [
    (1980, "New York Islanders", "Minnesota North Stars"), (1981, "New York Islanders", "Vancouver Canucks"),
    (1982, "New York Islanders", "Edmonton Oilers"), (1983, "Edmonton Oilers", "New York Islanders"),
    (1984, "Edmonton Oilers", "Philadelphia Flyers"), (1985, "Montreal Canadiens", "Calgary Flames"),
    (1986, "Edmonton Oilers", "Philadelphia Flyers"), (1987, "Edmonton Oilers", "Boston Bruins"),
    (1988, "Calgary Flames", "Montreal Canadiens"), (1989, "Edmonton Oilers", "Boston Bruins"),
    (1990, "Pittsburgh Penguins", "Minnesota North Stars"), (1991, "Pittsburgh Penguins", "Chicago Blackhawks"),
    (1992, "Montreal Canadiens", "Los Angeles Kings"), (1993, "New York Rangers", "Vancouver Canucks"),
    (1994, "New Jersey Devils", "Detroit Red Wings"), (1995, "Colorado Avalanche", "Florida Panthers"),
    (1996, "Detroit Red Wings", "Philadelphia Flyers"), (1997, "Detroit Red Wings", "Washington Capitals"),
    (1998, "Dallas Stars", "Buffalo Sabres"), (1999, "New Jersey Devils", "Dallas Stars"),
    (2000, "Colorado Avalanche", "New Jersey Devils"), (2001, "Detroit Red Wings", "Carolina Hurricanes"),
    (2002, "New Jersey Devils", "Mighty Ducks of Anaheim"), (2003, "Tampa Bay Lightning", "Calgary Flames"),
    (2005, "Carolina Hurricanes", "Edmonton Oilers"), (2006, "Anaheim Ducks", "Ottawa Senators"),
    (2007, "Detroit Red Wings", "Pittsburgh Penguins"), (2008, "Pittsburgh Penguins", "Detroit Red Wings"),
    (2009, "Chicago Blackhawks", "Philadelphia Flyers"), (2010, "Boston Bruins", "Vancouver Canucks"),
    (2011, "Los Angeles Kings", "New Jersey Devils"), (2012, "Chicago Blackhawks", "Boston Bruins"),
    (2013, "Los Angeles Kings", "New York Rangers"), (2014, "Chicago Blackhawks", "Tampa Bay Lightning"),
    (2015, "Pittsburgh Penguins", "San Jose Sharks"), (2016, "Pittsburgh Penguins", "Nashville Predators"),
    (2017, "Washington Capitals", "Vegas Golden Knights"), (2018, "St. Louis Blues", "Boston Bruins"),
    (2019, "Tampa Bay Lightning", "Dallas Stars"), (2020, "Tampa Bay Lightning", "Montreal Canadiens"),
    (2021, "Colorado Avalanche", "Tampa Bay Lightning"), (2022, "Vegas Golden Knights", "Florida Panthers"),
    (2023, "Florida Panthers", "Edmonton Oilers"), (2024, "Florida Panthers", "Edmonton Oilers"),
    (2025, "Carolina Hurricanes", "Vegas Golden Knights"),
]


def wiki_cup_finals():
    """[(year, champion, runner-up)] from Wikipedia's Stanley Cup champions table."""
    out = {}
    for text, names in wiki_html_rows(CUP_PAGE):
        season = SEASON_RE.search(text)
        if not season:
            continue
        teams = [n for n in names if TEAM_LINK_RE.search(n)]
        if len(teams) >= 2:
            # The page also contains footnotes and franchise-summary tables.
            # Keep the first result from the actual Finals table rather than
            # allowing a later, unrelated row to replace it.
            out.setdefault(int(season.group(1)), (teams[0], teams[1]))
    finals = sorted((y, a, b) for y, (a, b) in out.items())
    return finals if len(finals) >= 40 else CUP_FINALS_FALLBACK


def fetch_cup_history(cache, today):
    """[(year, champion, runner-up, Conn Smythe winner)] — cached, since it barely changes."""
    saved = cache.get("_cups")
    if (saved and saved.get("version") == 5 and saved.get("rows")
            and (today - date.fromisoformat(saved["day"])).days < 14):
        return [tuple(r) for r in saved["rows"]]
    finals = wiki_cup_finals()
    if len(finals) < 30:
        print("  Cup history: couldn't read Wikipedia's Stanley Cup table, so Playoff History is off for now.")
        return []
    smythe = {r[1]: r[2] for r in AWARD_HISTORY if "Conn Smythe" in r[0]}
    smythe.update(CONN_SMYTHE_BY_FINAL_YEAR)
    rows = [[y, a, b, smythe.get(y + 1, ""), CONN_SMYTHE_TEAM_BY_FINAL_YEAR.get(y + 1, "")]
            for y, a, b in finals if y >= CUPS_FIRST_YEAR]
    with_mvp = sum(1 for r in rows if r[3])
    print(f"  Cup history: {len(rows)} finals, {with_mvp} with a Conn Smythe winner"
          + ("" if with_mvp >= len(rows) * 0.6 else " (the grid will show winners and runners-up only)"))
    cache["_cups"] = {"version": 5, "day": today.isoformat(), "rows": rows}
    return [tuple(r) for r in rows]


CUPS_FIRST_YEAR = 1980     # the grid runs from 1980 to the latest final
CUPS_SECONDS = 600


def cups_puzzle(history, rnd):
    rows = [r for r in history if r[0] >= CUPS_FIRST_YEAR and r[1] and r[2]]
    if len(rows) < 40 or any(not r[3] for r in rows):
        return None
    return {"rows": [list(r) for r in rows], "mvp": True}


def wiki_award_history():
    """Trophy winners plus their team from Wikipedia's per-trophy tables."""
    rows = []
    for title in WIKI_TROPHIES:
        found = []
        for text, names in wiki_html_rows(title):
            season = SEASON_RE.search(text)
            if not season:
                continue
            team = next((abbrev_for(name) for name in names if TEAM_LINK_RE.search(name) and abbrev_for(name)), "")
            for name in names:
                if " " not in name or NOT_A_PLAYER.search(name) or re.search(r"\d", name):
                    continue
                found.append((title, int(season.group(1)), name, team))
                break
        if len(found) >= 10:
            rows += found
        else:
            print(f"  (Wikipedia: couldn't read the winners table for {title})", file=sys.stderr)
    return sorted(set(rows))


def report_trophies(rows):
    counts = {}
    for t, y, w, *_ in rows:
        counts[t] = counts.get(t, 0) + 1
    print("    " + ", ".join(f"{t.replace(' Trophy', '').replace(' Memorial', '')}: {n}"
                             for t, n in sorted(counts.items())))


def fetch_award_history(cache, today):
    """[(trophy, season start year, winner name, team)] for every winner the NHL lists."""
    saved = cache.get("_trophies")
    if (saved and saved.get("team_version") == 1
            and (today - date.fromisoformat(saved["day"])).days < 14 and saved.get("rows")):
        rows = [tuple(r) for r in saved["rows"]]
        if any("Conn Smythe" in r[0] for r in rows):
            print(f"  Award history: {len(rows)} winners saved from an earlier build")
            report_trophies(rows)
            return rows
        print("  Award history: the saved copy has no Conn Smythe winners, so it's being looked up again")
    rows, source = [], None
    for url in TROPHY_URLS:
        try:
            data = get_json(url, timeout=20)
        except Exception:
            continue
        items = data.get("data") if isinstance(data, dict) else data
        if not isinstance(items, list):
            continue
        found = []
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict):
                continue
            name = dig(item, "trophy", "trophyName", "awardName", "name")
            seasons = item.get("seasons") if isinstance(item.get("seasons"), list) else [item]
            for sn in seasons:
                if not isinstance(sn, dict):
                    continue
                season = dig(sn, "seasonId", "season", "seasonNumber")
                winner = dig(sn, "playerName", "fullName", "winner", "player")
                team = dig(sn, "teamAbbrev", "teamCode", "teamName", "team") or ""
                team = str(team).upper() if re.fullmatch(r"[A-Za-z]{2,4}", str(team)) else (abbrev_for(str(team)) or "")
                if not winner:
                    first, last = dig(sn, "firstName"), dig(sn, "lastName")
                    winner = f"{first} {last}" if first and last else None
                try:
                    year = int(str(season)[:4])
                except (TypeError, ValueError):
                    continue
                if name and winner and 1900 < year < 2100:
                    found.append((str(name), year, str(winner).strip(), team))
        if len(found) >= 200:
            rows, source = sorted(set(found)), url
            break
    if not rows:
        rows, source = wiki_award_history(), "Wikipedia"
    if rows:
        print(f"  Award history: {len(rows)} winners from {source}")
        report_trophies(rows)
        if not any("Conn Smythe" in r[0] for r in rows):
            print("    (no Conn Smythe winners yet, so this isn't saved and will be looked up again next build)")
            return rows
        cache["_trophies"] = {"team_version": 1, "day": today.isoformat(), "rows": [list(r) for r in rows]}
    else:
        print("  Award history: neither the NHL's award lists nor Wikipedia were reachable, "
              "so Trophy Case uses current players only.")
    return rows


def trophy_team_for(player, year):
    """The team a current/archived player spent most of an award season with."""
    rows = [r for r in player.get("car", []) if r[0] == year and len(r) > 2 and r[1]]
    return max(rows, key=lambda r: r[2])[1] if rows else ""


def trophy_entries(players, history=()):
    """(trophy, year, winner name, team) — historical winners with their award-season club."""
    by_name = {p["name"]: p for p in players}
    out = []
    for row in history:
        if len(row) < 3:
            continue
        t, y, w = row[:3]
        team = row[3] if len(row) > 3 else ""
        if y >= TROPHY_FIRST_YEAR and not any(skip in t for skip in TROPHY_SKIP):
            out.append((t, y, w, team or trophy_team_for(by_name.get(w, {}), y)))
    if not out:
        for p in players:
            for name, year in p.get("aw", []):
                if not any(skip in name for skip in TROPHY_SKIP):
                    out.append((name, year, p["name"], trophy_team_for(p, year)))
    return sorted(set(out))


def trophy_puzzle(players, entries, rnd):
    if len(entries) < 12:
        return None
    by_trophy = {}
    for t, y, w, team in entries:
        by_trophy.setdefault(t, []).append((y, w, team))
    rounds, used = [], set()
    for _ in range(3000):
        if len(rounds) == 20:
            return {"rounds": rounds}
        t, y, w, team = rnd.choice(entries)
        if (t, y) in used:
            continue
        # the wrong options are always other winners of the same trophy, so a Vezina round
        # never lists a skater; a trophy with too few winners is skipped instead
        all_others = [(yy, n, tm) for yy, n, tm in by_trophy[t] if n != w]
        others = [(yy, n, tm) for yy, n, tm in all_others if abs(yy - y) <= 12]
        if len({n for _, n, _ in others}) < 3:
            others = [(yy, n, tm) for yy, n, tm in all_others if abs(yy - y) <= 20]
        if len({n for _, n, _ in others}) < 3:
            others = all_others
        by_winner = {}
        for row in sorted(others, key=lambda item: abs(item[0] - y)):
            by_winner.setdefault(row[1], row)
        others = list(by_winner.values())
        if len(others) < 3:
            continue
        choices = rnd.sample(others, 3)
        a = rnd.randrange(4)
        choices.insert(a, (y, w, team))
        rounds.append({"t": t, "y": y, "names": [n for _, n, _ in choices],
                       "teams": [tm for _, _, tm in choices], "a": a})
        used.add((t, y))
    return None


def overtime_puzzle(players, entries, rnd):
    """Freeze a mixed 100-question daily board so rebuilds preserve answers."""
    if len(players) < 20:
        return None
    trophies = (trophy_puzzle(players, entries, rnd) or {}).get("rounds", [])
    rounds, seen, used = [], set(), {"kinds": set(), "players": set()}
    for _ in range(1000):
        index = len(rounds)
        if index >= 100:
            return {"rounds": rounds}
        if index % 5 == 4 and index // 5 < len(trophies):
            r = trophies[index // 5]
            q = {"q": f"Who won the {r['t']} in {r['y']}–{str(r['y'] + 1)[-2:]}?",
                 "o": r["names"], "a": r["a"], "kind": "trophy"}
        else:
            q = quiz_question(players, rnd, used)
        if not q or q["kind"] == "pastTeam" or q["q"] in seen:
            continue
        rounds.append(q)
        seen.add(q["q"])
    return None


def mroster_puzzle(players, rnd):
    rosters = {}
    for p in players:
        rosters.setdefault(p["team"], []).append(p)
    teams = sorted(t for t, r in rosters.items() if t in CURRENT_TEAMS and len(r) >= 6)
    if not teams:
        return None
    team = rnd.choice(teams)
    if len(rosters[team]) < 6:
        return None
    picks = rnd.sample(rosters[team], 6)
    return {"team": team, "ids": [p["id"] for p in picks]}


def plan_generated(days, pool, today, make, seed):
    """Day-by-day puzzles built by `make`; days after tomorrow are rebuilt if a player left."""
    lock = (today + timedelta(days=LOCK_DAYS)).isoformat()
    days = {k: v for k, v in days.items() if k <= lock or all(i in pool for i in extra_ids(v))}
    players = [pool[i] for i in sorted(pool)]
    for n in range(AHEAD + 1):
        k = (today + timedelta(days=n)).isoformat()
        if k not in days:
            puzzle = make(players, random.Random(f"{seed}-{k}"))
            if puzzle:
                days[k] = puzzle
    return dict(sorted(days.items()))


def extra_ids(v):
    if not isinstance(v, dict):
        return []
    if "ids" in v:
        return list(v["ids"])
    if "rounds" in v:                                    # two truths, trophy case, team H/L
        out = []
        for r in v["rounds"]:
            if isinstance(r, dict):
                out += [r["p"]] if "p" in r else list(r.get("ids", []))
        return out
    if "team" in v and "ids" in v:
        return list(v["ids"])
    if "id" in v:                                        # mystery season
        return [v["id"]]
    return []


def player_of(v):
    """What counts as 'the same puzzle' for no-repeat rules."""
    if isinstance(v, dict):
        return v["team"]
    return v[0] if isinstance(v, list) else v


def ids_of(v):
    """Every player a scheduled puzzle needs."""
    if isinstance(v, dict):
        return list(v.get("ids", []))
    if isinstance(v, list) and v and isinstance(v[0], dict):   # connections
        return [i for g in v for i in g["ids"]]
    return [v[0]] if isinstance(v, list) else [v]


def plan_days(days, candidates, today, seed, no_repeat=NO_REPEAT_DAYS):
    """candidates: {key: value}; values are player ids, [player id, season] for 'guess the team',
    or {team, ids} for roster recall."""
    def key(v):
        if isinstance(v, dict):
            return v["team"]
        return f"{v[0]}:{v[1]}" if isinstance(v, list) else str(v)
    lock = (today + timedelta(days=LOCK_DAYS)).isoformat()
    days = dict(days)
    # future picks (after tomorrow) are re-drawn if they're no longer possible
    for k in list(days):
        if k > lock and key(days[k]) not in candidates:
            del days[k]
        elif k > lock:
            days[k] = candidates[key(days[k])]   # refresh (e.g. a roster snapshot) until it's locked
    order = sorted(candidates)
    for i in range(AHEAD + 1):
        k = (today + timedelta(days=i)).isoformat()
        if k in days or not order:
            continue
        kd = date.fromisoformat(k)
        recent = {player_of(v) for d, v in days.items()
                  if abs((date.fromisoformat(d) - kd).days) <= no_repeat}
        choices = [c for c in order if player_of(candidates[c]) not in recent] or order
        days[k] = candidates[random.Random(f"{seed}-{k}").choice(choices)]
    return dict(sorted(days.items()))


def update_schedule(players, today):
    """Keep a fixed day-by-day list of puzzles for each game. Past days and tomorrow never change."""
    try:
        sched = json.loads(SCHEDULE.read_text(encoding="utf-8"))
    except Exception:
        sched = {}
    archive = {int(k): v for k, v in sched.get("players", {}).items()}
    pool = {p["id"]: p for p in players}
    roster_teams = {}
    for i, p in pool.items():
        roster_teams.setdefault(p["team"], []).append(i)
    games = {
        # game: (days key, start key, candidates, seed[, no-repeat days])
        "classic": ("days", "start", {str(i): i for i in pool}, "sweater"),
        "statline": ("statline_days", "statline_start",
                     {str(i): i for i, p in pool.items() if statline_ok(p)}, "sweater-sl"),
        "team": ("team_days", "team_start",
                 {f"{i}:{y}": [i, y] for i, p in pool.items() for y in team_seasons(p)}, "sweater-tt"),
        "journey": ("journey_days", "journey_start",
                    {str(i): i for i, p in pool.items() if journey_ok(p)}, "sweater-jy"),
        "blur": ("blur_days", "blur_start", {str(i): i for i, p in pool.items() if p.get("headshot")}, "sweater-bl"),
        "number": ("number_days", "number_start",
                   {str(i): i for i, p in pool.items() if (p.get("number") or 0) > 0}, "sweater-num"),
        "draft": ("draft_days", "draft_start",
                  {str(i): i for i, p in pool.items() if isinstance(p.get("draft"), list) and len(p["draft"]) >= 2},
                  "sweater-dr"),
        "map": ("map_days", "map_start", {str(i): i for i, p in pool.items() if p.get("bp")}, "sweater-map"),
        "zam": ("zam_days", "zam_start", {str(i): i for i, p in pool.items() if p.get("headshot")}, "sweater-zam"),
        "roster": ("roster_days", "roster_start",
                   {t: {"team": t, "ids": sorted(ids)} for t, ids in roster_teams.items() if len(ids) >= 10},
                   "sweater-ro", 20),
    }
    first = "0000-00-00"   # every past day, for the archive
    last = (today + timedelta(days=EMBED_AHEAD)).isoformat()
    result, new = {}, {}
    for g, (dk, sk, cands, seed, *rest) in games.items():
        days = plan_days(sched.get(dk, {}), cands, today, seed, *rest)
        start = sched.get(sk) or (today.isoformat() if days else "")
        new[dk], new[sk] = days, start
        result[g] = (start, {k: v for k, v in days.items() if first <= k <= last})

    # remember every scheduled player, so a past answer still works after he leaves the league
    award_history = AWARD_HISTORY
    rules = puck_rules([pool[i] for i in sorted(pool)])
    extra_games = {
        "rank": (lambda pl, rnd: rank_puzzle(pl, rnd), "sweater-rank"),
        "puck": (lambda pl, rnd: puck_puzzle(pl, rules, rnd), "sweater-puck"),
        "shoot": (lambda pl, rnd: shootout_puzzle(pl, rnd), "sweater-shoot"),
        "goalie": (lambda pl, rnd: {"seed": rnd.getrandbits(32)}, "sweater-goalie"),
        "overtime": (lambda pl, rnd: overtime_puzzle(pl, trophy_entries(pl, award_history), rnd), "sweater-overtime"),
        "truths": (lambda pl, rnd: truths_puzzle(pl, rnd), "sweater-truths"),
        "hlt": (lambda pl, rnd: hlt_puzzle(pl, rnd), "sweater-hlt"),
        "season": (lambda pl, rnd: season_puzzle(pl, rnd), "sweater-season"),
        "playoff": (lambda pl, rnd: playoff_puzzle(pl, rnd), "sweater-playoff"),
        "trophy": (lambda pl, rnd: trophy_puzzle(pl, trophy_entries(pl, award_history), rnd), "sweater-trophy"),
        "mroster": (lambda pl, rnd: mroster_puzzle(pl, rnd), "sweater-mroster"),
        "cups": (lambda pl, rnd: cups_puzzle(CUP_HISTORY, rnd), "sweater-cups"),
    }
    for g, (make, seed) in extra_games.items():
        days = plan_generated(sched.get(f"{g}_days", {}), pool, today, make, seed)
        new[f"{g}_days"] = days
        new[f"{g}_start"] = sched.get(f"{g}_start") or (today.isoformat() if days else "")
        result[g] = (new[f"{g}_start"], {k: v for k, v in days.items() if first <= k <= last})
        for v in days.values():
            for i in extra_ids(v):
                if i in pool:
                    archive[i] = pool[i]

    conn_days = plan_conn(sched.get("conn_days", {}), pool, today)
    new["conn_days"] = conn_days
    new["conn_start"] = sched.get("conn_start") or (today.isoformat() if conn_days else "")
    result["conn"] = (new["conn_start"], {k: v for k, v in conn_days.items() if first <= k <= last})
    for v in conn_days.values():
        for i in ids_of(v):
            if i in pool:
                archive[i] = pool[i]

    hl_days = plan_hl(sched.get("hl_days", {}), pool, today)
    new["hl_days"] = hl_days
    new["hl_start"] = sched.get("hl_start") or (today.isoformat() if hl_days else "")
    hl_window = {k: v for k, v in hl_days.items() if first <= k <= last}
    result["hl"] = (new["hl_start"], hl_window)

    for g, (dk, *_) in games.items():
        for v in new[dk].values():
            for i in ids_of(v):
                if i in pool:
                    archive[i] = pool[i]
    for day in hl_days.values():
        for seq in day.values():
            for i in seq:
                if i in pool:
                    archive[i] = pool[i]
    new["players"] = {str(k): v for k, v in sorted(archive.items())}
    SCHEDULE.write_text(json.dumps(new, ensure_ascii=False, indent=1), encoding="utf-8")

    needed = {i for g, (_, window) in result.items() if g != "hl" for v in window.values() for i in ids_of(v)}
    needed |= {i for day in hl_window.values() for seq in day.values() for i in seq}
    extras = [archive[i] for i in sorted(needed) if i not in pool and i in archive]
    return result, extras


def abbrev_for(name):
    for nick, ab in NICKNAMES:
        if nick.lower() in name.lower():
            return ab
    return None


def career_data(pid):
    """Every NHL team a player has appeared for, plus regular-season stats by season and team.
    Rows are [season start year, team, GP, G, A, PTS] (goalies: [.., GP, W, GAA, SV%])."""
    data = get_json(f"https://api-web.nhle.com/v1/player/{pid}/landing")
    goalie = data.get("position") == "G"
    teams, rows, playoffs = [], [], []
    for row in data.get("seasonTotals", []):
        if row.get("leagueAbbrev") != "NHL":
            continue
        ab = row.get("teamAbbrev")
        if isinstance(ab, dict):
            ab = ab.get("default")
        if not ab:
            name = (row.get("teamName") or {}).get("default", "")
            if isinstance(row.get("teamCommonName"), dict):
                name += " " + row["teamCommonName"].get("default", "")
            ab = abbrev_for(name)
        if ab and ab not in teams:
            teams.append(ab)
        kind = row.get("gameTypeId", 2)
        if kind not in (2, 3):
            continue
        try:
            year = int(str(row.get("season"))[:4])
        except ValueError:
            continue
        gp = row.get("gamesPlayed") or 0
        if gp <= 0:
            continue
        if goalie:
            stats = [row.get("wins") or 0, round(float(row.get("goalsAgainstAvg") or 0), 2),
                     round(float(row.get("savePctg") or 0), 3), row.get("shutouts") or 0]
        else:
            stats = [row.get("goals") or 0, row.get("assists") or 0, row.get("points") or 0,
                     row.get("pim") or row.get("penaltyMinutes") or 0, row.get("plusMinus") or 0]
        (rows if kind == 2 else playoffs).append([year, ab or "", gp] + stats)
    rows.sort(key=lambda r: r[0])
    playoffs.sort(key=lambda r: r[0])
    awards = []
    for a in data.get("awards") or []:
        name = (a.get("trophy") or {}).get("default")
        for season in a.get("seasons") or []:
            try:
                awards.append([name, int(str(season.get("seasonId"))[:4])])
            except (ValueError, TypeError):
                continue  # stable: keeps trade order within a season
    d = data.get("draftDetails") or {}
    draft = [d.get("year"), d.get("round"), d.get("overallPick") or 0, d.get("teamAbbrev") or ""] \
        if d.get("year") and d.get("round") else 0   # 0 = undrafted
    return teams, rows, draft, playoffs, [a for a in awards if a[0]]


ISO2 = {"CAN": "CA", "USA": "US", "SWE": "SE", "FIN": "FI", "CZE": "CZ", "RUS": "RU", "SVK": "SK", "CHE": "CH",
        "DEU": "DE", "AUT": "AT", "DNK": "DK", "NOR": "NO", "LVA": "LV", "FRA": "FR", "GBR": "GB", "SVN": "SI",
        "BLR": "BY", "UKR": "UA", "KAZ": "KZ", "AUS": "AU", "NLD": "NL", "POL": "PL", "ITA": "IT", "JPN": "JP",
        "KOR": "KR", "HUN": "HU", "BRA": "BR", "JAM": "JM", "NGA": "NG", "ZAF": "ZA", "LTU": "LT", "EST": "EE",
        "BEL": "BE", "CHN": "CN", "TWN": "TW", "HRV": "HR", "SRB": "RS", "BGR": "BG", "ROU": "RO", "ISR": "IL",
        "IRL": "IE", "MEX": "MX", "VEN": "VE", "KEN": "KE", "GHA": "GH", "HTI": "HT", "THA": "TH"}
REGIONS = {
    "AB": "Alberta", "BC": "British Columbia", "MB": "Manitoba", "NB": "New Brunswick", "NL": "Newfoundland and Labrador",
    "NS": "Nova Scotia", "NT": "Northwest Territories", "NU": "Nunavut", "ON": "Ontario", "PE": "Prince Edward Island",
    "QC": "Quebec", "SK": "Saskatchewan", "YT": "Yukon",
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado",
    "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii",
    "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana",
    "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey",
    "NM": "New Mexico", "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming"}
COUNTRY_LABELS = {"CAN": "Canada", "USA": "USA", "SWE": "Sweden", "FIN": "Finland", "CZE": "Czechia", "RUS": "Russia",
                  "SVK": "Slovakia", "CHE": "Switzerland", "DEU": "Germany", "AUT": "Austria", "DNK": "Denmark",
                  "NOR": "Norway", "LVA": "Latvia", "FRA": "France", "GBR": "Great Britain", "SVN": "Slovenia",
                  "BLR": "Belarus", "UKR": "Ukraine", "KAZ": "Kazakhstan", "AUS": "Australia", "NLD": "Netherlands",
                  "POL": "Poland", "ITA": "Italy", "JPN": "Japan", "KOR": "South Korea", "HUN": "Hungary"}
GEO_BUDGET = 4 * 60        # seconds
CAREER_BUDGET = 8 * 60     # seconds
GEO_URL = "https://geocoding-api.open-meteo.com/v1/search?name={name}&count=10&language=en&format=json{cc}"


def add_birthplaces(players, cache, today):
    """Look up birthplace coordinates (Open-Meteo geocoding), saved in the career cache under "_geo"."""
    geo = cache.setdefault("_geo", {})
    todo = {}
    for p in players:
        if not p.get("bc"):
            continue
        key = f'{p["bc"]}|{p.get("bs", "")}|{p["nation"]}'
        hit = geo.get(key)
        stale = hit is None or (hit.get("at") is None and (today - date.fromisoformat(hit["day"])).days >= 30)
        if stale:
            todo[key] = (p["bc"], p.get("bs", ""), p["nation"])
    if todo:
        print(f"\n{stamp()} Looking up {len(todo)} birthplaces (up to {GEO_BUDGET // 60} minutes)...")

    def lookup(item):
        key, (city, region, nation) = item
        cc = f"&countryCode={ISO2[nation]}" if nation in ISO2 else ""
        results = get_json(GEO_URL.format(name=urllib.parse.quote(city), cc=cc), timeout=8).get("results") or []
        if nation in ISO2:
            results = [r for r in results if (r.get("country_code") or "").upper() == ISO2[nation]]
        want = REGIONS.get(region, region).lower()
        best = next((r for r in results if want and (r.get("admin1") or "").lower() == want), None)
        if not best and results:
            best = max(results, key=lambda r: r.get("population") or 0)
        return key, ([round(best["latitude"], 2), round(best["longitude"], 2)] if best else None)

    started, done, errors = time.time(), 0, 0
    items = sorted(todo.items())
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(lookup, it) for it in items]
        try:
            for f in as_completed(futures, timeout=GEO_BUDGET):
                try:
                    key, at = f.result()
                    geo[key] = {"day": today.isoformat(), "at": at}
                except Exception:
                    errors += 1
                done += 1
                if done == 20 and errors == 20:
                    print("  The place-name service isn't responding; skipping birthplaces this time.")
                    break
                if done % 50 == 0 or done == len(items):
                    print(f"  {done}/{len(items)}")
        except FuturesTimeout:
            print(f"  Time's up after {done} lookups; the rest will be looked up in the next build.")
        for f in futures:
            f.cancel()
    if errors:
        print(f"  {errors} lookups failed; they'll be retried in the next build.")
    found = 0
    for p in players:
        hit = geo.get(f'{p.get("bc")}|{p.get("bs", "")}|{p["nation"]}') if p.get("bc") else None
        if hit and hit.get("at"):
            where = [p["bc"]] + ([p["bs"]] if p.get("bs") and p["nation"] in ("CAN", "USA") else []) \
                + [COUNTRY_LABELS.get(p["nation"], p["nation"])]
            p["bp"] = hit["at"] + [", ".join(where)]
            found += 1
    print(f"  {stamp()} Birthplaces found for {found} of {len(players)} players.")


def add_career_teams(players):
    try:
        cache = json.loads(CACHE.read_text(encoding="utf-8"))
    except Exception:
        cache = {}
    today = date.today()

    def fresh(pid):
        c = cache.get(str(pid))
        return bool(c) and c.get("v") == 6 and (today - date.fromisoformat(c["day"])).days < CACHE_DAYS

    todo = [p["id"] for p in players if not fresh(p["id"])]
    print(f"\n{stamp()} Loading career history and stats ({len(players) - len(todo)} saved, {len(todo)} to download, up to {CAREER_BUDGET // 60} minutes)...")

    def job(pid):
        try:
            return pid, career_data(pid)
        except Exception:
            return pid, None

    failed, i = 0, 0
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(job, pid) for pid in todo]
        try:
            for f in as_completed(futures, timeout=CAREER_BUDGET):
                pid, result = f.result()
                i += 1
                if result is None:
                    failed += 1
                else:
                    cache[str(pid)] = {"day": today.isoformat(), "v": 6, "teams": result[0], "car": result[1],
                                   "draft": result[2], "po": result[3], "aw": result[4]}
                if i % 50 == 0 or i == len(todo):
                    print(f"  {i}/{len(todo)}")
        except FuturesTimeout:
            print(f"  Time's up after {i} downloads; the rest will be downloaded in the next build (saved data is used for now).")
        for f in futures:
            f.cancel()
    if failed:
        print(f"  {failed} players' history couldn't be loaded (no yellow hints or stats games for them).")
    add_birthplaces(players, cache, today)
    global AWARD_HISTORY
    AWARD_HISTORY = fetch_award_history(cache, today)
    global CUP_HISTORY
    CUP_HISTORY = fetch_cup_history(cache, today)
    try:
        CACHE.write_text(json.dumps(cache), encoding="utf-8")
    except Exception:
        pass

    for p in players:
        entry = cache.get(str(p["id"])) or {}
        p["past"] = [t for t in entry.get("teams", []) if t != p["team"]]
        if entry.get("car"):
            p["car"] = entry["car"]
        if "draft" in entry:
            p["draft"] = entry["draft"]
        if entry.get("po"):
            p["po"] = entry["po"]
        if entry.get("aw"):
            p["aw"] = entry["aw"]
    print(f"  Stats games: {sum(map(statline_ok, players))} players for 'guess the player', "
          f"{sum(len(team_seasons(p)) > 0 for p in players)} for 'guess the team', "
          f"{sum(map(hl_ok, players))} for 'higher or lower', {sum(map(journey_ok, players))} for 'journey', "
          f"{sum(isinstance(p.get('draft'), list) for p in players)} with draft info, "
          f"{sum(1 for p in players if p.get('po'))} with playoff stats, {sum(1 for p in players if p.get('aw'))} with trophies.")


def recent_games():
    """NHL regular-season games per player: last season + this season."""
    today = date.today()
    start = today.year if today.month >= 7 else today.year - 1
    seasons = [f"{start - 1}{start}", f"{start}{start + 1}"]
    games, failures = {}, 0
    for season in seasons:
        for kind in ("skater", "goalie"):
            rows = None
            for attempt in range(3):
                try:
                    rows = get_json(STATS.format(kind=kind, season=season), timeout=25).get("data", [])
                    break
                except Exception as e:
                    print(f"  (couldn't load {kind} stats for {season}, try {attempt + 1}: {e})", file=sys.stderr)
                    time.sleep(3)
            if rows is None:
                failures += 1
                continue
            for r in rows:
                pid = r.get("playerId")
                games[pid] = games.get(pid, 0) + (r.get("gamesPlayed") or 0)
    # a half-loaded list would wrongly cut most of the league, so treat it as no list at all
    if failures or len(games) < GAMES_LIST_MIN:
        print(f"  Games-played list looks incomplete ({len(games)} players, {failures} requests failed), "
              f"so every rostered player is included this time.")
        return {}
    return games


def players_from(team, roster, include_all):
    out = []
    for group in ("forwards", "defensemen", "goalies"):
        for p in roster.get(group, []):
            num = p.get("sweaterNumber")
            if num is None and not include_all:
                continue
            out.append({
                "id": p["id"],
                "name": f'{p["firstName"]["default"]} {p["lastName"]["default"]}',
                "team": team,
                "pos": p.get("positionCode", "?"),
                "shoots": p.get("shootsCatches", "?"),
                "birth": p.get("birthDate", "2000-01-01"),
                "nation": p.get("birthCountry", "?"),
                "number": num if num is not None else 0,
                "headshot": p.get("headshot", ""),
                "ht": p.get("heightInInches") or 0,
                "bc": (p.get("birthCity") or {}).get("default", ""),
                "bs": (p.get("birthStateProvince") or {}).get("default", ""),
                "wt": p.get("weightInPounds") or 0,
            })
    return out


STARTED = time.time()


def stamp():
    return f"[{int(time.time() - STARTED) // 60}m{int(time.time() - STARTED) % 60:02d}s]"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="include players without a sweater number")
    ap.add_argument("--min-games", type=int, default=10,
                    help="NHL games (last season + this season) needed to be included (default 10)")
    ap.add_argument("--quiet", action="store_true",
                    help="for scheduled updates: don't open the browser or wait for Enter")
    ap.add_argument("--no-career", action="store_true",
                    help="skip career history (no yellow team hints, faster)")
    ap.add_argument("--out", default=str(HERE / "sweater.html"),
                    help="where to write the game (use site/index.html for the website)")
    ap.add_argument("--api-url", default="",
                    help="leaderboard server address, e.g. https://api.sweater.win (leave empty to hide the leaderboard)")
    ap.add_argument("--site-url", default="",
                    help="your website address, e.g. https://playsweater.com/ (used in share text and link previews)")
    args = ap.parse_args()

    games = {}
    if not args.all and args.min_games > 0:
        print(f"{stamp()} Loading NHL games played...")
        games = recent_games()
        if not games:
            print("  Couldn't load games played - skipping that filter.\n")
        else:
            print(f"  Found {len(games)} players with NHL games.\n")

    players, seen = [], set()
    for team in TEAMS:
        try:
            batch = players_from(team, fetch(team), args.all)
            if games:
                batch = [p for p in batch if games.get(p["id"], 0) >= args.min_games]
        except Exception as e:  # keep going if one team fails
            print(f"  {team}: failed ({e})", file=sys.stderr)
            continue
        for p in batch:
            if p["id"] not in seen:
                seen.add(p["id"])
                players.append(p)
        print(f"  {stamp()} {team}: {len(batch)} players")
        time.sleep(0.3)  # be polite to the NHL API

    if not players:
        sys.exit("No players fetched - check your internet connection.")

    if len(players) < PLAYER_POOL_MIN and not args.all:
        sys.exit(f"Only {len(players)} players came back, which is far fewer than a full league. "
                 "Nothing was changed; the next build will try again.")

    if not args.no_career:
        add_career_teams(players)

    today = eastern_today()
    print(f"\n{stamp()} Planning daily puzzles...")
    games, extras = update_schedule(players, today)
    embedded = players + extras
    for g, (start, window) in games.items():
        print(f"Daily {g}: {len(window)} days in this page" + (f", Daily #1 was {start}." if start else " (not available)."))

    site = args.site_url.strip()
    if site and not site.endswith("/"):
        site += "/"
    esc = lambda obj: json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")
    fills = {
        "/*__PLAYERS__*/[]": esc(embedded),
        "/*__DAILY_ALL__*/{}": esc({g: w for g, (_, w) in games.items() if g != "hl"}),
        "/*__START_ALL__*/{}": esc({g: st for g, (st, _) in games.items()}),
        "/*__DAILY_HL__*/{}": esc(games["hl"][1]),
        "/*__CUPS__*/[]": esc([list(r) for r in CUP_HISTORY]),
        "/*__TROPHIES__*/[]": esc([list(r) for r in trophy_entries(embedded, AWARD_HISTORY)]),
        "/*__SITE__*/": site,
        "/*__API__*/": args.api_url.strip(),
        "/*__BUILT__*/": f"{today.isoformat()} · builder v{VERSION}",
    }
    html = TEMPLATE
    for placeholder, value in fills.items():
        html = html.replace(placeholder, value)
    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    og = HERE / "sweater-trivia-preview.png"
    if og.exists() and out.parent != HERE:
        shutil.copy(og, out.parent / "sweater-trivia-preview.png")
    # Companion files make a deployed HTTPS build installable as a lightweight
    # phone app. They live next to the generated HTML, so publishing is just a
    # matter of uploading the build folder rather than hand-editing a host.
    pwa_icon = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><rect width="512" height="512" rx="112" fill="#111113"/><path d="M82 252h348M112 174h288M112 330h288" stroke="#fff" stroke-opacity=".16" stroke-width="10"/><circle cx="256" cy="256" r="118" fill="none" stroke="#fff" stroke-opacity=".2" stroke-width="12"/><circle cx="256" cy="256" r="55" fill="#fff"/><circle cx="238" cy="238" r="13" fill="#111113"/><circle cx="274" cy="274" r="13" fill="#111113"/></svg>'''
    manifest = {
        "name": "Sweater · Daily NHL Trivia",
        "short_name": "Sweater",
        "start_url": "./",
        "display": "standalone",
        "background_color": "#111113",
        "theme_color": "#111113",
        "description": "Daily NHL trivia, player guessing games, Trophy Case and Playoff History.",
        "icons": [{"src": "sweater-icon.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "any maskable"}],
    }
    service_worker = f'''const CACHE = "sweater-shell-{today.isoformat()}";
const CORE = ["./", "./sweater.webmanifest", "./sweater-icon.svg", "./sweater-trivia-preview.png"];
self.addEventListener("install", event => event.waitUntil(
  caches.open(CACHE).then(cache => Promise.all(CORE.map(url => cache.add(url).catch(() => undefined)))).then(() => self.skipWaiting())
));
self.addEventListener("activate", event => event.waitUntil(
  caches.keys().then(keys => Promise.all(keys.filter(key => key.startsWith("sweater-shell-") && key !== CACHE).map(key => caches.delete(key)))).then(() => self.clients.claim())
));
self.addEventListener("fetch", event => {{
  if (event.request.method !== "GET" || new URL(event.request.url).origin !== location.origin) return;
  event.respondWith(fetch(event.request).then(response => {{
    const copy = response.clone(); caches.open(CACHE).then(cache => cache.put(event.request, copy)); return response;
  }}).catch(() => caches.match(event.request)));
}});\n'''
    (out.parent / "sweater.webmanifest").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (out.parent / "sweater-icon.svg").write_text(pwa_icon, encoding="utf-8")
    (out.parent / "sw.js").write_text(service_worker, encoding="utf-8")
    # double-check the page that was written
    check = out.read_text(encoding="utf-8")
    if "/*__" in check or check.count('"headshot"') != len(embedded):
        sys.exit(f"The game file was written but the player data didn't go in correctly ({check.count(chr(34) + 'headshot' + chr(34))} of {len(embedded)}).")
    print("\nDone! Built the game with", len(players), "players.")
    print("Your game file is:\n  ", out)
    if not args.quiet:
        print("Opening it in your browser...")
        webbrowser.open(out.as_uri())


if __name__ == "__main__":
    # show progress in build logs right away (Python holds output back when it isn't a window)
    try:
        sys.stdout.reconfigure(line_buffering=True)
        sys.stderr.reconfigure(line_buffering=True)
    except Exception:
        pass
    print(f"Building Sweater (builder version {VERSION}) from:\n   {Path(__file__).resolve()}\n")
    failed = False
    try:
        main()
    except SystemExit as e:
        if e.code not in (None, 0):
            failed = True
            print(f"\nERROR: {e.code}")
    except Exception:
        failed = True
        print("\nSomething went wrong:\n")
        traceback.print_exc()
    # keep the window open when the script is double-clicked
    if "--quiet" not in sys.argv:
        input("\nPress Enter to close this window...")
    sys.exit(1 if failed else 0)
