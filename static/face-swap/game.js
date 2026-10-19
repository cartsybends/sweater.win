const FACE_SWAP_PUZZLES = /*__FACE_SWAP_PUZZLES__*/[];
const FS_POOL = FACE_SWAP_PUZZLES.filter(t => t.players.every(id => BYID.has(id)));
const fsState = (t, guesses) => FACE_SWAP_MODEL.progress(t, guesses);
function fsAge(birth, day) {
  const age = Number(day.slice(0, 4)) - Number(birth.slice(0, 4)) - (day.slice(5) < birth.slice(5) ? 1 : 0);
  return Number.isFinite(age) ? age : null;
}
function fsRandom() {
  const key = 'sweater-faceswap-rotation-v1', saved = store.get(key);
  const ids = FS_POOL.map(t => t.id), last = saved?.last || S.faceswap.target?.id;
  let remaining = Array.isArray(saved?.remaining) ? [...new Set(saved.remaining.filter(id => ids.includes(id)))] : [];
  if (!remaining.length) remaining = shuffled(ids);
  if (remaining.length > 1 && remaining[0] === last) [remaining[0], remaining[1]] = [remaining[1], remaining[0]];
  const next = remaining.shift();
  store.set(key, { remaining, last: next });
  return FS_POOL.find(t => t.id === next);
}
function fsIdentity(t, id, index, state, over) {
  const p = t.people.find(p => p.id === id), found = state.found.includes(id), revealed = found || over;
  const age = fsAge(p.birth, t.asOf), hints = [];
  if (state.wrong >= 1) hints.push(['Position', posName(p)]);
  if (state.wrong >= 2 && age !== null) hints.push(['Age', `${age} years`]);
  if (state.wrong >= 3) hints.push(['Country', countryName(p.nation)]);
  if (state.wrong >= 4) hints.push(['Team', teamName(p.team), p.team]);
  return `<article class="fs-identity${found ? ' found' : ''}">
    <div class="fs-identity-label"><span>Player ${index + 1}</span>${revealed ? `<em>${found ? '✓ Identified' : 'Revealed'}</em>` : ''}</div>
    <div class="fs-person">${revealed
      ? `<img src="face-swap/players/${id}.webp" alt="${esc(p.name)}" onerror="this.onerror=null;this.src=FALLBACK">`
      : '<span class="fs-unknown" aria-hidden="true">?</span>'}
      <div><b>${revealed ? esc(p.name) : 'Who is it?'}</b><small>${revealed
        ? `${esc(posName(p))} · ${esc(teamName(p.team))}${age !== null ? ` · ${age}` : ''}`
        : state.wrong ? 'Use the clues below.' : 'Position revealed after a miss.'}</small>${revealed ? `<a href="https://www.nhl.com/player/${id}" target="_blank" rel="noopener">NHL profile ↗</a>` : ''}</div>
    </div>${!revealed && hints.length ? `<ul class="fs-clues">${hints.map(([label, value, team]) => `<li>${team ? `<img src="${logo(team)}" alt="" onerror="this.remove()">` : ''}<small>${label}</small><b>${esc(value)}</b></li>`).join('')}</ul>` : ''}
  </article>`;
}
G.faceswap = {
  title: 'Face Swap', share: 'Sweater Face Swap', view: 'view-faceswap', max: FACE_SWAP_MODEL.max,
  next: 'Next face', hideReveal: true, quietFinish: true, persistUnlimited: true, orderedRotation: true,
  pool: () => FS_POOL,
  daily(k) {
    const id = DAILY.faceswap[k]?.id;
    return FS_POOL.find(t => t.id === id) || FS_POOL[hash(`sweater-faceswap-${k}`) % FS_POOL.length];
  },
  random: fsRandom, tid: t => t.id, player: () => null, meta: () => '',
  prepareTarget(t, opts) {
    const saved = opts.faceSwapPeople;
    const valid = Array.isArray(saved) && saved.length === 2 && saved.every((p, i) =>
      p?.id === t.players[i] && typeof p.name === 'string' && typeof p.birth === 'string' && typeof p.team === 'string' && typeof p.pos === 'string' && typeof p.nation === 'string');
    const people = valid ? saved : t.players.map(id => {
      const p = BYID.get(id);
      return { id, name: p.name, birth: p.birth, team: p.team, pos: p.pos, nation: p.nation };
    });
    opts.faceSwapPeople = people;
    return { ...t, people, asOf: mode === 'unlimited' ? dayKey() : S.faceswap.day };
  },
  loadPhoto(t) {
    this.ready = false; this.failed = false;
    const image = $('fsImage');
    const settle = failed => {
      if (S.faceswap.target?.id !== t.id) return;
      this.ready = !failed; this.failed = failed;
      this.render(S.faceswap.target, S.faceswap);
      if (game === 'faceswap') updateLabels();
    };
    image.onload = () => settle(false);
    image.onerror = () => settle(true);
    image.src = `face-swap/${t.image}`;
    if (image.complete && image.naturalWidth > 0) settle(false);
  },
  reset(t) { $('fsGuess').value = ''; $('fsGuesses').innerHTML = ''; this.loadPhoto(t); },
  guess(t, id, fresh) {
    if (fresh && !this.ready) { toast('Wait for the portrait to load.'); return null; }
    if (!BYID.has(id)) return null;
    try { return fsState(t, [...S.faceswap.guesses, id]).won; }
    catch (error) { if (fresh) toast(error.message); return null; }
  },
  right: (t, id) => t.players.includes(id),
  isWin: () => false,
  isDone: (t, guesses) => fsState(t, guesses).over,
  wonGame: (t, guesses) => fsState(t, guesses).won,
  score: (t, guesses) => fsState(t, guesses).points,
  endText(t, guesses) {
    const state = fsState(t, guesses);
    return { result: state.won ? 'Both players found!' : `${state.found.length} of 2 players found`,
      cheer: `${state.points}/10 points · ${state.wrong} ${state.wrong === 1 ? 'miss' : 'misses'}${state.won ? '' : ' · Source players revealed'}` };
  },
  shareText(t, saved, number, link) {
    const state = fsState(t, saved.guesses), marks = saved.guesses.map(id => t.players.includes(id) ? '🟩' : '⬛').join('');
    return `${this.share} #${number}\n${state.found.length}/2 players · ${state.wrong}/5 misses · ${state.points}/10 points\n\n${marks}${link}`;
  },
  render(t, st) {
    const state = fsState(t, st.guesses), last = st.guesses.at(-1), hit = t.players.includes(last);
    $('fsPhoto').dataset.state = this.failed ? 'error' : this.ready ? 'ready' : 'loading';
    $('fsPhotoMessage').hidden = this.ready;
    $('fsPhotoStatus').textContent = this.failed ? "The photo couldn't load. Retry to keep playing." : 'Loading face…';
    $('fsRetry').hidden = !this.failed;
    $('fsProgress').textContent = `${state.found.length} / 2 identified`;
    $('fsPoints').textContent = st.over ? `${state.points} / 10 points` : `${state.available} points available`;
    $('fsMisses').innerHTML = Array.from({ length: FACE_SWAP_MODEL.misses }, (_, i) => `<i${i < state.wrong ? ' class="used"' : ''}></i>`).join('');
    $('fsMisses').setAttribute('aria-label', `${state.wrong} of 5 misses used`);
    $('fsIdentities').innerHTML = t.players.map((id, i) => fsIdentity(t, id, i, state, st.over)).join('');
    $('fsGuessing').hidden = st.over;
    $('fsFeedback').classList.toggle('hit', hit);
    const clue = ['position', 'age', 'country', 'team'][state.wrong - 1];
    $('fsFeedback').textContent = !last ? 'Guess either player. Correct names lock in.' : hit
      ? `${BYID.get(last).name} is one of the players. Find the other player.`
      : `No match.${clue ? ` ${clue[0].toUpperCase() + clue.slice(1)} clues unlocked.` : ''}`;
    $('fsRemaining').textContent = `${state.left} wrong ${state.left === 1 ? 'guess' : 'guesses'} left · Correct names don't use a miss.`;
    $('fsHistory').hidden = st.guesses.length === 0;
    $('fsGuesses').innerHTML = st.guesses.map((id, i) => {
      const correct = t.players.includes(id);
      return `<li class="${correct ? 'hit' : 'miss'}"><span class="fs-guess-index">${String(i + 1).padStart(2, '0')}</span><span class="fs-guess-name">${esc(BYID.get(id)?.name || 'Unknown player')}</span><span class="fs-guess-mark">${correct ? '✓ Identified' : 'Miss'}</span></li>`;
    }).reverse().join('');
  }
};
$('fsRetry').onclick = () => { if (game === 'faceswap' && S.faceswap.target) { G.faceswap.loadPhoto(S.faceswap.target); G.faceswap.render(S.faceswap.target, S.faceswap); updateLabels(); } };
