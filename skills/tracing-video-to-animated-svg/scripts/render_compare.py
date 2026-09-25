"""Render an SVG over the background plate in headless Chrome and compare it with the video.

Writes OUT_render.png and OUT_compare.png: the render, the reference, and a 50% blend stacked (wide
crops) or side by side (tall crops). Misplaced edges show as ghosted doubles in the blend.

  --at T        freeze every CSS animation at T seconds, so a pose can be matched to a video frame
  --frame N     compare with aligned video frame N instead of the median reference (poses, blur)
  --display W   also judge at the width the page actually shows the art (both sides resized to W);
                realism problems (hard outlines, cartoon highlights, seams) show up here first

usage:
  python render_compare.py WORK ART.svg [--at 1.2] [--frame 95] [--crop X0,Y0,X1,Y1]
                           [--display 1280] [--out compare]

Needs Playwright (pip install playwright). Set CHROME to a Chrome executable, or run
`playwright install chromium` to use the bundled browser.
"""
import argparse
import base64
import os
import re
from pathlib import Path

import cv2
import numpy as np
from playwright.sync_api import sync_playwright

from stack_reference import aligned_frame

DEFAULT_CHROME = r'C:\Program Files\Google\Chrome\Application\chrome.exe'


def launch(p):
    exe = os.environ.get('CHROME') or (DEFAULT_CHROME if Path(DEFAULT_CHROME).exists() else None)
    return p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()


def svg_size(svg):
    vb = re.search(r'viewBox="\s*[-\d.]+\s+[-\d.]+\s+([\d.]+)\s+([\d.]+)"', svg)
    return int(float(vb.group(1))), int(float(vb.group(2)))


def render(svg, background, width=None, at=None):
    """Screenshot the SVG as an <img> over the background image, at the viewBox size or `width`."""
    if at is not None:
        # Important declarations beat every animation shorthand, whatever its specificity.
        svg = svg.replace('</svg>', f'<style>*{{animation-delay:-{at}s!important;'
                                    f'animation-play-state:paused!important}}</style></svg>')
    w, h = svg_size(svg)
    if width:
        w, h = width, round(h * width / w)
    art = base64.b64encode(svg.encode('utf-8')).decode()
    bg = base64.b64encode(Path(background).read_bytes()).decode()
    html = (f'<body style="margin:0;background:url(data:image/png;base64,{bg}) 0 0/100% 100%">'
            f'<img id="i" src="data:image/svg+xml;base64,{art}" width="{w}" height="{h}" style="display:block"></body>')
    with sync_playwright() as p:
        b = launch(p)
        pg = b.new_page(viewport={'width': w, 'height': h})
        pg.set_content(html)
        pg.wait_for_function("document.getElementById('i').complete")
        pg.wait_for_timeout(300)
        png = pg.screenshot()
        b.close()
    return cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)


def sheet(img, ref):
    blend = cv2.addWeighted(img, .5, ref, .5, 0)
    tall = img.shape[0] > img.shape[1] / 1.6
    return np.hstack([img, ref, blend]) if tall else np.vstack([img, ref, blend])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('work'); ap.add_argument('svg')
    ap.add_argument('--at', type=float); ap.add_argument('--frame', type=int)
    ap.add_argument('--crop', help='X0,Y0,X1,Y1 in SVG units'); ap.add_argument('--display', type=int)
    ap.add_argument('--out', default='compare')
    a = ap.parse_args()
    svg = Path(a.svg).read_text(encoding='utf-8')
    work = Path(a.work)
    img = render(svg, work / 'bg.png', at=a.at)
    full_ref = aligned_frame(work, a.frame) if a.frame else cv2.imread(str(work / 'ref.png'))
    if full_ref.shape[:2] != img.shape[:2]:
        print(f'warning: the SVG viewBox ({img.shape[1]}x{img.shape[0]}) is not the reference size '
              f'({full_ref.shape[1]}x{full_ref.shape[0]}); coordinates will not line up')
        full_ref = cv2.resize(full_ref, (img.shape[1], img.shape[0]))
    cv2.imwrite(f'{a.out}_render.png', img)
    view, ref = img, full_ref
    if a.crop:
        x0, y0, x1, y1 = map(int, a.crop.split(','))
        view, ref = img[y0:y1, x0:x1], full_ref[y0:y1, x0:x1]
    cv2.imwrite(f'{a.out}_compare.png', sheet(view, ref))
    if a.display:
        small = render(svg, work / 'bg.png', width=a.display, at=a.at)
        ref_small = cv2.resize(full_ref, (small.shape[1], small.shape[0]), interpolation=cv2.INTER_AREA)
        cv2.imwrite(f'{a.out}_display.png', np.vstack([small, ref_small]))
    print(f'wrote {a.out}_render.png, {a.out}_compare.png' + (f', {a.out}_display.png' if a.display else ''))


if __name__ == '__main__':
    main()
