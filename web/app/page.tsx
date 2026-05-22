"use client";

import { useState } from "react";
import CategoryNav from "@/components/CategoryNav";
import BrowseGrid from "@/components/BrowseGrid";

export default function HomePage() {
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);

  return (
    <main className="min-h-screen bg-paper">
      {/* Hero */}
      <section className="mx-auto max-w-6xl px-6 pt-12 pb-8">
        {/* Hairline rule above */}
        <div className="hr-rule mb-6" />

        {/* Script flourish */}
        <p
          className="text-2xl text-ink-soft mb-2"
          style={{ fontFamily: "var(--font-script-var), cursive" }}
        >
          curated for you
        </p>

        <h1
          className="text-4xl sm:text-5xl font-semibold uppercase tracking-[0.12em] text-ink leading-tight"
          style={{ fontFamily: "var(--font-display-var), serif" }}
        >
          Browse the Catalog
        </h1>

        <div className="hr-rule mt-4 mb-4" />

        <p
          className="mt-3 max-w-lg text-base text-ink-soft leading-relaxed"
          style={{ fontFamily: "var(--font-body-var), serif" }}
        >
          Choose a seed garment and let our graph neural network compose a
          complete, type-aware ensemble around it.
        </p>
      </section>

      {/* Category pills */}
      <section className="mx-auto max-w-6xl px-6 pb-6">
        <CategoryNav
          selected={selectedCategory}
          onSelect={setSelectedCategory}
        />
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
