// Shared by the browser and leaderboard: five misses, two identities, either order.
export const FACE_SWAP_MODEL = Object.freeze({
  misses: 5,
  max: 6,
  progress(puzzle, guesses) {
    const answers = puzzle?.players;
    if (!Array.isArray(answers) || answers.length !== 2 || new Set(answers).size !== 2 ||
        answers.some(id => !Number.isInteger(id) || id < 1000000 || id > 9999999)) {
      throw new Error('Face Swap puzzle is missing its two players.');
    }
    if (!Array.isArray(guesses) || guesses.length > this.max) throw new Error('Invalid guesses.');
    const used = new Set(), found = [];
    let wrong = 0;
    for (const id of guesses) {
      if (wrong >= this.misses || found.length === 2) throw new Error('That round is already finished.');
      if (!Number.isInteger(id) || id < 1000000 || id > 9999999) throw new Error('Choose a player from the search results.');
      if (used.has(id)) throw new Error('You already guessed that player.');
      used.add(id);
      if (answers.includes(id)) found.push(id);
      else wrong++;
    }
    const won = found.length === 2;
    return { found, wrong, won, over: won || wrong >= this.misses,
      left: this.misses - wrong, available: 10 - 2 * wrong,
      points: won ? 10 - 2 * wrong : 0 };
  },
  result(puzzle, guesses) {
    const state = this.progress(puzzle, guesses);
    if (!state.over) throw new Error("That game isn't finished yet.");
    return { won: state.won, tries: guesses.length, points: state.points };
  }
});
