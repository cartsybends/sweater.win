// Team mini-games share a five-question run, but keep their answer models separate.
const TEAM_GAME_MODEL = (() => {
  const group = pos => pos === "G" ? "G" : pos === "D" ? "D" : "F";
  function identityPlayers(h) {
    const players = new Map([...h.byPlayer].map(([id, p]) => [id, {...p, rows: p.rows.slice()}]));
    for (const row of h.goalies) {
      if (!players.has(row.id)) players.set(row.id, {id: row.id, name: row.name, pos: "G", rows: []});
      players.get(row.id).rows.push(row);
    }
    return [...players.values()].map(p => {
      const rows = p.rows.slice().sort((a, b) => a.y - b.y), gp = rows.reduce((n, r) => n + r.gp, 0);
      const peak = rows.reduce((best, r) => (p.pos === "G" ? r.wins : r.points) > (p.pos === "G" ? best.wins : best.points) ? r : best);
      return {...p, rows, gp, first: rows[0].y, last: rows.at(-1).y, peak};
    }).filter(p => p.gp >= 30 && p.name && p.pos !== "?");
  }
  function pool(players, mode, level, team) {
    if (mode === "identity") {
      const ranked = players.slice().sort((a, b) => b.gp - a.gp || b.last - a.last);
      return level === "challenge" ? ranked : ranked.slice(0, 48);
    }
    return players.filter(p => p.stints.length >= (level === "challenge" ? 6 : 3) &&
      p.stints.length <= (level === "challenge" ? 10 : 5) && p.stints.some(s => s.team === team && s.gp >= 20))
      .sort((a, b) => b.stints.filter(s => s.team === team).reduce((n, s) => n + s.gp, 0) -
        a.stints.filter(s => s.team === team).reduce((n, s) => n + s.gp, 0));
  }
  function identityRound(player, players, shuffle) {
    // Some alumni share a name (including both Elias Petterssons in VAN).
    // Each visible answer must identify one choice unambiguously.
    const byName = new Map(), targetName = player.name.trim().toLowerCase();
    for (const p of players) {
      const name = p.name.trim().toLowerCase();
      if (p.id !== player.id && name !== targetName && !byName.has(name)) byName.set(name, p);
    }
    const others = [...byName.values()];
    const similar = others.filter(p => group(p.pos) === group(player.pos) && p.first <= player.last + 5 && p.last >= player.first - 5);
    const ordered = [...shuffle(similar), ...shuffle(others.filter(p => !similar.includes(p)))];
    return {player, choices: shuffle([player, ...ordered.slice(0, 3)]), clue: 1, wrong: new Set(), over: false, won: false, points: 0};
  }
  function answerIdentity(round, id) {
    if (round.over || round.wrong.has(id) || !round.choices.some(p => p.id === id)) return null;
    const correct = id === round.player.id;
    if (correct) {
      round.over = round.won = true;
      round.points = [10, 6, 3][round.clue - 1];
    } else {
      round.wrong.add(id);
      round.clue = Math.min(3, round.clue + 1);
      if (round.wrong.size === 3) round.over = true;
    }
    return correct;
  }
  function journeyRound(player, shuffle) {
    let order = shuffle(player.stints.map((_, i) => i));
    const solved = () => order.every((tile, i) => player.stints[tile].team === player.stints[i].team);
    // Identical return-visit tiles are interchangeable; never start solved.
    if (solved()) {
      const different = order.findIndex(tile => player.stints[tile].team !== player.stints[order[0]].team);
      if (different >= 0) [order[0], order[different]] = [order[different], order[0]];
    }
    return {player, order, locked: new Set(), checks: 0, hinted: false, over: false, won: false, points: 0};
  }
  function swapJourney(round, from, to) {
    if (round.over || !Number.isInteger(from) || !Number.isInteger(to) || from < 0 || to < 0 ||
      from >= round.order.length || to >= round.order.length || from === to || round.locked.has(from) || round.locked.has(to)) return false;
    [round.order[from], round.order[to]] = [round.order[to], round.order[from]];
    return true;
  }
  function hintJourney(round) {
    if (round.over || round.hinted || round.locked.has(0)) return false;
    const index = round.order.findIndex((tile, i) => !round.locked.has(i) && round.player.stints[tile].team === round.player.stints[0].team);
    if (index < 0) return false;
    if (index !== 0) swapJourney(round, 0, index);
    round.locked.add(0); round.hinted = true;
    return true;
  }
  function checkJourney(round) {
    if (round.over) return null;
    round.checks++;
    round.order.forEach((tile, i) => {if (round.player.stints[tile].team === round.player.stints[i].team) round.locked.add(i);});
    round.won = round.locked.size === round.order.length;
    round.over = round.won || round.checks === 3;
    if (round.won) round.points = Math.min([10, 6, 3][round.checks - 1], round.hinted ? 6 : 10);
    return round.won;
  }
  return {identityPlayers, pool, identityRound, answerIdentity, journeyRound, swapJourney, hintJourney, checkJourney};
})();

