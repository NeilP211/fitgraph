"use client";

import { useRef } from "react";
import { motion, useScroll, useTransform } from "motion/react";
import { usePrefersReducedMotion } from "./motion/usePrefersReducedMotion";

/**
 * RunwayHero — a CSS 3D perspective catwalk backdrop for the browse home.
 *
 * Visual anatomy:
 *  - Outer wrapper: CSS `perspective` that sets the vanishing point.
 *  - Floor strip: `rotateX` + trapezoid illusion creates the receding catwalk.
 *  - Center seam: a hairline running the length of the floor.
 *  - Spotlight cones: two radial-gradient glows framing the runway head.
 *  - Editorial text (title + rule + script) overlaid at the runway head.
 *  - Subtle scroll parallax on floor + spotlights (reduced-motion: static).
 *
 * Palette: stays entirely within --paper, --surface, --ink, --gold, --rule.
 */
export default function RunwayHero() {
  const reduced = usePrefersReducedMotion();
  const containerRef = useRef<HTMLDivElement>(null);

  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ["start start", "end start"],
  });

  // Very gentle parallax — floor lifts 30px, spotlights drift 15px
  const floorY = useTransform(scrollYProgress, [0, 1], [0, reduced ? 0 : 30]);
  const spotY = useTransform(scrollYProgress, [0, 1], [0, reduced ? 0 : 15]);

  return (
    <div
      ref={containerRef}
      className="relative w-full overflow-hidden"
      style={{ height: "340px" }}
      aria-hidden="true" // decorative; editorial text below carries semantics
    >
      {/* ── Background warm stage-light gradient ── */}
      <div
        className="absolute inset-0"
        style={{
          background:
            "linear-gradient(180deg, var(--paper) 0%, #EBE0C8 55%, #DDD0B0 100%)",
        }}
      />

      {/* ── Spotlight cones (radial-gradient glows) ── */}
      <motion.div
        className="absolute inset-0 pointer-events-none"
        style={{ y: spotY }}
      >
        {/* Left spotlight */}
        <div
          style={{
            position: "absolute",
            top: 0,
            left: "10%",
            width: "45%",
            height: "100%",
            background:
              "radial-gradient(ellipse 60% 80% at 30% 0%, rgba(178,138,78,0.18) 0%, transparent 70%)",
          }}
        />
        {/* Right spotlight */}
        <div
          style={{
            position: "absolute",
            top: 0,
            right: "10%",
            width: "45%",
            height: "100%",
            background:
              "radial-gradient(ellipse 60% 80% at 70% 0%, rgba(178,138,78,0.18) 0%, transparent 70%)",
          }}
        />
        {/* Center warm bloom at vanishing point */}
        <div
          style={{
            position: "absolute",
            top: "15%",
            left: "50%",
            transform: "translateX(-50%)",
            width: "50%",
            height: "60%",
            background:
              "radial-gradient(ellipse 70% 60% at 50% 0%, rgba(239,231,212,0.55) 0%, transparent 75%)",
          }}
        />
      </motion.div>

      {/* ── Perspective runway floor ── */}
      <motion.div
        className="absolute bottom-0 left-0 right-0"
        style={{
          perspective: "600px",
          perspectiveOrigin: "50% 0%",
          y: floorY,
          height: "75%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "flex-end",
        }}
      >
        {/* Floor plane */}
        <div
          style={{
            width: "100%",
            height: "100%",
            transform: "rotateX(52deg)",
            transformOrigin: "50% 100%",
            position: "relative",
            overflow: "hidden",
            borderTop: "1px solid rgba(178,138,78,0.35)",
          }}
        >
          {/* Floor fill */}
          <div
            style={{
              position: "absolute",
              inset: 0,
              background:
                "linear-gradient(180deg, rgba(221,208,176,0.55) 0%, rgba(239,231,212,0.25) 100%)",
            }}
          />

          {/* Center seam */}
          <div
            style={{
              position: "absolute",
              top: 0,
              bottom: 0,
              left: "50%",
              width: "1px",
              transform: "translateX(-50%)",
              background:
                "linear-gradient(180deg, rgba(178,138,78,0.5) 0%, rgba(178,138,78,0.1) 100%)",
            }}
          />

          {/* Subtle lateral guide lines */}
          {[25, 75].map((pct) => (
            <div
              key={pct}
              style={{
                position: "absolute",
                top: 0,
                bottom: 0,
                left: `${pct}%`,
                width: "1px",
                background:
                  "linear-gradient(180deg, rgba(178,138,78,0.2) 0%, transparent 80%)",
              }}
            />
          ))}
        </div>
      </motion.div>

      {/* ── Fade vignette at bottom so floor blends into content below ── */}
      <div
        className="absolute bottom-0 left-0 right-0 pointer-events-none"
        style={{
          height: "80px",
          background:
            "linear-gradient(to bottom, transparent, var(--paper))",
        }}
      />

      {/* ── Fade vignette at sides ── */}
      <div
        className="absolute inset-y-0 left-0 w-16 pointer-events-none"
        style={{
          background: "linear-gradient(to right, var(--paper), transparent)",
        }}
      />
      <div
        className="absolute inset-y-0 right-0 w-16 pointer-events-none"
        style={{
          background: "linear-gradient(to left, var(--paper), transparent)",
        }}
      />
    </div>
  );
}
