"use client";

import { useEffect, useReducer } from "react";
import Image from "next/image";
import { getOutfitSuggestions, imageUrl } from "@/lib/api";
import type { CatalogItem, OutfitSuggestionsResponse, SuggestionItem } from "@/lib/api";
import SuggestionCard from "@/components/SuggestionCard";
import OutfitTray from "@/components/OutfitTray";
import { Reveal, RevealGroup, RevealItem } from "@/components/motion/Reveal";

// ---------------------------------------------------------------------------
// State machine
// ---------------------------------------------------------------------------

type State =
  | { status: "loading" }
  | { status: "error"; message: string }
  | {
      status: "loaded";
      seed: CatalogItem;
      suggestions: Record<string, SuggestionItem[]>;
      // one selected item_id per category (or null)
      selected: Record<string, string | null>;
    };

type Action =
  | { type: "FETCH_SUCCESS"; data: OutfitSuggestionsResponse }
  | { type: "FETCH_ERROR"; message: string }
  | { type: "TOGGLE_SELECT"; category: string; itemId: string };

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
    case "TOGGLE_SELECT": {
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
// Seed item header
// ---------------------------------------------------------------------------

function SeedItem({ item }: { item: CatalogItem }) {
  const label = item.title || item.semantic_category || "Seed item";
  const catLabel = item.semantic_category
    ? item.semantic_category.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
    : null;
  // view-transition-name to morph from browse card
  const safeId = item.item_id.replace(/[^a-zA-Z0-9-_]/g, "_");

  return (
    <div className="flex items-center gap-4 rounded-sm bg-surface border border-rule p-4">
      <div className="relative h-20 w-20 flex-shrink-0 overflow-hidden rounded-sm bg-rule/30">
        <Image
          src={imageUrl(item.item_id)}
          alt={label}
          fill
          sizes="80px"
          className="object-cover"
          style={{ viewTransitionName: `catalog-img-${safeId}` }}
          unoptimized
        />
      </div>
      <div className="min-w-0">
        <span
          className="inline-block rounded-sm bg-ink/5 border border-rule px-2 py-0.5 text-[10px] uppercase tracking-[0.15em] text-ink-soft mb-2"
          style={{ fontFamily: "var(--font-body-var), serif" }}
        >
          Seed Item
        </span>
        <p
          className="font-medium text-ink truncate"
          style={{ fontFamily: "var(--font-body-var), serif" }}
        >
          {label}
        </p>
        {catLabel && (
          <p
            className="text-xs text-ink-soft uppercase tracking-[0.1em] mt-0.5"
            style={{ fontFamily: "var(--font-body-var), serif" }}
          >
            {catLabel}
          </p>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Category section header skeleton
// ---------------------------------------------------------------------------

function SectionSkeleton() {
  return (
    <div className="space-y-4">
      <div className="h-4 w-36 animate-pulse rounded-sm bg-rule/60" />
      <div className="hr-rule" />
      <div className="flex gap-3 overflow-x-auto pb-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <div
            key={i}
            className="flex-shrink-0 w-44 rounded-sm bg-surface border border-rule overflow-hidden"
          >
            <div className="aspect-square w-full animate-pulse bg-rule/50" />
            <div className="p-3 space-y-2">
              <div className="h-3 w-3/4 animate-pulse rounded-sm bg-rule/60" />
              <div className="h-3 w-1/2 animate-pulse rounded-sm bg-rule/60" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

interface OutfitBuilderProps {
  itemId: string;
}

export default function OutfitBuilder({ itemId }: OutfitBuilderProps) {
  const [state, dispatch] = useReducer(reducer, { status: "loading" });

  useEffect(() => {
    let cancelled = false;

    getOutfitSuggestions(itemId)
      .then((data) => {
        if (cancelled) return;
        dispatch({ type: "FETCH_SUCCESS", data });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        dispatch({
          type: "FETCH_ERROR",
          message:
            err instanceof Error ? err.message : "Failed to load suggestions.",
        });
      });

    return () => {
      cancelled = true;
    };
  }, [itemId]);

  if (state.status === "loading") {
    return (
      <main className="min-h-screen bg-transparent">
        <section
          aria-busy="true"
          aria-label="Loading outfit suggestions"
          className="mx-auto max-w-6xl px-6 pt-10 pb-16 space-y-8"
        >
          {/* Seed skeleton */}
          <div className="flex items-center gap-4 rounded-sm bg-surface border border-rule p-4">
            <div className="h-20 w-20 flex-shrink-0 animate-pulse rounded-sm bg-rule/50" />
            <div className="space-y-2 flex-1">
              <div className="h-3 w-20 animate-pulse rounded-sm bg-rule/60" />
              <div className="h-4 w-48 animate-pulse rounded-sm bg-rule/60" />
            </div>
          </div>
          {Array.from({ length: 3 }).map((_, i) => (
            <SectionSkeleton key={i} />
          ))}
        </section>
      </main>
    );
  }

  if (state.status === "error") {
    return (
      <main className="min-h-screen bg-transparent">
        <section className="mx-auto max-w-6xl px-6 pt-10 pb-16">
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
  const selectedIds = Object.values(selected).filter(
    (id): id is string => id !== null
  );

  if (categories.length === 0) {
    return (
      <main className="min-h-screen bg-transparent">
        <section className="mx-auto max-w-6xl px-6 pt-10 pb-16">
          <SeedItem item={seed} />
          <div className="mt-8 rounded-sm bg-surface border border-rule p-16 text-center">
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
      {/* Outfit tray — sticky on desktop, bottom bar on mobile */}
      <OutfitTray seedItem={seed} selectedIds={selectedIds} seedItemId={itemId} />

      <section className="mx-auto max-w-6xl px-6 pt-10 pb-32 space-y-10">
        {/* Page header */}
        <Reveal>
          <div>
            <div className="hr-rule mb-5" />
            <h1
              className="text-3xl font-semibold uppercase tracking-[0.12em] text-ink"
              style={{ fontFamily: "var(--font-display-var), serif" }}
            >
              Build Your Outfit
            </h1>
            <div className="hr-rule mt-4" />
            <p
              className="mt-3 text-base text-ink-soft"
              style={{ fontFamily: "var(--font-body-var), serif" }}
            >
              Select one piece per category to compose a complete look.
            </p>
          </div>
        </Reveal>

        {/* Seed item — morphs from browse card via view-transition-name */}
        <Reveal delay={0.1}>
          <SeedItem item={seed} />
        </Reveal>

        {/* Per-category suggestion sections — staggered reveal */}
        <RevealGroup stagger={0.12} className="space-y-10">
          {categories.map((cat) => {
            const items = suggestions[cat];
            const catLabel = cat
              .replace(/_/g, " ")
              .replace(/\b\w/g, (c) => c.toUpperCase());

            return (
              <RevealItem key={cat}>
                <div className="space-y-3">
                  {/* Section header with hairline rule */}
                  <div className="flex items-center gap-3">
                    <h2
                      className="text-sm font-semibold uppercase tracking-[0.14em] text-ink flex-shrink-0"
                      style={{ fontFamily: "var(--font-display-var), serif" }}
                    >
                      {catLabel}
                    </h2>
                    <div className="flex-1 h-px bg-rule" />
                    <span
                      className="text-[10px] uppercase tracking-[0.1em] text-ink-soft flex-shrink-0"
                      style={{ fontFamily: "var(--font-body-var), serif" }}
                    >
                      {items.length} option{items.length !== 1 ? "s" : ""}
                    </span>
                    {selected[cat] && (
                      <span
                        className="ml-1 rounded-sm bg-accent/10 border border-accent/30 px-2 py-0.5 text-[10px] uppercase tracking-[0.1em] text-accent-deep flex-shrink-0"
                        style={{ fontFamily: "var(--font-body-var), serif" }}
                      >
                        Selected
                      </span>
                    )}
                  </div>

                  {/* Horizontal scroll row — suggestion cards stagger within row */}
                  <RevealGroup stagger={0.055} className="flex gap-3 overflow-x-auto pb-2 snap-x">
                    {items.map((item) => (
                      <RevealItem
                        key={item.item_id}
                        className="flex-shrink-0 w-44 snap-start"
                      >
                        <SuggestionCard
                          item={item}
                          queryItemId={itemId}
                          selected={selected[cat] === item.item_id}
                          onToggleSelect={() =>
                            dispatch({
                              type: "TOGGLE_SELECT",
                              category: cat,
                              itemId: item.item_id,
                            })
                          }
                        />
                      </RevealItem>
                    ))}
                  </RevealGroup>
                </div>
              </RevealItem>
            );
          })}
        </RevealGroup>
      </section>
    </main>
  );
}
