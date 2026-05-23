# The Show — Theater Redesign

**Date:** 2026-05-23
**Status:** Approved (design)
**Area:** `web/` frontend only — no backend / model changes.

## Summary

Replace the current `/build/[itemId]` outfit-builder (cream "paper" theme, all
category rails visible at once) with an immersive **dark theater**: the whole
viewport blacks out, a spotlight lights a runway and a head-to-toe figure, and
the user assembles an outfit one slot at a time. The user picks which element
type to add next; the model offers **one** suggestion at a time which they
accept (✓) or reject (✗ → next-best). A shadowed audience **roars** on every
accept and whenever the user clicks them.

This is a UX + visual redesign of an existing, working flow. The data source
(the type-aware HGAT suggestions endpoint) is unchanged.

## Goals

- Turn outfit-building into a "fashion show" performance: dark room, spotlight,
  runway, reactive crowd.
- One element type at a time, chosen by the user in any order.
- One suggestion at a time per slot, with reject-to-cycle.
- Crowd reactions (visual + audio) on accept and on click.

## Non-goals / YAGNI

- No backend, API, or model changes (reuse `/items/{id}/outfit-suggestions`).
- No new persisted "show session" state, no multi-user, no drag-and-drop.
- No new suggestions endpoint or pagination — a deep pool fetched once suffices.
- Keep the existing save-outfit flow; only restyle it for the dark theater.

## Decisions (locked with the user)

1. **Scope:** the theater **replaces** the current build page. The left/right
   suggestion rails (`SuggestionRail`, `RailColumn`) are removed.
2. **Reject behavior:** **next-best, no repeats.** Rejecting advances a per-slot
   cursor down the model's ranked candidates; rejected items don't reappear this
   session. When a slot's pool is exhausted, show a quiet "no more pieces"
   state for that slot.
3. **Slot order:** **user picks the slot.** A slot dock lets the user tap
   Top / Bottom / Outerwear / Shoes / Bag / … in any order. No forced sequence,
   no auto-advance after accept — control returns to the user.
4. **Crowd sound:** **on by default.** Ambient runway pad + applause via the
   existing Web-Audio synth. Because browsers block autoplay, audio "arms" on
   the first user gesture, then plays. A prominent, always-visible mute toggle
   lets it be silenced instantly.

## Entry point (unchanged)

The user still picks a seed garment from the homepage catalog and navigates to
`/build/[itemId]` (the existing ViewTransition image morph is preserved). The
seed item is the first lit piece on the figure; the show begins from there.

## UX flow

1. **Blackout / house-lights-down:** on mount, cream fades to near-black, the
   site nav is covered, and a warm spotlight irises onto the runway. (Reduced
   motion: appears dark instantly, no animation.)
2. **Slot dock** (bottom): one button per compatible element type, derived from
   the suggestion response keys. Filled slots show ✓; empty slots invite a tap.
