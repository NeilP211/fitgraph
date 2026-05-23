"use client";

import StageFigure, { type StageFigureItem } from "@/components/StageFigure";
import TheatreStand from "@/components/show/TheatreStand";

/**
 * The lit stage: a perspective runway with the figure standing at its front,
 * pushed toward the back so the picking card has clear room below it. Tiered
 * theatre seating flanks the runway on the left and right. No crowd sits below
 * the runway: that space is reserved for choosing pieces.
 */
export default function Stage({
  items,
  onCheer,
}: {
  items: StageFigureItem[];
  onCheer?: () => void;
}) {
  return (
    <div
      className="show-stage"
      style={{ minHeight: "46vh", justifyContent: "flex-start", paddingTop: "0.25rem" }}
    >
      <div className="show-stage-backdrop" aria-hidden="true" />

      {/* Runway + figure (figure sits up toward the back of the catwalk) */}
      <div className="show-runway">
        <div className="show-runway-floor" style={{ width: 300, height: 440 }} aria-hidden="true" />
        <div className="relative z-10">
          <StageFigure figureHeight={300} items={items} />
        </div>
      </div>

      {/* Tiered theatre seating flanking the runway, filling the side space */}
      <div className="fixed left-0 top-[20%] bottom-4 z-[6] hidden w-[28vw] max-w-[440px] px-2 md:block">
        <TheatreStand side="left" onCheer={onCheer} />
      </div>
      <div className="fixed right-0 top-[20%] bottom-4 z-[6] hidden w-[28vw] max-w-[440px] px-2 md:block">
        <TheatreStand side="right" onCheer={onCheer} />
      </div>
    </div>
  );
}
