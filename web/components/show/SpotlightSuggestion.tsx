"use client";

import Image from "next/image";
import { AnimatePresence, motion } from "motion/react";
import { imageUrl, type SuggestionItem } from "@/lib/api";

function label(cat: string) {
  return cat.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

/**
 * Presents exactly ONE candidate for the active slot under the spotlight.
 * ✗ rejects (parent advances to the next-best), ✓ accepts. When the ranked
 * pool is spent, shows a quiet "no more" state.
 */
export default function SpotlightSuggestion({
  slot,
  candidate,
  exhausted,
  onAccept,
  onReject,
}: {
  slot: string;
  candidate: SuggestionItem | null;
  exhausted: boolean;
  onAccept: () => void;
  onReject: () => void;
}) {
  if (exhausted) {
    return (
      <p
        role="status"
        className="py-10 text-center text-sm text-[#f4ecd8]/60"
        style={{ fontFamily: "var(--font-body-var), serif" }}
      >
        No more {label(slot)} pieces — pick another slot.
      </p>
    );
  }
  if (!candidate) return null;

  const match = Math.max(0, Math.min(100, Math.round(candidate.score * 100)));

  return (
    <div className="flex flex-col items-center gap-4" aria-live="polite">
      <span
        className="text-[11px] uppercase tracking-[0.2em] text-[#d4af6e]"
        style={{ fontFamily: "var(--font-display-var), serif" }}
      >
        {label(slot)} · {match}% match
      </span>

      <AnimatePresence mode="wait">
        <motion.div
          key={candidate.item_id}
          initial={{ opacity: 0, x: 40 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -40 }}
          transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
          className="relative aspect-square w-56 overflow-hidden rounded-sm border border-[#f4ecd8]/15 bg-black/40"
        >
          <Image
            src={imageUrl(candidate.item_id)}
            alt={candidate.title ?? "Suggested item"}
            fill
            sizes="224px"
            className="object-cover"
            unoptimized
          />
        </motion.div>
      </AnimatePresence>

      <p
        className="max-w-xs truncate text-center text-sm text-[#f4ecd8]/90"
        style={{ fontFamily: "var(--font-body-var), serif" }}
      >
        {candidate.title || "Untitled"}
      </p>

      <div className="flex items-center gap-4">
        <button
          onClick={onReject}
          aria-label={`Show another ${label(slot)}`}
          className="h-12 w-12 rounded-full border border-[#f4ecd8]/30 text-xl text-[#f4ecd8]/80 transition-colors hover:border-[#f4ecd8] hover:text-[#f4ecd8]"
        >
          ✗
        </button>
        <button
          onClick={onAccept}
          aria-label={`Accept this ${label(slot)}`}
          className="h-14 w-14 rounded-full bg-[#d4af6e] text-2xl text-[#0a0a0b] transition-colors hover:bg-[#e6c486]"
        >
          ✓
        </button>
      </div>
    </div>
  );
}
