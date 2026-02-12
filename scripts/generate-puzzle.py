#!/usr/bin/env python3
"""
Layered pipeline puzzle generator for CNMN.

Multi-stage pipeline:
  1. Theme → 6 word pairs (LLM)
  2. Deterministic validation (consonant skeleton uniqueness, etc.)
  3. Parallel distractor generation (6 concurrent LLM calls)
  4. Rule-based disguise generation (no LLM)
  5. Playtester review (LLM-as-judge)
  6. Targeted regeneration for flagged questions

Usage:
    venv/bin/python scripts/generate-puzzle.py --theme "Breakfast Foods" --date 2026-02-17
"""

import argparse
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import requests
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def consonant_skeleton(word):
    """Strip vowels and lowercase — the key uniqueness check."""
    return re.sub(r'[aeiou]', '', word.lower())


def generate_disguise(word):
    """Rule-based consonant-stripping disguise (ported from puzzle-ai-assistant.html)."""
    if not word:
        return ''
    lower = word.lower()
    disguise = lower
    # Phonetic substitutions (order matters — apply suffix rules first)
    disguise = re.sub(r'tion$', 'shn', disguise)
    disguise = re.sub(r'sion$', 'zhn', disguise)
    disguise = re.sub(r'age$', 'j', disguise)
    disguise = re.sub(r'dge$', 'j', disguise)
    disguise = re.sub(r'ght$', 't', disguise)
    disguise = disguise.replace('ck', 'k')
    disguise = disguise.replace('ph', 'f')
    disguise = disguise.replace('wh', 'w')
    disguise = disguise.replace('wr', 'r')
    disguise = disguise.replace('kn', 'n')
    # Strip vowels
    disguise = re.sub(r'[aeiou]', '', disguise)

    if len(disguise) < 2:
        # Keep some vowels if result is too short
        disguise = re.sub(r'[aeiou](?=[aeiou])', '', lower)
        disguise = re.sub(r'[aeiou]$', '', disguise)

    return disguise or lower[:3]


def _disguise_with_kept_vowel(word):
    """Generate a disguise that retains the first interior vowel for disambiguation."""
    lower = word.lower()
    # Apply phonetic substitutions first (same as generate_disguise)
    d = lower
    d = re.sub(r'tion$', 'shn', d)
    d = re.sub(r'sion$', 'zhn', d)
    d = re.sub(r'age$', 'j', d)
    d = re.sub(r'dge$', 'j', d)
    d = re.sub(r'ght$', 't', d)
    d = d.replace('ck', 'k').replace('ph', 'f').replace('wh', 'w')
    d = d.replace('wr', 'r').replace('kn', 'n')
    # Strip vowels except the first interior one
    chars = list(d)
    kept = False
    for idx in range(1, len(chars) - 1):
        if chars[idx] in 'aeiou' and not kept:
            kept = True  # keep this one
        elif chars[idx] in 'aeiou':
            chars[idx] = ''
    # Still strip leading/trailing vowels
    result = ''.join(chars)
    if result and result[0] in 'aeiou':
        result = result[1:]
    if result and result[-1] in 'aeiou':
        result = result[:-1]
    return result or lower[:3]


def resolve_disguise_collisions(answer_disguise, distractor_disguises, answer_word='', distractor_words=None):
    """If any two options in a question share a disguise, try to differentiate them.

    Re-derives colliding distractors with a kept interior vowel.
    Returns (answer_disguise, distractor_disguises) — possibly modified.
    """
    distractor_words = distractor_words or [''] * len(distractor_disguises)

    all_disguises = [answer_disguise] + distractor_disguises

    # Quick check: any duplicates?
    if len(set(all_disguises)) == len(all_disguises):
        return answer_disguise, distractor_disguises

    # The answer disguise is authoritative; fix colliding distractors
    taken = {answer_disguise}
    for i, d in enumerate(distractor_disguises):
        if d in taken:
            # Try keeping an interior vowel
            alt = _disguise_with_kept_vowel(distractor_words[i]) if distractor_words[i] else d
            if alt != d and alt not in taken:
                distractor_disguises[i] = alt
            else:
                # Last resort: prepend first letter of word
                first = distractor_words[i][0].lower() if distractor_words[i] else str(i)
                distractor_disguises[i] = first + d
        taken.add(distractor_disguises[i])

    return answer_disguise, distractor_disguises


