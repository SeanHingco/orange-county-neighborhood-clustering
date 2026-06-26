# Recovering Neighborhood Boundaries from Public Data

*A technique writeup, demonstrated on Pittsburgh, PA.*

## The problem

Ask someone where they live and they'll say a neighborhood name, not a census tract or a ZIP code. "Bloomfield." "The Northside." "Shadyside." These names carry real information — about housing stock, walkability, who lives there, what it's like to be there — but in most US cities they have no official boundary file. Census geography is drawn for statistical sampling, not lived experience. ZIP codes are drawn for mail routing. Neither one respects the line a Pittsburgh native could draw on a map without thinking about it.

For any product that wants to reason about *places* — not just listings, not just addresses, but the actual neighborhoods people search for — this is a real gap. You can't join other data (walkability, amenities, demographics) to a boundary that doesn't exist.

This writeup walks through one way to recover those boundaries algorithmically, using only public data, and where that approach broke and had to be fixed.

## First attempt, and why it didn't work

The obvious first move is unsupervised clustering: pull a feature vector per spatial unit (income, density, housing age, walkability, whatever's available) and run a standard clustering algorithm — k-means, or density-based methods like HDBSCAN — to find groups.

This doesn't work, for a structural reason rather than a tuning reason: **standard clustering algorithms have no concept of geography.** They group points that are close together in *feature space*, with no constraint that the result be a contiguous region on a map. Two pockets of similar income and density on opposite sides of a city will happily get merged into one "cluster" even though no human would ever call them the same neighborhood. The output isn't gerrymandered, exactly — it's worse, because it isn't even guaranteed to be one connected shape at all.

Density-based methods like HDBSCAN have an additional failure mode here: with default parameters, sparse or transitional areas (an industrial corridor, a stretch with thin data coverage) get labeled as noise rather than assigned anywhere, leaving holes in the map.

What's needed is a method that respects two kinds of distance at once — similarity in *signal* (the demographic/built-environment feature vector) and proximity in *space* (is this geographically next to that) — and treats the second one as a hard constraint, not just another feature to weight.

## The actual approach

### Spatial unit: H3 hexagons, not raw points or census polygons

Working with raw points (parcel centroids, address points) makes "is A next to B" expensive and irregular. Working directly with census block group polygons makes it geometrically awkward — they're irregularly shaped and unevenly sized by design (drawn for roughly equal population, not equal area).

[H3](https://h3geo.org) (Uber's hexagonal hierarchical spatial index) solves this cleanly: it tiles the world into hexagons at a chosen resolution, and "is this hex adjacent to that hex" is a simple, uniform lookup regardless of where on the map you are. Public signal data (Census ACS, OSM amenity counts) gets joined onto hexes by spatial overlap, and from that point on, every downstream step — adjacency, connectivity, clustering — operates on a uniform grid instead of irregular polygons.

### Clustering: Ward agglomerative, constrained to spatial adjacency

The fix for the "no concept of geography" problem is to make geography load-bearing rather than advisory. `scikit-learn`'s `AgglomerativeClustering` accepts a `connectivity` matrix — a graph of which points are allowed to merge directly. By building that graph from H3 adjacency (a hex can only merge with its physical neighbors, not with a similar-looking hex across town), Ward clustering is structurally prevented from producing a non-contiguous group. Geographic contiguity stops being something to check for after the fact and becomes something the algorithm cannot violate.

This single change — adjacency as a hard constraint, not a soft feature — is the difference between clustering output that needs to be manually checked for sanity and clustering output that's geographically valid by construction.

### The barrier problem: physical dividers outrank signal similarity

Adjacency-constrained clustering solves contiguity, but introduces a new problem: rivers, highways, and rail corridors are real psychological and practical boundaries between neighborhoods, even when the signal data on both sides looks nearly identical. Two hexes facing each other across a six-lane freeway can have the same income, same housing age, same density — and still belong to two different neighborhoods, because nobody who lives there thinks of "across the freeway" as the same place.

The fix has two parts. First, adjacency edges that cross a known physical barrier (sourced from OSM's tagged freeway/highway/rail geometry) are cut from the connectivity graph entirely, so the algorithm can't merge directly across them. Second — because a barrier can run *through* a hex, not just along a hex boundary — a signed-distance feature is added to the signal vector itself: for each hex, compute which side of the nearest barrier line it falls on, using a perpendicular-projection check, and inject that as an extra coordinate. Even where two adjacent hexes have identical demographic profiles, this gives Ward clustering a real, numeric reason to split them.

### Picking the number of clusters, and the tradeoff that creates

Agglomerative clustering needs a target cluster count, and there's no single right answer — it's set by a genuine tradeoff. Too few clusters and you get **low coherence**: a handful of distinct, well-known neighborhoods get fused into one oversized district. Too many clusters and you get **low purity**: a single large, internally-varied neighborhood gets needlessly chopped into fragments along noisy internal signal gradients that don't correspond to any boundary a resident would recognize.

These two failure modes don't move together — in practice, pushing the cluster count up to fix coherence (stop merging distinct neighborhoods) tends to *hurt* purity (start fragmenting large-but-real neighborhoods), and vice versa. There's no k that's "correct" in both directions at once; it's a real tradeoff to navigate, not a knob to tune until both numbers look good.

This is measured directly, against a published ground-truth boundary set where one exists: for each known neighborhood, **purity** is what fraction of its area landed in a single predicted district (low purity = the neighborhood got fragmented), and **coherence** is the inverse — what fraction of a predicted district's area belongs to a single known neighborhood (low coherence = the district swallowed multiple real neighborhoods). The demo notebook in this repo computes both on Pittsburgh's published neighborhood boundaries.

### Cleaning up the shapes: two repair passes

Even with adjacency constraints and barrier-awareness, raw clustering output has two recurring geometric defects:

**Dumbbell shapes** — two reasonably-sized blobs connected by a thin one-hex-wide neck, usually an artifact of the connectivity graph finding a technically-valid but visually wrong merge path. These are detected and fixed using graph theory, not signal data: representing each district as a graph of its hexes, `networkx.articulation_points` finds hexes whose removal would disconnect the district, and a minimum cut at that point splits the dumbbell into two separate, sensibly-shaped districts.

**Jagged hex-tooth edges** — every raw boundary follows the zig-zag edge of individual hexagons, which is geometrically accurate but visually and practically unusable (oversized GeoJSON, ugly map rendering). The naive fix — smoothing each district's boundary independently — creates a subtler problem: two adjacent districts that share an edge will each round that shared edge slightly differently, leaving slivers of gaps or overlaps between them. The actual fix is topological: union every district boundary into one shared line network first, simplify that network exactly once, then re-split it back into per-district polygons. Because the shared edge only exists once during simplification, both neighbors end up with the *same* simplified edge, by construction.

## Honest results

On Pittsburgh's [90 officially-defined city neighborhoods](https://engage.pittsburghpa.gov/neighborhood-snapshots), this approach gets meaningfully closer to the real boundary set than unconstrained clustering — but it does not perfectly recover it, and the purity/coherence tradeoff described above is real and visible in the numbers (see the demo notebook for exact figures on this run).

The clearest remaining failure mode is the same one described above in the abstract: neighborhoods with strong internal signal heterogeneity (a large neighborhood spanning a hillside and a flat commercial strip, for instance) tend to get split along that internal gradient even when residents would call it one place. Conversely, small, named neighborhoods with no strong demographic signature distinct from their neighbors are the ones most likely to get absorbed into a larger adjacent district.

Algorithmic clustering gets you most of the way to a defensible boundary set, fast, from public data with no labeling effort. It does not replace local knowledge entirely — the lowest-purity, lowest-coherence districts are the ones worth a human, structured review pass against, rather than something to keep tuning hyperparameters against indefinitely.

## What's in the demo notebook

`notebooks/01_pittsburgh_demo.ipynb` runs the full pipeline end-to-end on a small sub-region of Pittsburgh (chosen for a mix of strong physical barriers and a couple of well-known, distinctly-named neighborhoods), using only:

- **OpenStreetMap** (via `osmnx`) for street networks, barrier geometry (rivers, freeways), and amenity counts
- **US Census ACS** (5-year estimates, via the Census API) for demographic/economic signal
- **City of Pittsburgh open data** for the published neighborhood boundary file used as ground truth

It walks through: H3 hex generation, signal joining, barrier-aware connectivity graph construction, Ward clustering, purity/coherence validation against the real boundary file, articulation-point repair, and topological boundary smoothing — the same sequence described above, runnable by anyone with no API keys beyond a free Census key.

## Where this came from

This technique was built for the neighborhood-matching layer of a rental discovery product, where the underlying motivation was different from a generic "draw neighborhood boundaries" tool: matching renters to *places*, not just listings, requires having defensible place boundaries to score and explain against in the first place. The production version of this pipeline uses a larger proprietary signal set, additional barrier and terrain features, and a manual review/correction layer on top of the algorithmic output — none of which is in this repo, by design (see the main README's [Scope](../README.md#scope--whats-not-here) section). This repo exists to demonstrate the underlying spatial-clustering technique on its own, independent of any specific product.
