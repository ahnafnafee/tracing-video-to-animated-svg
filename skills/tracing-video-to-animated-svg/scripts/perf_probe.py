"""Frame-interval probe for animated SVGs, shown both as <img> and inline, at a display width.

Compare variants (clip vs mask, filter on vs off, slice count) side by side. A variant whose median
interval rises above the plain baseline is repainting something expensive on every frame; the
display's refresh interval (about 6.9 ms at 144 Hz, 16.7 ms at 60 Hz) is the floor.

usage:
  python perf_probe.py ART.svg [VARIANT.svg ...] [--width 1280] [--dpr 2] [--frames 240]
"""
import argparse
import base64
from pathlib import Path

from playwright.sync_api import sync_playwright

from render_compare import launch, svg_size

PROBE = """async (n) => {
  const t = []; let last = performance.now();
  await new Promise((done) => { const tick = (now) => { t.push(now - last); last = now; t.length < n ? requestAnimationFrame(tick) : done(); }; requestAnimationFrame(tick); });
  t.sort((a, b) => a - b); const q = (p) => t[Math.min(t.length - 1, Math.floor(t.length * p))].toFixed(1);
  return `median ${q(.5)} ms  p90 ${q(.9)} ms  p99 ${q(.99)} ms`;
}"""


def page(svg, width, inline):
    w, h = svg_size(svg)
    height = round(h * width / w)
    if inline:
        return f'<body style="margin:0">{svg.replace("<svg ", f"<svg width={width} height={height} ", 1)}</body>'
    data = base64.b64encode(svg.encode('utf-8')).decode()
    return f'<body style="margin:0"><img src="data:image/svg+xml;base64,{data}" width="{width}" height="{height}"></body>'


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('svgs', nargs='+')
    ap.add_argument('--width', type=int, default=1280); ap.add_argument('--dpr', type=float, default=2)
    ap.add_argument('--frames', type=int, default=240)
    a = ap.parse_args()
    with sync_playwright() as p:
        b = launch(p)
        for path in a.svgs:
            svg = Path(path).read_text(encoding='utf-8')
            for inline in (False, True):
                pg = b.new_page(viewport={'width': a.width, 'height': 800}, device_scale_factor=a.dpr)
                pg.set_content(page(svg, a.width, inline))
                pg.wait_for_timeout(800)
                print(f'{Path(path).name:28s} {"inline" if inline else "img   "}  {pg.evaluate(PROBE, a.frames)}')
                pg.close()
        b.close()


if __name__ == '__main__':
    main()
