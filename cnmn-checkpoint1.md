# CNMN — Game Design Checkpoint

## Concept

A daily word puzzle game inspired by Part III ("Spelling Clues") of the Modern Language Aptitude Test (MLAT), used by the Foreign Service Institute to assess language learning aptitude.

Players decode **phonetically compressed words** (disguised spellings) and connect them in a chain where each answer hints at the next.

---

## Core Mechanic

**Disguised Words:** Words spelled approximately as they sound, with letters simplified or removed.

Examples from MLAT:
- `kloz` → clothes
- `prezns` → presents  
- `grbj` → garbage
- `restrnt` → restraint

This is NOT simply "vowels removed" — it's phonetic shorthand. Some vowels stay when sonically essential; consonants may change to reflect pronunciation.

---

## Game Flow

1. **Link 1:** Category shown (e.g., "Ocean animal")
2. **Player picks** from 4 disguised word options
3. **Correct:** Answer revealed (SHARK), brief pause, then...
4. **Link 2+:** Only the previous answer shown — player must infer the connection
5. **Repeat** until chain complete
6. **End screen:** Stats + full chain review

**Two-layer puzzle:**
1. Figure out what connects to the previous answer
2. Decode which disguised word matches

---

## Rules

| Element | Decision |
|---------|----------|
| Links per day | 6 |
| Input | Multiple choice (4 options) |
| Failure state | None — play until solved |
| Wrong guesses | Eliminated from options, miss counter increments |
| Hints | None (wrong guesses eliminate options naturally) |
| Daily scaling | Links 1-2 easy, 3-4 moderate, 5-6 hard |

---

## Stats & Sharing

**End screen shows:**
- Time to complete (M:SS)
- Total misses

**Share format:**
```
CNMN #47 🔗
●●●○●○
2:34 | 2 missed
```

- `●` = solved clean (no misses on that link)
- `○` = needed extra guesses

---

## Sample Chain

| Link | Prompt | Options | Answer | Bridge Logic |
|------|--------|---------|--------|--------------|
| 1 | "Ocean animal" | shrk, cml, frg, lbrtr | shrk (SHARK) | Has sharp teeth... |
| 2 | SHARK | drl, hmrtn, skrw, pncl | drl (DRILL) | Makes holes... |
| 3 | DRILL | drik, pump, fns, bskt | drik (DERRICK) | Tall tower... |
| 4 | DERRICK | efl, lvr, notr, mprs | efl (EIFFEL) | Made of iron... |
| 5 | EIFFEL | irn, wdg, putr, drvr | irn (IRON) | Pressed flat... |
| 6 | IRON | colr, slf, cuf, bttn | colr (COLLAR) | — |

---

## UI/UX Notes

**Aesthetic:** Warm, editorial, puzzle-y
- Paper-tone background (`#faf7f2`)
- Monospace font for disguised words (cipher feel)
- Serif font for UI text
- Minimal, focused layout

**Audio:**
- Rising tones on correct
- Low thud on wrong
- Celebratory arpeggio on completion

**Animations:**
- Shake on wrong guess
- Fade transition between links
- Option grays out when eliminated

---

## Comparables

- **NYT Games** (Wordle, Connections) — daily ritual, shareable results
- **Clues by Sam** — no failure state, stats at end
- **Only Connect (BBC)** — chain/connection logic, missing vowels round

---

## Academic Source

**Modern Language Aptitude Test (MLAT)**  
Carroll, J.B. & Sapon, S. (1959)

Part III "Spelling Clues" tests:
- Sound-symbol association ability
- English vocabulary knowledge

Used by Foreign Service Institute, Peace Corps, military, missionaries to predict language learning success.

---

## Open Questions / Future Polish

- Difficulty tuning across days of week
- Onboarding for first-time players
- Streak tracking
- Animation/transition refinements
- Sound design polish
- Backend for daily puzzle delivery

---

## Prototype

React component: `cnmn-prototype.jsx`

Hardcoded single chain, core loop functional:
- Category/answer display
- 4-option multiple choice
- Miss tracking
- End screen with stats
- Share to clipboard
- Audio feedback
