"""Measure and trace the stacked reference. All coordinates are SVG units (see stack_reference.py).

subcommands:
  circle  WORK --center X,Y --r R              least-squares circle through dark pixels near radius R
                                               (wheels, tires, hubs); prints center, radii, radial profile
  colors  WORK name=X,Y [name=X,Y ...]         5x5-averaged hex color at each named point
  classes WORK OUT.png                         paints each material's pixels in a flat color (sanity map)
  trace   WORK --material M --box X0,Y0,X1,Y1  outline of the largest blob of material M in the box as a
                                               smoothed, simplified closed path (points JSON + SVG path d)
  glyphs  WORK --box X0,Y0,X1,Y1 --channel C --split V
                                               lettering outlines with counters, thresholding one color
                                               channel between the ink and cloth values
  track   WORK --material M --box ... --frames A:B
                                               centroid of material M per aligned frame (a pedal, a piston);
                                               warns when the track jumps between parts
  period  WORK --box ... --frames A:B          cycle length of the motion in the box from self-similarity;
                                               works where tracking fails (crossing legs, merging parts)

Materials are HSV ranges (OpenCV: H 0-180, S and V 0-255) given as name=hmin,hmax,smin,smax,vmin,vmax;
hmin > hmax wraps through red. Override or add with --material-def name=... (repeatable). Only pixels
the matte marks as subject count (--matte-min, 0-255).
"""
import argparse
import json
import math
from pathlib import Path

import cv2
import numpy as np
from scipy.ndimage import gaussian_filter1d

from stack_reference import aligned_frame

MATERIALS = {
    'blue': (100, 125, 150, 255, 60, 255),
    'black': (0, 180, 0, 255, 0, 70),
    'white': (0, 180, 0, 40, 140, 255),
    'skin': (0, 22, 60, 255, 50, 255),
    'yellow': (18, 35, 120, 255, 120, 255),
    'red': (170, 8, 150, 255, 60, 255),
}


def material_mask(img, spec, matte=None, matte_min=110):
    h0, h1, s0, s1, v0, v1 = spec
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(np.int16)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    hue = (h >= h0) & (h <= h1) if h0 <= h1 else (h >= h0) | (h <= h1)
    m = hue & (s >= s0) & (s <= s1) & (v >= v0) & (v <= v1)
    if matte is not None:
        m &= matte >= matte_min
    return m.astype(np.uint8) * 255


def smooth_closed(pts, sigma, step):
    """Gaussian-smooth a closed polyline (wrapping at the ends) and resample it every `step` units."""
    k = int(sigma * 3) + 1
    ext = np.concatenate([pts[-k:], pts, pts[:k]])
    sm = np.stack([gaussian_filter1d(ext[:, 0], sigma), gaussian_filter1d(ext[:, 1], sigma)], 1)[k:-k]
    closed = np.vstack([sm, sm[:1]])
    cum = np.concatenate([[0], np.cumsum(np.hypot(*np.diff(closed, axis=0).T))])
    t = np.linspace(0, cum[-1], max(8, int(cum[-1] / step)), endpoint=False)
    return np.stack([np.interp(t, cum, closed[:, 0]), np.interp(t, cum, closed[:, 1])], 1)


def catmull_rom(points, tension=.9):
    """Closed cubic Bezier path through the points. Tension .5 is classic Catmull-Rom; higher values
    swing wider through each point, which suits sparse points on round silhouettes."""
    p = np.asarray(points, float)
    n = len(p)
    d = [f'M{p[0][0]:.1f} {p[0][1]:.1f}']
    for i in range(n):
        p0, p1, p2, p3 = p[(i - 1) % n], p[i], p[(i + 1) % n], p[(i + 2) % n]
        c1 = p1 + (p2 - p0) * tension / 3
        c2 = p2 - (p3 - p1) * tension / 3
        d.append(f'C{c1[0]:.1f} {c1[1]:.1f} {c2[0]:.1f} {c2[1]:.1f} {p2[0]:.1f} {p2[1]:.1f}')
    return ''.join(d) + 'Z'


