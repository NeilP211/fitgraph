"use client";

import { useEffect, useReducer, useRef } from "react";
import Image from "next/image";
import Link from "next/link";
import { getCatalogItems, imageUrl } from "@/lib/api";
import type { CatalogItem } from "@/lib/api";

const PAGE_SIZE = 24;

interface BrowseGridProps {
  category: string;
}

// ---------------------------------------------------------------------------
// State machine
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

// ---------------------------------------------------------------------------
// Skeleton
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function BrowseGrid({ category }: BrowseGridProps) {
  const [state, dispatch] = useReducer(reducer, { status: "idle" });
  const offsetRef = useRef(0);

  useEffect(() => {
    let cancelled = false;
    offsetRef.current = 0;

    dispatch({ type: "FETCH_START" });

    getCatalogItems(category, PAGE_SIZE, 0)
      .then((resp) => {
        if (cancelled) return;
        dispatch({
          type: "FETCH_SUCCESS",
          items: resp.items,
          hasMore: resp.items.length === PAGE_SIZE,
        });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        dispatch({
          type: "FETCH_ERROR",
          message: err instanceof Error ? err.message : "Failed to load items.",
        });
      });

    return () => {
      cancelled = true;
    };
  }, [category]);

  const handleLoadMore = () => {
    const nextOffset = offsetRef.current + PAGE_SIZE;
    offsetRef.current = nextOffset;
    dispatch({ type: "MORE_START" });

    getCatalogItems(category, PAGE_SIZE, nextOffset)
      .then((resp) => {
        dispatch({
          type: "MORE_SUCCESS",
          items: resp.items,
          hasMore: resp.items.length === PAGE_SIZE,
        });
      })
      .catch((err: unknown) => {
        dispatch({
          type: "MORE_ERROR",
          message: err instanceof Error ? err.message : "Failed to load more items.",
        });
      });
  };

  const categoryLabel = category
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());

  if (state.status === "idle" || state.status === "loading") {
    return (
      <section aria-busy="true" aria-label="Loading catalog items">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6">
          {Array.from({ length: PAGE_SIZE }).map((_, i) => (
            <ItemCardSkeleton key={i} />
          ))}
        </div>
      </section>
    );
  }

  if (state.status === "error") {
    return (
      <div
        role="alert"
        className="rounded-sm bg-surface border border-rule px-4 py-3 text-sm text-accent-deep"
        style={{ fontFamily: "var(--font-body-var), serif" }}
      >
        <strong>Error:</strong> {state.message}
      </div>
    );
  }

  if (state.items.length === 0) {
    return (
      <div className="rounded-sm bg-surface border border-rule p-16 text-center">
        <p
          className="text-base uppercase tracking-[0.15em] text-ink-soft mb-2"
          style={{ fontFamily: "var(--font-display-var), serif" }}
        >
          No Items Found
        </p>
        <p
          className="text-sm text-ink-soft"
          style={{ fontFamily: "var(--font-body-var), serif" }}
        >
          Select a different category to browse.
        </p>
      </div>
    );
  }

  return (
    <section aria-label={`${categoryLabel} items`}>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6">
        {state.items.map((item) => (
          <Link
            key={item.item_id}
            href={`/build/${encodeURIComponent(item.item_id)}`}
            className="group relative flex flex-col overflow-hidden rounded-sm border border-rule bg-surface hover:border-ink-soft hover:shadow-md transition-all"
          >
            {/* Image */}
            <div className="relative aspect-square w-full bg-rule/30 overflow-hidden">
              <Image
                src={imageUrl(item.item_id)}
                alt={item.title || categoryLabel}
                fill
                sizes="(min-width: 1280px) 16vw, (min-width: 1024px) 20vw, (min-width: 768px) 25vw, (min-width: 640px) 33vw, 50vw"
                className="object-cover transition-transform duration-300 group-hover:scale-105"
                unoptimized
              />
              {/* Hover overlay */}
              <div className="absolute inset-0 flex items-center justify-center bg-ink/0 group-hover:bg-ink/10 transition-colors">
                <span
                  className="rounded-sm bg-paper/90 px-3 py-1 text-[10px] uppercase tracking-[0.14em] text-ink opacity-0 group-hover:opacity-100 transition-opacity"
                  style={{ fontFamily: "var(--font-body-var), serif" }}
                >
                  Build outfit
                </span>
              </div>
            </div>

            {/* Title */}
            <div className="px-3 py-2.5">
              <p
                className="text-xs text-ink leading-snug line-clamp-2"
                style={{ fontFamily: "var(--font-body-var), serif" }}
              >
                {item.title || categoryLabel}
              </p>
            </div>
          </Link>
        ))}
      </div>

      {/* Load more */}
      {state.hasMore && (
        <div className="mt-10 flex justify-center">
          <button
            type="button"
            onClick={handleLoadMore}
            disabled={state.loadingMore}
            className="rounded-sm border border-ink px-8 py-2.5 text-xs uppercase tracking-[0.14em] text-ink hover:bg-ink hover:text-paper disabled:opacity-50 disabled:cursor-not-allowed transition-all"
            style={{ fontFamily: "var(--font-body-var), serif" }}
          >
            {state.loadingMore ? (
              <span className="flex items-center gap-2">
                <svg
                  className="h-4 w-4 animate-spin text-ink-soft"
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                  aria-hidden="true"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8v8H4z"
                  />
                </svg>
                Loading…
              </span>
            ) : (
              "Load More"
            )}
          </button>
        </div>
      )}
    </section>
  );
}
