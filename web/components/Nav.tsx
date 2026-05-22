"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/", label: "Browse" },
  { href: "/outfits", label: "Saved Outfits" },
];

export default function Nav() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-50 border-b border-rule bg-paper/95 backdrop-blur-sm">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        {/* Brand wordmark */}
        <Link href="/" className="flex items-center gap-4 group">
          {/* Tiny side labels flanking the wordmark */}
          <span className="hidden sm:block text-[9px] font-body uppercase tracking-[0.2em] text-ink-soft leading-tight text-right">
            Style<br />AI
          </span>
          <span
            className="font-display font-semibold text-xl uppercase tracking-[0.18em] text-ink group-hover:text-accent transition-colors"
            style={{ fontFamily: "var(--font-display-var), serif" }}
          >
            FITGRAPH
          </span>
          <span className="hidden sm:block text-[9px] font-body uppercase tracking-[0.2em] text-ink-soft leading-tight">
            The<br />Catalog
          </span>
        </Link>

        {/* Navigation links */}
        <nav className="flex items-center gap-1">
          {links.map(({ href, label }) => {
            const active = pathname === href;
            return (
              <Link
                key={href}
                href={href}
                className={`px-4 py-2 text-xs uppercase tracking-[0.14em] transition-colors border-b-2 ${
                  active
                    ? "text-accent border-accent font-medium"
                    : "text-ink-soft border-transparent hover:text-ink hover:border-rule"
                }`}
                style={{ fontFamily: "var(--font-body-var), serif" }}
              >
                {label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
