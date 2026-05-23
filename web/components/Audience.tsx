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
  const variants: Record<FigureVariant, React.ReactElement> = {
    0: (
      <>
        <ellipse cx="20" cy="14" rx="7" ry="9" fill="currentColor" />
        <rect x="17" y="22" width="6" height="5" rx="2" fill="currentColor" />
        <path d="M2 27 Q4 24 10 24 L17 26 L20 27 L23 26 L30 24 Q36 24 38 27 L36 52 Q30 56 20 56 Q10 56 4 52 Z" fill="currentColor" />
      </>
    ),
    1: (
      <>
        <ellipse cx="20" cy="13" rx="6.5" ry="8.5" fill="currentColor" />
        <rect x="17" y="21" width="6" height="4" rx="2" fill="currentColor" />
        <path d="M0 26 Q3 22 11 23 L17 25 L20 26 L23 25 L29 23 Q37 22 40 26 L38 52 Q31 57 20 57 Q9 57 2 52 Z" fill="currentColor" />
      </>
    ),
    2: (
      <>
        <ellipse cx="20" cy="14" rx="6" ry="8" fill="currentColor" />
        <rect x="17.5" y="22" width="5" height="5" rx="2" fill="currentColor" />
        <path d="M6 28 Q8 25 13 25 L17 27 L20 28 L23 27 L27 25 Q32 25 34 28 L33 52 Q27 56 20 56 Q13 56 7 52 Z" fill="currentColor" />
      </>
    ),
    3: (
      <>
        <ellipse cx="20" cy="13" rx="6" ry="10" fill="currentColor" />
        <rect x="17.5" y="22" width="5" height="5" rx="2" fill="currentColor" />
        <path d="M5 27 Q7 24 12 24 L17 26 L20 27 L23 26 L28 24 Q33 24 35 27 L34 56 Q28 60 20 60 Q12 60 6 56 Z" fill="currentColor" />
      </>
    ),
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
// Sparkle burst — rendered above a figure on cheer
// ---------------------------------------------------------------------------

function SparkleBurst({ id }: { id: string }) {
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
            transition={{ duration: 0.55, delay: i * 0.03, ease: "easeOut" }}
            style={{ position: "absolute", fontSize: s.size, color: "var(--gold)", lineHeight: 1, top: 0, left: 0 }}
          >
            {s.char}
          </motion.span>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Figure configuration
// ---------------------------------------------------------------------------

interface FigureConfig {
  variant: FigureVariant;
  width: number;
  height: number;
  yOffset: number;
  opacity: number;
  swayX: number;
  swayRot: number;
  phase: number;
  period: number;
}

/** Deterministically generate `count` figure configs (stable across SSR/CSR). */
function makeConfigs(count: number): FigureConfig[] {
  const rnd = (n: number) => {
    const x = Math.sin(n * 127.1 + 311.7) * 43758.5453;
    return x - Math.floor(x);
  };
  const out: FigureConfig[] = [];
  for (let i = 0; i < count; i++) {
    const r1 = rnd(i + 1);
    const r2 = rnd(i + 41);
    const r3 = rnd(i + 97);
    const back = i % 3 === 2; // ~1/3 form a dimmer, smaller back row
    out.push({
      variant: (Math.floor(r1 * 5) % 5) as FigureVariant,
      width: back ? 18 + Math.round(r2 * 6) : 24 + Math.round(r2 * 10),
      height: back ? 32 + Math.round(r3 * 8) : 44 + Math.round(r3 * 12),
      yOffset: back ? -6 - Math.round(r1 * 6) : Math.round(r2 * 4),
      opacity: back ? 0.3 + r3 * 0.12 : 0.55 + r3 * 0.22,
      swayX: 1.2 + r1 * 2,
      swayRot: 0.6 + r2 * 1.2,
      phase: r3,
      period: 3 + r1 * 1.6,
    });
  }
  return out;
}

// ---------------------------------------------------------------------------
// Idle sway — CSS keyframes injected once
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

  const cheerVariants = {
    idle: { y: 0, scale: 1 },
    cheer: reduced
      ? { scale: [1, 1.12, 1] }
      : { y: [0, -18, -10, -16, 0], scale: [1, 1.08, 1.05, 1.07, 1] },
  };

  const cheerTransition = reduced
    ? { duration: 0.3, ease: "easeOut" as const }
    : { duration: 0.65, ease: [0.22, 1, 0.36, 1] as [number, number, number, number], times: [0, 0.3, 0.5, 0.7, 1] };

  const idleInnerStyle: React.CSSProperties = !reduced
    ? {
        animation: cheering ? "none" : `audience-sway ${config.period}s ease-in-out infinite`,
        animationDelay: `${-config.phase * config.period}s`,
        ["--sway-x" as string]: `${config.swayX}px`,
        ["--sway-rot" as string]: `${config.swayRot}deg`,
        transformOrigin: "bottom center",
        width: "100%",
        height: "100%",
      }
    : { width: "100%", height: "100%" };

  return (
    <div className="relative flex-shrink-0" style={{ width: config.width, height: config.height + 10 }}>
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
        tabIndex={index < 3 ? 0 : -1}
      >
        <div className="audience-figure" style={idleInnerStyle}>
          <FigureSilhouette variant={config.variant} />
        </div>
      </motion.button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Public props + component
// ---------------------------------------------------------------------------

export interface AudienceProps {
  /** Called each time any figure is clicked to cheer. */
  onCheer?: () => void;
  /** Additional CSS class for the wrapper */
  className?: string;
  /** How many figures to render (default 14). */
  count?: number;
  /** "row" = crowd row (front); "column" = side flank. */
  layout?: "row" | "column";
}

export default function Audience({ onCheer, className, count = 14, layout = "row" }: AudienceProps) {
  const reduced = usePrefersReducedMotion();
  const figures = makeConfigs(count);
  const isColumn = layout === "column";

  return (
    <div className={`relative ${className ?? ""}`} aria-label="Audience" role="group">
      <div
        className={
          isColumn
            ? "flex flex-col items-center gap-1"
            : "flex flex-wrap items-end justify-center gap-x-0.5 gap-y-1 px-2"
        }
      >
        {figures.map((cfg, i) => (
          <div key={i} style={{ marginTop: cfg.yOffset < 0 ? Math.abs(cfg.yOffset) : 0 }}>
            <AudienceFigure config={cfg} index={i} reduced={reduced} onCheer={onCheer} />
          </div>
        ))}
      </div>
    </div>
  );
}
