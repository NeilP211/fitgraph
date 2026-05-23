# The Show — Theater Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the `/build/[itemId]` rails builder with an immersive dark theater where the user assembles an outfit one slot at a time — picking the slot, accepting/rejecting one suggestion at a time, with a crowd that roars on accept and on click.

**Architecture:** Frontend-only. A new `components/show/` tree renders a full-bleed dark scene over the site chrome. A pure `showReducer` owns state (per-slot ranked pools, cursors, chosen pieces, active slot). Data comes from the existing `getOutfitSuggestions(itemId, 24)` endpoint — fetched once, cycled client-side. Reuses `StageFigure`, `Audience`, `MusicToggle`, `CameraFlash`, `useShowAudio`.

**Tech Stack:** Next.js 16 (App Router), React 19, Framer Motion (`motion`), Tailwind v4, Web Audio (existing synth). Tests: vitest (added for the reducer).

**Spec:** `docs/superpowers/specs/2026-05-23-the-show-theater-redesign-design.md`

**Run/verify:** production build only (`scripts/demo_up.sh` → http://localhost:3012). Never `next dev` (freezes 16 GB Mac).

---

### Task 1: Audio — default ON + arm on first gesture

**Files:**
- Modify: `web/components/audio/useShowAudio.ts`

- [ ] **Step 1: Default to ON unless explicitly off**

In the `useState` initializer, change the default so sound is on unless the user previously turned it off:

```ts
const [soundOn, setSoundOn] = useState<boolean>(() => {
  if (typeof window === "undefined") return true;
  try {
    return localStorage.getItem(STORAGE_KEY) !== "off"; // default ON
  } catch {
    return true;
  }
});
```

- [ ] **Step 2: Add an `arm()` to start audio on first gesture (autoplay-safe)**

Add to the hook, and include in the returned object/interface:

```ts
const arm = useCallback(() => {
  if (!soundOnRef.current) return;
  getCtx();          // creates + resumes the AudioContext (needs a user gesture)
  startPad();        // idempotent
}, [getCtx, startPad]);
```

Add `arm: () => void;` to `ShowAudioState` and return `arm` alongside `soundOn, toggleMusic, playCheer`.

- [ ] **Step 3: Build to verify it compiles**

Run: `cd web && npm run build`
Expected: `✓ Compiled successfully`.

- [ ] **Step 4: Commit**

```bash
git add web/components/audio/useShowAudio.ts
git commit -m "feat(show): audio on by default + arm() on first gesture"
```

---

### Task 2: Pure show reducer + types (TDD)

**Files:**
- Create: `web/components/show/showReducer.ts`
- Create: `web/components/show/showReducer.test.ts`
- Modify: `web/package.json` (add vitest + `test` script)

- [ ] **Step 1: Add vitest**

```bash
cd web && npm install -D vitest@^2
```
Add to `package.json` scripts: `"test": "vitest run"`.

- [ ] **Step 2: Write the failing test**

`web/components/show/showReducer.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { reducer, initialLoaded, currentCandidate, type State } from "./showReducer";
import type { OutfitSuggestionsResponse } from "@/lib/api";

const resp: OutfitSuggestionsResponse = {
  seed: { item_id: "S", title: "Seed", semantic_category: "tops", image_path: null },
  suggestions: {
    bottoms: [
      { item_id: "b1", score: 0.9, title: "B1", semantic_category: "bottoms", image_path: null },
      { item_id: "b2", score: 0.8, title: "B2", semantic_category: "bottoms", image_path: null },
    ],
    shoes: [
      { item_id: "s1", score: 0.7, title: "S1", semantic_category: "shoes", image_path: null },
    ],
  },
};

function loaded(): State { return reducer({ status: "loading" }, { type: "FETCH_SUCCESS", data: resp }); }

describe("showReducer", () => {
  it("loads with cursors at 0, nothing chosen, no active slot", () => {
    const s = loaded();
    expect(s.status).toBe("loaded");
    if (s.status !== "loaded") return;
    expect(s.cursor).toEqual({ bottoms: 0, shoes: 0 });
    expect(s.chosen).toEqual({ bottoms: null, shoes: null });
    expect(s.activeSlot).toBeNull();
  });

  it("REJECT advances the cursor (next best, no repeat)", () => {
    let s = loaded();
    s = reducer(s, { type: "SET_ACTIVE_SLOT", slot: "bottoms" });
    expect(currentCandidate(s)?.item_id).toBe("b1");
    s = reducer(s, { type: "REJECT" });
    expect(currentCandidate(s)?.item_id).toBe("b2");
    s = reducer(s, { type: "REJECT" });
    expect(currentCandidate(s)).toBeNull(); // exhausted
  });

  it("ACCEPT records the choice and clears the active slot", () => {
    let s = loaded();
    s = reducer(s, { type: "SET_ACTIVE_SLOT", slot: "shoes" });
    s = reducer(s, { type: "ACCEPT" });
    if (s.status !== "loaded") throw new Error("expected loaded");
    expect(s.chosen.shoes).toBe("s1");
    expect(s.activeSlot).toBeNull();
  });

  it("UNCHOOSE clears a slot", () => {
    let s = loaded();
    s = reducer(s, { type: "SET_ACTIVE_SLOT", slot: "shoes" });
    s = reducer(s, { type: "ACCEPT" });
    s = reducer(s, { type: "UNCHOOSE", slot: "shoes" });
    if (s.status !== "loaded") throw new Error("expected loaded");
    expect(s.chosen.shoes).toBeNull();
  });
});
```

- [ ] **Step 3: Run to verify it fails**

Run: `cd web && npm test`
Expected: FAIL — cannot find `./showReducer`.

- [ ] **Step 4: Implement `showReducer.ts`**

```ts
import type { OutfitSuggestionsResponse, SuggestionItem } from "@/lib/api";
import { categoryToSlot, CENTER_SLOTS } from "@/components/StageFigure";

export type State =
  | { status: "loading" }
  | { status: "error"; message: string }
  | {
      status: "loaded";
      seed: { item_id: string; title: string | null; semantic_category: string | null };
      slots: string[];
      pools: Record<string, SuggestionItem[]>;
      cursor: Record<string, number>;
      chosen: Record<string, string | null>;
      activeSlot: string | null;
    };

export type Action =
  | { type: "FETCH_SUCCESS"; data: OutfitSuggestionsResponse }
  | { type: "FETCH_ERROR"; message: string }
  | { type: "SET_ACTIVE_SLOT"; slot: string | null }
  | { type: "REJECT" }
  | { type: "ACCEPT" }
  | { type: "UNCHOOSE"; slot: string };

function sortSlots(cats: string[]): string[] {
  const order = CENTER_SLOTS as readonly string[];
  return [...cats].sort((a, b) => {
    const ia = order.indexOf(categoryToSlot(a));
    const ib = order.indexOf(categoryToSlot(b));
    if (ia !== -1 && ib !== -1) return ia - ib;
    if (ia !== -1) return -1;
    if (ib !== -1) return 1;
    return 0;
  });
}

export function initialLoaded(data: OutfitSuggestionsResponse): State {
  const slots = sortSlots(Object.keys(data.suggestions));
  const cursor: Record<string, number> = {};
  const chosen: Record<string, string | null> = {};
  for (const s of slots) { cursor[s] = 0; chosen[s] = null; }
  return {
    status: "loaded",
    seed: data.seed,
    slots,
    pools: data.suggestions,
    cursor,
    chosen,
    activeSlot: null,
  };
}

/** The candidate currently in the spotlight for the active slot, or null. */
export function currentCandidate(state: State): SuggestionItem | null {
  if (state.status !== "loaded" || !state.activeSlot) return null;
  const pool = state.pools[state.activeSlot] ?? [];
  return pool[state.cursor[state.activeSlot]] ?? null;
}

export function reducer(state: State, action: Action): State {
  switch (action.type) {
    case "FETCH_SUCCESS":
      return initialLoaded(action.data);
    case "FETCH_ERROR":
      return { status: "error", message: action.message };
    case "SET_ACTIVE_SLOT":
      if (state.status !== "loaded") return state;
      return { ...state, activeSlot: action.slot };
    case "REJECT": {
      if (state.status !== "loaded" || !state.activeSlot) return state;
      const slot = state.activeSlot;
      return { ...state, cursor: { ...state.cursor, [slot]: state.cursor[slot] + 1 } };
    }
    case "ACCEPT": {
      if (state.status !== "loaded" || !state.activeSlot) return state;
      const cand = currentCandidate(state);
      if (!cand) return state;
      return {
        ...state,
        chosen: { ...state.chosen, [state.activeSlot]: cand.item_id },
        activeSlot: null,
      };
    }
    case "UNCHOOSE": {
      if (state.status !== "loaded") return state;
      return { ...state, chosen: { ...state.chosen, [action.slot]: null } };
    }
    default:
      return state;
  }
}
```

- [ ] **Step 5: Run to verify it passes**

Run: `cd web && npm test`
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add web/components/show/showReducer.ts web/components/show/showReducer.test.ts web/package.json web/package-lock.json
git commit -m "feat(show): pure showReducer with slot/cursor/chosen state + vitest"
```

---

### Task 3: Theater scene shell (blackout + spotlight + chrome)

**Files:**
- Create: `web/components/show/TheaterScene.tsx`
- Modify: `web/app/globals.css` (theater utilities)

- [ ] **Step 1: Add CSS utilities to `globals.css`**

```css
/* ── The Show: dark theater ── */
body.theater-dark { background: #0a0a0b; }
.theater-spotlight {
  background:
    radial-gradient(60% 55% at 50% 22%, rgba(212,175,110,0.22) 0%, rgba(212,175,110,0.06) 35%, transparent 70%),
    #0a0a0b;
}
.theater-vignette { box-shadow: inset 0 0 240px 80px rgba(0,0,0,0.9); }
```

- [ ] **Step 2: Implement `TheaterScene.tsx`**

```tsx
"use client";
import { useEffect, type ReactNode } from "react";
import Link from "next/link";
import MusicToggle from "@/components/audio/MusicToggle";

export default function TheaterScene({
  children, soundOn, onToggleSound,
}: { children: ReactNode; soundOn: boolean; onToggleSound: () => void }) {
  useEffect(() => {
    document.body.classList.add("theater-dark");
    return () => document.body.classList.remove("theater-dark");
  }, []);
  return (
    <div className="fixed inset-0 z-50 overflow-y-auto theater-spotlight text-[#f4ecd8]">
      <div className="theater-vignette pointer-events-none fixed inset-0 z-0" aria-hidden />
      <Link
        href="/"
        className="fixed left-4 top-4 z-20 text-[11px] uppercase tracking-[0.18em] text-[#f4ecd8]/70 hover:text-[#f4ecd8] transition-colors"
        style={{ fontFamily: "var(--font-display-var), serif" }}
      >← Leave the runway</Link>
      <div className="fixed right-4 top-4 z-20">
        <MusicToggle soundOn={soundOn} onToggle={onToggleSound} />
      </div>
      <div className="relative z-10 mx-auto max-w-3xl px-4 pt-16 pb-40 flex flex-col items-center">
        {children}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Build to verify it compiles**

Run: `cd web && npm run build` → `✓ Compiled successfully`.

- [ ] **Step 4: Commit**

```bash
git add web/components/show/TheaterScene.tsx web/app/globals.css
git commit -m "feat(show): dark theater scene shell — blackout, spotlight, exit/mute chrome"
```

---

### Task 4: SlotPicker dock

**Files:**
- Create: `web/components/show/SlotPicker.tsx`

- [ ] **Step 1: Implement `SlotPicker.tsx`**

```tsx
"use client";
import { motion } from "motion/react";

function label(cat: string) {
  return cat.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function SlotPicker({
  slots, chosen, activeSlot, onPick,
}: {
  slots: string[];
  chosen: Record<string, string | null>;
  activeSlot: string | null;
  onPick: (slot: string) => void;
}) {
  return (
    <div className="fixed inset-x-0 bottom-0 z-20 border-t border-[#f4ecd8]/15 bg-[#0a0a0b]/85 backdrop-blur-sm">
      <div className="mx-auto max-w-3xl px-4 py-3 flex flex-wrap items-center justify-center gap-2">
        {slots.map((slot) => {
          const filled = !!chosen[slot];
          const active = slot === activeSlot;
          return (
            <motion.button
              key={slot}
              whileTap={{ scale: 0.95 }}
              onClick={() => onPick(slot)}
              aria-label={filled ? `Swap ${label(slot)}` : `Add ${label(slot)}`}
              aria-pressed={active}
              className={[
                "rounded-full px-4 py-1.5 text-[11px] uppercase tracking-[0.14em] border transition-colors",
                active ? "border-[#d4af6e] text-[#d4af6e]"
                : filled ? "border-[#f4ecd8]/40 text-[#f4ecd8]/90"
                : "border-[#f4ecd8]/20 text-[#f4ecd8]/60 hover:text-[#f4ecd8]",
              ].join(" ")}
              style={{ fontFamily: "var(--font-display-var), serif" }}
            >
              {filled ? "✓ " : ""}{label(slot)}
            </motion.button>
          );
        })}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Build → commit**

```bash
cd web && npm run build && cd ..
git add web/components/show/SlotPicker.tsx
git commit -m "feat(show): slot picker dock"
```

---

### Task 5: SpotlightSuggestion (accept / reject / no-more)

**Files:**
- Create: `web/components/show/SpotlightSuggestion.tsx`

- [ ] **Step 1: Implement `SpotlightSuggestion.tsx`**

```tsx
"use client";
import Image from "next/image";
import { AnimatePresence, motion } from "motion/react";
import { imageUrl, type SuggestionItem } from "@/lib/api";

function label(cat: string) {
  return cat.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function SpotlightSuggestion({
  slot, candidate, exhausted, onAccept, onReject,
}: {
  slot: string;
  candidate: SuggestionItem | null;
  exhausted: boolean;
  onAccept: () => void;
  onReject: () => void;
}) {
  if (exhausted) {
    return (
      <p className="text-center text-sm text-[#f4ecd8]/60 py-10"
         style={{ fontFamily: "var(--font-body-var), serif" }}>
        No more {label(slot)} pieces — pick another slot.
      </p>
    );
  }
  if (!candidate) return null;
  return (
    <div className="flex flex-col items-center gap-4" aria-live="polite">
      <span className="text-[11px] uppercase tracking-[0.2em] text-[#d4af6e]"
            style={{ fontFamily: "var(--font-display-var), serif" }}>
        {label(slot)} · {Math.round(candidate.score * 100)}% match
      </span>
      <AnimatePresence mode="wait">
        <motion.div
          key={candidate.item_id}
          initial={{ opacity: 0, x: 40 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -40 }}
          transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
          className="relative w-56 aspect-square rounded-sm overflow-hidden border border-[#f4ecd8]/15 bg-black/40"
        >
          <Image src={imageUrl(candidate.item_id)} alt={candidate.title ?? "Suggested item"}
                 fill sizes="224px" className="object-cover" unoptimized />
        </motion.div>
      </AnimatePresence>
      <p className="text-center text-sm text-[#f4ecd8]/90 max-w-xs truncate"
         style={{ fontFamily: "var(--font-body-var), serif" }}>
        {candidate.title || "Untitled"}
      </p>
      <div className="flex items-center gap-4">
        <button onClick={onReject} aria-label={`Show another ${label(slot)}`}
                className="h-12 w-12 rounded-full border border-[#f4ecd8]/30 text-xl text-[#f4ecd8]/80 hover:border-[#f4ecd8] hover:text-[#f4ecd8] transition-colors">✗</button>
        <button onClick={onAccept} aria-label={`Accept this ${label(slot)}`}
                className="h-14 w-14 rounded-full bg-[#d4af6e] text-2xl text-[#0a0a0b] hover:bg-[#e6c486] transition-colors">✓</button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Build → commit**

```bash
cd web && npm run build && cd ..
git add web/components/show/SpotlightSuggestion.tsx
git commit -m "feat(show): single-suggestion spotlight with accept/reject/no-more"
```

---

### Task 6: Dark SavePanel (extract + restyle)

**Files:**
- Create: `web/components/show/SavePanel.tsx`

- [ ] **Step 1: Implement `SavePanel.tsx`**

Port the existing `SavePanel` + `CameraFlash` from `OutfitBuilder.tsx` (lines ~75-229) into this file, swapping the cream classes for theater equivalents: container `bg-black/40 border-[#f4ecd8]/15`, input `bg-black/30 border-[#f4ecd8]/20 text-[#f4ecd8]`, button `bg-[#d4af6e] text-[#0a0a0b] hover:bg-[#e6c486]`. Keep `DEMO_USER_ID = 1`, `saveOutfit`, `usePrefersReducedMotion`, and the success state linking to `/outfits`. Props: `{ seedItemId: string; selectedIds: string[]; savedName: string; setSavedName: (v: string) => void }`.

- [ ] **Step 2: Build → commit**

```bash
cd web && npm run build && cd ..
git add web/components/show/SavePanel.tsx
git commit -m "feat(show): dark-themed SavePanel for the theater"
```

---

### Task 7: TheShow — wire it all together

**Files:**
- Create: `web/components/show/TheShow.tsx`

- [ ] **Step 1: Implement `TheShow.tsx`**

Compose everything. Key wiring:

```tsx
"use client";
import { useEffect, useReducer } from "react";
import { getOutfitSuggestions } from "@/lib/api";
import { reducer, currentCandidate, type State } from "@/components/show/showReducer";
import TheaterScene from "@/components/show/TheaterScene";
import SlotPicker from "@/components/show/SlotPicker";
import SpotlightSuggestion from "@/components/show/SpotlightSuggestion";
import SavePanel from "@/components/show/SavePanel";
import StageFigure, { type StageFigureItem } from "@/components/StageFigure";
import Audience from "@/components/Audience";
import { useShowAudio } from "@/components/audio/useShowAudio";
import { useState } from "react";

export default function TheShow({ itemId }: { itemId: string }) {
  const [state, dispatch] = useReducer(reducer, { status: "loading" } as State);
  const { soundOn, toggleMusic, playCheer, arm } = useShowAudio();
  const [savedName, setSavedName] = useState("");

  useEffect(() => {
    let cancelled = false;
    getOutfitSuggestions(itemId, 24)
      .then((data) => { if (!cancelled) dispatch({ type: "FETCH_SUCCESS", data }); })
      .catch((e: unknown) => { if (!cancelled) dispatch({ type: "FETCH_ERROR", message: e instanceof Error ? e.message : "Failed to load." }); });
    return () => { cancelled = true; };
  }, [itemId]);

  // arm audio on first interaction
  const roar = () => { arm(); playCheer(); };

  if (state.status === "loading") return <TheaterScene soundOn={soundOn} onToggleSound={toggleMusic}><p className="text-[#f4ecd8]/60 pt-20">Setting the stage…</p></TheaterScene>;
  if (state.status === "error") return <TheaterScene soundOn={soundOn} onToggleSound={toggleMusic}><p role="alert" className="text-red-300 pt-20">{state.message}</p></TheaterScene>;

  const cand = currentCandidate(state);
  const exhausted = !!state.activeSlot && !cand;

  const figureItems: StageFigureItem[] = [
    { item_id: state.seed.item_id, title: state.seed.title, semantic_category: state.seed.semantic_category, isSeed: true },
    ...state.slots.flatMap((slot) => {
      const id = state.chosen[slot];
      if (!id) return [];
      const it = state.pools[slot].find((p) => p.item_id === id);
      return it ? [{ item_id: it.item_id, title: it.title, semantic_category: it.semantic_category }] : [];
    }),
  ];
  const selectedIds = state.slots.map((s) => state.chosen[s]).filter((x): x is string => !!x);

  const onAccept = () => { dispatch({ type: "ACCEPT" }); roar(); };

  return (
    <TheaterScene soundOn={soundOn} onToggleSound={() => { arm(); toggleMusic(); }}>
      <h1 className="text-2xl uppercase tracking-[0.2em] text-[#d4af6e] mb-2" style={{ fontFamily: "var(--font-display-var), serif" }}>The Show</h1>
      <StageFigure figureHeight={420} items={figureItems} />
      <div className="my-4"><Audience onCheer={roar} /></div>
      {state.activeSlot
        ? <SpotlightSuggestion slot={state.activeSlot} candidate={cand} exhausted={exhausted} onAccept={onAccept} onReject={() => dispatch({ type: "REJECT" })} />
        : <p className="text-sm text-[#f4ecd8]/60 py-6" style={{ fontFamily: "var(--font-body-var), serif" }}>Pick a piece below to add to the look.</p>}
      <div className="w-full max-w-sm mt-6">
        <SavePanel seedItemId={itemId} selectedIds={selectedIds} savedName={savedName} setSavedName={setSavedName} />
      </div>
      <SlotPicker slots={state.slots} chosen={state.chosen} activeSlot={state.activeSlot} onPick={(slot) => { arm(); dispatch({ type: "SET_ACTIVE_SLOT", slot }); }} />
    </TheaterScene>
  );
}
```

- [ ] **Step 2: Build → commit**

```bash
cd web && npm run build && cd ..
git add web/components/show/TheShow.tsx
git commit -m "feat(show): wire TheShow — scene + figure + crowd + slot picker + suggestion + save"
```

---

### Task 8: Point the route at TheShow; remove the rails

**Files:**
- Modify: `web/app/build/[itemId]/page.tsx`
- Delete: `web/components/OutfitBuilder.tsx`

- [ ] **Step 1: Update the route**

```tsx
"use client";
import { use } from "react";
import TheShow from "@/components/show/TheShow";

export default function BuildPage({ params }: { params: Promise<{ itemId: string }> }) {
  const { itemId } = use(params);
  return <TheShow itemId={decodeURIComponent(itemId)} />;
}
```

- [ ] **Step 2: Delete the old builder + check for stragglers**

```bash
cd web && rm components/OutfitBuilder.tsx
grep -rn "OutfitBuilder\|SuggestionRail\|RailColumn" app components || echo "no references"
```
If `SuggestionCard`/`OutfitTray`/`BrowseGrid` are now unreferenced by the build route but still used elsewhere (homepage browse), leave them. Only remove what's truly orphaned.

- [ ] **Step 3: Build + lint + reducer test**

```bash
cd web && npm run build && npm run lint && npm test
```
Expected: build ✓, lint clean, 4 tests pass.

- [ ] **Step 4: Commit**

```bash
git add web/app/build/[itemId]/page.tsx web/components/OutfitBuilder.tsx
git commit -m "feat(show): /build now renders the theater; remove rails builder"
```

---

### Task 9: Live verification + push

- [ ] **Step 1: Bring up the prod stack**

```bash
cd ~/projects/fitgraph && scripts/demo_up.sh
```

- [ ] **Step 2: Verify the flow** (browser at http://localhost:3012 → pick a catalog item → `/build/...`)

Check: blackout + spotlight; site nav covered; slot dock; pick slot → one suggestion; ✗ cycles to next-best; pool exhaustion message; ✓ places piece on figure + crowd roars; click crowd → roars; sound on by default (mute works); save the look → flash → /outfits; "← Leave the runway" exits to the light site; toggle OS reduced-motion → no animation, still usable.

- [ ] **Step 3: Confirm freeze-safety**

Memory stayed flat during load (it will — prod build). `sysctl -n kern.memorystatus_vm_pressure_level` → 1.

- [ ] **Step 4: Push**

```bash
git push origin main
```

- [ ] **Step 5: Update FitGraph memory** with the redesign outcome.

---

## Self-Review

**Spec coverage:** blackout/spotlight (T3) ✓; user-picks-slot dock (T4) ✓; one-suggestion + reject-next-best + no-more (T2 reducer, T5 UI) ✓; crowd roar on accept + click (T7) ✓; sound on by default + arm (T1) ✓; save flow (T6) ✓; replace rails (T8) ✓; reduced-motion + a11y (T3/T5/T9) ✓; testing (T2 reducer + T9 live) ✓; freeze-safety (T9) ✓.

**Placeholder scan:** Task 6 references the existing `SavePanel`/`CameraFlash` source by line range rather than repeating it — acceptable since it's a port of in-repo code, not a new invention; classes to change are listed explicitly.

**Type consistency:** `reducer`, `currentCandidate`, `State`, `Action`, action tags (`FETCH_SUCCESS`, `SET_ACTIVE_SLOT`, `REJECT`, `ACCEPT`, `UNCHOOSE`), and `arm()` are used identically across Tasks 1, 2, 5, 7. `StageFigureItem`, `categoryToSlot`, `CENTER_SLOTS`, `imageUrl`, `getOutfitSuggestions(itemId, 24)` match existing exports.
