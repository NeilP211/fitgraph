"use client";

/**
 * Page transition template — remounts on every navigation change.
 *
 * Uses Framer Motion for a gentle fade-slide entrance on each route.
 * The ViewTransition shared-element morph (catalog card → builder seed)
 * is handled separately via `view-transition-name` on the images + the
 * experimental.viewTransition Next.js config flag.
 *
 * Reduced-motion: wraps in a plain div (no animation).
 */

import { motion } from "motion/react";
import type { ReactNode } from "react";
import { usePrefersReducedMotion } from "@/components/motion/usePrefersReducedMotion";

export default function Template({ children }: { children: ReactNode }) {
  const reduced = usePrefersReducedMotion();

  if (reduced) {
    return <div>{children}</div>;
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
    >
      {children}
    </motion.div>
  );
}