def call_llm(server, model, prompt, max_tokens=2048, auth=None):
    """POST to /api/chat and return the response text."""
    url = f'{server}/api/chat'
    payload = {
        'model': model,
        'prompt': prompt,
        'max_tokens': max_tokens,
    }
    headers = {'Content-Type': 'application/json'}
    resp = requests.post(url, json=payload, headers=headers, auth=auth, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    return data.get('content', data.get('response', data.get('text', '')))


def parse_json_response(text):
    """Extract JSON from LLM response, handling markdown code fences."""
    # Try to find JSON inside code fences first
    m = re.search(r'```(?:json)?\s*\n?(.*?)\n?\s*```', text, re.DOTALL)
    if m:
        text = m.group(1)
    # Strip leading/trailing whitespace
    text = text.strip()
    return json.loads(text)

# ---------------------------------------------------------------------------
# Stage 1: Theme → 6 Word Pairs
# ---------------------------------------------------------------------------

STAGE1_PROMPT = """\
You are generating puzzle content for a word-guessing game called CNMN ("Consonant Moon").

Theme: "{theme}"

Generate exactly 6 prompt/answer pairs that fit this theme. Each pair has:
- "prompt": a specific noun or thing that is an EXAMPLE of the theme — not an adjective, \
feeling, or loosely related concept. For "Winter Clothing" use garment names like "jacket", \
"mittens", "scarf" — NOT "cold", "cozy", "frosty".
- "answer": a synonym or strongly-associated word for the prompt (what players must guess)
- "emoji": a single emoji that represents the prompt (or empty string if none fits)

Rules:
- All words must be common English words
- Every prompt must be a concrete instance/example of the theme category
- Answers should be interesting synonyms — not the most obvious choice
- No duplicate prompts or answers across the 6 pairs
- Prompt and answer must be different words for each pair
- Answers should vary in length (mix of short and long words)
- Order from easiest to hardest synonym relationship

Return ONLY a JSON array, no other text:
[{{"prompt": "word1", "answer": "WORD2", "emoji": "🎯"}}, ...]
"""


def stage1_generate_pairs(server, model, theme, auth=None):
    """Ask the LLM for 6 prompt/answer pairs."""
    prompt = STAGE1_PROMPT.format(theme=theme)
    text = call_llm(server, model, prompt, max_tokens=1024, auth=auth)
    return parse_json_response(text)

# ---------------------------------------------------------------------------
# Stage 2: Deterministic Validation
# ---------------------------------------------------------------------------

def stage2_validate(pairs):
    """Validate the 6 pairs. Returns (ok, errors)."""
    errors = []

    if len(pairs) != 6:
        errors.append(f'Expected 6 pairs, got {len(pairs)}')
        return False, errors

    prompts = []
    answers = []
    skeletons = []

    for i, p in enumerate(pairs):
        prompt_word = p.get('prompt', '').strip()
        answer_word = p.get('answer', '').strip()

        if not prompt_word or not answer_word:
            errors.append(f'Pair {i+1}: missing prompt or answer')
            continue

        if prompt_word.lower() == answer_word.lower():
            errors.append(f'Pair {i+1}: prompt "{prompt_word}" == answer "{answer_word}"')

        prompts.append(prompt_word.lower())
        answers.append(answer_word.upper())
        skeletons.append(consonant_skeleton(answer_word))

    # Duplicate checks
    if len(set(prompts)) != len(prompts):
        errors.append('Duplicate prompts found')
    if len(set(answers)) != len(answers):
        errors.append('Duplicate answers found')

    # Consonant skeleton uniqueness
    if len(set(skeletons)) != len(skeletons):
        seen = {}
        for i, sk in enumerate(skeletons):
            if sk in seen:
                errors.append(
                    f'Skeleton collision: "{answers[i]}" and "{answers[seen[sk]]}" '
                    f'both produce "{sk}"'
                )
            seen[sk] = i

    return len(errors) == 0, errors

# ---------------------------------------------------------------------------
# Stage 3: Parallel Distractor Generation
# ---------------------------------------------------------------------------

STAGE3_PROMPT = """\
For a word-guessing puzzle, the player sees a clue "{prompt}" and must pick the synonym "{answer}" \
from four disguised options (vowels stripped).

The answer's consonant skeleton is "{skeleton}".

Generate exactly 3 distractor words. Each distractor must:
- Be a real, common English word
- NOT be a synonym of "{prompt}"
- Have a consonant skeleton DIFFERENT from "{skeleton}"
- Be plausible enough to trick a player (related to the theme or similar-looking when disguised)

Assign each distractor one of these types:
- "wrong-letters": a word whose disguise looks similar but decodes to something wrong
- "non-synonym": a thematically related word that isn't actually a synonym
- "phonetic-trap": a word that sounds vaguely similar when consonants are read aloud

Return ONLY a JSON array:
[{{"word": "EXAMPLE", "type": "wrong-letters"}}, ...]
"""


def stage3_generate_distractors_for_question(server, model, question, auth=None):
    """Generate 3 distractors for a single question. Returns list of dicts."""
    prompt_word = question['prompt']
    answer_word = question['answer']
    skeleton = consonant_skeleton(answer_word)

    prompt = STAGE3_PROMPT.format(
        prompt=prompt_word, answer=answer_word, skeleton=skeleton
    )
    text = call_llm(server, model, prompt, max_tokens=512, auth=auth)
    distractors = parse_json_response(text)

    # Validate: no distractor matches answer/prompt or shares skeleton
    valid = []
    for d in distractors:
        word = d.get('word', '').upper()
        d['word'] = word
        if not word:
            continue
        if word == answer_word.upper() or word == prompt_word.upper():
            continue
        d_skel = consonant_skeleton(word)
        if d_skel != skeleton and d_skel:
            valid.append(d)

    if len(valid) < 3:
        # Pad with whatever we have; a later stage will catch issues
        return distractors[:3]
    return valid[:3]


def stage3_parallel_distractors(server, model, pairs, auth=None, max_retries=2):
    """Generate distractors for all 6 questions in parallel."""
    results = [None] * len(pairs)

    def gen(idx):
        for attempt in range(max_retries + 1):
            try:
                distractors = stage3_generate_distractors_for_question(
                    server, model, pairs[idx], auth=auth
                )
                if len(distractors) >= 3:
                    return idx, distractors[:3]
                if attempt < max_retries:
                    print(f'  Q{idx+1}: retrying distractor generation (got {len(distractors)})')
            except Exception as e:
                if attempt < max_retries:
                    print(f'  Q{idx+1}: retrying distractor generation ({e})')
                else:
                    print(f'  Q{idx+1}: distractor generation failed: {e}')
        return idx, distractors if 'distractors' in dir() else []

    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(gen, i) for i in range(len(pairs))]
        for future in as_completed(futures):
            idx, distractors = future.result()
            results[idx] = distractors

    return results

