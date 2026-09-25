# tracing-video-to-animated-svg

An agent skill for recreating a moving subject from a video, GIF, or frame sequence as a
resolution-independent animated SVG that matches the footage. It covers vehicles, riders,
characters, and towed banners, and cyclic motion such as pedaling legs, wheels, propellers, and
cloth.

The method is to measure rather than draw:
1. Stack the motion-compensated frames into one clean 4x reference image.
2. Read every coordinate, color, and cycle off it with the bundled tools.
3. Generate the SVG from a script.
4. Judge the result animated, at display size, inside the real page.

## Install

With the [`skills` CLI](https://github.com/vercel-labs/skills), which installs into
`~/.agents/skills` and links the skill for the agents you choose:

```sh
npx skills add ahnafnafee/tracing-video-to-animated-svg
```

The repository is private, so the CLI needs git credentials for it. Running `gh auth setup-git`
once is enough.

To install by hand, copy `skills/tracing-video-to-animated-svg/` into an agent's skills directory:
- `~/.claude/skills/` for Claude Code.
- `~/.agents/skills/` for Codex, Copilot CLI, Gemini CLI, and the other agents that read that
  shared root.

## Requirements

- Python 3 with `opencv-python`, `numpy`, and `scipy`.
- `playwright`, with Chrome or its bundled Chromium, for rendering and frame-time checks.
- `ffmpeg` for frame extraction.

## Contents

All paths are under `skills/tracing-video-to-animated-svg/`.

| Path | What it is |
|---|---|
| `SKILL.md` | The method, the pipeline with a command for each step, the decisions that matter, and common mistakes |
| `references/measuring-and-tracing.md` | Building the reference, then reading coordinates, colors, materials, silhouettes, lettering, and cycles |
| `references/drawing-rigging-shipping.md` | Shading recipes, painter's order and clothing, limb rigs, cloth, verification, and inlining in a page |
| `scripts/stack_reference.py` | Motion-compensated median stack of the video at 4x, with a matte, a spread map, and the background |
| `scripts/zoom.py` | Gridded crops in SVG units for reading coordinates |
| `scripts/measure.py` | Circle fits, color samples, material maps, traced outlines and lettering, and cycle periods |
| `scripts/two_bone_rig.py` | Pedaling-leg rig: fits measured knee extremes, writes CSS keyframes, overlays skeletons on frames |
| `scripts/render_compare.py` | Frozen renders over the background beside the reference or a video frame, also at display size |
| `scripts/perf_probe.py` | Frame-interval probe for SVG variants, as `<img>` and inline |
| `scripts/namespace_svg.py` | Prefixes ids, classes, and keyframes so the art can be inlined safely |

Each script documents itself; run it with `--help`.

## Updating

The authored copy is the live skill folder in `~/.claude/skills/`. To publish a change, mirror that
folder over `skills/tracing-video-to-animated-svg/` in a clone of this repository, then commit.
