"use client";

import { motion } from "motion/react";
import type { Variants } from "motion/react";
import { usePrefersReducedMotion } from "./usePrefersReducedMotion";
import type { ReactNode } from "react";

interface RevealProps {
  children: ReactNode;
  /** Delay in seconds before animation begins */
  delay?: number;
  /** Extra className forwarded to the wrapper element */
  className?: string;
}

/** Custom cubic-bezier ease-out for all reveals */
const EASE_OUT = "easeOut" as const;

/**
 * Reveal — wraps children with a fade + slide-up entrance animation
 * triggered when the element enters the viewport. Supports optional delay
 * for staggered "models walking out" sequences. Degrades gracefully under
 * `prefers-reduced-motion`.
 */
export function Reveal({ children, delay = 0, className }: RevealProps) {
  const reduced = usePrefersReducedMotion();

  if (reduced) {
    // Static render — no transform or opacity animation
    return <div className={className}>{children}</div>;
  }

  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-40px" }}
      transition={{
        duration: 0.45,
        delay,
        ease: EASE_OUT,
      }}
    >
      {children}
    </motion.div>
  );
}

/**
 * RevealGroup — a parent that staggered-reveals its children.
 * Each child should be a <RevealItem> or have its own delay.
 *
 * animateOnMount — when true the reveal plays immediately on mount
 * (for above-the-fold content like the browse grid).  When false (default)
 * the reveal is scroll-triggered via whileInView.
 */
interface RevealGroupProps {
  children: ReactNode;
  stagger?: number; // seconds between each child
  className?: string;
  animateOnMount?: boolean;
}

const groupVariants: Variants = {
  hidden: {},
  visible: (stagger: number) => ({
    transition: { staggerChildren: stagger },
  }),
};

const itemVariants: Variants = {
  hidden: { opacity: 0, y: 16 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.45, ease: EASE_OUT },
  },
};

export function RevealGroup({ children, stagger = 0.07, className, animateOnMount = false }: RevealGroupProps) {
  const reduced = usePrefersReducedMotion();

  if (reduced) {
    return <div className={className}>{children}</div>;
  }

  if (animateOnMount) {
    return (
      <motion.div
        className={className}
        initial="hidden"
        animate="visible"
        custom={stagger}
        variants={groupVariants}
      >
        {children}
      </motion.div>
    );
  }

  return (
    <motion.div
      className={className}
      initial="hidden"
      whileInView="visible"
      viewport={{ once: true, margin: "-40px" }}
      custom={stagger}
      variants={groupVariants}
    >
      {children}
    </motion.div>
  );
}

export function RevealItem({ children, className }: { children: ReactNode; className?: string }) {
  const reduced = usePrefersReducedMotion();

  if (reduced) {
    return <div className={className}>{children}</div>;
  }

  return (
    <motion.div className={className} variants={itemVariants}>
      {children}
    </motion.div>
  );
}