# ---------------------------------------------------------------------------
# Stage 4: Rule-Based Disguise Generation
# ---------------------------------------------------------------------------

def stage4_generate_disguises(pairs, all_distractors):
    """Generate disguises for answers and distractors. Returns list of question dicts."""
    questions = []
    for i, pair in enumerate(pairs):
        answer = pair['answer'].upper()
        answer_disguise = generate_disguise(answer)

        distractor_list = all_distractors[i] or []
        distractor_disguises = [generate_disguise(d['word']) for d in distractor_list]

        # Resolve collisions
        distractor_words = [d['word'] for d in distractor_list]
        answer_disguise, distractor_disguises = resolve_disguise_collisions(
            answer_disguise, distractor_disguises,
            answer_word=answer, distractor_words=distractor_words,
        )

        # Build distractor records
        distractors_out = []
        for j, d in enumerate(distractor_list):
            distractors_out.append({
                'word': d['word'].upper(),
                'disguise': distractor_disguises[j] if j < len(distractor_disguises) else generate_disguise(d['word']),
                'type': d.get('type', 'non-synonym'),
            })

        # Difficulty assignment: 1-2 easy, 3-4 medium, 5-6 hard
        if i < 2:
            difficulty = 'easy'
        elif i < 4:
            difficulty = 'medium'
        else:
            difficulty = 'hard'

        questions.append({
            'prompt': pair['prompt'].lower(),
            'emoji': pair.get('emoji', ''),
            'answer': answer,
            'answerDisguise': answer_disguise,
            'distractors': distractors_out,
            'difficulty': difficulty,
            'correctOption': answer.capitalize(),
        })

    return questions

