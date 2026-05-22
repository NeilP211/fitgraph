"use client";

import { useState, useCallback, useId } from "react";
import { motion, AnimatePresence } from "motion/react";
import { usePrefersReducedMotion } from "@/components/motion/usePrefersReducedMotion";

// ---------------------------------------------------------------------------
// Audience figure SVG variants
// 5 distinct silhouette "archetypes" — head + shoulders + torso shapes
// All drawn in a 40×72 viewBox so we can scale them uniformly.
// ---------------------------------------------------------------------------

type FigureVariant = 0 | 1 | 2 | 3 | 4;

/** Returns an SVG path set for a given variant (head+shoulders silhouette). */
function FigureSilhouette({ variant }: { variant: FigureVariant }) {
  // Each variant: slightly different head size, shoulder width, torso taper
  const variants: Record<FigureVariant, React.ReactElement> = {
    // Variant 0 — average build
    0: (
      <>
        {/* Head */}
        <ellipse cx="20" cy="14" rx="7" ry="9" fill="currentColor" />
        {/* Neck */}
        <rect x="17" y="22" width="6" height="5" rx="2" fill="currentColor" />
        {/* Shoulders + torso */}
        <path d="M2 27 Q4 24 10 24 L17 26 L20 27 L23 26 L30 24 Q36 24 38 27 L36 52 Q30 56 20 56 Q10 56 4 52 Z" fill="currentColor" />
      </>
    ),
    // Variant 1 — broader shoulders
    1: (
      <>
        <ellipse cx="20" cy="13" rx="6.5" ry="8.5" fill="currentColor" />
        <rect x="17" y="21" width="6" height="4" rx="2" fill="currentColor" />
        <path d="M0 26 Q3 22 11 23 L17 25 L20 26 L23 25 L29 23 Q37 22 40 26 L38 52 Q31 57 20 57 Q9 57 2 52 Z" fill="currentColor" />
      </>
    ),
    // Variant 2 — petite / narrower
    2: (
      <>
        <ellipse cx="20" cy="14" rx="6" ry="8" fill="currentColor" />
        <rect x="17.5" y="22" width="5" height="5" rx="2" fill="currentColor" />
        <path d="M6 28 Q8 25 13 25 L17 27 L20 28 L23 27 L27 25 Q32 25 34 28 L33 52 Q27 56 20 56 Q13 56 7 52 Z" fill="currentColor" />
      </>
    ),
    // Variant 3 — taller head, lean torso
    3: (
      <>
        <ellipse cx="20" cy="13" rx="6" ry="10" fill="currentColor" />
        <rect x="17.5" y="22" width="5" height="5" rx="2" fill="currentColor" />
        <path d="M5 27 Q7 24 12 24 L17 26 L20 27 L23 26 L28 24 Q33 24 35 27 L34 56 Q28 60 20 60 Q12 60 6 56 Z" fill="currentColor" />
      </>
    ),
    // Variant 4 — rounder, wider
    4: (
      <>
        <ellipse cx="20" cy="15" rx="8" ry="10" fill="currentColor" />
        <rect x="16.5" y="24" width="7" height="4" rx="2" fill="currentColor" />
        <path d="M1 27 Q3 23 10 23 L16 26 L20 27 L24 26 L30 23 Q37 23 39 27 L38 54 Q31 59 20 59 Q9 59 2 54 Z" fill="currentColor" />
      </>
    ),
  };

  return (
    <svg
      viewBox="0 0 40 72"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
      className="w-full h-full"
    >
      {variants[variant]}
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Sparkle burst — rendered above figure on cheer
// ---------------------------------------------------------------------------

interface SparkleProps {
  id: string;
}

function SparkleBurst({ id }: SparkleProps) {
  // 6 small ✦ / dot sparks radiating outward
  const sparks = [
    { angle: -80, dist: 22, char: "✦", size: 9 },
    { angle: -45, dist: 18, char: "·", size: 14 },
    { angle: -110, dist: 20, char: "✦", size: 7 },
    { angle: -60, dist: 28, char: "✦", size: 6 },
    { angle: -130, dist: 24, char: "·", size: 12 },
    { angle: -95, dist: 14, char: "✦", size: 8 },
  ];

  return (
    <div
      className="absolute pointer-events-none select-none"
      style={{ top: -8, left: "50%", transform: "translateX(-50%)" }}
      aria-hidden="true"
    >
      {sparks.map((s, i) => {
        const rad = (s.angle * Math.PI) / 180;
        return (
          <motion.span
            key={`${id}-spark-${i}`}
            initial={{ opacity: 1, x: 0, y: 0, scale: 0.4 }}
            animate={{
              opacity: [1, 1, 0],
              x: Math.cos(rad) * s.dist,
              y: Math.sin(rad) * s.dist,
              scale: [0.4, 1.2, 0.8],
            }}
            transition={{
              duration: 0.55,
              delay: i * 0.03,
              ease: "easeOut",
            }}
            style={{
              position: "absolute",
              fontSize: s.size,
              color: "var(--gold)",
              lineHeight: 1,
              top: 0,
              left: 0,
            }}
          >
            {s.char}
          </motion.span>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Figure configuration — 14 audience members with staggered properties
// ---------------------------------------------------------------------------

interface FigureConfig {
  variant: FigureVariant;
  /** Width in px */
  width: number;
  /** Height in px */
  height: number;
  /** Vertical offset from the row baseline (negative = taller/closer) */
  yOffset: number;
  /** Opacity: front row slightly more visible */
  opacity: number;
  /** Idle sway: x amplitude in px */
  swayX: number;
  /** Idle sway: rotation amplitude in deg */
  swayRot: number;
  /** Phase offset for stagger (0–1) */
  phase: number;
  /** Sway period in seconds */
  period: number;
}

const FIGURES: FigureConfig[] = [
  // --- front row (larger, more visible) ---
  { variant: 0, width: 32, height: 54, yOffset: 0,   opacity: 0.72, swayX: 2.5, swayRot: 1.5, phase: 0.0,  period: 3.4 },
  { variant: 2, width: 28, height: 50, yOffset: 2,   opacity: 0.68, swayX: 2.0, swayRot: 1.2, phase: 0.3,  period: 3.8 },
  { variant: 1, width: 34, height: 56, yOffset: -2,  opacity: 0.74, swayX: 3.0, swayRot: 1.8, phase: 0.6,  period: 3.1 },
  { variant: 4, width: 30, height: 52, yOffset: 1,   opacity: 0.70, swayX: 1.8, swayRot: 1.0, phase: 0.85, period: 3.6 },
  { variant: 3, width: 26, height: 48, yOffset: 3,   opacity: 0.65, swayX: 2.2, swayRot: 1.3, phase: 0.15, period: 4.0 },
  { variant: 0, width: 31, height: 53, yOffset: 0,   opacity: 0.71, swayX: 2.8, swayRot: 1.6, phase: 0.5,  period: 3.3 },
  { variant: 2, width: 27, height: 49, yOffset: 2,   opacity: 0.67, swayX: 1.5, swayRot: 0.9, phase: 0.72, period: 3.9 },
  // --- back row (smaller, dimmer) ---
  { variant: 1, width: 24, height: 42, yOffset: -8,  opacity: 0.42, swayX: 1.8, swayRot: 1.0, phase: 0.2,  period: 4.2 },
  { variant: 3, width: 22, height: 38, yOffset: -6,  opacity: 0.38, swayX: 2.2, swayRot: 1.2, phase: 0.45, period: 3.7 },
  { variant: 4, width: 26, height: 44, yOffset: -9,  opacity: 0.44, swayX: 1.6, swayRot: 0.8, phase: 0.65, period: 4.5 },
  { variant: 0, width: 23, height: 40, yOffset: -7,  opacity: 0.40, swayX: 2.0, swayRot: 1.1, phase: 0.88, period: 3.5 },
  { variant: 2, width: 25, height: 43, yOffset: -8,  opacity: 0.43, swayX: 1.4, swayRot: 0.7, phase: 0.1,  period: 4.1 },
  { variant: 1, width: 21, height: 37, yOffset: -6,  opacity: 0.37, swayX: 2.4, swayRot: 1.4, phase: 0.35, period: 3.9 },
  { variant: 3, width: 24, height: 41, yOffset: -9,  opacity: 0.41, swayX: 1.7, swayRot: 0.9, phase: 0.58, period: 4.3 },
];

// ---------------------------------------------------------------------------
// Idle sway — CSS keyframe approach (no JS loop needed, pure CSS)
// We define the keyframes inline via a <style> tag injected once.
// Each figure gets a unique animation-delay based on its phase.
// ---------------------------------------------------------------------------

const IDLE_STYLE_ID = "audience-idle-keyframes";

function ensureIdleKeyframes() {
  if (typeof document === "undefined") return;
  if (document.getElementById(IDLE_STYLE_ID)) return;
  const style = document.createElement("style");
  style.id = IDLE_STYLE_ID;
  style.textContent = `
    @keyframes audience-sway {
      0%   { transform: translateX(0px) rotate(0deg); }
      25%  { transform: translateX(var(--sway-x)) rotate(var(--sway-rot)); }
      75%  { transform: translateX(calc(var(--sway-x) * -1)) rotate(calc(var(--sway-rot) * -1)); }
      100% { transform: translateX(0px) rotate(0deg); }
    }
    @media (prefers-reduced-motion: reduce) {
      .audience-figure { animation: none !important; }
    }
  `;
  document.head.appendChild(style);
}

// ---------------------------------------------------------------------------
// Single audience figure — handles its own cheer state
// ---------------------------------------------------------------------------

interface AudienceFigureProps {
  config: FigureConfig;
  index: number;
  reduced: boolean;
  onCheer?: () => void;
}

function AudienceFigure({ config, index, reduced, onCheer }: AudienceFigureProps) {
  const [cheering, setCheering] = useState(false);
  const uid = useId();

  // Ensure CSS keyframes are in the document
  if (typeof window !== "undefined") {
    ensureIdleKeyframes();
  }

  const handleCheer = useCallback(() => {
    if (cheering) return;
    setCheering(true);
    onCheer?.();
    setTimeout(() => setCheering(false), 700);
  }, [cheering, onCheer]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        handleCheer();
      }
    },
    [handleCheer]
  );

  // Cheer Framer Motion variants — on the button itself (vertical jump)
  const cheerVariants = {
    idle: { y: 0, scale: 1 },
    cheer: reduced
      ? { scale: [1, 1.12, 1] }
      : { y: [0, -18, -10, -16, 0], scale: [1, 1.08, 1.05, 1.07, 1] },
  };

  const cheerTransition = reduced
    ? { duration: 0.3, ease: "easeOut" as const }
    : { duration: 0.65, ease: [0.22, 1, 0.36, 1] as [number, number, number, number], times: [0, 0.3, 0.5, 0.7, 1] };

  // Idle CSS sway — on an inner div (child of the FM button) so transforms don't conflict
  const idleInnerStyle: React.CSSProperties = !reduced
    ? {
        animation: cheering
          ? "none"
          : `audience-sway ${config.period}s ease-in-out infinite`,
        animationDelay: `${-config.phase * config.period}s`,
        ["--sway-x" as string]: `${config.swayX}px`,
        ["--sway-rot" as string]: `${config.swayRot}deg`,
        transformOrigin: "bottom center",
        width: "100%",
        height: "100%",
      }
    : { width: "100%", height: "100%" };

  return (
    <div
      className="relative flex-shrink-0"
      style={{ width: config.width, height: config.height + 10 }}
    >
      {/* Sparkle burst — shown on cheer */}
      <AnimatePresence>
        {cheering && !reduced && (
          <motion.div
            key={`${uid}-sparkle`}
            initial={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.1, delay: 0.5 }}
            style={{ position: "absolute", top: 0, left: 0, width: "100%", pointerEvents: "none" }}
          >
            <SparkleBurst id={uid} />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Clickable figure — FM controls cheer jump; inner div handles CSS idle sway */}
      <motion.button
        type="button"
        className="audience-figure absolute bottom-0 left-0 cursor-pointer bg-transparent border-0 p-0 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--gold)]"
        style={{
          width: config.width,
          height: config.height,
          color: "var(--ink)",
          opacity: config.opacity,
          display: "block",
          transformOrigin: "bottom center",
        }}
        aria-label="Audience member — click to cheer"
        title="Click to cheer"
        variants={cheerVariants}
        animate={cheering ? "cheer" : "idle"}
        transition={cheerTransition}
        onClick={handleCheer}
        onKeyDown={handleKeyDown}
        tabIndex={index < 4 ? 0 : -1}
      >
        {/* Inner div carries CSS sway animation (separate transform layer from FM) */}
        <div className="audience-figure" style={idleInnerStyle}>
          <FigureSilhouette variant={config.variant} />
        </div>
      </motion.button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Public props
// ---------------------------------------------------------------------------

export interface AudienceProps {
  /** Called each time any figure is clicked to cheer. No-op by default. Phase 3 will wire audio here. */
  onCheer?: () => void;
  /** Additional CSS class for the wrapper */
  className?: string;
}

// ---------------------------------------------------------------------------
// Audience component — the full crowd row
// ---------------------------------------------------------------------------

export default function Audience({ onCheer, className }: AudienceProps) {
  const reduced = usePrefersReducedMotion();

  return (
    <div
      className={`relative w-full overflow-hidden ${className ?? ""}`}
      aria-label="Audience"
      role="group"
    >
      {/* Subtle stage-floor line */}
      <div
        className="absolute top-0 left-0 right-0 h-px"
        style={{ background: "var(--rule)", opacity: 0.6 }}
        aria-hidden="true"
      />

      {/* Crowd row — flex, centered, slight perspective crush */}
      <div
        className="flex items-end justify-center gap-0.5 pt-1 pb-0 px-2 flex-wrap"
      >
        {FIGURES.map((cfg, i) => (
          <div
            key={i}
            style={{ marginTop: cfg.yOffset < 0 ? Math.abs(cfg.yOffset) : 0 }}
          >
            <AudienceFigure
              config={cfg}
              index={i}
              reduced={reduced}
              onCheer={onCheer}
            />
          </div>
        ))}
      </div>
    </div>
  );
}