3. **Pick a slot →** the spotlight presents **one** candidate: image, title,
   compatibility score.
   - **✗ Reject:** card flips/slides to the next-best candidate (cursor++).
     Pool exhausted → "no more pieces for this slot."
   - **✓ Accept:** piece animates onto the figure, camera-flash sparkle, crowd
     roars; control returns to the dock with that slot now ✓.
   - Re-tapping a filled slot lets the user swap (re-enters that slot's cursor).
4. **Crowd:** roars on every accept; also clickable anytime to roar on demand.
5. **Save the Look:** name → save → camera flash → link to `/outfits`.
6. **Exit:** a discreet "← Leave the runway" control (top-left) returns to the
   normal (light) site; the `theater-dark` body class is removed on unmount.

## Architecture & components

New, under `web/components/show/`:

- **`TheShow.tsx`** — top-level client component (rendered by
  `app/build/[itemId]/page.tsx`). Owns all state via `useReducer`; orchestrates
  fetch, slot selection, accept/reject, crowd roar, and save.
- **`TheaterScene.tsx`** — the dark full-bleed scene: fixed `inset-0` black
  layer, spotlight cone (CSS radial/conic gradient + blur), vignette, runway
  perspective, exit + mute controls. Adds/removes the `theater-dark` class on
  `<body>` so site chrome behind it is black (no cream flashes during the page
  transition).
- **`SlotPicker.tsx`** — the slot dock; buttons per category with filled/empty
  state and the active highlight.
- **`SpotlightSuggestion.tsx`** — presents the single active candidate with
  Accept/Reject controls; handles the swap and "no more" states.
- **`SavePanel.tsx`** — extracted from the current `OutfitBuilder` and
  dark-themed (reused, not rewritten in logic).

Reused as-is (or with theme props): `StageFigure` (`categoryToSlot`,
`CENTER_SLOTS`, `StageFigureItem`), `Audience` (`onCheer`), `MusicToggle`,
`CameraFlash`, `Reveal`, `usePrefersReducedMotion`, `useShowAudio`.

Removed: `OutfitBuilder`'s rails (`SuggestionRail`, `RailColumn`) and the
3-column light layout. `OutfitBuilder.tsx` is either slimmed to a thin wrapper
or deleted in favor of `TheShow.tsx`.

## State model & data flow

Single `useReducer` in `TheShow`:

```
type State =
  | { status: "loading" }
  | { status: "error"; message: string }
  | {
      status: "loaded";
      seed: { item_id; title; semantic_category };
      slots: string[];                       // category keys, sorted by body order
      pools: Record<string, SuggestionItem[]>;  // ranked candidates per slot
      cursor: Record<string, number>;        // current candidate index per slot
      chosen: Record<string, string | null>; // accepted item id per slot
      activeSlot: string | null;             // slot currently in the spotlight
    }

Actions:
  FETCH_SUCCESS | FETCH_ERROR
  SET_ACTIVE_SLOT(slot)
  REJECT            // cursor[activeSlot]++
  ACCEPT            // chosen[activeSlot] = pools[activeSlot][cursor[activeSlot]].item_id; activeSlot = null
  UNCHOOSE(slot)    // optional: clear a slot
```

- **Fetch once:** `getOutfitSuggestions(itemId, /* perCategory */ 24)` on mount.
  24 ranked items/slot is plenty to cycle through; reuses the existing endpoint
  (`suggest_by_categories` already fetches `5*perCategory` ANN candidates).
- `slots` sorted via `categoryToSlot` / `CENTER_SLOTS` (head-to-toe order).
- Current candidate for a slot = `pools[slot][cursor[slot]]`; exhausted when
  `cursor[slot] >= pools[slot].length`.
- Figure items = seed + every `chosen` non-null, mapped to `StageFigureItem`.
- Selected ids for save = `[seed.item_id, ...Object.values(chosen).filter(Boolean)]`.

## Visual & motion design (Framer Motion; respects reduced-motion)

- Near-black base (`#0a0a0b`), warm gold spotlight cone from top-center; outside
  the cone falls to shadow + vignette. Light/gold typography (Cinzel marquee
  feel, EB Garamond body).
- **Enter:** cream→black fade, spotlight iris-in.
- **Reject:** current card slides/fades out, next slides in (flipping looks).
- **Accept:** piece drops onto the figure (layout animation) + camera flash +
  crowd roar.
- **Crowd roar:** audience figures jump/scale, brief light flare + sparkle burst.
- **Reduced motion:** every animation degrades to an instant state change; no
  flashes. Audio is independent of reduced-motion (gated only by the mute toggle).

## Audio

- Extend `useShowAudio`: default **ON** unless `localStorage` is explicitly
  `"off"` (currently defaults off). Add an `arm()`-style path so the ambient pad
  starts and cheers are allowed after the **first user gesture** (autoplay-safe;
  the hook already resumes a suspended `AudioContext` in `getCtx`).
- `playCheer()` already no-ops when sound is off — crowd visual still plays.
- `MusicToggle` stays prominently visible (recruiter-safe instant mute).

## Accessibility

- Slot/accept/reject are real `<button>`s with descriptive `aria-label`s
  ("Add a top", "Accept this top", "Show another top").
- `aria-live="polite"` region announces placements ("Added <title> to Top") and
  "no more pieces for this slot."
- Full `prefers-reduced-motion` path. WCAG-AA contrast for light/gold on black.
- Crowd-click is a decorative enhancement; accept already triggers the roar, so
  keyboard-only users are never blocked.
- Visible exit and mute controls at all times.

## Testing

- **Unit:** pure reducer tested — reject advances cursor, accept records the
  choice and clears active slot, no-repeats (cursor monotonic), pool exhaustion,
  swap of a filled slot. (Add a JS test runner config if none exists in `web/`;
  otherwise keep reducer logic in a pure module and test via a lightweight
  harness.)
- **Manual / live:** verify the full flow in the running app (blackout,
  spotlight, slot pick, reject-cycle, accept→roar, crowd-click→roar, save,
  reduced-motion, mute) on the local URL.
- **Build safety:** must remain freeze-safe — this is all client UI served via
  the production build (`scripts/demo_up.sh`); never demo via `next dev`.

## Files touched

- `web/app/build/[itemId]/page.tsx` — render `<TheShow>`.
- `web/components/show/{TheShow,TheaterScene,SlotPicker,SpotlightSuggestion,SavePanel}.tsx` — new.
- `web/components/OutfitBuilder.tsx` — removed/replaced; rails deleted.
- `web/components/audio/useShowAudio.ts` — default-on + arm-on-first-gesture.
- `web/app/globals.css` (or scene-local styles) — `theater-dark`, spotlight,
  vignette utilities.
- `web/components/StageFigure.tsx`, `Audience.tsx`, `MusicToggle.tsx` — minor
  theme props if needed for dark mode; logic unchanged.
