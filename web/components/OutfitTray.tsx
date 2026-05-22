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
      <div className="fixed bottom-0 inset-x-0 z-40 border-t border-rule bg-surface/98 backdrop-blur-sm shadow-2xl">
        <div className="mx-auto max-w-6xl px-6 py-4 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <span className="flex h-8 w-8 items-center justify-center rounded-sm bg-accent/10 border border-accent/30 text-accent text-sm font-bold">
              ✓
            </span>
            <div>
              <p
                className="text-sm font-medium text-ink"
                style={{ fontFamily: "var(--font-body-var), serif" }}
              >
                Outfit saved
              </p>
              <p
                className="text-xs text-ink-soft"
                style={{ fontFamily: "var(--font-body-var), serif" }}
              >
                &ldquo;{name}&rdquo; — {pieceCount} piece{pieceCount !== 1 ? "s" : ""}
              </p>
            </div>
          </div>
          <Link
            href="/outfits"
            className="rounded-sm bg-accent px-5 py-2 text-xs uppercase tracking-[0.12em] text-paper hover:bg-accent-deep transition-colors"
            style={{ fontFamily: "var(--font-body-var), serif" }}
          >
            View Outfits
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed bottom-0 inset-x-0 z-40 border-t border-rule bg-surface/98 backdrop-blur-sm shadow-2xl">
      <div className="mx-auto max-w-6xl px-6 py-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:gap-4">
          {/* Item strip */}
          <div className="flex items-center gap-2 min-w-0 flex-1">
            <span
              className="text-[10px] uppercase tracking-[0.12em] text-ink-soft flex-shrink-0"
              style={{ fontFamily: "var(--font-body-var), serif" }}
            >
              {pieceCount} piece{pieceCount !== 1 ? "s" : ""}:
            </span>
            <div className="flex items-center gap-1.5 overflow-x-auto">
              {/* Seed */}
              <div
                className="relative flex-shrink-0 h-10 w-10 overflow-hidden rounded-sm bg-rule/30 ring-2 ring-ink"
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
                  className="relative flex-shrink-0 h-10 w-10 overflow-hidden rounded-sm bg-rule/30 ring-2 ring-ink-soft"
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
                <span
                  className="text-[10px] uppercase tracking-[0.1em] text-ink-soft pl-1"
                  style={{ fontFamily: "var(--font-body-var), serif" }}
                >
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
                className="rounded-sm border border-rule bg-paper px-3 py-2 text-sm text-ink placeholder:text-ink-soft/70 focus:outline-none focus:border-ink-soft focus:ring-1 focus:ring-rule w-44"
                style={{ fontFamily: "var(--font-body-var), serif" }}
              />
              {error && (
                <p
                  role="alert"
                  className="text-xs text-accent-deep"
                  style={{ fontFamily: "var(--font-body-var), serif" }}
                >
                  {error}
                </p>
              )}
            </div>
            <button
              type="submit"
              disabled={!name.trim() || saving || selectedIds.length === 0}
              className="rounded-sm bg-accent px-5 py-2 text-xs uppercase tracking-[0.12em] text-paper hover:bg-accent-deep disabled:opacity-50 disabled:cursor-not-allowed transition-colors whitespace-nowrap"
              style={{ fontFamily: "var(--font-body-var), serif" }}
            >
              {saving ? "Saving…" : "Save Outfit"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
