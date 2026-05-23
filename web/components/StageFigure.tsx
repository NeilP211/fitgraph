"use client";

import Image from "next/image";
import { AnimatePresence, motion } from "motion/react";
import { imageUrl } from "@/lib/api";
import { usePrefersReducedMotion } from "@/components/motion/usePrefersReducedMotion";

// ---------------------------------------------------------------------------
// Slot configuration - pure helpers live in lib/slots (React-free); re-exported
// here so existing imports (`@/components/StageFigure`) keep working.
// ---------------------------------------------------------------------------

import { CENTER_SLOTS, categoryToSlot, type CenterSlot } from "@/lib/slots";

export { CENTER_SLOTS, SIDE_SLOTS, categoryToSlot } from "@/lib/slots";
export type { CenterSlot, SideSlot, SlotName } from "@/lib/slots";

// ---------------------------------------------------------------------------
// Slot visual configuration - controls size and offset of each body part
// ---------------------------------------------------------------------------

interface SlotConfig {
  /** label for aria/screen-reader */
  label: string;
  /** height as % of total figure height */
  heightPct: number;
  /** how object-fit works for this slot */
  objectFit: "contain" | "cover";
  /** z-index for layering (outerwear behind top, etc.) */
  zIndex: number;
  /** horizontal scale factor: 1 = full slot width */
  widthFactor: number;
}

const CENTER_SLOT_CONFIG: Record<CenterSlot, SlotConfig> = {
  hats: {
    label: "Hat",
    heightPct: 10,
    objectFit: "contain",
    zIndex: 10,
    widthFactor: 0.65,
  },
  sunglasses: {
    label: "Sunglasses",
    heightPct: 7,
    objectFit: "contain",
    zIndex: 11,
    widthFactor: 0.6,
  },
  outerwear: {
    label: "Outerwear",
    heightPct: 26,
    objectFit: "contain",
    zIndex: 5,
    widthFactor: 1.05, // slightly wider - layered behind top
  },
  tops: {
    label: "Top",
    heightPct: 24,
    objectFit: "contain",
    zIndex: 6,
    widthFactor: 0.9,
  },
  "all-body": {
    label: "Full-length piece",
    heightPct: 50, // spans torso + legs
    objectFit: "contain",
    zIndex: 6,
    widthFactor: 0.9,
  },
  bottoms: {
    label: "Bottom",
    heightPct: 26,
    objectFit: "contain",
    zIndex: 7,
    widthFactor: 0.85,
  },
  shoes: {
    label: "Shoes",
    heightPct: 10,
    objectFit: "contain",
    zIndex: 8,
    widthFactor: 0.7,
  },
};

// ---------------------------------------------------------------------------
// Mannequin silhouette SVG
// Subtle dress-form outline in --rule color
// ---------------------------------------------------------------------------

