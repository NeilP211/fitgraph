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
    <div className="rounded-2xl bg-white border border-stone-200 overflow-hidden">
      <div className="aspect-square w-full animate-pulse bg-stone-200" />
      <div className="p-3">
        <div className="h-3 w-3/4 animate-pulse rounded bg-stone-200" />
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
        className="rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700"
      >
        <strong>Error:</strong> {state.message}
      </div>
    );
  }

  if (state.items.length === 0) {
    return (
      <div className="rounded-2xl bg-white border border-stone-200 p-16 text-center">
        <p className="text-4xl mb-3">&#128268;</p>
        <p className="font-medium text-stone-700">No items found</p>
        <p className="mt-1 text-sm text-stone-400">
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
            className="group relative flex flex-col overflow-hidden rounded-2xl border border-stone-200 bg-white shadow-sm hover:border-stone-300 hover:shadow-md transition-all"
          >
            {/* Image */}
            <div className="relative aspect-square w-full bg-stone-100 overflow-hidden">
              <Image
                src={imageUrl(item.item_id)}
                alt={item.title || categoryLabel}
                fill
                sizes="(min-width: 1280px) 16vw, (min-width: 1024px) 20vw, (min-width: 768px) 25vw, (min-width: 640px) 33vw, 50vw"
                className="object-cover transition-transform duration-300 group-hover:scale-105"
                unoptimized
              />
              {/* Hover overlay */}
              <div className="absolute inset-0 flex items-center justify-center bg-black/0 group-hover:bg-black/10 transition-colors">
                <span className="rounded-full bg-white/90 px-3 py-1 text-xs font-semibold text-stone-900 opacity-0 group-hover:opacity-100 transition-opacity shadow-sm">
                  Build outfit
                </span>
              </div>
            </div>

            {/* Title */}
            <div className="px-3 py-2.5">
              <p className="text-xs font-medium text-stone-700 leading-snug line-clamp-2">
                {item.title || categoryLabel}
              </p>
            </div>
          </Link>
        ))}
      </div>

      {/* Load more */}
      {state.hasMore && (
        <div className="mt-8 flex justify-center">
          <button
            type="button"
            onClick={handleLoadMore}
            disabled={state.loadingMore}
            className="rounded-xl border border-stone-300 bg-white px-6 py-2.5 text-sm font-medium text-stone-700 shadow-sm hover:bg-stone-50 hover:border-stone-400 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
          >
            {state.loadingMore ? (
              <span className="flex items-center gap-2">
                <svg
                  className="h-4 w-4 animate-spin text-stone-400"
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
              "Load more"
            )}
          </button>
        </div>
      )}
    </section>
  );
}
