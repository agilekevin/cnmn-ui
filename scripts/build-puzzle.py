#!/usr/bin/env python3
"""
Build script to inject today's puzzle into index.html.

Usage:
    python scripts/build-puzzle.py [--date YYYY-MM-DD]

If no date is provided, uses today's date.
"""

import json
import os
import re
import sys
from datetime import datetime

# Emoji mapping for common themes/words (can be expanded)
EMOJI_MAP = {
    'building': '🏢', 'house': '🏠', 'home': '🏠', 'garage': '🏗️',
    'hotel': '🏨', 'castle': '🏰', 'church': '⛪', 'tower': '🗼',
    'emotion': '😊', 'happy': '😊', 'sad': '😢', 'angry': '😠',
    'weather': '🌤️', 'rain': '🌧️', 'sun': '☀️', 'storm': '⛈️',
    'animal': '🐾', 'dog': '🐕', 'cat': '🐱', 'bird': '🐦',
    'default': '❓'
}

def get_emoji(word, theme=''):
    """Get an emoji for a word or theme."""
    word_lower = word.lower()
    theme_lower = theme.lower()

    for key, emoji in EMOJI_MAP.items():
        if key in word_lower or key in theme_lower:
            return emoji
    return EMOJI_MAP['default']

def transform_quiz_to_chain(quiz_data):
    """Transform our quiz JSON format to the CHAIN_DATA format."""
    pub_date = quiz_data.get('publicationDate', datetime.now().strftime('%Y-%m-%d'))
    theme = quiz_data.get('theme', 'Quiz')
    questions = quiz_data.get('questions', [])

    # Parse date for display
    try:
        date_obj = datetime.strptime(pub_date, '%Y-%m-%d')
        date_display = date_obj.strftime('%A')  # Day name
    except:
        date_display = pub_date

    # Calculate puzzle number from date (days since epoch or similar)
    try:
        epoch = datetime(2024, 1, 1)
        date_obj = datetime.strptime(pub_date, '%Y-%m-%d')
        puzzle_num = (date_obj - epoch).days + 1
    except:
        puzzle_num = 1

    links = []
    for i, q in enumerate(questions):
        # Build options array: correct answer first, then distractors
        options = [q.get('answerDisguise', '')]
        for d in q.get('distractors', []):
            options.append(d.get('disguise', ''))

        # Shuffle options (but keep track of answer)
        import random
        answer_disguise = q.get('answerDisguise', '')
        random.shuffle(options)

        link = {
            'category': q.get('prompt', '').capitalize(),  # Prompt becomes the hint
            'options': options[:4],  # Max 4 options
            'answer': answer_disguise,
            'decoded': q.get('answer', ''),
            'emoji': get_emoji(q.get('answer', ''), theme),
            'bridge': None  # No chaining in quiz mode
        }
        links.append(link)

    return {
        'number': puzzle_num,
        'date': date_display,
        'links': links
    }

def inject_puzzle_data(html_content, chain_data):
    """Replace the puzzle data section in index.html."""
    # Convert to JavaScript
    chain_js = json.dumps(chain_data, indent=6, ensure_ascii=False)
    # Fix indentation for embedding
    chain_js = chain_js.replace('\n', '\n    ')

    new_block = f'''// __PUZZLE_DATA_START__
    const CHAIN_DATA = {chain_js};
    // __PUZZLE_DATA_END__'''

    # Find and replace between markers (avoid re.sub escape issues)
    start_marker = '// __PUZZLE_DATA_START__'
    end_marker = '// __PUZZLE_DATA_END__'

    start_idx = html_content.find(start_marker)
    end_idx = html_content.find(end_marker) + len(end_marker)

    if start_idx == -1 or end_idx == -1:
        raise ValueError("Could not find puzzle data markers in index.html")

    new_html = html_content[:start_idx] + new_block + html_content[end_idx:]

    return new_html

def main():
    # Parse arguments
    target_date = datetime.now().strftime('%Y-%m-%d')
    if len(sys.argv) > 2 and sys.argv[1] == '--date':
        target_date = sys.argv[2]

    # Paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(script_dir)
    puzzles_dir = os.path.join(root_dir, 'puzzles')
    index_path = os.path.join(root_dir, 'index.html')

    # Find puzzle file
    puzzle_file = os.path.join(puzzles_dir, f'{target_date}.json')

    if not os.path.exists(puzzle_file):
        print(f'No puzzle found for {target_date}')
        print(f'Looking for: {puzzle_file}')
        sys.exit(1)

    # Load puzzle
    with open(puzzle_file, 'r') as f:
        quiz_data = json.load(f)

    print(f'Loaded puzzle for {target_date}: {quiz_data.get("theme", "unknown theme")}')

    # Transform to CHAIN_DATA format
    chain_data = transform_quiz_to_chain(quiz_data)
    print(f'Transformed to puzzle #{chain_data["number"]} ({chain_data["date"]})')

    # Load and update index.html
    with open(index_path, 'r') as f:
        html_content = f.read()

    new_html = inject_puzzle_data(html_content, chain_data)

    with open(index_path, 'w') as f:
        f.write(new_html)

    print(f'Updated index.html with puzzle data')

if __name__ == '__main__':
    main()
