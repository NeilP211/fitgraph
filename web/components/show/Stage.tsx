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

      {/* Front crowd — closest, largest, in the foreground */}
      <div className="relative z-10 mt-1 w-full">
        <Audience layout="row" count={30} onCheer={onCheer} />
      </div>

      {/* Side flanks — anchored to the theater edges, in the shadows */}
      <div className="fixed left-1 top-[22%] z-[5] hidden lg:block">
        <Audience layout="column" count={9} onCheer={onCheer} />
      </div>
      <div className="fixed right-1 top-[22%] z-[5] hidden lg:block">
        <Audience layout="column" count={9} onCheer={onCheer} />
      </div>
    </div>
  );
}
