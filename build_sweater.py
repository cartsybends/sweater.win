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
VERSION = "47 · Rinkside"


TEMPLATE = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sweater · The Daily NHL Player Guessing Game</title>
<meta name="description" content="Guess the mystery NHL player in 8 tries. A new player every day at midnight ET, plus unlimited mode.">
<meta name="theme-color" content="#0b2538">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Sweater">
<meta property="og:title" content="Sweater · The Daily NHL Player Guessing Game">
<meta property="og:description" content="Guess the mystery NHL player in 8 tries. A new player every day.">
<meta property="og:url" content="/*__SITE__*/">
<meta property="og:image" content="/*__SITE__*/og-image.png">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="Sweater · The Daily NHL Player Guessing Game">
<meta name="twitter:description" content="Guess the mystery NHL player in 8 tries. A new player every day.">
<meta name="twitter:image" content="/*__SITE__*/og-image.png">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🏒</text></svg>">
<script>
  // apply saved day/night choice before the page paints
  try { const t = JSON.parse(localStorage.getItem("sweater-theme")); if (t) document.documentElement.dataset.theme = t; } catch {}
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
    <label class="switch" title="Play as many puzzles as you like"><input type="checkbox" id="unlimited"><span class="track"></span><span>Unlimited</span></label>
    <button class="iconbtn round themebtn" id="themeBtn" type="button"></button>
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
    <div id="hubSections"></div>
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
      <div class="hlscore"><span>Time<b id="cuTime">600</b></span><span>Squares<b id="cuCount">0/0</b></span></div>
      <div class="numrow wide">
        <input id="cuInput" autocomplete="off" autocorrect="off" autocapitalize="words" spellcheck="false" enterkeyhint="send"
               placeholder="Press Start to begin" aria-label="Team or player name">
        <button class="btn" id="cuStart" type="button">Start</button>
      </div>
      <p class="hint romsg" id="cuMsg" aria-live="polite"></p>
    </div>
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
      <li><span aria-hidden="true">🌙</span>Night and day mode</li>
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
const TROPHY_WINNERS = /*__TROPHIES__*/[];   // [trophy, season start year, winner]
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
const logo = t => `https://assets.nhle.com/logos/nhl/svg/${t}_light.svg`;
const FALLBACK = "data:image/svg+xml," + encodeURIComponent(
  `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><circle cx='50' cy='38' r='20'/><path d='M12 100c2-26 18-38 38-38s36 12 38 38z'/></svg>`);

