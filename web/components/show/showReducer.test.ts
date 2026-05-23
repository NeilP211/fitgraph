import { describe, it, expect } from "vitest";
import { reducer, currentCandidate, type State } from "./showReducer";
import type { OutfitSuggestionsResponse } from "@/lib/api";

const resp: OutfitSuggestionsResponse = {
  seed: { item_id: "S", title: "Seed", semantic_category: "tops", image_path: null },
  suggestions: {
    bottoms: [
      { item_id: "b1", score: 0.9, title: "B1", semantic_category: "bottoms", image_path: null },
      { item_id: "b2", score: 0.8, title: "B2", semantic_category: "bottoms", image_path: null },
    ],
    shoes: [
      { item_id: "s1", score: 0.7, title: "S1", semantic_category: "shoes", image_path: null },
    ],
  },
};

function loaded(): State {
  return reducer({ status: "loading" }, { type: "FETCH_SUCCESS", data: resp });
}

describe("showReducer", () => {
  it("loads with cursors at 0, nothing chosen, no active slot", () => {
    const s = loaded();
    expect(s.status).toBe("loaded");
    if (s.status !== "loaded") return;
    expect(s.cursor).toEqual({ bottoms: 0, shoes: 0 });
    expect(s.chosen).toEqual({ bottoms: null, shoes: null });
    expect(s.activeSlot).toBeNull();
    // sorted head-to-toe: bottoms before shoes
    expect(s.slots).toEqual(["bottoms", "shoes"]);
  });

  it("REJECT advances the cursor (next best, no repeat)", () => {
    let s = loaded();
    s = reducer(s, { type: "SET_ACTIVE_SLOT", slot: "bottoms" });
    expect(currentCandidate(s)?.item_id).toBe("b1");
    s = reducer(s, { type: "REJECT" });
    expect(currentCandidate(s)?.item_id).toBe("b2");
    s = reducer(s, { type: "REJECT" });
    expect(currentCandidate(s)).toBeNull(); // exhausted
  });

  it("ACCEPT records the choice and clears the active slot", () => {
    let s = loaded();
    s = reducer(s, { type: "SET_ACTIVE_SLOT", slot: "shoes" });
    s = reducer(s, { type: "ACCEPT" });
    if (s.status !== "loaded") throw new Error("expected loaded");
    expect(s.chosen.shoes).toBe("s1");
    expect(s.activeSlot).toBeNull();
  });

  it("UNCHOOSE clears a slot", () => {
    let s = loaded();
    s = reducer(s, { type: "SET_ACTIVE_SLOT", slot: "shoes" });
    s = reducer(s, { type: "ACCEPT" });
    s = reducer(s, { type: "UNCHOOSE", slot: "shoes" });
    if (s.status !== "loaded") throw new Error("expected loaded");
    expect(s.chosen.shoes).toBeNull();
  });
});
