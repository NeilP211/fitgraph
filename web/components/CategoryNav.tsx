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
            className="h-8 w-28 animate-pulse rounded-sm bg-rule/60"
          />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div
        role="alert"
        className="rounded-sm bg-surface border border-rule px-4 py-3 text-sm text-accent-deep"
        style={{ fontFamily: "var(--font-body-var), serif" }}
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
            className={`inline-flex items-center gap-2 rounded-sm px-4 py-1.5 text-xs uppercase tracking-[0.14em] transition-all border ${
              active
                ? "bg-ink text-paper border-ink"
                : "bg-surface text-ink-soft border-rule hover:border-ink-soft hover:text-ink"
            }`}
            style={{ fontFamily: "var(--font-body-var), serif" }}
          >
            {label}
            <span
              className={`tabular-nums text-[10px] ${
                active ? "text-rule" : "text-rule"
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
