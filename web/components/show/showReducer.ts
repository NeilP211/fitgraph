import type { OutfitSuggestionsResponse, SuggestionItem } from "@/lib/api";
import { categoryToSlot, CENTER_SLOTS } from "@/lib/slots";

export type State =
  | { status: "loading" }
  | { status: "error"; message: string }
  | {
      status: "loaded";
      seed: { item_id: string; title: string | null; semantic_category: string | null };
      slots: string[];
      pools: Record<string, SuggestionItem[]>;
      cursor: Record<string, number>;
      chosen: Record<string, string | null>;
      activeSlot: string | null;
    };

export type Action =
  | { type: "FETCH_SUCCESS"; data: OutfitSuggestionsResponse }
  | { type: "FETCH_ERROR"; message: string }
  | { type: "SET_ACTIVE_SLOT"; slot: string | null }
  | { type: "REJECT" }
  | { type: "ACCEPT" }
  | { type: "UNCHOOSE"; slot: string };

/** Sort categories into head-to-toe body order, with side slots last. */
function sortSlots(cats: string[]): string[] {
  const order = CENTER_SLOTS as readonly string[];
  return [...cats].sort((a, b) => {
    const ia = order.indexOf(categoryToSlot(a));
    const ib = order.indexOf(categoryToSlot(b));
    if (ia !== -1 && ib !== -1) return ia - ib;
    if (ia !== -1) return -1;
    if (ib !== -1) return 1;
    return 0;
  });
}

export function initialLoaded(data: OutfitSuggestionsResponse): State {
  const slots = sortSlots(Object.keys(data.suggestions));
  const cursor: Record<string, number> = {};
  const chosen: Record<string, string | null> = {};
  for (const s of slots) {
    cursor[s] = 0;
    chosen[s] = null;
  }
  return {
    status: "loaded",
    seed: data.seed,
    slots,
    pools: data.suggestions,
    cursor,
    chosen,
    activeSlot: null,
  };
}

/** The candidate currently in the spotlight for the active slot, or null. */
export function currentCandidate(state: State): SuggestionItem | null {
  if (state.status !== "loaded" || !state.activeSlot) return null;
  const pool = state.pools[state.activeSlot] ?? [];
  return pool[state.cursor[state.activeSlot]] ?? null;
}

export function reducer(state: State, action: Action): State {
  switch (action.type) {
    case "FETCH_SUCCESS":
      return initialLoaded(action.data);
    case "FETCH_ERROR":
      return { status: "error", message: action.message };
    case "SET_ACTIVE_SLOT":
      if (state.status !== "loaded") return state;
      return { ...state, activeSlot: action.slot };
    case "REJECT": {
      if (state.status !== "loaded" || !state.activeSlot) return state;
      const slot = state.activeSlot;
      return { ...state, cursor: { ...state.cursor, [slot]: state.cursor[slot] + 1 } };
    }
    case "ACCEPT": {
      if (state.status !== "loaded" || !state.activeSlot) return state;
      const cand = currentCandidate(state);
      if (!cand) return state;
      return {
        ...state,
        chosen: { ...state.chosen, [state.activeSlot]: cand.item_id },
        activeSlot: null,
      };
    }
    case "UNCHOOSE": {
      if (state.status !== "loaded") return state;
      return { ...state, chosen: { ...state.chosen, [action.slot]: null } };
    }
    default:
      return state;
  }
}
