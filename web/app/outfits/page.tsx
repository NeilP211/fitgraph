"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import { getOutfits, imageUrl } from "@/lib/api";
import type { OutfitHistoryEntry } from "@/lib/api";
import Link from "next/link";

const DEMO_USER_ID = 1;

function OutfitCard({
  outfit,
  onOpen,
}: {
  outfit: OutfitHistoryEntry;
  onOpen: () => void;
}) {
  const visibleIds = outfit.item_ids.slice(0, 4);
  const extra = outfit.item_ids.length - visibleIds.length;

  return (
    <button
      type="button"
      onClick={onOpen}
      className="block w-full text-left rounded-sm bg-surface border border-rule overflow-hidden hover:border-ink-soft hover:shadow-md transition-all cursor-pointer"
    >
      {/* Item image strip */}
      <div className="grid grid-cols-4 gap-0.5 bg-rule/40">
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
              <div
                className="absolute inset-0 flex items-center justify-center bg-ink/40 text-paper text-xs font-medium"
                style={{ fontFamily: "var(--font-body-var), serif" }}
              >
                +{extra}
              </div>
            )}
          </div>
        ))}
        {/* Placeholder cells if fewer than 4 items */}
        {Array.from({ length: Math.max(0, 4 - visibleIds.length) }).map(
          (_, i) => (
            <div key={`ph-${i}`} className="aspect-square bg-rule/40" />
          )
        )}
      </div>

      {/* Metadata */}
      <div className="p-4">
        <p
          className="font-medium text-ink truncate"
          style={{ fontFamily: "var(--font-body-var), serif" }}
        >
          {outfit.outfit_name || `Outfit #${outfit.outfit_id}`}
        </p>
        <div className="mt-2 flex items-center justify-between">
          <p
            className="text-[10px] uppercase tracking-[0.12em] text-ink-soft"
            style={{ fontFamily: "var(--font-body-var), serif" }}
          >
            {outfit.item_ids.length} piece{outfit.item_ids.length !== 1 ? "s" : ""}
          </p>
          {outfit.created_at && (
            <p
              className="text-[10px] uppercase tracking-[0.08em] text-ink-soft"
              style={{ fontFamily: "var(--font-body-var), serif" }}
            >
              {new Date(outfit.created_at).toLocaleDateString(undefined, {
                month: "short",
                day: "numeric",
                year: "numeric",
              })}
            </p>
          )}
        </div>
      </div>
    </button>
  );
}

function OutfitDetailModal({
  outfit,
  onClose,
}: {
  outfit: OutfitHistoryEntry;
  onClose: () => void;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={outfit.outfit_name || `Outfit ${outfit.outfit_id}`}
      onClick={onClose}
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink/50 p-4"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="max-h-[85vh] w-full max-w-3xl overflow-y-auto rounded-sm bg-surface border border-rule p-6"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2
              className="text-2xl uppercase tracking-[0.1em] text-ink"
              style={{ fontFamily: "var(--font-display-var), serif" }}
            >
              {outfit.outfit_name || `Outfit #${outfit.outfit_id}`}
            </h2>
            <p
              className="mt-1 text-[10px] uppercase tracking-[0.14em] text-ink-soft"
              style={{ fontFamily: "var(--font-body-var), serif" }}
            >
              {outfit.item_ids.length} piece
              {outfit.item_ids.length !== 1 ? "s" : ""} · tap a piece to restyle
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="px-2 text-2xl leading-none text-ink-soft hover:text-ink"
          >
            ×
          </button>
        </div>
        <div className="hr-rule my-4" />
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
          {outfit.item_ids.map((id) => (
            <Link
              key={id}
              href={`/build/${encodeURIComponent(id)}`}
              className="group relative block aspect-square overflow-hidden rounded-sm border border-rule bg-paper"
            >
              <Image
                src={imageUrl(id)}
                alt={`Item ${id}`}
                fill
                sizes="20vw"
                className="object-cover"
                unoptimized
              />
              <span
                className="absolute inset-x-0 bottom-0 bg-ink/60 py-1 text-center text-[10px] uppercase tracking-[0.12em] text-paper opacity-0 transition-opacity group-hover:opacity-100"
                style={{ fontFamily: "var(--font-body-var), serif" }}
              >
                Restyle
              </span>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function OutfitsPage() {
  const [outfits, setOutfits] = useState<OutfitHistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<OutfitHistoryEntry | null>(null);

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
    <main className="min-h-screen bg-transparent">
      <section className="mx-auto max-w-6xl px-6 pt-10 pb-16">
        {/* Page header */}
        <div className="hr-rule mb-6" />
        <div className="mb-8 flex items-center justify-between flex-wrap gap-4">
          <div>
            <h1
              className="text-3xl font-semibold uppercase tracking-[0.12em] text-ink"
              style={{ fontFamily: "var(--font-display-var), serif" }}
            >
              Saved Outfits
            </h1>
            <p
              className="mt-2 text-base text-ink-soft"
              style={{ fontFamily: "var(--font-body-var), serif" }}
            >
              Your curated looks, all in one place.
            </p>
          </div>
          <Link
            href="/"
            className="rounded-sm bg-accent px-5 py-2.5 text-xs uppercase tracking-[0.12em] text-paper hover:bg-accent-deep transition-colors"
            style={{ fontFamily: "var(--font-body-var), serif" }}
          >
            New Outfit
          </Link>
        </div>
        <div className="hr-rule mb-8" />

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
                className="rounded-sm bg-surface border border-rule overflow-hidden"
              >
                <div className="grid grid-cols-4 gap-0.5 bg-rule/40">
                  {Array.from({ length: 4 }).map((_, j) => (
                    <div
                      key={j}
                      className="aspect-square animate-pulse bg-rule/60"
                    />
                  ))}
                </div>
                <div className="p-4 space-y-2">
                  <div className="h-4 w-2/3 animate-pulse rounded-sm bg-rule/60" />
                  <div className="h-3 w-1/3 animate-pulse rounded-sm bg-rule/60" />
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Error state */}
        {!loading && error && (
          <div
            role="alert"
            className="rounded-sm bg-surface border border-rule px-4 py-3 text-sm text-accent-deep"
            style={{ fontFamily: "var(--font-body-var), serif" }}
          >
            <strong>Error:</strong> {error}
          </div>
        )}

        {/* Empty state */}
        {!loading && !error && outfits.length === 0 && (
          <div className="rounded-sm bg-surface border border-rule p-16 text-center">
            <p
              className="text-base uppercase tracking-[0.15em] text-ink-soft mb-3"
              style={{ fontFamily: "var(--font-display-var), serif" }}
            >
              No Outfits Yet
            </p>
            <p
              className="text-sm text-ink-soft"
              style={{ fontFamily: "var(--font-body-var), serif" }}
            >
              Head to{" "}
              <Link href="/" className="text-accent underline underline-offset-2">
                the catalog
              </Link>{" "}
              to build your first look.
            </p>
          </div>
        )}

        {/* Outfits grid */}
        {!loading && !error && outfits.length > 0 && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {outfits.map((outfit) => (
              <OutfitCard
                key={outfit.outfit_id}
                outfit={outfit}
                onOpen={() => setSelected(outfit)}
              />
            ))}
          </div>
        )}
      </section>
      {selected && (
        <OutfitDetailModal
          outfit={selected}
          onClose={() => setSelected(null)}
        />
      )}
    </main>
  );
}
