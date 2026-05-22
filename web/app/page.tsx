"use client";

import { useState } from "react";
import CategoryNav from "@/components/CategoryNav";
import BrowseGrid from "@/components/BrowseGrid";

export default function HomePage() {
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);

  return (
    <main className="min-h-screen bg-stone-50">
      {/* Hero */}
      <section className="mx-auto max-w-6xl px-6 pt-10 pb-6">
        <span className="inline-block rounded-full bg-stone-900/5 px-3 py-1 text-xs font-medium uppercase tracking-widest text-stone-500 mb-4">
          AI-powered styling
        </span>
        <h1 className="text-3xl font-bold text-stone-900 tracking-tight sm:text-4xl">
          Browse the catalog
        </h1>
        <p className="mt-2 max-w-lg text-sm text-stone-500">
          Pick a seed garment and let our graph neural network build a
          complete, type-aware outfit around it.
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
          <div className="rounded-2xl bg-white border border-stone-200 p-16 text-center">
            <p className="text-4xl mb-3">&#128248;</p>
            <p className="font-medium text-stone-700">Choose a category above</p>
            <p className="mt-1 text-sm text-stone-400">
              Select a category to browse catalog items.
            </p>
          </div>
        )}
      </section>
    </main>
  );
}
