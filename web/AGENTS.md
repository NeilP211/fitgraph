<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

# Memory: never demo with `next dev` on a 16 GB Mac

Turbopack compiles the homepage route on-demand on first browser load; that
dev-mode compile balloons system memory to ~8 GB in seconds and can hard-freeze
a 16 GB machine. Serve a production build instead: `next build` + `next start`,
or just run `../scripts/demo_up.sh` from the repo (it builds, serves on :3012,
and runs a memory-pressure watchdog). Verified: same page in prod build = ~1 GB,
1.3 s compile, zero swap. Dev mode is only safe on ≥32 GB.
