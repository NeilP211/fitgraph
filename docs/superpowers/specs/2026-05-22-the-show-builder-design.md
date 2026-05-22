# FitGraph — "The Show" Center-Stage Builder Design Spec

**Date:** 2026-05-22
**Status:** Approved for planning
**Replaces:** the per-category-rows outfit builder (`OutfitBuilder`).

## 1. Summary

Reimagine the outfit builder as a **fashion show**. The runway runs down the
middle; the chosen pieces **stack into a head-to-toe "look"** on a figure at
center stage; an **animated audience** lines the runway and **cheers when
clicked**; optional **ambient runway music** plays via a toggle. Stays in the
cream / Cinzel / terracotta editorial palette. Backend is unchanged — reuses the
existing `/items/{id}/outfit-suggestions`, `/outfits`, `/feedback`, and
`/images/{id}` endpoints.

## 2. Phases (build in order; each ships independently)

### Phase 1 — Center stage (core "wow")
- Replace `web/app/build/[itemId]/page.tsx` + `OutfitBuilder.tsx` with a
  center-stage layout: a runway/stage down the middle with the **seed piece**
  placed in its slot, and **category suggestion rails** flanking it.
- **Figure stacking:** selecting an item for a category animates its cutout
  image into a vertical **slot** so the selections compose a head-to-toe look
  over a faint **mannequin/dress-form silhouette**. Slot map by
  `semantic_category`:
  - center column (top→bottom): `hats` → `sunglasses` → `tops`/`outerwear`
    (torso; `all-body`/dresses span torso+legs) → `bottoms` (legs) →
    `shoes` (base)
  - side floats: `bags` (left), `jewellery` (right/neck), `scarves` (neck),
    `accessories` (side). Unmapped categories default to a side float.
  - one selection per category; the seed occupies its own category's slot and is
    badged as the seed; tapping a different suggestion swaps that slot (with a
    swap animation).
- Suggestion rails: per category (from the existing endpoint), horizontally
  scrollable; cards keep the match-score badge (CountUp) + thumbs feedback.
- Save: name + **Save the look** (`POST /outfits` with seed + selected ids) —
  reuse existing flow; keep the camera-flash on save.
- Reuse existing motion primitives (`Reveal`, `CountUp`), palette, fonts.
  Responsive: on narrow screens stack figure above rails.

### Phase 2 — The crowd
- Stylized **audience silhouettes** (SVG, ink/sepia, on-palette) along the foot
  of the runway, gently swaying/clapping in a loop (staggered, subtle).
- **Click an audience member → it cheers**: a jump + ✨ burst animation (and a
  cheer SFX once Phase 3 audio exists). Reduced-motion: no idle sway; click
  still gives a small static acknowledgement.

### Phase 3 — Audio
- A small **♪ play/mute toggle** (corner of the stage), **off by default**
  (browsers block autoplay; play starts on user gesture). Plays a looping
  **ambient runway track**.
- **Cheer/applause SFX** fires on audience click.
- **Assets:** prefer small **royalty-free / CC0** audio files committed under
  `web/public/audio/` (with a `CREDITS`/license note). If a properly-licensed
  file can't be reliably obtained, **fall back to Web Audio API** synthesis
  (ambient pad + applause burst) so there are zero licensing/asset issues.
  Respect a global mute; persist the user's mute choice (localStorage).

## 3. Accessibility & performance
- All motion behind `prefers-reduced-motion`. Audio off by default, with a
  visible, keyboard-accessible toggle; never autoplay. Transform/opacity-based
  animation; keep it smooth. Alt text on item images; rails keyboard-navigable;
  the figure conveys selections textually too (for SR users).

## 4. Out of scope
- No backend/model/data changes. No true 3D avatar/virtual try-on — the figure
  is a stylized stacked collage of the cutout images. AWS deploy still deferred.

## 5. Verification
- Each phase: `npm run lint` + `npm run build` green; backend `pytest` stays
  green (unchanged); browser verification via agent-browser (build flow:
  pick suggestions → pieces stack into the figure → save; Phase 2: crowd sways +
  cheers on click; Phase 3: music toggle + cheer SFX). Screenshots saved for
  review. Commit + push per phase.
