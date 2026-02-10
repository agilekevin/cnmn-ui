# CNMN Puzzle Generation Prompt

Use the following prompt to ask an LLM to generate new cnmn puzzles.

---

## The Prompt

You are a puzzle designer for **CNMN**, a daily word puzzle game inspired by the MLAT (Modern Language Aptitude Test) "Spelling Clues" format. Your job is to generate high-quality puzzle chains.

### Game Mechanics

The player sees a **category word** (e.g., "spice") and four **compressed word options**. Exactly one option is a compressed version of a word that is a **synonym or example** of the category. The player taps their choice. Wrong guesses are tracked but don't end the game.

A daily puzzle is a **chain of 6 links**. Each solved link reveals the next category, connected by a lateral bridge (e.g., "cinnamon" → next category might be "brown things" or "tree products").

### How Word Compression Works

Compressed words are created by removing letters — usually vowels — and sometimes applying phonetic substitutions. This is NOT simple vowel removal. It is **phonetic shorthand**: the compressed form approximates how the word sounds.

Rules for compression:
- Remove most vowels, but **keep vowels that are sonically essential** (e.g., the "o" in `kloz` for "clothes")
- Apply phonetic substitutions where natural (e.g., `ph` → `f`, `ght` → `t`, `tion` → `shn`, `-es` that sounds like "z" → `z`)
- Drop silent letters (e.g., the "k" in "knife" → `nif`)
- The result should be **pronounceable as the original word** when sounded out

Examples:
| Word | Compressed | Why |
|------|-----------|-----|
| clothes | kloz | "cl" → "kl", "-thes" sounds like "z" |
| cinnamon | cnmn | vowels removed, still readable |
| garbage | grbj | vowels removed, "-age" → "j" |
| restaurant | restrnt | minimal vowel removal, keeps readability |
| presents | prezns | "s" → "z" (phonetic), vowels stripped |
| spatula | sptvla | compressed but keeps critical vowels |
| cashmere | cshmr | vowels stripped |
| happy | hpy | simple vowel removal |

### Difficulty Levels

Each daily chain should scale in difficulty across its 6 links:

**Links 1–2: Easy (Level 1)**
- Standard vowel removal, common words
- Distractors are random/unrelated words
- Example: Clue `hpy` (happy) → Correct: **Glad** | Distractors: Sad, Tired, Angry

**Links 3–4: Medium (Level 2 — "Look-Alike")**
- The compressed clue is designed to **look like multiple words**, but a specific "differentiating letter" proves it can only be one
- Distractors are **synonyms of the OTHER words** the clue resembles (not random)
- Example: Clue `blst` → looks like "best", "bust", "last", but the 'l'+'b' confirms **blast** → Correct: **Explosion** | Distractors: Greatest (synonym of "best"), Failure (synonym of "bust"), Final (synonym of "last")

**Links 5–6: Hard (Level 3–4 — Phonetic + Maximum Compression)**
- Phonetic spelling: `ph`→`f`, `c`→`k` or `s`, `ough`→`uf`, etc.
- Extreme compression: multiple vowels stripped, skeletal clues
- Distractors test specific letter presence/absence
- No perfect homophones as target words (not right/write)
- Example: Clue `nife` (knife) → Correct: **Blade** | Distractors based on similar-sounding words like "life", "wife"

### Critical Rules for Answers and Distractors

1. **The correct answer is NEVER the decoded word itself.** It must be a strict **synonym, definition, or category example**.
   - ✅ `cloz` (clothes) → **Attire**
   - ❌ `cloz` (clothes) → **Clothes**

2. **Distractors must be related words but NOT synonyms** of the target. They should be words associated with alternate interpretations of the clue.
   - `cloz` could also look like "close" → Distractor: **Door** (a thing you close, but not a synonym of "close")

3. **Every clue must be unambiguous** when you examine which specific letters are present or absent, even if it looks ambiguous at first glance.
   - ❌ Bad: `btl` (could be "bottle" or "battle" — truly ambiguous)
   - ✅ Good: `blst` (the 'l'+'b' combination confirms "blast")

4. **Each puzzle needs exactly 4 options**: 1 correct synonym + 3 distractors.

### Chain Structure

Each chain of 6 links must have a **bridging logic** connecting them. When a link is solved, the decoded word has a lateral connection to the next category.

Example chain:
```
SPICE → cnmn (cinnamon)
  cinnamon is a tree bark...
TREE → wlnt (walnut)
  walnut has a hard shell...
SHELL → trtls (turtles)
  turtles are slow...
SLOW → mlses (molasses)
  molasses is sticky...
STICKY → situshn (situation)
  "sticky situation" is an idiom...
IDIOM → brk (break → "break a leg")
```

The bridge between links should produce an "aha!" moment — not just a dictionary association but a playful or surprising lateral connection.

### Output Format

Generate puzzles in this JSON format:

```json
{
  "puzzle_number": 1,
  "chain": [
    {
      "link": 1,
      "difficulty": "easy",
      "category": "spice",
      "compressed": "cnmn",
      "answer_word": "cinnamon",
      "correct_option": "Bark seasoning",
      "distractors": ["Chili pepper", "Rock salt", "Vanilla bean"],
      "bridge_to_next": "Cinnamon comes from tree bark..."
    },
    {
      "link": 2,
      "difficulty": "easy",
      "category": "tree",
      "compressed": "wlnt",
      "answer_word": "walnut",
      "correct_option": "Hard shell nut",
      "distractors": ["Pine cone", "Maple leaf", "Tree stump"],
      "bridge_to_next": "Walnuts have a hard shell..."
    }
  ]
}
```

### Quality Checklist

Before finalizing each link, verify:
- [ ] The compressed word can be logically decoded back to the answer word
- [ ] The correct option is a true synonym/definition (NOT the word itself)
- [ ] Distractors are related but NOT synonyms of the answer
- [ ] The compressed clue is unambiguous — only one English word matches
- [ ] (Level 2+) Distractors correspond to alternate readings of the clue
- [ ] (Level 3+) Phonetic logic is consistent
- [ ] The bridge connection to the next link is surprising/delightful
- [ ] Difficulty scales across the 6 links (easy → hard)

### Now Generate

Please generate a complete 6-link daily CNMN chain. Start with a category of your choice. Ensure difficulty scales from links 1–2 (easy) through 3–4 (medium) to 5–6 (hard). Provide the full JSON output and briefly explain each bridge connection.
