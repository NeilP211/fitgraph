"use client";

import { useEffect, useRef, useState } from "react";
import { useInView, animate } from "motion/react";
import { usePrefersReducedMotion } from "./usePrefersReducedMotion";

interface CountUpProps {
  /** The final numeric value to animate toward */
  value: number;
  /** Optional suffix rendered after the number, e.g. "%" */
  suffix?: string;
  /** Number of decimal places to display */
  decimals?: number;
  /** Animation duration in seconds (default 0.8) */
  duration?: number;
  /** Extra className for the wrapper span */
  className?: string;
}

/**
 * CountUp — animates a number from 0 → value when it enters the viewport.
 * Intended for match-score badges and stat callouts. Degrades to the final
 * value immediately under `prefers-reduced-motion`.
 */
export function CountUp({
  value,
  suffix = "",
  decimals = 0,
  duration = 0.8,
  className,
}: CountUpProps) {
  const reduced = usePrefersReducedMotion();
  const ref = useRef<HTMLSpanElement>(null);
  const isInView = useInView(ref, { once: true });
  // Start at `value` when reduced-motion is on so no update is needed
  const [displayed, setDisplayed] = useState(() => (reduced ? value : 0));

  useEffect(() => {
    // Keep displayed in sync if `value` changes while reduced-motion is active
    if (reduced) return;
    if (!isInView) return;

    const controls = animate(0, value, {
      duration,
      ease: [0.22, 1, 0.36, 1],
      onUpdate: (v) => setDisplayed(v),
    });

    return () => controls.stop();
  }, [isInView, value, reduced, duration]);

  // Ensure final value is always correct under reduced-motion
  const finalDisplayed = reduced ? value : displayed;

  return (
    <span ref={ref} className={className}>
      {finalDisplayed.toFixed(decimals)}
      {suffix}
    </span>
  );
}