# ---------------------------------------------------------------------------
# Stage 5: Playtester Review (LLM-as-Judge)
# ---------------------------------------------------------------------------

STAGE5_PROMPT = """\
You are a playtester for the word puzzle game CNMN ("Consonant Moon"). In this game, \
players see a clue word and must pick the correct synonym from 4 options that have been \
"disguised" by stripping vowels and applying phonetic shortcuts.

Here is a complete puzzle to review:

{puzzle_json}

For each question, evaluate:
1. Can the answer be reasonably decoded from its disguise?
2. Are the distractors distinguishable from the answer's disguise?
3. Is the synonym relationship between prompt and answer clear?
4. Are there any consonant skeleton collisions (two options producing the same stripped form)?

Return ONLY a JSON array of issues found. If the puzzle is perfect, return an empty array [].
Format: [{{"question": 1, "severity": "high", "issue": "description"}}, ...]

Severity levels:
- "high": game-breaking (collision, answer undecodable, synonym wrong)
- "low": minor quality concern (distractor too easy, etc.)
"""


def stage5_playtester(server, model, questions, theme, auth=None):
    """Send puzzle to LLM playtester, return list of issues."""
    puzzle_for_review = {
        'theme': theme,
        'questions': questions,
    }
    prompt = STAGE5_PROMPT.format(puzzle_json=json.dumps(puzzle_for_review, indent=2))
    text = call_llm(server, model, prompt, max_tokens=2048, auth=auth)
    try:
        return parse_json_response(text)
    except (json.JSONDecodeError, ValueError):
        print(f'  Warning: could not parse playtester response')
        return []

# ---------------------------------------------------------------------------
# Stage 6: Targeted Regeneration
# ---------------------------------------------------------------------------

def stage6_regenerate(server, model, questions, issues, pairs, auth=None):
    """Re-run distractor + disguise generation for high-severity flagged questions."""
    high_issues = [iss for iss in issues if iss.get('severity') == 'high']
    if not high_issues:
        return questions

    # Which question indices need regen?
    flagged = set()
    for iss in high_issues:
        q_num = iss.get('question', 0)
        if 1 <= q_num <= len(questions):
            flagged.add(q_num - 1)  # 0-indexed

    if not flagged:
        return questions

    print(f'  Regenerating questions: {[i+1 for i in sorted(flagged)]}')

    for idx in flagged:
        # Re-generate distractors
        try:
            new_distractors = stage3_generate_distractors_for_question(
                server, model, pairs[idx], auth=auth
            )
        except Exception as e:
            print(f'  Q{idx+1}: regen failed ({e}), keeping original')
            continue

        if len(new_distractors) < 3:
            print(f'  Q{idx+1}: regen produced only {len(new_distractors)} distractors, keeping original')
            continue

        # Rebuild disguises for this question
        answer = pairs[idx]['answer'].upper()
        answer_disguise = generate_disguise(answer)
        distractor_disguises = [generate_disguise(d['word']) for d in new_distractors]
        distractor_words = [d['word'] for d in new_distractors]
        answer_disguise, distractor_disguises = resolve_disguise_collisions(
            answer_disguise, distractor_disguises,
            answer_word=answer, distractor_words=distractor_words,
        )

        distractors_out = []
        for j, d in enumerate(new_distractors[:3]):
            distractors_out.append({
                'word': d['word'].upper(),
                'disguise': distractor_disguises[j],
                'type': d.get('type', 'non-synonym'),
            })

        questions[idx]['answerDisguise'] = answer_disguise
        questions[idx]['distractors'] = distractors_out

    return questions

