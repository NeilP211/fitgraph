"use client";

import { useEffect, useReducer, useState } from "react";
import Link from "next/link";
import { motion } from "motion/react";
import { getOutfitSuggestions, saveOutfit } from "@/lib/api";
import type { OutfitSuggestionsResponse, SuggestionItem } from "@/lib/api";
import SuggestionCard from "@/components/SuggestionCard";
import StageFigure, { categoryToSlot, CENTER_SLOTS } from "@/components/StageFigure";
import type { StageFigureItem } from "@/components/StageFigure";
import { Reveal } from "@/components/motion/Reveal";
import { usePrefersReducedMotion } from "@/components/motion/usePrefersReducedMotion";

const DEMO_USER_ID = 1;

// ---------------------------------------------------------------------------
// State machine
// ---------------------------------------------------------------------------

type State =
  | { status: "loading" }
  | { status: "error"; message: string }
  | {
      status: "loaded";
      seed: { item_id: string; title: string | null; semantic_category: string | null };
      suggestions: Record<string, SuggestionItem[]>;
      selected: Record<string, string | null>;
    };

type Action =
  | { type: "FETCH_SUCCESS"; data: OutfitSuggestionsResponse }
  | { type: "FETCH_ERROR"; message: string }
  | { type: "SELECT"; category: string; itemId: string | null };

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case "FETCH_SUCCESS": {
      const selected: Record<string, string | null> = {};
      for (const cat of Object.keys(action.data.suggestions)) {
        selected[cat] = null;
      }
      return {
        status: "loaded",
        seed: action.data.seed,
        suggestions: action.data.suggestions,
        selected,
      };
    }
    case "FETCH_ERROR":
      return { status: "error", message: action.message };
    case "SELECT": {
      if (state.status !== "loaded") return state;
      const current = state.selected[action.category];
      return {
        ...state,
        selected: {
          ...state.selected,
          [action.category]:
            current === action.itemId ? null : action.itemId,
        },
      };
    }
    default:
      return state;
  }
}

// ---------------------------------------------------------------------------
// Camera flash (reused from old OutfitTray)
// ---------------------------------------------------------------------------

