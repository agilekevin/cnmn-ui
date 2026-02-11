# Puzzle Packs: Monetization Plan

## Concept

Sell themed bundles of past puzzles as **Puzzle Packs**. The daily free puzzle drives engagement; packs let players binge on themes they enjoy and support the game.

## What's in a Pack

Each pack contains 5-10 puzzles grouped by theme (e.g. "Animals", "Food & Drink", "Geography"). Packs are curated from the archive — not random, but hand-picked for quality and variety within the theme.

Example packs:
- **Starter Pack** (free, 3 puzzles) — onboarding for the pack experience
- **Animal Kingdom** (5 puzzles) — $1.99
- **Around the World** (7 puzzles) — $2.99
- **Ultimate Wordsmith** (10 puzzles, mixed hard themes) — $4.99
- **Season Pass** (all packs for a month/quarter) — $9.99

## Pricing Strategy

- Keep individual packs cheap ($1.99-$4.99) to minimize purchase friction
- Offer a free starter pack so players experience the flow before paying
- Consider a "buy 3 get 1 free" bundle discount
- Season pass for superfans who want everything

## Payment Integration

**Recommended: Lemon Squeezy** (simplest for digital products)
- No backend needed — generates a checkout link per product
- Handles tax/VAT globally
- Provides license keys or webhook on purchase
- Alternatives: Gumroad (similar simplicity), Stripe (more control, more setup)

**Purchase flow:**
1. Player taps "Puzzle Packs" from the results screen or a new nav element
2. Sees available packs with themes, puzzle count, price
3. Taps "Buy" → redirects to Lemon Squeezy hosted checkout
4. On success, receives an unlock code (or webhook triggers unlock)
5. Returns to cnmn.app and enters the code (or auto-unlocked via URL param)

## Unlock & Delivery

**Option A: Code-based (simplest, no backend)**
- Purchase generates a unique unlock code
- Player enters code on cnmn.app
- Code is validated client-side (signed JWT or hash) and stored in localStorage
- Puzzle pack data is already in the repo (JSON files), just gated behind the code check
- Pro: No server needed. Con: Technically bypassable by determined users (acceptable for price point)

**Option B: API-based (more secure)**
- Purchase triggers webhook to a small API (could live on the existing Render server)
- API stores purchase record, returns pack data
- Player authenticates via email used at checkout
- Pro: Secure. Con: Requires backend work, account system

**Recommendation:** Start with Option A. At $1.99-$4.99, the honor system + light client-side gating is sufficient. Migrate to Option B only if piracy becomes a real issue.

## UI Changes

### Results screen
Add a "Puzzle Packs" link/button below the newsletter signup:
```
[Share]
[Newsletter signup]
[Puzzle Packs - Play more themed puzzles!]
[Answers review]
```

### Pack browser (new screen or modal)
- Grid of available packs with theme artwork, puzzle count, price
- "Owned" badge on purchased packs
- Tap to see puzzles in the pack, then buy or play

### Pack play mode
- Same game UI, but with pack branding at the top
- Sequential play through the pack puzzles
- Track progress per pack in localStorage

## Data Model

Pack definition (JSON, stored in repo):
```json
{
  "id": "animal-kingdom",
  "name": "Animal Kingdom",
  "description": "5 puzzles featuring creatures great and small",
  "price": 1.99,
  "puzzles": ["2025-01-30", "2026-01-29", "2026-02-06", ...],
  "artwork": "packs/animal-kingdom.png"
}
```

Player ownership (localStorage):
```json
{
  "owned_packs": ["starter", "animal-kingdom"],
  "pack_progress": {
    "animal-kingdom": { "completed": 3, "total": 5 }
  }
}
```

## Implementation Roadmap

### Phase 1: Foundation
- [ ] Create `packs/` directory with pack definition JSON files
- [ ] Build pack browser UI (grid of packs)
- [ ] Build pack play mode (load puzzle by date, sequential play)
- [ ] Add "Puzzle Packs" button to results screen

### Phase 2: Payment
- [ ] Set up Lemon Squeezy account and products
- [ ] Generate checkout links per pack
- [ ] Implement unlock code validation (client-side)
- [ ] Store ownership in localStorage

### Phase 3: Polish
- [ ] Pack artwork/thumbnails
- [ ] Progress tracking per pack
- [ ] Free starter pack for onboarding
- [ ] "Gift a pack" feature (generate gift codes)

### Phase 4: Growth
- [ ] Season pass / subscription option
- [ ] Bundle discounts
- [ ] Pack recommendation based on play history
- [ ] Social proof ("X players completed this pack")
