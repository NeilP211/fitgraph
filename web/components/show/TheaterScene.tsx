"use client";

import { useEffect, type ReactNode } from "react";
import Link from "next/link";
import MusicToggle from "@/components/audio/MusicToggle";

/**
 * The dark theater shell. Renders a full-bleed fixed layer over the whole site
 * (covering the global nav), lights the runway with a spotlight, and exposes an
 * exit + mute control. Adds `theater-dark` to <body> so chrome behind it is
 * black (no cream flashes during the page transition).
 */
export default function TheaterScene({
  children,
  soundOn,
  onToggleSound,
}: {
  children: ReactNode;
  soundOn: boolean;
  onToggleSound: () => void;
}) {
  useEffect(() => {
    document.body.classList.add("theater-dark");
    return () => document.body.classList.remove("theater-dark");
  }, []);

  return (
    <div className="theater-spotlight fixed inset-0 z-[100] overflow-y-auto text-[#f4ecd8]">
      <div className="theater-vignette pointer-events-none fixed inset-0 z-0" aria-hidden="true" />

      <Link
        href="/"
        className="fixed left-4 top-4 z-20 text-[11px] uppercase tracking-[0.18em] text-[#f4ecd8]/70 transition-colors hover:text-[#f4ecd8]"
        style={{ fontFamily: "var(--font-display-var), serif" }}
      >
        ← Leave the runway
      </Link>

      <div className="fixed right-4 top-4 z-20">
        <MusicToggle soundOn={soundOn} onToggle={onToggleSound} />
      </div>

      <div className="relative z-10 mx-auto flex max-w-3xl flex-col items-center px-4 pb-40 pt-16">
        {children}
      </div>
    </div>
  );
}