function MannequinSilhouette() {
  return (
    <svg
      viewBox="0 0 120 360"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
      className="absolute inset-0 w-full h-full pointer-events-none select-none"
      style={{ opacity: 0.18 }}
    >
      {/* Stand / base */}
      <rect x="52" y="340" width="16" height="10" rx="2" fill="var(--rule)" />
      <rect x="44" y="348" width="32" height="5" rx="2.5" fill="var(--rule)" />
      {/* Pole */}
      <rect x="58" y="310" width="4" height="35" rx="2" fill="var(--rule)" />
      {/* Hips / skirt form */}
      <ellipse cx="60" cy="305" rx="26" ry="10" fill="var(--rule)" />
      {/* Torso */}
      <path
        d="M34 220 Q28 260 34 305 L86 305 Q92 260 86 220 Z"
        fill="var(--rule)"
      />
      {/* Waist */}
      <ellipse cx="60" cy="220" rx="20" ry="6" fill="var(--rule)" />
      {/* Bust / chest */}
      <path
        d="M34 170 Q30 200 34 220 L86 220 Q90 200 86 170 Z"
        fill="var(--rule)"
      />
      {/* Shoulders */}
      <ellipse cx="60" cy="170" rx="28" ry="8" fill="var(--rule)" />
      {/* Neck */}
      <rect x="54" y="148" width="12" height="26" rx="6" fill="var(--rule)" />
      {/* Head */}
      <ellipse cx="60" cy="136" rx="18" ry="22" fill="var(--rule)" />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Empty slot placeholder
// ---------------------------------------------------------------------------

function SlotPlaceholder({ label }: { label: string }) {
  return (
    <div
      className="w-full h-full flex items-center justify-center"
      style={{
        border: "1.5px dashed var(--rule)",
        borderRadius: "2px",
        opacity: 0.5,
      }}
      aria-label={`Empty ${label} slot`}
    >
      <span
        className="text-[9px] uppercase tracking-[0.12em] text-ink-soft select-none"
        style={{ fontFamily: "var(--font-body-var), serif" }}
      >
        {label}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Individual slot cell - shows either a garment image or a placeholder
// ---------------------------------------------------------------------------

interface SlotCellProps {
  slot: CenterSlot;
  item: { item_id: string; title: string | null; isSeed?: boolean } | null;
  /** absolute pixel height of this slot cell */
  heightPx: number;
  widthPx: number;
  reduced: boolean;
  /** when true this slot is hidden (e.g. tops/bottoms when all-body is selected) */
  hidden?: boolean;
}

function SlotCell({ slot, item, heightPx, widthPx, reduced, hidden }: SlotCellProps) {
  const cfg = CENTER_SLOT_CONFIG[slot];
  const label = cfg.label;

  if (hidden) return <div style={{ height: heightPx }} aria-hidden="true" />;

  const slotWidthPx = Math.round(widthPx * cfg.widthFactor);

  return (
    <div
      style={{
        height: heightPx,
        width: widthPx,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        position: "relative",
        zIndex: cfg.zIndex,
        flexShrink: 0,
      }}
      role="region"
      aria-label={`${label} slot${item ? `: ${item.title || item.item_id}` : " - empty"}`}
    >
      <div
        style={{
          width: slotWidthPx,
          height: heightPx,
          position: "relative",
          overflow: "visible",
        }}
      >
        <AnimatePresence mode="wait">
          {item ? (
            <motion.div
              key={item.item_id}
              initial={reduced ? false : { opacity: 0, scale: 0.75, y: -12 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={reduced ? {} : { opacity: 0, scale: 0.85 }}
              transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
              style={{
                position: "absolute",
                inset: 0,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              {/* Seed badge */}
              {item.isSeed && (
                <span
                  className="absolute top-1 left-1 z-20 rounded-sm bg-ink/80 px-1.5 py-0.5 text-[8px] uppercase tracking-[0.12em] text-paper"
                  style={{ fontFamily: "var(--font-body-var), serif" }}
                  aria-label="Seed item"
                >
                  Seed
                </span>
              )}
              <Image
                src={imageUrl(item.item_id)}
                alt={item.title || label}
                fill
                sizes={`${slotWidthPx}px`}
                className="object-contain drop-shadow-md"
                unoptimized
                style={{ objectPosition: "center top" }}
              />
            </motion.div>
          ) : (
            <motion.div
              key="empty"
              initial={false}
              animate={{ opacity: 1 }}
              style={{ position: "absolute", inset: 0 }}
            >
              <SlotPlaceholder label={label} />
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Side float item (bags, jewellery, scarves, accessories)
// ---------------------------------------------------------------------------

interface SideFloatProps {
  side: "left" | "right";
  items: Array<{ item_id: string; title: string | null; isSeed?: boolean }>;
  reduced: boolean;
}

function SideFloat({ side, items, reduced }: SideFloatProps) {
  if (items.length === 0) return null;

  return (
    <div
      className="flex flex-col gap-2 items-center"
      style={{ minWidth: 64, maxWidth: 80 }}
    >
      <AnimatePresence>
        {items.map((item) => (
          <motion.div
            key={item.item_id}
            initial={reduced ? false : { opacity: 0, x: side === "left" ? -20 : 20, scale: 0.8 }}
            animate={{ opacity: 1, x: 0, scale: 1 }}
            exit={reduced ? {} : { opacity: 0, scale: 0.8 }}
            transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
            className="relative overflow-visible"
            style={{ width: 64, height: 64, position: "relative" }}
          >
            {item.isSeed && (
              <span
                className="absolute top-0.5 left-0.5 z-20 rounded-sm bg-ink/80 px-1 py-px text-[8px] uppercase tracking-[0.1em] text-paper"
                style={{ fontFamily: "var(--font-body-var), serif" }}
              >
                Seed
              </span>
            )}
            <Image
              src={imageUrl(item.item_id)}
              alt={item.title || "Accessory"}
              fill
              sizes="64px"
              className="object-contain drop-shadow-sm"
              unoptimized
            />
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface StageFigureItem {
  item_id: string;
  title: string | null;
  semantic_category: string | null;
  isSeed?: boolean;
}

export interface StageFigureProps {
  /** Total figure height in px (default 480) */
  figureHeight?: number;
  /** The currently selected/placed items (seed + selections) */
  items: StageFigureItem[];
}

// ---------------------------------------------------------------------------
// Main StageFigure component
// ---------------------------------------------------------------------------

export default function StageFigure({ figureHeight = 480, items }: StageFigureProps) {
  const reduced = usePrefersReducedMotion();

  // Determine which items occupy which slots
  const centerItems: Partial<Record<CenterSlot, StageFigureItem>> = {};
  const leftItems: StageFigureItem[] = []; // bags
  const rightItems: StageFigureItem[] = []; // jewellery, scarves, accessories

  for (const item of items) {
    const slot = categoryToSlot(item.semantic_category);
    if ((CENTER_SLOTS as readonly string[]).includes(slot)) {
      // For outerwear + tops, allow both simultaneously (different z-index)
      if (!centerItems[slot as CenterSlot]) {
        centerItems[slot as CenterSlot] = item;
      }
    } else if (slot === "bags") {
      leftItems.push(item);
    } else {
      rightItems.push(item);
    }
  }

  // If all-body is selected, hide tops and bottoms slots
  const hasAllBody = !!centerItems["all-body"];

  // Compute heights for center slots
  // all-body replaces tops+bottoms, so redistribute
  const FIGURE_HEIGHT = figureHeight;
  const figureWidthPx = Math.round(FIGURE_HEIGHT * 0.45); // ~45% of height

  // Slot heights as px - proportional percentages of figure height
  // When all-body present: tops slot hidden, bottoms slot hidden, all-body gets their combined height
  const slotHeights: Record<CenterSlot, number> = {
    hats: Math.round(FIGURE_HEIGHT * 0.1),
    sunglasses: Math.round(FIGURE_HEIGHT * 0.07),
    outerwear: Math.round(FIGURE_HEIGHT * 0.26),
    tops: Math.round(FIGURE_HEIGHT * 0.24),
    "all-body": Math.round(FIGURE_HEIGHT * 0.50),
    bottoms: Math.round(FIGURE_HEIGHT * 0.26),
    shoes: Math.round(FIGURE_HEIGHT * 0.10),
  };

  // Determine which center slots to render and in what order
  // When all-body is set: render hats, sunglasses, outerwear, all-body, shoes
  // Otherwise: render all 7 center slots
  const visibleCenterSlots: CenterSlot[] = hasAllBody
    ? ["hats", "sunglasses", "outerwear", "all-body", "shoes"]
    : ["hats", "sunglasses", "outerwear", "tops", "bottoms", "shoes"];

  // Recalculate heights when all-body: distribute tops+bottoms height to all-body
  const effectiveHeights = { ...slotHeights };
  if (hasAllBody) {
    effectiveHeights["all-body"] =
      slotHeights.tops + slotHeights.bottoms;
  }

  // Verify total height is correct
  const totalH = visibleCenterSlots.reduce((sum, s) => sum + effectiveHeights[s], 0);
  const scale = FIGURE_HEIGHT / totalH;
  // Normalize so slots fill exactly figureHeight
  const normalizedHeights: Record<CenterSlot, number> = {} as Record<CenterSlot, number>;
  for (const s of visibleCenterSlots) {
    normalizedHeights[s] = Math.round(effectiveHeights[s] * scale);
  }

  return (
    <div
      className="relative flex items-start justify-center gap-2"
      style={{ height: FIGURE_HEIGHT }}
      aria-label="Outfit figure - selected pieces stacked as a look"
    >
      {/* Left side floats (bags) */}
      <div
        className="flex flex-col justify-center self-stretch"
        style={{ paddingTop: Math.round(FIGURE_HEIGHT * 0.35), minWidth: 72 }}
      >
        <SideFloat side="left" items={leftItems} reduced={reduced} />
      </div>

      {/* Center stage: mannequin + item stack */}
      <div
        className="relative flex-shrink-0"
        style={{ width: figureWidthPx, height: FIGURE_HEIGHT }}
      >
        {/* Mannequin silhouette */}
        <MannequinSilhouette />

        {/* Stack of slot cells */}
        <div
          className="absolute inset-0 flex flex-col items-center justify-start"
          style={{ zIndex: 1 }}
        >
          {visibleCenterSlots.map((slot) => (
            <SlotCell
              key={slot}
              slot={slot}
              item={centerItems[slot] ?? null}
              heightPx={normalizedHeights[slot]}
              widthPx={figureWidthPx}
              reduced={reduced}
            />
          ))}
        </div>
      </div>

      {/* Right side floats (jewellery, scarves, accessories) */}
      <div
        className="flex flex-col justify-center self-stretch"
        style={{ paddingTop: Math.round(FIGURE_HEIGHT * 0.2), minWidth: 72 }}
      >
        <SideFloat side="right" items={rightItems} reduced={reduced} />
      </div>
    </div>
  );
}
