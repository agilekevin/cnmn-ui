# cnmn - Word Puzzle Game

A word puzzle game where players decode phonetically disguised words and identify synonyms. Inspired by the MLAT language aptitude test.

## Game Concept

Inspired by [Part III of the Modern Language Aptitude Test (MLAT)](https://lltf.net/mlat-sample-items/mlat-part-iii/), players decode phonetically disguised words and identify synonyms.

### MLAT Part III: Spelling Clues

The MLAT is a standardized test measuring language learning aptitude. Part III ("Spelling Clues") presents words in non-standard phonetic spellings, and test-takers must identify the meaning from multiple choices — in just 6 seconds per question.

**Official MLAT examples:**

| Disguised | Decoded | Answer Choices | Correct |
|-----------|---------|----------------|---------|
| kloz | clothes | attire, nearby, stick, giant, relatives | **attire** |
| restrnt | restraint | food, self-control, sleep, space explorer, drug | **self-control** |
| prezns | presents | kings, explanations, dates, gifts, forecasts | **gifts** |
| grbj | garbage | car port, seize, boat, boast, waste | **waste** |

cnmn builds on this concept by adding:
- Multiple-choice distractors (wrong decodings, non-synonyms, phonetic traps)
- Themed quiz sets
- A playful, game-like experience

See `cnmn-checkpoint1.md` for full game design details.

## How the Puzzle Works

Each puzzle presents a **prompt word** and four **consonant-only options**. Players must:

1. **Decode** the consonant patterns back into words
2. **Identify** which decoded word is a true synonym of the prompt

### Example

**Prompt:** "shed"

| Option | Decoded | Analysis |
|--------|---------|----------|
| a: lntso | lean-to? | ❌ Wrong letters — "lean-to" has no 's' |
| b: grj | garage | ✅ **Correct!** A garage is a synonym for shed |
| c: prch | porch | ❌ Valid word, but not a synonym for shed |
| d: chk | chuck? | ❌ Phonetic trap — "ch" ≠ "sh", so not "shack" |

### Distractor Types

The puzzle uses three types of "almost right" distractors:

- **Wrong letters**: The consonants don't quite match a real word (lntso ≈ lean-to, but the 's' is wrong)
- **Non-synonyms**: Valid words that decode correctly but aren't synonyms of the prompt
- **Phonetic traps**: Consonant patterns that look like they could be a synonym but use the wrong phoneme

This creates a layered challenge: decoding skill alone isn't enough — players must also verify meaning.

### Quiz Generator

The `puzzle-ai-assistant.html` tool helps create themed quizzes by:
- Generating synonym pairs for a given theme (buildings, emotions, weather, etc.)
- Creating phonetic disguises for answer words
- Reviewing quiz quality before export

The `puzzle-generator.html` tool provides a form-based interface for manually building puzzles.

## Project Structure

```
cnmn/
├── index.html               # Main game (deploy this!)
├── puzzle-generator.html    # Puzzle creation tool
├── puzzle-ai-assistant.html # AI helper for puzzle ideas
├── cnmn-prototype-v2.jsx    # React component source
├── cnmn-checkpoint1.md      # Game design document
└── README.md                # This file
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

### Method 1: Using the Puzzle Generator (Recommended)

1. **Open the generator**
   ```
   \\wsl.localhost\Ubuntu\home\zipwow\cnmn\puzzle-generator.html
   ```
   (Or open `puzzle-generator.html` directly in your browser)

2. **Fill out the form**
   - Puzzle # and date
   - For each of the 6 links:
     - Decoded word (the actual answer)
     - Emoji (click one or type it)
     - 4 disguised word options
     - Correct answer (should match first option)
     - Bridge hint (connection to next word)
   - First link also needs a category

3. **Generate and copy**
   - Click "Generate Code"
   - Click "Copy to Clipboard"

4. **Paste into index.html**
   - Open `index.html`
   - Find `const CHAIN_DATA = {` (around line 43)
   - Replace the entire CHAIN_DATA object with the generated code

### Method 2: Manual Editing

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

## AI Puzzle Assistant

Need help brainstorming puzzles? Use the AI assistant tool:

```
\\wsl.localhost\Ubuntu\home\zipwow\cnmn\puzzle-ai-assistant.html
```

**Features:**
- **💡 Brainstorm Chain:** Get AI suggestions for 6-word chains based on a theme
- **🎭 Create Disguises:** Generate phonetic variants for words
- **✅ Validate Chain:** Get feedback on connection logic and difficulty

**Providers:**
- **Rule-Based (Free):** No API key needed, uses simple algorithms
- **OpenAI (GPT-4):** More creative, requires API key (~$0.01/puzzle)
- **Anthropic (Claude):** Great at word puzzles, requires API key

**Usage:**
1. Select your provider
2. (Optional) Add API key if using OpenAI/Anthropic
3. Use the three tabs to brainstorm, create disguises, or validate
4. Copy suggestions into the puzzle generator

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

## Analytics

Pageview tracking via [GoatCounter](https://www.goatcounter.com/) (cookie-free, GDPR-friendly).

Dashboard: https://cnmn.goatcounter.com/

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
- Accessibility improvements (keyboard nav, screen readers)
- Backend for puzzle delivery

---

Built with [Claude Code](https://claude.com/claude-code)
