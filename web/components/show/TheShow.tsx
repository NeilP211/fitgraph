"use client";

import { useEffect, useReducer, useState } from "react";
import { getOutfitSuggestions } from "@/lib/api";
import { reducer, currentCandidate, type State } from "@/components/show/showReducer";
import TheaterScene from "@/components/show/TheaterScene";
import Stage from "@/components/show/Stage";
import SlotPicker from "@/components/show/SlotPicker";
import SpotlightSuggestion from "@/components/show/SpotlightSuggestion";
import SavePanel from "@/components/show/SavePanel";
import type { StageFigureItem } from "@/components/StageFigure";
import { useShowAudio } from "@/components/audio/useShowAudio";

/**
 * The Show - the dark-theater outfit builder. The user picks a slot from the
 * bottom dock, gets one suggestion at a time (✗ to cycle next-best, ✓ to place
 * it on the lit figure), and the crowd roars on accept and on click.
 */
export default function TheShow({ itemId }: { itemId: string }) {
  const [state, dispatch] = useReducer(reducer, { status: "loading" } as State);
  const { soundOn, toggleMusic, playCheer, arm } = useShowAudio();
  const [savedName, setSavedName] = useState("");

  useEffect(() => {
    let cancelled = false;
    getOutfitSuggestions(itemId, 24)
      .then((data) => {
        if (!cancelled) dispatch({ type: "FETCH_SUCCESS", data });
      })
      .catch((e: unknown) => {
        if (!cancelled)
          dispatch({
            type: "FETCH_ERROR",
            message: e instanceof Error ? e.message : "Failed to load suggestions.",
          });
      });
    return () => {
      cancelled = true;
    };
  }, [itemId]);

  // Crowd roar: arm audio on the gesture, then play the cheer (no-op if muted).
  const roar = () => {
    arm();
    playCheer();
  };

  if (state.status === "loading") {
    return (
      <TheaterScene soundOn={soundOn} onToggleSound={toggleMusic}>
        <p className="pt-20 text-[#f4ecd8]/60" style={{ fontFamily: "var(--font-body-var), serif" }}>
          Setting the stage…
        </p>
      </TheaterScene>
    );
  }

  if (state.status === "error") {
    return (
      <TheaterScene soundOn={soundOn} onToggleSound={toggleMusic}>
        <p role="alert" className="pt-20 text-red-300">
          {state.message}
        </p>
      </TheaterScene>
    );
  }

  const cand = currentCandidate(state);
  const exhausted = !!state.activeSlot && !cand;

  const figureItems: StageFigureItem[] = [
    {
      item_id: state.seed.item_id,
      title: state.seed.title,
      semantic_category: state.seed.semantic_category,
      isSeed: true,
    },
    ...state.slots.flatMap((slot): StageFigureItem[] => {
      const id = state.chosen[slot];
      if (!id) return [];
      const it = state.pools[slot].find((p) => p.item_id === id);
      return it
        ? [{ item_id: it.item_id, title: it.title, semantic_category: it.semantic_category }]
        : [];
    }),
  ];

  const selectedIds = state.slots
    .map((s) => state.chosen[s])
    .filter((x): x is string => !!x);

  const onAccept = () => {
    dispatch({ type: "ACCEPT" });
    roar();
  };

  return (
    <TheaterScene soundOn={soundOn} onToggleSound={toggleMusic}>
      <h1
        className="text-xl uppercase tracking-[0.24em] text-[#d4af6e]"
        style={{ fontFamily: "var(--font-display-var), serif" }}
      >
        The Show
      </h1>

      <Stage items={figureItems} onCheer={roar} />

      {/*
        Foreground control zone - pinned just above the dock so the stage stays
        uncluttered. Shows the active suggestion, else a compact save bar once
        pieces exist, else nothing.
      */}
      <div className="fixed bottom-24 left-1/2 z-30 w-full max-w-md -translate-x-1/2 px-4">
        {state.activeSlot ? (
          <SpotlightSuggestion
            slot={state.activeSlot}
            candidate={cand}
            exhausted={exhausted}
            onAccept={onAccept}
            onReject={() => dispatch({ type: "REJECT" })}
          />
        ) : selectedIds.length > 0 ? (
          <SavePanel
            seedItemId={itemId}
            selectedIds={selectedIds}
            savedName={savedName}
            setSavedName={setSavedName}
          />
        ) : null}
      </div>

      <SlotPicker
        slots={state.slots}
        chosen={state.chosen}
        activeSlot={state.activeSlot}
        onPick={(slot) => {
          arm();
          dispatch({ type: "SET_ACTIVE_SLOT", slot });
        }}
      />
    </TheaterScene>
  );
}