# ---------------------------------------------------------------------------
# Output Assembly
# ---------------------------------------------------------------------------

def assemble_puzzle(theme, date_str, questions):
    """Build the final puzzle JSON matching the existing format."""
    return {
        'theme': theme,
        'publicationDate': date_str,
        'questions': questions,
    }

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description='Generate a CNMN puzzle via layered pipeline')
    parser.add_argument('--theme', required=True, help='Puzzle theme')
    parser.add_argument('--date', required=True, help='Publication date (YYYY-MM-DD)')
    parser.add_argument('--model', default='claude-sonnet-4-5-20250929', help='LLM model ID')
    parser.add_argument('--server', default='http://localhost:5000', help='Server URL')
    args = parser.parse_args()

    # Validate date format
    try:
        datetime.strptime(args.date, '%Y-%m-%d')
    except ValueError:
        print(f'Error: invalid date format "{args.date}" (expected YYYY-MM-DD)')
        sys.exit(1)

    # Load .env for auth credentials
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(script_dir)
    load_dotenv(os.path.join(root_dir, '.env'))

    auth_users = os.environ.get('AUTH_USERS', '')
    auth = None
    if auth_users:
        first_entry = auth_users.split(',')[0].strip()
        if ':' in first_entry:
            user, password = first_entry.split(':', 1)
            auth = (user, password)

    # --- Stage 1 ---
    print(f'Stage 1: Generating word pairs for theme "{args.theme}"...')
    pairs = None
    for attempt in range(3):
        try:
            pairs = stage1_generate_pairs(args.server, args.model, args.theme, auth=auth)
        except Exception as e:
            print(f'  Attempt {attempt+1} failed: {e}')
            continue

        # --- Stage 2 ---
        ok, errors = stage2_validate(pairs)
        if ok:
            print(f'  Got {len(pairs)} valid pairs')
            break
        else:
            print(f'  Validation failed (attempt {attempt+1}): {"; ".join(errors)}')
            pairs = None

    if pairs is None:
        print('Error: failed to generate valid word pairs after 3 attempts')
        sys.exit(1)

    # --- Stage 3 ---
    print('Stage 3: Generating distractors (parallel)...')
    all_distractors = stage3_parallel_distractors(
        args.server, args.model, pairs, auth=auth
    )

    # --- Stage 4 ---
    print('Stage 4: Generating disguises...')
    questions = stage4_generate_disguises(pairs, all_distractors)

    # --- Stage 5 ---
    print('Stage 5: Playtester review...')
    issues = stage5_playtester(args.server, args.model, questions, args.theme, auth=auth)
    high_count = sum(1 for iss in issues if iss.get('severity') == 'high')
    low_count = len(issues) - high_count
    print(f'  Found {high_count} high-severity, {low_count} low-severity issues')

    # --- Stage 6 ---
    if high_count > 0:
        print('Stage 6: Targeted regeneration...')
        questions = stage6_regenerate(
            args.server, args.model, questions, issues, pairs, auth=auth
        )
    else:
        print('Stage 6: No regeneration needed')

    # --- Output ---
    puzzle = assemble_puzzle(args.theme, args.date, questions)
    puzzles_dir = os.path.join(root_dir, 'puzzles')
    os.makedirs(puzzles_dir, exist_ok=True)
    out_path = os.path.join(puzzles_dir, f'{args.date}.json')

    with open(out_path, 'w') as f:
        json.dump(puzzle, f, indent=2, ensure_ascii=False)
        f.write('\n')

    print(f'\nPuzzle written to {out_path}')
    print(f'  Theme: {args.theme}')
    print(f'  Date:  {args.date}')
    print(f'  Questions:')
    for i, q in enumerate(questions):
        print(f'    {i+1}. {q["prompt"]} → {q["answer"]} [{q["answerDisguise"]}] ({q["difficulty"]})')
        for d in q.get('distractors', []):
            print(f'       - {d["word"]} [{d["disguise"]}] ({d["type"]})')


if __name__ == '__main__':
    main()