// ======================= helpers =======================
const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
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
TEAM_NAMES.ARI = "Arizona";
TEAM_NAMES.ATL = "Atlanta";
const KNOWN_TEAMS = new Set([...Object.keys(TEAMS), "ARI", "ATL"]);
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
  let start = null, moved = false, pinchStart = null;
  svg.addEventListener("pointerdown", e => {
    svg.setPointerCapture(e.pointerId);
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pointers.size === 1) { start = { x: e.clientX, y: e.clientY, view: { ...mapView } }; moved = false; }
    if (pointers.size === 2) {
      const [a, b] = [...pointers.values()];
      pinchStart = { d: Math.hypot(a.x - b.x, a.y - b.y), view: { ...mapView } };
      moved = true;
    }
  });
  svg.addEventListener("pointermove", e => {
    if (!pointers.has(e.pointerId)) return;
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    const { cw } = mapSize();
    if (pointers.size === 2 && pinchStart) {
      const [a, b] = [...pointers.values()], d = Math.hypot(a.x - b.x, a.y - b.y);
      const v = pinchStart.view, w = Math.min(Math.max(v.w * pinchStart.d / d, 6), 360 * MAP_K * 1.05), s = w / v.w;
      setView(v.x + (v.w - w) / 2, v.y + (v.h - v.h * s) / 2, w, v.h * s);
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
  svg.addEventListener("wheel", e => {
    e.preventDefault();
    const p = svgPoint(e);
    mapZoom(e.deltaY > 0 ? 1.2 : 1 / 1.2, p.x, p.y);
  }, { passive: false });
  document.querySelectorAll("[data-region]").forEach(b => b.onclick = () => mapRegion(b.dataset.region));
  $("mapIn").onclick = () => mapZoom(1 / 1.5);
  $("mapOut").onclick = () => mapZoom(1.5);
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
  const metric = pick(Object.keys(HLT_METRICS)), seq = [];
  while (seq.length < HL_LEN + 1) {
    const recent = seq.slice(-4).map(x => x[0]);
    let t = null;
    for (let i = 0; i < 60 && !t; i++) {
      const c = teams[Math.floor(rnd() * teams.length)];
      if (seq.length && hltValue(c, metric) === seq[seq.length - 1][1]) continue;
      if ((i < 40 ? recent : recent.slice(-1)).includes(c)) continue;
      t = c;
    }
    seq.push([t || teams[0], hltValue(t || teams[0], metric)]);
  }
  return { metric, seq, rid: Math.random() };
}
G.hlt = {
  kind: "streak", repeat: true, title: "Team Higher or Lower", share: "Sweater Team H/L", view: "view-hlt",
  max: HL_LEN, next: "Play again", hideReveal: true,
  pool: () => Object.keys(TEAMS).filter(t => PLAYERS.filter(p => p.team === t).length >= 10),
  daily(k) {
    const v = DAILY.hlt[k];
    if (v && v.seq && v.seq.length > 1 && HLT_METRICS[v.metric]) return v;
    return hltRandom(seeded(hash("sweater-hlt-" + k)));
  },
  random: () => hltRandom(Math.random),
  tid: t => t.rid ? `hlt:${t.rid}` : `${t.metric}:${hash(t.seq.map(x => x[0]).join())}`,
  limit: t => t.seq.length - 1,
  correct(t, i, ans) { const a = Number(t.seq[i][1]), b = Number(t.seq[i + 1][1]); return ans === "H" ? b >= a : b <= a; },
  score(t, g) { let n = 0; for (const [i, x] of g.entries()) { if (!this.correct(t, i, x)) break; n++; } return n; },
  isWin: () => false,
  isDone(t, g) { return g.some((x, i) => !this.correct(t, i, x)) || g.length >= this.limit(t); },
  wonGame(t, g) { return g.length >= this.limit(t) && this.score(t, g) === g.length; },
  player: () => null,
  meta(t) {
    const i = Math.min(S.hlt.guesses.length, t.seq.length - 1), info = HLT_METRICS[t.metric];
    return `${teamName(t.seq[i][0])}: ${info.show(t.seq[i][1])} ${info.unit}`;
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
    return `Sweater Team H/L #${num} · ${HLT_METRICS[t.metric].name}\nStreak: ${this.score(t, saved.guesses)}${won ? " (perfect!)" : ""}\n\n${rows}${link}`;
  },
  onFinish(st) { const k = `sweater-hlt-best-${st.target.metric}`, n = this.score(st.target, st.guesses);
    if (n > (store.get(k) || 0)) store.set(k, n); },
  reset() { clearTimeout(this.timer); this.pending = false; },
  card(t, i, reveal, state) {
    const [team, value] = t.seq[i], info = HLT_METRICS[t.metric];
    const other = teamName(t.seq[Math.max(0, i - 1)][0]);
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
    if (i + 1 >= t.seq.length) return null;
    const ok = this.correct(t, i, x);
    if (fresh) {
      this.pending = true;
      $("htB").innerHTML = this.card(t, i + 1, true, ok ? "ok" : "bad");
      clearTimeout(this.timer);
      this.timer = setTimeout(() => { this.pending = false; if (game === "hlt") this.render(t, S.hlt, true); }, ok ? 1100 : 1400);
    }
    return ok;
  },
  render(t, st, slide = false) {
    if (this.pending) return;
    const info = HLT_METRICS[t.metric];
    $("htIntro").innerHTML = `Which team has the higher <b>${esc(info.name.toLowerCase())}</b>?`;
    $("htStreak").textContent = this.score(t, st.guesses);
    $("htBest").textContent = Math.max(store.get(`sweater-hlt-best-${t.metric}`) || 0, this.score(t, st.guesses));
    $("htLeft").textContent = st.over ? "" : `${Math.max(0, this.limit(t) - st.guesses.length)} left in today's run · ties count as right`;
    const i = st.over ? Math.max(0, Math.min(st.guesses.length, t.seq.length - 1) - 1) : st.guesses.length;
    const lastOk = st.over && st.guesses.length ? this.correct(t, st.guesses.length - 1, st.guesses[st.guesses.length - 1]) : null;
    $("htA").innerHTML = this.card(t, i, true, "");
    $("htB").innerHTML = this.card(t, i + 1, st.over, st.over ? (lastOk ? "ok" : "bad") : "");
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
  const winners = new Map(), byTrophy = {};
  for (const [t, y, w] of TROPHY_WINNERS) {
    if (!t || !Number.isInteger(y) || !w) continue;
    winners.set(`${t}:${y}`, { t, y, w });
    byTrophy[t] = [...(byTrophy[t] || []), { y, w }];
  }
  for (const day of Object.values(DAILY.trophy || {})) {
    for (const r of day.rounds || []) {
      const names = r.names || (r.ids || []).map(i => (BYID.get(i) || {}).name);
      if (!names || !names[r.a]) continue;
      winners.set(`${r.t}:${r.y}`, { t: r.t, y: r.y, w: names[r.a] });
    }
  }
  return { winners: [...winners.values()], byTrophy };
})();
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
    const names = shuffled(pool, rnd).slice(0, 3).map(x => x.w);
    const a = Math.floor(rnd() * 4);
    names.splice(a, 0, e.w);
    rounds.push({ t: e.t, y: e.y, names, a });
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
      return { rounds: v.rounds.map(r => ({ ...r, names: r.names || r.ids.map(i => (BYID.get(i) || {}).name || "?") })) };
    }
    return trophyRandom(seeded(hash(`sweater-trophy-${trophy}-${k}`)), trophy);
  },
  random() { return trophyRandom(Math.random, this.trophy()); },
  tid: t => `trophy:${this.trophy()}:${t.rid || hash(t.rounds.map(r => `${r.t}${r.y}`).join())}`,
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
      : `Who won the <b>${esc(r.t)}</b> for ${seasonLabel(r.y)}?`;
    $("trOpts").innerHTML = st.over && !showing ? "" : r.names.map((name, n) => {
      const cls = showing ? (n === r.a ? " right" : n === Number(st.guesses[last]) ? " wrong" : " dim") : "";
      return `<button type="button" class="shopt${cls}" data-c="${n}"${showing ? " disabled" : ""}>${esc(name)}</button>`;
    }).join("");
    $("trMsg").textContent = showing
      ? (this.right(t, st.guesses[last], last) ? "Correct!" : `It was ${t.rounds[last].names[t.rounds[last].a]}.`)
      : st.over ? "" : "Winners from 1980 onwards, including retired players. Wrong answers are winners of this trophy from the same era.";
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
  "minnesota north stars":"MNS", "montreal canadiens":"MTL", "mighty ducks of anaheim":"ANA", "nashville predators":"NSH",
  "new jersey devils":"NJD", "new york islanders":"NYI", "new york rangers":"NYR", "ottawa senators":"OTT",
  "philadelphia flyers":"PHI", "pittsburgh penguins":"PIT", "san jose sharks":"SJS", "st louis blues":"STL",
  "tampa bay lightning":"TBL", "vancouver canucks":"VAN", "vegas golden knights":"VGK", "washington capitals":"WSH"
};
const cupsTeamAbbr = value => TEAMS[value] ? value : (CUP_TEAM_ABBRS[cupsNorm(value)] || "");
const cupsAnswer = (name, team) => {
  const abbr = cupsTeamAbbr(team);
  return `<span class="cuanswer">${abbr ? `<img class="culogo" src="${logo(abbr)}" alt="" onerror="this.remove()">` : ""}<span>${esc(name)}</span></span>`;
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
    $("cuTime").textContent = st.over ? 0 : running ? Math.max(0, Math.ceil((st.endsAt - Date.now()) / 1000)) : CUPS_SECONDS;
    $("cuStart").hidden = running || !!st.over;
    $("cuInput").disabled = !running;
    $("cuInput").placeholder = running ? "Type a team or player, then press Enter" : st.over ? "Time's up" : "Press Start to begin";
    const cols = cupsCols(t);
    $("cuHead").innerHTML = `<th>Season</th><th>Stanley Cup</th><th>Runner-up</th>` + (cols.length === 3 ? "<th>Conn Smythe</th>" : "");
    $("cuRows").innerHTML = t.rows.map((r, i) => `<tr>
      <td class="cuyear">${seasonLabel(r[0])}</td>
      ${cols.map((c, ci) => {
        const got = marks[i * cols.length + ci];
        const team = c === 3 ? r[4] : r[c];
        return `<td class="cucell${got ? " got" : st.over ? " miss" : ""}">${got || st.over ? cupsAnswer(r[c], team) : ""}</td>`;
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
      $("cuTime").textContent = left;
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

function startGame(t, restore = [], opts) {
  const st = S[game], g = G[game];
  Object.assign(st, { target: t, guesses: [], over: false, mode, opts: opts || prefOpts(game) });
  hideBanner();
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
  if (fresh) {
    const party = g.celebrate ? g.celebrate(st.target, st.guesses, won) : won;
    void $("banner").offsetWidth; // restart the pop animation
    $("banner").classList.add("pop");
    if (party) confetti();
    if (g.onFinish) g.onFinish(st);
    if (mode === "daily") {
      recordResult(won);
      submitPending();
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
  $("gIcon").textContent = card.icon;
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
$("shareBtn").onclick = async () => {
  const text = shareText();
  try { await navigator.clipboard.writeText(text); toast("Result copied to clipboard"); }
  catch {
    const ta = Object.assign(document.createElement("textarea"), { value: text });
    document.body.appendChild(ta); ta.select();
    try { document.execCommand("copy"); toast("Result copied to clipboard"); } catch { toast("Couldn't copy the result"); }
    ta.remove();
  }
};

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

// ---- day / night toggle ----
const isDark = () => {
  const t = document.documentElement.dataset.theme;
  return t ? t === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
};
function paintThemeBtn() {
  const dark = isDark();
  $("themeBtn").textContent = dark ? "☀️" : "🌙";
  $("themeBtn").setAttribute("aria-label", dark ? "Switch to day mode" : "Switch to night mode");
  $("themeBtn").title = $("themeBtn").getAttribute("aria-label");
}
$("themeBtn").onclick = () => {
  const next = isDark() ? "light" : "dark";
  document.documentElement.dataset.theme = next;
  store.set("sweater-theme", next);
  paintThemeBtn();
};
paintThemeBtn();
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

function renderHub() {
  let played = 0, total = 0;
  $("hubSections").innerHTML = HUB.map(sec => `
    <section class="hubsec tone-${sec.tone}">
      <h2>${sec.title}</h2>
      <div class="glist">${sec.games.map(([id, icon, blurb]) => {
        const [cls, text] = hubStatus(id);
        total++; if (cls === "done" || cls === "missed") played++;
        const ready = id === "hl" ? HL_POOL.length > 1 : G[id].pool().length > 0;
        return `<button type="button" class="grow ${cls}" data-open="${id}"${ready ? "" : " disabled"}>
          <span class="gicon" aria-hidden="true">${icon}</span>
          <span class="gtext"><b>${esc(cardTitle(id))}</b><small>${esc(blurb)}</small></span>
          <span class="gstat">${ready ? esc(text) : "Not available"}</span>
          <span class="chev" aria-hidden="true">›</span>
        </button>`;
      }).join("")}</div>
    </section>`).join("");
  $("hubProgress").textContent = `${played} of ${total} played today.`;
  $("hubBar").style.width = `${Math.round(played / total * 100)}%`;
  $("hubDate").textContent = new Date().toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" });
  document.querySelector(".partycard").disabled = !API_ON;
  document.querySelector(".partycard .partycta").textContent = API_ON ? "Start a party" : "Not available";
}
$("view-hub").addEventListener("click", e => {
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
  $("gIcon").textContent = "🎉";
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
      <summary><span class="hicon" aria-hidden="true">${icon}</span><span>${esc(cardTitle(id))}</span></summary>
      <div class="helpbody">${HELP[id] || ""}</div>
    </details>`).join("")).join("");
  $("helpLead").hidden = !current;
  if (current) {
    $("helpLead").textContent = `You're playing ${cardTitle(current)}. Its rules are open below.`;
    requestAnimationFrame(() => { const el = $("helpGames").querySelector("[open]"); if (el) el.scrollIntoView({ block: "nearest" }); });
  }
}

