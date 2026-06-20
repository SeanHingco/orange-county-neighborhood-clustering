# Spatially-Constrained Neighborhood Delineation

Algorithmic boundary detection for informal, locally-recognized neighborhoods — using hexagonal spatial indexing, adjacency-constrained agglomerative clustering, and topological boundary repair.

**This repo is a technique writeup and a small reproducible demo.** It is *not* the production pipeline — it runs on a single public-data city (Pittsburgh, PA) with no proprietary signals, weights, or outputs. See [Scope & What's Not Here](#scope--whats-not-here) below.

## Why this exists

Most US cities have no authoritative neighborhood boundary file. Census tracts and ZIP codes are administrative conveniences, not the mental map people actually use ("the Northside," "Highland Park," "Eastside Pittsburgh"). For products that reason about *places* rather than just *listings* — discovery tools, local search, relocation/moving products — that gap matters: there's no ground truth to join other data against.

This project asks: can you recover defensible neighborhood-like boundaries algorithmically from public geographic and demographic signals, in a city with no usable boundary file of its own?

The full writeup is in **[docs/WRITEUP.md](docs/WRITEUP.md)** — it covers the approach, the specific problems that came up (informal boundaries don't follow census geography; physical barriers like rivers and highways matter more than raw similarity; naive clustering produces gerrymandered/non-contiguous shapes), and how each was solved.

## What's in this repo

```
notebooks/   01_pittsburgh_demo.ipynb   — end-to-end demo on a small Pittsburgh sub-region
docs/        WRITEUP.md                 — full technical narrative
src/         pipeline/                  — reusable clustering + repair functions, importable
data/        raw/, processed/           — small public-data extracts used by the demo
assets/                                 — figures referenced in the writeup
```

Start with the writeup for the narrative, or the notebook if you want to run the code yourself.

## Quickstart

```bash
git clone <repo-url>
cd neighborhood-clustering
pip install -r requirements.txt
jupyter notebook notebooks/01_pittsburgh_demo.ipynb
```

The notebook pulls only public data (OpenStreetMap via OSMnx, US Census ACS via the Census API, City of Pittsburgh open data) — no API keys required beyond a free Census API key for the ACS pull, and no proprietary or paid data sources.

## Scope & what's not here

This repo demonstrates the *technique*, deliberately separated from any production application of it:

- Runs on Pittsburgh, a city with no relationship to any product I've built — chosen specifically so there's no overlap with real output.
- Uses only free, public data sources.
- Does not include tuned production parameters, the full multi-source signal set used in a real deployment, or any real product's boundary output.
- The clustering and repair code in `src/` is the general-purpose technique; it does not include any product-specific feature engineering.

If you're here from my resume or LinkedIn and want to talk about how this applies to a real, shipped product, I'm happy to talk through it — just not in a public repo.

## Background

Written up while building the neighborhood-matching engine for a full-stack rental discovery product (not affiliated with or representing any employer). More on that in the writeup's closing section.
