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
from concurrent.futures import ThreadPoolExecutor
import traceback
import webbrowser
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
VERSION = "25"


TEMPLATE = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sweater · The Daily NHL Player Guessing Game</title>
<meta name="description" content="Guess the mystery NHL player in 8 tries. A new player every day at midnight ET, plus unlimited mode.">
<meta name="theme-color" content="#528f4f">
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
  }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {
      --bg: #16181b; --fg: #eee; --muted: #9aa; --cell: #2a2d31; --cell-fg: #e6e6e6;
      --hit: #4f8a4c; --hit-fg: #fff; --near: #c9a227; --near-fg: #17140a; --line: #33373c; --link: #6cc3cf;
      --panel: #1f2226; --scrim: rgba(0,0,0,.7); --silbg: var(--cream);
    }
  }
  :root[data-theme="dark"] {
      --bg: #16181b; --fg: #eee; --muted: #9aa; --cell: #2a2d31; --cell-fg: #e6e6e6;
      --hit: #4f8a4c; --hit-fg: #fff; --near: #c9a227; --near-fg: #17140a; --line: #33373c; --link: #6cc3cf;
      --panel: #1f2226; --scrim: rgba(0,0,0,.7); --silbg: var(--cream);
  }
  body, td, .search input, .list, .card { transition: background-color .3s ease, color .3s ease, border-color .3s ease; }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--bg); color: var(--fg);
         font-family: Roboto, "Segoe UI", Helvetica, Arial, sans-serif; }
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
  .topbar { position: absolute; top: 14px; right: 18px; display: flex; align-items: center;
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
  .topleft { position: absolute; top: 14px; left: 18px; display: flex; gap: 8px; }
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
  .help ul { padding-left: 18px; margin: 6px 0; }
  .help a { color: var(--fg); text-underline-offset: 2px; }
  .swatch { display: inline-block; width: 14px; height: 14px; border-radius: 3px; vertical-align: -2px; margin-right: 4px; }
  .toast { position: fixed; left: 50%; top: 80px; transform: translateX(-50%); background: var(--fg); color: var(--bg);
           padding: 8px 14px; border-radius: 6px; font-size: 14px; z-index: 20; opacity: 0; transition: opacity .2s; pointer-events: none; }
  .toast.show { opacity: 1; }
  @media (max-width: 700px) {
    .topleft { top: 10px; left: 12px; }
    .topbar { position: static; justify-content: flex-end; padding: 10px 12px 0; gap: 10px; }
    #modeLabel, .switch .long { display: none; }
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
</style>
</head>
<body>
<div class="topleft">
  <button class="iconbtn" id="statsBtn" type="button" aria-label="Statistics">📊<span class="txt"> Stats</span></button>
  <button class="iconbtn round" id="lbBtn" type="button" aria-label="Leaderboard" title="Leaderboard" hidden>🏆</button>
  <button class="iconbtn round" id="archiveBtn" type="button" aria-label="Archive" title="Archive: replay past puzzles">📅</button>
  <button class="iconbtn round" id="helpBtn" type="button" aria-label="How to play">?</button>
</div>
<div class="topbar">
  <span id="modeLabel">Daily</span>
  <label class="switch"><input type="checkbox" id="unlimited"><span class="track"></span><span>Unlimited<span class="long"> mode</span></span></label>
  <button class="themebtn" id="themeBtn" type="button"></button>
</div>
<header>
  <h1>SWEATER</h1>
  <p class="sub">NHL Player Guessing Game</p>
  <div class="tabrow">
    <div class="tabs" role="tablist" aria-label="Game">
      <button type="button" role="tab" data-game="classic">Classic</button>
      <button type="button" role="tab" data-game="stats">Stats</button>
      <button type="button" role="tab" data-game="hl">Higher or Lower</button>
    </div>
  </div>
  <div class="tabrow" id="subtabs" hidden>
    <div class="tabs small" role="tablist" aria-label="Stats game">
      <button type="button" role="tab" data-game="statline">Guess the player</button>
      <button type="button" role="tab" data-game="team">Guess the team</button>
    </div>
  </div>
  <div class="tabrow" id="hlsubtabs" hidden>
    <div class="tabs small" role="tablist" aria-label="Stat">
      <button type="button" role="tab" data-game="hl_goals">Goals</button>
      <button type="button" role="tab" data-game="hl_assists">Assists</button>
      <button type="button" role="tab" data-game="hl_points">Points</button>
      <button type="button" role="tab" data-game="hl_pim">PIM</button>
    </div>
  </div>
  <p class="archbar" id="archBar" hidden><span id="archText"></span>
    <button class="linkbtn" id="pickDay" type="button">Pick another day</button>
    <button class="linkbtn" id="backToday" type="button">Back to today</button></p>
  <button class="linkbtn" id="silBtn">SHOW SILHOUETTE</button>
  <div class="optrow" id="classicOpts" hidden>
    <label class="switch"><input type="checkbox" id="hardMode"><span class="track"></span><span>Hard mode</span></label>
    <span class="optnote" id="hardNote"></span>
  </div>
</header>
<main>
  <section class="view" id="view-classic">
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
    <p class="hint">Career high means his best single regular season. Ties count as right.<span class="keytip"> Tip: use the ↑ and ↓ keys.</span></p>
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
    <div class="tabs small lbtabs" role="tablist" aria-label="Game">
      <button type="button" role="tab" data-lbgame="classic">Classic</button>
      <button type="button" role="tab" data-lbgame="statline">Guess the player</button>
      <button type="button" role="tab" data-lbgame="team">Guess the team</button>
      <button type="button" role="tab" data-lbgame="hl">Higher or Lower</button>
    </div>
    <div class="tabs small lbtabs" role="tablist" aria-label="Stat" id="lbHl" hidden>
      <button type="button" role="tab" data-lbhl="hl_goals">Goals</button>
      <button type="button" role="tab" data-lbhl="hl_assists">Assists</button>
      <button type="button" role="tab" data-lbhl="hl_points">Points</button>
      <button type="button" role="tab" data-lbhl="hl_pim">PIM</button>
    </div>
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
    <p class="hint">Replay past daily puzzles. Archive games don't count toward your stats or the leaderboard.</p>
    <ol class="arlist" id="arList"></ol>
  </div>
</div>

<div class="modal" id="helpModal" role="dialog" aria-modal="true" aria-labelledby="hTitle">
  <div class="card wide help">
    <button class="xbtn" data-close aria-label="Close">×</button>
    <h2 id="hTitle">How to play</h2>
    <p>Sweater has four games. Pick one with the <b>Classic</b>, <b>Stats</b> and <b>Higher or Lower</b> tabs at the top. Each has a daily puzzle and an unlimited mode.</p>

    <h3>Classic</h3>
    <p>Guess the mystery NHL player in 8 tries. Start typing a name and pick a player from the list. After each guess, the row shows how close that player is to the mystery player.</p>
    <ul>
      <li><span class="swatch" style="background:var(--hit)"></span><b>Green</b> means it's an exact match.</li>
      <li><span class="swatch" style="background:var(--near)"></span><b>Yellow</b> means close:
        <ul>
          <li><b>Age</b> and <b>#</b>: within 2 of the mystery player's value.</li>
          <li><b>Team</b>: the mystery player used to play for the team you guessed at some point in his NHL career, but isn't on it now.</li>
        </ul>
      </li>
      <li><span class="swatch" style="background:var(--cell);border:1px solid var(--line)"></span><b>Grey</b> means no match.</li>
      <li><b>↑ / ↓</b> on age and number means the mystery player's value is higher or lower than your guess.</li>
      <li><b>Team</b>: current NHL team. <b>Conf / Div</b>: East or West; Atlantic (A), Metropolitan (M), Central (C) or Pacific (P).</li>
      <li><b>Pos</b>: C, L, R, D or G. <b>Shoots</b>: L or R (for goalies, the hand they catch with). <b>Nation</b>: country of birth. <b>#</b>: sweater number.</li>
      <li><b>Show silhouette</b> reveals the mystery player's outline if you need a hint.</li>
      <li><b>Hard mode</b> (switch under the tabs) hides the silhouette. Once you make a guess, it's locked until that game ends, and your share result says "Hard mode".</li>
    </ul>

    <h3>Stats: Guess the player</h3>
    <p>You see the mystery player's position and the span of his NHL career, one row per season. Only one season's regular-season stats are shown at the start: games, goals, assists, points and plus/minus (for goalies: games, wins, GAA, save percentage and shutouts). Every wrong guess unlocks another season. You have 8 tries.</p>
    <ul>
      <li>Choose <b>Oldest season first</b> or <b>Newest season first</b> above the table. The choice is locked once you make a guess, until that game ends.</li>
      <li>After 4 wrong guesses, a hint shows the logo of the team he plays for now.</li>
    </ul>

    <h3>Stats: Guess the team</h3>
    <p>You're shown a player and his regular-season stats for one season. Pick the team he played for that season from the list. You have 4 tries. A <span class="swatch" style="background:var(--near)"></span><b>yellow</b> team means close: it's in the same division as the right answer (based on today's divisions).</p>

    <h3>Higher or Lower</h3>
    <p>Two players go head to head. You can see the first player's career high, meaning his best single regular season, in the stat you picked: <b>goals</b>, <b>assists</b>, <b>points</b> or <b>PIM</b> (penalty minutes). Guess whether the second player's career high is <b>higher</b> or <b>lower</b>. Get it right and he moves over to face a new player; get it wrong and your run ends. Ties count as right. The daily run has 40 matchups for each stat, and your score is how many you get right in a row.</p>

    <h3>Daily and Unlimited</h3>
    <ul>
      <li><b>Daily</b>: one puzzle per game per day. Everyone gets the same puzzles, and they switch at 12:00 am Eastern Time (ET). Your results stay until then.</li>
      <li><b>Unlimited</b>: turn on the switch in the top-right corner to play as many random puzzles as you like.</li>
      <li><b>📅 Archive</b> (top left): replay any past daily puzzle for the game you're on. Archive games don't count toward stats or the leaderboard.</li>
      <li><b>Stats</b> (top left) tracks your daily wins, streaks and guess distribution for the game you're on, and lets you share your result. Only daily games count.</li>
      <li class="lbhelp" hidden><b>🏆 Leaderboard</b> (top left): pick a name to put your daily results on a global leaderboard for each game, for today, this week and all time. Each game scores differently:
        <ul>
          <li><b>Classic</b>: 10 points for 1 guess, 9 for 2, down to 3 for 8. A loss scores 0.</li>
          <li><b>Guess the player</b>: 8 points for 1 guess down to 1 for 8, plus 2 bonus points for every season still locked when you get it (up to +10).</li>
          <li><b>Guess the team</b>: 10 points on the first try, 6 on the second, 3 on the third and 1 on the fourth.</li>
          <li><b>Higher or Lower</b> (a separate board for each stat): 1 point for every right answer in a row, up to 40.</li>
        </ul>
        Only daily puzzles count, and each one only counts once.
      </li>
      <li>The 🌙 / ☀️ button switches between night and day mode.</li>
    </ul>

    <h3>Credits</h3>
    <p>Inspired by Bradley Connolly with <a href="https://www.hertl.app/" target="_blank" rel="noopener">hertl.app</a> and the people at <a href="https://poeltl.nbpa.com/" target="_blank" rel="noopener">Poeltl</a>.</p>
    <p style="color:var(--muted)">Player data and headshots come from NHL.com.</p>
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
const DAILY = { classic: /*__DAILY__*/{}, statline: /*__DAILY_SL__*/{}, team: /*__DAILY_TT__*/{} };
const DAILY_HL = /*__DAILY_HL__*/{};   // "YYYY-MM-DD" -> { goals: [ids], assists: [...], points: [...], pim: [...] }
const START = { classic: "/*__START__*/", statline: "/*__START_SL__*/", team: "/*__START_TT__*/", hl: "/*__START_HL__*/" };

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
const validStart = s => s && !/__START/.test(s);
const startOf = g => START[g.startsWith("hl_") ? "hl" : g];
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
    title: "Guess the player", share: "Sweater Stats", view: "view-statline", max: 8, next: "Next player",
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
    title: "Guess the team", share: "Sweater Team", view: "view-team", max: 4, next: "Next puzzle",
    cheers: ["Bang on! 🎯", "Nice read! 🧠", "Got there! 💪", "Last chance, nailed it! 🚨"],
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
  goals:   { key: "a", name: "Goals",   label: "goals",           one: "goal" },
  assists: { key: "b", name: "Assists", label: "assists",         one: "assist" },
  points:  { key: "c", name: "Points",  label: "points",          one: "point" },
  pim:     { key: "d", name: "PIM",     label: "penalty minutes", one: "penalty minute" },
};
const HL_LEN = 40;   // answers in a daily run
const HL_POOL = PLAYERS.filter(p => p.pos !== "G" && seasonsOf(p).reduce((n, r) => n + r.gp, 0) >= 100);
const highCache = new Map();
function careerHigh(p, stat) {
  const k = `${p.id}:${stat}`;
  if (highCache.has(k)) return highCache.get(k);
  let best = { v: 0, y: null };
  for (const r of seasonsOf(p)) {
    const v = r[HL_STATS[stat].key] || 0;
    if (best.y === null || v > best.v) best = { v, y: r.y };
  }
  highCache.set(k, best);
  return best;
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
    if (seq.length && i < 59 && careerHigh(c, stat).v === careerHigh(seq[seq.length - 1], stat).v) continue;
    seq.push(c);
    return;
  }
  seq.push(HL_POOL[Math.floor(rnd() * HL_POOL.length)]);
}

let hlTimer = null;
function makeHL(stat) {
  const info = HL_STATS[stat], id = `hl_${stat}`;
  const unit = v => v === 1 ? info.one : info.label;
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
      const a = careerHigh(t.seq[i], stat).v, b = careerHigh(t.seq[i + 1], stat).v;
      return ans === "H" ? b >= a : b <= a;   // ties count either way
    },
    score(t, guesses) { let n = 0; for (const [i, x] of guesses.entries()) { if (!this.correct(t, i, x)) break; n++; } return n; },
    isWin: () => false,
    isDone(t, guesses) { return guesses.some((x, i) => !this.correct(t, i, x)) || guesses.length >= this.limit(t); },
    wonGame(t, guesses) { return guesses.length >= this.limit(t) && this.score(t, guesses) === guesses.length; },
    player(t) { return t.seq[Math.min(S[id].guesses.length, t.seq.length - 1)]; },
    meta(t) {
      const p = this.player(t), h = careerHigh(p, stat);
      return `Career high: ${h.v} ${unit(h.v)}${h.y ? ` in ${seasonLabel(h.y)}` : ""}`;
    },
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
      const h = careerHigh(p, stat);
      const other = side === "b" ? S[id].target.seq[Math.min(S[id].guesses.length, S[id].target.seq.length - 2)] : null;
      return `<div class="hlcard ${state || ""}">
        <img class="hlimg" src="${esc(p.headshot || FALLBACK)}" alt="" onerror="this.onerror=null;this.src=FALLBACK">
        <p class="hlname">${esc(p.name)}</p>
        <p class="hlteam"><img src="${logo(p.team)}" alt="" onerror="this.remove()">${esc(p.team)} · ${esc(p.pos)}</p>
        ${reveal
          ? `<p class="hlval"><b data-count="${h.v}">${h.v}</b></p><p class="hlunit">career-high ${unit(h.v)}</p><p class="hlyr">${h.y ? `in ${seasonLabel(h.y)}` : ""}</p>`
          : `<p class="hlunit">career-high ${info.label}:</p>
             <div class="hlbtns"><button class="btn hlbtn" type="button" data-hl="H">▲ Higher</button>
             <button class="btn hlbtn" type="button" data-hl="L">▼ Lower</button></div>
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
      $("hlIntro").innerHTML = `Whose career-high <b>${info.label}</b> in a single season is higher?`;
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

// ======================= game engine =======================
const GAME_IDS = Object.keys(G);
const KEYS = {
  classic: { daily: "sweater-daily", stats: "sweater-stats" },
  statline: { daily: "sweater-daily-statline", stats: "sweater-stats-statline" },
  team: { daily: "sweater-daily-team", stats: "sweater-stats-team" },
  ...Object.fromEntries(Object.keys(HL_STATS).map(s => [`hl_${s}`, { daily: `sweater-daily-hl_${s}`, stats: `sweater-stats-hl_${s}` }]))
};
const isStatsGame = g => g === "statline" || g === "team";
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
  $("reveal").src = p.headshot || FALLBACK;
  $("reveal").alt = p.name;
  const text = g.endText && g.endText(st.target, st.guesses, won);
  $("result").textContent = text ? text.result : won ? `You got it in ${n}!` : "Out of guesses";
  $("cheer").textContent = text ? text.cheer : won ? g.cheers[n - 1] : (game === "team" ? "The answer was" : "The mystery player was");
  $("pname").textContent = p.name;
  $("pmeta").textContent = g.meta(st.target);
  $("profile").href = `https://www.nhl.com/player/${p.id}`;
  $("again").textContent = mode === "archive" ? "Pick another day" : g.next;
  $("again").hidden = mode === "daily";
  $("countdown").hidden = mode !== "daily";
  $("banner").classList.toggle("won", won);
  $("banner").classList.remove("pop");
  tick();
  $("banner").style.display = "block";
  if (mode !== "unlimited" && (fresh || !historyGet(game, st.day))) {
    historySet(game, st.day, g.kind === "streak" ? { s: g.score(st.target, st.guesses), w: won } : { n, w: won });
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
      setTimeout(() => openModal("statsModal"), party ? 2400 : 1600);
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
  for (const id of ["guess", "slGuess"]) { $(id).placeholder = text; $(id).disabled = !st.target || st.over; }
  $("modeLabel").textContent = mode === "daily" ? `Daily #${dailyNumber(game, dayKey())}`
    : mode === "archive" ? `Archive #${dailyNumber(game, archiveDay)}` : "Unlimited";
  $("unlimited").checked = mode === "unlimited";
  $("archBar").hidden = mode !== "archive";
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
  game = g;
  store.set("sweater-game", g);
  document.querySelectorAll("[data-game]").forEach(b => {
    const on = b.dataset.game === g || (b.dataset.game === "stats" && isStatsGame(g))
      || (b.dataset.game === "hl" && g.startsWith("hl_"));
    b.setAttribute("aria-selected", on);
  });
  $("subtabs").hidden = !isStatsGame(g);
  $("hlsubtabs").hidden = !g.startsWith("hl_");
  new Set(GAME_IDS.map(id => G[id].view)).forEach(v => { $(v).hidden = v !== G[g].view; });
  document.querySelectorAll(".nodata").forEach(n => n.hidden = true);
  searches.forEach(s => s.close());
  loadCurrent();
}

// ---- archive picker ----
function openArchive() {
  const g = G[game], days = archiveDays(game);
  $("arTitle").textContent = `Archive · ${game === "classic" ? "Classic" : isStatsGame(game) ? `Stats: ${g.title}` : g.title}`;
  const status = d => {
    const h = historyGet(game, d);
    if (!h) return archiveGet(game, d)?.guesses?.length ? "In progress" : "Play";
    if (g.kind === "streak") return `🔥 ${h.s}`;
    return h.w ? `✓ ${h.n}/${g.max}` : "✗";
  };
  $("arList").innerHTML = days.length ? days.map(d => `
    <li><button type="button" class="arbtn${archiveDay === d && mode === "archive" ? " on" : ""}" data-day="${d}">
      <span class="arno">#${dailyNumber(game, d)}</span><span class="ardate">${niceDay(d)}</span>
      <span class="arstat">${status(d)}</span></button></li>`).join("")
    : '<li class="empty">No past puzzles yet for this game. Check back tomorrow.</li>';
  openModal("archiveModal");
}
$("arList").addEventListener("click", e => {
  const b = e.target.closest("[data-day]");
  if (!b) return;
  closeModals();
  mode = "archive";
  loadArchive(b.dataset.day);
  window.scrollTo({ top: 0, behavior: "smooth" });
});
$("archiveBtn").onclick = openArchive;
$("pickDay").onclick = openArchive;
$("backToday").onclick = () => { mode = "daily"; store.set("sweater-mode", "daily"); loadDaily(); };

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
function makeSearch(inputId, listId) {
  const input = $(inputId), ul = $(listId);
  let idx = -1, found = [];
  function close() { ul.hidden = true; idx = -1; input.setAttribute("aria-expanded", false); }
  function choose(p) { if (!p) return; close(); input.value = ""; doGuess(p.id); }
  function render() {
    const q = norm(input.value.trim());
    if (!q) return close();
    const used = S[game].guesses;
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
const searches = [makeSearch("guess", "opts"), makeSearch("slGuess", "slOpts")];
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
function getStats(g = game) {
  const st = Object.assign(blankStats(G[g].max), store.get(KEYS[g].stats) || {});
  st.dist = Array.from({ length: G[g].max }, (_, i) => st.dist[i] || 0);
  return st;
}

function recordResult(won) {
  const day = S[game].day, st = getStats(), n = S[game].guesses.length;
  if (st.lastDay === day) return;
  if (G[game].kind === "streak") {
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
  const st = getStats(), today = dayKey();
  const streak = st.lastWinDay === today || st.lastWinDay === prevDayKey(today) ? st.streak : 0;
  $("sTitle").textContent = game === "classic" ? "Statistics · Classic"
    : isStatsGame(game) ? `Statistics · Stats: ${G[game].title}` : `Statistics · ${G[game].title}`;
  const streakGame = G[game].kind === "streak";
  $("distTitle").hidden = $("dist").hidden = streakGame;
  ["Played", streakGame ? "Best run" : "Win %", streakGame ? "Average" : "Current streak", streakGame ? "Today" : "Max streak"]
    .forEach((label, i) => { $(`stL${i + 1}`).textContent = label; });
  if (streakGame) {
    $("stPlayed").textContent = st.played;
    $("stWin").textContent = st.best || 0;
    $("stStreak").textContent = st.played ? Math.round((st.total || 0) / st.played * 10) / 10 : 0;
    $("stMax").textContent = st.lastDay === today ? st.lastScore : "–";
    const saved = store.get(KEYS[game].daily);
    $("shareBtn").hidden = !(saved && saved.date === today && st.lastDay === today);
    renderStatsLb();
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
  renderStatsLb();
}

function shareText() {
  const g = G[game], saved = store.get(KEYS[game].daily);
  const t = g.daily(saved.date);
  if (g.kind === "streak") {
    const n = g.score(t, saved.guesses), won = g.wonGame(t, saved.guesses);
    const marks = saved.guesses.map((x, i) => g.squares(t, x, i)).join("");
    const rows = (marks.match(/(?:🟩|🟥){1,10}/gu) || []).join("\n");
    const link = !SITE || /__SITE__/.test(SITE) ? "" : `\n\n${SITE}`;
    return `${g.share} #${dailyNumber(game, saved.date)} · ${HL_STATS[g.stat].name}\nStreak: ${n}${won ? " (perfect!)" : ""}\n\n${rows}${link}`;
  }
  const won = saved.guesses.some(x => g.isWin(t, x));
  const body = saved.guesses.map(x => g.squares(t, x)).join("").trim();
  const link = !SITE || /__SITE__/.test(SITE) ? "" : `\n\n${SITE}`;
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
  $(id).classList.add("open");
}
document.querySelectorAll(".modal").forEach(m => m.addEventListener("click", e => {
  if (m.id === "modal" || e.target === m || e.target.closest("[data-close]")) m.classList.remove("open");
}));
$("statsBtn").onclick = () => openModal("statsModal");
$("helpBtn").onclick = () => openModal("helpModal");
$("silBtn").onclick = () => { if (!(S.classic.opts && S.classic.opts.hard)) openModal("modal"); };
$("lbBtn").onclick = () => openLeaderboard();
$("stLbBtn").onclick = () => openLeaderboard();

// ======================= countdown + midnight rollover =======================
function tick() {
  if (mode === "daily" && S[game].day && S[game].day !== dayKey()) { loadDaily(); return; }
  const s = secondsToEtMidnight();
  const pad = n => String(n).padStart(2, "0");
  const clock = `${pad(Math.floor(s / 3600))}:${pad(Math.floor(s / 60) % 60)}:${pad(s % 60)}`;
  $("countdown").textContent = `New puzzle in ${clock}`;
  $("stNext").textContent = clock;
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
document.querySelectorAll("[data-game]").forEach(b => b.addEventListener("click", () => {
  let g = b.dataset.game;
  if (g === "stats") g = isStatsGame(game) ? game : (store.get("sweater-stats-game") || "statline");
  if (g === "hl") g = game.startsWith("hl_") ? game : (G[store.get("sweater-hl-game")] ? store.get("sweater-hl-game") : "hl_points");
  if (!G[g]) return;
  if (isStatsGame(g)) store.set("sweater-stats-game", g);
  if (g.startsWith("hl_")) store.set("sweater-hl-game", g);
  if (g !== game) setGame(g);
}));

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
  if (!game.startsWith("hl_") || document.querySelector(".modal.open") || /INPUT|TEXTAREA/.test(e.target.tagName)) return;
  if (e.key === "ArrowUp") { e.preventDefault(); doGuess("H"); }
  if (e.key === "ArrowDown") { e.preventDefault(); doGuess("L"); }
});
$("hlPair").addEventListener("click", e => {
  const b = e.target.closest("[data-hl]");
  if (b) doGuess(b.dataset.hl);
});

// ======================= global leaderboard =======================
const LB_RULES = {
  ...Object.fromEntries(Object.entries(HL_STATS).map(([s, i]) =>
    [`hl_${s}`, `Higher or Lower (${i.name}): 1 point for every right answer in a row, up to ${HL_LEN}.`])),
  classic: "Classic: 10 points for 1 guess, 9 for 2, down to 3 for 8. A loss scores 0.",
  statline: "Guess the player: 8 points for 1 guess down to 1 for 8, plus 2 for every season still locked when you get it (up to +10).",
  team: "Guess the team: 10 points on the first try, 6 on the second, 3 on the third, 1 on the fourth.",
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

function renderStatsLb() {
  $("stLb").hidden = !API_ON;
  if (!API_ON) return;
  const pts = (store.get("sweater-lb-sent") || {})[`${game}:${dayKey()}`];
  $("stLbText").textContent = !store.get("sweater-lb-name") ? "Add your name to compete with other players."
    : typeof pts === "number" ? `You scored ${pts} ${pts === 1 ? "point" : "points"} today.` : "";
  $("stLbBtn").textContent = store.get("sweater-lb-name") ? "See the leaderboard" : "Join the leaderboard";
}

function openLeaderboard() {
  lbGame = game;
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
  document.querySelectorAll("[data-lbgame]").forEach(b => b.setAttribute("aria-selected",
    b.dataset.lbgame === lbGame || (b.dataset.lbgame === "hl" && lbGame.startsWith("hl_"))));
  document.querySelectorAll("[data-lbhl]").forEach(b => b.setAttribute("aria-selected", b.dataset.lbhl === lbGame));
  $("lbHl").hidden = !lbGame.startsWith("hl_");
  document.querySelectorAll("[data-period]").forEach(b => b.setAttribute("aria-selected", b.dataset.period === lbPeriod));
  $("lbRules").textContent = LB_RULES[lbGame];
  renderLbName();
  const req = ++lbRequest, me = lbIdentity(false), name = store.get("sweater-lb-name");
  if (!$("lbList").children.length) $("lbList").innerHTML = '<li class="empty">Loading…</li>';
  try {
    const d = await api(`/api/leaderboard?game=${lbGame}&period=${lbPeriod}${me ? `&uid=${me.uid}` : ""}`);
    if (req !== lbRequest) return;
    const medal = r => ["🥇", "🥈", "🥉"][r - 1] || r;
    const hlBoard = lbGame.startsWith("hl_");
    $("lbList").innerHTML = d.rows.length ? d.rows.map(r => `
      <li class="${r.me ? "me" : ""}">
        <span class="rk">${medal(r.rank)}</span>
        <span class="nm">${esc(r.name)}${lbPeriod === "today" ? "" : `<small>${r.played} played · ${hlBoard ? `best run ${r.top}` : `${r.wins} won`}</small>`}</span>
        <span class="pt">${r.points} pts${lbPeriod === "today" ? `<small>${hlBoard ? `run of ${r.top}` : r.wins ? `${r.best} ${r.best === 1 ? "guess" : "guesses"}` : "missed"}</small>` : ""}</span>
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

document.querySelectorAll("[data-lbgame]").forEach(b => b.onclick = () => {
  const pickHl = b.dataset.lbgame === "hl";
  if (pickHl && lbGame.startsWith("hl_")) return;
  lbGame = pickHl ? (G[store.get("sweater-hl-game")] ? store.get("sweater-hl-game") : "hl_points") : b.dataset.lbgame;
  $("lbList").innerHTML = ""; renderLeaderboard();
});
document.querySelectorAll("[data-lbhl]").forEach(b => b.onclick = () => { lbGame = b.dataset.lbhl; $("lbList").innerHTML = ""; renderLeaderboard(); });
document.querySelectorAll("[data-period]").forEach(b => b.onclick = () => { lbPeriod = b.dataset.period; $("lbList").innerHTML = ""; renderLeaderboard(); });
$("lbBtn").hidden = !API_ON;
document.querySelectorAll(".lbhelp").forEach(el => el.hidden = !API_ON);

// ======================= start =======================
$("foot").textContent = `Player data from NHL.com · updated ${BUILT} · ${PLAYERS.length} players`;
if (!store.get("sweater-seen-help")) { store.set("sweater-seen-help", true); openModal("helpModal"); }

if (PLAYERS.length) {
  setGame(game);
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


def get_json(url):
    req = urllib.request.Request(url,
                                 headers={"User-Agent": "Mozilla/5.0 (Sweater game builder)"})
    with urllib.request.urlopen(req, timeout=30) as r:
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


HL_STATS = {"goals": 3, "assists": 4, "points": 5, "pim": 6}
HL_LEN = 40


def hl_ok(p):
    """Higher or Lower: skaters with 100+ NHL regular-season games."""
    return p["pos"] != "G" and sum(r[2] for r in p.get("car", [])) >= 100


def career_high(p, stat):
    idx, totals = HL_STATS[stat], {}
    for r in p.get("car", []):
        totals[r[0]] = totals.get(r[0], 0) + (r[idx] if len(r) > idx else 0)
    return max(totals.values()) if totals else 0


def hl_sequence(ids, highs, seed):
    """HL_LEN + 1 players in a row, no repeats, and no two neighbours with the same career high."""
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
    highs = {s: {i: career_high(pool[i], s) for i in ids} for s in HL_STATS}
    for n in range(AHEAD + 1):
        k = (today + timedelta(days=n)).isoformat()
        day = days.setdefault(k, {})
        for s in HL_STATS:
            if s not in day:
                day[s] = hl_sequence(ids, highs[s], f"sweater-hl-{s}-{k}")
    return dict(sorted(days.items()))


def player_of(v):
    return v[0] if isinstance(v, list) else v


def plan_days(days, candidates, today, seed):
    """candidates: {key: value}; values are player ids, or [player id, season] for 'guess the team'."""
    key = lambda v: f"{v[0]}:{v[1]}" if isinstance(v, list) else str(v)
    lock = (today + timedelta(days=LOCK_DAYS)).isoformat()
    days = dict(days)
    # future picks (after tomorrow) are re-drawn if they're no longer possible
    for k in list(days):
        if k > lock and key(days[k]) not in candidates:
            del days[k]
    order = sorted(candidates)
    for i in range(AHEAD + 1):
        k = (today + timedelta(days=i)).isoformat()
        if k in days or not order:
            continue
        kd = date.fromisoformat(k)
        recent = {player_of(v) for d, v in days.items()
                  if abs((date.fromisoformat(d) - kd).days) <= NO_REPEAT_DAYS}
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
    games = {
        # game: (days key, start key, candidates, seed)
        "classic": ("days", "start", {str(i): i for i in pool}, "sweater"),
        "statline": ("statline_days", "statline_start",
                     {str(i): i for i, p in pool.items() if statline_ok(p)}, "sweater-sl"),
        "team": ("team_days", "team_start",
                 {f"{i}:{y}": [i, y] for i, p in pool.items() for y in team_seasons(p)}, "sweater-tt"),
    }
    first = "0000-00-00"   # every past day, for the archive
    last = (today + timedelta(days=EMBED_AHEAD)).isoformat()
    result, new = {}, {}
    for g, (dk, sk, cands, seed) in games.items():
        days = plan_days(sched.get(dk, {}), cands, today, seed)
        start = sched.get(sk) or (today.isoformat() if days else "")
        new[dk], new[sk] = days, start
        result[g] = (start, {k: v for k, v in days.items() if first <= k <= last})

    # remember every scheduled player, so a past answer still works after he leaves the league
    hl_days = plan_hl(sched.get("hl_days", {}), pool, today)
    new["hl_days"] = hl_days
    new["hl_start"] = sched.get("hl_start") or (today.isoformat() if hl_days else "")
    hl_window = {k: v for k, v in hl_days.items() if first <= k <= last}
    result["hl"] = (new["hl_start"], hl_window)

    for dk in ("days", "statline_days", "team_days"):
        for v in new[dk].values():
            if player_of(v) in pool:
                archive[player_of(v)] = pool[player_of(v)]
    for day in hl_days.values():
        for seq in day.values():
            for i in seq:
                if i in pool:
                    archive[i] = pool[i]
    new["players"] = {str(k): v for k, v in sorted(archive.items())}
    SCHEDULE.write_text(json.dumps(new, ensure_ascii=False, indent=1), encoding="utf-8")

    needed = {player_of(v) for g, (_, window) in result.items() if g != "hl" for v in window.values()}
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
    teams, rows = [], []
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
        if row.get("gameTypeId", 2) != 2:
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
        rows.append([year, ab or "", gp] + stats)
    rows.sort(key=lambda r: r[0])  # stable: keeps trade order within a season
    return teams, rows


def add_career_teams(players):
    try:
        cache = json.loads(CACHE.read_text(encoding="utf-8"))
    except Exception:
        cache = {}
    today = date.today()

    def fresh(pid):
        c = cache.get(str(pid))
        return bool(c) and c.get("v") == 4 and (today - date.fromisoformat(c["day"])).days < CACHE_DAYS

    todo = [p["id"] for p in players if not fresh(p["id"])]
    print(f"\nLoading career history and stats ({len(players) - len(todo)} saved, {len(todo)} to download)...")

    def job(pid):
        try:
            return pid, career_data(pid)
        except Exception:
            return pid, None

    failed = 0
    with ThreadPoolExecutor(max_workers=6) as pool:
        for i, (pid, result) in enumerate(pool.map(job, todo), 1):
            if result is None:
                failed += 1
            else:
                cache[str(pid)] = {"day": today.isoformat(), "v": 4, "teams": result[0], "car": result[1]}
            if i % 50 == 0 or i == len(todo):
                print(f"  {i}/{len(todo)}")
    if failed:
        print(f"  {failed} players' history couldn't be loaded (no yellow hints or stats games for them).")
    try:
        CACHE.write_text(json.dumps(cache), encoding="utf-8")
    except Exception:
        pass

    for p in players:
        entry = cache.get(str(p["id"])) or {}
        p["past"] = [t for t in entry.get("teams", []) if t != p["team"]]
        if entry.get("car"):
            p["car"] = entry["car"]
    print(f"  Stats games: {sum(map(statline_ok, players))} players for 'guess the player', "
          f"{sum(len(team_seasons(p)) > 0 for p in players)} for 'guess the team', "
          f"{sum(map(hl_ok, players))} for 'higher or lower'.")


def recent_games():
    """NHL regular-season games per player: last season + this season."""
    today = date.today()
    start = today.year if today.month >= 7 else today.year - 1
    seasons = [f"{start - 1}{start}", f"{start}{start + 1}"]
    games = {}
    for season in seasons:
        for kind in ("skater", "goalie"):
            try:
                rows = get_json(STATS.format(kind=kind, season=season)).get("data", [])
            except Exception as e:
                print(f"  (couldn't load {kind} stats for {season}: {e})", file=sys.stderr)
                continue
            for r in rows:
                pid = r.get("playerId")
                games[pid] = games.get(pid, 0) + (r.get("gamesPlayed") or 0)
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
            })
    return out


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
        print("Loading NHL games played...")
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
        print(f"  {team}: {len(batch)} players")
        time.sleep(0.3)  # be polite to the NHL API

    if not players:
        sys.exit("No players fetched - check your internet connection.")

    if not args.no_career:
        add_career_teams(players)

    today = eastern_today()
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
        "/*__DAILY__*/{}": esc(games["classic"][1]),
        "/*__DAILY_SL__*/{}": esc(games["statline"][1]),
        "/*__DAILY_TT__*/{}": esc(games["team"][1]),
        "/*__START__*/": games["classic"][0],
        "/*__START_SL__*/": games["statline"][0],
        "/*__START_TT__*/": games["team"][0],
        "/*__DAILY_HL__*/{}": esc(games["hl"][1]),
        "/*__START_HL__*/": games["hl"][0],
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