def regularize(poly, tol_deg=7.0):
    """Snap nearly horizontal or vertical edges to exact ones (typeset lettering has straight stems)."""
    p = np.array(poly, float)
    for _ in range(2):
        for i in range(len(p)):
            j = (i + 1) % len(p)
            dx, dy = p[j] - p[i]
            ang = abs(math.degrees(math.atan2(dy, dx))) % 180
            if min(ang, 180 - ang) < tol_deg:
                p[i][1] = p[j][1] = (p[i][1] + p[j][1]) / 2
            elif abs(ang - 90) < tol_deg:
                p[i][0] = p[j][0] = (p[i][0] + p[j][0]) / 2
    return p


def box_arg(text):
    return tuple(int(float(v)) for v in text.split(','))


def cmd_circle(a, ref, _matte):
    g = ref.mean(axis=2)
    cx0, cy0 = map(float, a.center.split(','))
    ys, xs = np.nonzero(g < a.dark)
    r0 = np.hypot(xs - cx0, ys - cy0)
    keep = (r0 > a.r * (1 - a.band)) & (r0 < a.r * (1 + a.band))
    x, y = xs[keep].astype(float), ys[keep].astype(float)
    for _ in range(4):
        c = np.linalg.lstsq(np.stack([x, y, np.ones_like(x)], 1), x * x + y * y, rcond=None)[0]
        cx, cy = c[0] / 2, c[1] / 2
        r = math.sqrt(c[2] + cx * cx + cy * cy)
        d = np.hypot(x - cx, y - cy)
        x, y = x[np.abs(d - r) < a.r * .15], y[np.abs(d - r) < a.r * .15]
    d = np.hypot(x - cx, y - cy)
    print(f'center {cx:.1f},{cy:.1f}  r {r:.1f}  inner(2%) {np.percentile(d, 2):.1f}  outer(98%) {np.percentile(d, 98):.1f}')
    th = np.linspace(0, 2 * np.pi, 720, endpoint=False)
    prof = []
    for rr in np.arange(a.r * .6, a.r * 1.25, 2):
        px = np.clip((cx + rr * np.cos(th)).astype(int), 0, g.shape[1] - 1)
        py = np.clip((cy + rr * np.sin(th)).astype(int), 0, g.shape[0] - 1)
        prof.append(f'{rr:.0f}:{np.median(g[py, px]):.0f}')
    print('median brightness by radius:', ' '.join(prof))


def cmd_colors(a, ref, _matte):
    for item in a.points:
        name, xy = item.split('=')
        x, y = map(int, xy.split(','))
        b, g, r = ref[y - 2:y + 3, x - 2:x + 3].reshape(-1, 3).mean(0)
        print(f'{name:24s} ({x},{y}) #{int(r):02x}{int(g):02x}{int(b):02x}')


def cmd_classes(a, ref, matte):
    colors = [(255, 80, 0), (0, 0, 0), (255, 255, 255), (60, 140, 255), (0, 220, 255), (0, 0, 200),
              (200, 0, 200), (0, 160, 0)]
    vis = np.full_like(ref, 128)
    for (name, spec), col in zip(a.materials.items(), colors * 4):
        vis[material_mask(ref, spec, matte, a.matte_min) > 0] = col
    cv2.imwrite(a.out, vis)
    print('painted', ', '.join(f'{n}={c}' for n, c in zip(a.materials, colors * 4)))