function journeyTeamName(team) {
  return team === "ARI" ? "Phoenix / Arizona Coyotes" : team === "WIN" ? "Winnipeg Jets (1979–96)" : teamFullName(team);
}
function teamMiniPortrait(player, team) {
  return player.headshot || teamHistHeadshot(team, player.id, player.last ?? player.stints.at(-1).to);
}
function teamMiniImage(src, className = "") {
  return `<img class="${className}" src="${esc(src)}" alt="" decoding="async" onerror="this.onerror=null;this.src=FALLBACK">`;
}

let teamMiniCleanup = () => {};
function startTeamMiniGame(team, mode) {
  teamMiniCleanup();
  const h = historyForTeam(team), model = TEAM_GAME_MODEL;
  const players = mode === "identity" ? model.identityPlayers(h) : TEAM_CAREERS;
  const preference = `sweater-team-${mode}-difficulty`;
  const challenge = model.pool(players, mode, "challenge", team);
  let level = store.get(preference) === "challenge" && challenge.length >= 5 ? "challenge" : "classic";
  const classic = model.pool(players, mode, "classic", team);
  if (classic.length < 5 && level === "classic") return teamModeNoData(team, mode);
  const eligible = level === "challenge" ? challenge : mode === "journey" ? classic.slice(0, 40) : classic;
  const run = shuffled(eligible).slice(0, 5), results = [], total = run.length;
  let index = 0, round, selected = -1, analyticsMoves = 0, dragCleanup = () => {}, active = true, ignoreJourneyClicksUntil = 0, touchClickUntil = 0;
  teamMiniCleanup = () => {active = false; dragCleanup();};
  const token = globalThis.SweaterAnalytics?.context(`team_${mode}`, "unlimited", `${team}:${mode}`, true);
  teamModeShell(team, mode, `<div class="team-mini" data-team-game="${mode}">
    <div class="team-mini-settings"><p>${mode === "identity" ? "Five players. Follow the clues and choose a name." : "Five careers. Arrange the NHL teams from earliest to latest."}</p>
      <label>Difficulty<select id="teamMiniDifficulty"><option value="classic">Classic</option><option value="challenge"${challenge.length < 5 ? " disabled" : ""}>Challenge</option></select></label></div>
    <div class="team-mini-line"><span id="teamMiniQuestion"></span><span id="teamMiniScore"></span></div>
    <div class="shdots question-progress" id="teamMiniDots"></div><div id="teamMiniRound"></div></div>`);
  $("teamMiniDifficulty").value = level;
  $("teamMiniDifficulty").onchange = e => {dragCleanup(); store.set(preference, e.target.value); startTeamMiniGame(team, mode);};

  function progress() {
    $("teamMiniQuestion").textContent = index < total ? `Question ${index + 1} / ${total}` : "Run complete";
    $("teamMiniScore").textContent = `${results.reduce((n, r) => n + r.points, 0)} / ${total * 10} points`;
    paintQuestionProgress("teamMiniDots", total, index < total ? index : -1, results.map(r => ({status: r.won ? "ok" : "bad", mark: r.won ? "check" : "x"})));
  }
  function step(correct) {globalThis.SweaterAnalytics?.step?.(++analyticsMoves, correct, token);}
  function settled() {
    if (!round.over || results.length > index) return;
    results.push({won: round.won, points: round.points}); progress();
    if (results.length === total) globalThis.SweaterAnalytics?.completeRound(null, {token, attempts: analyticsMoves, score: results.reduce((n, r) => n + r.points, 0)});
  }
  function next() {
    dragCleanup(); index++; selected = -1; renderRound();
    $("teamMiniRound").focus({preventScroll: true});
    // A mobile player answers near the bottom of a tall question. Bring the
    // next question's progress and clues into view rather than leaving them
    // looking at another set of choices with the clues above the screen.
    $("teamMiniQuestion").scrollIntoView({block: "start", behavior: "auto"});
  }
  function footer(message, detail, actions) {
    return `<div class="team-mini-feedback" role="status"><b>${esc(message)}</b><span>${esc(detail)}</span></div><div class="team-mini-actions">${actions}</div>`;
  }
  function finish() {
    progress();
    const score = results.reduce((n, r) => n + r.points, 0), right = results.filter(r => r.won).length;
    $("teamMiniRound").innerHTML = `<div class="team-mini-summary"><span>Your score</span><strong>${score}<small> / ${total * 10}</small></strong><p>${right} of ${total} ${mode === "identity" ? "players identified" : "journeys solved"}</p>
      <button type="button" class="btn" id="teamMiniAgain">Play again</button></div>`;
    $("teamMiniAgain").onclick = () => startTeamMiniGame(team, mode);
  }
  function renderRound() {
    if (index >= total) return finish();
    round = mode === "identity" ? model.identityRound(run[index], players, shuffled) : model.journeyRound(run[index], shuffled);
    selected = -1; progress(); draw();
  }
  function drawIdentity() {
    const p = round.player, peak = p.peak, revealed = round.over || round.clue === 3;
    const position = p.pos === "G" ? "Goalie" : p.pos === "D" ? "Defenceman" : p.pos === "C" ? "Centre" : p.pos === "L" ? "Left winger" : "Right winger";
    const facts = `${position} · ${seasonText(p.first)}${p.first === p.last ? "" : ` to ${seasonText(p.last)}`}`;
    const peakText = p.pos === "G" ? `${peak.wins} wins in ${seasonText(peak.y)}` : `${peak.points} points (${peak.goals} goals, ${peak.assists} assists) in ${seasonText(peak.y)}`;
    const clues = [
      ["The sweater", facts, `Played ${p.gp.toLocaleString()} regular-season games for ${teamFullName(team)}.`],
      [p.pos === "G" ? "Most wins in a season" : "Highest-scoring season", peakText, "With this team · regular season"],
      ["The face", "Recognize this player?", "One final clue"],
    ];
    $("teamMiniRound").innerHTML = `<div class="team-identity-heading"><div class="team-mini-avatar">${revealed ? teamMiniImage(teamMiniPortrait(p, team)) : '<span aria-hidden="true">?</span>'}</div><div><p class="team-mini-eyebrow">${round.over ? "Answer revealed" : `Clue ${round.clue} / 3`}</p><h4>${round.over ? esc(p.name) : "Who wore this sweater?"}</h4><p>${round.over ? esc(teamFullName(team)) : `${[10, 6, 3][round.clue - 1]} points available`}</p></div></div>
      <ol class="team-clues">${clues.map(([title, fact, note], i) => `<li${i >= round.clue && !round.over ? ' class="is-locked"' : ""}><span class="team-clue-number">${i + 1}</span><div><small>${esc(title)}</small><b>${i < round.clue || round.over ? esc(fact) : "Reveal the next clue"}</b>${i < round.clue || round.over ? `<span>${esc(note)}</span>` : ""}</div></li>`).join("")}</ol>
      <div class="team-identity-choices">${round.choices.map(choice => `<button type="button" data-identity-choice="${choice.id}" class="team-identity-choice${round.over && choice.id === p.id ? " is-right" : round.wrong.has(choice.id) ? " is-wrong" : ""}"${round.over || round.wrong.has(choice.id) ? " disabled" : ""}>${esc(choice.name)}${round.over && choice.id === p.id ? '<span aria-label="correct answer">✓</span>' : round.wrong.has(choice.id) ? '<span aria-label="incorrect">×</span>' : ""}</button>`).join("")}</div>` +
      footer(round.over ? round.won ? "Correct" : `It was ${p.name}` : round.wrong.size ? "Another clue unlocked" : "Choose a name when you're ready", round.over ? round.won ? `+${round.points} points` : "The full clues are shown above." : "Earlier answers earn more points.", round.over ? `<button type="button" class="btn" id="teamMiniNext">${index === total - 1 ? "See results" : "Next player"}</button>` : `<button type="button" class="btn ghost" id="teamIdentityClue"${round.clue === 3 ? " disabled" : ""}>Reveal next clue</button><button type="button" class="btn ghost" id="teamMiniReveal">Reveal answer</button>`);
    $("teamMiniRound").querySelectorAll("[data-identity-choice]").forEach(button => button.onclick = () => {
      if (!active) return;
      const correct = model.answerIdentity(round, Number(button.dataset.identityChoice));
      if (correct === null) return;
      step(correct); settled(); draw();
    });
    if (!round.over) $("teamIdentityClue").onclick = () => {if (round.clue >= 3) return; round.clue++; step(); draw();};
  }
  function drawJourney() {
    const p = round.player, order = round.over ? p.stints.map((_, i) => i) : round.order;
    const dates = stint => stint.from === stint.to ? seasonText(stint.from) : `${seasonText(stint.from)} to ${seasonText(stint.to)}`;
    $("teamMiniRound").innerHTML = `<div class="team-journey-player">${teamMiniImage(teamMiniPortrait(p, team))}<div><p class="team-mini-eyebrow">${p.stints.length} career stops</p><h4>${esc(p.name)}</h4><p>NHL regular season · return visits count separately</p></div></div>
      <div class="team-journey-direction"><span>1 · Earliest</span><span>Latest · ${p.stints.length}</span></div>
      <div class="team-journey-board" id="teamJourneyBoard" style="--stops:${Math.min(5, order.length)}" aria-label="Career teams, earliest to latest">${order.map((tile, i) => {
        const stint = p.stints[tile], locked = !round.over && round.locked.has(i);
        return `<button type="button" class="team-journey-tile${locked || round.over && round.won ? " is-fixed" : ""}${selected === i ? " is-selected" : ""}" data-journey-slot="${i}" aria-pressed="${selected === i}" aria-label="Stop ${i + 1}: ${esc(journeyTeamName(stint.team))}${locked ? ", correct and locked" : ""}"${round.over || locked ? " disabled" : ""}><span class="team-journey-number">${i + 1}${locked ? " ✓" : ""}</span><img src="${logo(stint.team)}" alt="" draggable="false" onerror="this.style.visibility='hidden'"><span class="team-journey-copy"><b>${esc(journeyTeamName(stint.team))}</b>${round.over ? `<small>${dates(stint)} · ${stint.gp.toLocaleString()} GP</small>` : ""}</span><span class="team-journey-grip" aria-hidden="true">⠿</span></button>`;
      }).join("")}</div><p class="team-journey-instructions">${round.over ? `NHL career as of ${p.verified}` : "Drag a grip, or tap two teams to swap. Keyboard: use the arrow keys on a tile."}</p>` +
      footer(round.over ? round.won ? "Journey complete" : "Here's the full journey" : round.checks ? `${round.locked.size} of ${p.stints.length} stops in place` : "Put the teams in career order", round.over ? round.won ? `+${round.points} points` : "Keep these stops in mind for next time." : `${3 - round.checks} checks left · ${Math.min([10, 6, 3][round.checks], round.hinted ? 6 : 10)} pts${round.hinted ? " · hint used" : " · hint: max 6 pts"}${round.locked.size ? " · correct stops are locked" : ""}`, round.over ? `<button type="button" class="btn" id="teamMiniNext">${index === total - 1 ? "See results" : "Next player"}</button>` : `<button type="button" class="btn" id="teamJourneyCheck">Check order</button><button type="button" class="btn ghost" id="teamJourneyHint"${round.hinted || round.locked.has(0) ? " disabled" : ""}>First-team hint</button><button type="button" class="btn ghost" id="teamMiniReveal">Reveal journey</button>`);
    if (round.over) return;
    $("teamJourneyCheck").onclick = () => {const won = model.checkJourney(round); if (won === null) return; selected = -1; step(won); settled(); draw();};
    $("teamJourneyHint").onclick = () => {if (!model.hintJourney(round)) return; selected = -1; step(); draw();};
    bindJourneyBoard();
  }
  function bindJourneyBoard() {
    const board = $("teamJourneyBoard");
    let dragged = -1, target = -1, pointer = null, startX = 0, startY = 0, ghost = null;
    const tiles = [...board.querySelectorAll("[data-journey-slot]")];
    const announce = text => {const status = $("teamMiniRound").querySelector(".team-mini-feedback b"); status.textContent = text;};
    function cancel() {
      ghost?.remove(); ghost = null; tiles.forEach(tile => tile.classList.remove("is-dragging", "is-drop-target"));
      if (pointer !== null && tiles[dragged]?.hasPointerCapture(pointer)) tiles[dragged].releasePointerCapture(pointer);
      pointer = null; dragged = target = -1;
    }
    dragCleanup = cancel;
    function swap(from, to, focus = false, defer = false) {
      if (!model.swapJourney(round, from, to)) return;
      selected = -1;
      const update = () => {
        if (!active || !board.isConnected) return;
        draw();
        if (focus) $("teamJourneyBoard").querySelector(`[data-journey-slot="${to}"]`)?.focus({preventScroll: true});
        announce("Teams swapped. Check the order when you're ready.");
      };
      // Keep the captured tile alive until the pointer-up dispatch finishes.
      // Removing it during dispatch can swallow the next mobile tap.
      if (defer) requestAnimationFrame(update); else update();
    }
    tiles.forEach(tile => {
      const slot = Number(tile.dataset.journeySlot);
      let touchStart = null;
      const choose = (defer = false) => {
        if (Date.now() < ignoreJourneyClicksUntil || !active || round.over || round.locked.has(slot)) return;
        if (selected === slot) {selected = -1; tile.classList.remove("is-selected"); tile.setAttribute("aria-pressed", "false"); announce("Selection cleared."); return;}
        if (selected >= 0) {swap(selected, slot, false, defer); return;}
        selected = slot; tile.classList.add("is-selected"); tile.setAttribute("aria-pressed", "true");
        announce(`${journeyTeamName(round.player.stints[round.order[slot]].team)} selected. Choose another team to swap.`);
      };
      tile.onclick = e => {
        // Touch is handled at pointer-up, including browsers that suppress a
        // compatibility click after a drag. Keyboard and mouse use click.
        if (e.pointerType === "touch" || e.sourceCapabilities?.firesTouchEvents ||
          e.detail > 0 && Date.now() < touchClickUntil) return;
        choose();
      };
      tile.onkeydown = e => {
        const direction = ["ArrowRight", "ArrowDown"].includes(e.key) ? 1 : ["ArrowLeft", "ArrowUp"].includes(e.key) ? -1 : 0;
        if (!direction || round.over || round.locked.has(slot)) return;
        e.preventDefault(); e.stopPropagation();
        let next = slot + direction;
        while (next >= 0 && next < round.order.length && round.locked.has(next)) next += direction;
        if (next >= 0 && next < round.order.length) swap(slot, next, true);
      };
      tile.onpointerdown = e => {
        if (!active || round.over || round.locked.has(slot) || e.button !== 0 || !e.isPrimary || pointer !== null) return;
        if (e.pointerType === "mouse") touchClickUntil = 0;
        if (e.pointerType === "touch") {
          touchStart = {id: e.pointerId, x: e.clientX, y: e.clientY};
          touchClickUntil = Date.now() + 700;
        }
        if (e.pointerType !== "mouse" && !e.target.closest(".team-journey-grip")) return;
        dragged = target = slot; pointer = e.pointerId; startX = e.clientX; startY = e.clientY;
        tile.setPointerCapture(pointer);
      };
      tile.onpointerup = e => {
        if (touchStart?.id !== e.pointerId) return;
        touchClickUntil = Date.now() + 700;
        if (!ghost && Math.hypot(e.clientX - touchStart.x, e.clientY - touchStart.y) < 7) choose(true);
        touchStart = null;
      };
      tile.onpointercancel = () => {touchStart = null;};
    });
    board.onpointermove = e => {
      if (e.pointerId !== pointer || !board.isConnected) return;
      if (!ghost && Math.hypot(e.clientX - startX, e.clientY - startY) < 7) return;
      if (!ghost) {
        ghost = tiles[dragged].cloneNode(true); ghost.classList.add("team-journey-ghost"); ghost.setAttribute("aria-hidden", "true");
        ghost.style.width = `${tiles[dragged].getBoundingClientRect().width}px`;
        ghost.style.height = `${tiles[dragged].getBoundingClientRect().height}px`;
        document.body.appendChild(ghost); tiles[dragged].classList.add("is-dragging");
      }
      ghost.style.left = `${e.clientX - ghost.offsetWidth / 2}px`; ghost.style.top = `${e.clientY - ghost.offsetHeight / 2}px`;
      const hit = document.elementFromPoint(e.clientX, e.clientY)?.closest("[data-journey-slot]");
      target = hit && board.contains(hit) && !round.locked.has(Number(hit.dataset.journeySlot)) ? Number(hit.dataset.journeySlot) : -1;
      tiles.forEach((tile, i) => tile.classList.toggle("is-drop-target", i === target && i !== dragged));
    };
    board.onpointerup = e => {
      if (e.pointerId !== pointer) return;
      const from = dragged, to = target, moved = !!ghost;
      if (moved) ignoreJourneyClicksUntil = Date.now() + 100;
      cancel();
      if (moved && to >= 0) swap(from, to, false, true);
    };
    board.onpointercancel = board.onlostpointercapture = cancel;
  }
  function draw() {
    if (!active) return;
    dragCleanup(); dragCleanup = () => {};
    mode === "identity" ? drawIdentity() : drawJourney();
    $("teamMiniRound").tabIndex = -1;
    if (round.over) $("teamMiniNext").onclick = next;
    else $("teamMiniReveal").onclick = () => {if (round.over) return; round.over = true; selected = -1; step(false); settled(); draw();};
  }
  renderRound();
}
function startTeamIdentity(team) {startTeamMiniGame(team, "identity");}
function startTeamJourney(team) {startTeamMiniGame(team, "journey");}
