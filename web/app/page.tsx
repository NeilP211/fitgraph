"use client";

import { useState } from "react";
import CategoryNav from "@/components/CategoryNav";
import BrowseGrid from "@/components/BrowseGrid";
import RunwayHero from "@/components/RunwayHero";
import FashionBand from "@/components/FashionBand";
import { Reveal } from "@/components/motion/Reveal";

export default function HomePage() {
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);

  return (
    <main className="min-h-screen bg-paper">
      {/* ── Runway hero — a pure visual stage (marquee + catwalk + floats).
           No editorial text overlays it anymore, so nothing collides with
           the floating models. RunwayHero is owned by the runway workstream. ── */}
      <RunwayHero />

      {/* ── Catalog area: drifting HIGH FASHION backdrop behind a clean,
           centered editorial lockup + the browse grid ── */}
      <div className="relative isolate overflow-hidden">
        <FashionBand top="38%" />

        {/* Editorial header — moved off the runway, sits on plain paper */}
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

        {/* Category pills */}
        <section className="relative z-10 mx-auto max-w-6xl px-6 pb-6 pt-6">
          <Reveal delay={0.1}>
            <CategoryNav
              selected={selectedCategory}
              onSelect={setSelectedCategory}
            />
          </Reveal>
        </section>

        {/* Item grid */}
        <section className="relative z-10 mx-auto max-w-6xl px-6 pb-16">
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
      </div>
    </main>
  );
}
