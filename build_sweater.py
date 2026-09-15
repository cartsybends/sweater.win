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
VERSION = "18"


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
  table { border-collapse: separate; border-spacing: 8px; margin: 0 auto; min-width: 1000px; }
  th { font-weight: 400; font-size: 16px; padding: 4px 0 8px; border-bottom: 1px solid var(--line); }
  td { height: 72px; background: var(--cell); color: var(--cell-fg); text-align: center;
       font-size: 16px; padding: 0 14px; min-width: 120px; }
  td.name { background: none; text-align: left; min-width: 200px; padding-left: 4px; }
  td.team { min-width: 90px; }
  td.team img { width: 34px; height: 34px; display: block; margin: 0 auto 2px; }
  td.hit { background: var(--hit); color: var(--hit-fg); }
  td.near { background: var(--near); color: var(--near-fg); }
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
    table, tbody { display: block; min-width: 0; }
    thead { display: none; }
    tr { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; margin: 0 0 16px; }
    td { display: flex; flex-direction: column; align-items: center; justify-content: center;
         height: 58px; min-width: 0; padding: 14px 2px 4px; font-size: 14px; position: relative; }
    td::before { content: attr(data-label); position: absolute; top: 4px; left: 0; right: 0;
                 font-size: 10px; opacity: .75; }
    td.name { grid-column: 1 / -1; height: auto; padding: 0 2px; font-weight: 600; font-size: 15px;
              align-items: flex-start; min-width: 0; }
    td.name::before { content: none; }
    td.team { min-width: 0; flex-direction: row; gap: 4px; }
    td.team img { width: 20px; height: 20px; margin: 0; }
    .num { padding: 0; gap: 4px; justify-content: center; }
    .arrow { font-size: 16px; }
    .card { padding: 20px; }
    .statgrid b { font-size: 26px; }
  }
  .foot small { display: block; margin-top: 6px; font-size: 12px; opacity: .85; }
  .foot { text-align: center; color: var(--muted); font-size: 13px; padding: 32px 16px 8px; }
  @media (prefers-reduced-motion: no-preference) {
    td { transition: background .3s; }
    tr.newrow { animation: rowin .35s cubic-bezier(.2,.8,.2,1) both; }
  }
  @keyframes rowin { from { opacity: 0; transform: translateY(-8px); } to { opacity: 1; transform: none; } }
</style>
</head>
<body>
<div class="topleft">
  <button class="iconbtn" id="statsBtn" type="button" aria-label="Statistics">📊 Stats</button>
  <button class="iconbtn round" id="helpBtn" type="button" aria-label="How to play">?</button>
</div>
<div class="topbar">
  <span id="modeLabel">Daily</span>
  <label class="switch"><input type="checkbox" id="unlimited"><span class="track"></span>Unlimited<span class="long">&nbsp;mode</span></label>
  <button class="themebtn" id="themeBtn" type="button"></button>
</div>
<header>
  <h1>SWEATER</h1>
  <p class="sub">NHL Player Guessing Game</p>
  <button class="linkbtn" id="silBtn">SHOW SILHOUETTE</button>
</header>
<main>
  <div class="search">
    <input id="guess" autocomplete="off" role="combobox" aria-expanded="false"
           aria-controls="opts" placeholder="Guess 1 of 8">
    <ul class="list" id="opts" role="listbox" hidden></ul>
  </div>
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
  <div class="board">
    <table>
      <thead><tr><th></th><th>TEAM</th><th>CONF</th><th>DIV</th><th>POS</th><th>SHOOTS</th><th>AGE</th><th>NATION</th><th>#</th></tr></thead>
      <tbody id="rows"></tbody>
    </table>
  </div>
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
      <div><b id="stPlayed">0</b><span>Played</span></div>
      <div><b id="stWin">0</b><span>Win %</span></div>
      <div><b id="stStreak">0</b><span>Current streak</span></div>
      <div><b id="stMax">0</b><span>Max streak</span></div>
    </div>
    <h3>Guess distribution</h3>
    <div id="dist"></div>
    <div class="statfoot">
      <div><small>Next player</small><b id="stNext">--:--:--</b></div>
      <button class="btn" id="shareBtn" type="button">Share</button>
    </div>
  </div>
