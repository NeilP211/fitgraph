"use client";

import { useEffect, useState } from "react";
import { getCategories } from "@/lib/api";
import type { CategoryCount } from "@/lib/api";

interface CategoryNavProps {
  selected: string | null;
  onSelect: (category: string) => void;
}

export default function CategoryNav({ selected, onSelect }: CategoryNavProps) {
  const [categories, setCategories] = useState<CategoryCount[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const resp = await getCategories();
        if (mounted) {
          setCategories(resp.categories);
          // Auto-select the first (most-populous) category if none selected
          if (!selected && resp.categories.length > 0) {
            onSelect(resp.categories[0].category);
          }
        }
      } catch (err) {
        if (mounted)
          setError(
            err instanceof Error ? err.message : "Failed to load categories."
          );
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => {
      mounted = false;
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (loading) {
    return (
      <div
        aria-busy="true"
        aria-label="Loading categories"
        className="flex flex-wrap gap-2"
      >
        {Array.from({ length: 8 }).map((_, i) => (
          <div
            key={i}
            className="h-9 w-24 animate-pulse rounded-full bg-stone-200"
          />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div
        role="alert"
        className="rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700"
      >
        <strong>Error:</strong> {error}
      </div>
    );
  }

  return (
    <nav aria-label="Browse by category" className="flex flex-wrap gap-2">
      {categories.map(({ category, count }) => {
        const active = category === selected;
        const label = category
          .replace(/_/g, " ")
          .replace(/\b\w/g, (c) => c.toUpperCase());
        return (
          <button
            key={category}
            type="button"
            aria-pressed={active}
            onClick={() => onSelect(category)}
            className={`inline-flex items-center gap-1.5 rounded-full px-4 py-2 text-sm font-medium transition-all ${
              active
                ? "bg-stone-900 text-white shadow-sm"
                : "bg-white border border-stone-200 text-stone-600 hover:border-stone-300 hover:bg-stone-50 hover:text-stone-900"
            }`}
          >
            {label}
            <span
              className={`text-xs tabular-nums ${
                active ? "text-stone-300" : "text-stone-400"
              }`}
            >
              {count.toLocaleString()}
            </span>
          </button>
        );
      })}
    </nav>
  );
}
