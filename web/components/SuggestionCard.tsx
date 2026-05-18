"use client";

import { useState } from "react";
import Image from "next/image";
import { imageUrl, postFeedback } from "@/lib/api";
import type { SuggestionItem } from "@/lib/api";

const DEMO_USER_ID = 1;

interface SuggestionCardProps {
  item: SuggestionItem;
  queryItemId: string;
  selected: boolean;
  onToggleSelect: () => void;
}

function ScoreBadge({ score }: { score: number }) {
  // Map [-1, 1] → [0, 100]
  const pct = Math.round(((score + 1) / 2) * 100);
  const color =
    pct >= 75
      ? "bg-emerald-100 text-emerald-700"
      : pct >= 50
      ? "bg-amber-100 text-amber-700"
      : "bg-stone-100 text-stone-500";

  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${color}`}
      title={`Raw score: ${score.toFixed(3)}`}
    >
      {pct}% match
    </span>
  );
}

export default function SuggestionCard({
  item,
  queryItemId,
  selected,
  onToggleSelect,
}: SuggestionCardProps) {
  const [feedback, setFeedback] = useState<1 | -1 | null>(null);
  const [feedbackLoading, setFeedbackLoading] = useState(false);

  const submitFeedback = async (rating: 1 | -1) => {
    if (feedback !== null || feedbackLoading) return;
    setFeedbackLoading(true);
    try {
      await postFeedback(DEMO_USER_ID, queryItemId, item.item_id, rating);
      setFeedback(rating);
    } catch {
      // ignore network errors silently for feedback
    } finally {
      setFeedbackLoading(false);
    }
  };

  return (
    <article
      className={`group relative flex flex-col overflow-hidden rounded-2xl border bg-white shadow-sm transition-all
        ${
          selected
            ? "border-stone-900 ring-2 ring-stone-900"
            : "border-stone-200 hover:border-stone-300 hover:shadow-md"
        }`}
    >
      {/* Selection toggle */}
      <button
        type="button"
        onClick={onToggleSelect}
        aria-pressed={selected}
        aria-label={selected ? "Deselect item" : "Select item for outfit"}
        className={`absolute top-2 left-2 z-10 flex h-6 w-6 items-center justify-center rounded-full border-2 text-xs font-bold transition-all
          ${
            selected
              ? "border-stone-900 bg-stone-900 text-white"
              : "border-white/70 bg-white/70 text-transparent group-hover:border-stone-400"
          }`}
      >
        ✓
      </button>

      {/* Image */}
      <div className="relative aspect-square w-full bg-stone-100 overflow-hidden">
        <Image
          src={imageUrl(item.item_id)}
          alt={item.title || `Item ${item.item_id}`}
          fill
          sizes="(min-width: 1024px) 20vw, (min-width: 640px) 33vw, 50vw"
          className="object-cover transition-transform duration-300 group-hover:scale-105"
          unoptimized
        />
      </div>

      {/* Content */}
      <div className="flex flex-1 flex-col gap-2 p-4">
        <div className="flex items-start justify-between gap-2">
          <p className="text-sm font-medium text-stone-800 leading-snug line-clamp-2">
            {item.title || "Untitled piece"}
          </p>
          <ScoreBadge score={item.score} />
        </div>

        <p className="text-xs text-stone-400 capitalize">
          {item.semantic_category}
        </p>

        {/* Feedback */}
        <div className="mt-auto flex items-center gap-2 pt-2 border-t border-stone-100">
          <span className="text-xs text-stone-400 flex-1">
            {feedback === 1
              ? "👍 Liked"
              : feedback === -1
              ? "👎 Disliked"
              : "Rate this suggestion"}
          </span>
          {feedback === null && (
            <>
              <button
                type="button"
                aria-label="Thumbs up — good match"
                disabled={feedbackLoading}
                onClick={() => submitFeedback(1)}
                className="rounded-lg p-1.5 text-stone-400 hover:bg-emerald-50 hover:text-emerald-600 transition-colors disabled:opacity-50"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="currentColor"
                  className="h-4 w-4"
                  aria-hidden="true"
                >
                  <path d="M7.493 18.75c-.425 0-.82-.236-.975-.632A7.48 7.48 0 016 15.375c0-1.75.599-3.358 1.602-4.634.151-.192.373-.309.6-.397.473-.183.89-.514 1.212-.924a9.042 9.042 0 012.861-2.4c.723-.384 1.35-.956 1.653-1.715a4.498 4.498 0 00.322-1.672V3a.75.75 0 01.75-.75 2.25 2.25 0 012.25 2.25c0 1.152-.26 2.243-.723 3.218-.266.558.107 1.282.725 1.282h3.126c1.026 0 1.945.694 2.054 1.715.045.422.068.85.068 1.285a11.95 11.95 0 01-2.649 7.521c-.388.482-.987.729-1.605.729H14.23c-.483 0-.964-.078-1.423-.23l-3.114-1.04a4.501 4.501 0 00-1.423-.23h-.777zM2.331 10.977a11.969 11.969 0 00-.831 4.398 12 12 0 00.52 3.507c.26.85 1.084 1.368 1.973 1.368H4.9c.445 0 .72-.498.523-.898a8.963 8.963 0 01-.924-3.977c0-1.708.476-3.305 1.302-4.666.245-.403-.028-.959-.5-.959H4.25c-.832 0-1.612.453-1.918 1.227z" />
                </svg>
              </button>
              <button
                type="button"
                aria-label="Thumbs down — poor match"
                disabled={feedbackLoading}
                onClick={() => submitFeedback(-1)}
                className="rounded-lg p-1.5 text-stone-400 hover:bg-red-50 hover:text-red-500 transition-colors disabled:opacity-50"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="currentColor"
                  className="h-4 w-4"
                  aria-hidden="true"
                >
                  <path d="M15.73 5.25h1.035A7.465 7.465 0 0118 9.375a7.465 7.465 0 01-1.235 4.125h-.148c-.806 0-1.534.446-2.031 1.08a9.04 9.04 0 01-2.861 2.4c-.723.384-1.35.956-1.653 1.715a4.498 4.498 0 00-.322 1.672V21a.75.75 0 01-.75.75 2.25 2.25 0 01-2.25-2.25c0-1.152.26-2.243.723-3.218.266-.558-.107-1.282-.725-1.282H3.622c-1.026 0-1.945-.694-2.054-1.715A12.134 12.134 0 011.5 12c0-2.848.992-5.464 2.649-7.521.388-.482.987-.729 1.605-.729H9.77a4.5 4.5 0 011.423.23l3.114 1.04a4.5 4.5 0 001.423.23zM21.669 13.023c.536-1.362.831-2.845.831-4.398 0-1.22-.182-2.398-.52-3.507-.26-.85-1.084-1.368-1.973-1.368H19.1c-.445 0-.72.498-.523.898.591 1.2.924 2.55.924 3.977a8.959 8.959 0 01-1.302 4.666c-.245.403.028.959.5.959h1.053c.832 0 1.612-.453 1.918-1.227z" />
                </svg>
              </button>
            </>
          )}
        </div>
      </div>
    </article>
  );
}
