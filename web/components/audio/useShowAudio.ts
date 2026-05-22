"use client";

/**
 * useShowAudio — Phase 3 of "The Show"
 *
 * Audio is synthesised entirely via the Web Audio API (no binary asset files).
 * This avoids all licensing concerns and works offline.
 *
 * Design:
 *  - Single "sound on/off" toggle, persisted to localStorage (key: fitgraph_audio).
 *  - OFF by default — never autoplays; music only starts on a user gesture.
 *  - When ON:  ambient runway pad loops + cheers play on demand.
 *  - When OFF: both are silenced.
 *  - SSR-safe: all Web Audio / localStorage access is guarded behind typeof checks.
 *
 * Ambient pad:  3 detuned sine oscillators (root + 5th + octave) fed through a
 *               low-pass filter and a slow (4 s) amplitude LFO, giving a gentle
 *               breathing lounge-music feel.
 *
 * Applause SFX: a filtered white-noise burst with a fast attack and smooth
 *               exponential decay (~0.9 s total), imitating a small crowd cheer.
 */

import { useEffect, useRef, useState, useCallback } from "react";

const STORAGE_KEY = "fitgraph_audio";

// ---------------------------------------------------------------------------
// Helpers — pure Web Audio synthesis (no fetch / no binary assets)
// ---------------------------------------------------------------------------

/** Create the ambient pad node graph. Returns { gainNode, stop }. */
function createAmbientPad(ctx: AudioContext): { masterGain: GainNode; stop: () => void } {
  const masterGain = ctx.createGain();
  masterGain.gain.setValueAtTime(0.0, ctx.currentTime);
  masterGain.gain.linearRampToValueAtTime(0.18, ctx.currentTime + 2.0); // fade in
  masterGain.connect(ctx.destination);

  // Low-pass filter for warmth
  const filter = ctx.createBiquadFilter();
  filter.type = "lowpass";
  filter.frequency.setValueAtTime(800, ctx.currentTime);
  filter.Q.setValueAtTime(0.8, ctx.currentTime);
  filter.connect(masterGain);

  // Slow amplitude LFO (breathing, 0.25 Hz ≈ 4 s cycle)
  const lfo = ctx.createOscillator();
  const lfoGain = ctx.createGain();
  lfo.type = "sine";
  lfo.frequency.setValueAtTime(0.22, ctx.currentTime);
  lfoGain.gain.setValueAtTime(0.04, ctx.currentTime);
  lfo.connect(lfoGain);
  lfoGain.connect(masterGain.gain);
  lfo.start();

  // Root note — A2 (110 Hz), detune +0
  const osc0 = ctx.createOscillator();
  const g0 = ctx.createGain();
  osc0.type = "sine";
  osc0.frequency.setValueAtTime(110, ctx.currentTime);
  g0.gain.setValueAtTime(0.55, ctx.currentTime);
  osc0.connect(g0);
  g0.connect(filter);
  osc0.start();

  // Perfect fifth — E3 (165 Hz), detune +3 cents
  const osc1 = ctx.createOscillator();
  const g1 = ctx.createGain();
  osc1.type = "sine";
  osc1.frequency.setValueAtTime(165, ctx.currentTime);
  osc1.detune.setValueAtTime(3, ctx.currentTime);
  g1.gain.setValueAtTime(0.30, ctx.currentTime);
  osc1.connect(g1);
  g1.connect(filter);
  osc1.start();

  // Octave — A3 (220 Hz), detune -5 cents (gives subtle beating)
  const osc2 = ctx.createOscillator();
  const g2 = ctx.createGain();
  osc2.type = "sine";
  osc2.frequency.setValueAtTime(220, ctx.currentTime);
  osc2.detune.setValueAtTime(-5, ctx.currentTime);
  g2.gain.setValueAtTime(0.18, ctx.currentTime);
  osc2.connect(g2);
  g2.connect(filter);
  osc2.start();

  // Sub harmonic hint — A1 (55 Hz) very soft
  const osc3 = ctx.createOscillator();
  const g3 = ctx.createGain();
  osc3.type = "sine";
  osc3.frequency.setValueAtTime(55, ctx.currentTime);
  g3.gain.setValueAtTime(0.10, ctx.currentTime);
  osc3.connect(g3);
  g3.connect(filter);
  osc3.start();

  const stop = () => {
    const t = ctx.currentTime;
    masterGain.gain.linearRampToValueAtTime(0, t + 0.4); // short fade-out
    setTimeout(() => {
      try {
        osc0.stop(); osc1.stop(); osc2.stop(); osc3.stop(); lfo.stop();
      } catch {
        // already stopped / context closed — ignore
      }
    }, 450);
  };

  return { masterGain, stop };
}

