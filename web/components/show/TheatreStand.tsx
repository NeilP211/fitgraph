"use client";

import { useState } from "react";
import { motion } from "motion/react";

/**
 * A single seated patron: a head-and-shoulders silhouette over a seat back.
 * Clickable to cheer (jumps + fires onCheer).
 */
function SeatedPatron({
  size,
  opacity,
  onCheer,
}: {
  size: number;
  opacity: number;
  onCheer?: () => void;
}) {
  const [cheering, setCheering] = useState(false);
  const cheer = () => {
    if (cheering) return;
    setCheering(true);
    onCheer?.();
    setTimeout(() => setCheering(false), 650);
  };
  return (
    <motion.button
      type="button"
      onClick={cheer}
      aria-label="Audience member, click to cheer"
      title="Click to cheer"
      animate={cheering ? { y: [0, -7, 0] } : { y: 0 }}
      transition={{ duration: 0.5, ease: "easeOut" }}
      tabIndex={-1}
      className="relative flex shrink-0 cursor-pointer flex-col items-center border-0 bg-transparent p-0"
      style={{ width: size, opacity }}
    >
      {/* Person: head + shoulders */}
      <svg viewBox="0 0 32 28" className="w-[80%]" aria-hidden="true" style={{ color: "var(--ink)" }}>
        <ellipse cx="16" cy="8.5" rx="5.5" ry="6.2" fill="currentColor" />
        <path d="M3.5 28 Q3.5 16 16 16 Q28.5 16 28.5 28 Z" fill="currentColor" />
      </svg>
      {/* Seat back */}
      <div
        style={{
          width: "100%",
          height: size * 0.4,
          marginTop: -1,
          background: "var(--rule)",
          opacity: 0.42,
          borderRadius: "4px 4px 1px 1px",
        }}
      />
    </motion.button>
  );
}

function Row({
  count,
  size,
  opacity,
  onCheer,
}: {
  count: number;
  size: number;
  opacity: number;
  onCheer?: () => void;
}) {
  return (
    <div className="flex items-end justify-center gap-[3px]">
      {Array.from({ length: count }).map((_, i) => (
        <SeatedPatron key={i} size={size} opacity={opacity} onCheer={onCheer} />
      ))}
    </div>
  );
}

function Rail() {
  return <div className="h-px w-full" style={{ background: "var(--rule)", opacity: 0.32 }} aria-hidden="true" />;
}

/**
 * Tiered theatre seating that flanks one side of the runway and fills the side
 * space. Three levels (upper balcony, middle, front) separated by rails, rows
 * growing larger and brighter toward the front. Bottom-aligned and faded into
 * the dark up top so the back rows recede.
 */
export default function TheatreStand({ onCheer }: { side?: "left" | "right"; onCheer?: () => void }) {
  return (
    <div
      className="flex h-full flex-col justify-end gap-3"
      style={{
        WebkitMaskImage: "linear-gradient(to top, black 70%, transparent 100%)",
        maskImage: "linear-gradient(to top, black 70%, transparent 100%)",
      }}
      aria-label="Audience"
      role="group"
    >
      {/* Upper balcony (back: small, dim) */}
      <div className="flex flex-col gap-1">
        <Row count={8} size={17} opacity={0.3} onCheer={onCheer} />
        <Row count={8} size={19} opacity={0.38} onCheer={onCheer} />
      </div>
      <Rail />
      {/* Middle tier */}
      <div className="flex flex-col gap-1">
        <Row count={7} size={23} opacity={0.5} onCheer={onCheer} />
        <Row count={7} size={27} opacity={0.6} onCheer={onCheer} />
        <Row count={6} size={31} opacity={0.7} onCheer={onCheer} />
      </div>
      <Rail />
      {/* Front tier (closest: largest, brightest) */}
      <div className="flex flex-col gap-1">
        <Row count={6} size={36} opacity={0.8} onCheer={onCheer} />
        <Row count={5} size={42} opacity={0.92} onCheer={onCheer} />
      </div>
    </div>
  );
}
