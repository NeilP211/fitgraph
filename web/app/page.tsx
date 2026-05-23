"use client";

import { useEffect, useState } from "react";
import CategoryNav from "@/components/CategoryNav";
import BrowseGrid from "@/components/BrowseGrid";
import SearchGrid from "@/components/SearchGrid";
import RunwayHero from "@/components/RunwayHero";
import FashionBand from "@/components/FashionBand";
import { Reveal } from "@/components/motion/Reveal";

export default function HomePage() {
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");

  // Debounce the search box so we don't hit the API on every keystroke.
  useEffect(() => {
    const t = setTimeout(() => setDebounced(query.trim()), 320);
    return () => clearTimeout(t);
  }, [query]);

  const searching = debounced.length > 0;

  return (
    <main className="min-h-screen bg-paper">
      <RunwayHero />

      <div className="relative isolate overflow-hidden">
        <FashionBand top="38%" />

        {/* Editorial header */}
        <section className="relative z-10 mx-auto max-w-6xl px-6 pt-12 pb-2">
          <div className="mx-auto max-w-2xl flex flex-col items-center text-center">
            <div className="hr-rule w-full max-w-md mb-5" />

            <Reveal delay={0.05}>
              <p
                className="text-2xl text-ink-soft mb-1"
                style={{ fontFamily: "var(--font-script-var), cursive" }}
              >
                curated for you
              </p>
            </Reveal>

            <Reveal delay={0.15}>
              <h1
                className="text-4xl sm:text-5xl font-semibold uppercase tracking-[0.12em] text-ink leading-tight"
                style={{ fontFamily: "var(--font-display-var), serif" }}
              >
                Browse the Catalog
              </h1>
            </Reveal>

            <div className="hr-rule w-full max-w-md mt-5 mb-4" />

            <Reveal delay={0.25}>
              <p
                className="max-w-lg text-base text-ink-soft leading-relaxed"
                style={{ fontFamily: "var(--font-body-var), serif" }}
              >
                Choose a seed garment and let our graph neural network compose a
                complete, type-aware ensemble around it.
              </p>
            </Reveal>
          </div>
        </section>

        {/* Search */}
        <section className="relative z-10 mx-auto max-w-6xl px-6 pt-6">
          <Reveal delay={0.05}>
            <div className="mx-auto flex max-w-xl items-center gap-2 rounded-sm border border-rule bg-surface px-4 py-2.5 transition-colors focus-within:border-ink-soft">
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
                className="shrink-0 text-ink-soft"
              >
                <circle cx="11" cy="11" r="7" />
                <path d="M21 21l-4.3-4.3" />
              </svg>
              <input
                type="search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search the catalog…"
                aria-label="Search the catalog"
                className="w-full bg-transparent text-sm text-ink placeholder:text-ink-soft/70 focus:outline-none"
                style={{ fontFamily: "var(--font-body-var), serif" }}
              />
              {query && (
                <button
                  type="button"
                  onClick={() => setQuery("")}
                  aria-label="Clear search"
                  className="shrink-0 px-1 text-xl leading-none text-ink-soft hover:text-ink"
                >
                  ×
                </button>
              )}
            </div>
          </Reveal>
        </section>

        {/* Category pills (hidden while searching) */}
        {!searching && (
          <section className="relative z-10 mx-auto max-w-6xl px-6 pb-6 pt-6">
            <Reveal delay={0.1}>
              <CategoryNav selected={selectedCategory} onSelect={setSelectedCategory} />
            </Reveal>
          </section>
        )}

        {/* Item grid: search results, else category browse, else a prompt */}
        <section className="relative z-10 mx-auto max-w-6xl px-6 pb-16 pt-6">
          {searching ? (
            <SearchGrid query={debounced} />
          ) : selectedCategory ? (
            <BrowseGrid category={selectedCategory} />
          ) : (
            <div className="rounded-sm bg-surface border border-rule p-16 text-center">
              <p
                className="text-base uppercase tracking-[0.15em] text-ink-soft mb-2"
                style={{ fontFamily: "var(--font-display-var), serif" }}
              >
                Select a Category
              </p>
              <p
                className="text-sm text-ink-soft"
                style={{ fontFamily: "var(--font-body-var), serif" }}
              >
                Choose a category above, or search the catalog.
              </p>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
