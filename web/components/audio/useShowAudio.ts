"use client";

/**
 * useShowAudio - audio for "The Show"
 *
 * Synthesised entirely via the Web Audio API (no binary asset files), so there
 * are no licensing concerns and it works offline.
 *
 * Design:
 *  - Single "sound on/off" toggle, persisted to localStorage (key: fitgraph_audio).
 *  - ON by default - but autoplay-safe: nothing plays until the first user
 *    gesture (call arm()); only OFF if the user explicitly toggled it off.
 *  - When ON:  an upbeat runway groove loops + a crowd cheer plays on demand.
 *  - When OFF: both are silenced.
 *  - SSR-safe: all Web Audio / localStorage access is guarded behind typeof checks.
 *
 * Runway groove: a glossy four-on-the-floor house loop (~122 BPM) - kick,
 *                offbeat hats, a filtered saw bass, and a bright triangle
 *                arpeggio - scheduled with a small lookahead clock.
 *
 * Crowd cheer:   a layered burst - a vocal "roar" swell (band-passed noise)
 *                + dozens of short clap transients (dense then thinning) + a
 *                couple of whistles. Sounds like a real crowd, not a single pop.
 */

import { useEffect, useRef, useState, useCallback } from "react";

const STORAGE_KEY = "fitgraph_audio";

// ---------------------------------------------------------------------------
// Runway groove - an upbeat looping house/electro bed (no assets)
// ---------------------------------------------------------------------------

function createRunwayGroove(ctx: AudioContext): { stop: () => void } {
  const master = ctx.createGain();
  master.gain.setValueAtTime(0.0001, ctx.currentTime);
  master.gain.linearRampToValueAtTime(0.2, ctx.currentTime + 1.2); // fade in
  master.connect(ctx.destination);

  // Gentle glue bus - open enough to stay bright (not muddy/ominous)
  const bus = ctx.createBiquadFilter();
  bus.type = "lowpass";
  bus.frequency.value = 3400;
  bus.connect(master);

  const bpm = 122;
  const beat = 60 / bpm;
  const stepDur = beat / 2; // 8th notes → 8 steps per bar
  let nextTime = ctx.currentTime + 0.1;
  let step = 0;

  // Bright vamp (A minor-ish, high octave) + a simple moving bassline
  const arp = [440, 523.25, 659.25, 783.99, 659.25, 523.25, 587.33, 659.25];
  const bassByBar = [55, 65.41, 49.0, 73.42]; // A1 C2 G1 D2

  const kick = (t: number) => {
    const o = ctx.createOscillator();
    const g = ctx.createGain();
    o.type = "sine";
    o.frequency.setValueAtTime(150, t);
    o.frequency.exponentialRampToValueAtTime(48, t + 0.11);
    g.gain.setValueAtTime(0.8, t);
    g.gain.exponentialRampToValueAtTime(0.001, t + 0.18);
    o.connect(g);
    g.connect(bus);
    o.start(t);
    o.stop(t + 0.2);
  };

  const hat = (t: number, open: boolean) => {
    const dur = open ? 0.11 : 0.035;
    const buf = ctx.createBuffer(1, Math.max(1, Math.floor(ctx.sampleRate * dur)), ctx.sampleRate);
    const d = buf.getChannelData(0);
    for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
    const src = ctx.createBufferSource();
    src.buffer = buf;
    const hp = ctx.createBiquadFilter();
    hp.type = "highpass";
    hp.frequency.value = 7500;
    const g = ctx.createGain();
    g.gain.setValueAtTime(open ? 0.12 : 0.16, t);
    g.gain.exponentialRampToValueAtTime(0.001, t + dur);
    src.connect(hp);
    hp.connect(g);
    g.connect(bus);
    src.start(t);
    src.stop(t + dur);
  };

  const bass = (t: number, freq: number) => {
    const o = ctx.createOscillator();
    const lp = ctx.createBiquadFilter();
    const g = ctx.createGain();
    o.type = "sawtooth";
    o.frequency.value = freq;
    lp.type = "lowpass";
    lp.frequency.value = 700;
    g.gain.setValueAtTime(0.0001, t);
    g.gain.linearRampToValueAtTime(0.26, t + 0.01);
    g.gain.exponentialRampToValueAtTime(0.001, t + beat * 0.85);
    o.connect(lp);
    lp.connect(g);
    g.connect(bus);
    o.start(t);
    o.stop(t + beat);
  };

  const pluck = (t: number, freq: number) => {
    const o = ctx.createOscillator();
    const g = ctx.createGain();
    o.type = "triangle";
    o.frequency.value = freq;
    g.gain.setValueAtTime(0.0001, t);
    g.gain.linearRampToValueAtTime(0.14, t + 0.005);
    g.gain.exponentialRampToValueAtTime(0.001, t + 0.22);
    o.connect(g);
    g.connect(bus);
    o.start(t);
    o.stop(t + 0.25);
  };

  const timer = setInterval(() => {
    while (nextTime < ctx.currentTime + 0.12) {
      const t = nextTime;
      const s = step % 8;
      const bar = Math.floor(step / 8);
      if (s % 2 === 0) {
        kick(t); // four-on-the-floor
        bass(t, bassByBar[bar % bassByBar.length]);
      }
      hat(t, s % 2 === 1); // open hats on the offbeats
      pluck(t, arp[step % arp.length]);
      nextTime += stepDur;
      step++;
    }
  }, 25);

  const stop = () => {
    clearInterval(timer);
    const t = ctx.currentTime;
    master.gain.cancelScheduledValues(t);
    master.gain.setValueAtTime(master.gain.value, t);
    master.gain.linearRampToValueAtTime(0, t + 0.3);
    setTimeout(() => {
      try {
        master.disconnect();
      } catch {
        // already disconnected
      }
    }, 400);
  };

  return { stop };
}

