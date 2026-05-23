"use client";

import StageFigure, { type StageFigureItem } from "@/components/StageFigure";
import Audience from "@/components/Audience";

/**
 * The lit stage: a perspective runway with the figure standing at its front,
 * a faint upstage backdrop, and the crowd surrounding it — a dense front row
 * plus flanks anchored to the left and right edges of the theater.
 */
export default function Stage({
  items,
  onCheer,
}: {
  items: StageFigureItem[];
  onCheer?: () => void;
}) {
  return (
    <div className="show-stage">
      <div className="show-stage-backdrop" aria-hidden="true" />

      {/* Runway + figure */}
      <div className="show-runway">
        <div className="show-runway-floor" aria-hidden="true" />
        <div className="relative z-10">
          <StageFigure figureHeight={460} items={items} />
        </div>
      </div>

      {/* Crowd banks flanking the runway — fill the side space, surround the catwalk */}
      <div className="fixed left-0 top-[12%] bottom-16 z-[6] hidden w-[32vw] max-w-[460px] md:block">
        <Audience layout="bank" count={52} onCheer={onCheer} />
      </div>
      <div className="fixed right-0 top-[12%] bottom-16 z-[6] hidden w-[32vw] max-w-[460px] md:block">
        <Audience layout="bank" count={52} onCheer={onCheer} />
      </div>
    </div>
  );
}