// ======================= start =======================
$("foot").textContent = `Player data from NHL.com · updated ${BUILT} · ${PLAYERS.length} players`;
if (!store.get("sweater-seen-help")) { store.set("sweater-seen-help", true); openModal("helpModal"); }

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


KNOWN_TEAMS = CURRENT_TEAMS | {"ARI", "ATL"}


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
    "VAN": "Vancouver", "VGK": "Vegas", "WSH": "Washington", "WPG": "Winnipeg"}
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
    metric = rnd.choice(HLT_METRICS)
    values = {t: hlt_value(rosters[t], metric) for t in teams}
    seq = []
    while len(seq) < HL_LEN + 1:
        recent = [x[0] for x in seq[-4:]]
        pick = None
        for attempt in range(60):
            t = rnd.choice(teams)
            if seq and values[t] == seq[-1][1]:
                continue
            if t in (recent if attempt < 40 else recent[-1:]):
                continue
            pick = t
            break
        pick = pick if pick else rnd.choice(teams)
        seq.append([pick, values[pick]])
    return {"metric": metric, "seq": seq}


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
    smythe = {y: w for t, y, w in AWARD_HISTORY if "Conn Smythe" in t}
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
    """Trophy winners from Wikipedia's per-trophy tables: [(trophy, season start year, winner)]."""
    rows = []
    for title in WIKI_TROPHIES:
        found = []
        for text, names in wiki_html_rows(title):
            season = SEASON_RE.search(text)
            if not season:
                continue
            for name in names:
                if " " not in name or NOT_A_PLAYER.search(name) or re.search(r"\d", name):
                    continue
                found.append((title, int(season.group(1)), name))
                break
        if len(found) >= 10:
            rows += found
        else:
            print(f"  (Wikipedia: couldn't read the winners table for {title})", file=sys.stderr)
    return sorted(set(rows))


