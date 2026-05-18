"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import { getOutfits, imageUrl } from "@/lib/api";
import type { OutfitHistoryEntry } from "@/lib/api";
import Link from "next/link";

const DEMO_USER_ID = 1;

function OutfitCard({ outfit }: { outfit: OutfitHistoryEntry }) {
  const visibleIds = outfit.item_ids.slice(0, 4);
  const extra = outfit.item_ids.length - visibleIds.length;

  return (
    <article className="rounded-2xl bg-white border border-stone-200 shadow-sm overflow-hidden hover:shadow-md transition-shadow">
      {/* Item image strip */}
      <div className="grid grid-cols-4 gap-0.5 bg-stone-100">
        {visibleIds.map((id, idx) => (
          <div key={id} className="relative aspect-square overflow-hidden">
            <Image
              src={imageUrl(id)}
              alt={`Item ${id}`}
              fill
              sizes="15vw"
              className="object-cover"
              unoptimized
            />
            {idx === visibleIds.length - 1 && extra > 0 && (
              <div className="absolute inset-0 flex items-center justify-center bg-black/40 text-white text-sm font-semibold">
                +{extra}
              </div>
            )}
          </div>
        ))}
        {/* Placeholder cells if fewer than 4 items */}
        {Array.from({ length: Math.max(0, 4 - visibleIds.length) }).map(
          (_, i) => (
            <div key={`ph-${i}`} className="aspect-square bg-stone-200" />
          )
        )}
      </div>

      {/* Metadata */}
      <div className="p-4">
        <p className="font-medium text-stone-900 truncate">
          {outfit.outfit_name || `Outfit #${outfit.outfit_id}`}
        </p>
        <div className="mt-1 flex items-center justify-between">
          <p className="text-xs text-stone-400">
            {outfit.item_ids.length} piece{outfit.item_ids.length !== 1 ? "s" : ""}
          </p>
          {outfit.created_at && (
            <p className="text-xs text-stone-400">
              {new Date(outfit.created_at).toLocaleDateString(undefined, {
                month: "short",
                day: "numeric",
                year: "numeric",
              })}
            </p>
          )}
        </div>
      </div>
    </article>
  );
}

export default function OutfitsPage() {
  const [outfits, setOutfits] = useState<OutfitHistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const resp = await getOutfits(DEMO_USER_ID);
        if (mounted) setOutfits(resp.outfits);
      } catch (err) {
        if (mounted)
          setError(
            err instanceof Error ? err.message : "Failed to load outfits."
          );
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => {
      mounted = false;
    };
  }, []);

  return (
    <main className="min-h-screen bg-stone-50">
      <section className="mx-auto max-w-6xl px-6 pt-10 pb-16">
        <div className="mb-8 flex items-center justify-between flex-wrap gap-4">
          <div>
            <h1 className="text-2xl font-bold text-stone-900 tracking-tight">
              Saved Outfits
            </h1>
            <p className="mt-1 text-sm text-stone-500">
              Your curated looks, all in one place.
            </p>
          </div>
          <Link
            href="/"
            className="rounded-xl bg-stone-900 px-5 py-2.5 text-sm font-semibold text-white shadow hover:bg-stone-700 transition-colors"
          >
            + New outfit
          </Link>
        </div>

        {/* Loading skeleton */}
        {loading && (
          <div
            aria-busy="true"
            aria-label="Loading outfits"
            className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3"
          >
            {Array.from({ length: 6 }).map((_, i) => (
              <div
                key={i}
                className="rounded-2xl bg-white border border-stone-200 overflow-hidden"
              >
                <div className="grid grid-cols-4 gap-0.5 bg-stone-100">
                  {Array.from({ length: 4 }).map((_, j) => (
                    <div
                      key={j}
                      className="aspect-square animate-pulse bg-stone-200"
                    />
                  ))}
                </div>
                <div className="p-4 space-y-2">
                  <div className="h-4 w-2/3 animate-pulse rounded bg-stone-200" />
                  <div className="h-3 w-1/3 animate-pulse rounded bg-stone-200" />
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Error state */}
        {!loading && error && (
          <div role="alert" className="rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
            <strong>Error:</strong> {error}
          </div>
        )}

        {/* Empty state */}
        {!loading && !error && outfits.length === 0 && (
          <div className="rounded-2xl bg-white border border-stone-200 p-16 text-center">
            <p className="text-4xl mb-4">&#128248;</p>
            <p className="font-medium text-stone-700 text-lg">No outfits yet</p>
            <p className="mt-2 text-sm text-stone-400">
              Head to{" "}
              <Link href="/" className="text-stone-700 underline underline-offset-2">
                Discover
              </Link>{" "}
              to build your first look.
            </p>
          </div>
        )}

        {/* Outfits grid */}
        {!loading && !error && outfits.length > 0 && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {outfits.map((outfit) => (
              <OutfitCard key={outfit.outfit_id} outfit={outfit} />
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