/** Play a one-shot applause/cheer SFX burst (filtered white noise, ~0.9 s). */
function playApplauseSFX(ctx: AudioContext): void {
  const duration = 0.9;
  const bufferSize = Math.floor(ctx.sampleRate * duration);
  const buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
  const data = buffer.getChannelData(0);

  // White noise
  for (let i = 0; i < bufferSize; i++) {
    data[i] = Math.random() * 2 - 1;
  }

  const source = ctx.createBufferSource();
  source.buffer = buffer;

  // Band-pass filter: crowd applause lives ~1 kHz–4 kHz
  const bp = ctx.createBiquadFilter();
  bp.type = "bandpass";
  bp.frequency.setValueAtTime(2200, ctx.currentTime);
  bp.Q.setValueAtTime(0.7, ctx.currentTime);

  // Gain envelope — fast attack, smooth exponential decay
  const gain = ctx.createGain();
  const t0 = ctx.currentTime;
  gain.gain.setValueAtTime(0, t0);
  gain.gain.linearRampToValueAtTime(0.55, t0 + 0.04);   // 40 ms attack
  gain.gain.setValueAtTime(0.55, t0 + 0.04);
  gain.gain.exponentialRampToValueAtTime(0.001, t0 + duration);

  source.connect(bp);
  bp.connect(gain);
  gain.connect(ctx.destination);
  source.start(t0);
  source.stop(t0 + duration);
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

interface ShowAudioState {
  /** Whether sound is currently enabled (ON). */
  soundOn: boolean;
  /** Toggle sound on/off. Starts or stops the ambient pad; persists choice. */
  toggleMusic: () => void;
  /** Play the cheer SFX if sound is ON. Safe to call unconditionally. */
  playCheer: () => void;
}

export function useShowAudio(): ShowAudioState {
  // Read initial persisted value (default: OFF)
  const [soundOn, setSoundOn] = useState<boolean>(() => {
    if (typeof window === "undefined") return false;
    try {
      return localStorage.getItem(STORAGE_KEY) === "on";
    } catch {
      return false;
    }
  });

  // Refs — stable across renders; created lazily on first user gesture.
  // NOTE: soundOn state drives rendering; we keep a separate ref only for
  // callbacks that need the latest value without being re-created on every
  // render. We sync it inside useEffect (not during render) to satisfy the
  // react-hooks/refs rule.
  const ctxRef = useRef<AudioContext | null>(null);
  const padStopRef = useRef<(() => void) | null>(null);
  const soundOnRef = useRef(soundOn);

  // Keep soundOnRef in sync with state — runs after render, never during.
  useEffect(() => {
    soundOnRef.current = soundOn;
  }, [soundOn]);

  /** Lazily create (or resume) the AudioContext. SSR-safe. */
  const getCtx = useCallback((): AudioContext | null => {
    if (typeof window === "undefined") return null;
    if (!ctxRef.current) {
      try {
        ctxRef.current = new AudioContext();
      } catch {
        return null;
      }
    }
    // Resume if suspended (needed after autoplay policy suspends it)
    if (ctxRef.current.state === "suspended") {
      void ctxRef.current.resume();
    }
    return ctxRef.current;
  }, []);

  /** Start the ambient pad loop. Idempotent — won't double-start. */
  const startPad = useCallback(() => {
    if (padStopRef.current) return; // already running
    const ctx = getCtx();
    if (!ctx) return;
    const { stop } = createAmbientPad(ctx);
    padStopRef.current = stop;
  }, [getCtx]);

  /** Stop the ambient pad. Idempotent. */
  const stopPad = useCallback(() => {
    if (!padStopRef.current) return;
    padStopRef.current();
    padStopRef.current = null;
  }, []);

  const toggleMusic = useCallback(() => {
    // We use a functional updater so we don't need soundOn in the dep array.
    setSoundOn((prev) => {
      const next = !prev;
      soundOnRef.current = next; // safe: called inside setState updater (not render)

      // Persist
      try {
        localStorage.setItem(STORAGE_KEY, next ? "on" : "off");
      } catch {
        // localStorage unavailable — ignore
      }

      if (next) {
        // startPad is stable (no closure over soundOn); call directly.
        startPad();
      } else {
        stopPad();
      }

      return next;
    });
  }, [startPad, stopPad]);

  const playCheer = useCallback(() => {
    if (!soundOnRef.current) return;
    const ctx = getCtx();
    if (!ctx) return;
    playApplauseSFX(ctx);
  }, [getCtx]);

  // If page is reloaded with soundOn=true from localStorage, auto-start pad
  // ONLY after a user gesture has resumed the AudioContext.
  // We do NOT start on mount — we wait for the first toggleMusic or playCheer.
  // This ensures we never violate the browser autoplay policy.

  // Clean up pad on unmount
  useEffect(() => {
    return () => {
      stopPad();
      // Close the AudioContext to free OS resources
      if (ctxRef.current && ctxRef.current.state !== "closed") {
        void ctxRef.current.close();
        ctxRef.current = null;
      }
    };
  }, [stopPad]);

  return { soundOn, toggleMusic, playCheer };
}
