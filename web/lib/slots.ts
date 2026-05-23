/**
 * Pure slot configuration for the outfit figure — React-free so it can be
 * imported by the show reducer and unit tests without dragging in a client
 * component. `StageFigure` re-exports these for existing callers.
 */

/** Vertical body slots in top-to-bottom order */
export const CENTER_SLOTS = [
  "hats",
  "sunglasses",
  "outerwear",
  "tops",
  "all-body",
  "bottoms",
  "shoes",
] as const;

export const SIDE_SLOTS = [
  "bags",
  "jewellery",
  "scarves",
  "accessories",
] as const;

export type CenterSlot = (typeof CENTER_SLOTS)[number];
export type SideSlot = (typeof SIDE_SLOTS)[number];
export type SlotName = CenterSlot | SideSlot;

/** Map a semantic_category string → SlotName (unmapped → "accessories") */
export function categoryToSlot(cat: string | null): SlotName {
  if (!cat) return "accessories";
  const c = cat.toLowerCase().trim();
  if (c === "hats" || c === "hat") return "hats";
  if (c === "sunglasses" || c === "glasses" || c === "eyewear") return "sunglasses";
  if (c === "outerwear" || c === "jacket" || c === "coat") return "outerwear";
  if (c === "tops" || c === "top" || c === "shirts" || c === "blouses" || c === "shirt" || c === "blouse") return "tops";
  if (c === "all-body" || c === "dresses" || c === "dress" || c === "jumpsuits" || c === "jumpsuit" || c === "all_body" || c === "all body") return "all-body";
  if (c === "bottoms" || c === "bottom" || c === "pants" || c === "skirts" || c === "shorts" || c === "skirt" || c === "pant") return "bottoms";
  if (c === "shoes" || c === "shoe" || c === "boots" || c === "sneakers" || c === "footwear") return "shoes";
  if (c === "bags" || c === "bag" || c === "handbag" || c === "purse") return "bags";
  if (c === "jewellery" || c === "jewelry" || c === "necklace" || c === "earrings" || c === "bracelet" || c === "ring") return "jewellery";
  if (c === "scarves" || c === "scarf") return "scarves";
  if (c === "accessories" || c === "accessory" || c === "belt" || c === "watch") return "accessories";
  return "accessories";
}
