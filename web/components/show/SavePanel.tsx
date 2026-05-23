"use client";

import { useState } from "react";
import Link from "next/link";
import { motion } from "motion/react";
import { saveOutfit } from "@/lib/api";
import { usePrefersReducedMotion } from "@/components/motion/usePrefersReducedMotion";

const DEMO_USER_ID = 1;

/** Bright camera-flash overlay (explicit white - independent of theme vars). */
function CameraFlash({ onDone }: { onDone: () => void }) {
  return (
    <>
      <div
        className="camera-flash pointer-events-none fixed inset-0 z-[120]"
        style={{ background: "#ffffff" }}
        onAnimationEnd={onDone}
        aria-hidden="true"
      />
      <div className="pointer-events-none fixed inset-0 z-[121] flex items-center justify-center" aria-hidden="true">
        <motion.div
          initial={{ scale: 0.5, opacity: 0 }}
          animate={{ scale: 1.5, opacity: [0, 1, 0] }}
          transition={{ duration: 0.3, ease: "easeOut" }}
          className="select-none text-4xl"
          style={{ filter: "drop-shadow(0 0 8px #EFE7D4)" }}
        >
          ✦
        </motion.div>
      </div>
    </>
  );
}

/** Dark-theater save panel: name the look and save it (seed + chosen pieces). */
export default function SavePanel({
  seedItemId,
  selectedIds,
  savedName,
  setSavedName,
}: {
  seedItemId: string;
  selectedIds: string[];
  savedName: string;
  setSavedName: (v: string) => void;
}) {
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedId, setSavedId] = useState<number | null>(null);
  const [showFlash, setShowFlash] = useState(false);
  const reduced = usePrefersReducedMotion();

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
      setSavedName(name.trim());
      if (!reduced) {
        setShowFlash(true);
        setTimeout(() => {
          setSavedId(outfit.outfit_id);
          setShowFlash(false);
        }, 320);
      } else {
        setSavedId(outfit.outfit_id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save outfit.");
    } finally {
      setSaving(false);
    }
  };

  if (savedId !== null) {
    return (
      <motion.div
        initial={reduced ? false : { opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="flex items-center justify-between gap-4 rounded-sm border border-[#f4ecd8]/15 bg-black/40 px-5 py-3"
      >
        <div className="flex items-center gap-3">
          <span className="flex h-7 w-7 items-center justify-center rounded-sm border border-[#EFE7D4]/40 bg-[#EFE7D4]/15 text-sm font-bold text-[#EFE7D4]">
            ✓
          </span>
          <div>
            <p className="text-sm font-medium text-[#f4ecd8]" style={{ fontFamily: "var(--font-body-var), serif" }}>
              Look saved - &ldquo;{savedName}&rdquo;
            </p>
            <p className="text-xs text-[#f4ecd8]/60" style={{ fontFamily: "var(--font-body-var), serif" }}>
              {pieceCount} piece{pieceCount !== 1 ? "s" : ""}
            </p>
          </div>
        </div>
        <Link
          href="/outfits"
          className="rounded-sm bg-[#EFE7D4] px-4 py-1.5 text-xs uppercase tracking-[0.12em] text-[#0a0a0b] transition-colors hover:bg-[#FBF6E9]"
          style={{ fontFamily: "var(--font-body-var), serif" }}
        >
          View Outfits
        </Link>
      </motion.div>
    );
  }

  return (
    <>
      {showFlash && <CameraFlash onDone={() => {}} />}
      <form onSubmit={handleSave} className="flex flex-wrap items-center gap-3">
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Name this look…"
            aria-label="Outfit name"
            className="w-full rounded-sm border border-[#f4ecd8]/20 bg-black/30 px-3 py-2 text-sm text-[#f4ecd8] placeholder:text-[#f4ecd8]/40 focus:border-[#EFE7D4] focus:outline-none focus:ring-1 focus:ring-[#EFE7D4]/40"
            style={{ fontFamily: "var(--font-body-var), serif" }}
          />
          {error && (
            <p role="alert" className="text-xs text-red-300" style={{ fontFamily: "var(--font-body-var), serif" }}>
              {error}
            </p>
          )}
        </div>
        <button
          type="submit"
          disabled={!name.trim() || saving || selectedIds.length === 0}
          className="flex-shrink-0 whitespace-nowrap rounded-sm bg-[#EFE7D4] px-5 py-2 text-xs uppercase tracking-[0.12em] text-[#0a0a0b] transition-colors hover:bg-[#FBF6E9] disabled:cursor-not-allowed disabled:opacity-50"
          style={{ fontFamily: "var(--font-body-var), serif" }}
        >
          {saving ? "Saving…" : "Save the Look"}
        </button>
      </form>
    </>
  );
}
