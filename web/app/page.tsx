"use client";

import { useState } from "react";
import CategoryNav from "@/components/CategoryNav";
import BrowseGrid from "@/components/BrowseGrid";
import RunwayHero from "@/components/RunwayHero";
import { Reveal } from "@/components/motion/Reveal";

export default function HomePage() {
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);

  return (
    <main className="min-h-screen bg-transparent">
      {/* ── Runway Hero ── */}
      <div className="relative">
        <RunwayHero />

        {/* Editorial overlay — title sits at the runway head */}
        <div className="absolute inset-0 flex flex-col items-center justify-center pb-8 px-6 pointer-events-none">
          {/* Hairline rule above */}
          <div
            className="w-full max-w-2xl mb-5"
            style={{
              height: "1px",
              background: "var(--rule)",
            }}
          />

          {/* Script flourish */}
          <Reveal delay={0.05}>
            <p
              className="text-2xl text-ink-soft mb-1 text-center"
              style={{ fontFamily: "var(--font-script-var), cursive" }}
            >
              curated for you
            </p>
          </Reveal>

          {/* Cinzel title */}
          <Reveal delay={0.15}>
            <h1
              className="text-4xl sm:text-5xl font-semibold uppercase tracking-[0.12em] text-ink leading-tight text-center"
              style={{ fontFamily: "var(--font-display-var), serif" }}
            >
              Browse the Catalog
            </h1>
          </Reveal>

          {/* Hairline rule below */}
          <div
            className="w-full max-w-2xl mt-5 mb-4"
            style={{
              height: "1px",
              background: "var(--rule)",
            }}
          />

          {/* Subtext */}
          <Reveal delay={0.25}>
            <p
              className="max-w-lg text-base text-ink-soft leading-relaxed text-center"
              style={{ fontFamily: "var(--font-body-var), serif" }}
            >
              Choose a seed garment and let our graph neural network compose a
              complete, type-aware ensemble around it.
            </p>
          </Reveal>
        </div>
      </div>

      {/* Category pills */}
      <section className="mx-auto max-w-6xl px-6 pb-6 pt-2">
        <Reveal delay={0.1}>
          <CategoryNav
            selected={selectedCategory}
            onSelect={setSelectedCategory}
          />
        </Reveal>
      </section>

      {/* Item grid */}
      <section className="mx-auto max-w-6xl px-6 pb-16">
        {selectedCategory ? (
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
              Choose a category above to explore catalog items.
            </p>
          </div>
        )}
      </section>
    </main>
  );
}