def cmd_trace(a, ref, matte):
    m = material_mask(ref, a.materials[a.material], matte, a.matte_min)
    if a.open:
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (a.open, a.open)))
    if a.close:
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (a.close, a.close)))
    x0, y0, x1, y1 = box_arg(a.box)
    sub = np.zeros_like(m)
    sub[y0:y1, x0:x1] = m[y0:y1, x0:x1]
    cs, _ = cv2.findContours(sub, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not cs:
        raise SystemExit('No pixels of that material in the box; check classes and the matte.')
    c = max(cs, key=cv2.contourArea)[:, 0, :].astype(float)
    pts = smooth_closed(c, a.sigma, a.step)
    pts = cv2.approxPolyDP(pts.reshape(-1, 1, 2).astype(np.float32), a.eps, True)[:, 0, :]
    d = catmull_rom(pts, a.tension)
    if a.out:
        Path(a.out).write_text(json.dumps(np.round(pts, 1).tolist()))
    over = ref.copy()
    cv2.polylines(over, [pts.astype(np.int32)], True, (0, 255, 255), 1)
    cv2.imwrite(a.overlay or 'trace_overlay.png', over[max(0, y0 - 20):y1 + 20, max(0, x0 - 20):x1 + 20])
    print(f'{len(pts)} points, bbox {pts.min(0).round()} {pts.max(0).round()}')
    print(d)


def cmd_glyphs(a, ref, _matte):
    x0, y0, x1, y1 = box_arg(a.box)
    ch = {'b': 0, 'g': 1, 'r': 2}[a.channel]
    up = cv2.resize(ref[y0:y1, x0:x1, ch].astype(np.float32), None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    ink = (up > a.split) if a.ink_brighter else (up < a.split)
    cs, hier = cv2.findContours(ink.astype(np.uint8) * 255, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    polys = []
    for i, c in enumerate(cs):
        if cv2.contourArea(c) < a.min_area:
            continue
        ap_ = cv2.approxPolyDP(c, a.eps, True)[:, 0, :] / 2.0 + [x0, y0]
        polys.append({'pts': np.round(regularize(ap_), 2).tolist(), 'hole': bool(hier[0][i][3] >= 0)})
    if a.out:
        Path(a.out).write_text(json.dumps(polys))
    d = ''.join('M' + ' '.join(f'{x:.1f} {y:.1f}' for x, y in p['pts']) + 'Z' for p in polys)
    print(f'{len(polys)} outlines ({sum(p["hole"] for p in polys)} counters); draw with fill-rule="evenodd":')
    print(d)


def cmd_track(a, _ref, _matte):
    x0, y0, x1, y1 = box_arg(a.box)
    first, last = map(int, a.frames.split(':'))
    rows = []
    previous = None
    for i in range(first, last + 1):
        crop = aligned_frame(a.work, i, (x0, y0, x1, y1))
        m = material_mask(crop, a.materials[a.material])
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        n, _, st, cen = cv2.connectedComponentsWithStats(m)
        blobs = [j for j in range(1, n) if st[j, cv2.CC_STAT_AREA] >= a.min_area]
        if not blobs:
            print(f'{i} -')
            continue
        # Follow the blob nearest to the last position so the track stays on one part (the near foot,
        # not whichever white shape is largest in this frame).
        if previous is None:
            j = max(blobs, key=lambda k: st[k, cv2.CC_STAT_AREA])
        else:
            j = min(blobs, key=lambda k: np.hypot(cen[k][0] + x0 - previous[0], cen[k][1] + y0 - previous[1]))
        previous = (cen[j][0] + x0, cen[j][1] + y0)
        rows.append((i, *previous, int(st[j, cv2.CC_STAT_AREA])))
        print(f'{i} {previous[0]:.0f} {previous[1]:.0f} area {rows[-1][3]}')
    jumps = sum(1 for p, q in zip(rows, rows[1:]) if math.hypot(q[1] - p[1], q[2] - p[2]) > a.jump)
    if jumps:
        print(f'{jumps} jumps over {a.jump} units: the track switched parts (crossing limbs merge and split '
              f'blobs). Tighten the box, change the material, or use the period subcommand instead.')


def cmd_period(a, _ref, _matte):
    """Cycle length from self-similarity: the lag at which the whole region looks like itself again.

    Robust where blob tracking fails (limbs that cross, parts that merge). Two-legged pedaling also
    dips at half the cycle, when the legs have swapped places; the far leg's shading keeps that dip
    shallower than the full-cycle one, so check both candidates against the frames.
    """
    x0, y0, x1, y1 = box_arg(a.box)
    first, last = map(int, a.frames.split(':'))
    feats = []
    for i in range(first, last + 1):
        crop = aligned_frame(a.work, i, (x0, y0, x1, y1))
        feats.append(cv2.resize(crop, None, fx=.25, fy=.25, interpolation=cv2.INTER_AREA).astype(np.float32).ravel())
    f = np.stack(feats)
    lags = np.arange(2, len(f) - a.min_overlap)
    dist = np.array([np.mean((f[:-k] - f[k:]) ** 2) for k in lags])
    # Nearby frames always look alike, so candidates start after the first peak of the distance curve.
    peak = int(np.argmax(dist[:len(dist) // 2 + 1]))
    minima = [i for i in range(peak + 1, len(dist) - 1) if dist[i] <= dist[i - 1] and dist[i] <= dist[i + 1]]
    for i in sorted(minima, key=lambda j: dist[j])[:3]:
        print(f'period candidate {lags[i]} frames (distance {dist[i] / dist[peak]:.2f} of peak, '
              f'{len(f) - lags[i]} frame pairs compared)')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--material-def', action='append', default=[], help='name=hmin,hmax,smin,smax,vmin,vmax')
    ap.add_argument('--matte-min', type=int, default=110)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('circle')
    p.add_argument('work'); p.add_argument('--center', required=True); p.add_argument('--r', type=float, required=True)
    p.add_argument('--band', type=float, default=.35); p.add_argument('--dark', type=int, default=70)
    p = sub.add_parser('colors')
    p.add_argument('work'); p.add_argument('points', nargs='+')
    p = sub.add_parser('classes')
    p.add_argument('work'); p.add_argument('out')
    p = sub.add_parser('trace')
    p.add_argument('work'); p.add_argument('--material', required=True); p.add_argument('--box', required=True)
    p.add_argument('--open', type=int, default=0, help='kernel size that removes thin parts (struts, spokes)')
    p.add_argument('--close', type=int, default=0, help='kernel size that fills small gaps')
    p.add_argument('--sigma', type=float, default=2.5); p.add_argument('--step', type=float, default=5)
    p.add_argument('--eps', type=float, default=1.2); p.add_argument('--tension', type=float, default=.9)
    p.add_argument('--out'); p.add_argument('--overlay')
    p = sub.add_parser('glyphs')
    p.add_argument('work'); p.add_argument('--box', required=True); p.add_argument('--channel', default='g')
    p.add_argument('--split', type=float, required=True, help='channel value halfway between ink and cloth')
    p.add_argument('--ink-brighter', action='store_true'); p.add_argument('--eps', type=float, default=4)
    p.add_argument('--min-area', type=float, default=400); p.add_argument('--out')
    p = sub.add_parser('track')
    p.add_argument('work'); p.add_argument('--material', required=True); p.add_argument('--box', required=True)
    p.add_argument('--frames', required=True); p.add_argument('--min-area', type=int, default=150)
    p.add_argument('--jump', type=float, default=40, help='frame-to-frame move that counts as a track switch')
    p = sub.add_parser('period')
    p.add_argument('work'); p.add_argument('--box', required=True); p.add_argument('--frames', required=True)
    p.add_argument('--min-overlap', type=int, default=12, help='fewest frame pairs a candidate lag must compare')
    a = ap.parse_args()
    a.materials = dict(MATERIALS)
    for item in a.material_def:
        name, spec = item.split('=')
        a.materials[name] = tuple(int(v) for v in spec.split(','))
    ref = cv2.imread(str(Path(a.work) / 'ref.png'))
    matte = cv2.imread(str(Path(a.work) / 'matte.png'), cv2.IMREAD_GRAYSCALE)
    {'circle': cmd_circle, 'colors': cmd_colors, 'classes': cmd_classes, 'trace': cmd_trace,
     'glyphs': cmd_glyphs, 'track': cmd_track, 'period': cmd_period}[a.cmd](a, ref, matte)


if __name__ == '__main__':
    main()