</div>

<div class="modal" id="helpModal" role="dialog" aria-modal="true" aria-labelledby="hTitle">
  <div class="card wide help">
    <button class="xbtn" data-close aria-label="Close">×</button>
    <h2 id="hTitle">How to play</h2>
    <p>Guess the mystery NHL player in 8 tries. Start typing a name and pick a player from the list. After each guess, the row shows how close that player is to the mystery player.</p>
    <h3>Colours</h3>
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
    </ul>
    <h3>Categories</h3>
    <ul>
      <li><b>Team</b>: current NHL team.</li>
      <li><b>Conf / Div</b>: East or West; Atlantic (A), Metropolitan (M), Central (C) or Pacific (P).</li>
      <li><b>Pos</b>: C (centre), L (left wing), R (right wing), D (defence) or G (goalie).</li>
      <li><b>Shoots</b>: L or R. For goalies, this is the hand they catch with.</li>
      <li><b>Age</b>, <b>Nation</b> (country of birth) and <b>#</b> (sweater number).</li>
    </ul>
    <h3>Modes</h3>
    <ul>
      <li><b>Daily</b>: one mystery player per day. Everyone gets the same player, and it switches at 12:00 am Eastern Time (ET). Your result stays until then. Only daily games count toward your stats.</li>
      <li><b>Unlimited</b>: turn on the switch in the top-right corner to play as many random players as you like.</li>
    </ul>
    <h3>Extras</h3>
    <ul>
      <li><b>Show silhouette</b> reveals the mystery player's outline if you need a hint.</li>
      <li><b>Stats</b> tracks your daily wins, streaks and guess distribution, and lets you share your result.</li>
      <li>The 🌙 / ☀️ button switches between night and day mode.</li>
    </ul>
    <h3>Credits</h3>
    <p>Inspired by Bradley Connolly with <a href="https://www.hertl.app/" target="_blank" rel="noopener">hertl.app</a> and the people at <a href="https://poeltl.nbpa.com/" target="_blank" rel="noopener">Poeltl</a>.</p>
    <p style="color:var(--muted)">Player data and headshots come from NHL.com.</p>
  </div>
</div>

<div class="toast" id="toast" role="status"></div>

<script>
// Filled in by build_sweater.py from api-web.nhle.com
const PLAYERS = /*__PLAYERS__*/[].sort((a, b) => a.id - b.id);
const BUILT = "/*__BUILT__*/";
const SITE = "/*__SITE__*/";
const DAILY = /*__DAILY__*/{};   // "YYYY-MM-DD" (Eastern) -> player id
const START = "/*__START__*/";   // date of Daily #1

const MAX = 8;
// abbr: [conference, division]
const TEAMS = {
  BOS:["East","A"],BUF:["East","A"],DET:["East","A"],FLA:["East","A"],MTL:["East","A"],OTT:["East","A"],TBL:["East","A"],TOR:["East","A"],
  CAR:["East","M"],CBJ:["East","M"],NJD:["East","M"],NYI:["East","M"],NYR:["East","M"],PHI:["East","M"],PIT:["East","M"],WSH:["East","M"],
  CHI:["West","C"],COL:["West","C"],DAL:["West","C"],MIN:["West","C"],NSH:["West","C"],STL:["West","C"],UTA:["West","C"],WPG:["West","C"],
  ANA:["West","P"],CGY:["West","P"],EDM:["West","P"],LAK:["West","P"],SEA:["West","P"],SJS:["West","P"],VAN:["West","P"],VGK:["West","P"]
};
const BYID = new Map(PLAYERS.map(p => [p.id, p]));
const logo = t => `https://assets.nhle.com/logos/nhl/svg/${t}_light.svg`;
const FALLBACK = "data:image/svg+xml," + encodeURIComponent(
  `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><circle cx='50' cy='38' r='20'/><path d='M12 100c2-26 18-38 38-38s36 12 38 38z'/></svg>`);

const $ = id => document.getElementById(id);
const norm = s => s.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
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

