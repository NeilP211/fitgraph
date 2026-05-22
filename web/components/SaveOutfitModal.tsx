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
        className="absolute inset-0 bg-ink/50 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Panel */}
      <div className="relative z-10 w-full max-w-sm rounded-sm bg-surface border border-rule p-6 shadow-2xl">
        {/* Header with hairline rule */}
        <h2
          id="save-outfit-title"
          className="text-base font-semibold uppercase tracking-[0.14em] text-ink mb-1"
          style={{ fontFamily: "var(--font-display-var), serif" }}
        >
          Save Outfit
        </h2>
        <div className="hr-rule mb-4" />
        <p
          className="text-sm text-ink-soft mb-5"
          style={{ fontFamily: "var(--font-body-var), serif" }}
        >
          {itemIds.length} piece{itemIds.length !== 1 ? "s" : ""} selected
        </p>

        <form onSubmit={handleSave} className="space-y-4">
          <div className="flex flex-col gap-1.5">
            <label
              htmlFor="outfit-name"
              className="text-[10px] uppercase tracking-[0.15em] text-ink-soft"
              style={{ fontFamily: "var(--font-body-var), serif" }}
            >
              Outfit Name
            </label>
            <input
              id="outfit-name"
              type="text"
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Summer Casual"
              className="rounded-sm border border-rule bg-paper px-4 py-2.5 text-sm text-ink placeholder:text-ink-soft/60 focus:outline-none focus:border-ink-soft focus:ring-1 focus:ring-rule"
              style={{ fontFamily: "var(--font-body-var), serif" }}
            />
          </div>

          {error && (
            <p
              role="alert"
              className="text-xs text-accent-deep"
              style={{ fontFamily: "var(--font-body-var), serif" }}
            >
              {error}
            </p>
          )}

          <div className="flex gap-3 pt-1">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 rounded-sm border border-rule px-4 py-2.5 text-xs uppercase tracking-[0.12em] text-ink-soft hover:border-ink-soft hover:text-ink transition-colors"
              style={{ fontFamily: "var(--font-body-var), serif" }}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!name.trim() || saving}
              className="flex-1 rounded-sm bg-accent px-4 py-2.5 text-xs uppercase tracking-[0.12em] text-paper hover:bg-accent-deep disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              style={{ fontFamily: "var(--font-body-var), serif" }}
            >
              {saving ? "Saving…" : "Save"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
