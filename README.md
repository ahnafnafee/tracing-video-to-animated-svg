<div align="center"><a name="readme-top"></a>

[![][image-banner]][github-link]

# Tracing Video to Animated SVG

Recreate a moving subject from footage as a measured, animated, resolution-independent SVG.

Stack the frames. Measure everything. Generate the art. Judge it in motion.

**English** · [Installation](#-installation) · [Pipeline](#-pipeline) · [Tools](#-tools) · [SKILL.md][skill-link] · [Report Bug][github-issues-link] · [Request Feature][github-issues-link]

<!-- SHIELD GROUP -->

[![][skill-shield]][skill-link]
[![][install-shield]][install-link]
[![][python-shield]][python-link]
[![][agents-shield]][agents-link]<br/>
[![][github-contributors-shield]][github-contributors-link]
[![][github-forks-shield]][github-forks-link]
[![][github-stars-shield]][github-stars-link]
[![][github-issues-shield]][github-issues-link]
[![][github-license-shield]][github-license-link]

**Share This Skill**

[![][share-x-shield]][share-x-link]
[![][share-reddit-shield]][share-reddit-link]
[![][share-linkedin-shield]][share-linkedin-link]
[![][share-telegram-shield]][share-telegram-link]

<sup>Measure, never eyeball.</sup>

</div>

<details>
<summary><kbd>Table of contents</kbd></summary>

#### TOC

- [👋🏻 Getting Started](#-getting-started)
- [✨ Features](#-features)
  - [`1` A clean reference from noisy footage](#1-a-clean-reference-from-noisy-footage)
  - [`2` Numbers you can type straight into the SVG](#2-numbers-you-can-type-straight-into-the-svg)
  - [`3` Rigs fitted to the footage](#3-rigs-fitted-to-the-footage)
  - [`4` Cloth that bends as one sheet](#4-cloth-that-bends-as-one-sheet)
  - [`5` Checked in motion, at display size](#5-checked-in-motion-at-display-size)
  - [`6` Safe to inline in a page](#6-safe-to-inline-in-a-page)
- [📦 Installation](#-installation)
- [🛠 Pipeline](#-pipeline)
- [🧰 Tools](#-tools)
- [⌨️ Local Development](#️-local-development)
- [🤝 Contributing](#-contributing)

####

<br/>

</details>

## 👋🏻 Getting Started

This is an [Agent Skill][agent-skills-spec]: a folder of instructions and tools that a coding agent
loads when a task matches. It does one job: turning footage into an SVG that matches it closely. It
handles vehicles, riders, characters, towed banners, and anything with cyclic motion such as pedaling
legs, wheels, propellers, or cloth.

A drawing made from memory of a video reads as a cartoon, and a raster frame sequence is blurry and
heavy. This skill avoids both. It builds one clean, upscaled reference from the footage, reads every
coordinate, color, and cycle off it with tools, and generates the SVG from a script whose numbers
came from those measurements.

> \[!TIP]
>
> Ask your agent to "recreate the bike in this video as an animated SVG that matches it 1:1" and it
> will load the skill on its own.

<details>
  <summary><kbd>Star History</kbd></summary>
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=ahnafnafee%2Ftracing-video-to-animated-svg&theme=dark&type=Date">
    <img width="100%" src="https://api.star-history.com/svg?repos=ahnafnafee%2Ftracing-video-to-animated-svg&type=Date">
  </picture>
</details>

<div align="right">

[![][back-to-top]](#readme-top)

</div>

## ✨ Features

### `1` A clean reference from noisy footage

`stack_reference.py` tracks a rigid part of the subject, fits its motion, and median-stacks every
frame warped into the subject's rest pose at 4x. Compression noise cancels out, and detail that no
single frame has comes back. Frames where part of the subject was out of shot are masked, so they
can't smear the edges.

- **`ref.png`**: the image to trace.
- **`spread.png`**: lights up exactly the parts that move on the body, so you know what to rig.
- **`matte.png` and `bg.png`**: subject coverage and the clean background behind it.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

### `2` Numbers you can type straight into the SVG

Every output is in SVG units: source pixels times the scale.

- **Gridded crops:** `zoom.py` puts a labeled grid on any region or single frame.
- **Circles:** `measure.py` fits wheels and hubs.
- **Colors:** it samples lit, middle, and shadow tones for each material.
- **Paths:** it traces silhouettes and lettering into smooth curves.
- **Cycles:** it finds cycle lengths by self-similarity, which works where blob tracking fails on
  crossing legs.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

### `3` Rigs fitted to the footage

`two_bone_rig.py` solves a pedaling leg with a foot model built on the shoe's sole. It then:
- fits the hip and bone lengths to the knee's measured extremes;
- writes nested thigh, shin, and foot CSS keyframes;
- overlays its skeleton on real frames, so you can check every phase.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

### `4` Cloth that bends as one sheet

A lettered banner ripples through vertical `<use>` slices. Each slice shears along a traveling wave,
so the whole print bends as one sheet. The skill includes the fix for seams between slices: overlap
them and isolate each one as its own layer. It also records the measured cost of the alternative:
feathered masks run about 3x slower.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

### `5` Checked in motion, at display size

`render_compare.py` freezes the SVG at any animation time and sets it beside the matching video
frame. It adds a blend in which misplaced parts show as doubled edges, and a copy at the page's real
width, where cartoonish details show up first. `perf_probe.py` measures frame intervals for each
variant.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

### `6` Safe to inline in a page

`namespace_svg.py` prefixes every id, class, and keyframe, so inline art can't collide with the page.
It deliberately doesn't scope class rules under the root id. Copies drawn through `<use>` live in a
shadow tree where `#root .x` never matches, so scoped rules would silently freeze any reused art.

<div align="right">

[![][back-to-top]](#readme-top)

</div>

## 📦 Installation

Install with the [`skills` CLI][skills-cli]. It copies the skill into `~/.agents/skills` and links it
for the agents you pick:

```bash
npx skills add ahnafnafee/tracing-video-to-animated-svg
```

Or copy [`skills/tracing-video-to-animated-svg`](./skills/tracing-video-to-animated-svg) into an
agent's skills directory:

| Agent                                                              | Skills directory             |
| :----------------------------------------------------------------- | :--------------------------- |
| Claude Code                                                        | `~/.claude/skills/`          |
| Codex, Copilot CLI, Gemini CLI, and others that read the shared root | `~/.agents/skills/`          |
| Cursor                                                             | `~/.cursor/skills/`          |
| OpenCode                                                           | `~/.config/opencode/skills/` |

> \[!IMPORTANT]
>
> The tools need:
> - Python 3.9 or newer, with OpenCV, NumPy, and SciPy.
> - Playwright, with Chrome or its bundled Chromium.
> - ffmpeg.

```bash
pip install opencv-python numpy scipy playwright
playwright install chromium
```

<div align="right">

[![][back-to-top]](#readme-top)

</div>

## 🛠 Pipeline

| Step          | Run                                                                    | You get                                                  |
| :------------ | :--------------------------------------------------------------------- | :------------------------------------------------------- |
| `1` Source    | The largest rendition the host lists                                   | The best pixels available                                |
| `2` Reference | `stack_reference.py VIDEO --out WORK --template X0,Y0,X1,Y1 --ref-frame N` | `ref.png`, `matte.png`, `spread.png`, `bg.png`           |
| `3` Read      | `zoom.py`, then `measure.py circle`, `colors`, `trace`, `glyphs`, `period` | Coordinates, radii, palette, paths, cycle length        |
| `4` Decompose | Build geometric parts from parameters; trace organic silhouettes         | A parts list                                             |
| `5` Generate  | Your generator script (Python writing SVG)                              | Art you can regenerate at any time                       |
| `6` Animate   | `two_bone_rig.py fit`, `keyframes`, `overlay`, plus CSS keyframes       | Motion matched to the footage                            |
| `7` Compare   | `render_compare.py WORK art.svg --at T --frame N --display 1280`       | Side-by-side and display-size comparison sheets          |
| `8` Ship      | `namespace_svg.py`, `perf_probe.py`, and a check at several screen sizes | Inline-safe art that holds its frame rate               |

The full method, including the decisions that matter and common mistakes, is in
[SKILL.md][skill-link]. The two reference files hold the details:
- [measuring and tracing](./skills/tracing-video-to-animated-svg/references/measuring-and-tracing.md);
- [drawing, rigging, and shipping](./skills/tracing-video-to-animated-svg/references/drawing-rigging-shipping.md).

<div align="right">

[![][back-to-top]](#readme-top)

</div>

## 🧰 Tools

| Script              | What it does                                                                             |
| :------------------ | :--------------------------------------------------------------------------------------- |
| `stack_reference.py` | Motion-compensated median stack at 4x, with a matte, a spread map, and the background   |
| `zoom.py`           | Gridded crops in SVG units for reading coordinates                                       |
| `measure.py`        | Circle fits, color samples, material maps, traced outlines and lettering, cycle periods   |
| `two_bone_rig.py`   | Pedaling-leg rig: fits the footage, writes CSS keyframes, overlays skeletons on frames    |
| `render_compare.py` | Frozen renders beside the reference or a video frame, also at display size               |
| `perf_probe.py`     | Frame-interval probe for SVG variants, as `<img>` and inline                             |
| `namespace_svg.py`  | Prefixes ids, classes, and keyframes so the art can be inlined safely                    |

<div align="right">

[![][back-to-top]](#readme-top)

</div>

## ⌨️ Local Development

```bash
git clone https://github.com/ahnafnafee/tracing-video-to-animated-svg.git
cd tracing-video-to-animated-svg/skills/tracing-video-to-animated-svg
python scripts/stack_reference.py --help
```

Every script documents itself with `--help`. A first pass on any clip:

```bash
python scripts/stack_reference.py clip.mp4 --out work --template X0,Y0,X1,Y1 --ref-frame N
python scripts/measure.py classes work classes.png
python scripts/zoom.py work X0,Y0,X1,Y1 zoom.png --frame N
```

<div align="right">

[![][back-to-top]](#readme-top)

</div>

## 🤝 Contributing

Contributions are welcome. Open an issue describing footage that tripped the method up, or send a
pull request with the fix and before-and-after renders.

[![][pr-welcome-shield]][pr-welcome-link]

<div align="right">

[![][back-to-top]](#readme-top)

</div>

---

<details><summary><h4>📝 License</h4></summary>

[![][github-license-shield]][github-license-link]

</details>

Copyright © 2026 [Ahnaf An Nafee][profile-link]. <br />
This project is [MIT](./LICENSE) licensed.

<!-- LINK GROUP -->

[agent-skills-spec]: https://agentskills.io
[agents-link]: #-installation
[agents-shield]: https://img.shields.io/badge/works%20with-Claude%20Code%20%C2%B7%20Codex%20%C2%B7%20Gemini%20%C2%B7%20Cursor-c4f042?labelColor=black&style=flat-square
[back-to-top]: https://img.shields.io/badge/-BACK_TO_TOP-151515?style=flat-square
[github-contributors-link]: https://github.com/ahnafnafee/tracing-video-to-animated-svg/graphs/contributors
[github-contributors-shield]: https://img.shields.io/github/contributors/ahnafnafee/tracing-video-to-animated-svg?color=c4f042&labelColor=black&style=flat-square
[github-forks-link]: https://github.com/ahnafnafee/tracing-video-to-animated-svg/network/members
[github-forks-shield]: https://img.shields.io/github/forks/ahnafnafee/tracing-video-to-animated-svg?color=8ae8ff&labelColor=black&style=flat-square
[github-issues-link]: https://github.com/ahnafnafee/tracing-video-to-animated-svg/issues
[github-issues-shield]: https://img.shields.io/github/issues/ahnafnafee/tracing-video-to-animated-svg?color=ff80eb&labelColor=black&style=flat-square
[github-license-link]: https://github.com/ahnafnafee/tracing-video-to-animated-svg/blob/main/LICENSE
[github-license-shield]: https://img.shields.io/badge/license-mit-white?labelColor=black&style=flat-square
[github-link]: https://github.com/ahnafnafee/tracing-video-to-animated-svg
[github-stars-link]: https://github.com/ahnafnafee/tracing-video-to-animated-svg/stargazers
[github-stars-shield]: https://img.shields.io/github/stars/ahnafnafee/tracing-video-to-animated-svg?color=ffcb47&labelColor=black&style=flat-square
[image-banner]: ./assets/banner.svg
[install-link]: #-installation
[install-shield]: https://img.shields.io/badge/npx%20skills%20add-ahnafnafee%2Ftracing--video--to--animated--svg-8ae8ff?labelColor=black&style=flat-square
[pr-welcome-link]: https://github.com/ahnafnafee/tracing-video-to-animated-svg/pulls
[pr-welcome-shield]: https://img.shields.io/badge/🤯_pr_welcome-%E2%86%92-ffcb47?labelColor=black&style=for-the-badge
[profile-link]: https://github.com/ahnafnafee
[python-link]: https://www.python.org/
[python-shield]: https://img.shields.io/badge/python-3.9%2B-ffcb47?labelColor=black&logo=python&logoColor=white&style=flat-square
[share-linkedin-link]: https://linkedin.com/feed
[share-linkedin-shield]: https://img.shields.io/badge/-share%20on%20linkedin-black?labelColor=black&logo=linkedin&logoColor=white&style=flat-square
[share-reddit-link]: https://www.reddit.com/submit?title=Check%20this%20GitHub%20repository%20out%20%F0%9F%A4%AF%20tracing-video-to-animated-svg%3A%20an%20agent%20skill%20that%20recreates%20video%20footage%20as%20a%20measured%2C%20animated%20SVG&url=https%3A%2F%2Fgithub.com%2Fahnafnafee%2Ftracing-video-to-animated-svg
[share-reddit-shield]: https://img.shields.io/badge/-share%20on%20reddit-black?labelColor=black&logo=reddit&logoColor=white&style=flat-square
[share-telegram-link]: https://t.me/share/url?text=Check%20this%20GitHub%20repository%20out%20%F0%9F%A4%AF%20tracing-video-to-animated-svg%3A%20an%20agent%20skill%20that%20recreates%20video%20footage%20as%20a%20measured%2C%20animated%20SVG&url=https%3A%2F%2Fgithub.com%2Fahnafnafee%2Ftracing-video-to-animated-svg
[share-telegram-shield]: https://img.shields.io/badge/-share%20on%20telegram-black?labelColor=black&logo=telegram&logoColor=white&style=flat-square
[share-x-link]: https://x.com/intent/tweet?hashtags=svg%2Canimation%2Cagentskills&text=Check%20this%20GitHub%20repository%20out%20%F0%9F%A4%AF%20tracing-video-to-animated-svg%3A%20an%20agent%20skill%20that%20recreates%20video%20footage%20as%20a%20measured%2C%20animated%20SVG&url=https%3A%2F%2Fgithub.com%2Fahnafnafee%2Ftracing-video-to-animated-svg
[share-x-shield]: https://img.shields.io/badge/-share%20on%20x-black?labelColor=black&logo=x&logoColor=white&style=flat-square
[skill-link]: ./skills/tracing-video-to-animated-svg/SKILL.md
[skill-shield]: https://img.shields.io/badge/agent%20skill-SKILL.md-369eff?labelColor=black&style=flat-square
[skills-cli]: https://github.com/vercel-labs/skills
