"use client";

import { useRef } from "react";
import Image from "next/image";
import { motion, useScroll, useTransform } from "motion/react";
import { usePrefersReducedMotion } from "./motion/usePrefersReducedMotion";

const BASE_URL =
  typeof window !== "undefined"
    ? (process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "http://localhost:8011")
    : (process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "http://localhost:8011");

function catalogImg(id: string) {
  return `${BASE_URL}/images/${encodeURIComponent(id)}`;
}

/**
 * A handful of hardcoded item IDs used as runway "models".
 * These are real items from the catalog; a mix of shoes + tops.
 */
const RUNWAY_ITEMS = [
  { id: "100094985", x: "18%", delay: 0 },
  { id: "100116756", x: "38%", delay: 0.15 },
  { id: "100058266", x: "58%", delay: 0.08 },
  { id: "100305898", x: "76%", delay: 0.22 },
];

/**
 * Marquee text repeated twice (CSS infinite loop trick: two identical halves,
 * translate from 0 → -50% so seam is invisible).
 */
const MARQUEE_TEXT =
  "FITGRAPH · HIGH FASHION · FALL / WINTER · ✦ ";

/**
 * RunwayHero — a CSS 3D perspective catwalk backdrop for the browse home.
 *
 * Visual anatomy:
 *  - Scrolling marquee band (sepia text on cream, fashion-week energy).
 *  - Background warm gold stage-light gradient (no pink).
 *  - Spotlight cones in warm gold/sepia tones.
 *  - Perspective runway floor with guide lines.
 *  - Catalog item thumbnails gently floating on the catwalk.
 *  - Editorial text overlay (title + rule + script).
 *  - Subtle scroll parallax on floor + spotlights.
 *
 * Palette: --paper, --surface, --ink, --gold, --rule (no pink).
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
    <>
      {/* ── Marquee band — fashion-week energy ── */}
      <div
        className="relative w-full overflow-hidden border-y"
        style={{
          borderColor: "var(--rule)",
          background: "var(--paper)",
          height: "34px",
        }}
        aria-hidden="true"
      >
        {/* Top hairline already handled by border-y */}
        <div
          className="marquee-track absolute inset-y-0 flex items-center"
          style={{ top: 0 }}
        >
          {/* Two identical copies so the infinite scroll seam is invisible */}
          {[0, 1].map((n) => (
            <span
              key={n}
              className="whitespace-nowrap px-4 text-[11px] uppercase tracking-[0.2em]"
              style={{
                fontFamily: "var(--font-display-var), serif",
                color: "var(--ink-soft)",
              }}
            >
              {Array.from({ length: 6 }).fill(MARQUEE_TEXT).join("")}
            </span>
          ))}
        </div>
      </div>

      {/* ── Catwalk stage ── */}
      <div
        ref={containerRef}
        className="relative w-full overflow-hidden"
        style={{ height: "340px" }}
        aria-hidden="true"
      >
        {/* Background warm stage-light gradient — gold/sepia, no pink */}
        <div
          className="absolute inset-0"
          style={{
            background:
              "linear-gradient(180deg, #F5EDD8 0%, #EAD9B0 55%, #DCC898 100%)",
          }}
        />

        {/* ── Spotlight cones — warm gold/sepia only ── */}
        <motion.div
          className="absolute inset-0 pointer-events-none"
          style={{ y: spotY }}
        >
          {/* Left spotlight — warm gold */}
          <div
            style={{
              position: "absolute",
              top: 0,
              left: "5%",
              width: "50%",
              height: "100%",
              background:
                "radial-gradient(ellipse 65% 85% at 25% 0%, rgba(178,138,78,0.28) 0%, transparent 68%)",
            }}
          />
          {/* Right spotlight — warm gold */}
          <div
            style={{
              position: "absolute",
              top: 0,
              right: "5%",
              width: "50%",
              height: "100%",
              background:
                "radial-gradient(ellipse 65% 85% at 75% 0%, rgba(178,138,78,0.28) 0%, transparent 68%)",
            }}
          />
          {/* Center warm bloom at vanishing point */}
          <div
            style={{
              position: "absolute",
              top: "10%",
              left: "50%",
              transform: "translateX(-50%)",
              width: "55%",
              height: "65%",
              background:
                "radial-gradient(ellipse 75% 65% at 50% 0%, rgba(220,200,152,0.7) 0%, transparent 72%)",
            }}
          />
          {/* Sepia vignette at edges */}
          <div
            style={{
              position: "absolute",
              inset: 0,
              background:
                "radial-gradient(ellipse 140% 100% at 50% 0%, transparent 50%, rgba(150,120,70,0.12) 100%)",
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
              borderTop: "1px solid rgba(178,138,78,0.5)",
            }}
          >
            {/* Floor fill — warm sepia */}
            <div
              style={{
                position: "absolute",
                inset: 0,
                background:
                  "linear-gradient(180deg, rgba(210,185,140,0.6) 0%, rgba(235,220,185,0.3) 100%)",
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
                  "linear-gradient(180deg, rgba(178,138,78,0.65) 0%, rgba(178,138,78,0.1) 100%)",
              }}
            />

            {/* Lateral guide lines */}
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
                    "linear-gradient(180deg, rgba(178,138,78,0.3) 0%, transparent 75%)",
                }}
              />
            ))}

            {/* Additional runway edge lines for definition */}
            {[12, 88].map((pct) => (
              <div
                key={pct}
                style={{
                  position: "absolute",
                  top: 0,
                  bottom: 0,
                  left: `${pct}%`,
                  width: "1px",
                  background:
                    "linear-gradient(180deg, rgba(178,138,78,0.15) 0%, transparent 60%)",
                }}
              />
            ))}
          </div>
        </motion.div>

        {/* ── Catalog item floats on catwalk ── */}
        {!reduced &&
          RUNWAY_ITEMS.map((item) => (
            <motion.div
              key={item.id}
              className="absolute pointer-events-none"
              style={{
                bottom: "28%",
                left: item.x,
                width: "64px",
                height: "64px",
                transform: "translateX(-50%)",
              }}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 0.82, y: [10, 0, 6, 0] }}
              transition={{
                opacity: { duration: 0.6, delay: item.delay },
                y: {
                  delay: item.delay + 0.6,
                  duration: 3.5,
                  repeat: Infinity,
                  ease: "easeInOut",
                },
              }}
            >
              <div
                className="relative w-full h-full overflow-hidden rounded-sm shadow-md"
                style={{
                  border: "1px solid rgba(178,138,78,0.4)",
                  background: "var(--surface)",
                }}
              >
                <Image
                  src={catalogImg(item.id)}
                  alt=""
                  fill
                  sizes="64px"
                  className="object-cover"
                  unoptimized
                />
              </div>
            </motion.div>
          ))}

        {/* ── Fade vignette at bottom — floor blends into content below ── */}
        <div
          className="absolute bottom-0 left-0 right-0 pointer-events-none"
          style={{
            height: "90px",
            background: "linear-gradient(to bottom, transparent, var(--paper))",
          }}
        />

        {/* ── Side vignettes ── */}
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
    </>
  );
}