def report_trophies(rows):
    counts = {}
    for t, y, w in rows:
        counts[t] = counts.get(t, 0) + 1
    print("    " + ", ".join(f"{t.replace(' Trophy', '').replace(' Memorial', '')}: {n}"
                             for t, n in sorted(counts.items())))


def fetch_award_history(cache, today):
    """[(trophy, season start year, winner name)] for every winner the NHL lists, retired players included."""
    saved = cache.get("_trophies")
    if saved and (today - date.fromisoformat(saved["day"])).days < 14 and saved.get("rows"):
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
                if not winner:
                    first, last = dig(sn, "firstName"), dig(sn, "lastName")
                    winner = f"{first} {last}" if first and last else None
                try:
                    year = int(str(season)[:4])
                except (TypeError, ValueError):
                    continue
                if name and winner and 1900 < year < 2100:
                    found.append((str(name), year, str(winner).strip()))
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
        cache["_trophies"] = {"day": today.isoformat(), "rows": [list(r) for r in rows]}
    else:
        print("  Award history: neither the NHL's award lists nor Wikipedia were reachable, "
              "so Trophy Case uses current players only.")
    return rows


def trophy_entries(players, history=()):
    """(trophy, year, winner name) — the league's full history when we have it."""
    out = [(t, y, w) for t, y, w in history
           if y >= TROPHY_FIRST_YEAR and not any(skip in t for skip in TROPHY_SKIP)]
    if not out:
        for p in players:
            for name, year in p.get("aw", []):
                if not any(skip in name for skip in TROPHY_SKIP):
                    out.append((name, year, p["name"]))
    return sorted(set(out))


