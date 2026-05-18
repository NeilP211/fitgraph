"use client";

import { useState } from "react";
import UploadZone from "@/components/UploadZone";
import SuggestionCard from "@/components/SuggestionCard";
import SaveOutfitModal from "@/components/SaveOutfitModal";
import { getSuggestions } from "@/lib/api";
import type { SuggestionItem } from "@/lib/api";

export default function HomePage() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<SuggestionItem[]>([]);
  const [queryItemId, setQueryItemId] = useState<string>("");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [showModal, setShowModal] = useState(false);
  const [savedToast, setSavedToast] = useState(false);

  const handleSubmit = async (file: File, category: string, text: string) => {
    setLoading(true);
    setError(null);
    setSuggestions([]);
    setSelectedIds(new Set());
    try {
      const resp = await getSuggestions(
        file,
        text || undefined,
        category || undefined
      );
      setSuggestions(resp.suggestions);
      // Use the first suggestion's item_id as a stand-in for query tracking
      setQueryItemId(resp.suggestions[0]?.item_id ?? "query");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Something went wrong. Try again."
      );
    } finally {
      setLoading(false);
    }
  };

  const toggleSelect = (itemId: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(itemId)) next.delete(itemId);
      else next.add(itemId);
      return next;
    });
  };

  const onSaved = () => {
    setSavedToast(true);
    setSelectedIds(new Set());
    setTimeout(() => setSavedToast(false), 3000);
  };

  return (
    <main className="min-h-screen bg-stone-50">
      {/* Hero */}
      <section className="mx-auto max-w-6xl px-6 pt-12 pb-10 text-center">
        <span className="inline-block rounded-full bg-stone-900/5 px-3 py-1 text-xs font-medium uppercase tracking-widest text-stone-500 mb-4">
          AI-powered styling
        </span>
        <h1 className="text-4xl font-bold text-stone-900 tracking-tight sm:text-5xl">
          Find your perfect match
        </h1>
        <p className="mx-auto mt-4 max-w-lg text-base text-stone-500">
          Upload a piece from your wardrobe and our graph neural network will
          discover compatible items that complete the look.
        </p>
      </section>

      {/* Upload panel */}
      <section
        aria-label="Upload a garment"
        className="mx-auto max-w-xl px-6 pb-12"
      >
        <div className="rounded-2xl bg-white p-6 shadow-sm border border-stone-200">
          <UploadZone onSubmit={handleSubmit} loading={loading} />
        </div>
      </section>

      {/* Error state */}
      {error && (
        <div role="alert" className="mx-auto max-w-xl px-6 pb-6">
          <div className="rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
            <strong>Error:</strong> {error}
          </div>
        </div>
      )}

      {/* Loading skeleton */}
      {loading && (
        <section
          aria-label="Loading suggestions"
          aria-busy="true"
          className="mx-auto max-w-6xl px-6 pb-16"
        >
          <div className="mb-6 h-6 w-48 animate-pulse rounded-lg bg-stone-200" />
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
            {Array.from({ length: 10 }).map((_, i) => (
              <div
                key={i}
                className="rounded-2xl bg-white border border-stone-200 overflow-hidden"
              >
                <div className="aspect-square w-full animate-pulse bg-stone-200" />
                <div className="p-4 space-y-2">
                  <div className="h-3 w-3/4 animate-pulse rounded bg-stone-200" />
                  <div className="h-3 w-1/2 animate-pulse rounded bg-stone-200" />
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Suggestions grid */}
      {!loading && suggestions.length > 0 && (
        <section
          aria-label="Suggested matching items"
          className="mx-auto max-w-6xl px-6 pb-16"
        >
          <div className="mb-6 flex items-center justify-between flex-wrap gap-3">
            <div>
              <h2 className="text-xl font-semibold text-stone-900">
                {suggestions.length} compatible pieces
              </h2>
              <p className="text-sm text-stone-500">
                Select items to save as an outfit
              </p>
            </div>

            {selectedIds.size > 0 && (
              <button
                type="button"
                onClick={() => setShowModal(true)}
                className="rounded-xl bg-stone-900 px-5 py-2.5 text-sm font-semibold text-white shadow hover:bg-stone-700 transition-colors"
              >
                Save outfit ({selectedIds.size})
              </button>
            )}
          </div>

          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
            {suggestions.map((item) => (
              <SuggestionCard
                key={item.item_id}
                item={item}
                queryItemId={queryItemId}
                selected={selectedIds.has(item.item_id)}
                onToggleSelect={() => toggleSelect(item.item_id)}
              />
            ))}
          </div>
        </section>
      )}

      {/* Empty state after successful search with 0 results */}
      {!loading && !error && suggestions.length === 0 && queryItemId && (
        <section className="mx-auto max-w-md px-6 pb-16 text-center">
          <div className="rounded-2xl bg-white border border-stone-200 p-10">
            <p className="text-4xl mb-3">&#128269;</p>
            <p className="font-medium text-stone-700">No suggestions found</p>
            <p className="mt-1 text-sm text-stone-400">
              Try uploading a different image or changing the category.
            </p>
          </div>
        </section>
      )}

      {/* Save outfit modal */}
      {showModal && (
        <SaveOutfitModal
          itemIds={Array.from(selectedIds)}
          onClose={() => setShowModal(false)}
          onSaved={onSaved}
        />
      )}

      {/* Saved toast */}
      {savedToast && (
        <div
          role="status"
          aria-live="polite"
          className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 rounded-xl bg-stone-900 px-5 py-3 text-sm font-medium text-white shadow-lg"
        >
          Outfit saved successfully!
        </div>
      )}
    </main>
  );
}
