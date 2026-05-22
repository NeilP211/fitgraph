"use client";

/**
 * MusicToggle — Phase 3 of "The Show"
 *
 * A small, tasteful ♪ / muted button overlaid on the stage.
 * On-palette (ink / terracotta), keyboard-accessible.
 * Tells the user whether sound is ON or OFF.
 */

import { motion } from "motion/react";

interface MusicToggleProps {
  soundOn: boolean;
  onToggle: () => void;
  /** Extra CSS class for positioning (e.g. "absolute top-2 right-2") */
  className?: string;
}

export default function MusicToggle({ soundOn, onToggle, className = "" }: MusicToggleProps) {
  return (
    <motion.button
      type="button"
      aria-label={soundOn ? "Mute runway music" : "Play runway music"}
      aria-pressed={soundOn}
      title={soundOn ? "Music on — click to mute" : "Music off — click to play"}
      onClick={onToggle}
      whileTap={{ scale: 0.88 }}
      whileHover={{ scale: 1.08 }}
      transition={{ type: "spring", stiffness: 400, damping: 25 }}
      className={[
        "flex items-center justify-center",
        "w-8 h-8 rounded-full",
        "border transition-colors duration-200",
        "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--gold)]",
        "cursor-pointer select-none",
        soundOn
          ? "bg-accent/90 border-accent text-paper hover:bg-accent-deep"
          : "bg-surface/80 border-rule text-ink-soft hover:border-ink-soft hover:text-ink",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
      style={{ backdropFilter: "blur(4px)" }}
    >
      {soundOn ? (
        /* Musical note — sound ON */
        <svg
          width="16"
          height="16"
          viewBox="0 0 16 16"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          aria-hidden="true"
        >
          {/* Eighth note */}
          <path
            d="M10 2v7.27A2.5 2.5 0 1 1 8 7V3.8L6 4.5V11a2 2 0 1 1-2-2V5.5l6-2.5V2z"
            fill="currentColor"
          />
        </svg>
      ) : (
        /* Muted note with slash */
        <svg
          width="16"
          height="16"
          viewBox="0 0 16 16"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          aria-hidden="true"
        >
          {/* Muted note */}
          <path
            d="M10 2v7.27A2.5 2.5 0 1 1 8 7V3.8L6 4.5V11a2 2 0 1 1-2-2V5.5l6-2.5V2z"
            fill="currentColor"
            opacity="0.4"
          />
          {/* Diagonal slash indicating muted */}
          <line
            x1="2"
            y1="13"
            x2="14"
            y2="2"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
          />
        </svg>
      )}
    </motion.button>
  );
}
