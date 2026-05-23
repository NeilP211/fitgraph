"use client";

/**
 * FashionBand — an oversized, low-contrast editorial wordmark that drifts
 * slowly across the page behind content. Reads as paper-on-paper texture,
 * not a second ticker: it's much larger and much slower than the runway's
 * top marquee, and sits at the back of the stacking context.
 *
 * Decorative only (aria-hidden). Place inside a `relative` (ideally
 * `isolate overflow-hidden`) parent and render real content above it with a
 * higher z-index. Honors `prefers-reduced-motion` via the `.fashion-band`
 * animation rule in globals.css.
 */

interface FashionBandProps {
  /** Repeated wordmark. Keep it short — it's set very large. */
  text?: string;
  /** Vertical placement of the band's center, e.g. "50%" (default) or "30%". */
  top?: string;
  /** Extra classes for the outer (absolute) layer. */
  className?: string;
}

const SEP = " · "; // thin-space-flanked middot

export default function FashionBand({
  text = "HIGH FASHION",
  top = "50%",
  className = "",
}: FashionBandProps) {
  // One "half" repeated enough to overflow wide viewports; rendered twice so
  // the 0 → -50% drift loops seamlessly.
  const half = Array.from({ length: 4 }, () => text).join(SEP) + SEP;

  return (
    <div
      aria-hidden="true"
      className={`pointer-events-none absolute inset-x-0 overflow-hidden select-none ${className}`}
      style={{ top, transform: "translateY(-50%)" }}
    >
      <div className="fashion-band">
        {[0, 1].map((n) => (
          <span
            key={n}
            className="whitespace-nowrap uppercase leading-none"
            style={{
              fontFamily: "var(--font-display-var), serif",
              fontWeight: 700,
              fontSize: "clamp(4rem, 13vw, 11rem)",
              letterSpacing: "0.06em",
              color: "var(--ink)",
              opacity: 0.05,
            }}
          >
            {half}
          </span>
        ))}
      </div>
    </div>
  );
}
