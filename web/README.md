# personal-agent-web

A React + Vite web frontend for [personal-agent](../README.md). Talks to the backend's FastAPI server over HTTP. Works as a phone-browser UI too (no native app needed) — install as a home-screen bookmark for an app-like feel.

## Setup

```bash
export PATH="$HOME/.local/node/bin:$PATH"   # if Node was installed without Homebrew, as done here
npm install
cp .env.example .env   # defaults to http://127.0.0.1:8000
```

## Run

1. Start the backend first (from the repo root): `python -m agent.cli serve`
2. Then: `npm run dev` — opens at http://localhost:5173

## Build

```bash
npm run build   # type-checks with tsc, then builds to dist/
```