// ---- daily puzzle: same player for everyone, switching at midnight Eastern ----
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
const secondsToEtMidnight = () => {
  const o = etParts();
  return Math.max(0, 86400 - (Number(o.hour) * 3600 + Number(o.minute) * 60 + Number(o.second)));
};
function hash(str) { // FNV-1a
  let h = 2166136261;
  for (const c of str) { h ^= c.charCodeAt(0); h = Math.imul(h, 16777619); }
  return h >>> 0;
}
// the schedule is fixed ahead of time; the hash is only a fallback if the site hasn't been rebuilt in a while
const dailyPlayer = key => BYID.get(DAILY[key]) || PLAYERS[hash("sweater-" + key) % PLAYERS.length];
const dailyNumber = key => Math.round((keyUTC(key) - keyUTC(/__START__/.test(START) ? key : START)) / 864e5) + 1;

let mode = store.get("sweater-mode") === "unlimited" ? "unlimited" : "daily";
let target, guesses, over, day, activeIdx = -1, matches = [];

function reset(p) {
  target = p; guesses = []; over = false;
  $("rows").innerHTML = "";
  $("banner").style.display = "none";
  $("guess").disabled = false; $("guess").value = "";
  $("silImg").onerror = function () { this.onerror = null; this.src = FALLBACK; };
  $("silImg").src = target.headshot || FALLBACK;
}

function loadDaily() {
  day = dayKey();
  reset(dailyPlayer(day));
  const saved = store.get("sweater-daily");
  if (saved && saved.date === day && saved.target === target.id) {
    saved.guesses.forEach(id => { const p = BYID.get(id); if (p) play(p, false); });
  }
  updateLabels();
}

function loadUnlimited() {
  let p;
  do { p = PLAYERS[Math.floor(Math.random() * PLAYERS.length)]; }
  while (PLAYERS.length > 1 && target && p.id === target.id);
  reset(p);
  updateLabels();
}

function updateLabels() {
  $("guess").placeholder = over ? (mode === "daily" ? "Done for today. Turn on Unlimited (top right) to keep playing" : "Game over. Click Next player")
                                : `Guess ${guesses.length + 1} of ${MAX}`;
  $("modeLabel").textContent = mode === "daily" ? `Daily #${dailyNumber(dayKey())}` : "Unlimited";
  $("unlimited").checked = mode === "unlimited";
}

function cell(text, hit, cls = "") {
  const td = document.createElement("td");
  td.className = cls + (hit === true ? " hit" : hit === "near" ? " near" : "");
  td.textContent = text;
  return td;
}
const CLOSE = 2; // age / number within this many counts as close (yellow)
const numState = (g, t) => g === t ? true : Math.abs(g - t) <= CLOSE ? "near" : false;
function numCell(g, t) {
  if (g === t) return cell(g, true);
  const td = cell("", numState(g, t));
  td.innerHTML = `<div class="num"><span>${g}</span><span class="arrow" aria-label="${t > g ? "higher" : "lower"}">${t > g ? "↑" : "↓"}</span></div>`;
  return td;
}

