---
name: tracing-video-to-animated-svg
description: Use when recreating a moving subject from a video, GIF, or frame sequence as a resolution-independent animated SVG that must match the footage closely (vehicles, riders, characters, towed banners, anything with cyclic motion such as pedaling legs, wheels, propellers, or cloth), especially after a hand-drawn or raster-frame attempt looked cartoonish, blurry, or heavy.
---

# Tracing video into an animated SVG

## Overview

Measure, never eyeball. Build one clean, upscaled reference image of the subject from the footage,
read every coordinate, color, and cycle off it with tools, and generate the SVG from a script whose
numbers came from those measurements. Then judge the result the way visitors see it: animated, at
the page's display size, inside the real layout.

A drawing made from memory of the footage reads as a cartoon, and a raster frame sequence is blurry
and heavy. Both get rejected.

## When to use

- Recreating footage "1:1" as SVG: shapes, proportions, colors, and motion must match.
- The subject moves rigidly across the frame (a pan or a flyby) with parts that move on the body.
- Not for: stylized or new illustration (there is nothing to measure), or a static logo (trace one
  frame instead).

## Pipeline

Tools live in `scripts/`; run each with `python <this skill>/scripts/NAME.py --help`. Needs Python 3
with opencv-python, numpy, scipy, playwright (with Chrome), and ffmpeg. All coordinates are SVG
units: source pixels times the scale (4), measured from the reconstruction window's top-left.

1. **Source.** Get the highest-quality file. Hosted sites often list variants (a Wix page's
   `qualities` array, `srcset`, HLS renditions); take the largest.
2. **Reference.** `stack_reference.py VIDEO --out WORK --template X0,Y0,X1,Y1 --ref-frame N`
   tracks a rigid, textured patch (frame and torso, never limbs or props), fits the motion, and
   median-stacks the motion-compensated frames at 4x. Outputs `ref.png` (trace this), `matte.png`,
   `spread.png` (bright = parts that move on the body), and `bg.png`. The SVG viewBox is the window
   times 4.
3. **Read.** `zoom.py WORK BOX out.png` puts a labeled SVG-unit grid on any region or single frame.
   `measure.py` fits circles (wheels), samples colors, maps materials, traces silhouettes and
   lettering into paths, and finds cycle periods (`period`, which survives crossing limbs; blob
   `track` does not).
4. **Decompose.** Geometric parts are built from parameters (tubes, wheels, spokes, engines,
   propellers, flags). Organic silhouettes are traced (fairings, bodies, clothing, lettering). See
   `references/measuring-and-tracing.md`.
5. **Generate.** Write a generator script (Python emitting SVG). Never hand-edit its output, and keep
   traced data in JSON beside it. Shading, painter's order, and clothing are covered in
   `references/drawing-rigging-shipping.md`.
6. **Rig and animate** with CSS keyframes. `two_bone_rig.py` fits a pedaling leg to the measured
   knee extremes, writes nested thigh, shin, and foot keyframes, and overlays its skeleton on real
   frames.
7. **Compare.** `render_compare.py WORK art.svg --at T --frame N --display 1280` freezes the SVG at
   time T and sets it beside video frame N, plus a copy at display size. Check at least 6 phases of
   every cycle.
8. **Ship.** `namespace_svg.py` makes the art safe to inline. `perf_probe.py` measures frame time
   per variant. Test the page at several viewport sizes, including short ones.

## Decisions that matter

| Decision | Choose | Because |
|---|---|---|
| Animation engine | CSS `@keyframes` with `transform-box: view-box` and `transform-origin` in user units | SMIL is invisible to `getAnimations()`, so page code can't speed up, pause, or sync it; CSS also obeys `prefers-reduced-motion` |
| Clothing on a moving limb | Moving limb first, then a static piece (seat of the shorts) that covers the joint, then the torso garment whose hem overlaps it | Otherwise the joint pivots in plain view and the garments "flow" wrongly; give adjacent garments contrasting values |
| Waving cloth with lettering | Art in `<defs>`, drawn through ~24 vertical `<use>` slices, each with a translateY + skewY keyframe that follows a traveling wave | Path morphing needs identical commands in every keyframe for every glyph; slices bend the whole print for free |
| Slice seams | Overlap slices ~1.5 units and set `opacity=".999"` on each clipped group | Clipping stacked layers leaves hairlines; feathered masks also work but cost about 3x the frame time |
| Inlining | Prefix every id, class, and keyframe name; do not scope class rules under the root id | `<use>` copies live in a shadow tree where `#root .x` never matches, so scoped rules silently stop animating reused art |
| Page geometry | The generator publishes anchors (CSS custom properties, `data-*` on groups); page code reads them | Hard-coded copies drift when the art is regenerated |
| Scroll choreography | Define the start and end states by what must be readable (whole subject in view, banner text clear of overlapping cards); check a viewport matrix | An end state tuned at one size hides the subject behind layout at another |

## Common mistakes

| Mistake | Symptom | Fix |
|---|---|---|
| Tracing a single frame | Wobbly, noisy edges; wrong proportions | Trace the median stack (`ref.png`) |
| Frames partly out of shot in the stack | Smeared edges near the window border | `stack_reference.py` masks pixels from outside the frame; keep that |
| Guessing the cadence | Feet slide on the pedals | `measure.py period`, then confirm with `two_bone_rig.py overlay` |
| Judging only at 4x | Looks fine zoomed, cartoonish on the page | Use `--display` at the real width; soften outlines and highlights |
| Near leg drawn after the torso | Shorts leg covers the shirt hem | Use the clothing order above |
| `offsetWidth` on the inline `<svg>` | `undefined`, so NaN positions | `getBoundingClientRect().width` |
| Masks or filters in a loop | Frame time rises from 7 ms to 20 ms | Compare variants with `perf_probe.py` |
| Scoping CSS under `#root` | A `<use>`-drawn part never animates | Prefix only (see Decisions) |

## Worked example

The PedalTopia hero (a bicycle-plane with a pedaling rider and a towed banner) was built this way.
Its generator, if present, is in `F:\Miscellaneous\GitHub\gve-site\scripts\ride-bike\`:
`gen.py` (parts and shading), `rider.py` (limbs, clothing, rig), `banner.py` (cloth slices), and
`build.py` (assembly, namespacing, anchors). Reference numbers: window 960x230 at 4x (viewBox
3840x920), 73-frame median stack, cadence of about 118 to 120 frames, 36-step keyframes. Two of its
choices depart from the footage on purpose: the restyled banner and a slightly faster 3.6 s cadence.
Re-measure rather than copy its constants.
