/**
 * WrapBackground — fixed full-viewport SVG layer showing a diagonal
 * "HIGH FASHION" step-and-repeat pattern, like luxury tissue/wrapping paper.
 *
 * Uses an SVG <pattern> with patternTransform="rotate(-30)" so the tiling is
 * seamless by construction — no edge gaps from CSS rotation tricks.
 * z-index: -10 keeps it behind all page content.
 */
export default function WrapBackground() {
  return (
    <div
      aria-hidden="true"
      style={{
        position: "fixed",
        inset: 0,
        zIndex: -10,
        pointerEvents: "none",
      }}
    >
      <svg
        width="100%"
        height="100%"
        xmlns="http://www.w3.org/2000/svg"
        style={{ display: "block" }}
      >
        <defs>
          {/*
           * Pattern cell: 320 × 80 px (userSpaceOnUse).
           * Two text labels per cell, offset so adjacent rows interleave:
           *   row A at y=20, row B at y=60 (x shifted half-width for a brick layout).
           * The whole cell is then rotated -30° via patternTransform.
           */}
          <pattern
            id="hf-wrap"
            x="0"
            y="0"
            width="320"
            height="80"
            patternUnits="userSpaceOnUse"
            patternTransform="rotate(-30)"
          >
            {/* Row A — "HIGH FASHION ✦" */}
            <text
              x="0"
              y="22"
              fontFamily="var(--font-display-var), 'Cinzel', 'Trajan Pro', serif"
              fontSize="15"
              fontWeight="400"
              letterSpacing="5"
              textAnchor="start"
              fill="#D4899A"
              fillOpacity="0.55"
              style={{ userSelect: "none" }}
            >
              HIGH FASHION ✦
            </text>

            {/* Row B — offset by half the cell width for a staggered brick look */}
            <text
              x="160"
              y="62"
              fontFamily="var(--font-display-var), 'Cinzel', 'Trajan Pro', serif"
              fontSize="15"
              fontWeight="400"
              letterSpacing="5"
              textAnchor="start"
              fill="#D4899A"
              fillOpacity="0.55"
              style={{ userSelect: "none" }}
            >
              HIGH FASHION ✦
            </text>
          </pattern>
        </defs>

        {/* Base blush fill */}
        <rect width="100%" height="100%" fill="#F5E1E4" />

        {/* Pattern overlay */}
        <rect width="100%" height="100%" fill="url(#hf-wrap)" />
      </svg>
    </div>
  );
}