function addRow(p) {
  const t = target, tr = document.createElement("tr");
  const [pc, pd] = TEAMS[p.team] || ["?", "?"];
  const [tc, td] = TEAMS[t.team] || ["?", "?"];
  tr.appendChild(cell(p.name, false, "name"));
  const teamState = p.team === t.team ? true : (t.past || []).includes(p.team) ? "near" : false;
  const team = cell("", teamState, "team");
  team.innerHTML = `<img alt="" src="${logo(p.team)}" onerror="this.remove()">${p.team}`;
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

function play(p, save = true) {
  if (over || !p) return;
  guesses.push(p.id);
  addRow(p);
  if (save && mode === "daily") store.set("sweater-daily", { date: day, target: target.id, guesses });
  if (p.id === target.id) end(true, save);
  else if (guesses.length >= MAX) end(false, save);
}

function submit(p) {
  if (over || !p) return;
  play(p);
  closeList(); $("guess").value = "";
  updateLabels();
}

function end(won, fresh = false) {
  over = true;
  $("guess").disabled = true;
  $("reveal").src = target.headshot || FALLBACK;
  $("reveal").alt = target.name;
  const n = guesses.length;
  const CHEERS = ["Top shelf, first try! 🥅", "Snipe! 🎯", "Hat trick! 🎩", "Nice dangle! 🏒",
                  "Five-hole! 🙌", "Solid shift! 💪", "Clutch! ⏱️", "Buzzer beater! 🚨"];
  $("result").textContent = won ? `You got it in ${n}!` : "Out of guesses";
  $("cheer").textContent = won ? CHEERS[n - 1] : "The mystery player was";
  $("pname").textContent = target.name;
  $("pmeta").textContent = `${target.team} · #${target.number} · ${target.pos}`;
  $("banner").classList.toggle("won", won);
  $("banner").classList.remove("pop");
  $("profile").href = `https://www.nhl.com/player/${target.id}`;
  $("again").hidden = mode !== "unlimited";
  $("countdown").hidden = mode !== "daily";
  tick();
  $("banner").style.display = "block";
  if (fresh) {
    void $("banner").offsetWidth; // restart the pop animation
    $("banner").classList.add("pop");
    if (won) confetti();
  }
  if (mode === "daily" && fresh) {
    recordResult(won);
    setTimeout(() => openModal("statsModal"), won ? 2400 : 1400);
  }
}

// ---- confetti ----
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

// ---- stats (daily games only) ----
const blankStats = () => ({ played: 0, wins: 0, streak: 0, maxStreak: 0, dist: Array(MAX).fill(0), lastDay: null, lastWinDay: null, lastGuesses: 0 });
const getStats = () => Object.assign(blankStats(), store.get("sweater-stats") || {});
const prevDayKey = key => shiftKey(key, -1);

function recordResult(won) {
  const st = getStats();
  if (st.lastDay === day) return;
  st.played++;
  if (won) {
    st.wins++;
    st.streak = st.lastWinDay === prevDayKey(day) ? st.streak + 1 : 1;
    st.maxStreak = Math.max(st.maxStreak, st.streak);
    st.dist[guesses.length - 1]++;
    st.lastWinDay = day;
  } else st.streak = 0;
  st.lastDay = day;
  st.lastGuesses = won ? guesses.length : 0;
  store.set("sweater-stats", st);
}

function renderStats() {
  const st = getStats(), today = dayKey();
  const streak = st.lastWinDay === today || st.lastWinDay === prevDayKey(today) ? st.streak : 0;
  $("stPlayed").textContent = st.played;
  $("stWin").textContent = st.played ? Math.round(st.wins / st.played * 100) : 0;
  $("stStreak").textContent = streak;
  $("stMax").textContent = st.maxStreak;
  const most = Math.max(1, ...st.dist);
  $("dist").innerHTML = st.dist.map((n, i) =>
    `<div class="distrow"><span class="k">${i + 1}</span><div class="bar${st.lastDay === today && st.lastGuesses === i + 1 ? " today" : ""}" style="width:0">${n}</div></div>`).join("");
  requestAnimationFrame(() => requestAnimationFrame(() =>
    $("dist").querySelectorAll(".bar").forEach((b, i) => b.style.width = `${Math.max(8, st.dist[i] / most * 100)}%`)));
  const saved = store.get("sweater-daily");
  $("shareBtn").hidden = !(saved && saved.date === today && st.lastDay === today);
}

function shareText() {
  const saved = store.get("sweater-daily");
  const t = dailyPlayer(saved.date);
  const won = saved.guesses.includes(t.id);
  const sq = v => v === true ? "🟩" : v === "near" ? "🟨" : "⬛";
  const lines = saved.guesses.map(id => {
    const p = BYID.get(id); if (!p) return "";
    const [pc, pd] = TEAMS[p.team] || [], [tc, td] = TEAMS[t.team] || [];
    return [
      p.team === t.team ? true : (t.past || []).includes(p.team) ? "near" : false,
      pc === tc, pd === td, p.pos === t.pos, p.shoots === t.shoots,
      numState(ageOf(p.birth), ageOf(t.birth)), p.nation === t.nation, numState(p.number, t.number)
    ].map(sq).join("");
  });
  const link = /__SITE__/.test(SITE) || !SITE ? "" : `\n\n${SITE}`;
  return `Sweater #${dailyNumber(saved.date)} ${won ? saved.guesses.length : "X"}/${MAX}\n\n${lines.join("\n")}${link}`;
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

// ---- modals ----
function closeModals() { document.querySelectorAll(".modal.open").forEach(m => m.classList.remove("open")); }
function openModal(id) {
  closeModals();
  if (id === "statsModal") renderStats();
  $(id).classList.add("open");
}
document.querySelectorAll(".modal").forEach(m => m.addEventListener("click", e => {
  if (m.id === "modal" || e.target === m || e.target.closest("[data-close]")) m.classList.remove("open");
}));
$("statsBtn").onclick = () => openModal("statsModal");
$("helpBtn").onclick = () => openModal("helpModal");

// ---- countdown + midnight rollover ----
function tick() {
  const now = new Date();
  if (mode === "daily" && day !== dayKey(now)) { loadDaily(); return; }
  const s = secondsToEtMidnight();
  const pad = n => String(n).padStart(2, "0");
  const clock = `${pad(Math.floor(s / 3600))}:${pad(Math.floor(s / 60) % 60)}:${pad(s % 60)}`;
  $("countdown").textContent = `New player in ${clock}`;
  $("stNext").textContent = clock;
}
setInterval(tick, 1000);
document.addEventListener("visibilitychange", () => { if (!document.hidden) tick(); });

// ---- mode switch ----
$("unlimited").addEventListener("change", e => {
  mode = e.target.checked ? "unlimited" : "daily";
  store.set("sweater-mode", mode);
  target = null;
  mode === "daily" ? loadDaily() : loadUnlimited();
});
$("again").onclick = loadUnlimited;

// ---- autocomplete ----
function renderList() {
  const q = norm($("guess").value.trim());
  const ul = $("opts");
  if (!q) return closeList();
  matches = PLAYERS.filter(p => !guesses.includes(p.id) && norm(p.name).includes(q)).slice(0, 30);
  ul.innerHTML = "";
  matches.forEach((p, i) => {
    const li = document.createElement("li");
    li.role = "option"; li.id = "opt" + i;
    li.setAttribute("aria-selected", i === activeIdx);
    li.innerHTML = `<span></span><small>${p.team} · ${p.pos}</small>`;
    li.firstChild.textContent = p.name;
    li.onmousedown = e => { e.preventDefault(); submit(p); };
    ul.appendChild(li);
  });
  ul.hidden = matches.length === 0;
  $("guess").setAttribute("aria-expanded", !ul.hidden);
}
function closeList() { $("opts").hidden = true; activeIdx = -1; $("guess").setAttribute("aria-expanded", false); }

$("guess").addEventListener("input", () => { activeIdx = 0; renderList(); });
$("guess").addEventListener("keydown", e => {
  if ($("opts").hidden) return;
  if (e.key === "ArrowDown") { activeIdx = Math.min(activeIdx + 1, matches.length - 1); renderList(); e.preventDefault(); }
  else if (e.key === "ArrowUp") { activeIdx = Math.max(activeIdx - 1, 0); renderList(); e.preventDefault(); }
  else if (e.key === "Enter") { submit(matches[activeIdx]); e.preventDefault(); }
  else if (e.key === "Escape") closeList();
  const a = $("opt" + activeIdx); if (a) a.scrollIntoView({ block: "nearest" });
});
$("guess").addEventListener("blur", closeList);

// ---- silhouette modal ----
$("silBtn").onclick = () => openModal("modal");

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

$("foot").textContent = `Player data from NHL.com · updated ${BUILT} · ${PLAYERS.length} players`;
if (!store.get("sweater-seen-help")) { store.set("sweater-seen-help", true); openModal("helpModal"); }

if (PLAYERS.length) {
  if (mode === "daily") loadDaily(); else loadUnlimited();
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
    ("Winnipeg Jets", "WPG"),
]
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


def update_schedule(players, today):
    """Keep a fixed day-by-day list of mystery players. Past days and tomorrow never change."""
    try:
        sched = json.loads(SCHEDULE.read_text(encoding="utf-8"))
    except Exception:
        sched = {}
    days = sched.get("days", {})
    archive = {int(k): v for k, v in sched.get("players", {}).items()}
    start = sched.get("start") or today.isoformat()
    pool = {p["id"]: p for p in players}
    lock = (today + timedelta(days=LOCK_DAYS)).isoformat()

    # future picks (after tomorrow) are re-drawn if that player dropped out of the pool
    for k in list(days):
        if k > lock and days[k] not in pool:
            del days[k]

    for i in range(AHEAD + 1):
        k = (today + timedelta(days=i)).isoformat()
        if k in days:
            continue
        recent = {v for d, v in days.items()
                  if abs((date.fromisoformat(d) - date.fromisoformat(k)).days) <= NO_REPEAT_DAYS}
        choices = [pid for pid in sorted(pool) if pid not in recent] or sorted(pool)
        days[k] = random.Random(f"sweater-{k}").choice(choices)

    # remember details of every scheduled player, so a past answer still works after he leaves the league
    for pid in set(days.values()):
        if pid in pool:
            archive[pid] = pool[pid]
    sched = {"start": start, "days": dict(sorted(days.items())),
             "players": {str(k): v for k, v in sorted(archive.items())}}
    SCHEDULE.write_text(json.dumps(sched, ensure_ascii=False, indent=1), encoding="utf-8")

    first = (today - timedelta(days=1)).isoformat()
    last = (today + timedelta(days=EMBED_AHEAD)).isoformat()
    window = {k: v for k, v in sched["days"].items() if first <= k <= last}
    extras = [archive[pid] for pid in set(window.values()) if pid not in pool and pid in archive]
    return start, window, extras


def abbrev_for(name):
    for nick, ab in NICKNAMES:
        if nick.lower() in name.lower():
            return ab
    return None


def career_teams(pid):
    """Every NHL team a player has appeared for."""
    data = get_json(f"https://api-web.nhle.com/v1/player/{pid}/landing")
    teams = []
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
    return teams


def add_career_teams(players):
    try:
        cache = json.loads(CACHE.read_text(encoding="utf-8"))
    except Exception:
        cache = {}
    today = date.today()

    def fresh(pid):
        c = cache.get(str(pid))
        return bool(c) and (today - date.fromisoformat(c["day"])).days < CACHE_DAYS

    todo = [p["id"] for p in players if not fresh(p["id"])]
    print(f"\nLoading career history ({len(players) - len(todo)} saved, {len(todo)} to download)...")

    def job(pid):
        try:
            return pid, career_teams(pid)
        except Exception:
            return pid, None

    failed = 0
    with ThreadPoolExecutor(max_workers=6) as pool:
        for i, (pid, teams) in enumerate(pool.map(job, todo), 1):
            if teams is None:
                failed += 1
            else:
                cache[str(pid)] = {"day": today.isoformat(), "teams": teams}
            if i % 50 == 0 or i == len(todo):
                print(f"  {i}/{len(todo)}")
    if failed:
        print(f"  {failed} players' history couldn't be loaded (their team won't show yellow).")
    try:
        CACHE.write_text(json.dumps(cache), encoding="utf-8")
    except Exception:
        pass

    for p in players:
        teams = (cache.get(str(p["id"])) or {}).get("teams", [])
        p["past"] = [t for t in teams if t != p["team"]]


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
    start, window, extras = update_schedule(players, today)
    embedded = players + extras
    print(f"\nDaily schedule: {len(window)} days in this page, starting from Daily #1 on {start}.")

    site = args.site_url.strip()
    if site and not site.endswith("/"):
        site += "/"
    esc = lambda obj: json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")
    html = (TEMPLATE.replace("/*__PLAYERS__*/[]", esc(embedded))
                    .replace("/*__DAILY__*/{}", esc(window))
                    .replace("/*__START__*/", start)
                    .replace("/*__SITE__*/", site)
                    .replace("/*__BUILT__*/", f"{today.isoformat()} · builder v{VERSION}"))
    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    og = HERE / "og-image.png"
    if og.exists() and out.parent != HERE:
        shutil.copy(og, out.parent / "og-image.png")
    # double-check the page that was written
    check = out.read_text(encoding="utf-8")
    if "/*__PLAYERS__*/" in check or "/*__DAILY__*/" in check or check.count('"headshot"') != len(embedded):
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