// ---------------------------------------------------------------------------
// Crowd cheer - layered roar + claps + whistles (one-shot)
// ---------------------------------------------------------------------------

function playCrowdCheer(ctx: AudioContext): void {
  const t0 = ctx.currentTime;
  const out = ctx.createGain();
  out.gain.value = 0.9;
  out.connect(ctx.destination);

  // 1) Vocal roar - band-passed noise that swells and falls
  const roarDur = 1.6;
  const rbuf = ctx.createBuffer(1, Math.floor(ctx.sampleRate * roarDur), ctx.sampleRate);
  const rd = rbuf.getChannelData(0);
  for (let i = 0; i < rd.length; i++) rd[i] = Math.random() * 2 - 1;
  const rsrc = ctx.createBufferSource();
  rsrc.buffer = rbuf;
  const rbp = ctx.createBiquadFilter();
  rbp.type = "bandpass";
  rbp.frequency.value = 900;
  rbp.Q.value = 0.5;
  const rg = ctx.createGain();
  rg.gain.setValueAtTime(0.0001, t0);
  rg.gain.linearRampToValueAtTime(0.5, t0 + 0.18);
  rg.gain.linearRampToValueAtTime(0.4, t0 + 0.75);
  rg.gain.exponentialRampToValueAtTime(0.001, t0 + roarDur);
  rsrc.connect(rbp);
  rbp.connect(rg);
  rg.connect(out);
  rsrc.start(t0);
  rsrc.stop(t0 + roarDur);

  // 2) Claps - many short transients, dense at first then thinning out
  const clapCount = 36;
  for (let i = 0; i < clapCount; i++) {
    const t = t0 + Math.pow(Math.random(), 0.6) * 1.2 + Math.random() * 0.02;
    const dur = 0.03;
    const cbuf = ctx.createBuffer(1, Math.max(1, Math.floor(ctx.sampleRate * dur)), ctx.sampleRate);
    const cd = cbuf.getChannelData(0);
    for (let j = 0; j < cd.length; j++) cd[j] = (Math.random() * 2 - 1) * (1 - j / cd.length);
    const csrc = ctx.createBufferSource();
    csrc.buffer = cbuf;
    const chp = ctx.createBiquadFilter();
    chp.type = "highpass";
    chp.frequency.value = 1500 + Math.random() * 1600;
    const cg = ctx.createGain();
    cg.gain.value = 0.1 + Math.random() * 0.1;
    csrc.connect(chp);
    chp.connect(cg);
    cg.connect(out);
    csrc.start(t);
    csrc.stop(t + dur);
  }

  // 3) A couple of whistles rising over the top
  for (let i = 0; i < 2; i++) {
    const t = t0 + 0.2 + Math.random() * 0.5;
    const o = ctx.createOscillator();
    const g = ctx.createGain();
    o.type = "sine";
    const f = 1800 + Math.random() * 700;
    o.frequency.setValueAtTime(f, t);
    o.frequency.linearRampToValueAtTime(f + 320, t + 0.15);
    g.gain.setValueAtTime(0.0001, t);
    g.gain.linearRampToValueAtTime(0.06, t + 0.05);
    g.gain.exponentialRampToValueAtTime(0.001, t + 0.35);
    o.connect(g);
    g.connect(out);
    o.start(t);
    o.stop(t + 0.4);
  }

  // Tidy up the temp bus shortly after the cheer ends
  setTimeout(() => {
    try {
      out.disconnect();
    } catch {
      // already disconnected
    }
  }, (roarDur + 0.3) * 1000);
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

interface ShowAudioState {
  /** Whether sound is currently enabled (ON). */
  soundOn: boolean;
  /** Toggle sound on/off. Starts or stops the runway groove; persists choice. */
  toggleMusic: () => void;
  /** Play the crowd cheer if sound is ON. Safe to call unconditionally. */
  playCheer: () => void;
  /**
   * Arm audio on the first user gesture: resumes the AudioContext and starts
   * the runway groove if sound is ON. No-op when sound is OFF. Browser
   * autoplay-safe - must be called from within a user-gesture handler.
   */
  arm: () => void;
}

export function useShowAudio(): ShowAudioState {
  const [soundOn, setSoundOn] = useState<boolean>(() => {
    if (typeof window === "undefined") return true;
    try {
      // Default ON - only off if the user explicitly turned it off.
      return localStorage.getItem(STORAGE_KEY) !== "off";
    } catch {
      return true;
    }
  });

  const ctxRef = useRef<AudioContext | null>(null);
  const grooveStopRef = useRef<(() => void) | null>(null);
  const soundOnRef = useRef(soundOn);

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
    if (ctxRef.current.state === "suspended") {
      void ctxRef.current.resume();
    }
    return ctxRef.current;
  }, []);

  /** Start the runway groove loop. Idempotent - won't double-start. */
  const startGroove = useCallback(() => {
    if (grooveStopRef.current) return;
    const ctx = getCtx();
    if (!ctx) return;
    const { stop } = createRunwayGroove(ctx);
    grooveStopRef.current = stop;
  }, [getCtx]);

  /** Stop the runway groove. Idempotent. */
  const stopGroove = useCallback(() => {
    if (!grooveStopRef.current) return;
    grooveStopRef.current();
    grooveStopRef.current = null;
  }, []);

  const toggleMusic = useCallback(() => {
    setSoundOn((prev) => {
      const next = !prev;
      soundOnRef.current = next;
      try {
        localStorage.setItem(STORAGE_KEY, next ? "on" : "off");
      } catch {
        // localStorage unavailable - ignore
      }
      if (next) {
        startGroove();
      } else {
        stopGroove();
      }
      return next;
    });
  }, [startGroove, stopGroove]);

  const playCheer = useCallback(() => {
    if (!soundOnRef.current) return;
    const ctx = getCtx();
    if (!ctx) return;
    playCrowdCheer(ctx);
  }, [getCtx]);

  const arm = useCallback(() => {
    if (!soundOnRef.current) return;
    getCtx(); // creates + resumes the AudioContext (needs a user gesture)
    startGroove(); // idempotent
  }, [getCtx, startGroove]);

  // Clean up on unmount
  useEffect(() => {
    return () => {
      stopGroove();
      if (ctxRef.current && ctxRef.current.state !== "closed") {
        void ctxRef.current.close();
        ctxRef.current = null;
      }
    };
  }, [stopGroove]);

  return { soundOn, toggleMusic, playCheer, arm };
}
