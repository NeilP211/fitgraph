"use client";

import { useEffect, useReducer } from "react";
import Image from "next/image";
import { getOutfitSuggestions, imageUrl } from "@/lib/api";
import type { CatalogItem, OutfitSuggestionsResponse, SuggestionItem } from "@/lib/api";
import SuggestionCard from "@/components/SuggestionCard";
import OutfitTray from "@/components/OutfitTray";

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

  return (
    <div className="flex items-center gap-4 rounded-2xl bg-white border border-stone-200 shadow-sm p-4">
      <div className="relative h-20 w-20 flex-shrink-0 overflow-hidden rounded-xl bg-stone-100">
        <Image
          src={imageUrl(item.item_id)}
          alt={label}
          fill
          sizes="80px"
          className="object-cover"
          unoptimized
        />
      </div>
      <div className="min-w-0">
        <span className="inline-block rounded-full bg-stone-900/5 px-2 py-0.5 text-xs font-medium uppercase tracking-widest text-stone-500 mb-1">
          Seed item
        </span>
        <p className="font-semibold text-stone-900 truncate">{label}</p>
        {catLabel && (
          <p className="text-xs text-stone-400 capitalize mt-0.5">{catLabel}</p>
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
      <div className="h-5 w-32 animate-pulse rounded bg-stone-200" />
      <div className="flex gap-3 overflow-x-auto pb-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <div
            key={i}
            className="flex-shrink-0 w-44 rounded-2xl bg-white border border-stone-200 overflow-hidden"
          >
            <div className="aspect-square w-full animate-pulse bg-stone-200" />
            <div className="p-4 space-y-2">
              <div className="h-3 w-3/4 animate-pulse rounded bg-stone-200" />
              <div className="h-3 w-1/2 animate-pulse rounded bg-stone-200" />
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
      <main className="min-h-screen bg-stone-50">
        <section
          aria-busy="true"
          aria-label="Loading outfit suggestions"
          className="mx-auto max-w-6xl px-6 pt-10 pb-16 space-y-8"
        >
          {/* Seed skeleton */}
          <div className="flex items-center gap-4 rounded-2xl bg-white border border-stone-200 p-4">
            <div className="h-20 w-20 flex-shrink-0 animate-pulse rounded-xl bg-stone-200" />
            <div className="space-y-2 flex-1">
              <div className="h-3 w-20 animate-pulse rounded bg-stone-200" />
              <div className="h-4 w-48 animate-pulse rounded bg-stone-200" />
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
      <main className="min-h-screen bg-stone-50">
        <section className="mx-auto max-w-6xl px-6 pt-10 pb-16">
          <div
            role="alert"
            className="rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700"
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
      <main className="min-h-screen bg-stone-50">
        <section className="mx-auto max-w-6xl px-6 pt-10 pb-16">
          <SeedItem item={seed} />
          <div className="mt-8 rounded-2xl bg-white border border-stone-200 p-16 text-center">
            <p className="text-4xl mb-3">&#128268;</p>
            <p className="font-medium text-stone-700">No suggestions found</p>
            <p className="mt-1 text-sm text-stone-400">
              This item has no compatible pieces in other categories.
            </p>
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-stone-50">
      {/* Outfit tray — sticky on desktop, bottom bar on mobile */}
      <OutfitTray seedItem={seed} selectedIds={selectedIds} seedItemId={itemId} />

      <section className="mx-auto max-w-6xl px-6 pt-10 pb-32 space-y-10">
        {/* Page header */}
        <div>
          <span className="inline-block rounded-full bg-stone-900/5 px-3 py-1 text-xs font-medium uppercase tracking-widest text-stone-500 mb-3">
            Outfit builder
          </span>
          <h1 className="text-2xl font-bold text-stone-900 tracking-tight">
            Build your outfit
          </h1>
          <p className="mt-1 text-sm text-stone-500">
            Pick one item per category to build a complete look.
          </p>
        </div>

        {/* Seed item */}
        <SeedItem item={seed} />

        {/* Per-category suggestion sections */}
        {categories.map((cat) => {
          const items = suggestions[cat];
          const catLabel = cat
            .replace(/_/g, " ")
            .replace(/\b\w/g, (c) => c.toUpperCase());

          return (
            <div key={cat} className="space-y-3">
              <div className="flex items-center gap-3">
                <h2 className="text-base font-semibold text-stone-900">
                  {catLabel}
                </h2>
                <span className="text-xs text-stone-400">
                  {items.length} option{items.length !== 1 ? "s" : ""}
                </span>
                {selected[cat] && (
                  <span className="ml-auto rounded-full bg-emerald-50 border border-emerald-200 px-2.5 py-0.5 text-xs font-medium text-emerald-700">
                    1 selected
                  </span>
                )}
              </div>

              {/* Horizontal scroll row of suggestion cards */}
              <div className="flex gap-3 overflow-x-auto pb-2 snap-x">
                {items.map((item) => (
                  <div
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
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </section>
    </main>
  );
}
