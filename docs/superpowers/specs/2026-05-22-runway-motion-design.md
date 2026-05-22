# FitGraph — "The Runway" Motion & Hero Design Spec

**Date:** 2026-05-22
**Status:** Approved for planning
**Builds on:** the editorial cream/Cinzel/terracotta theme + catalog outfit-builder.

## 1. Summary

Bring FitGraph to life with a fashion-**show** metaphor and tasteful motion, without
abandoning the editorial cream/Cinzel/terracotta aesthetic. A perspective
**catwalk hero**, **staggered "runway" reveals**, a **shared-element page
transition** from browse → builder, **count-up** match scores, and a
**camera-flash** flourish on save. Refined, brand-site motion — not bouncy or
gimmicky — and fully degradable under `prefers-reduced-motion`.

## 2. Goals & non-goals

- **Goal:** a recruiter-impressive, high-craft frontend that feels like a luxury
  collection site; demonstrate real motion/transition engineering.
- **Goal:** stay in the existing palette + type; motion *enhances* the editorial
  look, doesn't replace it.
- **Non-goal:** changing backend, model, data, or routes/behavior. This is
  presentational only.
- **Non-goal:** heavy/jarring animation. Everything subtle, smooth (~200–500ms,
  eased), and skippable.

## 3. Tech

- **Framer Motion** (`motion` package, `motion/react`) for reveals, hover, layout,
  and orchestration.
- **Route transition:** prefer React's View Transition API / `<ViewTransition>`
  (consult the `vercel-react-view-transitions` skill) for a shared-element morph
  of the clicked item into the builder seed; **fall back** gracefully to a
  Framer Motion page transition (`template.tsx`) if the Next version doesn't
  support it cleanly. Do not block the feature on the fancy morph.
- **`prefers-reduced-motion`:** all motion gated; reduced-motion users get the
  static editorial layout with instant (non-animated) state changes.
- Read `web/AGENTS.md` — this is a newer Next.js; check `node_modules/next/dist/docs/`
  before using framework features.

## 4. Components / changes

### 4.1 Runway hero (browse home `app/page.tsx`)
- A CSS 3D **perspective catwalk**: a tapering strip receding to a vanishing
  point (perspective + rotateX on a floor element), a subtle center seam, and
  soft **spotlight cones** (radial-gradient glows) — all in cream/sepia with a
  faint warm stage-light gradient. No new colors.
- The "BROWSE THE CATALOG" Cinzel title sits at the head of the runway; a thin
  rule + the script flourish remain.
- Subtle **scroll parallax** on the runway/spotlights (transform on scroll).
- Keep it performant and tasteful; the catwalk is a backdrop, the category nav +
  grid remain the functional focus directly below.

### 4.2 Motion primitives (`web/components/motion/`)
- `<Reveal>` — wraps children; staggered fade + slide-up on enter/in-view
  (Framer Motion `whileInView`, stagger via parent variants). Reused by the grid
  and builder sections.
- `<CountUp value> ` — animates a number from 0 → value (used for match-score
  badges). Respects reduced-motion (renders final value instantly).
- A shared `motionConfig`/`prefers-reduced-motion` hook.

### 4.3 Browse grid (`components/BrowseGrid.tsx`)
- Cards reveal in a **staggered** "models walking out" sequence as they load /
  scroll into view; hover = gentle lift + slow image zoom (Ken Burns).

### 4.4 Page transition browse → builder
- Clicking an item transitions to `/build/[itemId]`; the clicked card's image
  **morphs/expands into the builder's seed item** (shared-element via View
  Transition API / `view-transition-name`, or a clean fade-slide fallback).

### 4.5 Outfit builder (`components/OutfitBuilder.tsx`, `OutfitTray.tsx`)
- Category sections reveal staggered; suggestion cards stagger within each row.
- Match-score badges use `<CountUp>` (e.g. 0 → 97%).
- Selecting a piece animates it into the tray (layout animation / slide-in).
- **Save = camera flash:** on successful save, a brief full-screen white
  flash + subtle sparkle, then the existing success state ("paparazzi finale").

### 4.6 Saved outfits (`app/outfits/page.tsx`)
- Outfit cards labeled **"LOOK 01 / LOOK 02 …"** and revealed staggered. The
  click-to-open detail modal (already built) stays; add a smooth open/close.

## 5. Accessibility & performance
- Everything behind `prefers-reduced-motion: reduce` collapses to no/instant
  motion. Keyboard focus, alt text, and existing a11y preserved.
- Use transform/opacity (GPU-friendly); avoid layout thrash. Lazy/`whileInView`
  so off-screen work is deferred. Target smooth 60fps on the local stack.

## 6. Testing / verification
- `npm run lint` + `npm run build` green.
- Browser verification (agent-browser): runway hero renders and parallaxes;
  grid + sections reveal staggered; score badges count up; browse→build
  transition is smooth; save triggers the flash; reduced-motion path is static.
- No backend/pytest changes expected; the Python suite stays green.

## 7. Build phases
1. Motion setup + primitives (`motion` install, `<Reveal>`, `<CountUp>`,
   reduced-motion hook).
2. Runway hero (perspective catwalk + spotlights + parallax).
3. App-wide motion (grid stagger/hover, builder sections, count-up scores,
   tray animation, camera-flash save, "LOOK NN" + reveal on saved outfits,
   page transition browse→build).
4. Verify (lint/build + browser iteration), commit, push.
