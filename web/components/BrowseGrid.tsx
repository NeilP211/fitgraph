"use client";

import { useEffect, useReducer, useRef, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { getCatalogItems, getCatalogFacets, imageUrl } from "@/lib/api";
import type { CatalogItem, FacetValue } from "@/lib/api";
import { RevealGroup, RevealItem } from "@/components/motion/Reveal";

const PAGE_SIZE = 24;

/** Representative swatch color for each palette name. */
const SWATCH: Record<string, string> = {
  black: "#161310",
  white: "#ffffff",
  gray: "#9b9588",
  beige: "#d8c9a8",
  brown: "#6b4f34",
  red: "#b23a2e",
  orange: "#cf7a3a",
  yellow: "#d8c24a",
  green: "#5a7d4f",
  blue: "#4a6b9b",
  purple: "#7a5a9b",
  pink: "#cf8fa8",
};

interface BrowseGridProps {
  category: string;
}

// ---------------------------------------------------------------------------
// State machine (items + pagination)
// ---------------------------------------------------------------------------

type State =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "loaded"; items: CatalogItem[]; hasMore: boolean; loadingMore: boolean };

type Action =
  | { type: "FETCH_START" }
  | { type: "FETCH_SUCCESS"; items: CatalogItem[]; hasMore: boolean }
  | { type: "FETCH_ERROR"; message: string }
  | { type: "MORE_START" }
  | { type: "MORE_SUCCESS"; items: CatalogItem[]; hasMore: boolean }
  | { type: "MORE_ERROR"; message: string };

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case "FETCH_START":
      return { status: "loading" };
    case "FETCH_SUCCESS":
      return { status: "loaded", items: action.items, hasMore: action.hasMore, loadingMore: false };
    case "FETCH_ERROR":
      return { status: "error", message: action.message };
    case "MORE_START":
      if (state.status !== "loaded") return state;
      return { ...state, loadingMore: true };
    case "MORE_SUCCESS":
      if (state.status !== "loaded") return state;
      return { ...state, items: [...state.items, ...action.items], hasMore: action.hasMore, loadingMore: false };
    case "MORE_ERROR":
      if (state.status !== "loaded") return state;
      return { ...state, loadingMore: false };
    default:
      return state;
  }
}

function ItemCardSkeleton() {
  return (
    <div className="rounded-sm bg-surface border border-rule overflow-hidden">
      <div className="aspect-square w-full animate-pulse bg-rule/50" />
      <div className="p-3">
        <div className="h-3 w-3/4 animate-pulse rounded-sm bg-rule/70" />
      </div>
    </div>
  );
}