def trophy_puzzle(players, entries, rnd):
    if len(entries) < 12:
        return None
    by_trophy = {}
    for t, y, w in entries:
        by_trophy.setdefault(t, []).append((y, w))
    rounds, used = [], set()
    for _ in range(3000):
        if len(rounds) == 20:
            return {"rounds": rounds}
        t, y, w = rnd.choice(entries)
        if (t, y) in used:
            continue
        # the wrong options are always other winners of the same trophy, so a Vezina round
        # never lists a skater; a trophy with too few winners is skipped instead
        all_others = [(yy, n) for yy, n in by_trophy[t] if n != w]
        others = [(yy, n) for yy, n in all_others if abs(yy - y) <= 12]
        if len({n for _, n in others}) < 3:
            others = [(yy, n) for yy, n in all_others if abs(yy - y) <= 20]
        if len({n for _, n in others}) < 3:
            others = all_others
        others = list(dict.fromkeys(n for _, n in sorted(others, key=lambda item: abs(item[0] - y))))
        if len(others) < 3:
            continue
        names = rnd.sample(others, 3)
        a = rnd.randrange(4)
        names.insert(a, w)
        rounds.append({"t": t, "y": y, "names": names, "a": a})
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
    if "rounds" in v:                                    # two truths, trophy case
        out = []
        for r in v["rounds"]:
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
    og = HERE / "og-image.png"
    if og.exists() and out.parent != HERE:
        shutil.copy(og, out.parent / "og-image.png")
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
