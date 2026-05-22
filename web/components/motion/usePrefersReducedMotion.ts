"use client";

import { useReducedMotion } from "motion/react";

/**
 * Returns `true` when the user has requested reduced motion.
 * All animated components should check this and skip/instant transitions
 * when true. Wraps motion's built-in hook so we have a single import point.
 */
export function usePrefersReducedMotion(): boolean {
  return useReducedMotion() ?? false;
}
