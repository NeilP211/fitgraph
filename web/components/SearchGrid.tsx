"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { searchCatalog, imageUrl } from "@/lib/api";
import type { CatalogItem } from "@/lib/api";
import { RevealGroup, RevealItem } from "@/components/motion/Reveal";

type State =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "loaded"; items: CatalogItem[] };

/** Catalog search results grid, wired to the /catalog/search endpoint. */
export default function SearchGrid({ query }: { query: string }) {
  const [state, setState] = useState<State>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    setState({ status: "loading" });
    searchCatalog(query, 36)
      .then((resp) => {
        if (!cancelled) setState({ status: "loaded", items: resp.items });
      })
      .catch((err: unknown) => {
        if (!cancelled)
          setState({
            status: "error",
            message: err instanceof Error ? err.message : "Search failed.",
          });
      });
    return () => {
      cancelled = true;
    };
  }, [query]);

  if (state.status === "loading") {
    return (
      <section aria-busy="true" aria-label="Searching catalog">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6">
          {Array.from({ length: 12 }).map((_, i) => (
            <div key={i} className="overflow-hidden rounded-sm border border-rule bg-surface">
              <div className="aspect-square w-full animate-pulse bg-rule/50" />
              <div className="p-3">
                <div className="h-3 w-3/4 animate-pulse rounded-sm bg-rule/70" />
              </div>
            </div>
          ))}
        </div>
      </section>
    );
  }

  if (state.status === "error") {
    return (
      <div
        role="alert"
        className="rounded-sm border border-rule bg-surface px-4 py-3 text-sm text-ink-soft"
        style={{ fontFamily: "var(--font-body-var), serif" }}
      >
        <strong>Error:</strong> {state.message}
      </div>
    );
  }

  if (state.items.length === 0) {
    return (
      <div className="rounded-sm border border-rule bg-surface p-16 text-center">
        <p
          className="mb-2 text-base uppercase tracking-[0.15em] text-ink-soft"
          style={{ fontFamily: "var(--font-display-var), serif" }}
        >
          No matches for &ldquo;{query}&rdquo;
        </p>
        <p className="text-sm text-ink-soft" style={{ fontFamily: "var(--font-body-var), serif" }}>
          Try another word, or clear the search to browse by category.
        </p>
      </div>
    );
  }

  return (
    <section aria-label={`Search results for ${query}`}>
      <RevealGroup
        stagger={0.04}
        animateOnMount
        className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6"
      >
        {state.items.map((item) => {
          const safeId = item.item_id.replace(/[^a-zA-Z0-9-_]/g, "_");
          const label = item.title || item.semantic_category || "Catalog item";
          return (
            <RevealItem key={item.item_id}>
              <Link
                href={`/build/${encodeURIComponent(item.item_id)}`}
                className="group relative flex flex-col overflow-hidden rounded-sm border border-rule bg-surface transition-[border-color,box-shadow,transform] duration-300 hover:-translate-y-0.5 hover:border-ink-soft hover:shadow-md"
              >
                <div className="relative aspect-square w-full overflow-hidden bg-rule/30">
                  <Image
                    src={imageUrl(item.item_id)}
                    alt={label}
                    fill
                    sizes="(min-width: 1280px) 16vw, (min-width: 1024px) 20vw, (min-width: 768px) 25vw, 50vw"
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
            </RevealItem>
          );
        })}
      </RevealGroup>
    </section>
  );
}
