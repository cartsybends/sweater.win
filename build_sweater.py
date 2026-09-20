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
VERSION = "58 · Capital Label Fade"


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
  .mapsvg .land { fill: var(--land); stroke: var(--coast); stroke-width: .15; }
  .mapsvg .borders { fill: none; stroke: var(--coast); stroke-width: .12; }
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
        <g transform="scale(0.72,1)"><path class="land" d="M52.5,-41.8L52.6,-42.8L51.3,-43.2L50.8,-44.2L50.4,-44.6L51.5,-44.5L51.1,-44.8L51.4,-45.4L53.2,-45.3L52.8,-45.6L53.1,-46.2L52.9,-47L52.1,-46.8L51.2,-47.1L49.2,-46.3L48.3,-45.8L47.5,-45.6L46.8,-44.7L47.4,-44L47.5,-43L48.6,-41.8L49.2,-41L50.4,-40.3L49.6,-40.2L48.9,-38.4L49.1,-37.7L50.1,-37.4L51.1,-36.7L52.2,-36.6L54,-36.8L53.9,-37.3L53.9,-38.9L53.2,-39.3L53.5,-39.9L52.9,-39.9L52.9,-41L53.8,-40.7L54.7,-40.9L53.8,-42.1L53,-42L52.9,-41.2ZM-180,-69L-180,-69L-175.3,-67.7L-174.8,-67.3L-174.9,-66.6L-174.4,-66.3L-174,-66.8L-174.4,-67.1L-171.8,-66.9L-170.2,-66.2L-170.7,-65.6L-172.2,-65.5L-172.2,-65L-173,-64.9L-173,-64.3L-175.9,-65L-176.1,-65.5L-177.1,-65.6L-178.3,-65.5L-179.1,-66.3L-179.8,-66L-179.4,-65.5L-180,-65.1L-180,-65.1L-180,-69ZM180,-65.1L179.8,-65L178.5,-64.6L176.1,-65L176.7,-64.6L177.4,-64.8L177.4,-64.4L178.2,-64.4L179.6,-62.7L179.1,-62.3L177.3,-62.6L173.6,-61.7L172.4,-61.1L170.6,-60.4L170.4,-60L169.2,-60.6L168.1,-60.6L167,-60.3L166.3,-59.9L166.4,-60.5L165.1,-60.1L163.4,-59.8L163.3,-59.3L162.1,-58.4L162,-58.1L162.5,-57.8L163.2,-57.8L162.8,-57.4L162.8,-56.8L163.3,-56.2L162.1,-56.1L161.7,-55.4L162.1,-54.8L160.8,-54.5L159.8,-53.8L160,-53.1L159.6,-53.2L158.6,-52.9L158.1,-51.8L156.7,-51L156.4,-52.5L156.1,-53L155.6,-55.3L156,-56.7L157,-57.5L156.8,-57.7L158.2,-58L159,-58.4L159.8,-59.1L161.8,-60.2L162,-60.4L163.7,-60.9L164.2,-62.3L165.4,-62.5L164.3,-62.7L163.3,-62.6L163,-61.8L162.4,-61.7L160.8,-60.8L159.8,-61L160.3,-61.8L159.1,-61.9L157.5,-61.8L155.7,-60.7L155,-60.4L154.1,-59.5L155.2,-59.2L154,-59.1L153.4,-59.2L152.9,-58.9L151.3,-58.9L151.1,-59.1L152.3,-59.2L151.5,-59.5L149.6,-59.8L147.5,-59.3L146.4,-59.4L143.2,-59.4L142,-59L140,-57.7L138.7,-57L137.7,-56.1L135.3,-54.9L135.9,-54.6L136.8,-54.6L136.7,-53.8L137.1,-54.1L137.8,-53.9L137.2,-53.6L138.6,-53.8L138.7,-54.3L139.7,-54.3L141.4,-53.2L141.2,-52.4L141.5,-52.2L140.7,-51.2L140.5,-50.5L140.5,-49.6L140.2,-48.5L138.6,-47.1L137.7,-45.8L135.9,-44.4L135.1,-43.5L133.2,-42.7L132.3,-42.9L132.3,-43.3L131.8,-43.3L130.7,-42.3L129.8,-41.7L129.7,-40.9L128.3,-40L127.6,-39.8L127.4,-39.2L128.4,-38.6L129.3,-37.3L129.6,-36.1L129.2,-35.2L128.4,-34.9L127.7,-35L126.5,-34.4L126.3,-35.2L126.7,-35.8L126.5,-36.7L126.6,-37.8L125.8,-38L125.4,-37.7L124.7,-38.1L125.3,-38.7L125.4,-39.5L124.4,-40L123,-39.7L121.7,-38.9L121.1,-38.9L121.8,-39.4L121.3,-39.4L122.3,-40.5L121.2,-40.9L120.5,-40.2L119.6,-39.9L118.9,-39.2L117.8,-39.1L117.6,-38.6L118,-38.2L118.9,-38L119,-37.3L119.5,-37.1L120.8,-37.8L121.6,-37.5L122.6,-37.4L122.5,-36.9L121.9,-37L121,-36.6L120.7,-36.2L119.4,-35.3L119.2,-34.7L120.3,-34.3L120.9,-33L121.9,-31.7L120.7,-32L121.7,-31.3L121.5,-30.8L120.6,-30.1L121.2,-30.3L122.1,-29.9L121.9,-29.1L121.1,-28.3L119.9,-26.3L119.6,-25.4L119.1,-25.4L118.6,-24.6L116.6,-23.4L116.5,-22.9L115.2,-22.8L114.3,-22.5L114,-22.5L113.6,-22.9L113.5,-22.2L113.5,-22.2L112.3,-21.7L110.4,-21.3L110.2,-20.9L110.5,-20.5L110.1,-20.3L109.7,-21.1L109.9,-21.5L109.1,-21.4L108.5,-21.7L108,-21.5L107.2,-20.9L106.7,-21L106.5,-20.3L106,-19.9L105.6,-19L106.5,-17.9L107.2,-16.9L108,-16.3L108.8,-15.4L109.3,-13.9L109.4,-12.6L109.2,-12.6L109,-11.3L106.8,-10.1L106.4,-9.6L104.8,-8.6L104.8,-9.6L105.1,-9.9L104.4,-10.4L103.2,-10.9L102.9,-11.7L101.7,-12.7L100.9,-12.7L101,-13.4L100,-13.4L100,-12.2L99.2,-10.3L99.4,-9.2L99.7,-9.3L100.3,-8.3L100.4,-7.2L101.5,-6.9L102.1,-6.2L103,-5.5L103.4,-4.9L103.4,-2.9L103.8,-2.6L104.3,-1.4L103.4,-1.5L101.3,-2.9L101.3,-3.3L100.7,-4L100.1,-6.4L99,-7.9L98.2,-8.5L98.7,-10.2L98.5,-10.7L98.7,-11.6L98.6,-13.2L97.8,-14.9L97.7,-16.6L97.4,-16.5L97,-17.3L96.6,-16.6L94.7,-15.9L94.7,-16.4L94.2,-16L94.6,-17.6L94.1,-18.8L93.5,-19.4L94,-19.4L93,-20.1L92.3,-20.8L91.5,-22.9L90.9,-22.6L90.6,-23.1L90.6,-22.3L89.4,-21.7L89.1,-22.1L89.1,-21.7L87.7,-21.7L86.9,-21.2L87,-20.7L86.3,-19.9L85.2,-19.5L84.1,-18.3L82.3,-16.9L82.3,-16.6L81.3,-16.3L81,-15.8L80.3,-15.7L80.1,-15.1L80.3,-13.4L79.9,-12L79.8,-10.3L79.4,-10.3L79,-9.3L78.2,-8.9L78.1,-8.4L77.5,-8.1L77,-8.4L76.3,-9.5L76.3,-9.9L75.7,-11.4L75.2,-12.1L74.4,-14.5L73.5,-16.1L72.7,-19.8L72.9,-20.6L72.3,-22.2L72,-21.2L71,-20.7L70.5,-20.8L69,-22.2L70.2,-22.6L70.4,-23L69.7,-22.8L68.6,-23.2L68.2,-23.9L67.7,-23.8L67.2,-24.8L66.7,-24.9L66.4,-25.6L64.7,-25.2L61.6,-25.2L59,-25.4L57.3,-25.8L57,-26.9L56.4,-27.2L54.9,-26.6L53.7,-26.7L52.5,-27.6L51.3,-28.1L50.9,-29.1L50.1,-30.2L49.6,-30L49.1,-30.3L48.5,-30L48,-30L48.4,-28.5L48.8,-27.7L50,-26.8L50,-26.1L50.8,-24.8L50.8,-25.4L51.3,-26.2L51.6,-25.1L51.3,-24.6L51.6,-24.3L51.9,-24L52.6,-24.2L53.9,-24.1L56.1,-26.1L56.3,-25.7L56.4,-25L57.2,-23.9L58.6,-23.6L59.8,-22.2L58.5,-20.4L58.1,-20.6L57.7,-19.6L57.8,-19L56.7,-18.6L56.3,-18L55.5,-17.8L55.1,-17L54.1,-17L53.1,-16.6L52.3,-16.3L52.2,-15.7L51.6,-15.3L49.4,-14.6L48.7,-14.1L48,-14L47.4,-13.7L45.7,-13.3L45,-12.8L43.9,-12.6L43.5,-12.8L42.7,-15.7L42.8,-16.4L42.3,-17.4L41.8,-17.9L40.8,-19.8L39.6,-20.5L39.1,-21.3L39,-22.8L38.3,-23.9L37.5,-24.3L37.2,-25.3L35.2,-28L34.6,-28.1L35,-29.4L35,-29.6L34.9,-29.5L34.2,-27.8L33.2,-28.6L32.6,-30L32.4,-29.6L32.9,-28.6L33.5,-27.9L34,-26.6L35.5,-23.9L35.7,-22.9L36.9,-22L37.2,-21.2L37.2,-19.6L37.5,-18.8L38.6,-18L38.9,-17.4L39.3,-15.9L39.8,-15.1L41.2,-14.6L42.4,-13.2L43.1,-12.7L43.4,-12.2L42.6,-11.6L43.2,-11.5L44.4,-10.4L44.9,-10.4L45.8,-10.8L46.6,-10.7L47.4,-11.2L48.9,-11.3L50.1,-11.5L50.8,-12L51.3,-11.8L51.1,-10.7L50.8,-9.4L49.3,-7L49,-6.2L48,-4.5L46,-2.5L44.3,-1.4L43.5,-0.6L42,1L41.5,1.7L40.2,2.7L40.1,3.3L39.2,4.7L38.8,5.9L38.9,6.3L39.5,7.1L39.3,7.5L39.3,8.4L39.8,9.9L40.5,10.5L40.4,11.3L40.6,12.6L40.6,14.5L40.6,15.5L39.8,16.4L39.1,17L38.1,17.2L37.2,17.7L36.3,18.8L34.9,19.8L34.7,20.4L35,20.8L35.6,23L35.2,24.5L33.3,25.3L32.6,26L32.9,26.9L32.3,28.6L31.3,29.4L30.3,31L28.9,32.3L27.9,33.1L26.4,33.8L24.8,34.2L23.6,34L22.2,34.1L21.8,34.4L20.5,34.5L19.6,34.8L18.5,33.9L17.9,32.8L18.3,32.7L18.2,31.7L17.7,31L17,29.4L16.4,28.6L16.4,28.6L15.3,27.4L15,26.3L14.8,25L14.5,24.2L14.3,22.2L13.5,20.9L12.5,18.9L11.8,18L11.7,17.3L11.8,15.8L12,15.6L12.6,13.4L13.4,12.5L13.8,11.8L13.8,11.1L13,9L13.4,8.4L12.3,6.1L13.1,5.9L12.2,5.8L12,5L11.1,3.9L9.3,1.9L8.8,0.7L9.3,0.4L9.6,-1L9.4,-1.1L9.8,-2.3L9.9,-3.1L9.6,-3.8L9,-4.1L8.6,-4.8L7.5,-4.7L6.1,-4.3L5.6,-4.6L5.4,-5.4L4.9,-6L4.1,-6.4L2.7,-6.4L1.6,-6.2L1.2,-6.1L-2,-4.8L-3.1,-5.1L-3.1,-5.1L-3,-5.1L-4,-5.2L-5.6,-5.1L-7.5,-4.4L-9.1,-5.1L-10.3,-6.1L-11.5,-6.9L-12.5,-7.4L-13.1,-8.2L-13.3,-9L-13.7,-9.9L-14.4,-10.2L-15,-10.9L-15.4,-11.2L-15.4,-11.9L-15.8,-11.8L-16.7,-12.4L-16.8,-13.1L-16.6,-13.6L-17.2,-14.6L-16.5,-15.8L-16.5,-16.6L-16.1,-17.5L-16.1,-18.5L-16.5,-19.4L-16.2,-20.2L-16.9,-21.1L-17,-20.8L-17,-21.4L-16.9,-21.9L-16.4,-22.6L-15.9,-23.8L-15,-24.5L-14.4,-26.3L-13.6,-26.7L-12.9,-27.9L-11.4,-28.4L-10.5,-29.1L-9.7,-30.1L-9.8,-31.4L-9.2,-32.6L-8.6,-33.2L-6.9,-34L-5.9,-35.8L-5.3,-35.7L-4.8,-35.3L-2.2,-35.1L-1.9,-35.1L-0.4,-35.9L0,-35.9L1.3,-36.5L2.6,-36.6L3.8,-36.9L4.8,-36.9L5.4,-36.7L6.5,-37.1L7.9,-36.9L8.6,-36.9L9.7,-37.3L10.4,-36.7L11.1,-36.9L10.5,-36.3L11.1,-35.2L10.1,-34.2L10.2,-33.8L11.1,-33.6L11.5,-33.2L12.3,-32.9L13.3,-32.9L15.2,-32.4L15.5,-31.7L16.1,-31.3L17.4,-31.1L18.9,-30.3L19.7,-30.5L20.2,-31.1L19.9,-31.8L20.4,-32.4L21.6,-32.9L23.1,-32.6L23.3,-32.2L24.7,-32L25.2,-31.7L27.2,-31.4L29,-30.9L30.4,-31.5L31.5,-31.5L32.1,-31.1L33.9,-31.2L34.2,-31.3L34.5,-31.6L35.1,-33.1L36,-34.6L35.9,-35.9L36,-36.9L35.4,-36.6L34.6,-36.8L33.7,-36.2L32.8,-36L31.4,-36.8L30.6,-36.9L30.4,-36.2L29.7,-36.2L29,-36.7L27.5,-37.2L27.1,-37.7L27.2,-38L26.3,-38.3L27.1,-38.4L26.7,-39.3L26.1,-39.5L26.2,-40L26.7,-40.4L29.1,-40.4L29.8,-40.7L29,-41L29.3,-41.2L31.3,-41.1L32.3,-41.7L33.4,-42L34.7,-42L36.1,-41.7L36.5,-41.3L38.4,-40.9L39.4,-41.1L40.3,-41L41.5,-41.5L41.8,-42L41.5,-42.7L40,-43.4L38.7,-44.3L36.7,-45.1L37.6,-45.4L37.9,-46L38.5,-46.1L37.8,-46.6L39.3,-47.1L38.2,-47.1L35.8,-46.6L34.9,-46.2L35,-45.7L35.6,-45.3L36.6,-45.4L36.4,-45.1L35.6,-45.1L33.9,-44.4L33.4,-44.6L33.6,-45.1L32.5,-45.4L33.6,-46.1L32.5,-46.1L31.8,-46.3L32.6,-46.6L30.8,-46.6L30.2,-45.9L29.6,-45.7L29.7,-45.3L29,-44.8L28.6,-43.7L27.9,-43.2L27.5,-42.5L28,-42L28.3,-41.5L29.1,-41.2L28.8,-41L27.5,-41L26.8,-40.6L26,-40.7L25.1,-41L23.8,-40.7L23.3,-40.2L22.6,-40.5L22.6,-40L23.3,-39.3L22.6,-38.9L24,-38.3L24.1,-37.7L23.6,-38L23,-37.9L23.5,-37.4L22.7,-37.5L23,-37L22.4,-36.5L21.9,-36.7L21.6,-37.5L21.1,-37.9L21.8,-38.3L22.9,-38L23.2,-38.2L22.4,-38.4L21.1,-38.4L20.8,-39L20,-39.7L19.3,-40.7L19.6,-41.8L19.3,-41.9L18.5,-42.4L17.7,-42.9L17.6,-42.9L16.9,-43.4L16,-43.5L15.1,-44.3L14.9,-45.1L14.3,-45.3L14,-44.8L13.6,-45.5L13.7,-45.6L13.6,-45.8L12.3,-45.4L12.5,-45L12.4,-44.2L13.5,-43.6L14,-42.7L15.2,-41.9L16,-41.9L16,-41.4L18,-40.7L18.5,-40.1L16.9,-40.5L16.5,-39.9L17.2,-39L16.6,-38.7L16.1,-37.9L15.7,-37.9L16.2,-38.8L15.7,-40L14.9,-40.2L14.8,-40.7L13.7,-41.2L12.6,-41.5L10.7,-42.9L10,-44L8.8,-44.4L7.5,-43.8L7.4,-43.7L7.4,-43.7L6.1,-43.1L5.1,-43.4L4.1,-43.6L3.1,-42.9L3.2,-42.4L3.2,-41.9L2.1,-41.3L1,-41.1L-0.3,-39.5L0.2,-38.8L-0.6,-38.2L-0.8,-37.6L-1.3,-37.6L-2.2,-36.7L-4.4,-36.7L-5.6,-36L-6,-36.2L-6.5,-37L-7.4,-37.2L-9,-37L-8.9,-38.4L-9.5,-38.7L-8.7,-41L-8.8,-41.9L-8.7,-42.3L-9.2,-43L-8.9,-43.3L-7.7,-43.8L-7.3,-43.6L-5.7,-43.6L-4.5,-43.4L-3.6,-43.5L-1.8,-43.4L-1.5,-43.6L-1,-45.7L-1.1,-46.3L-1.8,-46.5L-2.4,-47.5L-4.7,-48L-4.7,-48.5L-3.2,-48.8L-2.7,-48.5L-1.4,-48.7L-1.9,-49.7L-1.1,-49.4L-0.2,-49.3L0.2,-49.7L1.6,-50.3L1.6,-50.7L2.5,-51.1L3.3,-51.4L4.2,-51.4L3.5,-51.5L4.5,-52.3L4.7,-52.8L6.1,-53.4L7.2,-53.3L7.3,-53.7L8.5,-53.5L9,-53.9L8.7,-54.9L8.6,-55.4L8.1,-55.6L8.2,-56.6L8.6,-57.1L9.6,-57.2L10.5,-57.7L10.3,-56.6L10.8,-56.5L9.6,-55.5L9.7,-54.8L10.1,-54.5L11,-54.4L11.4,-53.9L12.6,-54.5L13.7,-54.2L14.3,-53.7L14.2,-53.9L14.2,-54L16.2,-54.3L16.6,-54.6L18.3,-54.8L18.7,-54.4L19.6,-54.5L20,-54.9L20.9,-55.3L21,-55.3L21.2,-55.3L21,-56.1L21.1,-56.8L21.7,-57.6L22.6,-57.7L23.6,-57L24.4,-57.3L24.3,-57.9L24.5,-58.4L23.8,-58.4L23.5,-59.2L25.5,-59.6L27,-59.5L28,-59.5L28,-59.7L29.1,-60L28.5,-60.7L27.8,-60.5L25.7,-60.3L23,-59.8L22.6,-60.4L21.4,-60.6L21.6,-61.6L21.1,-62.6L21.5,-63.2L22.3,-63.3L24.6,-64.8L25.3,-64.9L25.3,-65.5L24.2,-65.8L22.4,-65.8L21.6,-65.4L21.1,-64.8L21.5,-64.5L20.8,-63.9L18.6,-63.2L17.9,-62.8L17.2,-61.7L17.2,-60.7L18,-60.6L19,-59.8L18.2,-59.4L18.3,-59.1L16.8,-58.6L16.5,-57.1L16,-56.2L14.7,-56.1L14.2,-55.4L12.9,-55.4L12.5,-56.3L12.9,-56.6L12.4,-56.9L11.3,-58.5L11.4,-59L10.6,-59.6L10.2,-59L9.7,-59L8.5,-58.3L7.5,-58L6.6,-58.1L5.7,-58.5L5.6,-59L6.3,-59.5L5.4,-59.2L5.1,-59.7L5.3,-61.1L4.9,-61.7L5.1,-62.2L6.8,-62.7L7,-63L8.1,-63.1L8.4,-63.5L9.7,-63.6L10.8,-63.5L10.9,-63.8L9.9,-63.5L9.6,-63.8L10.6,-64.4L11.5,-64.7L13.1,-66.2L13.2,-66.6L15,-67.6L15,-68L16,-68.2L16.3,-67.9L16.7,-68.6L17.4,-68.8L19.2,-69.7L21.9,-70L21.4,-70.2L22.7,-70.4L23.4,-70.2L24.8,-71L25.8,-70.9L25,-70.1L26.5,-70.9L26.6,-70.4L27.6,-70.8L27.6,-71.1L28.4,-71L28.2,-70.3L29.1,-70.9L30.9,-70.3L29.6,-70L29.6,-69.8L30.9,-69.8L32,-70L32.9,-69.8L32.4,-69.5L35.9,-69.2L37.7,-68.7L38.4,-68.4L41,-67.7L41.4,-67.2L40.5,-66.4L38.4,-66.1L35.5,-66.4L33.5,-66.8L32.9,-67.1L31.9,-67.2L34.8,-65.9L34.4,-65.4L34.9,-64.6L36.4,-64L37.4,-63.8L38,-64.3L37.2,-64.4L36.5,-64.8L36.9,-65.2L39.8,-64.6L40.4,-64.8L39.8,-65.6L41.5,-66.1L42.2,-66.5L43.2,-66.4L44.1,-66L44.5,-66.7L43.9,-67.2L44.2,-68.3L43.4,-68.6L45.9,-68.5L46.7,-67.8L45.5,-67.8L44.9,-67.4L46,-66.9L47.7,-67L47.9,-67.6L50.8,-68.4L53.8,-69L53.9,-68.4L53.3,-68.3L54.6,-68.3L56,-68.6L57.1,-68.6L59.1,-69L59.1,-68.4L59.9,-68.4L59.9,-68.7L60.9,-69L60.2,-69.6L61,-69.9L63.4,-69.7L67,-68.9L68.4,-68.3L69.1,-69L68.5,-69L68,-69.5L66.8,-69.7L67.3,-70.7L66.8,-70.8L66.9,-71.3L68.3,-71.7L69,-72.7L69.6,-72.9L71.5,-72.9L72.8,-72.7L72.6,-72.1L71.9,-71.5L72.6,-71.2L72.5,-70.3L72.7,-68.9L73.5,-68.6L73.2,-67.9L71.6,-66.8L70.7,-66.5L69.9,-66.8L69.2,-66.6L70.3,-66.3L71.9,-66.2L72.4,-66.6L73.8,-67L74.8,-67.8L74.4,-68.4L74.6,-68.8L76.5,-69L77.2,-68.5L77.2,-67.8L77.6,-67.8L78,-68.3L77.7,-68.9L76,-69.2L74,-69.1L73.6,-69.7L74.3,-70.6L73.1,-71.4L73.7,-71.8L75,-72.1L74.8,-72.8L75.4,-72.8L75.7,-72.3L75.2,-71.8L75.3,-71.3L77.6,-71.2L78.2,-71.3L76.3,-71.6L76,-71.9L78.2,-72L77.5,-72.2L79.4,-72.4L80.8,-72.1L81.5,-71.7L83,-71.7L82.3,-71.3L82.3,-70.5L83,-70.9L83.1,-70.3L83.7,-70.5L83.2,-71.1L83.6,-71.6L82.2,-72.2L80.8,-72.5L80.6,-73.6L83.5,-73.7L86.6,-73.9L87,-73.8L85.8,-73.5L87.1,-73.6L87.2,-73.9L85.8,-74.6L86.7,-74.7L87.7,-75.1L90.2,-75.6L93.5,-75.9L93,-76.1L94.6,-76.2L96.1,-76.1L96.5,-75.9L98.7,-76.2L99.8,-76.1L98.8,-76.5L100.8,-76.5L101,-77L103.1,-77.6L104,-77.7L106.1,-77.4L104.2,-77.1L106.9,-77L107.4,-76.9L106.4,-76.5L107.6,-76.5L108,-76.7L111.1,-76.7L113.3,-76.3L113.7,-75.5L112.9,-75L109.8,-74.3L108.2,-73.7L106.2,-73.3L105.7,-72.8L106.5,-73.1L107.8,-73.2L109.9,-73.5L110.9,-73.7L109.8,-73.7L110.3,-74L112.1,-73.7L112.8,-74L113.2,-73.5L115.3,-73.7L118.5,-73.6L118.4,-73.2L119.7,-73L123.2,-73L123.6,-73.2L123.3,-73.5L124.4,-73.8L126.6,-73.3L127,-73.5L128.9,-73.2L128.6,-72.9L129.3,-72.7L128.4,-72.5L129.4,-72.3L128.9,-72.1L127.8,-72.4L129.8,-71.1L131.2,-70.7L131.6,-70.9L132.7,-71.9L133.4,-71.5L134.7,-71.4L135.9,-71.6L137.8,-71.2L138.1,-71.6L140,-71.5L139.2,-72.2L139.6,-72.5L141.1,-72.6L140.7,-72.9L142.1,-72.7L143.5,-72.7L146.3,-72.4L144.2,-72.3L145.7,-72.2L145.8,-71.7L147.4,-72.3L149.5,-72.2L149.9,-71.8L149.1,-71.8L151.6,-71.3L152.5,-70.8L155.9,-71.1L158,-71L159.4,-70.8L160,-70.3L159.8,-69.8L160.9,-69.6L161,-69.1L161.6,-68.9L161.5,-69.4L162.4,-69.6L164.2,-69.7L164.5,-69.6L166.9,-69.5L167.6,-69.7L168.3,-69.3L169.3,-69.1L169.6,-68.8L171,-69L170.2,-69.6L170.5,-70.1L173.7,-69.9L175.8,-69.9L178.8,-69.4L179.9,-69L180,-69L180,-65.1ZM42.6,-15.3L42.6,-15.3L42.6,-15.3ZM42.8,-13.7L42.8,-13.7L42.8,-13.7ZM42.8,-14L42.8,-14L42.8,-14ZM53.8,-12.6L54.5,-12.6L53.6,-12.3ZM104.1,-10.4L104.1,-10.4L104.1,-10.4ZM106.6,-8.7L106.6,-8.7L106.6,-8.7ZM107.2,-10.4L107.2,-10.4L107.2,-10.4ZM106.9,-20.8L106.9,-20.8L106.9,-20.8ZM107.6,-21.2L107.6,-21.2L107.6,-21.2ZM107.5,-20.9L107.5,-20.9L107.5,-20.9ZM107,-20.7L107,-20.7L107,-20.7ZM-60.8,-9.1L-60.8,-9.1L-60.8,-9.1ZM-63.8,-11.1L-63.8,-11.1L-63.8,-11.1ZM-65.2,-10.9L-65.2,-10.9L-65.2,-10.9ZM-61,-8.9L-61,-8.9L-61,-8.9ZM-57.2,-5.5L-57,-6L-55.9,-5.8L-54.8,-6L-54.1,-5.8L-54.2,-5.4L-53.8,-5.8L-52.9,-5.4L-51.8,-4.6L-51.7,-4.1L-51.2,-4.1L-51.1,-3.3L-50.5,-1.8L-50,-1.7L-49.9,-1.2L-50.8,-0.2L-51.3,0.1L-52,1.4L-51.9,1.6L-50.9,0.9L-50.4,2L-49.3,1.7L-49.2,1.9L-48.1,0.7L-47.4,0.6L-45.1,1.5L-44.4,2.2L-44.7,3.1L-43.4,2.4L-42.2,2.8L-41.3,2.9L-40,2.9L-38.5,3.7L-37.2,4.9L-35.5,5.1L-35.2,5.6L-34.8,7.3L-35.2,8.9L-36.4,10.5L-36.9,10.8L-38.2,12.8L-38.7,12.6L-39.1,13.6L-38.9,15.9L-39.2,17.3L-39.2,17.7L-39.7,18.6L-39.7,19.3L-40.4,20.6L-40.8,20.9L-41.1,22.1L-41.7,22.3L-42,22.9L-43.9,22.9L-44.6,23.1L-45.5,23.8L-46,23.8L-46.9,24.2L-47.9,25L-48.5,25.8L-48.6,27.2L-48.8,28.6L-49.7,29.4L-50.3,30.4L-51.2,30.2L-51.5,31.1L-52,31.4L-52.1,32.2L-52.7,33.1L-53.4,33.7L-53.8,34.4L-54.9,34.9L-56.1,34.9L-57.2,34.5L-57.8,34.5L-58.4,33.9L-58.2,32.5L-58.5,33.7L-58.3,34.7L-57.3,35.2L-57.3,36.1L-56.7,36.4L-56.7,36.9L-57.5,38.1L-58.2,38.4L-59.8,38.8L-61.6,39L-62.4,38.9L-62.1,39.4L-62.4,40.9L-63.8,41.1L-65.1,40.9L-65.1,42L-64.1,42.4L-63.8,42.1L-63.7,42.8L-64.7,42.5L-65,42.8L-64.3,43L-65.3,43.6L-65.6,45L-66.9,45.3L-67.6,46L-67.6,46.3L-66.8,47L-66,47.1L-65.8,47.9L-67,48.6L-67.7,49.2L-67.8,49.9L-68.9,50.4L-69.2,51L-69.1,51.5L-68.4,52.4L-69.2,52.2L-70.8,52.8L-71,53.8L-72.2,53.6L-72.3,53.3L-71.7,53.2L-71.4,52.8L-72.5,53.3L-73.1,53.2L-72.7,52.7L-71.5,52.6L-72.6,52.5L-73.1,53.1L-74,52.6L-74.3,52.1L-73.1,52.1L-74.2,51.7L-73.9,51.3L-74.8,51.1L-75.1,50.7L-74.3,50L-74.3,48.6L-74.6,48L-73.6,48L-74.7,47.7L-74.2,47.2L-75.1,46.6L-75.7,46.6L-74.9,46.2L-75.1,45.9L-74.2,45.8L-74.1,46.1L-73.2,45.4L-73.4,45L-72.7,44.4L-73.3,44.2L-73,43.6L-72.8,42.3L-72.4,42.4L-72.7,41.7L-73.7,41.7L-74,41.1L-73.2,39.2L-73.7,37.7L-73.2,37.2L-72.6,35.6L-72.2,35.1L-71.7,33.7L-71.7,33.1L-71.4,32.4L-71.7,30.8L-71.3,29.7L-71.5,28.9L-71.2,28.4L-70.4,25.2L-70.6,23.1L-70.3,22.8L-70.1,21.5L-70.2,19.7L-70.4,18.3L-71.3,17.7L-71.5,17.3L-72.5,16.7L-73.8,16.2L-75.1,15.4L-75.9,14.6L-76.4,13.9L-76.2,13.5L-77.2,11.7L-77.6,11.3L-79,8.2L-80.1,6.7L-81.1,6.1L-80.9,5.8L-81.3,4.7L-81.3,4.3L-80.3,3.4L-79.7,2.6L-80.3,2.7L-80.8,2.1L-80.9,1.1L-80.1,0L-80.1,-0.8L-78.9,-1.2L-78.9,-1.5L-78.6,-2.3L-77.7,-2.9L-77.1,-3.9L-77.4,-3.9L-77.4,-6.5L-77.9,-7.2L-78.4,-8.1L-78.1,-8.4L-79.4,-9L-80.5,-8.1L-80,-7.5L-80.8,-7.2L-81.2,-7.9L-82.7,-8.3L-82.9,-8.1L-83.2,-8.6L-83.7,-8.6L-83.6,-9L-84.7,-9.6L-85.6,-9.9L-85.7,-11.1L-86.8,-12.2L-87.7,-12.9L-87.3,-13L-87.8,-13.4L-87.9,-13.2L-88.9,-13.3L-90.1,-13.7L-91.1,-13.9L-92.2,-14.5L-93.9,-16.1L-94.9,-16.4L-95.5,-16L-96.5,-15.7L-97.8,-16L-98.8,-16.5L-99.7,-16.7L-100.8,-17.2L-101.8,-17.9L-103.4,-18.3L-103.9,-18.8L-104.9,-19.3L-105.7,-20.4L-105.2,-21.5L-105.8,-22.6L-107.1,-24L-108,-24.6L-108,-25L-109.2,-25.6L-109.2,-26.3L-109.9,-27.1L-110.5,-27.3L-110.5,-27.9L-111.1,-28L-112.2,-29L-113.1,-30.8L-113,-31.2L-114.9,-31.9L-114.6,-30L-112.9,-28.4L-112.7,-27.8L-111.6,-26.7L-111.3,-25.8L-110.7,-24.8L-109.4,-23.5L-109.9,-22.9L-110.4,-23.6L-112.1,-24.8L-112.1,-25.5L-112.4,-26.2L-113.2,-26.9L-113.6,-26.7L-114.4,-27.2L-115,-27.8L-114.2,-28L-114.1,-28.6L-115,-29.4L-115.7,-29.8L-116.1,-30.8L-116.7,-31.6L-117.1,-32.5L-117.5,-33.3L-118.5,-34L-119.6,-34.4L-120.5,-34.5L-120.6,-35.1L-121.9,-36.3L-121.9,-36.9L-122.4,-37.2L-122.5,-37.8L-123.7,-38.9L-123.9,-39.9L-124.4,-40.5L-124.1,-41.4L-124.5,-42.8L-124.1,-43.7L-123.9,-46.2L-124.1,-47L-124.7,-48.4L-124,-48.2L-122.8,-48.1L-122.6,-47.3L-122.2,-48L-122.8,-49L-123.3,-49.5L-123.9,-49.5L-124.8,-50L-125.1,-50.5L-126.4,-50.5L-126.5,-51.1L-127.1,-50.9L-127.7,-51.2L-127.8,-52.3L-128.1,-51.8L-128.4,-52.8L-129.1,-53.6L-128.5,-53.4L-128.7,-53.9L-129.6,-53.3L-130.3,-53.7L-130,-54.1L-130.4,-54.4L-129.6,-55.5L-130,-55.4L-130,-55.9L-130.2,-55L-130.6,-54.8L-131.1,-56L-132.2,-55.7L-131.8,-56.2L-132.9,-57L-133.5,-57.2L-133.6,-57.7L-134.7,-58.4L-135.5,-59.2L-135,-58.3L-136.6,-58.2L-137.5,-58.6L-138.4,-59.1L-139.8,-59.5L-139.5,-60L-140.2,-59.7L-142.9,-60.1L-144.1,-60L-145.7,-60.7L-146.5,-60.7L-146.6,-61.1L-148.6,-60.8L-148,-60.6L-148.2,-60.2L-148.8,-60L-149.4,-60.1L-149.6,-59.8L-150.6,-59.6L-150.9,-59.2L-151.7,-59.2L-151.3,-59.6L-151.9,-59.8L-151.4,-60.7L-150.4,-61L-149.6,-61L-150.6,-61.3L-151.6,-61L-154.2,-59.2L-153.3,-58.9L-154.2,-58.2L-155,-58L-156.5,-57.3L-156.6,-57L-158.4,-56.4L-158.3,-56.2L-161.5,-55.4L-162.1,-55.1L-162.9,-55.2L-162.2,-55.7L-160.3,-56.3L-158.9,-56.9L-157.7,-57.5L-157.5,-58.4L-157.1,-58.9L-158,-58.6L-158.8,-58.9L-158.8,-58.4L-160.4,-59.1L-161.4,-58.7L-162,-59.3L-161.8,-59.6L-162.4,-60.3L-162.6,-60L-163.9,-59.8L-165.4,-60.5L-164.8,-60.9L-163.7,-60.6L-163.4,-60.8L-165.2,-61L-166.2,-61.7L-164.1,-63.3L-163.4,-63L-162.3,-63.5L-161.3,-63.5L-160.8,-63.8L-161.4,-64.5L-161.2,-64.9L-162.8,-64.4L-163.7,-64.6L-164.9,-64.5L-166.1,-64.6L-166.9,-65.2L-166.2,-65.3L-168.1,-65.7L-165.4,-66.4L-163.7,-66.6L-163.7,-66.1L-161.8,-66.1L-161.9,-66.6L-160.6,-66.4L-160.3,-66.6L-161.4,-66.6L-161.6,-67L-163.7,-67.2L-164.1,-67.6L-165.4,-68L-166.8,-68.4L-166.2,-68.9L-164.3,-68.9L-163.2,-69.4L-163,-69.8L-162,-70.2L-161,-70.3L-159.3,-70.9L-158,-70.8L-156.5,-71.4L-154.2,-70.8L-153.2,-70.9L-151.2,-70.4L-149.3,-70.5L-147.7,-70.2L-145.8,-70.2L-145.2,-70L-143.2,-70.1L-141,-69.7L-139.2,-69.5L-138.1,-69.2L-136.7,-68.9L-135.9,-68.9L-135.7,-69.3L-133.9,-69.5L-133.2,-69.4L-130.5,-70.1L-129.6,-70L-131,-69.6L-131.9,-69.6L-133.4,-68.9L-131.8,-69.4L-131,-69.4L-129.1,-69.9L-129,-69.7L-127.7,-70.3L-127.1,-70.2L-126.6,-69.7L-125.4,-69.3L-125.2,-69.8L-124.4,-70.1L-124.1,-69.7L-124.5,-69.4L-123.6,-69.4L-123,-69.8L-121,-69.7L-120.3,-69.4L-118.1,-69L-116.1,-68.8L-115.6,-69L-114,-68.4L-115.4,-67.9L-113.7,-67.7L-111,-67.8L-110.1,-68L-108.6,-67.6L-107.9,-67.2L-108.5,-67.1L-107.7,-66.7L-107.2,-66.9L-108,-67.7L-107.8,-68L-106.4,-68.2L-105.8,-68.5L-108.7,-68.3L-108.3,-68.6L-106.2,-68.9L-105.4,-68.5L-104.2,-68L-103.5,-68.1L-102.7,-67.8L-101.6,-67.7L-100.5,-67.8L-99,-67.7L-98.4,-67.8L-97.5,-67.6L-97.2,-67.9L-98.1,-67.9L-98.6,-68.4L-97.3,-68.5L-96.7,-68.1L-96,-68.2L-96.4,-67.5L-95.3,-67.3L-95.7,-67.7L-93.6,-68.6L-94.6,-68.9L-94.3,-69.5L-96.1,-69.8L-96.5,-70.3L-95.9,-70.5L-96.5,-70.8L-96.4,-71.3L-94.6,-72L-92.9,-71.3L-93,-70.9L-92.4,-70.7L-92,-70L-92.9,-69.7L-90.6,-69.5L-91.2,-69.3L-90.5,-68.9L-90.2,-68.3L-89.7,-69L-89.1,-69.3L-88,-68.8L-87.9,-68.3L-88.3,-68.3L-88.2,-67.8L-87.3,-67.2L-86.5,-67.5L-85.5,-68.8L-84.9,-69.1L-85.4,-69.2L-85.4,-69.8L-82.4,-69.6L-82.8,-69.5L-81.3,-69.1L-82,-68.9L-81.3,-68.7L-82.6,-68.4L-81.3,-67.5L-81.4,-67.1L-83.5,-66.4L-84.5,-67L-83.8,-66.3L-84.5,-66.2L-85.6,-66.6L-86.6,-66.5L-86,-66L-87.3,-65.4L-88,-65.3L-89.8,-65.9L-91,-66L-89.8,-65.7L-89,-65.3L-87,-65.2L-88.1,-64.2L-88.8,-64L-90.2,-64L-90.2,-63.6L-91.8,-63.7L-90.7,-63.4L-90.9,-62.9L-92.4,-62.8L-92,-62.6L-92.8,-62.4L-92.5,-62.2L-93.6,-61.9L-93.3,-61.8L-94.1,-61.3L-94.8,-60L-94.7,-58.9L-93.3,-58.8L-92.4,-57.3L-92.7,-56.9L-91.1,-57.2L-88.9,-56.9L-87.6,-56.1L-85.8,-55.7L-85.1,-55.3L-83.9,-55.3L-82.6,-55.1L-82.2,-54.8L-82.4,-54.4L-82.1,-53.8L-82.3,-53L-81.5,-52.2L-80.7,-51.8L-80.5,-51.3L-79.7,-51.1L-78.5,-52.3L-79.2,-54.1L-79.7,-54.7L-77.9,-55.2L-76.7,-56.1L-76.7,-57.4L-77.2,-58L-78.5,-58.7L-77.3,-60L-78.2,-60.8L-77.5,-61.6L-77.9,-61.8L-78.1,-62.4L-77.4,-62.6L-74.6,-62.2L-73.8,-62.5L-72.6,-62.1L-71.4,-61.2L-69.5,-61L-69.8,-59.9L-69.4,-59.3L-69.5,-58.9L-68.4,-58.8L-68.2,-58.4L-67.6,-58.2L-65.6,-59.1L-65.4,-59.8L-64.7,-60.3L-61.9,-57.9L-62.5,-57.5L-61.3,-57L-61.4,-56.7L-62.1,-56.7L-61.4,-56.4L-61.5,-56L-60.3,-55.8L-60.6,-55.1L-59.8,-55.3L-58.8,-54.8L-58,-54.9L-57.4,-54.6L-58.6,-54L-59.8,-53.8L-60.3,-53.3L-58.2,-54.2L-57.4,-54.2L-57.2,-53.8L-56.1,-53.6L-55.8,-53.2L-55.7,-52.1L-57,-51.5L-58.4,-51.3L-60.1,-50.3L-62.7,-50.3L-66.5,-50.2L-67.4,-49.3L-68.9,-48.8L-69.9,-47.8L-71.3,-46.8L-73,-46.2L-74,-45.3L-74.7,-45L-73.6,-45.4L-73.2,-46L-71.9,-46.6L-70.5,-47L-69,-48.3L-67.6,-48.9L-66.2,-49.2L-64.8,-49.2L-64.3,-48.9L-64.3,-48.4L-65.3,-48L-66.4,-48.1L-65.5,-47.7L-64.7,-47.7L-65.3,-47.1L-64.5,-46.2L-63.3,-45.8L-62.5,-45.6L-62,-45.9L-61,-45.3L-63.8,-44.5L-64,-44.6L-64.9,-43.9L-65.7,-43.6L-66.1,-43.8L-66.1,-44.4L-65.7,-44.8L-64.3,-45.3L-64.9,-45.4L-64.3,-45.8L-65.9,-45.2L-67.1,-45.2L-67.2,-44.7L-70,-43.9L-71,-42.3L-70.5,-41.8L-69.9,-41.7L-71.5,-41.4L-72.9,-41.3L-74.2,-40.6L-74,-40.3L-74.8,-39L-75.5,-39.5L-75,-38.5L-76,-37.3L-75.7,-38L-76.2,-39.2L-76.5,-38.2L-76.3,-37.9L-76.4,-36.9L-76,-36.9L-75.9,-36.2L-76.7,-36L-75.8,-35.9L-76.2,-35.4L-77.8,-34.3L-77.9,-33.9L-78.8,-33.7L-79.2,-33.2L-81.1,-31.9L-81.5,-30.9L-81.3,-29.8L-80,-26.6L-80.4,-25.3L-81.1,-25.1L-82.8,-27.8L-82.7,-28.9L-84,-30.1L-85.3,-29.7L-85.8,-30.2L-86.5,-30.4L-87.8,-30.3L-88.9,-30.4L-89.7,-30.2L-89.4,-29.8L-90.8,-29.1L-91.9,-29.8L-92.3,-29.6L-93.9,-29.8L-94.8,-29.5L-95.9,-28.6L-97,-28.1L-97.5,-27.3L-97.1,-26L-97.7,-24.4L-97.9,-22.6L-97.6,-21.6L-97.1,-20.6L-96.5,-19.9L-95.8,-18.8L-95.2,-18.7L-94.5,-18.2L-92,-18.7L-90.7,-19.4L-90.4,-21L-89.8,-21.3L-88.1,-21.6L-86.8,-21.4L-86.9,-20.9L-87.7,-19.6L-87.4,-19.6L-87.9,-18.3L-88,-18.8L-88.3,-18.5L-88.1,-18.1L-88.3,-16.6L-88.9,-15.9L-88.2,-15.7L-87.6,-15.9L-86.4,-15.8L-85.8,-16L-84.3,-15.8L-83.8,-15.2L-83.2,-15L-83.6,-12.7L-83.8,-12.5L-83.6,-10.9L-83.4,-10.5L-82.6,-9.6L-82.2,-9L-81.4,-8.8L-80.1,-9.2L-79.6,-9.6L-78.1,-9.2L-77.4,-8.7L-76.7,-8L-76.9,-8.6L-75.6,-9.4L-75.4,-10.6L-74.8,-11.1L-74.4,-10.8L-74.1,-11.3L-73.3,-11.3L-72.3,-11.9L-71.7,-12.4L-71.3,-12.3L-71.3,-11.9L-71.9,-11.4L-71.6,-10.7L-72.1,-9.8L-71.7,-9.1L-71.1,-9.7L-71.5,-11L-69.9,-11.4L-70.3,-11.9L-70,-12.2L-69.6,-11.5L-68.4,-11.2L-68.1,-10.5L-66.2,-10.6L-65.9,-10.3L-64.8,-10.1L-63.9,-10.6L-61.9,-10.7L-62.9,-10.5L-62.3,-9.8L-61.6,-9.9L-60.8,-9.4L-61.3,-8.4L-60,-8.5L-59.2,-8.1L-58,-6.8L-57.2,-6.2ZM166.7,14.8L167.2,15.5L166.8,15.6ZM167.4,16.1L167.4,16.1L167.4,16.1ZM168.4,16.8L168.4,16.8L168.4,16.8ZM168.3,16.3L168.3,16.3L168.3,16.3ZM168.4,17.5L168.4,17.5L168.4,17.5ZM167.9,15.4L167.9,15.4L167.9,15.4ZM168.2,16L168.2,16L168.2,16ZM168.2,15.3L168.2,15.3L168.2,15.3ZM167.2,15.7L167.2,15.7L167.2,15.7ZM167.6,14.3L167.6,14.3L167.6,14.3ZM167.5,13.9L167.5,13.9L167.5,13.9ZM169.9,20.2L169.9,20.2L169.9,20.2ZM169.5,19.5L169.5,19.5L169.5,19.5ZM169.3,18.9L169.3,18.9L169.3,18.9ZM163,-5.3L163,-5.3L163,-5.3ZM138.1,-9.5L138.1,-9.5L138.1,-9.5ZM151.6,-7.3L151.6,-7.3L151.6,-7.3ZM151.9,-7.4L151.9,-7.4L151.9,-7.4ZM158.3,-6.8L158.3,-6.8L158.3,-6.8ZM169.6,-5.8L169.6,-5.8L169.6,-5.8ZM168.8,-7.3L168.8,-7.3L168.8,-7.3ZM171.6,-7L171.6,-7L171.6,-7ZM171.1,-7.1L171.1,-7.1L171.1,-7.1ZM166.9,-11.2L166.9,-11.2L166.9,-11.2ZM145.7,-18.8L145.7,-18.8L145.7,-18.8ZM145.7,-16.3L145.7,-16.3L145.7,-16.3ZM145.3,-14.2L145.3,-14.2L145.3,-14.2ZM145.8,-18.1L145.8,-18.1L145.8,-18.1ZM145.8,-15.1L145.8,-15.1L145.8,-15.1ZM145.7,-15L145.7,-15L145.7,-15ZM-64.8,-18.3L-64.8,-18.3L-64.8,-18.3ZM-64.7,-18.4L-64.7,-18.4L-64.7,-18.4ZM-64.8,-17.8L-64.8,-17.8L-64.8,-17.8ZM144.7,-13.3L144.7,-13.3L144.7,-13.3ZM-170.7,14.4L-170.7,14.4L-170.7,14.4ZM-66.1,-18.4L-65.6,-18.4L-66,-18L-67.2,-18L-67.2,-18.5ZM-65.4,-18.1L-65.4,-18.1L-65.4,-18.1ZM-67.9,-18.1L-67.9,-18.1L-67.9,-18.1ZM-132.7,-56.5L-132.7,-56.5L-132.7,-56.5ZM-132.8,-56.2L-132.8,-56.2L-132.8,-56.2ZM-134.3,-58.2L-134.3,-58.2L-134.3,-58.2ZM-145.1,-60.3L-145.1,-60.3L-145.1,-60.3ZM-144.6,-59.8L-144.6,-59.8L-144.6,-59.8ZM-148,-60.1L-148,-60.1L-148,-60.1ZM-152,-60.4L-152,-60.4L-152,-60.4ZM-160.3,-55.3L-160.3,-55.3L-160.3,-55.3ZM-159.4,-55L-159.4,-55L-159.4,-55ZM-159.5,-55.2L-159.5,-55.2L-159.5,-55.2ZM-166.2,-53.7L-166.2,-53.7L-166.2,-53.7ZM-176,-51.8L-176,-51.8L-176,-51.8ZM-166.1,-66.2L-166.1,-66.2L-166.1,-66.2ZM-171.5,-63.6L-170.4,-63.7L-168.9,-63.2L-169.8,-63.1ZM-166.1,-60.4L-165.6,-59.9L-166.1,-59.8L-167.4,-60.2ZM-152.9,-57.8L-152.2,-57.6L-154.3,-56.9L-154.5,-57.6ZM-163.5,-55L-163.4,-54.7L-164.6,-54.4L-164.5,-54.9ZM-133.3,-55.5L-133.3,-55.5L-133.3,-55.5ZM-131.3,-55.1L-131.3,-55.1L-131.3,-55.1ZM-132.1,-56.1L-132.7,-56.1L-132.4,-56.5ZM-131,-55.5L-131.8,-55.2L-131.6,-55.8ZM-133.4,-57L-133,-56.9L-133.6,-56.5L-134,-57ZM-132.9,-54.9L-132.9,-54.9L-132.9,-54.9ZM-146.4,-60.5L-146.4,-60.5L-146.4,-60.5ZM-147.7,-59.8L-147.7,-59.8L-147.7,-59.8ZM-147.7,-60.5L-147.7,-60.5L-147.7,-60.5ZM-147.9,-60.8L-147.9,-60.8L-147.9,-60.8ZM-153,-57.1L-153,-57.1L-153,-57.1ZM-152.5,-58.5L-152.5,-58.5L-152.5,-58.5ZM-153.2,-57.8L-153.2,-57.8L-153.2,-57.8ZM-155.6,-55.8L-155.6,-55.8L-155.6,-55.8ZM-154.7,-56.4L-154.7,-56.4L-154.7,-56.4ZM-154.2,-56.5L-154.2,-56.5L-154.2,-56.5ZM-160.7,-55.3L-160.7,-55.3L-160.7,-55.3ZM-162.3,-54.8L-162.3,-54.8L-162.3,-54.8ZM-162.6,-54.4L-162.6,-54.4L-162.6,-54.4ZM-159.9,-55.1L-159.9,-55.1L-159.9,-55.1ZM-165.8,-54.1L-165.8,-54.1L-165.8,-54.1ZM-165.6,-54.1L-165.6,-54.1L-165.6,-54.1ZM-160.9,-58.6L-160.9,-58.6L-160.9,-58.6ZM-172.7,-60.5L-172.7,-60.5L-172.7,-60.5ZM-170.2,-57.2L-170.2,-57.2L-170.2,-57.2ZM-169.7,-52.8L-169.7,-52.8L-169.7,-52.8ZM-170.7,-52.6L-170.7,-52.6L-170.7,-52.6ZM-172.5,-52.3L-172.5,-52.3L-172.5,-52.3ZM-169.8,-56.6L-169.8,-56.6L-169.8,-56.6ZM-176.3,-51.8L-176.3,-51.8L-176.3,-51.8ZM-176,-52L-176,-52L-176,-52ZM-177.1,-51.7L-177.1,-51.7L-177.1,-51.7ZM178.6,-51.9L178.6,-51.9L178.6,-51.9ZM179.5,-51.4L179.5,-51.4L179.5,-51.4ZM173.7,-52.4L173.7,-52.4L173.7,-52.4ZM-135,-57.4L-134.7,-56.2L-135.2,-57L-135.8,-57.3ZM-134.7,-58.2L-134.2,-58.1L-133.9,-57.3L-134.5,-57ZM-135.7,-58.2L-135,-58.1L-134.9,-57.5L-135.7,-57.4L-136.6,-58ZM-133.6,-56.3L-133.2,-56.3L-132,-55.2L-132.1,-54.7L-133.7,-55.8ZM-134,-56.8L-134.2,-56.1L-134.4,-56.8ZM-152.4,-58.4L-152.8,-58L-153.4,-58.1ZM-168,-53.3L-169.1,-52.8L-168.3,-53.5ZM-166.6,-53.9L-166.6,-53.9L-166.6,-53.9ZM-173.6,-52.1L-173.6,-52.1L-173.6,-52.1ZM-174.7,-52L-174.7,-52L-174.7,-52ZM-176.6,-51.9L-176.6,-51.9L-176.6,-51.9ZM-177.9,-51.7L-177.9,-51.7L-177.9,-51.7ZM179.7,-51.9L179.7,-51.9L179.7,-51.9ZM177.4,-51.9L177.4,-51.9L177.4,-51.9ZM172.8,-53L172.8,-53L172.8,-53ZM-155.6,-19L-156,-19.7L-155.8,-20.3L-154.8,-19.5ZM-157.2,-21.2L-157.2,-21.2L-157.2,-21.2ZM-156.5,-20.9L-156.5,-20.9L-156.5,-20.9ZM-157.8,-21.5L-157.8,-21.5L-157.8,-21.5ZM-159.4,-21.9L-159.4,-21.9L-159.4,-21.9ZM-160.2,-21.8L-160.2,-21.8L-160.2,-21.8ZM-156.8,-20.8L-156.8,-20.8L-156.8,-20.8ZM-72.5,-41L-73.2,-40.7L-74,-40.6L-73.6,-40.9ZM-68.2,-44.3L-68.2,-44.3L-68.2,-44.3ZM-74.2,-40.5L-74.2,-40.5L-74.2,-40.5ZM-70.5,-41.4L-70.5,-41.4L-70.5,-41.4ZM-71.2,-41.5L-71.2,-41.5L-71.2,-41.5ZM-70,-41.3L-70,-41.3L-70,-41.3ZM-75.6,-35.9L-75.6,-35.9L-75.6,-35.9ZM-75.5,-35.2L-75.5,-35.2L-75.5,-35.2ZM-75.8,-35.2L-75.8,-35.2L-75.8,-35.2ZM-76.5,-34.6L-76.5,-34.6L-76.5,-34.6ZM-82,-26.5L-82,-26.5L-82,-26.5ZM-82.1,-26.6L-82.1,-26.6L-82.1,-26.6ZM-80.4,-25.1L-80.4,-25.1L-80.4,-25.1ZM-91.8,-29.5L-91.8,-29.5L-91.8,-29.5ZM-97,-27.9L-97,-27.9L-97,-27.9ZM-96.8,-28.2L-96.8,-28.2L-96.8,-28.2ZM-97.4,-27.3L-97.4,-27.3L-97.4,-27.3ZM-95,-29.1L-95,-29.1L-95,-29.1ZM-97.2,-26.2L-97.2,-26.2L-97.2,-26.2ZM-120.3,-34L-120.3,-34L-120.3,-34ZM-119.4,-33.2L-119.4,-33.2L-119.4,-33.2ZM-118.3,-32.8L-118.3,-32.8L-118.3,-32.8ZM-120,-33.9L-120,-33.9L-120,-33.9ZM-119.9,-34.1L-119.9,-34.1L-119.9,-34.1ZM-118.3,-33.4L-118.3,-33.4L-118.3,-33.4ZM-122.8,-48.7L-122.8,-48.7L-122.8,-48.7ZM-123,-48.5L-123,-48.5L-123,-48.5ZM-122.6,-48.2L-122.6,-48.2L-122.6,-48.2ZM-71.4,-41.5L-71.4,-41.5L-71.4,-41.5ZM-74.1,-39.7L-74.1,-39.7L-74.1,-39.7ZM-75.3,-37.9L-75.3,-37.9L-75.3,-37.9ZM-76.5,-34.7L-76.5,-34.7L-76.5,-34.7ZM-81.3,-24.7L-81.3,-24.7L-81.3,-24.7ZM-80.8,-24.8L-80.8,-24.8L-80.8,-24.8ZM-80.6,-24.9L-80.6,-24.9L-80.6,-24.9ZM-81,-24.7L-81,-24.7L-81,-24.7ZM-81.4,-31L-81.4,-31L-81.4,-31ZM-81.6,-24.6L-81.6,-24.6L-81.6,-24.6ZM-80.2,-27.3L-80.2,-27.3L-80.2,-27.3ZM-81.8,-24.5L-81.8,-24.5L-81.8,-24.5ZM-88.9,-29.7L-88.9,-29.7L-88.9,-29.7ZM-88.6,-30.2L-88.6,-30.2L-88.6,-30.2ZM-88.1,-30.3L-88.1,-30.3L-88.1,-30.3ZM-89.2,-30.1L-89.2,-30.1L-89.2,-30.1ZM-88.8,-29.8L-88.8,-29.8L-88.8,-29.8ZM-84.9,-29.6L-84.9,-29.6L-84.9,-29.6ZM-122.9,-47.2L-122.9,-47.2L-122.9,-47.2ZM-122.4,-47.4L-122.4,-47.4L-122.4,-47.4ZM-122.5,-47.6L-122.5,-47.6L-122.5,-47.6ZM-122.8,-48.4L-122.8,-48.4L-122.8,-48.4ZM-68.6,-44.2L-68.6,-44.2L-68.6,-44.2ZM-26.3,58.4L-26.3,58.4L-26.3,58.4ZM-37.1,54.1L-36.3,54.3L-35.8,54.8L-37.5,54.2ZM72.5,7.4L72.5,7.4L72.5,7.4ZM-5.7,16L-5.7,16L-5.7,16ZM-14.4,8L-14.4,8L-14.4,8ZM-128.3,24.4L-128.3,24.4L-128.3,24.4ZM-63,-18.2L-63,-18.2L-63,-18.2ZM-58.9,51.3L-58,51.4L-57.8,51.7L-59.2,52ZM-60.3,51.5L-59.3,51.4L-59.9,52L-61,52.1L-60.2,51.8ZM-61,51.8L-61,51.8L-61,51.8ZM-58.4,52L-58.4,52L-58.4,52ZM-60.1,51.4L-60.1,51.4L-60.1,51.4ZM-59.7,52.2L-59.7,52.2L-59.7,52.2ZM-81.4,-19.3L-81.4,-19.3L-81.4,-19.3ZM-80,-19.7L-80,-19.7L-80,-19.7ZM-79.8,-19.7L-79.8,-19.7L-79.8,-19.7ZM-64.7,-32.3L-64.7,-32.3L-64.7,-32.3ZM-64.4,-18.5L-64.4,-18.5L-64.4,-18.5ZM-64.6,-18.4L-64.6,-18.4L-64.6,-18.4ZM-64.3,-18.7L-64.3,-18.7L-64.3,-18.7ZM-71.7,-21.8L-71.7,-21.8L-71.7,-21.8ZM-71.9,-21.8L-71.9,-21.8L-71.9,-21.8ZM-72.3,-21.9L-72.3,-21.9L-72.3,-21.9ZM-62.1,-16.7L-62.1,-16.7L-62.1,-16.7ZM-2,-49.2L-2,-49.2L-2,-49.2ZM-2.5,-49.5L-2.5,-49.5L-2.5,-49.5ZM-4.4,-54.2L-4.4,-54.2L-4.4,-54.2ZM-2.7,-51.6L-3.3,-51.4L-5.3,-51.9L-4,-52.5L-4.1,-53.2L-3.2,-53.4L-2.9,-54.2L-3.6,-54.5L-3.4,-55L-4,-54.8L-5.1,-54.9L-4.7,-55.5L-4.8,-56.1L-5.8,-55.4L-5.2,-56.8L-6.1,-56.7L-5.6,-57.2L-5.6,-57.9L-5.2,-57.9L-5.1,-58.5L-3.1,-58.6L-4,-58L-4.1,-57.6L-2.1,-57.7L-1.8,-57.5L-2.7,-56.3L-3.4,-56L-2.6,-56L-1.7,-55.6L-1.3,-54.8L-0.1,-54.1L0.4,-53.2L0,-52.9L1.1,-53L1.7,-52.5L0.7,-51.4L1.4,-51.2L0.2,-50.8L-1.4,-50.9L-2,-50.6L-3.4,-50.6L-3.8,-50.2L-4.2,-50.4L-5.2,-50L-5.3,-50.2L-4.2,-51.2L-3.1,-51.2ZM-4.2,-53.3L-4.2,-53.3L-4.2,-53.3ZM-2.6,-59.2L-2.6,-59.2L-2.6,-59.2ZM-1,-60.5L-1,-60.5L-1,-60.5ZM-1.3,-60.5L-1.2,-60L-1.7,-60.3ZM-0.8,-60.8L-0.8,-60.8L-0.8,-60.8ZM-3.2,-58.8L-3.2,-58.8L-3.2,-58.8ZM-2.9,-58.7L-2.9,-58.7L-2.9,-58.7ZM-3.1,-59L-3.1,-59L-3.1,-59ZM-2.7,-59.2L-2.7,-59.2L-2.7,-59.2ZM-6.6,-56.6L-6.6,-56.6L-6.6,-56.6ZM-5.1,-55.4L-5.1,-55.4L-5.1,-55.4ZM-5.8,-56.3L-5.8,-56.3L-5.8,-56.3ZM-6.1,-55.9L-6.1,-55.9L-6.1,-55.9ZM-6,-55.8L-6,-55.8L-6,-55.8ZM-6.2,-58.4L-7,-57.8L-7,-58.2ZM-6.3,-57L-6.3,-57L-6.3,-57ZM-6.1,-57.5L-5.9,-57L-6.8,-57.4ZM-7.2,-57.7L-7.2,-57.7L-7.2,-57.7ZM-7.2,-57.1L-7.2,-57.1L-7.2,-57.1ZM-7.4,-57L-7.4,-57L-7.4,-57ZM-7.2,-55.1L-6.1,-55.2L-5.6,-54.7L-5.6,-54.3L-6.2,-54.1L-6,-52.9L-6.3,-52.2L-7.5,-52.1L-8.8,-51.6L-9.8,-51.5L-9.8,-51.8L-10.4,-52.1L-9.6,-52.5L-9.3,-53.1L-10.1,-53.5L-10.1,-54.3L-8.5,-54.2L-8.1,-54.6L-8.8,-54.7L-8.3,-55.1ZM-1.1,-50.7L-1.1,-50.7L-1.1,-50.7ZM53.3,-24.3L53.3,-24.3L53.3,-24.3ZM52.6,-24.3L52.6,-24.3L52.6,-24.3ZM53.9,-24.2L53.9,-24.2L53.9,-24.2ZM54.5,-24.4L54.5,-24.4L54.5,-24.4ZM32,-46.2L32,-46.2L32,-46.2ZM53.1,-38.8L53.1,-38.8L53.1,-38.8ZM26,-40.1L26,-40.1L26,-40.1ZM11.3,-34.8L11.3,-34.8L11.3,-34.8ZM11,-33.7L11,-33.7L11,-33.7ZM-60.8,-11.2L-60.8,-11.2L-60.8,-11.2ZM-61,-10.1L-61.7,-10.7L-60.9,-10.8ZM-175.2,21.2L-175.2,21.2L-175.2,21.2ZM-174,18.6L-174,18.6L-174,18.6ZM-174.9,21.3L-174.9,21.3L-174.9,21.3ZM125.6,8.1L125.6,8.1L125.6,8.1ZM124.4,9.2L124.9,8.9L125.8,8.5L127.3,8.4L125.1,9.5L124.4,10.1L123.6,10.3L124,9.3ZM102.6,-11.7L102.6,-11.7L102.6,-11.7ZM102.4,-12L102.4,-12L102.4,-12ZM98.4,-7.9L98.4,-7.9L98.4,-7.9ZM100.1,-9.7L100.1,-9.7L100.1,-9.7ZM100.1,-9.6L100.1,-9.6L100.1,-9.6ZM99.7,-6.5L99.7,-6.5L99.7,-6.5ZM98.6,-7.9L98.6,-7.9L98.6,-7.9ZM98.3,-9.1L98.3,-9.1L98.3,-9.1ZM99.1,-7.6L99.1,-7.6L99.1,-7.6ZM39.5,6.2L39.5,6.2L39.5,6.2ZM39.9,4.9L39.9,4.9L39.9,4.9ZM39.7,8L39.7,8L39.7,8ZM121,-22.6L120.8,-21.9L120.1,-23.2L120.1,-23.7L121,-25L121.6,-25.3L121.9,-25L121.4,-23.2ZM118.4,-24.5L118.4,-24.5L118.4,-24.5ZM19.1,-57.8L18.9,-57.4L18.1,-56.9L18.1,-57.6ZM16.5,-56.3L16.4,-56.6L17.1,-57.3ZM19.2,-57.9L19.2,-57.9L19.2,-57.9ZM18.4,-59L18.4,-59L18.4,-59ZM18.6,-59.5L18.6,-59.5L18.6,-59.5ZM80,-9.6L80,-9.6L80,-9.6ZM79.9,-9.1L79.9,-9.1L79.9,-9.1ZM80,-9.8L80.7,-9.4L81.4,-8.4L81.9,-7.3L81.6,-6.4L80.7,-6L80.1,-6.2L79.7,-8.1L80.1,-9.1ZM1.6,-38.7L1.6,-38.7L1.6,-38.7ZM3.1,-39.8L3.1,-39.3L2.4,-39.6ZM4.3,-39.8L4.3,-39.8L4.3,-39.8ZM1.4,-38.9L1.4,-38.9L1.4,-38.9ZM-16.3,-28.4L-16.3,-28.4L-16.3,-28.4ZM-13.7,-28.9L-13.7,-28.9L-13.7,-28.9ZM-14.2,-28.2L-14.2,-28.2L-14.2,-28.2ZM-15.4,-28.1L-15.4,-28.1L-15.4,-28.1ZM-17.2,-28L-17.2,-28L-17.2,-28ZM-17.9,-27.8L-17.9,-27.8L-17.9,-27.8ZM-17.8,-28.5L-17.8,-28.5L-17.8,-28.5ZM128.7,-34.8L128.7,-34.8L128.7,-34.8ZM128.1,-34.8L128.1,-34.8L128.1,-34.8ZM126.2,-34.4L126.2,-34.4L126.2,-34.4ZM126.5,-37.7L126.5,-37.7L126.5,-37.7ZM126.8,-34.3L126.8,-34.3L126.8,-34.3ZM127.8,-34.6L127.8,-34.6L127.8,-34.6ZM126.4,-36.5L126.4,-36.5L126.4,-36.5ZM126.2,-34.7L126.2,-34.7L126.2,-34.7ZM130.9,-37.5L130.9,-37.5L130.9,-37.5ZM126.3,-33.2L126.3,-33.2L126.3,-33.2ZM37.9,46.9L37.9,46.9L37.9,46.9ZM159.7,8.5L159.7,8.5L159.7,8.5ZM166.9,11.7L166.9,11.7L166.9,11.7ZM166.1,10.8L166.1,10.8L166.1,10.8ZM160.6,11.8L160.6,11.8L160.6,11.8ZM161.5,9.6L161.5,9.6L161.5,9.6ZM159.2,9.1L159.2,9.1L159.2,9.1ZM160.2,9L160.2,9L160.2,9ZM157.8,8.2L157.8,8.2L157.8,8.2ZM158.2,8.8L158.2,8.8L158.2,8.8ZM158.1,8.7L158.1,8.7L158.1,8.7ZM157.4,8.7L157.4,8.7L157.4,8.7ZM156.7,7.9L156.7,7.9L156.7,7.9ZM156.6,8.2L156.6,8.2L156.6,8.2ZM157.2,8.1L157.2,8.1L157.2,8.1ZM155.8,7.1L155.8,7.1L155.8,7.1ZM157.6,8.8L157.6,8.8L157.6,8.8ZM159.7,9.3L160.8,9.9L159.9,9.8ZM159.9,8.5L158.9,8L158.5,7.5L159.8,8.3ZM157.5,7.3L157.1,7.3L156.5,6.7ZM160.8,8.3L161.3,9.6L160.9,9.2ZM161.7,10.4L161.7,10.4L161.7,10.4ZM104,-1.3L104,-1.3L104,-1.3ZM-12.5,-7.4L-12.5,-7.4L-12.5,-7.4ZM55.5,4.7L55.5,4.7L55.5,4.7ZM36.9,-25.4L36.9,-25.4L36.9,-25.4ZM42,-16.7L42,-16.7L42,-16.7ZM36.6,-25.7L36.6,-25.7L36.6,-25.7ZM7.4,-1.6L7.4,-1.6L7.4,-1.6ZM6.7,-0.1L6.7,-0.1L6.7,-0.1ZM-172.3,13.5L-172.3,13.5L-172.3,13.5ZM-171.5,14L-171.5,14L-171.5,14ZM-61.2,-13.2L-61.2,-13.2L-61.2,-13.2ZM-61.2,-13L-61.2,-13L-61.2,-13ZM-61.3,-12.7L-61.3,-12.7L-61.3,-12.7ZM-60.9,-13.8L-60.9,-13.8L-60.9,-13.8ZM-62.5,-17.1L-62.5,-17.1L-62.5,-17.1ZM-62.6,-17.2L-62.6,-17.2L-62.6,-17.2ZM145.9,-43.5L145.9,-43.5L145.9,-43.5ZM146.4,-43.6L146.4,-43.6L146.4,-43.6ZM146,-43.4L146,-43.4L146,-43.4ZM137.2,-55.1L137.2,-55.1L137.2,-55.1ZM150.6,-59L150.6,-59L150.6,-59ZM120.3,-73.1L120.3,-73.1L120.3,-73.1ZM124.5,-73.9L124.5,-73.9L124.5,-73.9ZM106.3,-78.2L106.3,-78.2L106.3,-78.2ZM107.4,-77.2L107.4,-77.2L107.4,-77.2ZM97.6,-76.6L97.6,-76.6L97.6,-76.6ZM96.9,-76.2L96.9,-76.2L96.9,-76.2ZM100.1,-79.6L100.1,-79.6L100.1,-79.6ZM76.8,-73.4L76.8,-73.4L76.8,-73.4ZM82.7,-74.1L82.7,-74.1L82.7,-74.1ZM84.8,-74.5L84.8,-74.5L84.8,-74.5ZM86.7,-75L86.7,-75L86.7,-75ZM59.3,-81.3L59.3,-81.3L59.3,-81.3ZM47.4,-80.9L46.1,-80.4L44.9,-80.6ZM50.3,-80.9L51.7,-80.7L48.9,-80.4L49,-80.2L47.6,-80.1L46.6,-80.3L48.4,-80.6L49.1,-80.5L49.2,-80.8ZM67.8,-76.2L61.4,-75.3L60.5,-74.9L59.1,-74.5L57,-73.4L55,-73.5L54.3,-73.4L53.8,-73.8L54.6,-74L55.6,-74.6L56.5,-75L56.8,-75.4L57.6,-75.3L58.9,-75.9L60.9,-76.1L61.2,-76.3L63,-76.2L64.5,-76.4L67.5,-77L68.5,-76.9L68.9,-76.6ZM55.3,-73.3L56.4,-73.2L55.4,-72.5L55.3,-71.9L56,-71.3L57.6,-70.7L57.1,-70.6L54.6,-70.7L53.4,-70.9L54.2,-71.1L53.4,-71.5L51.8,-71.5L51.6,-72.1L52.3,-72.1L53.4,-72.9L53.4,-73.2ZM96.5,-81.1L97.8,-80.8L97,-80.5L97.2,-80.2L94.6,-80.1L93.9,-80L91.5,-80.4L93.3,-80.8L93.1,-81L95.8,-81.3ZM97.7,-80.2L97.7,-79.8L98.6,-80.1L100.1,-79.8L99.4,-78.8L97.6,-78.8L96.8,-79L94.8,-79.1L94.2,-79.4L93.1,-79.5L95,-80.1ZM102.9,-79.3L102.4,-78.8L103.7,-79.2L105.1,-78.8L105.3,-78.5L103.7,-78.3L101.2,-78.2L100.1,-78L99.3,-78L100.3,-78.7L100.9,-78.8L101.2,-79.2L102.3,-79.4ZM140.1,-75.8L140.6,-75.6L141.5,-76.1L143.2,-75.8L143.7,-75.9L145.3,-75.6L144,-75L142.7,-75.3L143,-75.7L142.1,-75.7L142.6,-75.1L140.3,-74.8L139.6,-74.9L139.1,-74.7L137.2,-75.1L137.3,-75.7L138.9,-76.2ZM146.8,-75.4L148.4,-75.4L148.5,-75.3L150.1,-75.2L150.6,-74.9L149.6,-74.8L148.1,-74.8L146.1,-75.2ZM142.8,-54.4L143.3,-53.2L143.2,-52.1L143.8,-50.3L144.6,-48.8L143.7,-49.3L143.1,-49.2L142.6,-47.7L143.3,-46.6L142.6,-46.7L142.1,-45.9L141.8,-46.5L142.2,-48L141.9,-48.7L142.1,-49.6L142.1,-51.4L141.7,-51.7L141.8,-53.3L142.5,-53.4ZM180,-71L179.9,-71L178.8,-70.8L178.9,-71.2L179.9,-71.5L180,-71.5L180,-71ZM-180,-71.5L-180,-71.5L-180,-71.5L-178.4,-71.5L-177.5,-71.3L-177.8,-71.1L-180,-71L-180,-71L-180,-71.5ZM35.8,-65.2L35.8,-65.2L35.8,-65.2ZM42.7,-66.7L42.7,-66.7L42.7,-66.7ZM52.9,-71.4L52.9,-71.4L52.9,-71.4ZM168,-54.6L168,-54.6L168,-54.6ZM160.7,-70.8L160.7,-70.8L160.7,-70.8ZM161.5,-68.9L161.5,-68.9L161.5,-68.9ZM152.9,-76.1L152.9,-76.1L152.9,-76.1ZM149.2,-76.7L149.2,-76.7L149.2,-76.7ZM138,-71.5L138,-71.5L138,-71.5ZM107.7,-78.1L107.7,-78.1L107.7,-78.1ZM112.5,-76.6L112.5,-76.6L112.5,-76.6ZM96.5,-76.3L96.5,-76.3L96.5,-76.3ZM96.3,-77L96.3,-77L96.3,-77ZM89.5,-77.2L89.5,-77.2L89.5,-77.2ZM74.7,-72.9L74.7,-72.9L74.7,-72.9ZM75.5,-73.5L75.5,-73.5L75.5,-73.5ZM83.5,-74.1L83.5,-74.1L83.5,-74.1ZM67.3,-69.5L67.3,-69.5L67.3,-69.5ZM66.6,-70.5L66.6,-70.5L66.6,-70.5ZM70,-66.5L70,-66.5L70,-66.5ZM50.1,-80.1L50.1,-80.1L50.1,-80.1ZM51.4,-79.9L51.4,-79.9L51.4,-79.9ZM50.8,-81L50.8,-81L50.8,-81ZM55.5,-80.3L55.5,-80.3L55.5,-80.3ZM54.4,-80.5L54.4,-80.5L54.4,-80.5ZM59.7,-80L59.7,-80L59.7,-80ZM58.6,-81L58.9,-80.8L57.2,-81ZM48,-45.5L48,-45.5L48,-45.5ZM50.3,-69.2L49.6,-68.9L48.7,-68.7L48.4,-69.3L49.2,-69.5ZM63.4,-80.7L62.5,-80.8L65.2,-81.1L65.4,-80.9ZM58,-80.1L57.1,-80.5L58.5,-80.5ZM62.2,-80.8L61.1,-80.4L59.3,-80.5L59.6,-80.8ZM61.1,-81L61.1,-81L61.1,-81ZM53.5,-80.2L52.2,-80.3L52.9,-80.4ZM57.1,-80.4L57.1,-80.1L55.7,-80.1L56,-80.3ZM57.8,-81.5L58.4,-81.5L57.5,-81.1L55.7,-81.2L57.1,-81.5ZM54.7,-81.1L57.7,-80.8L55.7,-80.6L54.1,-80.8ZM63.7,-81.6L63.7,-81.6L63.7,-81.6ZM58.3,-81.7L58.3,-81.7L58.3,-81.7ZM92.7,-79.7L91.1,-79.9L91.4,-80L93.8,-79.9ZM91.6,-81.1L91.6,-81.1L91.6,-81.1ZM141,-74L140.1,-74.2L140.8,-74.3ZM142.2,-73.9L143.3,-73.6L143.5,-73.2L141.6,-73.3L140.4,-73.5L141.1,-73.9ZM135.9,-75.4L135.5,-75.4L135.7,-75.8ZM136.2,-73.9L136.2,-73.9L136.2,-73.9ZM137.9,-55.1L137.9,-55.1L137.9,-55.1ZM169.2,-69.6L167.8,-69.8L168.4,-70L169.4,-69.9ZM163.6,-58.6L163.8,-59L164.6,-59.2L164.6,-58.9ZM166.7,-54.8L165.8,-55.3L166.3,-55.3ZM154.8,-49.3L154.8,-49.3L154.8,-49.3ZM156.4,-50.7L156.4,-50.7L156.4,-50.7ZM155.9,-50.3L155.2,-50.1L156.1,-50.8ZM154.1,-48.8L154.1,-48.8L154.1,-48.8ZM155.6,-50.8L155.6,-50.8L155.6,-50.8ZM153.1,-47.8L153.1,-47.8L153.1,-47.8ZM152,-46.9L152,-46.9L152,-46.9ZM149.7,-45.6L149.7,-45.6L149.7,-45.6ZM148.6,-45.3L147.2,-44.8L147.9,-45.2ZM146.7,-43.7L146.7,-43.7L146.7,-43.7ZM146.2,-44.5L146.6,-44.4L145.6,-43.8ZM113.4,-74.4L112.8,-74.1L111.5,-74.4L112.1,-74.5ZM76.3,-79.7L76.3,-79.7L76.3,-79.7ZM80,-80.8L80,-80.8L80,-80.8ZM70.7,-73.1L69.9,-73.1L70.1,-73.4L70.9,-73.5L71.6,-73.2ZM77.6,-72.3L76.9,-72.3L77.6,-72.6L78.4,-72.5ZM79.5,-72.7L78.7,-72.9L79.2,-73.1ZM82.2,-75.4L82.2,-75.4L82.2,-75.4ZM60.5,-69.9L60.4,-69.7L59,-69.9L58.5,-70.3L59,-70.5ZM-17.2,-32.9L-17.2,-32.9L-17.2,-32.9ZM-25,-37L-25,-37L-25,-37ZM-31.1,-39.4L-31.1,-39.4L-31.1,-39.4ZM-27.1,-38.6L-27.1,-38.6L-27.1,-38.6ZM-27.8,-38.6L-27.8,-38.6L-27.8,-38.6ZM-28.6,-38.5L-28.6,-38.5L-28.6,-38.5ZM-28.1,-38.5L-28.1,-38.5L-28.1,-38.5ZM-25.6,-37.8L-25.6,-37.8L-25.6,-37.8ZM121.1,-18.6L121.8,-18.3L122.3,-18.4L122.2,-17.7L122.5,-17.1L122.1,-16.2L121.6,-15.9L121.4,-15.3L121.8,-14.2L122.5,-14.3L123.2,-13.7L123.3,-14.1L123.9,-12.9L123.3,-13L122.5,-13.9L122.7,-13.3L121.8,-13.9L121.2,-13.6L120.6,-13.8L120.9,-14.6L120.4,-14.5L120.1,-14.9L119.8,-16.3L120.4,-16.2L120.4,-17.6L120.6,-18.5ZM117.3,-8.4L119,-10.4L119.5,-11.3L119.7,-10.6L118.8,-9.9L118.4,-9.3ZM122.5,-11.6L123.2,-11.5L122.8,-10.8L122,-10.5L122.1,-11.6ZM123.1,-9.1L122.6,-9.5L123,-10.9L123.6,-10.8L123.2,-9.9ZM124.6,-11.3L124.9,-11.4L125.3,-10.3L124.8,-10.2ZM125.2,-12.5L125.5,-12.2L125.7,-11.2L125.2,-11.1L124.3,-12.6ZM120.7,-13.5L121.5,-13.1L121.2,-12.2L120.4,-13.5ZM126,-9.3L126.3,-8.8L126.6,-7.2L126.2,-6.9L125.8,-7.3L125.4,-6.8L125.7,-6L125.3,-5.6L124.2,-6.2L124,-6.9L124.2,-7.4L123.5,-7.8L122.5,-7.7L122,-7L122.1,-7.8L122.9,-8.2L123.4,-8.7L123.8,-8.1L124.7,-8.6L124.9,-9L125.5,-9L125.5,-9.8ZM123.4,-9.4L123.4,-10L124,-11.3L124.1,-10.6ZM121.9,-18.9L121.9,-18.9L121.9,-18.9ZM121.5,-19.4L121.5,-19.4L121.5,-19.4ZM122,-20.4L122,-20.4L122,-20.4ZM121.9,-20.8L121.9,-20.8L121.9,-20.8ZM121.2,-6.1L121.2,-6.1L121.2,-6.1ZM117.1,-7.9L117.1,-7.9L117.1,-7.9ZM119.9,-10.5L119.9,-10.5L119.9,-10.5ZM120.1,-12.2L120.1,-12.2L120.1,-12.2ZM120,-11.7L120,-11.7L120,-11.7ZM122.6,-10.5L122.6,-10.5L122.6,-10.5ZM124.6,-9.8L123.9,-9.6L124.2,-10.1ZM120.3,-5.3L120.3,-5.3L120.3,-5.3ZM122.1,-6.4L122.1,-6.4L122.1,-6.4ZM126.1,-9.8L126.1,-9.8L126.1,-9.8ZM125.7,-9.9L125.7,-9.9L125.7,-9.9ZM120.3,-13.8L120.3,-13.8L120.3,-13.8ZM121.9,-13.5L121.9,-13.5L121.9,-13.5ZM122.1,-12.4L122.1,-12.4L122.1,-12.4ZM122.7,-12.3L122.7,-12.3L122.7,-12.3ZM123.3,-12.9L123.3,-12.9L123.3,-12.9ZM123.8,-12.5L123.8,-12.5L123.8,-12.5ZM123.7,-12.3L123.2,-11.9L123.2,-12.6ZM124.4,-13.6L124.4,-13.6L124.4,-13.6ZM122.2,-14L122.2,-14L122.2,-14ZM122,-15L122,-15L122,-15ZM124.3,-10.6L124.3,-10.6L124.3,-10.6ZM125.3,-10L125.3,-10L125.3,-10ZM122.9,-7.4L122.9,-7.4L122.9,-7.4ZM125.8,-7L125.8,-7L125.8,-7ZM124.6,-11.5L124.6,-11.5L124.6,-11.5ZM124.8,-9.1L124.8,-9.1L124.8,-9.1ZM121.3,-19.1L121.3,-19.1L121.3,-19.1ZM119.9,-11.5L119.9,-11.5L119.9,-11.5ZM123.8,-11.3L123.8,-11.3L123.8,-11.3ZM122.3,-12.5L122.3,-12.5L122.3,-12.5ZM126,-9.6L126,-9.6L126,-9.6ZM124.9,-11.6L124.9,-11.6L124.9,-11.6ZM117.4,-8.2L117.4,-8.2L117.4,-8.2ZM123.7,-9.2L123.7,-9.2L123.7,-9.2ZM153,4.8L152.2,3.4L153,4.1ZM151.9,4.3L152.4,4.3L152,5L152.1,5.4L150.4,6.3L149.7,6.3L148.4,5.8L148.3,5.5L151,5.4L151.7,4.9ZM141,2.6L143.5,3.4L144.5,3.9L145.8,4.8L145.7,5.4L147.8,6.3L147.8,6.7L147.1,6.7L147.2,7.4L148.1,8.1L148.6,9.1L149.2,9.1L149.2,9.4L150,9.7L149.9,10L150.7,10.3L150.3,10.7L149.8,10.4L147.8,10.1L146.7,9L146,8.1L144.5,7.6L143.6,8.2L143.1,8.3L143.4,9L142.6,9.3L141,9.1L139.9,8.1L138.9,8.1L139.1,7.6L138.6,6.9L138.1,5.5L137.1,4.9L136,4.5L135.2,4.5L134.7,4L134,3.8L133.7,3.4L133,4.1L132.8,3.3L132,2.8L133.6,2.5L133.9,2.1L132.3,2.2L131.9,1.6L131,1.4L131.3,0.9L132.6,0.4L134,0.7L134.3,1.4L134.2,2.2L134.6,2.5L135,3.3L135.5,3.3L136.4,2.3L137.2,2L137.8,1.5L139.8,2.3ZM148,5.8L148,5.8L148,5.8ZM146,4.7L146,4.7L146,4.7ZM152.7,3.1L152.7,3.1L152.7,3.1ZM152.1,2.9L152.1,2.9L152.1,2.9ZM149.8,1.6L149.8,1.6L149.8,1.6ZM151.1,10L151.1,10L151.1,10ZM150.3,9.5L150.3,9.5L150.3,9.5ZM151.1,8.7L151.1,8.7L151.1,8.7ZM154.3,11.4L154.3,11.4L154.3,11.4ZM143.6,8.5L143.6,8.5L143.6,8.5ZM147.2,5.4L147.2,5.4L147.2,5.4ZM147.1,2L147.1,2L147.1,2ZM150.4,2.7L150.4,2.7L150.4,2.7ZM150.5,9.3L150.5,9.3L150.5,9.3ZM152.6,9L152.6,9L152.6,9ZM153.5,11.5L153.5,11.5L153.5,11.5ZM143.6,8.6L143.6,8.6L143.6,8.6ZM147.9,2.3L147.9,2.3L147.9,2.3ZM152,2.8L152,2.8L152,2.8ZM150.9,10.6L150.9,10.6L150.9,10.6ZM153.7,4.1L153.7,4.1L153.7,4.1ZM156,6.7L155.3,6.7L154.8,6L155.1,5.6ZM154.6,5.4L154.6,5.4L154.6,5.4ZM-78.9,-8.3L-78.9,-8.3L-78.9,-8.3ZM-81.6,-7.3L-81.6,-7.3L-81.6,-7.3ZM-82.2,-9.4L-82.2,-9.4L-82.2,-9.4ZM-79.1,-8.3L-79.1,-8.3L-79.1,-8.3ZM131.2,-3L131.2,-3L131.2,-3ZM134.6,-7.4L134.6,-7.4L134.6,-7.4ZM58.7,-20.2L58.7,-20.2L58.7,-20.2ZM5,-61.1L5,-61.1L5,-61.1ZM5.1,-60.3L5.1,-60.3L5.1,-60.3ZM30,-69.8L30,-69.8L30,-69.8ZM12,-65.6L12,-65.6L12,-65.6ZM8.5,-63.7L8.5,-63.7L8.5,-63.7ZM8.1,-63.3L8.1,-63.3L8.1,-63.3ZM23.4,-70.8L22.4,-70.5L22,-70.7ZM25.6,-71.1L25.6,-71.1L25.6,-71.1ZM23.6,-70.6L23.6,-70.6L23.6,-70.6ZM24,-70.6L24,-70.6L24,-70.6ZM13.9,-68.3L13.9,-68.3L13.9,-68.3ZM13,-67.9L13,-67.9L13,-67.9ZM15.2,-68.9L15.2,-68.6L14.5,-68.6ZM19.8,-70.2L19.8,-70.2L19.8,-70.2ZM20.8,-70.1L20.8,-70.1L20.8,-70.1ZM19.3,-70.1L18.8,-69.6L18.3,-69.8ZM12.5,-65.9L12.5,-65.9L12.5,-65.9ZM12.4,-66L12.4,-66L12.4,-66ZM11.2,-64.9L11.2,-64.9L11.2,-64.9ZM17.5,-69.6L18,-69.2L17.2,-69ZM15.8,-68.6L15.9,-68.4L14.3,-68.2L15.4,-68.6L15.9,-69.3ZM-9,-70.8L-9,-70.8L-9,-70.8ZM19.2,-74.4L19.2,-74.4L19.2,-74.4ZM26.9,-78.6L26.9,-78.6L26.9,-78.6ZM32.5,-80.1L32.5,-80.1L32.5,-80.1ZM21.6,-78.6L23.1,-78L24.9,-77.8L22.8,-77.3L22.7,-77.5L21.1,-77.4L21.7,-77.9L20.4,-78.5ZM20.9,-80.2L22.3,-80L22.5,-80.4L23.1,-80.2L24.3,-80.4L26.9,-80.2L27.2,-79.9L25.6,-79.4L23.9,-79.2L22.9,-79.4L20.9,-79.4L19.7,-79.6L20.8,-79.7L18.9,-79.7L17.9,-80.1L19.8,-80.2L19.6,-80.5ZM16.8,-79.9L17.6,-79.9L19.1,-79.2L20.2,-79.1L21.4,-78.7L19.8,-78.6L18.4,-78L16.7,-76.6L14.4,-77.2L14.1,-77.6L17,-77.8L16.9,-77.9L14.6,-77.8L13.7,-78L16.8,-78.3L16.8,-78.7L15.4,-78.5L15.3,-78.8L14.5,-78.7L14.6,-78.4L13.1,-78.2L11.8,-78.7L12.3,-78.9L11.6,-79.3L11.2,-79.1L10.9,-79.8L12.3,-79.7L13.7,-79.9L13.3,-79.6L14,-79.3L14.6,-79.8L16.3,-79L15.8,-79.7L16.1,-80ZM11.3,-78.6L11.3,-78.6L11.3,-78.6ZM18.7,-80.3L18.7,-80.3L18.7,-80.3ZM29,-78.9L29,-78.9L29,-78.9ZM124.9,-39.5L124.9,-39.5L124.9,-39.5ZM7.3,-4.4L7.3,-4.4L7.3,-4.4ZM173.1,41.3L174.3,41L174.3,41.7L172.7,43.4L173.1,43.9L171.4,44.1L170.7,45.7L169.7,46.6L168.4,46.6L167.7,46.2L166.7,46.2L166.5,45.8L167,45.1L168.4,44.1L168.8,44L171,42.7L171.5,41.8L172,41.4L172.6,40.5ZM173.9,40.9L173.9,40.9L173.9,40.9ZM166.7,45.7L166.7,45.7L166.7,45.7ZM167,45.2L167,45.2L167,45.2ZM168.1,46.9L167.5,47.3L167.8,46.7ZM175.5,36.3L175.5,36.3L175.5,36.3ZM173.3,34.9L174.3,35.2L174.8,36.3L174.7,36.8L175.6,37.2L175.5,36.5L176,37.6L177.3,38L178,37.6L178.5,37.7L177.9,39.2L177.4,39.1L176,41.2L175.3,41.6L174.6,41.3L175.3,40.3L175,40L173.9,39.5L173.8,39.2L174.6,38.8L174.9,37.8L174.2,36.5L173.1,35.2ZM169.2,52.5L169.2,52.5L169.2,52.5ZM166.2,50.8L166.2,50.8L166.2,50.8ZM-176.2,43.7L-176.2,43.7L-176.2,43.7ZM-176.2,44.3L-176.2,44.3L-176.2,44.3ZM-172.5,8.6L-172.5,8.6L-172.5,8.6ZM-171.2,9.4L-171.2,9.4L-171.2,9.4ZM-169.8,19.1L-169.8,19.1L-169.8,19.1ZM-159.7,21.2L-159.7,21.2L-159.7,21.2ZM6.3,-53.5L6.3,-53.5L6.3,-53.5ZM5.9,-53.5L5.9,-53.5L5.9,-53.5ZM5.1,-53.3L5.1,-53.3L5.1,-53.3ZM5.3,-53.4L5.3,-53.4L5.3,-53.4ZM4.9,-53.1L4.9,-53.1L4.9,-53.1ZM3.9,-51.7L3.9,-51.7L3.9,-51.7ZM6.7,-53.6L6.7,-53.6L6.7,-53.6ZM-68.2,-12.1L-68.2,-12.1L-68.2,-12.1ZM-62.9,-17.5L-62.9,-17.5L-62.9,-17.5ZM-63.2,-17.6L-63.2,-17.6L-63.2,-17.6ZM-69.9,-12.5L-69.9,-12.5L-69.9,-12.5ZM-68.8,-12.1L-68.8,-12.1L-68.8,-12.1ZM167,0.5L167,0.5L167,0.5ZM-86.9,-20.3L-86.9,-20.3L-86.9,-20.3ZM-106.5,-21.6L-106.5,-21.6L-106.5,-21.6ZM-110.9,-18.7L-110.9,-18.7L-110.9,-18.7ZM-110.6,-25L-110.6,-25L-110.6,-25ZM-113.2,-29.1L-113.2,-29.1L-113.2,-29.1ZM-115.2,-28.1L-115.2,-28.1L-115.2,-28.1ZM-112.2,-29L-112.2,-29L-112.2,-29ZM-118.2,-28.9L-118.2,-28.9L-118.2,-28.9ZM-86.7,-21.2L-86.7,-21.2L-86.7,-21.2ZM-91.7,-18.7L-91.7,-18.7L-91.7,-18.7ZM-109.8,-24.2L-109.8,-24.2L-109.8,-24.2ZM-114.7,-31.7L-114.7,-31.7L-114.7,-31.7ZM-111.1,-26L-111.1,-26L-111.1,-26ZM-111.7,-24.4L-111.7,-24.4L-111.7,-24.4ZM-112.1,-24.5L-112.1,-24.5L-112.1,-24.5ZM57.7,20.5L57.7,20.5L57.7,20.5ZM-16.4,-19.7L-16.4,-19.7L-16.4,-19.7ZM14.6,-35.9L14.6,-35.9L14.6,-35.9ZM14.3,-36L14.3,-36L14.3,-36ZM73.4,-3.2L73.4,-3.2L73.4,-3.2ZM73.5,-4.2L73.5,-4.2L73.5,-4.2ZM109.6,-2L111.1,-1.4L111.2,-2.4L111.7,-2.9L113,-3.2L114.1,-4.6L115,-4.9L115.1,-4.9L115.6,-5.1L116.8,-7L118,-6.1L119.2,-5.4L119.1,-5.1L118.3,-5L118.6,-4.5L117.6,-4.2L117.8,-3.7L117.2,-3.6L118.1,-2.3L117.8,-2L119,-1L118.5,-0.8L117.9,-1.1L117.5,-0.2L117.6,0.7L116.3,1.8L116.5,2.5L116,3.6L114.7,4.2L114.5,3.4L113.8,3.5L113,2.9L112.6,3.4L111.8,3.5L111.8,3.1L110.3,3L110,1.4L109.3,0.7L109.3,0L108.9,-0.4L109.1,-1.5ZM104.2,-2.7L104.2,-2.7L104.2,-2.7ZM100.3,-5.3L100.3,-5.3L100.3,-5.3ZM99.8,-6.5L99.8,-6.5L99.8,-6.5ZM117.1,-7.2L117.1,-7.2L117.1,-7.2ZM101.3,-3L101.3,-3L101.3,-3ZM111.4,-2.4L111.4,-2.4L111.4,-2.4ZM117.6,-4.2L117.9,-4.2L117.6,-4.2ZM49.5,12.4L49.9,13.1L50.5,15.4L50.2,16L49.6,15.6L49.8,16.8L49.4,17.3L49.4,18.3L47.9,22.4L47.6,23.9L47.2,24.8L46.7,25.2L45.1,25.5L44,25L43.7,24.4L43.7,23.5L43.3,22.1L44.4,19.9L44.4,19.4L44,18.3L44,17.4L44.5,16.2L46.3,15.7L47.8,14.6L48,13.6L48.8,13.3L48.8,12.5L49.2,12.1ZM48.3,13.4L48.3,13.4L48.3,13.4ZM49.9,16.9L49.9,16.9L49.9,16.9ZM48.3,-29.6L48.3,-29.6L48.3,-29.6ZM173,-3.1L173,-3.1L173,-3.1ZM172.8,-3.1L172.8,-3.1L172.8,-3.1ZM173,-1.8L173,-1.8L173,-1.8ZM173,-1.7L173,-1.7L173,-1.7ZM173,-1L173,-1L173,-1ZM174.5,0.8L174.5,0.8L174.5,0.8ZM174.8,1.2L174.8,1.2L174.8,1.2ZM173,-1.3L173,-1.3L173,-1.3ZM169.6,0.9L169.6,0.9L169.6,0.9ZM-172.2,4.5L-172.2,4.5L-172.2,4.5ZM-171.1,3.1L-171.1,3.1L-171.1,3.1ZM-171.2,4.5L-171.2,4.5L-171.2,4.5ZM-174.5,4.7L-174.5,4.7L-174.5,4.7ZM-155,4.1L-155,4.1L-155,4.1ZM-151.8,11.4L-151.8,11.4L-151.8,11.4ZM-155.9,5.6L-155.9,5.6L-155.9,5.6ZM-157.3,-1.9L-157.3,-1.9L-157.3,-1.9ZM-159.3,-3.9L-159.3,-3.9L-159.3,-3.9ZM-171.7,2.8L-171.7,2.8L-171.7,2.8ZM41,2.2L41,2.2L41,2.2ZM50.2,-44.9L50.2,-44.9L50.2,-44.9ZM50.3,-45L50.3,-45L50.3,-45ZM52.7,-45.4L52.7,-45.4L52.7,-45.4ZM133.4,-36.2L133.4,-36.2L133.4,-36.2ZM138.3,-37.8L138.3,-37.8L138.3,-37.8ZM134.9,-34.3L134.9,-34.3L134.9,-34.3ZM130.6,-30.3L130.6,-30.3L130.6,-30.3ZM131,-30.4L131,-30.4L131,-30.4ZM130.1,-32.2L130.1,-32.2L130.1,-32.2ZM129.3,-34.1L129.3,-34.1L129.3,-34.1ZM129.4,-34.4L129.4,-34.4L129.4,-34.4ZM128.7,-32.8L128.7,-32.8L128.7,-32.8ZM130.4,-32.4L130.4,-32.4L130.4,-32.4ZM141.1,-45.3L141.1,-45.3L141.1,-45.3ZM141.3,-45.1L141.3,-45.1L141.3,-45.1ZM139.5,-42.1L139.5,-42.1L139.5,-42.1ZM134.4,-34.5L134.4,-34.5L134.4,-34.5ZM139.5,-34.7L139.5,-34.7L139.5,-34.7ZM129.1,-32.8L129.1,-32.8L129.1,-32.8ZM129.5,-33.2L129.5,-33.2L129.5,-33.2ZM129.8,-33.7L129.8,-33.7L129.8,-33.7ZM132.6,-34.1L132.6,-34.1L132.6,-34.1ZM132.3,-33.9L132.3,-33.9L132.3,-33.9ZM129.7,-31.7L129.7,-31.7L129.7,-31.7ZM142.2,-26.6L142.2,-26.6L142.2,-26.6ZM143.8,-44.1L144.8,-43.9L145.3,-44.3L145.1,-43.8L145.5,-43.2L144.2,-43L143.6,-42.6L143.2,-42L141.9,-42.6L140.3,-42.3L141.2,-41.8L140.1,-41.4L139.9,-42.6L140.4,-43.3L141.3,-43.2L141.8,-44.7L141.6,-45.2L141.9,-45.5L142.7,-44.8ZM131.2,-33.6L131.9,-33.3L131.3,-31.4L130.7,-31L130.2,-31.3L130.2,-32.1L130.6,-32.6L130.4,-33.1L129.8,-32.7L129.6,-33.2L131,-33.9ZM134.4,-34.3L134.7,-33.8L134.2,-33.2L133.6,-33.5L132.6,-32.8L132.4,-33.4L132.8,-34ZM141.2,-41.4L142,-39.8L141.9,-39.1L140.9,-37.9L141,-37L140.6,-36.5L140.9,-35.7L139.9,-34.9L139.3,-35.3L138.9,-34.6L138.6,-35.1L138.2,-34.6L136.9,-34.8L136.9,-34.3L136.3,-34.2L135.9,-33.6L135.5,-33.6L134.7,-34.8L133.1,-34.3L130.9,-34L132.9,-35.5L134.2,-35.5L135.2,-35.7L135.7,-35.5L136.7,-36.7L138.3,-37.2L139.4,-38.1L140,-39.4L139.7,-39.9L140.4,-41.2L141.1,-40.9ZM124.3,-24.5L124.3,-24.5L124.3,-24.5ZM123.9,-24.3L123.9,-24.3L123.9,-24.3ZM125.4,-24.7L125.4,-24.7L125.4,-24.7ZM128.3,-26.7L128.3,-26.7L128.3,-26.7ZM129,-27.7L129,-27.7L129,-27.7ZM129.5,-28.2L129.5,-28.2L129.5,-28.2ZM129.3,-28.1L129.3,-28.1L129.3,-28.1ZM139.8,-33.1L139.8,-33.1L139.8,-33.1ZM-77.3,-18.5L-76.4,-18.2L-77.2,-17.7L-77.8,-17.9L-78.2,-18.4ZM10.4,-42.9L10.4,-42.9L10.4,-42.9ZM13.9,-40.7L13.9,-40.7L13.9,-40.7ZM12.1,-36.8L12.1,-36.8L12.1,-36.8ZM15.6,-38.2L15.1,-37.5L15.1,-36.7L14.5,-36.8L12.4,-37.8L12.7,-38.2L13.7,-38ZM9.6,-40.9L9.8,-40.6L9.6,-39.4L8.9,-38.9L8.4,-39.2L8.5,-39.8L8.2,-40.9L9.2,-41.3ZM8.5,-39.1L8.5,-39.1L8.5,-39.1ZM8.3,-41L8.3,-41L8.3,-41ZM-9.9,-53.9L-9.9,-53.9L-9.9,-53.9ZM56.2,-26.9L56.2,-26.9L56.2,-26.9ZM97.5,-1.5L97.9,-1L97.7,-0.6L97.1,-1.4ZM99.2,1.8L98.6,1.2L98.9,0.9ZM116.6,8.6L116.4,8.9L116.1,8.4ZM115.4,8.2L115.7,8.4L115.2,8.8L114.5,8.1ZM106,1.7L106.4,2.5L106.8,2.6L106.7,3.1L106,2.8L105.8,2.2L105.1,2L105.6,1.5ZM123.2,4.6L122.8,5.7L122.6,5.5L122.9,4.4ZM122.6,5.3L122.3,5.3L122.7,4.6ZM108.3,-3.7L108.3,-3.7L108.3,-3.7ZM108.2,3L107.6,3.2L107.7,2.6ZM135.4,0.7L136.4,1.1L135.8,1.1ZM135.5,1.6L136.9,1.8L136.5,1.9ZM130.8,0L131,0.4L130.2,0.2ZM128.5,-2.1L128.5,-2.1L128.5,-2.1ZM128.2,1.7L127.4,1.6L127.6,1.3ZM126.1,2.5L126.1,2.5L126.1,2.5ZM126,1.8L126,1.8L126,1.8ZM125,1.7L125,1.7L125,1.7ZM131.3,8L131.1,7.9L131.6,7.1ZM126.8,7.7L125.8,8L126,7.7ZM124.6,8.1L124.6,8.1L124.6,8.1ZM131,1.3L131,1.3L131,1.3ZM96.5,-5.2L97.5,-5.2L97.9,-4.9L98.3,-4.1L99.7,-3.2L100.9,-1.9L101,-2.3L102.5,-0.8L103.3,-0.5L103.8,0L103.4,0.2L103.7,0.9L104.4,1L104.5,1.8L105,2.4L105.6,2.5L106,3.1L105.8,3.6L105.8,5.7L104.6,5.9L103.8,5.1L102.5,4.2L101.6,3.2L100.8,2.1L100.3,0.8L99.6,-0.1L99.2,-0.4L98.6,-1.9L97.7,-2.4L97.6,-2.8L97,-3.6L96.4,-3.8L95.5,-4.8L95.2,-5.6ZM122.8,8.6L121.7,8.9L119.9,8.9L119.9,8.4L120.6,8.2L121.5,8.6ZM120,9.4L120.8,10L120.4,10.3L119.2,9.4ZM118.2,8.3L119,8.3L119.1,8.7L117.1,9.1L116.8,8.5L117.6,8.4L117.8,8.7ZM124.9,-1L124.4,-0.5L123.8,-0.3L123.1,-0.5L120.5,-0.5L120,0.2L120.7,1.4L121,1.4L121.5,0.9L123.4,0.6L122.5,1.3L121.3,1.9L121.8,2.3L122.4,3.2L122.3,3.6L122.9,4.3L121.9,4.8L121.5,4.6L121.6,4.1L120.9,3.6L121.1,2.8L120.3,3.1L120.4,3.7L120.3,5.1L120.4,5.6L119.7,5.7L119.4,5.4L119.6,4L119.4,3.5L118.9,3.4L118.8,2.8L119.3,1.9L119.3,1.4L119.7,0.7L119.7,0.1L120.3,-1L120.9,-1.3L122.9,-0.8L123.8,-0.8L125,-1.7ZM107.4,6L108.3,6.3L108.7,6.8L110.4,6.9L110.7,6.5L112.5,6.9L112.8,7.6L114.1,7.6L114.4,7.9L114.6,8.8L113.3,8.3L112.7,8.4L110.6,8.1L109.9,7.8L108.5,7.8L106.5,7.4L106.5,7.1L105.5,6.8L106.1,5.9ZM127.7,-0.8L128.7,-1.6L128.3,-0.7L128.9,-0.2L128,-0.5L127.7,0.2L127.4,-1.3L127.6,-1.8L128,-1.3ZM129.8,2.9L130.4,3L130.8,3.9L129.8,3.3L129.5,3.5L127.9,3.2L128.2,2.9ZM126.9,3.1L127.2,3.6L126.7,3.8L126,3.2ZM134.7,5.7L134.8,6.2L134.2,6.1ZM134.5,6.4L134.1,6.8L134.1,6.2ZM138.5,8.3L137.7,8.4L138,7.6L138.8,7.4L139,7.7ZM138.9,8.4L138.9,8.4L138.9,8.4ZM101.7,-2.1L101.7,-2.1L101.7,-2.1ZM102.4,-1L102.4,-1L102.4,-1ZM102.5,-1.5L102.5,-1.5L102.5,-1.5ZM103,-0.7L103,-0.7L103,-0.7ZM103.2,-0.9L103.2,-0.9L103.2,-0.9ZM103.3,-0.5L103.3,-0.5L103.3,-0.5ZM103.4,-0.7L103.4,-0.7L103.4,-0.7ZM104,-1.2L104,-1.2L104,-1.2ZM104.6,-1.2L104.6,-1.2L104.6,-1.2ZM104.8,0.2L104.8,0.2L104.8,0.2ZM104.5,0.3L104.5,0.3L104.5,0.3ZM103.7,0.3L103.7,0.3L103.7,0.3ZM109.7,1.2L109.7,1.2L109.7,1.2ZM113.8,7.1L112.8,7.1L112.9,6.9L114,6.9ZM135,1.1L135,1.1L135,1.1ZM127.2,0.5L127.2,0.5L127.2,0.5ZM127.6,0.3L127.6,0.3L127.6,0.3ZM132.9,5.9L132.9,5.9L132.9,5.9ZM132.8,5.9L132.8,5.9L132.8,5.9ZM128.3,3.7L128.3,3.7L128.3,3.7ZM126.8,-4L126.8,-4L126.8,-4ZM125.7,-3.4L125.7,-3.4L125.7,-3.4ZM130.9,8.3L130.9,8.3L130.9,8.3ZM129.8,8L129.8,8L129.8,8ZM127.8,8.1L127.8,8.1L127.8,8.1ZM130.4,1.7L130.4,1.7L130.4,1.7ZM102.4,5.5L102.4,5.5L102.4,5.5ZM100.4,3.2L100.4,3.2L100.4,3.2ZM100.2,2.7L100.2,2.7L100.2,2.7ZM99.8,2.3L99.8,2.3L99.8,2.3ZM98.5,0.5L98.5,0.5L98.5,0.5ZM96.5,-2.4L96.5,-2.4L96.5,-2.4ZM122,5.4L122,5.4L122,5.4ZM123.2,1.2L123.2,1.2L123.2,1.2ZM121.9,0.4L121.9,0.4L121.9,0.4ZM120.5,6.3L120.5,6.3L120.5,6.3ZM115.4,7L115.4,7L115.4,7ZM116.3,3.9L116.3,3.9L116.3,3.9ZM123,10.9L123,10.9L123,10.9ZM124.3,8.3L124.3,8.3L124.3,8.3ZM123.9,8.3L123.9,8.3L123.9,8.3ZM123.3,8.4L123.3,8.4L123.3,8.4ZM134.7,6.5L134.7,6.5L134.7,6.5ZM103.4,-1L103.4,-1L103.4,-1ZM103.8,-0.8L103.8,-0.8L103.8,-0.8ZM104.2,-0.8L104.2,-0.8L104.2,-0.8ZM104.7,-0.1L104.7,-0.1L104.7,-0.1ZM106.3,-3.2L106.3,-3.2L106.3,-3.2ZM105.8,-2.9L105.8,-2.9L105.8,-2.9ZM108.9,-2.9L108.9,-2.9L108.9,-2.9ZM109,1.6L109,1.6L109,1.6ZM107.5,2.9L107.5,2.9L107.5,2.9ZM106.9,3L106.9,3L106.9,3ZM114.4,7.1L114.4,7.1L114.4,7.1ZM112.7,5.8L112.7,5.8L112.7,5.8ZM105.3,6.6L105.3,6.6L105.3,6.6ZM97.3,-2.1L97.3,-2.1L97.3,-2.1ZM95.4,-5.8L95.4,-5.8L95.4,-5.8ZM123.6,1.7L123.6,1.7L123.6,1.7ZM123.2,4.1L123.2,4.1L123.2,4.1ZM123.8,2L123.8,2L123.8,2ZM123.2,1.8L123.2,1.8L123.2,1.8ZM119.5,8.7L119.5,8.7L119.5,8.7ZM119.1,8.2L119.1,8.2L119.1,8.2ZM115.6,8.8L115.6,8.8L115.6,8.8ZM117.7,-3.3L117.7,-3.3L117.7,-3.3ZM124.1,6L124.1,6L124.1,6ZM123.6,5.3L123.6,5.3L123.6,5.3ZM120.8,7.1L120.8,7.1L120.8,7.1ZM117.6,8.4L117.6,8.4L117.6,8.4ZM116.4,3.5L116.4,3.5L116.4,3.5ZM127.4,-0.8L127.4,-0.8L127.4,-0.8ZM134.4,2.1L134.4,2.1L134.4,2.1ZM133.6,4.2L133.6,4.2L133.6,4.2ZM130.9,0.8L130.9,0.8L130.9,0.8ZM130.6,0.5L130.6,0.5L130.6,0.5ZM129.5,0.2L129.5,0.2L129.5,0.2ZM127.5,0L127.5,0L127.5,0ZM127.4,-0.6L127.4,-0.6L127.4,-0.6ZM127.3,0.8L127.3,0.8L127.3,0.8ZM128.7,3.5L128.7,3.5L128.7,3.5ZM128.6,3.6L128.6,3.6L128.6,3.6ZM126.7,-3.9L126.7,-3.9L126.7,-3.9ZM126.9,-3.8L126.9,-3.8L126.9,-3.8ZM125.4,-2.7L125.4,-2.7L125.4,-2.7ZM132,7.2L132,7.2L132,7.2ZM128.7,7.2L128.7,7.2L128.7,7.2ZM127.4,7.6L127.4,7.6L127.4,7.6ZM123.4,10.3L123.4,10.3L123.4,10.3ZM121.9,10.6L121.9,10.6L121.9,10.6ZM134.8,6.4L134.8,6.4L134.8,6.4ZM134.7,6.7L134.7,6.7L134.7,6.7ZM128,2.9L128,2.9L128,2.9ZM127.6,3.3L127.6,3.3L127.6,3.3ZM123,8.5L123,8.5L123,8.5ZM93.9,-6.8L93.9,-6.8L93.9,-6.8ZM93.7,-7.4L93.7,-7.4L93.7,-7.4ZM93.1,-8.3L93.1,-8.3L93.1,-8.3ZM93.4,-7.9L93.4,-7.9L93.4,-7.9ZM93.5,-8.1L93.5,-8.1L93.5,-8.1ZM92.8,-9.1L92.8,-9.1L92.8,-9.1ZM92.5,-10.6L92.5,-10.6L92.5,-10.6ZM92.7,-11.4L92.7,-11.4L92.7,-11.4ZM92.7,-11.5L92.5,-11.9L92.9,-13.4L93,-12.5ZM93,-12L93,-12L93,-12ZM92.7,-12.9L92.7,-12.9L92.7,-12.9ZM72.8,-11.2L72.8,-11.2L72.8,-11.2ZM73.1,-8.3L73.1,-8.3L73.1,-8.3ZM-15.5,-66.2L-14.8,-65.8L-13.6,-65.5L-13.6,-65L-14.5,-64.5L-16.6,-63.9L-17.8,-63.7L-18.7,-63.4L-20.2,-63.6L-21.2,-63.9L-22.7,-63.8L-21.6,-64.4L-22.5,-64.8L-24,-64.9L-21.9,-65L-22.5,-65.2L-21.8,-65.4L-22.9,-65.6L-23.9,-65.4L-24.1,-65.8L-23.3,-65.8L-23.7,-66.1L-22.4,-66.1L-23.1,-66.3L-22.4,-66.4L-21.4,-66L-21.1,-65.3L-20.4,-66L-19.6,-65.8L-19.4,-66.1L-18.3,-66.2L-17.6,-66L-16.5,-66.2L-16,-66.5ZM-86.4,-16.4L-86.4,-16.4L-86.4,-16.4ZM-85.9,-16.5L-85.9,-16.5L-85.9,-16.5ZM-71.8,-18L-72.1,-18.2L-73.4,-18.3L-73.9,-18L-74.5,-18.4L-74.2,-18.7L-72.8,-18.4L-72.3,-18.7L-72.7,-19.4L-73.4,-19.7L-72.9,-19.9L-71.8,-19.7L-71,-19.9L-70.1,-19.6L-69.6,-19.1L-68.3,-18.6L-68.7,-18.2L-69.8,-18.4L-71,-18.3L-71.4,-17.6ZM-72.8,-18.8L-72.8,-18.8L-72.8,-18.8ZM-72.7,-20L-72.7,-20L-72.7,-20ZM-16.1,-11.1L-16.1,-11.1L-16.1,-11.1ZM-15.9,-11.1L-15.9,-11.1L-15.9,-11.1ZM-15.7,-11.2L-15.7,-11.2L-15.7,-11.2ZM-15.6,-11.5L-15.6,-11.5L-15.6,-11.5ZM-15.9,-11.5L-15.9,-11.5L-15.9,-11.5ZM-16,-11.9L-16,-11.9L-16,-11.9ZM-61.7,-12L-61.7,-12L-61.7,-12ZM27.9,-36.6L27.9,-36.6L27.9,-36.6ZM20.6,-38.4L20.6,-38.4L20.6,-38.4ZM20.9,-37.8L20.9,-37.8L20.9,-37.8ZM20.7,-38.6L20.7,-38.6L20.7,-38.6ZM20.8,-38.3L20.8,-38.3L20.8,-38.3ZM20.1,-39.4L20.1,-39.4L20.1,-39.4ZM23.4,-39L24.1,-38.7L24.3,-38.2L23.3,-38.8ZM23.8,-39.1L23.8,-39.1L23.8,-39.1ZM23.9,-39.2L23.9,-39.2L23.9,-39.2ZM24.7,-38.8L24.7,-38.8L24.7,-38.8ZM24.8,-40.6L24.8,-40.6L24.8,-40.6ZM23.5,-37.9L23.5,-37.9L23.5,-37.9ZM23.1,-36.2L23.1,-36.2L23.1,-36.2ZM27.2,-35.5L27.2,-35.5L27.2,-35.5ZM27,-37L27,-37L27,-37ZM26.9,-36.7L26.9,-36.7L26.9,-36.7ZM25.5,-37L25.5,-37L25.5,-37ZM25.3,-37.1L25.3,-37.1L25.3,-37.1ZM25.5,-36.4L25.5,-36.4L25.5,-36.4ZM25.4,-36.7L25.4,-36.7L25.4,-36.7ZM26.8,-37.8L26.8,-37.8L26.8,-37.8ZM26,-37.5L26,-37.5L26,-37.5ZM25.9,-36.8L25.9,-36.8L25.9,-36.8ZM26.5,-36.6L26.5,-36.6L26.5,-36.6ZM24.4,-37.6L24.4,-37.6L24.4,-37.6ZM24.4,-37.3L24.4,-37.3L24.4,-37.3ZM24.5,-36.8L24.5,-36.8L24.5,-36.8ZM24.9,-37.5L24.9,-37.5L24.9,-37.5ZM25,-37.8L25,-37.8L25,-37.8ZM25.3,-37.6L25.3,-37.6L25.3,-37.6ZM24.7,-36.9L24.7,-36.9L24.7,-36.9ZM26.1,-38.2L26.1,-38.2L26.1,-38.2ZM26.4,-39.3L26.4,-39.3L26.4,-39.3ZM25.7,-40.4L25.7,-40.4L25.7,-40.4ZM25.4,-40L25.4,-40L25.4,-40ZM25.4,-37.4L25.4,-37.4L25.4,-37.4ZM24.5,-37.1L24.5,-37.1L24.5,-37.1ZM27.8,-35.9L27.8,-35.9L27.8,-35.9ZM23.9,-35.5L25.5,-35.3L26.2,-35L24.8,-34.9L23.5,-35.4ZM13.7,-54.4L13.7,-54.4L13.7,-54.4ZM11.3,-54.4L11.3,-54.4L11.3,-54.4ZM8.3,-54.8L8.3,-54.8L8.3,-54.8ZM8.6,-54.7L8.6,-54.7L8.6,-54.7ZM9.5,-42.8L9.6,-42.2L9.2,-41.4L8.8,-41.6L8.6,-42.4ZM-1.2,-45.9L-1.2,-45.9L-1.2,-45.9ZM45.2,13L45.2,13L45.2,13ZM55.8,21.3L55.8,21.3L55.8,21.3ZM-60.8,-14.5L-60.8,-14.5L-60.8,-14.5ZM-61.3,-16.2L-61.3,-16.2L-61.3,-16.2ZM-61.6,-16L-61.6,-16L-61.6,-16ZM-61.2,-15.9L-61.2,-15.9L-61.2,-15.9ZM-56.2,-46.8L-56.2,-46.8L-56.2,-46.8ZM-56.3,-46.8L-56.3,-46.8L-56.3,-46.8ZM-176.2,13.3L-176.2,13.3L-176.2,13.3ZM-178,14.3L-178,14.3L-178,14.3ZM-63.1,-18.1L-63,-18.1L-63.1,-18.1ZM-62.8,-17.9L-62.8,-17.9L-62.8,-17.9ZM-151.5,16.7L-151.5,16.7L-151.5,16.7ZM-149.8,17.5L-149.8,17.5L-149.8,17.5ZM-151.4,16.9L-151.4,16.9L-151.4,16.9ZM-149.3,17.7L-149.3,17.7L-149.3,17.7ZM-139,9.7L-139,9.7L-139,9.7ZM-139.1,9.9L-139.1,9.9L-139.1,9.9ZM-138.6,10.5L-138.6,10.5L-138.6,10.5ZM-140.1,8.9L-140.1,8.9L-140.1,8.9ZM-140.1,9.4L-140.1,9.4L-140.1,9.4ZM-140.8,17.9L-140.8,17.9L-140.8,17.9ZM-139.6,8.9L-139.6,8.9L-139.6,8.9ZM-140.7,18.4L-140.7,18.4L-140.7,18.4ZM-140.8,18.2L-140.8,18.2L-140.8,18.2ZM-136.3,18.5L-136.3,18.5L-136.3,18.5ZM-137,18.3L-137,18.3L-137,18.3ZM-138.5,20.9L-138.5,20.9L-138.5,20.9ZM-142.5,16.1L-142.5,16.1L-142.5,16.1ZM-143.4,16.6L-143.4,16.6L-143.4,16.6ZM-143.6,16.6L-143.6,16.6L-143.6,16.6ZM-145.1,15.9L-145.1,15.9L-145.1,15.9ZM-145.5,16.3L-145.5,16.3L-145.5,16.3ZM164.2,20.2L165.2,20.8L165.7,21.3L166.9,22.1L166.8,22.4L164.9,21.3ZM167.5,22.6L167.5,22.6L167.5,22.6ZM160,19.3L160,19.3L160,19.3ZM168,21.4L168,21.4L168,21.4ZM166.5,20.7L166.5,20.7L166.5,20.7ZM167.4,21.2L167.4,21.2L167.4,21.2ZM69.2,49.1L70.3,49.1L70.1,49.7L68.8,49.7L69.1,48.7ZM69.3,49.1L69.3,49.1L69.3,49.1ZM51.8,46.4L51.8,46.4L51.8,46.4ZM20,-60.4L20,-60.4L20,-60.4ZM19.7,-60.2L19.7,-60.2L19.7,-60.2ZM20.6,-60L20.6,-60L20.6,-60ZM22,-60.3L22,-60.3L22,-60.3ZM21.2,-63.2L21.2,-63.2L21.2,-63.2ZM22.2,-60.4L22.2,-60.4L22.2,-60.4ZM21.5,-60.5L21.5,-60.5L21.5,-60.5ZM21.8,-60.1L21.8,-60.1L21.8,-60.1ZM21.6,-60.1L21.6,-60.1L21.6,-60.1ZM24.8,-65L24.8,-65L24.8,-65ZM180,16.2L179.6,16.7L178.7,17L178.6,16.6ZM178.3,17.4L178.7,18.1L177.8,18.3L177.3,18.1L177.6,17.5ZM-180,16.8L-180,16.8L-180,16.8ZM180,17L180,17L180,17ZM178.5,19L178.5,19L178.5,19ZM-179,18L-179,18L-179,18ZM-178.8,18.2L-178.8,18.2L-178.8,18.2ZM-178.3,18L-178.3,18L-178.3,18ZM-179,17.3L-179,17.3L-179,17.3ZM-178.5,19.2L-178.5,19.2L-178.5,19.2ZM-179.8,18.9L-179.8,18.9L-179.8,18.9ZM177.2,17.1L177.2,17.1L177.2,17.1ZM179.4,17.4L179.4,17.4L179.4,17.4ZM179.3,18.1L179.3,18.1L179.3,18.1ZM178.8,17.7L178.8,17.7L178.8,17.7ZM-180,16.5L-180,16.5L-180,16.5L-180,16.5L-180,16.5ZM180,16.5L180,16.5L180,16.5L180,16.5L180,16.5L180,16.5ZM-180,16.2L-180,16.2L-180,16.2ZM177.1,12.5L177.1,12.5L177.1,12.5ZM174.6,21.7L174.6,21.7L174.6,21.7ZM-178.7,20.7L-178.7,20.7L-178.7,20.7ZM22.6,-58.6L23.3,-58.5L22.2,-58.2L21.9,-58.5ZM22.9,-58.8L22.9,-58.8L22.9,-58.8ZM23.3,-58.6L23.3,-58.6L23.3,-58.6ZM40.1,-16.1L40.1,-16.1L40.1,-16.1ZM40.1,-15.7L40.1,-15.7L40.1,-15.7ZM8.7,-3.8L8.7,-3.8L8.7,-3.8ZM-80.1,3L-80.1,3L-80.1,3ZM-78.9,-1.3L-78.9,-1.3L-78.9,-1.3ZM-90.3,0.8L-90.3,0.8L-90.3,0.8ZM-89.4,0.9L-89.4,0.9L-89.4,0.9ZM-91.4,0.5L-91.4,0.5L-91.4,0.5ZM-90.4,1.3L-90.4,1.3L-90.4,1.3ZM-91.3,0L-91.3,0L-91.3,0ZM-90.6,0.3L-90.6,0.3L-90.6,0.3ZM-61.3,-15.2L-61.3,-15.2L-61.3,-15.2ZM-30,-83.6L-25.9,-83.3L-26.2,-83.2L-32,-83.1L-27,-83.1L-25.1,-83.2L-24.5,-82.9L-22.5,-82.8L-21.5,-82.6L-23.9,-82.3L-29.6,-82.2L-29.8,-82L-27.8,-82L-25.1,-82L-24.3,-81.7L-23.1,-82L-21.3,-82.1L-21.2,-81.6L-23.1,-80.9L-21.9,-81L-20,-81.6L-17.5,-81.4L-15.6,-81.8L-12.4,-81.7L-11.4,-81.5L-13.5,-81L-14.5,-81L-14.5,-80.8L-16.8,-80.6L-15.9,-80.4L-16.9,-80.2L-19.4,-80.3L-20.1,-79.8L-19.3,-79.7L-19.1,-79.2L-21,-78.6L-21.7,-77.8L-20.9,-77.9L-19.5,-77.7L-20.7,-77.6L-20.2,-77.4L-18.3,-77.2L-18.5,-76.8L-20.9,-76.9L-21.9,-76.6L-21.4,-76.3L-20.1,-76.2L-19.4,-75.4L-19.8,-75.2L-20.5,-75.3L-21,-75.1L-20.6,-74.7L-20,-75L-19.2,-74.5L-19.4,-74.3L-21.1,-74.1L-22.3,-74.3L-22,-74L-20.4,-73.8L-20.5,-73.5L-22.2,-73.3L-23,-73.3L-24.2,-73.8L-24.8,-73.5L-26.8,-73.1L-24.6,-73.4L-23.9,-73.4L-22,-72.9L-22.3,-72.1L-24.1,-72.5L-24.6,-73L-26.7,-72.7L-24.8,-72.9L-24.7,-72.4L-22,-71.7L-21.5,-70.5L-22.7,-70.4L-24,-70.6L-24.6,-71.2L-25.9,-71.6L-25.7,-71.2L-26.7,-71L-28.3,-71L-28.1,-70.7L-29,-70.5L-26.5,-70.4L-27.6,-70.1L-25.5,-70.4L-23.7,-70.1L-22.3,-70.1L-23,-69.8L-25.5,-69L-26.5,-68.7L-30.6,-68.1L-31.4,-68.1L-32.3,-68.4L-32.2,-68L-33.2,-67.6L-34.1,-66.7L-36.4,-65.8L-38,-65.7L-37.3,-66.3L-37.8,-66.3L-38.6,-65.6L-40.2,-65.5L-39.6,-65.3L-40.3,-65L-41.1,-65.1L-40.2,-64.5L-40.8,-64.2L-40.5,-63.7L-42.1,-62.7L-42.7,-60.8L-43.3,-60.4L-43.1,-60.1L-44.1,-59.8L-45.4,-60.2L-46,-60.6L-45.8,-61.2L-46.9,-60.8L-48.2,-60.9L-48.9,-61.3L-49.6,-62.2L-50.3,-62.5L-50.4,-62.8L-51.5,-63.6L-51.4,-64.6L-51.9,-64.2L-52.3,-65.5L-53.2,-65.6L-52.9,-66.2L-53.6,-66.2L-53,-66.8L-53.9,-67.1L-53.8,-67.4L-52.7,-67.7L-51.2,-67.6L-51,-67.8L-52.3,-67.8L-53.7,-67.5L-53.2,-68.2L-51.6,-68.1L-51.2,-68.3L-53.4,-68.3L-53,-68.6L-51.6,-68.5L-51.2,-68.7L-50.7,-69.7L-50.3,-70L-52.3,-70.1L-54,-70.4L-54.2,-70.8L-52.8,-70.8L-51.5,-70.4L-51.4,-71.1L-53,-71.2L-52.7,-71.5L-53.4,-71.6L-54.7,-71.4L-55.6,-71.6L-55.3,-72.1L-55.6,-72.5L-54.7,-72.9L-55.7,-73.1L-55.3,-73.3L-56.1,-73.6L-55.9,-73.9L-56.7,-74.2L-56.3,-74.5L-58.6,-75.4L-58.5,-75.7L-61.4,-76.2L-63.4,-76.3L-65.5,-76.1L-67.1,-76.2L-66.7,-76L-68.2,-76.1L-69.4,-76.4L-68.2,-76.7L-70.4,-76.8L-70.9,-77.2L-69,-77.2L-68.6,-77.3L-66.4,-77.3L-66.7,-77.7L-69.4,-77.5L-72.1,-77.9L-72.8,-78.2L-72.4,-78.5L-69,-78.9L-67.4,-79.1L-66,-79.1L-65.4,-79.3L-64.5,-80.1L-65.8,-80L-67.1,-80.1L-66.6,-80.5L-64.5,-81L-63.1,-80.9L-63,-81.2L-61.4,-81.1L-61.2,-81.7L-59.9,-81.9L-56.9,-81.5L-59.3,-82L-54.7,-82.4L-53,-81.9L-53,-82.3L-50.9,-81.9L-49.5,-81.9L-51,-82.5L-48.9,-82.4L-45.3,-81.8L-44.5,-81.8L-44.2,-82.4L-45.6,-82.7L-45.1,-82.8L-41.4,-82.8L-44.8,-82.9L-46.1,-82.9L-43.2,-83.3L-41.3,-83.1L-40.4,-83.3L-38.3,-83L-38.7,-83.4L-37.8,-83.5L-33,-83.6ZM-52.7,-69.9L-52,-69.8L-52.1,-69.5L-53.6,-69.3L-53.8,-69.5L-54.9,-69.7L-54.4,-70.3L-53.4,-70.2ZM-51,-69.6L-51,-69.6L-51,-69.6ZM-53.5,-71L-53.5,-71L-53.5,-71ZM-55,-72.8L-55.5,-72.6L-56.2,-72.7ZM-71.7,-77.3L-71.7,-77.3L-71.7,-77.3ZM-44.9,-82.1L-46.8,-82.3L-47.3,-82.7L-46.4,-82.7L-44.8,-82.4ZM-25.4,-70.9L-25.4,-70.7L-27.9,-70.5L-27.7,-70.9L-25.8,-71ZM-18.7,-81.8L-18.7,-81.8L-18.7,-81.8ZM-17.6,-79.8L-19,-79.8L-19,-79.9L-17.5,-80ZM-19,-78L-19,-78L-19,-78ZM-18.6,-76L-19.1,-76.4L-18.7,-76.6ZM-18,-75.4L-17.6,-75L-18.7,-75L-18.9,-75.3ZM-18,-77.6L-18,-77.6L-18,-77.6ZM-37,-65.5L-37,-65.5L-37,-65.5ZM-46.3,-60.8L-46.3,-60.8L-46.3,-60.8ZM-51.7,-70.9L-51.7,-70.9L-51.7,-70.9ZM-6.6,-61.8L-6.6,-61.8L-6.6,-61.8ZM-6.7,-61.4L-6.7,-61.4L-6.7,-61.4ZM-7.2,-62.1L-7.2,-62.1L-7.2,-62.1ZM-6.6,-62.2L-6.6,-62.2L-6.6,-62.2ZM-6.4,-62.3L-6.4,-62.3L-6.4,-62.3ZM12.6,-55.8L11.9,-54.8L11,-55.7L12.6,-56.1ZM10.6,-55.6L10.8,-55.1L10,-55.2L9.9,-55.5ZM11.4,-54.9L11.4,-54.9L11.4,-54.9ZM10.7,-54.8L10.7,-54.8L10.7,-54.8ZM12.5,-55L12.5,-55L12.5,-55ZM12.7,-55.6L12.7,-55.6L12.7,-55.6ZM10.5,-54.8L10.5,-54.8L10.5,-54.8ZM10.1,-54.9L10.1,-54.9L10.1,-54.9ZM10.6,-55.8L10.6,-55.8L10.6,-55.8ZM11.1,-57.3L11.1,-57.3L11.1,-57.3ZM15.1,-55L15.1,-55L15.1,-55ZM32.7,-35.2L34.6,-35.7L34,-35.1L32.9,-34.6L32.3,-35ZM-81.8,-23.2L-80.6,-23.1L-79.3,-22.4L-78.7,-22.4L-76.6,-21.3L-75.6,-21L-74.2,-20.3L-75.1,-19.9L-76.2,-20L-77.7,-19.9L-77.2,-20.6L-78,-20.7L-78.6,-21.5L-79.3,-21.6L-80.5,-22.1L-81.8,-22.2L-81.9,-22.7L-82.7,-22.7L-83.4,-22.2L-84.5,-21.8L-84.4,-22.4L-83.3,-23ZM-77.7,-22L-77.7,-22L-77.7,-22ZM-78,-22.3L-78,-22.3L-78,-22.3ZM-78.6,-22.6L-78.6,-22.6L-78.6,-22.6ZM-77.9,-22.1L-77.9,-22.1L-77.9,-22.1ZM-82.6,-21.6L-82.6,-21.6L-82.6,-21.6ZM-79.4,-22.7L-79.4,-22.7L-79.4,-22.7ZM16.7,-43L16.7,-43L16.7,-43ZM17.2,-43.1L17.2,-43.1L17.2,-43.1ZM16.8,-43.3L16.8,-43.3L16.8,-43.3ZM15.2,-44.1L15.2,-44.1L15.2,-44.1ZM14.8,-45L14.8,-45L14.8,-45ZM14.8,-44.8L14.8,-44.8L14.8,-44.8ZM15.2,-44.3L15.2,-44.3L15.2,-44.3ZM15.2,-43.9L15.2,-43.9L15.2,-43.9ZM15.4,-44L15.4,-44L15.4,-44ZM14.5,-44.7L14.5,-44.7L14.5,-44.7ZM17.6,-42.8L17.6,-42.8L17.6,-42.8ZM44.5,12.1L44.5,12.1L44.5,12.1ZM43.8,12.3L43.8,12.3L43.8,12.3ZM43.5,11.9L43.5,11.9L43.5,11.9ZM-78.1,-2.5L-78.1,-2.5L-78.1,-2.5ZM118.2,-24.5L118.2,-24.5L118.2,-24.5ZM121.9,-31.5L121.9,-31.5L121.9,-31.5ZM122.3,-30L122.3,-30L122.3,-30ZM122.2,-29.7L122.2,-29.7L122.2,-29.7ZM122.4,-29.9L122.4,-29.9L122.4,-29.9ZM119.8,-25.5L119.8,-25.5L119.8,-25.5ZM110.4,-21.1L110.4,-21.1L110.4,-21.1ZM121.3,-28.1L121.3,-28.1L121.3,-28.1ZM113.6,-22.8L113.6,-22.8L113.6,-22.8ZM112.8,-21.6L112.8,-21.6L112.8,-21.6ZM112.6,-21.6L112.6,-21.6L112.6,-21.6ZM110.9,-20L111,-19.7L110.5,-18.7L109.5,-18.2L108.7,-18.5L108.7,-19.3L109.3,-19.9L110.7,-20.1ZM114.2,-22.2L114.2,-22.2L114.2,-22.2ZM114,-22.2L114,-22.2L114,-22.2ZM-109.3,27.1L-109.3,27.1L-109.3,27.1ZM-78.8,33.6L-78.8,33.6L-78.8,33.6ZM-68.7,54.9L-69.7,54.7L-70.5,54.8L-71.6,54.5L-70.7,54.3L-70.9,53.9L-70.2,54.4L-69,54.4L-70,54.1L-70.1,53.8L-69.4,53.5L-70.5,53.2L-69.5,52.5L-68.6,52.7L-68.5,53.3L-67.3,54L-66.2,54.5L-65.2,54.7L-66.5,55ZM-67.1,55.2L-68.1,55.2L-68.3,55ZM-73.8,43.3L-74.4,43.2L-74,41.8L-73.5,41.9L-73.4,42.9ZM-74.5,49.1L-74.6,50L-75,49.5L-75.5,49.8L-74.8,48.7ZM-75.5,48.8L-75.4,48L-75.2,48.6ZM-74.4,52.9L-74.4,52.9L-74.4,52.9ZM-74.6,48.6L-74.9,48.6L-75.2,48L-74.8,47.9ZM-72.9,53.5L-72.2,53.8L-73.3,53.9L-73.8,53.5ZM-74.8,51.6L-74.8,51.6L-74.8,51.6ZM-69.7,54.9L-68.3,55.3L-68,55.6ZM-71.4,54L-71.1,54.4L-71.9,54.3L-72,53.9ZM-73.7,44.4L-73.7,45.1L-74.1,45.3L-74.6,44.6L-73.9,44.1ZM-73,44.8L-73,44.8L-73,44.8ZM-75,44.9L-75,44.9L-75,44.9ZM-75.3,50.7L-75.3,50.7L-75.3,50.7ZM-75.1,48.8L-75.1,48.8L-75.1,48.8ZM-75.1,47.8L-75.1,47.8L-75.1,47.8ZM-74.7,43.6L-74.7,43.6L-74.7,43.6ZM-73.6,44.8L-73.6,44.8L-73.6,44.8ZM-74.6,51.3L-74.6,51.3L-74.6,51.3ZM-75.1,50.3L-75.1,50.3L-75.1,50.3ZM-73.8,43.8L-73.8,43.8L-73.8,43.8ZM-74.1,51.9L-74.1,51.9L-74.1,51.9ZM-74.3,45.7L-74.3,45.7L-74.3,45.7ZM-67.6,55.9L-67.6,55.9L-67.6,55.9ZM-66.5,55.2L-66.5,55.2L-66.5,55.2ZM-71,54.9L-71,54.9L-71,54.9ZM-67.3,55.8L-67.3,55.8L-67.3,55.8ZM-25.2,-16.9L-25.2,-16.9L-25.2,-16.9ZM-23.4,-15L-23.4,-15L-23.4,-15ZM-24.9,-16.8L-24.9,-16.8L-24.9,-16.8ZM-22.9,-16.2L-22.9,-16.2L-22.9,-16.2ZM-24.3,-14.9L-24.3,-14.9L-24.3,-14.9ZM-24.1,-16.6L-24.1,-16.6L-24.1,-16.6ZM-22.9,-16.7L-22.9,-16.7L-22.9,-16.7ZM-23.2,-15.1L-23.2,-15.1L-23.2,-15.1ZM-132.7,-54.1L-131.7,-54.1L-132,-53.3L-132.8,-53.5L-133,-54.2ZM-131.8,-53.2L-131.2,-52.2L-132.5,-53.1ZM-127.2,-50.6L-125.5,-50.3L-124.6,-49.4L-124,-49.2L-123.6,-48.3L-125.1,-48.8L-126.3,-49.7L-127.2,-50.1L-127.9,-50.1L-128.3,-50.7ZM-109.8,-78.7L-109.4,-78.3L-111.4,-78.3L-113.2,-78.4L-110.4,-78.8ZM-110.5,-78.1L-109.8,-78L-110.9,-77.8L-110.2,-77.5L-112,-77.3L-113.2,-77.5L-113.2,-77.9ZM-115.6,-77.4L-116.3,-77.1L-116.2,-76.6L-117.2,-76.3L-118,-76.4L-117.8,-76.8L-118.8,-76.5L-119.2,-76.1L-119.5,-76.3L-119.9,-75.9L-121,-76L-122.4,-75.9L-122.4,-76.4L-121.6,-76.4L-119.1,-77.3ZM-108.3,-76.1L-108,-75.8L-106.4,-76.1L-105.5,-75.7L-105.9,-75.2L-107.2,-74.9L-108.8,-75.1L-111.7,-74.5L-113,-74.4L-114.4,-74.7L-111,-75.2L-113.7,-75.1L-114,-75.4L-114.5,-75.1L-115.7,-75L-117.5,-75.2L-117.2,-75.5L-115.1,-75.7L-117,-75.6L-116.6,-76.1L-115.6,-76.4L-114.2,-76.5L-113.8,-76.2L-112.7,-76.2L-111.1,-75.5L-109.1,-75.5L-109.8,-75.9L-109.5,-76L-110.3,-76.3L-109.3,-76.8L-108.5,-76.7ZM-114.5,-72.6L-113.5,-72.7L-113.2,-73L-111.3,-72.7L-111.9,-72.4L-110.2,-72.7L-110.7,-73L-110,-73L-108.7,-72.5L-108.2,-71.8L-107.3,-71.9L-107.7,-72.1L-108.2,-73.1L-108,-73.3L-105.8,-73L-104.4,-71.6L-104.6,-71.1L-104,-70.8L-103,-70.7L-101,-70L-100.9,-69.7L-102.2,-69.8L-102.6,-69.6L-103.4,-69.7L-103.1,-69.2L-102,-69.4L-101.9,-69L-102.9,-68.8L-105.1,-68.9L-106.7,-69.4L-107.4,-69L-108.9,-68.8L-111.3,-68.5L-113.1,-68.5L-113.7,-69.2L-116.5,-69.4L-117.1,-70.1L-114.6,-70.3L-112.6,-70.2L-111.6,-70.3L-113.8,-70.7L-116,-70.6L-117.6,-70.6L-118.4,-71L-117.9,-71.1L-115.9,-71.4L-115.6,-71.5L-117.7,-71.4L-117.7,-71.7L-118.9,-71.7L-118.5,-72.4L-117.3,-72.9L-114.6,-73.4L-114.2,-73.3ZM-119.7,-74.1L-118.5,-74.2L-117.2,-74.2L-115.5,-73.6L-115.4,-73.4L-119,-72.7L-120.2,-72.2L-120.6,-71.5L-121.7,-71.4L-122.8,-71.1L-124,-71.7L-125.8,-72L-125,-72.6L-124.8,-73.1L-123.8,-73.8L-124.7,-74.3L-121.7,-74.5L-119.6,-74.2ZM-69.5,-83L-66.4,-82.9L-68.5,-82.7L-67.4,-82.7L-64.9,-82.9L-63.6,-82.8L-63.1,-82.6L-61.5,-82.5L-61.3,-82.3L-62.2,-82L-64.6,-81.7L-66.6,-81.6L-68.3,-81.3L-65.7,-81.5L-65.5,-81.3L-68.6,-80.7L-70.3,-80.2L-71.4,-79.8L-73.5,-79.8L-73.4,-79.5L-75.5,-79.4L-76.9,-79.5L-74.5,-79.1L-75.9,-79.1L-78.6,-79.1L-77.9,-78.9L-76.3,-79L-74.4,-78.7L-74.9,-78.5L-76.4,-78.5L-75.2,-78.3L-75.9,-78L-78,-77.9L-78.1,-77.5L-78.7,-77.3L-81.1,-77.3L-78.3,-77L-78.3,-76.6L-80.7,-76.2L-80.8,-76.4L-81.8,-76.5L-83.9,-76.5L-85.1,-76.3L-86.5,-76.6L-86.7,-76.4L-89.6,-76.5L-89.5,-76.8L-88.4,-77.1L-86.9,-77.2L-88.1,-77.7L-87,-77.9L-85.6,-77.5L-85.5,-77.9L-84.6,-78.2L-85,-78.3L-86.2,-78.1L-85.9,-78.3L-87.6,-78.2L-86.8,-78.8L-85.2,-78.9L-83.3,-78.8L-82.4,-78.9L-83.6,-79.1L-85.1,-79.6L-86.4,-79.8L-86.3,-80.3L-83.7,-80.2L-81.9,-79.7L-81,-79.7L-83,-80.3L-80.1,-80.5L-79.6,-80.6L-76.9,-80.9L-78.6,-80.9L-78.3,-81.2L-81,-80.7L-82.9,-80.6L-82.2,-80.8L-84.1,-80.6L-86.6,-80.7L-85.2,-81L-85.8,-81L-87.3,-80.7L-88.9,-80.8L-88.4,-81L-86.5,-81L-84.9,-81.3L-87.3,-81.1L-89.6,-81L-89.9,-81.2L-88.5,-81.6L-90.3,-81.4L-89.8,-81.6L-91.7,-81.6L-90.5,-81.9L-88.6,-82.1L-85.3,-82L-86.6,-82.2L-84.9,-82.4L-82.6,-82.2L-79.4,-81.9L-82,-82.3L-82.1,-82.6L-81.2,-82.7L-78.7,-82.7L-80.2,-82.9L-77.6,-82.9L-76,-82.5L-75.6,-82.6L-77.1,-83L-74.4,-83L-73.4,-82.9L-72.8,-83.1ZM-95.5,-77.8L-93.6,-77.8L-93.5,-77.5L-96,-77.5ZM-93.5,-75L-93.5,-74.7L-94.7,-74.6L-96.6,-75.1L-95.7,-75.5L-94.4,-75.6ZM-100,-73.9L-99.2,-73.7L-97.6,-73.9L-97,-73.7L-97.3,-73.4L-98.4,-73L-97.5,-73L-97.1,-72.6L-96.5,-72.7L-96.6,-71.8L-97.6,-71.6L-98.5,-71.8L-98.2,-71.4L-99.2,-71.4L-100.6,-72.2L-101.7,-72.3L-102.7,-72.8L-101.9,-73.1L-101.4,-72.7L-100.1,-73L-100.4,-73.3L-101.5,-73.4L-100.9,-73.8ZM-84.9,-65.3L-84.6,-65.4L-82.1,-64.6L-81.7,-64.1L-80.8,-64.1L-80.3,-63.8L-81,-63.5L-82.4,-63.7L-82.5,-63.9L-83.6,-64.1L-84.6,-63.3L-85.5,-63.1L-85.8,-63.7L-87.2,-63.6L-86.3,-64.1L-86.4,-64.6L-86,-65.7L-85.6,-65.9ZM-97.7,-76.5L-97.3,-75.4L-97.7,-75.1L-100.2,-75L-100.7,-75.3L-99.6,-75.7L-102.5,-75.5L-101.9,-75.9L-101.3,-75.8L-102.1,-76.3L-101.9,-76.4L-100,-75.9L-100.9,-76.5L-98.7,-76.7ZM-103.4,-79.3L-102.6,-78.9L-101.7,-79.1L-99.6,-78.6L-99.8,-78.3L-99.2,-77.9L-100.6,-77.9L-101.1,-78.2L-102.7,-78.4L-104.3,-78.3L-105,-78.5L-103.8,-78.5L-104.2,-79L-104.8,-78.8L-105.5,-79L-105.4,-79.3ZM-91.9,-81.1L-90.6,-80.6L-87.7,-80.4L-87.9,-80.1L-87,-79.9L-87.3,-79.6L-85.6,-79.6L-85.3,-79.2L-87.6,-78.7L-88.1,-79L-88.1,-78.5L-88.7,-78.6L-88.8,-78.2L-90,-78.6L-89.5,-78.2L-91.9,-78.2L-94.2,-79L-91.3,-79.4L-92.8,-79.5L-95.1,-79.3L-95.7,-79.5L-94.5,-79.7L-96,-79.7L-96.8,-80.1L-94.6,-80L-96.4,-80.3L-95.6,-80.4L-96.1,-80.7L-93.9,-80.6L-95.5,-80.8L-95.3,-81L-93.4,-81.2L-93.3,-81.4ZM-94.3,-76.9L-93,-76.6L-91.8,-76.7L-89.4,-76.2L-91.3,-76.2L-90.3,-76.1L-88.9,-75.5L-87.3,-75.6L-86.1,-75.5L-83.9,-75.8L-82.2,-75.8L-80.3,-75.6L-79.6,-75.2L-80.4,-75.1L-79.4,-74.9L-80.3,-74.6L-81.8,-74.5L-82.9,-74.6L-88.4,-74.5L-88.3,-74.8L-89.8,-74.5L-92,-74.8L-92.4,-75.4L-92.2,-75.8L-93.1,-76.4L-95.3,-76.3L-96.9,-76.7L-95.8,-77.1ZM-96.2,-78.5L-94.9,-78.3L-95.1,-78L-97,-77.8L-98.3,-78.4L-98.2,-78.8ZM-93.2,-74.2L-92.2,-74L-90.4,-73.9L-92.1,-72.8L-94.2,-72.8L-93.6,-72.4L-94,-72L-95.2,-72L-95.5,-72.8L-95.6,-73.7L-94.8,-73.7L-95.1,-74ZM-97.4,-69.6L-96.3,-69.3L-95.7,-68.7L-96.4,-68.5L-97.5,-68.5L-98.3,-68.8L-99.4,-68.9L-99.5,-69.1L-98.5,-69.3L-98.3,-69.8ZM-61.1,-45.9L-60.3,-46.3L-59.8,-46L-60.4,-45.7L-61.3,-45.6L-61.5,-45.9L-60.9,-46.8L-60.4,-47L-60.6,-46.2ZM-55.5,-51.5L-56,-51.3L-55.8,-51L-56.7,-50.1L-55.5,-50L-56.1,-49.5L-54.5,-49.5L-53.6,-49.1L-54.2,-48.8L-54.1,-48.4L-53.1,-48.7L-53.9,-47.8L-52.7,-47.5L-53.1,-46.7L-53.6,-46.7L-53.6,-47.1L-54.2,-46.9L-53.9,-47.4L-54.2,-47.9L-55.3,-46.9L-55.8,-46.9L-54.9,-47.6L-55.9,-47.5L-55.9,-47.8L-57,-47.6L-58.3,-47.7L-59.1,-47.6L-59.3,-48L-58.3,-48.5L-58.7,-48.6L-57.3,-50.7L-56.7,-51.3ZM-86.6,-71L-85.1,-71.2L-84.7,-71.6L-85.9,-72L-85.3,-72.2L-85.6,-72.8L-85,-73.3L-83.8,-73.4L-82.7,-73.7L-81.4,-73.6L-80.3,-72.7L-81.2,-72.3L-80.9,-71.9L-80,-72.4L-78.3,-72.4L-78.3,-72.6L-76.9,-72.7L-75.3,-72.5L-74.9,-72.1L-74.3,-72L-74.4,-71.7L-72.9,-71.7L-71.6,-71.5L-71.5,-71.1L-70.8,-71.1L-71.3,-70.5L-70,-70.8L-68.4,-70.5L-70.1,-70.1L-68.1,-70.3L-67.2,-69.7L-68.5,-69.6L-67.4,-69.5L-66.8,-69.2L-68.6,-69.2L-67.8,-69L-68,-68.6L-66.2,-68.3L-66.4,-67.8L-65,-68L-63.8,-67.3L-63,-67.2L-63.7,-66.8L-62,-67L-61.3,-66.6L-62,-66L-62.6,-66L-62.7,-65.6L-63.3,-65.6L-63.6,-64.9L-64.6,-65.1L-65.4,-65.8L-66.8,-66.6L-67.2,-66L-67.9,-65.8L-66.7,-65L-65.9,-64.9L-64.7,-64L-64.5,-63.3L-65.2,-63.8L-64.7,-62.9L-65.2,-62.6L-66.2,-63.1L-68.9,-63.7L-66,-62.2L-66.3,-61.9L-69.1,-62.4L-69.5,-62.7L-71.3,-63L-73.4,-64.4L-74.9,-64.8L-74.6,-64.6L-76.7,-64.2L-77.8,-64.4L-78.1,-64.9L-77.3,-65.5L-75.7,-65.3L-73.6,-65.5L-74.4,-66.1L-72.2,-67.3L-73.3,-68.4L-74.4,-68.6L-74.9,-69L-76.6,-68.7L-76.6,-69L-75.8,-69.3L-76.5,-69.7L-77.6,-69.8L-77.8,-70.2L-79.1,-70.6L-79.3,-70.4L-78.8,-70L-79.3,-69.9L-81.1,-70.1L-82.1,-69.8L-86.3,-70.1L-86.6,-70.4L-87.9,-70.3L-88.8,-70.5L-89.5,-71.1L-87.2,-71L-87.9,-71.2L-89.8,-71.5L-89.9,-72.4L-89.3,-73.1L-87.7,-73.7L-86.8,-73.8L-85,-73.7L-86.1,-73.3L-86.7,-72.8L-86,-71.8L-85,-71.4ZM-61.8,-49.1L-63.6,-49.4L-64.4,-49.8L-64.1,-49.9L-62.9,-49.7ZM-63.8,-46.5L-62.2,-46.5L-62.9,-46ZM-82,-63L-82.1,-62.7L-83,-62.2L-83.7,-62.2L-83.9,-62.5L-83.4,-62.9ZM-79.5,-62.4L-79.3,-62.2L-79.7,-61.6L-80.2,-62.2ZM-75.7,-68.3L-75.2,-68.2L-75.1,-67.5L-75.8,-67.3L-77,-67.3L-77.3,-67.7L-76.7,-68.2ZM-79.5,-73.7L-78.3,-73.7L-77.2,-73.5L-76.3,-73.1L-76.4,-72.8L-77.8,-72.9L-79.5,-72.8L-80.8,-73.4L-80.8,-73.7ZM-80.7,-52.7L-82,-53L-81.1,-53.2ZM-78.8,-56.1L-78.8,-56.1L-78.8,-56.1ZM-78.9,-56.3L-80,-55.9L-79.3,-56.6ZM-80,-56.2L-80,-56.2L-80,-56.2ZM-89.8,-77.3L-91.1,-77.4L-91.2,-77.6L-90.2,-77.6ZM-104.6,-77.1L-105.2,-77.2L-106.1,-77.7L-104.5,-77.3ZM-98.8,-80L-98.8,-79.7L-100,-79.9L-99.8,-80.1ZM-105.3,-72.9L-106.9,-73.5L-106.6,-73.7L-105.5,-73.8L-104.6,-73.6ZM-102.2,-76L-103.3,-75.8L-104.3,-76.2L-102.6,-76.3ZM-104,-76.6L-103.1,-76.4L-104.3,-76.3ZM-118.3,-75.6L-119.4,-75.6L-117.8,-76.1ZM-113.8,-77.8L-115,-78L-114.3,-78.1ZM-130.9,-54.5L-130.9,-54.5L-130.9,-54.5ZM-131,-52L-131,-52L-131,-52ZM-130.2,-54L-130.2,-54L-130.2,-54ZM-129.8,-53.2L-129.8,-53.2L-129.8,-53.2ZM-128.6,-52.9L-128.6,-52.9L-128.6,-52.9ZM-126.1,-49.4L-126.1,-49.4L-126.1,-49.4ZM-124.2,-49.5L-124.2,-49.5L-124.2,-49.5ZM-126.6,-49.6L-126.6,-49.6L-126.6,-49.6ZM-125.2,-50.1L-125.2,-50.1L-125.2,-50.1ZM-128.9,-52.5L-128.9,-52.5L-128.9,-52.5ZM-127.9,-51.5L-127.9,-51.5L-127.9,-51.5ZM-128.4,-52.4L-128.4,-52.4L-128.4,-52.4ZM-129.3,-53L-129.3,-53L-129.3,-53ZM-129.2,-53.1L-129.2,-53.1L-129.2,-53.1ZM-123.4,-48.8L-123.4,-48.8L-123.4,-48.8ZM-59.8,-43.9L-59.8,-43.9L-59.8,-43.9ZM-61,-45.5L-61,-45.5L-61,-45.5ZM-61.9,-47.3L-61.9,-47.3L-61.9,-47.3ZM-64.5,-47.9L-64.5,-47.9L-64.5,-47.9ZM-64.5,-48L-64.5,-48L-64.5,-48ZM-66.3,-44.3L-66.3,-44.3L-66.3,-44.3ZM-66.8,-44.7L-66.8,-44.7L-66.8,-44.7ZM-73.6,-45.5L-73.6,-45.5L-73.6,-45.5ZM-73.7,-45.6L-73.7,-45.6L-73.7,-45.6ZM-71,-46.9L-71,-46.9L-71,-46.9ZM-55.5,-50.7L-55.5,-50.7L-55.5,-50.7ZM-54.6,-49.6L-54.6,-49.6L-54.6,-49.6ZM-55.4,-51.9L-55.4,-51.9L-55.4,-51.9ZM-54.1,-49.7L-54.1,-49.7L-54.1,-49.7ZM-54.2,-47.4L-54.2,-47.4L-54.2,-47.4ZM-64.8,-62.6L-64.8,-62.6L-64.8,-62.6ZM-68.2,-60.2L-68.2,-60.2L-68.2,-60.2ZM-70.3,-62.5L-70.3,-62.5L-70.3,-62.5ZM-64.8,-61.4L-64.8,-61.4L-64.8,-61.4ZM-65,-61.9L-65,-61.9L-65,-61.9ZM-69.2,-59L-69.2,-59L-69.2,-59ZM-64.4,-60.4L-64.4,-60.4L-64.4,-60.4ZM-61,-56L-61,-56L-61,-56ZM-61.7,-57.6L-61.7,-57.6L-61.7,-57.6ZM-67.9,-69.5L-67.9,-69.5L-67.9,-69.5ZM-62.7,-67.1L-62.7,-67.1L-62.7,-67.1ZM-79.1,-75.9L-79.1,-75.9L-79.1,-75.9ZM-79.9,-56.8L-79.9,-56.8L-79.9,-56.8ZM-79.7,-57.5L-79.7,-57.5L-79.7,-57.5ZM-79.5,-56.7L-79.5,-56.7L-79.5,-56.7ZM-79.9,-53.3L-79.9,-53.3L-79.9,-53.3ZM-79.4,-52L-79.4,-52L-79.4,-52ZM-123.4,-48.9L-123.4,-48.9L-123.4,-48.9ZM-125,-50L-125,-50L-125,-50ZM-73.6,-67.8L-74.6,-67.8L-74.7,-68.1L-73.4,-68ZM-77.9,-63.5L-77.9,-63.1L-78.5,-63.5ZM-94.5,-75.7L-94.5,-75.7L-94.5,-75.7ZM-80.3,-59.6L-80.3,-59.6L-80.3,-59.6ZM-80.1,-59.8L-80.1,-59.8L-80.1,-59.8ZM-96.8,-72.9L-96.8,-72.9L-96.8,-72.9ZM-97.4,-74.5L-97.4,-74.5L-97.4,-74.5ZM-98.3,-73.9L-99.4,-73.9L-97.7,-74.1ZM-90.2,-69.4L-90.2,-69.4L-90.2,-69.4ZM-90.5,-69.2L-90.5,-69.2L-90.5,-69.2ZM-74,-62.6L-74,-62.6L-74,-62.6ZM-74.9,-68.3L-74.9,-68.3L-74.9,-68.3ZM-78.5,-60.7L-78.5,-60.7L-78.5,-60.7ZM-79,-68.2L-79,-68.2L-79,-68.2ZM-76.7,-63.4L-76.7,-63.4L-76.7,-63.4ZM-79.4,-69.8L-80,-69.5L-80.8,-69.7ZM-78,-69.7L-78,-69.7L-78,-69.7ZM-77.6,-64L-77.6,-64L-77.6,-64ZM-83.1,-66.3L-83.1,-66.3L-83.1,-66.3ZM-79.2,-68.8L-78.6,-69.4L-78.2,-69.3ZM-77,-69.1L-77,-69.1L-77,-69.1ZM-86.9,-70.1L-86.9,-70.1L-86.9,-70.1ZM-83.7,-65.8L-83.7,-65.8L-83.7,-65.8ZM-86.6,-67.7L-86.6,-67.7L-86.6,-67.7ZM-84.7,-65.6L-84.7,-65.6L-84.7,-65.6ZM-93,-61.8L-93,-61.8L-93,-61.8ZM-101.2,-76.6L-101.2,-76.6L-101.2,-76.6ZM-103,-78.1L-103,-78.1L-103,-78.1ZM-101.7,-77.7L-101.7,-77.7L-101.7,-77.7ZM-89.7,-76.5L-89.7,-76.5L-89.7,-76.5ZM-96.1,-75.5L-96.1,-75.5L-96.1,-75.5ZM-95.3,-74.5L-95.3,-74.5L-95.3,-74.5ZM-121.1,-75.7L-121.1,-75.7L-121.1,-75.7ZM-113.6,-76.7L-113.6,-76.7L-113.6,-76.7ZM-104.1,-75L-104.9,-75.1L-104.3,-75.4L-103.6,-75.2ZM-100.2,-68.8L-100.2,-68.8L-100.2,-68.8ZM-100,-69L-100,-69L-100,-69ZM-100.3,-70.5L-100.3,-70.5L-100.3,-70.5ZM-95.5,-69.6L-95.5,-69.6L-95.5,-69.6ZM-101.2,-69.4L-101.2,-69.4L-101.2,-69.4ZM-101.8,-68.6L-101.8,-68.6L-101.8,-68.6ZM-104.5,-68.4L-104.5,-68.4L-104.5,-68.4ZM-107.9,-67.4L-107.9,-67.4L-107.9,-67.4ZM-109.2,-68L-109.2,-68L-109.2,-68ZM-108.1,-67L-108.1,-67L-108.1,-67ZM-109.3,-68L-109.3,-68L-109.3,-68ZM-139,-69.6L-139,-69.6L-139,-69.6ZM103,-11.3L103,-11.3L103,-11.3ZM103.3,-10.7L103.3,-10.7L103.3,-10.7ZM98.2,-11L98.2,-11L98.2,-11ZM98.2,-9.9L98.2,-9.9L98.2,-9.9ZM98.2,-11.5L98.2,-11.5L98.2,-11.5ZM98.5,-11.9L98.5,-11.9L98.5,-11.9ZM98.6,-11.7L98.6,-11.7L98.6,-11.7ZM98.4,-12.6L98.4,-12.6L98.4,-12.6ZM98.1,-12.2L98.1,-12.2L98.1,-12.2ZM94.5,-15.9L94.5,-15.9L94.5,-15.9ZM97.6,-16.3L97.6,-16.3L97.6,-16.3ZM93.7,-18.7L93.7,-18.7L93.7,-18.7ZM93.5,-19.9L93.5,-19.9L93.5,-19.9ZM93.7,-19.6L93.7,-19.6L93.7,-19.6ZM98.5,-11L98.5,-11L98.5,-11ZM98.1,-11.7L98.1,-11.7L98.1,-11.7ZM98.1,-12.4L98.1,-12.4L98.1,-12.4ZM98.3,-13.1L98.3,-13.1L98.3,-13.1ZM94.8,-15.8L94.8,-15.8L94.8,-15.8ZM93,-19.9L93,-19.9L93,-19.9ZM-49.6,0.2L-48.4,0.4L-48.9,1.5L-49.8,1.8L-50.5,1.8L-50.8,1L-50.6,0.3ZM-44.1,23.1L-44.1,23.1L-44.1,23.1ZM-48.6,26.4L-48.6,26.4L-48.6,26.4ZM-45.3,23.9L-45.3,23.9L-45.3,23.9ZM-44.5,2.9L-44.5,2.9L-44.5,2.9ZM-38.7,13.1L-38.7,13.1L-38.7,13.1ZM-38.9,13.5L-38.9,13.5L-38.9,13.5ZM-44.9,1.3L-44.9,1.3L-44.9,1.3ZM-49.7,-0.3L-49.7,-0.3L-49.7,-0.3ZM-50.3,-1.9L-50.3,-1.9L-50.3,-1.9ZM-50.7,0.1L-50.7,0.1L-50.7,0.1ZM-49.4,0.1L-49.4,0.1L-49.4,0.1ZM-50.4,-0.1L-50.4,-0.1L-50.4,-0.1ZM-50.2,-0.4L-50.2,-0.4L-50.2,-0.4ZM-51.8,1.4L-51.5,0.7L-51.3,1ZM-48.5,27.8L-48.5,27.8L-48.5,27.8ZM-88,-17.9L-88,-17.9L-88,-17.9ZM-87.9,-17.4L-87.9,-17.4L-87.9,-17.4ZM-59.5,-13.1L-59.5,-13.1L-59.5,-13.1ZM91.2,-22.2L91.2,-22.2L91.2,-22.2ZM91.6,-22.4L91.6,-22.4L91.6,-22.4ZM90.8,-22.1L90.8,-22.1L90.8,-22.1ZM91.9,-21.8L91.9,-21.8L91.9,-21.8ZM92,-21.5L92,-21.5L92,-21.5ZM90.6,-23L90.6,-23L90.6,-23ZM50.6,-25.9L50.6,-25.9L50.6,-25.9ZM-77.7,-24.2L-77.7,-24.2L-77.7,-24.2ZM-77.2,-25.9L-77.2,-25.9L-77.2,-25.9ZM-73,-21.2L-73,-21.2L-73,-21.2ZM-77.7,-24.7L-78,-24.3L-78.4,-24.6L-78,-25.1ZM-78.5,-26.7L-78.5,-26.7L-78.5,-26.7ZM-77.3,-25L-77.3,-25L-77.3,-25ZM-74.1,-22.7L-74.1,-22.7L-74.1,-22.7ZM-74.4,-24.1L-74.4,-24.1L-74.4,-24.1ZM-74.2,-22.2L-74.2,-22.2L-74.2,-22.2ZM-76.7,-25.5L-76.7,-25.5L-76.7,-25.5ZM-75.7,-23.5L-75.7,-23.5L-75.7,-23.5ZM-74.8,-22.9L-74.8,-22.9L-74.8,-22.9ZM-75.3,-24.2L-75.3,-24.2L-75.3,-24.2ZM-73,-22.4L-73,-22.4L-73,-22.4ZM-72.9,-21.5L-72.9,-21.5L-72.9,-21.5ZM143.2,12L143.8,14.3L144.5,14.2L145.3,14.9L145.4,16.4L146.1,17.6L146,18.2L146.5,19.1L147.4,19.4L148.6,20.1L148.7,20.6L149.5,21.6L149.6,22.3L150.1,22.2L150.8,22.6L150.8,23.5L151.9,24.2L152.9,25.4L153.2,26L153.1,27.2L153.6,28.2L152.9,31.4L152.5,32.4L151.3,33.6L150.7,35.2L150.2,35.8L149.9,37.5L149.5,37.8L148.3,37.8L146.9,38.7L146.2,38.9L145.4,38.5L144.9,37.9L143.5,38.8L142.6,38.5L141.4,38.4L140.6,38L139.8,37.2L139.9,36.7L139,35.6L138.2,35.6L138.5,34.8L138.1,34.2L137.7,35.1L136.9,35.2L137.4,34.9L137.5,34.2L137.9,33.6L137.8,32.8L137.2,33.6L136.4,34L135.6,34.9L134.8,33.3L134.3,33.2L134.2,32.5L132.8,32L132.2,32L131.1,31.5L128.9,31.7L127.3,32.3L125.9,32.3L124.1,33.1L123.6,33.8L122.2,34L121.4,33.8L119.9,34L118.1,35L116.5,35L115,34.3L115,33.5L115.7,33.2L115.7,31.9L115.1,30.6L115,29.4L114.2,28.1L114,27.3L113.3,26.4L114.1,26.4L114.2,25.9L113.4,24.4L113.8,23.4L113.7,22.6L114.1,21.8L114.1,22.5L114.9,21.7L116.7,20.7L117.4,20.7L120.9,19.7L122.4,18L122.2,17.3L123,16.4L123.6,17.5L123.8,16.9L123.5,16.5L124.5,16.3L124.4,15.5L125.6,14.5L125.9,14.6L126.2,14L126.6,14.2L126.9,13.7L128.2,14.8L129.8,14.8L129.4,14.4L130.2,13L131.3,12.1L131.4,12.3L132.6,12L132.7,11.6L131.8,11.3L135.2,12.2L135.8,11.9L136.3,12.4L136.5,12L136.9,12.3L136.5,13.2L135.9,13.3L135.9,14.2L135.5,15L137.7,16.2L138.2,16.7L139,16.9L139.2,17.3L140,17.7L140.8,17.4L141.2,16.6L141.6,15.1L141.5,13.8L141.7,12.4L142.2,10.9L142.5,10.7ZM153.1,25.8L153.1,25.8L153.1,25.8ZM139.5,16.6L139.5,16.6L139.5,16.6ZM136.7,13.8L136.9,14.3L136.3,14.2ZM130.5,11.7L130.5,11.7L130.5,11.7ZM130.6,11.4L131.5,11.4L130.9,11.9ZM113.2,26.1L113.2,26.1L113.2,26.1ZM137.6,35.7L137.4,36.1L136.6,35.7ZM145.5,38.4L145.5,38.4L145.5,38.4ZM145.3,38.5L145.3,38.5L145.3,38.5ZM149,20.3L149,20.3L149,20.3ZM148.9,20.1L148.9,20.1L148.9,20.1ZM151.1,23.5L151.1,23.5L151.1,23.5ZM150.5,22.3L150.5,22.3L150.5,22.3ZM149.9,22.2L149.9,22.2L149.9,22.2ZM153.5,27.4L153.5,27.4L153.5,27.4ZM153.4,27.3L153.4,27.3L153.4,27.3ZM142.3,10.7L142.3,10.7L142.3,10.7ZM142.3,10.2L142.3,10.2L142.3,10.2ZM142.2,10.2L142.2,10.2L142.2,10.2ZM146.3,18.2L146.3,18.2L146.3,18.2ZM136.6,11.4L136.6,11.4L136.6,11.4ZM136.3,11.6L136.3,11.6L136.3,11.6ZM137.1,15.8L137.1,15.8L137.1,15.8ZM136.9,15.6L136.9,15.6L136.9,15.6ZM136.6,15.6L136.6,15.6L136.6,15.6ZM139.5,17.1L139.5,17.1L139.5,17.1ZM136.2,13.8L136.2,13.8L136.2,13.8ZM132.6,11.3L132.6,11.3L132.6,11.3ZM125.2,14.6L125.2,14.6L125.2,14.6ZM124.6,15.4L124.6,15.4L124.6,15.4ZM115.4,20.8L115.4,20.8L115.4,20.8ZM145,40.8L146.3,41.2L148.3,40.9L148.3,42L147.9,42.6L148,43.2L147.3,42.9L146.9,43.6L146,43.5L145.5,42.9L144.6,41ZM143.9,40.1L143.9,40.1L143.9,40.1ZM148,39.8L148,39.8L148,39.8ZM147.4,43.4L147.4,43.4L147.4,43.4ZM148.1,42.7L148.1,42.7L148.1,42.7ZM147.4,43.2L147.4,43.2L147.4,43.2ZM144.8,40.5L144.8,40.5L144.8,40.5ZM148.3,40.3L148.3,40.3L148.3,40.3ZM148.2,40.5L148.2,40.5L148.2,40.5ZM158.9,54.7L158.9,54.7L158.9,54.7ZM105.7,10.5L105.7,10.5L105.7,10.5ZM96.8,12.2L96.8,12.2L96.8,12.2ZM96.9,12.2L96.9,12.2L96.9,12.2ZM73.7,53.1L73.7,53.1L73.7,53.1ZM167.9,29L167.9,29L167.9,29ZM123.6,12.4L123.6,12.4L123.6,12.4ZM-64.6,54.7L-64.6,54.7L-64.6,54.7ZM-61.9,39.2L-61.9,39.2L-61.9,39.2ZM-61.7,-17L-61.7,-17L-61.7,-17ZM-61.7,-17.6L-61.7,-17.6L-61.7,-17.6Z"/><path class="borders" d="M25.3,17.8L24.3,17.5L23.4,17.6L22.1,16.6L22,16L22,13L24,13L24,10.9L24.3,11.4L25.3,11.2L25.3,11.6L26,11.9L26.9,11.9L27.2,11.6L27.5,12.2L28.4,12.5L29,13.4L29.8,13.4L29.8,12.2L29.1,12.3L28.4,11.5L28.6,10.7L28.4,9.2L29,8.5L30.7,8.2L31.9,9.1L32.9,9.4L33.7,10.6L33.3,10.9L33.4,12.5L33,12.6L32.7,13.6L33.2,14L30.2,15L30.4,15.6M42.8,-16.4L43.2,-16.7L43.2,-17.4L45.1,-17.4L47.4,-17.1L48.2,-18.2L49.2,-18.6L52,-19L53.1,-16.6M104.4,-10.4L105,-10.9L105.8,-11L106,-11.8L107.4,-12.3L107.6,-13.4L107.3,-14.1L107.5,-14.7L107.7,-15.3L107.2,-15.8L107.4,-16L106.7,-16.5L106.5,-17L104.7,-18.8L103.9,-19.3L104.9,-20L104.6,-20.6L104.1,-20.9L103.1,-20.9L102.1,-22.4L102.4,-22.7L103,-22.5L103.3,-22.8L103.9,-22.5L105.3,-23.3L105.8,-22.9L106.8,-22.8L106.7,-22L108,-21.5M-60,-8.5L-59.8,-8.3L-60.7,-7.5L-60.3,-7.1L-61.1,-6.7L-61.4,-5.9L-60.7,-5.2L-61,-4.5L-62.7,-4L-63,-3.6L-63.3,-3.9L-64,-3.9L-64.8,-4.2L-64.2,-3.6L-64.1,-2.5L-63.4,-2.4L-64.1,-1.6L-65.6,-0.7L-66.3,-0.8L-66.9,-1.2L-67.2,-2.4L-67.8,-2.9L-67.3,-3.4L-67.9,-4.5L-67.6,-6.2L-69.4,-6.1L-70.1,-6.9L-70.7,-7.1L-71.9,-7L-72.5,-7.5L-72.4,-8.4L-72.8,-9.1L-73.4,-9.2L-72.9,-10.5L-72,-11.7L-71.3,-11.9M12.4,-41.9L12.4,-41.9M70.7,-40.9L70.7,-40.9M71.2,-39.9L71.2,-39.9M71.8,-39.9L71.8,-39.9M-58.2,32.5L-58.2,31.9L-57.6,30.2L-56.8,30.1L-56,31.1L-55.6,30.9L-53.8,32.1L-53.1,32.7L-53.5,33.2L-53.4,33.7M-130.2,-55L-130.6,-54.8M-141,-69.7L-141,-60.3L-140,-60.2L-139.1,-60.3L-139.2,-60.1L-137.6,-59.2L-137.4,-58.9L-136.6,-59.2L-136.3,-59.6L-135.5,-59.8L-134.9,-59.3L-133.8,-58.7L-131.6,-56.6L-130.1,-56.1L-130,-55.9M-122.8,-49L-119.4,-49.4L-115.9,-49.6L-112.5,-49.8L-109,-49.8L-105.5,-49.8L-102,-49.6L-98.6,-49.4L-95.2,-49L-94.9,-49.3L-94.6,-48.7L-93.7,-48.5L-93,-48.6L-91.5,-48.1L-90.8,-48.2L-89.3,-48L-88.4,-48.3L-84.9,-46.9L-84.6,-46.5L-82.6,-45.3L-82.1,-43.6L-82.5,-42.6L-83.1,-42L-82.4,-41.7L-81.3,-42.2L-80.2,-42.4L-78.9,-42.9L-79.2,-43.5L-78.7,-43.6L-76.8,-43.6L-76.5,-44.1L-75.2,-44.9L-74.7,-45L-71.5,-45L-70.9,-45.3L-70.3,-45.9L-70,-46.7L-69.2,-47.5L-68.2,-47.3L-67.8,-47.1L-67.8,-45.7L-67.1,-45.2M-97.1,-26L-97.4,-25.9L-99.1,-26.4L-99.5,-27.5L-100.3,-28.3L-100.7,-29.1L-101.6,-29.8L-102.3,-29.9L-103.3,-29L-104.5,-29.7L-105,-30.6L-106.5,-31.8L-108.2,-31.8L-108.2,-31.3L-111,-31.3L-114.8,-32.5L-114.7,-32.7L-117.1,-32.5M-6.2,-54.1L-7.1,-54.4L-7.4,-54.1L-8.1,-54.4L-7.2,-55.1M56.4,-25L55.8,-24.9L55.2,-22.7L55.1,-22.6L52.6,-22.9L51.6,-24.3M56.1,-26.1L56.3,-25.7M56.3,-25.2L56.3,-25.2M35,-45.7L34.7,-46L33.6,-46.1M29.7,-45.3L28.8,-45.2L28.2,-45.5L28.9,-46L29.1,-46.5L29.8,-46.4L29.9,-46.8L29.2,-47.5L29.1,-48L27.5,-48.5L26.6,-48.3L26.2,-48L24.9,-47.7L23.1,-48.1L22.9,-47.9L22.1,-48.4L22.5,-49.1L22.6,-49.5L24.1,-50.8L23.6,-51.5L24.4,-51.9L25.9,-51.9L27.3,-51.6L29.1,-51.6L29.3,-51.4L30.5,-51.6L31,-52L31.8,-52.1L32.5,-52.3L33.7,-52.3L34.4,-51.8L34.2,-51.2L35.1,-51.2L35.4,-50.5L36.6,-50.2L37.4,-50.4L38.3,-50.1L40,-49.6L39.7,-49L40,-48.3L39.7,-47.8L38.9,-47.9L38.3,-47.6L38.2,-47.1M66.5,-37.3L65.8,-37.6L64.8,-37.1L64.5,-36.3L63.1,-35.8L63.1,-35.4L62.3,-35.2L61.3,-35.6L61.1,-36.6L60.3,-36.6L59.3,-37.5L56.4,-38.2L55.1,-37.9L54.7,-37.5L53.9,-37.3M52.5,-41.8L53.2,-42.2L54.1,-42.3L54.9,-41.9L55.5,-41.3L56,-41.3M41.5,-41.5L42.8,-41.6L43.4,-41.1L43.7,-40.2L44.8,-39.7L44.8,-39.7L44,-39.4L44.4,-38.4L44.2,-37.9L44.8,-37.1L42.8,-37.4L42.4,-37.1L40.7,-37.1L39.4,-36.7L38.2,-36.9L37.4,-36.6L36.7,-36.8L36.6,-36.2L35.9,-35.9M26,-40.7L26.6,-41.4L26.3,-41.7L27.3,-42.1L28,-42M11.5,-33.2L11.5,-32.4L10.1,-31.5L10.2,-30.8L9.5,-30.2L9,-32.1L8.3,-32.5L7.7,-33.3L7.5,-34.1L8.2,-34.7L8.4,-35.2L8.2,-36.5L8.6,-36.9M1.2,-6.1L0.5,-6.9L0.7,-8.3L0.2,-9.5L0.4,-10.3L-0.1,-11.1L0.9,-11L0.8,-10.4L1.3,-10L1.6,-9.1L1.6,-6.2M125.1,9.5L124.9,8.9M124.4,9.2L124,9.3M98.7,-10.2L98.8,-10.7L99.6,-11.8L99.1,-13.1L99.1,-13.7L98.2,-14.8L98.8,-16.2L98.4,-17L97.8,-17.7L97.5,-18.5L97.8,-18.6L98,-19.7L98.9,-19.8L99.5,-20.4L100.1,-20.3L100.5,-20.1L100.6,-19.5L101.2,-19.5L101.3,-19L100.9,-17.6L101.1,-17.5L102.1,-18.2L102.7,-17.9L103.3,-18.4L104.1,-18.2L104.8,-17.3L104.8,-16.6L105.6,-15.7L105.5,-14.5L105.2,-14.3L103.2,-14.3L102.3,-13.5L102.9,-11.7M102.1,-6.2L101.9,-5.8L101.1,-5.6L101.1,-6.2L100.2,-6.7L100.1,-6.4M30.7,8.2L30.3,7.2L29.7,6.6L29.3,5L29.4,4.4L29.7,4.5L30.8,3.3L30.4,2.9L30.6,2.4L30.8,1.6L30.5,1.1M33.9,1L30.5,1.1L29.6,1.4L29.7,-0.1L29.9,-0.8L31.3,-2L30.7,-2.5L30.8,-3.5L31.2,-3.8L32.2,-3.5L33,-3.9L33.5,-3.8L34,-4.2L34.4,-3.6L34.9,-2.5L35,-1.6L33.9,-0.2L33.9,1L37.6,3L37.8,3.7L39.2,4.7M40.5,10.5L40,10.8L38.5,11.4L38.2,11.3L37.4,11.7L36.5,11.7L35.8,11.5L35,11.6L34.6,11L34.5,9.9L32.9,9.4M71,-40.2L69.3,-40L69.3,-39.5L71.5,-39.6L71.8,-39.3L73.6,-39.4L73.8,-38.6L74.7,-38.5L75.1,-37.4L74.9,-37.2L73.5,-37.5L71.8,-36.7L71.4,-37.1L71.6,-37.9L70.9,-38.5L70.3,-37.7L69.5,-37.6L68.1,-36.9L67.8,-37.2M70.7,-39.8L70.7,-39.8M42.4,-37.1L41.4,-36.5L41.2,-34.8L40.7,-34.3L38.8,-33.4L36.8,-32.3L35.8,-32.7L35.9,-33.4L36.6,-34.2L36,-34.6M14.8,-50.9L14.4,-50.9L12.5,-50.3L12.2,-50.1L12.6,-49.5L13.8,-48.8L12.8,-48.2L13,-47.5L12.2,-47.7L10.3,-47.3L9.5,-47.5L9.5,-47.3L9.6,-47.1L10.5,-46.9L9.9,-46.4L9.3,-46.5L9,-45.8L8.4,-46.4L7.8,-45.9L7,-45.9L6.8,-46.4L6.1,-46.4L7,-47.3L7.6,-47.6L8.6,-47.8L9.5,-47.5M11.4,-59L11.7,-59.6L12.5,-60.1L12.3,-61L12.9,-61.4L12.2,-61.7L12.3,-62.3L12,-63.3L12.7,-63.9L14,-64L13.6,-64.6L14.5,-65.3L14.5,-66.1L16.4,-67.1L16.1,-67.4L17.3,-68.1L17.9,-68L18.4,-68.6L20,-68.4L20.6,-69L22,-68.5L22.8,-68.4L23.6,-68L23.5,-67.4L24,-66.8L23.7,-66.5L24.2,-65.8M31.3,22.4L29.4,22.2L29,21.8L28,21.6L27.7,21.1L27.7,20.5L26.2,19.5L25.3,17.8L26.8,18L27.9,16.9L28.8,16.5L28.9,16L29.5,15.7L30.4,15.6L30.4,16L31.2,16L32.9,16.7L33,18.3L32.7,18.8L33,19.9L32.5,20.7L32.4,21.3L31.3,22.4L31.5,23.5L32,24.5L31.9,26L32.1,26.8L32,27.3L31.1,27.1L30.8,26.4L31.4,25.7L31.9,26M-54.2,-5.4L-54.5,-5L-54.4,-4.1L-54,-3.6L-54.2,-2.8L-54.6,-2.3L-55,-2.6L-56.1,-2.3L-56.5,-1.9L-56.7,-2L-58.1,-4.2L-57.7,-5L-57.2,-5.5M30.8,-3.5L29.7,-4.6L28.2,-4.4L27.4,-5.1L27.1,-5.8L26.5,-6.1L26.4,-6.6L25.2,-7.5L24.9,-8.1L24.1,-8.7L24.5,-8.9L25.1,-10.3L25.8,-10.4L26.6,-9.5L27.9,-9.6L28,-9.3L28.8,-9.3L30,-10.3L30.7,-9.7L31.2,-9.8L32.4,-11.1L32.1,-12L33.2,-12.2L33.2,-10.9L33.9,-10.2L34.1,-9.5L34.1,-8.6L33.2,-8.4L33,-8L33.7,-7.7L34.7,-6.7L35.3,-5.5L34,-4.2M24.1,-8.7L23.5,-8.8L23.6,-9.8L22.9,-10.9L22.4,-12.7L21.8,-12.8L22.2,-13.3L23.1,-15.7L24,-15.8L24,-19.5L24,-20L25,-20L25,-22L30.9,-22.1L36.9,-22M38.6,-18L38.2,-17.6L37,-17.1L36.9,-16.3L36.4,-15.1L36.5,-14.3L36.1,-12.7L35.6,-12.5L35.1,-11.8L34.9,-10.9L34.3,-10.5L34.1,-9.5M-1.8,-43.4L-1.5,-43.1L1.4,-42.6L1.7,-42.5L3.2,-42.4M-7.4,-37.2L-7.5,-37.6L-7,-38L-7.3,-38.5L-7,-39.1L-7.5,-39.7L-7,-39.7L-6.8,-40.3L-6.9,-41L-6.2,-41.5L-6.6,-41.9L-7.4,-41.8L-8.8,-41.9M126.6,-37.8L127,-38.2L128,-38.3L128.4,-38.6M32.1,26.8L32.9,26.9M16.4,28.6L17.1,28L17.4,28.7L19.2,28.9L20,28.5L20,24.8L20.8,25.9L20.7,26.8L21.6,26.9L22.6,26.1L23.3,25.3L24.7,25.8L25.6,25.6L25.9,24.7L26.8,24.2L27,23.7L28.2,22.7L29.4,22.2M28.7,30.1L29.4,29.3L28.6,28.6L27.7,28.9L27.1,29.7L27.4,30.3L28,30.6L28.7,30.1M41.5,1.7L41,0.9L41,-2.8L41.9,-4L44,-5L44.9,-4.9L46.4,-6.5L48,-8L48.9,-9.5L48.9,-11.3M48,-8L46.9,-8L44,-9L43.5,-9.4L42.7,-10.6L42.9,-11L43.2,-11.5M22.1,-48.4L20.5,-48.5L19.9,-48.1L17.8,-47.8L17.1,-48L17,-48.6L18.8,-49.5L19.4,-49.6L19.8,-49.2L21.6,-49.4L22.5,-49.1M13.7,-45.6L13.7,-46.5L14.5,-46.4L16.1,-46.9L16.5,-46.5L15.6,-46.2L15.3,-45.5L13.6,-45.5M-13.3,-9L-12.5,-9.9L-11.2,-10L-10.3,-8.5L-10.6,-7.8L-11.5,-6.9M28.6,-43.7L27.1,-44.2L25.5,-43.7L23.2,-43.9L22.7,-44.2L22.6,-43.5L23,-43.2L22.5,-42.8L22.3,-42.3L21.6,-42.2L21.8,-42.7L20.8,-43.3L20.3,-42.8L19.2,-43.5L19.6,-44L19,-44.9L18.9,-45.9L20.2,-46.1L20.8,-45.5L21.4,-45.2L21.4,-44.9L22.1,-44.5L22.5,-44.7L22.7,-44.2M-16.5,-15.8L-16.2,-16.5L-15,-16.7L-14.3,-16.6L-13.6,-16.1L-12.9,-15.2L-12.3,-14.8L-12.1,-13.6L-11.4,-12.9L-11.4,-12.4L-12.3,-12.3L-13.7,-12.7L-15.2,-12.7L-16.7,-12.4M-16.8,-13.1L-15.8,-13.2L-15.2,-13.6L-14.2,-13.2L-13.8,-13.3L-14.9,-13.8L-16.6,-13.6M35,-29.4L36,-29.2L36.8,-29.9L37.5,-30L38,-30.5L37,-31.5L39.1,-32.1L40.4,-31.9L42.1,-31.1L44.7,-29.2L46.5,-29.1L47.4,-29L47.7,-28.5L48.4,-28.5M50.8,-24.8L51.3,-24.6M55.2,-22.7L55.6,-22L55,-20L52,-19M12.5,-43.9L12.5,-43.9M30.6,2.4L29.9,2.3L29.9,2.7L29,2.7L28.9,2.4L29.6,1.4M130.7,-42.3L130.5,-42.5L131.3,-43.4L131.1,-44.9L131.9,-45.3L132.9,-45L133.9,-46.2L134.2,-47.3L134.8,-47.7L134.3,-48.4L132.7,-47.9L132.6,-47.8L131,-47.7L130.6,-48.9L129.5,-49.4L128,-49.6L126.9,-51.1L126.3,-52.4L125.7,-53L124.8,-53.1L123.6,-53.5L121,-53.3L120.1,-52.8L120.7,-52.6L120.7,-52L120.1,-51.6L119.2,-50.4L119.3,-50.1L117.9,-49.5L116.7,-49.8L115.3,-49.9L114.3,-50.3L113.1,-49.6L110.8,-49.2L108.6,-49.3L107.9,-49.9L106.7,-50.3L105.4,-50.5L103.6,-50.1L102.3,-50.6L102.1,-51.4L99.9,-51.8L98.9,-52.1L97.9,-51.3L97.8,-51L98.3,-50.5L98.1,-50.1L97.2,-49.7L95.9,-50L94.6,-50L94.3,-50.6L93.1,-50.6L92.4,-50.9L89.6,-49.9L89,-49.5L88.2,-49.5L87.8,-49.2L87.3,-49.1L86.6,-49.6L85.2,-49.7L85,-50.1L84.3,-50.2L83.9,-50.8L83.4,-51L82.5,-50.7L81.5,-50.7L80.9,-51.3L80,-50.8L78.5,-52.6L77.7,-53.4L76.6,-53.9L76.8,-54.4L74.5,-53.6L73.4,-53.5L73.7,-53.9L72.3,-54.3L71.1,-54.2L71.2,-54.6L70.7,-55.3L70.2,-55.2L69,-55.4L67.7,-54.9L65.5,-54.6L61.9,-53.9L61.3,-54L61,-53.6L62,-52.9L61,-53L61,-52.4L60.1,-52L61.4,-51.4L61.4,-50.9L60.9,-50.7L60,-50.8L59.8,-50.6L58.9,-50.7L58.4,-51.1L57.4,-50.9L56.5,-51L55.8,-50.6L54.6,-51L54.7,-50.7L53.3,-51.5L52.3,-51.7L51.3,-51.5L50.8,-51.7L50.2,-51.3L48.6,-50.6L48.8,-50L48.4,-49.8L47.7,-50.4L47.3,-50.3L46.8,-49.4L47,-49.1L46.7,-48.4L47.3,-47.7L48.1,-47.7L49.2,-46.3M48.6,-41.8L47.9,-41.2L47.3,-41.3L46.4,-41.9L45.6,-42.2L45.7,-42.5L44.9,-42.8L44,-42.6L42.4,-43.2L41.6,-43.2L40.6,-43.5L40,-43.4M31.8,-52.1L31.4,-53.2L32.1,-53.1L32.7,-53.3L32.4,-53.7L31.8,-53.8L30.8,-54.8L30.9,-55.6L28.1,-56.1L27.6,-56.8L27.8,-57.2L27.4,-57.5L27.8,-57.8L27.5,-58.8L28,-59.5M27.8,-60.5L29.3,-61.3L31.3,-62.6L31.5,-62.9L30,-63.7L30.5,-64L30.1,-64.8L29.6,-65L29.9,-66.1L29.1,-67L30,-67.7L28.7,-68.2L28.5,-68.5L29,-69L30.9,-69.8M21.2,-55.3L22.6,-55.1L22.8,-54.4L19.6,-54.5M20.9,-55.3L21,-55.3M20.2,-46.1L21,-46.2L22.3,-47.7L22.9,-47.9M26.6,-48.3L27,-48.2L28.2,-46.6L28.2,-45.5M18.8,-49.5L18.6,-49.9L17.9,-50L16.4,-50.6L14.8,-50.9L15,-51.3L14.6,-51.8L14.6,-52.5L14.1,-52.9L14.3,-53.7M14.2,-53.9L14.2,-54M22.8,-54.4L23.5,-53.9L23.8,-52.7L23.2,-52.3L23.7,-52L23.6,-51.5M-80.3,3.4L-80.5,4.1L-79.6,4.5L-79.1,5L-78.7,4.6L-78.3,3.4L-77.9,3L-76.7,2.6L-75.6,1.5L-75.3,0.1L-74.8,0.2L-74.2,1L-73.7,1.2L-73.2,2.3L-72.4,2.4L-71.8,2.2L-70.9,2.2L-70.1,2.8L-70.7,3.8L-70,4.2L-70.8,4.2L-71.8,4.5L-72.9,5.1L-73.2,6.1L-73.1,6.5L-73.8,6.9L-74,7.6L-73,9L-73.2,9.4L-72.4,9.5L-72.2,10L-71.2,10L-70.5,9.4L-70.6,11L-69.6,11L-68.7,12.5L-69.1,13.7L-68.9,14.2L-69.4,15L-69.4,15.6L-69,16.6L-69.6,17.2L-69.5,17.5L-69.9,18.2L-70.4,18.3M141,9.1L141,2.6M-77.4,-8.7L-77.2,-8L-77.9,-7.2M-82.9,-8.1L-82.7,-8.9L-82.9,-9.4L-82.6,-9.6M61.6,-25.2L61.9,-26.2L63.2,-26.7L63.3,-27.1L62.8,-27.3L62.8,-28.3L61.9,-28.5L60.8,-29.9L62.5,-29.4L64.1,-29.4L66.2,-29.8L66.4,-30.9L66.9,-31.3L68.2,-31.8L68.9,-31.6L69.3,-31.9L69.5,-33L70.3,-33.3L69.9,-33.9L71.1,-34L71,-34.5L71.6,-35.2L71.2,-36L71.6,-36.4L72.6,-36.8L74.5,-37L75.8,-36.6L76.1,-35.8L76.8,-35.7L77,-35.1L76.6,-34.7L75.7,-34.5L74.3,-34.8L73.8,-34.3L74.2,-33.5L74,-33.2L74.7,-32.5L75.3,-32.3L74.5,-31.7L74.6,-31L73.4,-29.9L72.9,-29L72.3,-28.8L71.9,-28L70.9,-27.7L70.4,-28L69.6,-27.2L69.5,-26.8L70.2,-26.5L70.1,-26.1L70.7,-25.4L71,-24.4L69.7,-24.2L68.7,-24.3L68.2,-23.9M29,-69L29.1,-69.7L27.9,-70.1L26.5,-69.9L26,-69.7L25.7,-69L24.9,-68.6L23.9,-68.8L22.4,-68.7L21.6,-69.3L20.6,-69M124.4,-40L124.9,-40.5L126,-40.9L126.9,-41.8L128.1,-41.4L128,-42L128.9,-42L129.7,-42.5L129.9,-43L130.5,-42.5M2.7,-6.4L2.8,-9L3,-9.1L3.8,-10.6L3.6,-11.7L3.6,-12.5L4.1,-13.5L5.5,-13.9L6.4,-13.6L7.1,-13L7.8,-13.3L8.7,-12.9L9.6,-12.8L10.2,-13.3L11.4,-13.4L12.5,-13.1L13.6,-13.7L14.1,-13.1L14.2,-12.4L14.6,-12.1L14.6,-11.5L13.9,-11.1L12.4,-8.6L11.9,-7.1L11.2,-6.4L10.6,-7.1L10.1,-7L9.1,-6L8.6,-4.8M3.6,-11.7L2.9,-12.4L2.4,-11.9L2.1,-12.7L1.6,-12.6L1,-13L1.2,-13.4L0.6,-13.7L0.2,-14.5L0.2,-14.9L1.3,-15.3L3.5,-15.4L3.9,-15.8L4.2,-17L4.2,-19.1L5.8,-19.5L7.5,-20.9L12,-23.5L13.5,-23.2L14.2,-22.6L15,-23L15.2,-21.5L15.9,-20.3L15.7,-19.9L15.5,-16.9L14.4,-15.7L13.4,-14.4L13.6,-13.7M-83.6,-10.9L-85.7,-11.1M-87.3,-13L-86.7,-13.3L-86.7,-13.8L-86,-14.1L-85.8,-13.8L-85,-14.8L-84.5,-14.6L-83.2,-15M7.2,-53.3L6.7,-51.9L5.9,-51.8L6.2,-51.5L6,-50.8L5.8,-51.1L4.8,-51.5L4.2,-51.4L3.3,-51.4M25.3,17.8L24.4,18L23.6,18.5L23.3,18L21,18.3L21,22L20,22L20,24.8M11.7,17.3L13.1,17L13.9,17.4L18.4,17.4L19,17.8L21.4,18L23.4,17.6M33.2,14L33.6,14.6L34.3,14.4L34.5,15.3L34.2,15.9L35.3,17.1L35.2,16.6L35.8,16.1L35.8,14.7L34.6,13.4L34.4,12.2L35,11.6M34.6,12L34.6,12M34.7,12.1L34.7,12.1M-2.2,-35.1L-1.8,-34.8L-1.7,-33.3L-1.1,-32.5L-1.3,-32.1L-2.4,-32.1L-3.8,-31.7L-3.6,-31.1L-5,-30.5L-5.4,-30L-7.1,-29.6L-8.7,-28.7L-8.7,-27.7L-8.8,-27.1L-9.7,-26.9L-10.9,-27L-11.4,-26.9L-11.7,-26.1L-12,-26L-12.4,-24.8L-13.3,-24L-13.9,-23.7L-14.2,-22.3L-14.8,-21.5L-17,-21.4M-8.7,-27.7L-8.7,-27.3L-8.7,-26L-12,-26L-12,-23.5L-13,-23L-13,-21.3L-17,-21.3L-17,-20.8M20.3,-42.8L20.1,-42.5L19.7,-42.6L19.3,-41.9M18.5,-42.4L18.4,-42.6L18.4,-43L19.2,-43.5M116.7,-49.8L115.6,-47.9L115.9,-47.7L116.8,-47.9L117.4,-47.7L117.8,-48L118.5,-48L119.7,-47.2L119.7,-46.6L118.3,-46.7L116.6,-46.3L115.7,-45.5L114.5,-45.4L113.6,-44.7L111.9,-45.1L111.4,-44.4L111.9,-43.7L111,-43.3L110.4,-42.8L109.4,-42.5L106.8,-42.3L105.2,-41.7L103.7,-41.8L102,-42.2L101.7,-42.5L100,-42.7L99.5,-42.6L97.2,-42.8L96.4,-42.7L95.9,-43.2L95.3,-44.3L94.7,-44.4L93.7,-44.9L90.9,-45.2L90.7,-45.5L91,-46L90.9,-47L90.3,-47.7L89,-48L88,-48.6L87.8,-49.2M7.4,-43.7L7.4,-43.7M-88.3,-18.5L-89.2,-17.8L-91,-17.8L-91,-17.3L-91.4,-17.3L-90.4,-16.4L-90.4,-16.1L-91.7,-16.1L-92.2,-15.3L-92.2,-14.5M-8.7,-27.3L-4.8,-25L-6.6,-25L-5.6,-16.6L-5.4,-16.3L-5.5,-15.5L-9.2,-15.5L-10.7,-15.4L-10.9,-15.2L-11.5,-15.6L-12.3,-14.8M-4.8,-25L1.1,-21.1L1.7,-20.4L3.2,-19.8L3.1,-19.2L4.2,-19.1M0.2,-14.9L-0.8,-15L-2.5,-14.3L-3.2,-13.7L-3.3,-13.3L-4.1,-13.4L-4.4,-12.3L-5.3,-11.8L-5.5,-10.4L-6,-10.2L-6.3,-10.7L-7,-10.2L-7.7,-10.4L-8,-10.2L-8.4,-11.4L-8.8,-11.7L-9,-12.4L-10.7,-11.9L-11.4,-12.4M117.6,-4.2L115.9,-4.3L115.6,-3.9L115.5,-3L114.8,-2.3L114.5,-1.5L113.6,-1.2L112.9,-1.6L112.2,-1.4L111.8,-1L110.5,-0.9L109.7,-1.6L109.6,-2M114.1,-4.6L114.6,-4L115,-4.9L115.1,-4.9M117.9,-4.2L117.6,-4.2M22.3,-42.3L23,-41.7L22.9,-41.3L21,-40.9L20.5,-41.3L20.6,-41.9L21.6,-42.2M21,-56.1L22.1,-56.4L24.1,-56.3L24.9,-56.4L26.6,-55.7L26.8,-55.3L25.9,-54.9L25.5,-54.3L24.8,-54L23.5,-53.9M9.5,-47.3L9.6,-47.1M25.2,-31.7L24.7,-30.2L25,-29.2L25,-22M24,-19.5L20,-21.5L16,-23.4L15,-23M12,-23.5L11.5,-24.3L10.3,-24.6L10,-25.3L9.4,-26.1L9.9,-26.6L9.8,-29L9.3,-30.1L9.5,-30.2M-10.3,-8.5L-9.5,-8.3L-9.5,-7.4L-8.9,-7.3L-8.5,-7.6L-8.3,-7.1L-8.6,-6.5L-7.5,-5.8L-7.5,-4.4M35.9,-33.4L35.1,-33.1M24.3,-57.9L25.1,-58.1L26.5,-57.5L27.4,-57.5M28.1,-56.1L27.6,-55.8L26.6,-55.7M107.5,-14.7L106.8,-14.3L106.5,-14.6L105.9,-13.9L105.2,-14.3M100.1,-20.3L100.2,-20.7L101.1,-21.6L101.7,-21.2L101.7,-22.5L102.1,-22.4M70.9,-42.2L70.2,-41.6L71.4,-41.1L71.9,-41.2L73.1,-40.8L71.7,-40.2L71,-40.2L70.4,-40.5L70.4,-41L69.7,-40.7L68.5,-39.5L67.7,-39.6L67.4,-39.2L68.1,-39L68.3,-38L67.8,-37.2L66.5,-37.3L66.6,-37.9L65.6,-38.2L64.2,-39L62.6,-39.9L61.9,-41.1L60.5,-41.2L59.9,-42.3L58.6,-42.8L57.8,-42.2L57,-41.9L57,-41.3L56,-41.3L56,-45L58.4,-45.5L61,-44.4L62,-43.5L63.2,-43.6L64.4,-43.6L64.9,-43.7L65.8,-42.9L66.1,-43L66,-42L66.5,-42L66.8,-41.1L67.9,-41.2L68.6,-40.7L69.1,-41.4L70.9,-42.2L71.3,-42.7L72.3,-42.8L73.5,-42.4L73.6,-43L74.2,-43.2L75.6,-42.8L76.9,-43L79.1,-42.8L80.2,-42.2L78.4,-41.4L78.1,-41.1L76.8,-41L76.5,-40.4L75.7,-40.3L75.6,-40.6L74,-40L73.6,-39.4M46.5,-29.1L47.1,-30L48,-30M20.6,-41.9L20.1,-42.5M35.3,-5.5L35.7,-5.3L36.1,-4.5L36.9,-4.4L38.1,-3.6L39.5,-3.5L39.8,-3.9L40.8,-4.3L41.2,-3.9L41.9,-4M87.3,-49.1L86.8,-49L86.6,-48.5L85.8,-48.4L85.7,-47.3L84.8,-46.8L83.2,-47.2L82.3,-45.6L82.5,-45.1L81.7,-45.3L80.1,-45L80.5,-44.7L80.4,-44.1L80.8,-43.2L80.2,-42.7L80.2,-42.2M38.8,-33.4L39.1,-32.1M35,-29.6L35.5,-31.5L35.6,-32.4L35.8,-32.7M10.5,-46.9L12.2,-47.1L12.4,-46.7L13.7,-46.5M7.5,-43.8L7.7,-44.1L6.9,-44.3L6.6,-45.1L7.2,-45.4L7,-45.9M35.6,-32.4L35,-32.2L35.5,-31.5M34.9,-29.5L34.2,-31.2L34.5,-31.6M34.2,-31.2L34.2,-31.3M44.8,-37.1L45.4,-36L46.2,-35.8L46.1,-35.1L45.7,-34.8L45.4,-34L46.4,-32.9L47.4,-32.4L47.8,-31.8L47.7,-31L48.5,-30M61.3,-35.6L61,-34.7L60.5,-34.1L60.9,-33.5L60.6,-33.1L60.9,-31.5L61.7,-31.4L61.8,-30.8L60.8,-29.9M44.8,-39.7L45.6,-39L46.1,-38.9L46.5,-38.9L47.8,-39.6L48.3,-39.4L48,-38.8L48.9,-38.4M77,-35.1L77.8,-35.5L78.3,-34.7L79,-34.2L78.8,-33.5L79.2,-32.5L78.4,-32.5L78.7,-32L78.7,-31.3L81,-30.2M88.1,-27.9L88.1,-26.4L87.3,-26.4L85.3,-26.7L84.1,-27.5L83.3,-27.4L81.9,-27.9L80.1,-28.8L80.5,-29.9L81,-30.2L82,-30.3L83.6,-29.2L84.1,-29.2L85.1,-28.3L86,-27.9L86.6,-28.1L87.1,-27.8L88.1,-27.9L88.6,-28.1L88.9,-27.3L88.9,-27L89.8,-26.7L92.1,-26.9L91.6,-27.8L92.7,-27.9L93.2,-28.6L94.6,-29.3L95.4,-29.1L96,-29.4L96.6,-28.5L97.3,-28.2L97,-27.7L97,-27.1L96.1,-27.2L95.1,-26.6L95.1,-26L94.6,-25.2L94.7,-25L94.1,-23.9L93.3,-24L93.4,-23.1L93,-22L92.6,-22L92.2,-23.7L91.6,-23L91.2,-23.6L91.4,-24.1L91.9,-24.2L92.4,-25L92.1,-25.2L90.4,-25.2L89.8,-25.3L89.8,-25.9L88.5,-26.5L88.1,-25.9L88.8,-25.5L88,-24.6L88.7,-24.3L88.6,-23.7L89.1,-22.1M18.9,-45.9L17.8,-45.8L16.5,-46.5M16.1,-46.9L16.5,-47L16.6,-47.7L17.1,-48M-87.8,-13.4L-87.7,-13.8L-88.4,-13.9L-89.4,-14.4L-89.2,-14.9L-88.2,-15.7M-71.8,-19.7L-71.7,-19.1L-72,-18.6L-71.8,-18M-56.5,-1.9L-57.1,-2L-58.3,-1.6L-58.5,-1.3L-59.2,-1.4L-59.8,-1.9L-60,-2.7L-59.9,-3.6L-59.5,-3.9L-60.1,-4.5L-60,-5.1L-60.7,-5.2M-13.7,-12.7L-13.7,-11.7L-14.7,-11.5L-15,-10.9M-8,-10.2L-8.1,-9.5L-7.7,-8.4L-8.5,-7.6M-89.2,-17.8L-89.2,-15.9L-88.9,-15.9M-89.4,-14.4L-90.1,-13.7M20,-39.7L20.4,-39.8L21,-40.9M22.9,-41.3L24.5,-41.6L25.3,-41.2L26.1,-41.4L26.3,-41.7M-3.1,-5.1L-3.1,-5.1M-3,-5.1L-2.8,-5.2L-3.2,-6.8L-2.5,-8.2L-2.7,-9.5L-2.8,-11L-0.7,-11L-0.1,-11.1M7.6,-47.6L7.6,-48.1L8.1,-49L6.7,-49.2L6.3,-49.5M6.1,-50.1L6.3,-49.5L5.8,-49.5L6.1,-50.1L6,-50.8M8.7,-54.9L9.7,-54.8M46.4,-41.9L46.5,-41.1L45.3,-41.4L45,-41.3L43.4,-41.1M9.6,-1L11.3,-1L11.3,-2.2L11.3,-2.3L13.3,-2.2L13.3,-1.2L14.2,-1.4L14.4,-0.9L13.9,0.2L14.5,0.6L14.4,1.9L14.1,2.5L13.5,2.4L12.4,1.9L12.4,2.3L11.6,2.3L11.5,2.8L11.9,3.3L11.1,3.9M1.7,-42.5L1.4,-42.6M2.5,-51.1L4.1,-50L4.9,-50.1L4.9,-49.8L5.8,-49.5M-51.7,-4.1L-52.7,-2.4L-53,-2.2L-54.6,-2.3M-63,-18.1L-63.1,-18.1M36.5,-14.3L37.3,-14.5L37.6,-14.1L37.9,-14.9L38.5,-14.4L39.1,-14.6L40.2,-14.4L40.8,-14.1L42.4,-12.5L41.8,-11.6L41.8,-11L42.9,-11M43.1,-12.7L42.4,-12.5M9.8,-2.3L11.3,-2.2M-78.9,-1.5L-77.5,-0.6L-76.5,-0.2L-76.3,-0.4L-75.3,0.1M17,-48.6L15,-49L14.7,-48.6L13.8,-48.8M34,-35.1L32.7,-35.2M19,-44.9L18.7,-45.1L16.9,-45.3L16.3,-45L15.8,-45.2L15.7,-44.8L17.6,-42.9M17.7,-42.9L18.4,-42.6M-5.5,-10.4L-4.3,-9.6L-3.2,-9.9L-2.7,-9.5M24,10.9L22.3,11.2L22.2,10L21.8,9.5L21.9,8.3L21.7,7.3L20.6,7.3L20.5,6.9L19.5,7.1L19.3,8L17.5,8.1L17,7.3L16.7,6.2L16.3,5.9L13.1,5.9M12.2,5.8L12.5,5.1L13.1,4.6L13.4,4.8L14.4,4.3L14.8,4.8L16.1,3.5L16.2,2.2L17,1.1L17.8,0.5L18.1,-2L18.6,-3.5L18.6,-4.3L19.5,-5.1L20.6,-4.5L22.4,-4.1L22.8,-4.6L24.3,-5L25.2,-5L25.5,-5.3L27.4,-5.1M29,2.7L29.2,3.1L29.4,4.4M13.3,-2.2L14.5,-2.2L15.7,-1.9L16.1,-1.7L16.2,-2.3L16.6,-3.5L17.4,-3.7L18.6,-3.5M13.1,4.6L12.4,4.6L12,5M-66.9,-1.2L-67.5,-2.1L-68.2,-1.7L-69.8,-1.7L-69.9,-1.1L-69.2,-0.6L-70.1,-0.6L-70.1,0.1L-69.4,1.2L-70,4.2M101.1,-21.6L100.2,-21.5L99.9,-22L99.2,-22.1L99.3,-23.1L98.9,-23.2L98.8,-24.1L97.6,-23.9L97.5,-24.5L98.2,-25.6L98.6,-25.8L98.6,-27.6L98.3,-27.5L97.7,-28.5L97.3,-28.2M91.6,-27.8L91.6,-28L89.5,-28.1L88.9,-27.3M77.8,-35.5L76.8,-35.7M74.5,-37L74.9,-37.2M114.3,-22.5L114,-22.5M113.5,-22.2L113.5,-22.2M-69.5,17.5L-69.1,18.1L-69,19L-68.5,19.4L-68.7,20.5L-68.2,21.3L-67.9,22.8L-67.2,22.8L-67,23L-67.4,24L-68.3,24.4L-68.6,24.8L-68.3,27L-68.8,27.2L-69.7,28.4L-70,29.3L-70,30.4L-70.6,31.6L-69.8,33.3L-69.9,34.2L-70.5,35.3L-70.4,36.1L-71.1,36.5L-71.2,37.8L-71,38.7L-71.4,39L-71.9,40.7L-71.8,42.1L-72.1,42.3L-72.1,43L-71.7,43.9L-71.8,44.4L-71.3,44.8L-72,44.8L-71.4,45.2L-71.7,45.6L-71.7,46.7L-72.5,47.9L-72.4,48.4L-73.1,49.3L-73.5,49.3L-73.5,50.1L-73.2,50.7L-72.5,50.6L-72.4,51.5L-71.9,52L-70,52L-68.4,52.4M-68.6,52.7L-68.7,54.9M22.9,-10.9L22.5,-11L20.3,-9.1L19.1,-9L18.6,-8.1L17.6,-8L16.8,-7.6L16.5,-7.9L15.5,-7.5L15.1,-8.6L14,-9.7L14.2,-10L15.7,-10L15,-11.1L15.1,-11.8L14.5,-13L14.1,-13.1M16.2,-2.3L16.1,-2.9L15.1,-3.8L14.6,-5.3L14.8,-6.3L15.5,-7.5M92.3,-20.8L92.2,-21.3L92.6,-21.3L92.6,-22M2.4,-11.9L2,-11.4L1.4,-11.4L0.9,-11M-57.6,30.2L-55.7,28.2L-54.8,27.5L-53.8,27.1L-53.7,26.2L-53.9,25.7L-54.6,25.6M-58.2,20.2L-57.8,21L-58,22.1L-55.8,22.3L-55.4,24L-54.6,23.8L-54.2,24L-54.6,25.6L-54.8,26.7L-55.8,27.4L-56.4,27.5L-58.6,27.2L-57.6,25.5L-57.8,25.1L-59.2,24.6L-59.9,24.1L-61,23.8L-61.9,23.1L-62.6,22.2L-62.3,20.6L-61.8,19.6L-60,19.3L-59.1,19.3L-58.2,19.8L-58.2,20.2L-57.6,18.3L-57.8,17.5L-58.4,17.2L-58.5,16.3L-60.2,16.3L-60.5,13.8L-61.1,13.5L-61.8,13.5L-63.1,12.7L-64.4,12.4L-65,12L-65.4,11.2L-65.4,9.7L-66.7,10L-68.4,11L-69.6,11M-62.6,22.2L-62.8,22L-64,22.1L-64.3,22.8L-64.6,22.2L-65.8,22.1L-66.2,21.8L-67.2,22.8M44.8,-39.7L45.8,-39.4L46.1,-38.9M46.5,-38.9L46.2,-39.6L45.6,-40L46,-40.2L45,-41.3M45.6,-40.6L45.6,-40.6M45,-41L45,-41"/></g>
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
 "shoot", "zam", "truths", "hlt", "season", "playoff", "trophy", "mroster", "cups"].forEach(g => { DAILY[g] = DAILY[g] || {}; });
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
// Embedded map detail: no map service, extra upload, or API key is required.
// Natural Earth 1:50m admin-1 lines (USA/CAN), 1:10m populated places. Public domain.
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
  return { cw: r.width || 800, ch: r.height || 400 };
}
function setView(x, y, w, h) {
  const { cw, ch } = mapSize(), aspect = cw / ch;
  if (w / h > aspect) { const nh = w / aspect; y -= (nh - h) / 2; h = nh; } else { const nw = h * aspect; x -= (nw - w) / 2; w = nw; }
  const maxW = 360 * MAP_K * 1.05;
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
  const w = Math.min(Math.max(mapView.w * f, 6), 360 * MAP_K * 1.05), s = w / mapView.w;
  setView(cx - (cx - mapView.x) * s, cy - (cy - mapView.y) * s, w, mapView.h * s);
  document.querySelectorAll("[data-region]").forEach(b => b.setAttribute("aria-selected", false));
}
const toMap = (lat, lon) => [lon * MAP_K, -lat];
function drawMapCities() {
  const { cw, ch } = mapSize(), k = mapView.w / cw;
  // Reveal roughly one zoom-button step earlier, fading with zoom depth.
  // Screen-density limits keep the same progression comfortable on phones.
  const capitalOpacity = national => {
    const start = Math.min(national ? 36 : 24, cw * (national ? .095 : .065));
    const full = Math.min(national ? 24 : 16, cw * (national ? .065 : .045));
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
    const [x, y] = toMap(lat, lon), px = (x - mapView.x) / k, py = (y - mapView.y) / k;
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
    const step = Math.sign(wheelPending) * Math.min(Math.abs(wheelPending) * (1 - Math.exp(-elapsed / 45)), .00225 * elapsed);
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
      const v = pinchStart.view, w = Math.min(Math.max(v.w * Math.pow(pinchStart.d / Math.max(1, d), .75), 6), 360 * MAP_K * 1.05);
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
    const delta = Math.max(-100, Math.min(100, pixels)) * .0018;
    if (wheelPending * delta < 0) wheelPending = 0;
    wheelPending = Math.max(-.36, Math.min(.36, wheelPending + delta));
    wheelPoint = { clientX: e.clientX, clientY: e.clientY };
    if (!wheelFrame) wheelFrame = requestAnimationFrame(animateWheel);
  }, { passive: false });
  document.querySelectorAll("[data-region]").forEach(b => b.onclick = () => { stopWheel(); mapRegion(b.dataset.region); });
  $("mapIn").onclick = () => { stopWheel(); mapZoom(1 / 1.5); };
  $("mapOut").onclick = () => { stopWheel(); mapZoom(1.5); };
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

// finish a running arcade game if the player leaves it
function leaveGame(g) {
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
      setTimeout(() => { statsGame = null; openModal("statsModal"); }, party ? 2400 : 1600);
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
  ]},
];
const HL_IDS = Object.keys(HL_STATS).map(s => `hl_${s}`);
const CARD = {};
HUB.forEach(sec => sec.games.forEach(([id, icon]) => { CARD[id] = { icon, tone: sec.tone }; }));
/* Short, repeatable labels make a 22-mode library scannable before a player
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