function ItemCard({ item, fallbackLabel }: { item: CatalogItem; fallbackLabel: string }) {
  const safeId = item.item_id.replace(/[^a-zA-Z0-9-_]/g, "_");
  const label = item.title || fallbackLabel;
  return (
    <Link
      href={`/build/${encodeURIComponent(item.item_id)}`}
      transitionTypes={["nav-forward"]}
      className="group relative flex flex-col overflow-hidden rounded-sm border border-rule bg-surface transition-[border-color,box-shadow,transform] duration-300 hover:-translate-y-0.5 hover:border-ink-soft hover:shadow-md"
    >
      <div className="relative aspect-square w-full overflow-hidden bg-rule/30">
        <Image
          src={imageUrl(item.item_id)}
          alt={label}
          fill
          sizes="(min-width: 1280px) 16vw, (min-width: 1024px) 20vw, (min-width: 768px) 25vw, (min-width: 640px) 33vw, 50vw"
          className="object-cover transition-transform duration-[3000ms] ease-out group-hover:scale-110"
          style={{ viewTransitionName: `catalog-img-${safeId}` }}
          unoptimized
        />
        <div className="absolute inset-0 flex items-center justify-center bg-ink/0 transition-colors group-hover:bg-ink/10">
          <span
            className="rounded-sm bg-paper/90 px-3 py-1 text-[10px] uppercase tracking-[0.14em] text-ink opacity-0 transition-opacity group-hover:opacity-100"
            style={{ fontFamily: "var(--font-body-var), serif" }}
          >
            Build outfit
          </span>
        </div>
      </div>
      <div className="px-3 py-2.5">
        <p
          className="line-clamp-2 text-xs leading-snug text-ink"
          style={{ fontFamily: "var(--font-body-var), serif" }}
        >
          {label}
        </p>
      </div>
    </Link>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function BrowseGrid({ category }: BrowseGridProps) {
  const [state, dispatch] = useReducer(reducer, { status: "idle" });
  const offsetRef = useRef(0);
  const [color, setColor] = useState<string | null>(null);
  const [brand, setBrand] = useState<string | null>(null);
  const [facets, setFacets] = useState<{ colors: FacetValue[]; brands: FacetValue[] }>({
    colors: [],
    brands: [],
  });

  const categoryLabel = category
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());

  // Reset filters + load facets when the category changes.
  useEffect(() => {
    setColor(null);
    setBrand(null);
    let cancelled = false;
    getCatalogFacets(category)
      .then((f) => {
        if (!cancelled) setFacets({ colors: f.colors, brands: f.brands });
      })
      .catch(() => {
        if (!cancelled) setFacets({ colors: [], brands: [] });
      });
    return () => {
      cancelled = true;
    };
  }, [category]);

  // Load items whenever the category or a filter changes.
  useEffect(() => {
    let cancelled = false;
    offsetRef.current = 0;
    dispatch({ type: "FETCH_START" });
    getCatalogItems(category, PAGE_SIZE, 0, color, brand)
      .then((resp) => {
        if (cancelled) return;
        dispatch({ type: "FETCH_SUCCESS", items: resp.items, hasMore: resp.items.length === PAGE_SIZE });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        dispatch({ type: "FETCH_ERROR", message: err instanceof Error ? err.message : "Failed to load items." });
      });
    return () => {
      cancelled = true;
    };
  }, [category, color, brand]);

  const handleLoadMore = () => {
    const nextOffset = offsetRef.current + PAGE_SIZE;
    offsetRef.current = nextOffset;
    dispatch({ type: "MORE_START" });
    getCatalogItems(category, PAGE_SIZE, nextOffset, color, brand)
      .then((resp) => {
        dispatch({ type: "MORE_SUCCESS", items: resp.items, hasMore: resp.items.length === PAGE_SIZE });
      })
      .catch((err: unknown) => {
        dispatch({ type: "MORE_ERROR", message: err instanceof Error ? err.message : "Failed to load more." });
      });
  };

  // Filter bar: color swatches + brand dropdown.
  const hasFacets = facets.colors.length > 0 || facets.brands.length > 0;
  const filterBar = hasFacets ? (
    <div className="mb-6 flex flex-wrap items-center gap-x-8 gap-y-3">
      {facets.colors.length > 0 && (
        <div className="flex items-center gap-3">
          <span
            className="text-[10px] uppercase tracking-[0.16em] text-ink-soft"
            style={{ fontFamily: "var(--font-display-var), serif" }}
          >
            Color
          </span>
          <div className="flex flex-wrap gap-1.5">
            {facets.colors.map((c) => {
              const active = color === c.value;
              return (
                <button
                  key={c.value}
                  type="button"
                  onClick={() => setColor(active ? null : c.value)}
                  aria-pressed={active}
                  aria-label={`${c.value} (${c.count})`}
                  title={`${c.value} · ${c.count}`}
                  className={`h-6 w-6 rounded-full border transition-transform hover:scale-110 ${
                    active
                      ? "border-ink ring-2 ring-ink ring-offset-1 ring-offset-paper"
                      : "border-rule"
                  }`}
                  style={{ background: SWATCH[c.value] ?? "#cccccc" }}
                />
              );
            })}
          </div>
        </div>
      )}

      {facets.brands.length > 0 && (
        <div className="flex items-center gap-3">
          <span
            className="text-[10px] uppercase tracking-[0.16em] text-ink-soft"
            style={{ fontFamily: "var(--font-display-var), serif" }}
          >
            Brand
          </span>
          <select
            value={brand ?? ""}
            onChange={(e) => setBrand(e.target.value || null)}
            aria-label="Filter by brand"
            className="rounded-sm border border-rule bg-surface px-3 py-1.5 text-xs tracking-[0.04em] text-ink focus:border-ink-soft focus:outline-none"
            style={{ fontFamily: "var(--font-body-var), serif" }}
          >
            <option value="">All brands</option>
            {facets.brands.map((b) => (
              <option key={b.value} value={b.value}>
                {b.value} ({b.count})
              </option>
            ))}
          </select>
        </div>
      )}

      {(color || brand) && (
        <button
          type="button"
          onClick={() => {
            setColor(null);
            setBrand(null);
          }}
          className="text-xs uppercase tracking-[0.1em] text-ink-soft underline underline-offset-2 hover:text-ink"
          style={{ fontFamily: "var(--font-body-var), serif" }}
        >
          Clear
        </button>
      )}
    </div>
  ) : null;

  let content: React.ReactNode;

  if (state.status === "idle" || state.status === "loading") {
    content = (
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6">
        {Array.from({ length: PAGE_SIZE }).map((_, i) => (
          <ItemCardSkeleton key={i} />
        ))}
      </div>
    );
  } else if (state.status === "error") {
    content = (
      <div
        role="alert"
        className="rounded-sm bg-surface border border-rule px-4 py-3 text-sm text-ink-soft"
        style={{ fontFamily: "var(--font-body-var), serif" }}
      >
        <strong>Error:</strong> {state.message}
      </div>
    );
  } else if (state.items.length === 0) {
    content = (
      <div className="rounded-sm bg-surface border border-rule p-16 text-center">
        <p
          className="text-base uppercase tracking-[0.15em] text-ink-soft mb-2"
          style={{ fontFamily: "var(--font-display-var), serif" }}
        >
          No Items Found
        </p>
        <p className="text-sm text-ink-soft" style={{ fontFamily: "var(--font-body-var), serif" }}>
          {color || brand ? "No items match these filters. Try clearing one." : "Select a different category to browse."}
        </p>
      </div>
    );
  } else {
    content = (
      <>
        <RevealGroup
          stagger={0.045}
          animateOnMount
          className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6"
        >
          {state.items.map((item) => (
            <RevealItem key={item.item_id}>
              <ItemCard item={item} fallbackLabel={categoryLabel} />
            </RevealItem>
          ))}
        </RevealGroup>

        {state.hasMore && (
          <div className="mt-10 flex justify-center">
            <button
              type="button"
              onClick={handleLoadMore}
              disabled={state.loadingMore}
              className="rounded-sm border border-ink px-8 py-2.5 text-xs uppercase tracking-[0.14em] text-ink transition-all hover:bg-ink hover:text-paper disabled:cursor-not-allowed disabled:opacity-50"
              style={{ fontFamily: "var(--font-body-var), serif" }}
            >
              {state.loadingMore ? "Loading…" : "Load More"}
            </button>
          </div>
        )}
      </>
    );
  }

  return (
    <section aria-label={`${categoryLabel} items`}>
      {filterBar}
      {content}
    </section>
  );
}
