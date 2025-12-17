# CNMN - Word Chain Puzzle Game

A daily word puzzle game where players decode phonetically compressed words and connect them in a chain.

## Game Concept

Inspired by Part III of the Modern Language Aptitude Test (MLAT), players:
1. Decode disguised spellings (e.g., `shrk` → SHARK)
2. Find connections between words in a chain
3. Complete 6 linked puzzles per day

See `cnmn-checkpoint1.md` for full game design details.

## Project Structure

```
cnmn/
├── index.html              # Main game (deploy this!)
├── cnmn-prototype-v2.jsx   # React component source
├── cnmn-checkpoint1.md     # Game design document
└── README.md               # This file
```

## Local Development

Simply open `index.html` in your browser:

**From WSL:**
```
\\wsl.localhost\Ubuntu\home\zipwow\cnmn\index.html
```

**Or use a local server:**
```bash
python -m http.server 8000
# Then visit http://localhost:8000
```

## Releasing a New Puzzle

### 1. Edit the puzzle data

Open `index.html` and find the `CHAIN_DATA` object (around line 43).

Update:
- `number`: Increment puzzle number
- `date`: Today's date or day name
- `links`: Replace all 6 chain links

**Example puzzle format:**
```javascript
{
  category: "Ocean animal",      // Clue for first link only
  options: ["shrk", "cml", "frg", "lbrtr"],  // 4 disguised words
  answer: "shrk",                 // Correct option
  decoded: "SHARK",               // Full word
  emoji: "🦈",                    // Visual representation
  bridge: "Has sharp teeth..."    // Connection hint (null for last link)
}
```

### 2. Test locally

Open `index.html` in your browser and play through the puzzle to verify:
- All words decode correctly
- Connections make sense
- Emojis are appropriate
- No typos in disguised spellings

### 3. Commit and push

```bash
git add index.html
git commit -m "Puzzle #48: [brief theme description]"
git push
```

### 4. Deploy

Your static host will auto-deploy the update.

## Deployment Options

### Option 1: GitHub Pages (Recommended for MVP)

1. Push this repo to GitHub
2. Go to Settings → Pages
3. Source: Deploy from branch `main`
4. Your site: `https://yourusername.github.io/cnmn/`

### Option 2: Netlify

1. Connect your GitHub repo
2. Build settings: None needed (pure static)
3. Publish directory: `/`
4. Auto-deploys on push

### Option 3: Vercel

1. Import GitHub repo
2. Framework: Other
3. Root directory: `./`
4. Auto-deploys on push

## Puzzle Creation Tips

**Good phonetic disguises:**
- Remove vowels when not needed for pronunciation: `shrk` (shark)
- Keep vowels that are essential: `efl` (eiffel) keeps the 'e'
- Simplify consonant clusters: `drl` (drill)
- Use phonetic spelling: `notr` (notre)

**Good chain connections:**
- Clear thematic links (shark → drill = "sharp teeth")
- Avoid overly obscure connections
- Mix difficulty: Links 1-2 easy, 3-4 moderate, 5-6 hard

**Testing your chain:**
- Can someone solve Link 2 knowing only "SHARK"?
- Are the disguised words unique enough to distinguish?
- Do all 4 options fit the phonetic pattern?

## Technical Notes

- Pure static HTML/CSS/JS
- React via CDN (no build step)
- No backend required
- State stored in component only (resets on refresh)
- Audio uses Web Audio API

## Future Enhancements

- Archive of past puzzles
- Streak tracking (localStorage)
- Better mobile responsive design
- Share button with native share API
- Accessibility improvements (keyboard nav, screen readers)
- Backend for puzzle delivery
- Analytics

---

Built with [Claude Code](https://claude.com/claude-code)
