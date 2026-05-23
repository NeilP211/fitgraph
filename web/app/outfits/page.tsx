"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import { AnimatePresence, motion } from "motion/react";
import { getOutfits, deleteOutfit, imageUrl } from "@/lib/api";
import type { OutfitHistoryEntry } from "@/lib/api";
import Link from "next/link";
import { Reveal, RevealGroup, RevealItem } from "@/components/motion/Reveal";
import { usePrefersReducedMotion } from "@/components/motion/usePrefersReducedMotion";
import FashionBand from "@/components/FashionBand";

const DEMO_USER_ID = 1;

/** A small clothes-hanger hook drawn above each garment. */
function Hanger() {
  return (
    <svg
      width="22"
      height="16"
      viewBox="0 0 22 16"
      fill="none"
      stroke="#EFE7D4"
      strokeWidth="1.4"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className="mb-[-1px]"
    >
      {/* hook */}
      <path d="M11 6c0-3 3-3 3-1" />
      {/* shoulders */}
      <path d="M3 14 L11 6 L19 14" />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Closet tile — a wardrobe whose doors crack open on hover/focus
// ---------------------------------------------------------------------------

function ClosetTile({
  outfit,
  index,
  onOpen,
  onDelete,
}: {
  outfit: OutfitHistoryEntry;
  index: number;
  onOpen: () => void;
  onDelete: () => void;
}) {
  // A couple of pieces peek through the gap when the doors part.
  const peek = outfit.item_ids.slice(0, 3);
  const count = outfit.item_ids.length;
  const lookLabel = `LOOK ${String(index + 1).padStart(2, "0")}`;
  const name = outfit.outfit_name || `Outfit #${outfit.outfit_id}`;

  return (
    <div className="relative group/card">
      <button
        type="button"
        onClick={onOpen}
        aria-label={`Open ${name} — ${count} piece${count !== 1 ? "s" : ""}`}
        className="closet block w-full aspect-[3/4] overflow-hidden rounded-sm hover:-translate-y-0.5 transition-transform duration-300 cursor-pointer"
      >
        {/* Interior — peeks through the parting doors */}
        <div className="closet-interior">
          <div className="closet-rail" />
          <div className="absolute inset-x-0 top-[22%] bottom-[20%] flex items-start justify-center gap-2 px-4">
            {peek.map((id) => (
              <div
                key={id}
                className="relative w-1/3 max-w-[42%] aspect-[3/4] overflow-hidden rounded-[2px] border border-black/20 shadow-md"
              >
                <Image
                  src={imageUrl(id)}
                  alt=""
                  fill
                  sizes="12vw"
                  className="object-cover"
                  unoptimized
                />
              </div>
            ))}
          </div>
        </div>

        {/* Doors */}
        <div className="closet-doors">
          <div className="closet-door closet-door-left">
            <span className="closet-handle closet-handle-left" />
          </div>
          <div className="closet-door closet-door-right">
            <span className="closet-handle closet-handle-right" />
          </div>
        </div>

        {/* Brass nameplate */}
        <div className="closet-plate">
          <p
            className="text-[9px] uppercase tracking-[0.22em] text-ink/70"
            style={{ fontFamily: "var(--font-display-var), serif" }}
          >
            {lookLabel}
          </p>
          <p
            className="mt-0.5 text-sm font-medium text-ink truncate"
            style={{ fontFamily: "var(--font-body-var), serif" }}
          >
            {name}
          </p>
          <p
            className="mt-0.5 text-[9px] uppercase tracking-[0.14em] text-ink/60"
            style={{ fontFamily: "var(--font-body-var), serif" }}
          >
            {count} piece{count !== 1 ? "s" : ""}
          </p>
        </div>
      </button>

      {/* Delete — top-right, on hover */}
      <button
        type="button"
        aria-label={`Delete ${name}`}
        onClick={(e) => {
          e.stopPropagation();
          onDelete();
        }}
        className="absolute top-2 right-2 z-10 flex h-7 w-7 items-center justify-center rounded-sm bg-surface/90 border border-rule text-ink-soft opacity-0 group-hover/card:opacity-100 hover:bg-accent hover:text-paper hover:border-accent transition-all duration-200"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="13"
          height="13"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <polyline points="3 6 5 6 21 6" />
          <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
          <path d="M10 11v6" />
          <path d="M14 11v6" />
          <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
        </svg>
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Closet interior modal — pieces hanging on a rail, with a door-swing reveal
// ---------------------------------------------------------------------------

function ClosetInteriorModal({
  outfit,
  index,
  onClose,
  onDelete,
}: {
  outfit: OutfitHistoryEntry;
  index: number;
  onClose: () => void;
  onDelete: () => void;
}) {
  const reduced = usePrefersReducedMotion();
  const count = outfit.item_ids.length;
  const lookLabel = `LOOK ${String(index + 1).padStart(2, "0")}`;
  const name = outfit.outfit_name || `Outfit #${outfit.outfit_id}`;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <motion.div
      role="dialog"
      aria-modal="true"
      aria-label={name}
      onClick={onClose}
      initial={reduced ? false : { opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.2, ease: "easeOut" }}
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink/60 p-4"
    >
      <motion.div
        onClick={(e) => e.stopPropagation()}
        initial={reduced ? false : { scale: 0.96, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.96, opacity: 0 }}
        transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
        style={{ perspective: "1600px" }}
        className="relative max-h-[86vh] w-full max-w-3xl overflow-hidden rounded-sm border border-rule"
      >
        {/* ── Interior ── */}
        <div
          className="closet-modal-interior max-h-[86vh] overflow-y-auto p-6"
          style={{
            background:
              "radial-gradient(140% 80% at 50% -10%, rgba(239,231,212,0.16), transparent 60%), linear-gradient(180deg, #161310 0%, #211c16 100%)",
          }}
        >
          {/* Header on the interior back-panel */}
          <div className="flex items-start justify-between gap-4">
            <div>
              <p
                className="text-[10px] uppercase tracking-[0.22em] text-[#EFE7D4]"
                style={{ fontFamily: "var(--font-display-var), serif" }}
              >
                {lookLabel}
              </p>
              <h2
                className="mt-1 text-2xl uppercase tracking-[0.1em] text-paper"
                style={{ fontFamily: "var(--font-display-var), serif" }}
              >
                {name}
              </h2>
              <p
                className="mt-1 text-[10px] uppercase tracking-[0.14em] text-paper/60"
                style={{ fontFamily: "var(--font-body-var), serif" }}
              >
                {count} piece{count !== 1 ? "s" : ""} · tap a piece to restyle
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={onDelete}
                aria-label="Delete this look"
                className="flex items-center gap-1.5 rounded-sm border border-[#EFE7D4]/40 px-3 py-1.5 text-[10px] uppercase tracking-[0.12em] text-paper/80 transition-colors hover:border-[#EFE7D4] hover:text-paper"
                style={{ fontFamily: "var(--font-body-var), serif" }}
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="11"
                  height="11"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                >
                  <polyline points="3 6 5 6 21 6" />
                  <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
                  <path d="M10 11v6" />
                  <path d="M14 11v6" />
                  <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
                </svg>
                Delete
              </button>
              <button
                type="button"
                onClick={onClose}
                aria-label="Close"
                className="px-2 text-2xl leading-none text-paper/70 hover:text-paper"
              >
                ×
              </button>
            </div>
          </div>

          {/* Hanging rail */}
          <div className="relative mt-6 mb-2">
            <div className="h-0.5 w-full rounded-full bg-gradient-to-r from-transparent via-[#EFE7D4]/70 to-transparent" />
          </div>

          {/* Garments on hangers */}
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4">
            {outfit.item_ids.map((id) => (
              <Link
                key={id}
                href={`/build/${encodeURIComponent(id)}`}
                className="group flex flex-col items-center"
              >
                <Hanger />
                <div className="group relative block aspect-[3/4] w-full overflow-hidden rounded-sm border border-[#EFE7D4]/30 bg-paper shadow-lg transition-transform duration-300 group-hover:-translate-y-0.5">
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
                </div>
              </Link>
            ))}
          </div>
        </div>

        {/* ── Door-swing reveal (decorative, motion only) ── */}
        {!reduced && (
          <div
            className="pointer-events-none absolute inset-0"
            style={{ perspective: "1600px", transformStyle: "preserve-3d" }}
            aria-hidden="true"
          >
            {[
              { side: "left", origin: "left center", to: -118 },
              { side: "right", origin: "right center", to: 118 },
            ].map((d) => (
              <motion.div
                key={d.side}
                initial={{ rotateY: 0, opacity: 1 }}
                animate={{ rotateY: d.to, opacity: 0 }}
                transition={{ duration: 0.7, delay: 0.12, ease: [0.22, 1, 0.36, 1] }}
                style={{
                  position: "absolute",
                  top: 0,
                  bottom: 0,
                  [d.side]: 0,
                  width: "50%",
                  transformOrigin: d.origin,
                  backfaceVisibility: "hidden",
                  background: "var(--surface)",
                  borderRight: d.side === "left" ? "1px solid var(--rule)" : undefined,
                  borderLeft: d.side === "right" ? "1px solid var(--rule)" : undefined,
                  boxShadow:
                    "inset 0 0 0 10px var(--surface), inset 0 0 0 11px rgba(207,193,164,0.7)",
                }}
              />
            ))}
          </div>
        )}
      </motion.div>
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function OutfitsPage() {
  const [outfits, setOutfits] = useState<OutfitHistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<{
    outfit: OutfitHistoryEntry;
    index: number;
  } | null>(null);

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

  async function handleDelete(outfitId: number) {
    if (!window.confirm("Delete this look?")) return;
    try {
      await deleteOutfit(outfitId, DEMO_USER_ID);
      setOutfits((prev) => prev.filter((o) => o.outfit_id !== outfitId));
      if (selected?.outfit.outfit_id === outfitId) setSelected(null);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to delete outfit.");
    }
  }

  return (
    <main className="relative min-h-screen bg-paper">
      <div className="relative isolate overflow-hidden">
        <FashionBand text="WARDROBE" top="30%" />

        <section className="relative z-10 mx-auto max-w-6xl px-6 pt-10 pb-16">
          {/* Page header: centered title with a + to start a new outfit */}
          <Reveal>
            <div className="relative mb-8 pt-2">
              <h1
                className="text-center text-3xl font-semibold uppercase tracking-[0.12em] text-ink"
                style={{ fontFamily: "var(--font-display-var), serif" }}
              >
                Your Wardrobe
              </h1>
              <Link
                href="/"
                aria-label="New outfit"
                title="New outfit"
                className="absolute right-0 top-1/2 flex h-10 w-10 -translate-y-1/2 items-center justify-center rounded-full bg-accent text-2xl leading-none text-paper transition-colors hover:bg-accent-deep"
                style={{ fontFamily: "var(--font-body-var), serif" }}
              >
                +
              </Link>
            </div>
          </Reveal>
          <div className="hr-rule mb-8" />

          {/* Loading skeleton */}
          {loading && (
            <div
              aria-busy="true"
              aria-label="Loading wardrobe"
              className="grid grid-cols-2 gap-5 sm:grid-cols-3 lg:grid-cols-4"
            >
              {Array.from({ length: 8 }).map((_, i) => (
                <div
                  key={i}
                  className="aspect-[3/4] animate-pulse rounded-sm bg-surface border border-rule"
                />
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
                Your Wardrobe Is Empty
              </p>
              <p
                className="text-sm text-ink-soft"
                style={{ fontFamily: "var(--font-body-var), serif" }}
              >
                Head to{" "}
                <Link
                  href="/"
                  className="text-accent underline underline-offset-2"
                >
                  the catalog
                </Link>{" "}
                to build your first look.
              </p>
            </div>
          )}

          {/* Closet grid */}
          {!loading && !error && outfits.length > 0 && (
            <RevealGroup
              stagger={0.07}
              className="grid grid-cols-2 gap-5 sm:grid-cols-3 lg:grid-cols-4"
            >
              {outfits.map((outfit, idx) => (
                <RevealItem key={outfit.outfit_id}>
                  <ClosetTile
                    outfit={outfit}
                    index={idx}
                    onOpen={() => setSelected({ outfit, index: idx })}
                    onDelete={() => handleDelete(outfit.outfit_id)}
                  />
                </RevealItem>
              ))}
            </RevealGroup>
          )}
        </section>
      </div>

      {/* Modal */}
      <AnimatePresence>
        {selected && (
          <ClosetInteriorModal
            outfit={selected.outfit}
            index={selected.index}
            onClose={() => setSelected(null)}
            onDelete={() => handleDelete(selected.outfit.outfit_id)}
          />
        )}
      </AnimatePresence>
    </main>
  );
}
