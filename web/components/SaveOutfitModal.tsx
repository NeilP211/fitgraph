"use client";

import { useState } from "react";
import { createOutfit } from "@/lib/api";

const DEMO_USER_ID = 1;

interface SaveOutfitModalProps {
  itemIds: string[];
  onClose: () => void;
  onSaved: () => void;
}

export default function SaveOutfitModal({
  itemIds,
  onClose,
  onSaved,
}: SaveOutfitModalProps) {
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setSaving(true);
    setError(null);
    try {
      await createOutfit(DEMO_USER_ID, name.trim(), itemIds);
      onSaved();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save outfit.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="save-outfit-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/40 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Panel */}
      <div className="relative z-10 w-full max-w-sm rounded-2xl bg-white p-6 shadow-2xl">
        <h2
          id="save-outfit-title"
          className="text-lg font-semibold text-stone-900 mb-1"
        >
          Save Outfit
        </h2>
        <p className="text-sm text-stone-500 mb-5">
          {itemIds.length} piece{itemIds.length !== 1 ? "s" : ""} selected
        </p>

        <form onSubmit={handleSave} className="space-y-4">
          <div className="flex flex-col gap-1.5">
            <label
              htmlFor="outfit-name"
              className="text-xs font-medium text-stone-500 uppercase tracking-wide"
            >
              Outfit name
            </label>
            <input
              id="outfit-name"
              type="text"
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Summer Casual"
              className="rounded-xl border border-stone-300 px-4 py-2.5 text-sm text-stone-800 placeholder:text-stone-400 focus:outline-none focus:ring-2 focus:ring-stone-400"
            />
          </div>

          {error && (
            <p role="alert" className="text-xs text-red-500">
              {error}
            </p>
          )}

          <div className="flex gap-3 pt-1">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 rounded-xl border border-stone-300 px-4 py-2.5 text-sm font-medium text-stone-700 hover:bg-stone-50 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!name.trim() || saving}
              className="flex-1 rounded-xl bg-stone-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-stone-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {saving ? "Saving…" : "Save"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
