"use client";

import { useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { saveOutfit, imageUrl } from "@/lib/api";
import type { CatalogItem } from "@/lib/api";

const DEMO_USER_ID = 1;

interface OutfitTrayProps {
  seedItem: CatalogItem;
  selectedIds: string[];
  seedItemId: string;
}

export default function OutfitTray({
  seedItem,
  selectedIds,
  seedItemId,
}: OutfitTrayProps) {
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedOutfitId, setSavedOutfitId] = useState<number | null>(null);

  const allIds = [seedItemId, ...selectedIds];
  const pieceCount = allIds.length;

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || saving) return;
    setSaving(true);
    setError(null);
    try {
      const outfit = await saveOutfit({
        user_id: DEMO_USER_ID,
        name: name.trim(),
        item_ids: allIds,
      });
      setSavedOutfitId(outfit.outfit_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save outfit.");
    } finally {
      setSaving(false);
    }
  };

  // Success state
  if (savedOutfitId !== null) {
    return (
      <div className="fixed bottom-0 inset-x-0 z-40 border-t border-stone-200 bg-white/95 backdrop-blur-sm shadow-2xl">
        <div className="mx-auto max-w-6xl px-6 py-4 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-emerald-100 text-emerald-600 text-base">
              ✓
            </span>
            <div>
              <p className="text-sm font-semibold text-stone-900">
                Outfit saved!
              </p>
              <p className="text-xs text-stone-500">
                &ldquo;{name}&rdquo; saved with {pieceCount} piece
                {pieceCount !== 1 ? "s" : ""}
              </p>
            </div>
          </div>
          <Link
            href="/outfits"
            className="rounded-xl bg-stone-900 px-5 py-2 text-sm font-semibold text-white hover:bg-stone-700 transition-colors shadow-sm"
          >
            View saved outfits
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed bottom-0 inset-x-0 z-40 border-t border-stone-200 bg-white/95 backdrop-blur-sm shadow-2xl">
      <div className="mx-auto max-w-6xl px-6 py-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:gap-4">
          {/* Item strip */}
          <div className="flex items-center gap-2 min-w-0 flex-1">
            <span className="text-xs font-medium text-stone-500 flex-shrink-0">
              {pieceCount} piece{pieceCount !== 1 ? "s" : ""}:
            </span>
            <div className="flex items-center gap-1.5 overflow-x-auto">
              {/* Seed */}
              <div
                className="relative flex-shrink-0 h-10 w-10 overflow-hidden rounded-lg bg-stone-100 ring-2 ring-stone-900"
                title={seedItem.title || "Seed item"}
              >
                <Image
                  src={imageUrl(seedItemId)}
                  alt={seedItem.title || "Seed item"}
                  fill
                  sizes="40px"
                  className="object-cover"
                  unoptimized
                />
              </div>
              {/* Selected items */}
              {selectedIds.map((id) => (
                <div
                  key={id}
                  className="relative flex-shrink-0 h-10 w-10 overflow-hidden rounded-lg bg-stone-100 ring-2 ring-stone-400"
                >
                  <Image
                    src={imageUrl(id)}
                    alt={`Selected item ${id}`}
                    fill
                    sizes="40px"
                    className="object-cover"
                    unoptimized
                  />
                </div>
              ))}
              {/* Empty placeholder slots */}
              {selectedIds.length === 0 && (
                <span className="text-xs text-stone-400 pl-1">
                  Select items above to build your outfit
                </span>
              )}
            </div>
          </div>

          {/* Save form */}
          <form
            onSubmit={handleSave}
            className="flex items-center gap-2 flex-shrink-0"
          >
            <div className="flex flex-col gap-1">
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Name this outfit…"
                aria-label="Outfit name"
                className="rounded-xl border border-stone-300 px-3 py-2 text-sm text-stone-800 placeholder:text-stone-400 focus:outline-none focus:ring-2 focus:ring-stone-400 w-44"
              />
              {error && (
                <p role="alert" className="text-xs text-red-500">
                  {error}
                </p>
              )}
            </div>
            <button
              type="submit"
              disabled={!name.trim() || saving || selectedIds.length === 0}
              className="rounded-xl bg-stone-900 px-5 py-2 text-sm font-semibold text-white hover:bg-stone-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-sm whitespace-nowrap"
            >
              {saving ? "Saving…" : "Save outfit"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