function CameraFlash({ onDone }: { onDone: () => void }) {
  return (
    <>
      <div
        className="camera-flash fixed inset-0 z-[60] pointer-events-none bg-paper"
        onAnimationEnd={onDone}
        aria-hidden="true"
      />
      <div
        className="fixed inset-0 z-[61] pointer-events-none flex items-center justify-center"
        aria-hidden="true"
      >
        <motion.div
          initial={{ scale: 0.5, opacity: 0 }}
          animate={{ scale: 1.5, opacity: [0, 1, 0] }}
          transition={{ duration: 0.3, ease: "easeOut" }}
          className="text-4xl select-none"
          style={{ filter: "drop-shadow(0 0 8px var(--gold))" }}
        >
          ✦
        </motion.div>
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// Save panel — folded into the stage
// ---------------------------------------------------------------------------

interface SavePanelProps {
  seedItemId: string;
  selectedIds: string[];
  savedName: string;
  setSavedName: (v: string) => void;
}

function SavePanel({ seedItemId, selectedIds, savedName, setSavedName }: SavePanelProps) {
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedId, setSavedId] = useState<number | null>(null);
  const [showFlash, setShowFlash] = useState(false);
  const reduced = usePrefersReducedMotion();

  const allIds = [seedItemId, ...selectedIds];
  const pieceCount = allIds.length;

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || saving) return;
    setSaving(true);
    setError(null);
    try {
      const outfit = await saveOutfit({
        user_id: DEMO_USER_ID,
        name: name.trim(),
        item_ids: allIds,
      });
      setSavedName(name.trim());
      if (!reduced) {
        setShowFlash(true);
        setTimeout(() => {
          setSavedId(outfit.outfit_id);
          setShowFlash(false);
        }, 320);
      } else {
        setSavedId(outfit.outfit_id);
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to save outfit."
      );
    } finally {
      setSaving(false);
    }
  };

  if (savedId !== null) {
    return (
      <motion.div
        initial={reduced ? false : { opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="flex items-center justify-between gap-4 rounded-sm bg-surface border border-rule px-5 py-3"
      >
        <div className="flex items-center gap-3">
          <span className="flex h-7 w-7 items-center justify-center rounded-sm bg-accent/10 border border-accent/30 text-accent text-sm font-bold">
            ✓
          </span>
          <div>
            <p
              className="text-sm font-medium text-ink"
              style={{ fontFamily: "var(--font-body-var), serif" }}
            >
              Look saved — &ldquo;{savedName}&rdquo;
            </p>
            <p
              className="text-xs text-ink-soft"
              style={{ fontFamily: "var(--font-body-var), serif" }}
            >
              {pieceCount} piece{pieceCount !== 1 ? "s" : ""}
            </p>
          </div>
        </div>
        <Link
          href="/outfits"
          className="rounded-sm bg-accent px-4 py-1.5 text-xs uppercase tracking-[0.12em] text-paper hover:bg-accent-deep transition-colors"
          style={{ fontFamily: "var(--font-body-var), serif" }}
        >
          View Outfits
        </Link>
      </motion.div>
    );
  }

  return (
    <>
      {showFlash && <CameraFlash onDone={() => {}} />}
      <form
        onSubmit={handleSave}
        className="flex items-center gap-3 flex-wrap"
      >
        <div className="flex flex-col gap-1 flex-1 min-w-0">
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Name this look…"
            aria-label="Outfit name"
            className="rounded-sm border border-rule bg-paper px-3 py-2 text-sm text-ink placeholder:text-ink-soft/70 focus:outline-none focus:border-ink-soft focus:ring-1 focus:ring-rule w-full"
            style={{ fontFamily: "var(--font-body-var), serif" }}
          />
          {error && (
            <p
              role="alert"
              className="text-xs text-accent-deep"
              style={{ fontFamily: "var(--font-body-var), serif" }}
            >
              {error}
            </p>
          )}
        </div>
        <button
          type="submit"
          disabled={!name.trim() || saving || selectedIds.length === 0}
          className="rounded-sm bg-accent px-5 py-2 text-xs uppercase tracking-[0.12em] text-paper hover:bg-accent-deep disabled:opacity-50 disabled:cursor-not-allowed transition-colors whitespace-nowrap flex-shrink-0"
          style={{ fontFamily: "var(--font-body-var), serif" }}
        >
          {saving ? "Saving…" : "Save the Look"}
        </button>
      </form>
    </>
  );
}

// ---------------------------------------------------------------------------
// Suggestion rail for a single category
// ---------------------------------------------------------------------------

interface RailProps {
  category: string;
  items: SuggestionItem[];
  selectedId: string | null;
  seedItemId: string;
  onSelect: (itemId: string | null) => void;
  isActiveCategory: boolean;
}

function SuggestionRail({
  category,
  items,
  selectedId,
  seedItemId,
  onSelect,
  isActiveCategory,
}: RailProps) {
  const catLabel = category
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());

  return (
    <div className="space-y-2">
      {/* Rail header */}
      <div className="flex items-center gap-2 px-1">
        <h3
          className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink flex-shrink-0"
          style={{ fontFamily: "var(--font-display-var), serif" }}
        >
          {catLabel}
        </h3>
        <div className="flex-1 h-px bg-rule" />
        {selectedId && (
          <span
            className="rounded-sm bg-accent/10 border border-accent/30 px-1.5 py-0.5 text-[9px] uppercase tracking-[0.1em] text-accent-deep flex-shrink-0"
            style={{ fontFamily: "var(--font-body-var), serif" }}
          >
            ✓ Selected
          </span>
        )}
        {isActiveCategory && !selectedId && (
          <span
            className="rounded-sm bg-gold/10 border border-gold/30 px-1.5 py-0.5 text-[9px] uppercase tracking-[0.1em] text-gold flex-shrink-0"
            style={{ fontFamily: "var(--font-body-var), serif" }}
          >
            Seed
          </span>
        )}
      </div>

      {/* Horizontal scrollable card row */}
      <div
        className="flex gap-3 overflow-x-auto pb-2 snap-x"
        style={{ scrollbarWidth: "none" }}
        aria-label={`${catLabel} suggestions`}
      >
        {items.map((item) => (
          <div key={item.item_id} className="flex-shrink-0 w-40 snap-start">
            <SuggestionCard
              item={item}
              queryItemId={seedItemId}
              selected={selectedId === item.item_id}
              onToggleSelect={() =>
                onSelect(selectedId === item.item_id ? null : item.item_id)
              }
            />
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// RailColumn — renders a list of suggestion rails
// (defined outside OutfitBuilder to avoid "component created during render")
// ---------------------------------------------------------------------------

interface RailColumnProps {
  cats: string[];
  suggestions: Record<string, SuggestionItem[]>;
  selected: Record<string, string | null>;
  seedItemId: string;
  seedSlot: string;
  onSelect: (category: string, itemId: string | null) => void;
}

function RailColumn({
  cats,
  suggestions,
  selected,
  seedItemId,
  seedSlot,
  onSelect,
}: RailColumnProps) {
  return (
    <div className="flex flex-col gap-6 min-w-0">
      {cats.map((cat) => (
        <SuggestionRail
          key={cat}
          category={cat}
          items={suggestions[cat]}
          selectedId={selected[cat] ?? null}
          seedItemId={seedItemId}
          isActiveCategory={categoryToSlot(cat) === seedSlot}
          onSelect={(selId) => onSelect(cat, selId)}
        />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Loading skeleton
// ---------------------------------------------------------------------------

function LoadingSkeleton() {
  return (
    <main className="min-h-screen bg-transparent">
      <section
        aria-busy="true"
        aria-label="Loading outfit suggestions"
        className="mx-auto max-w-7xl px-4 pt-8 pb-16"
      >
        {/* Page header skeleton */}
        <div className="mb-8 space-y-3">
          <div className="hr-rule" />
          <div className="h-8 w-64 animate-pulse rounded-sm bg-rule/60 mx-auto" />
          <div className="hr-rule" />
        </div>

        {/* Stage + rails skeleton */}
        <div className="flex flex-col lg:flex-row gap-6">
          {/* Left rails skeleton */}
          <div className="hidden lg:flex flex-col gap-6 w-[340px] flex-shrink-0">
            {[1, 2].map((i) => (
              <div key={i} className="space-y-2">
                <div className="h-3 w-24 animate-pulse rounded-sm bg-rule/60" />
                <div className="flex gap-3">
                  {[1, 2, 3].map((j) => (
                    <div key={j} className="w-40 flex-shrink-0 rounded-sm bg-surface border border-rule overflow-hidden">
                      <div className="aspect-square animate-pulse bg-rule/40" />
                      <div className="p-3 space-y-1.5">
                        <div className="h-3 w-3/4 animate-pulse rounded-sm bg-rule/50" />
                        <div className="h-2 w-1/2 animate-pulse rounded-sm bg-rule/40" />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>

          {/* Center stage skeleton */}
          <div className="flex-shrink-0 mx-auto" style={{ width: 260 }}>
            <div className="mx-auto animate-pulse bg-rule/20 rounded-sm" style={{ width: 220, height: 480 }} />
          </div>

          {/* Right rails skeleton */}
          <div className="hidden lg:flex flex-col gap-6 w-[340px] flex-shrink-0">
            {[1, 2].map((i) => (
              <div key={i} className="space-y-2">
                <div className="h-3 w-24 animate-pulse rounded-sm bg-rule/60" />
                <div className="flex gap-3">
                  {[1, 2, 3].map((j) => (
                    <div key={j} className="w-40 flex-shrink-0 rounded-sm bg-surface border border-rule overflow-hidden">
                      <div className="aspect-square animate-pulse bg-rule/40" />
                      <div className="p-3 space-y-1.5">
                        <div className="h-3 w-3/4 animate-pulse rounded-sm bg-rule/50" />
                        <div className="h-2 w-1/2 animate-pulse rounded-sm bg-rule/40" />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}

// ---------------------------------------------------------------------------
// Main OutfitBuilder component
// ---------------------------------------------------------------------------

interface OutfitBuilderProps {
  itemId: string;
}

export default function OutfitBuilder({ itemId }: OutfitBuilderProps) {
  const [state, dispatch] = useReducer(reducer, { status: "loading" });
  const [savedName, setSavedName] = useState("");

  useEffect(() => {
    let cancelled = false;
    getOutfitSuggestions(itemId)
      .then((data) => {
        if (!cancelled) dispatch({ type: "FETCH_SUCCESS", data });
      })
      .catch((err: unknown) => {
        if (!cancelled)
          dispatch({
            type: "FETCH_ERROR",
            message:
              err instanceof Error ? err.message : "Failed to load suggestions.",
          });
      });
    return () => { cancelled = true; };
  }, [itemId]);

  if (state.status === "loading") return <LoadingSkeleton />;

  if (state.status === "error") {
    return (
      <main className="min-h-screen bg-transparent">
        <section className="mx-auto max-w-7xl px-4 pt-8 pb-16">
          <div
            role="alert"
            className="rounded-sm bg-surface border border-rule px-4 py-3 text-sm text-accent-deep"
            style={{ fontFamily: "var(--font-body-var), serif" }}
          >
            <strong>Error:</strong> {state.message}
          </div>
        </section>
      </main>
    );
  }

  const { seed, suggestions, selected } = state;
  const categories = Object.keys(suggestions);

  // Seed item slot
  const seedSlot = categoryToSlot(seed.semantic_category);

  // Build the list of items currently placed on the stage
  const stageFigureItems: StageFigureItem[] = [
    {
      item_id: seed.item_id,
      title: seed.title,
      semantic_category: seed.semantic_category,
      isSeed: true,
    },
  ];

  for (const [cat, selId] of Object.entries(selected)) {
    if (!selId) continue;
    const item = suggestions[cat]?.find((i) => i.item_id === selId);
    if (item) {
      stageFigureItems.push({
        item_id: item.item_id,
        title: item.title,
        semantic_category: item.semantic_category,
      });
    }
  }

  const selectedIds = Object.values(selected).filter(
    (id): id is string => id !== null
  );

  // Sort categories: center slots first (in body order), then side slots
  const sortedCategories = [...categories].sort((a, b) => {
    const slotA = categoryToSlot(a);
    const slotB = categoryToSlot(b);
    const centerOrder = CENTER_SLOTS as readonly string[];
    const ia = centerOrder.indexOf(slotA);
    const ib = centerOrder.indexOf(slotB);
    if (ia !== -1 && ib !== -1) return ia - ib;
    if (ia !== -1) return -1;
    if (ib !== -1) return 1;
    return 0;
  });

  // Partition into columns for desktop
  const half = Math.ceil(sortedCategories.length / 2);
  const leftCats = sortedCategories.slice(0, half);
  const rightCats = sortedCategories.slice(half);

  const handleSelect = (category: string, itemId: string | null) => {
    dispatch({ type: "SELECT", category, itemId });
  };

  if (categories.length === 0) {
    return (
      <main className="min-h-screen bg-transparent">
        <section className="mx-auto max-w-7xl px-4 pt-8 pb-16 space-y-8">
          <Reveal>
            <div>
              <div className="hr-rule mb-4" />
              <h1
                className="text-center text-2xl font-semibold uppercase tracking-[0.12em] text-ink"
                style={{ fontFamily: "var(--font-display-var), serif" }}
              >
                The Show
              </h1>
              <div className="hr-rule mt-4" />
            </div>
          </Reveal>
          <div className="rounded-sm bg-surface border border-rule p-16 text-center">
            <p
              className="text-base uppercase tracking-[0.15em] text-ink-soft mb-2"
              style={{ fontFamily: "var(--font-display-var), serif" }}
            >
              No Suggestions Found
            </p>
            <p
              className="text-sm text-ink-soft"
              style={{ fontFamily: "var(--font-body-var), serif" }}
            >
              This item has no compatible pieces in other categories.
            </p>
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-transparent">
      <section className="mx-auto max-w-7xl px-4 pt-8 pb-16 space-y-6">

        {/* ── Page header ── */}
        <Reveal>
          <div>
            <div className="hr-rule mb-4" />
            <h1
              className="text-center text-3xl font-semibold uppercase tracking-[0.12em] text-ink"
              style={{ fontFamily: "var(--font-display-var), serif" }}
            >
              The Show
            </h1>
            <div className="hr-rule mt-3" />
            <p
              className="mt-2 text-center text-sm text-ink-soft"
              style={{ fontFamily: "var(--font-body-var), serif" }}
            >
              Select one piece per category — watch the look come together
            </p>
          </div>
        </Reveal>

        {/* ── Stage + rails (3-column on desktop) ── */}
        <div className="flex flex-col lg:flex-row gap-6 lg:gap-8 lg:items-start">

          {/* Left suggestion rails */}
          <div className="hidden lg:block w-[340px] flex-shrink-0">
            <RailColumn
              cats={leftCats}
              suggestions={suggestions}
              selected={selected}
              seedItemId={itemId}
              seedSlot={seedSlot}
              onSelect={handleSelect}
            />
          </div>

          {/* ══ CENTER STAGE ══ */}
          <div className="flex-shrink-0 lg:flex-1 flex flex-col items-center gap-4">
            {/* Runway strip */}
            <div
              className="relative w-full max-w-sm flex flex-col items-center rounded-sm overflow-hidden"
              style={{
                background: "linear-gradient(to bottom, var(--paper) 0%, var(--surface) 60%, color-mix(in srgb, var(--rule) 20%, transparent) 100%)",
                border: "1px solid var(--rule)",
                boxShadow: "0 2px 24px 0 rgba(34,28,19,0.08)",
              }}
              aria-label="Runway stage"
            >
              {/* Stage label */}
              <div
                className="w-full text-center py-2 border-b border-rule"
                style={{ background: "var(--surface)" }}
              >
                <span
                  className="text-[10px] uppercase tracking-[0.2em] text-ink-soft"
                  style={{ fontFamily: "var(--font-display-var), serif" }}
                >
                  ✦ Center Stage ✦
                </span>
              </div>

              {/* Runway perspective lines */}
              <div className="absolute inset-x-0 top-10 bottom-0 pointer-events-none overflow-hidden" aria-hidden="true">
                <svg
                  viewBox="0 0 320 480"
                  preserveAspectRatio="none"
                  className="absolute inset-0 w-full h-full"
                  xmlns="http://www.w3.org/2000/svg"
                  style={{ opacity: 0.05 }}
                >
                  {/* Runway center lane */}
                  <path d="M120 0 L80 480 L240 480 L200 0 Z" fill="currentColor" />
                  {/* Left edge line */}
                  <line x1="120" y1="0" x2="80" y2="480" stroke="currentColor" strokeWidth="1" />
                  {/* Right edge line */}
                  <line x1="200" y1="0" x2="240" y2="480" stroke="currentColor" strokeWidth="1" />
                </svg>
              </div>

              {/* StageFigure */}
              <div className="relative w-full px-4 py-6" style={{ zIndex: 2 }}>
                <StageFigure
                  figureHeight={480}
                  items={stageFigureItems}
                />
              </div>

              {/* Piece count status bar */}
              <div
                className="w-full border-t border-rule px-4 py-2 text-center"
                style={{ background: "var(--surface)" }}
                aria-live="polite"
                aria-atomic="true"
              >
                <span
                  className="text-[10px] uppercase tracking-[0.12em] text-ink-soft"
                  style={{ fontFamily: "var(--font-body-var), serif" }}
                >
                  {selectedIds.length === 0
                    ? "Select pieces from the rails to build your look"
                    : `${selectedIds.length + 1} piece${selectedIds.length + 1 !== 1 ? "s" : ""} — tap to swap`}
                </span>
              </div>
            </div>

            {/* Save panel */}
            <div className="w-full max-w-sm">
              <div className="hr-rule mb-3" />
              <SavePanel
                seedItemId={itemId}
                selectedIds={selectedIds}
                savedName={savedName}
                setSavedName={setSavedName}
              />
            </div>
          </div>

          {/* Right suggestion rails */}
          <div className="hidden lg:block w-[340px] flex-shrink-0">
            <RailColumn
              cats={rightCats}
              suggestions={suggestions}
              selected={selected}
              seedItemId={itemId}
              seedSlot={seedSlot}
              onSelect={handleSelect}
            />
          </div>
        </div>

        {/* ── Mobile/tablet: rails stacked below the stage ── */}
        <div className="lg:hidden space-y-8">
          <div className="hr-rule" />
          <h2
            className="text-sm font-semibold uppercase tracking-[0.14em] text-ink text-center"
            style={{ fontFamily: "var(--font-display-var), serif" }}
          >
            Suggestion Rails
          </h2>
          <div className="space-y-8">
            {sortedCategories.map((cat) => (
              <SuggestionRail
                key={cat}
                category={cat}
                items={suggestions[cat]}
                selectedId={selected[cat] ?? null}
                seedItemId={itemId}
                isActiveCategory={categoryToSlot(cat) === seedSlot}
                onSelect={(selId) => handleSelect(cat, selId)}
              />
            ))}
          </div>
        </div>

      </section>
    </main>
  );
}
