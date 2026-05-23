"use client";

import { motion } from "motion/react";

function label(cat: string) {
  return cat.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

/**
 * The slot dock fixed to the bottom of the theater. One pill per element type;
 * the user taps any of them, in any order, to bring that slot into the
 * spotlight. Filled slots show ✓; the active slot is gold.
 */
export default function SlotPicker({
  slots,
  chosen,
  activeSlot,
  onPick,
}: {
  slots: string[];
  chosen: Record<string, string | null>;
  activeSlot: string | null;
  onPick: (slot: string) => void;
}) {
  return (
    <div className="fixed inset-x-0 bottom-0 z-20 border-t border-[#f4ecd8]/15 bg-[#0a0a0b]/85 backdrop-blur-sm">
      <div className="mx-auto flex max-w-3xl flex-wrap items-center justify-center gap-2 px-4 py-3">
        {slots.map((slot) => {
          const filled = !!chosen[slot];
          const active = slot === activeSlot;
          return (
            <motion.button
              key={slot}
              whileTap={{ scale: 0.95 }}
              onClick={() => onPick(slot)}
              aria-label={filled ? `Swap ${label(slot)}` : `Add ${label(slot)}`}
              aria-pressed={active}
              className={[
                "rounded-full border px-4 py-1.5 text-[11px] uppercase tracking-[0.14em] transition-colors",
                active
                  ? "border-[#d4af6e] text-[#d4af6e]"
                  : filled
                    ? "border-[#f4ecd8]/40 text-[#f4ecd8]/90"
                    : "border-[#f4ecd8]/20 text-[#f4ecd8]/60 hover:text-[#f4ecd8]",
              ].join(" ")}
              style={{ fontFamily: "var(--font-display-var), serif" }}
            >
              {filled ? "✓ " : ""}
              {label(slot)}
            </motion.button>
          );
        })}
      </div>
    </div>
  );
}
