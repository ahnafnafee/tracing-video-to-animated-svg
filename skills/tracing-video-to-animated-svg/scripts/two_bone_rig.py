"""Two-bone leg rig for crank-driven motion (pedaling, treadles), in SVG units.

The hip is fixed, the foot rides a crank, and the ankle comes from a foot model: the ankle and the
pedal spindle are fixed points in the shoe's sole frame, and the sole's pitch varies with the crank
angle (nearly flat over the top of the stroke, toe down through the back). The knee is solved with
the law of cosines on the side the rider faces.

Crank angle phi is 0 at the top of the stroke and grows in the pedaling direction.

usage:
  python two_bone_rig.py RIG.json solve --phase 90
  python two_bone_rig.py RIG.json fit --knee-y MIN,MAX --knee-x MAX [--hip-x A:B:S] [--hip-y A:B:S]
                                      [--thigh A:B:S] [--shin A:B:S]
  python two_bone_rig.py RIG.json keyframes --name leg-near --phase 0 [--steps 36]
  python two_bone_rig.py RIG.json overlay WORK --frames 52,64,76,88 --out rig_check.png

RIG.json (all lengths and points in SVG units):
  {"crank_center": [3040, 666], "crank": 70, "hip": [3005, 400], "thigh": 190, "shin": 218,
   "ankle_in_sole": [24, -34], "pedal_in_sole": [80, 6],
   "sole_pitch": {"base": 12, "swing": 43, "flattest_at": 20},
   "facing": 1, "period_s": 3.6, "period_frames": 118, "top_frame": 65}
  facing: 1 when the rider faces +x (right), -1 when facing left.
  period_frames and top_frame (a video frame where the near pedal is at the top) map frames to phases.
"""
import argparse
import itertools
import json
import math

import cv2
import numpy as np


def load(path):
    return json.loads(open(path, encoding='utf-8').read())


def pedal(rig, phi):
    a = math.radians(phi)
    cx, cy = rig['crank_center']
    return cx + rig['facing'] * rig['crank'] * math.sin(a), cy - rig['crank'] * math.cos(a)


def sole_pitch(rig, phi):
    p = rig['sole_pitch']
    return p['base'] + p['swing'] * (1 - math.cos(math.radians(phi - p['flattest_at']))) / 2


def solve(rig, phi, hip=None, thigh=None, shin=None):
    """Joint positions and absolute segment angles (degrees, SVG orientation) at crank angle phi."""
    hip = hip or rig['hip']
    thigh = thigh or rig['thigh']
    shin = shin or rig['shin']
    f = rig['facing']
    px, py = pedal(rig, phi)
    s = math.radians(sole_pitch(rig, phi)) * f
    vx = (rig['pedal_in_sole'][0] - rig['ankle_in_sole'][0]) * f
    vy = rig['pedal_in_sole'][1] - rig['ankle_in_sole'][1]
    ax = px - (vx * math.cos(s) - vy * math.sin(s))
    ay = py - (vx * math.sin(s) + vy * math.cos(s))
    hx, hy = hip
    dx, dy = ax - hx, ay - hy
    d = min(math.hypot(dx, dy), thigh + shin - 1e-3)
    along = (thigh ** 2 - shin ** 2 + d * d) / (2 * d)
    up = math.sqrt(max(0.0, thigh ** 2 - along ** 2))
    ux, uy = dx / d, dy / d
    bx, by = hx + along * ux, hy + along * uy
    kx, ky = bx - up * uy, by + up * ux
    if (kx - bx) * f < 0:
        kx, ky = bx + up * uy, by - up * ux
    return {'hip': (hx, hy), 'knee': (kx, ky), 'ankle': (ax, ay), 'pedal': (px, py),
            'thigh': math.degrees(math.atan2(ky - hy, kx - hx)),
            'shin': math.degrees(math.atan2(ay - ky, ax - kx)),
            'sole': math.degrees(s), 'reach': d / (thigh + shin)}


def frame_phase(rig, frame):
    return (360.0 * (frame - rig['top_frame']) / rig['period_frames']) % 360.0


def cmd_solve(rig, a):
    j = solve(rig, a.phase)
    for k in ('hip', 'knee', 'ankle', 'pedal'):
        print(f'{k:6s} {j[k][0]:.1f},{j[k][1]:.1f}')
    print(f'thigh {j["thigh"]:.1f} deg, shin {j["shin"]:.1f} deg, sole {j["sole"]:.1f} deg, reach {j["reach"]:.2f}')


def span(text, default):
    lo, hi, step = map(float, (text or default).split(':'))
    return np.arange(lo, hi + step / 2, step)


def cmd_fit(rig, a):
    """Grid-search hip and bone lengths so the knee's path spans the measured extremes."""
    ky0, ky1 = map(float, a.knee_y.split(','))
    kx1 = float(a.knee_x)
    hx0, hy0 = rig['hip']
    found = []
    for hx, hy, t, s in itertools.product(span(a.hip_x, f'{hx0 - 30}:{hx0 + 30}:5'), span(a.hip_y, f'{hy0 - 30}:{hy0 + 30}:3'),
                                          span(a.thigh, f'{rig["thigh"] - 30}:{rig["thigh"] + 30}:5'),
                                          span(a.shin, f'{rig["shin"] - 40}:{rig["shin"] + 40}:5')):
        joints = [solve(rig, phi, (hx, hy), t, s) for phi in range(0, 360, 15)]
        ys = [j['knee'][1] for j in joints]
        xs = [j['knee'][0] * rig['facing'] for j in joints]
        cost = (min(ys) - ky0) ** 2 + (max(ys) - ky1) ** 2 + (max(xs) - kx1 * rig['facing']) ** 2
        # A leg that locks straight at the bottom of the stroke reads as a mistake.
        if max(j['reach'] for j in joints) > .96:
            cost += 1e4
        found.append((cost, hx, hy, t, s, min(ys), max(ys), max(xs) * rig['facing']))
    for c, hx, hy, t, s, y0, y1, x1 in sorted(found)[:8]:
        print(f'cost {c:8.1f}  hip {hx:.0f},{hy:.0f}  thigh {t:.0f}  shin {s:.0f}  knee y {y0:.0f}..{y1:.0f}  knee x max {x1:.0f}')


def cmd_keyframes(rig, a):
    """CSS for three nested groups (thigh > shin > foot) posed at --phase, turning through one cycle."""
    rest = solve(rig, a.phase)
    th, sh, so = [], [], []
    for i in range(a.steps + 1):
        j = solve(rig, a.phase + 360 * i / a.steps)
        th.append(j['thigh'] - rest['thigh'])
        sh.append(j['shin'] - rest['shin'])
        so.append(j['sole'] - rest['sole'])
    th, sh, so = [np.degrees(np.unwrap(np.radians(v))) for v in (th, sh, so)]
    parts = {'thigh': (th, rest['hip']), 'shin': ([s - t for s, t in zip(sh, th)], rest['knee']),
             'foot': ([o - s for o, s in zip(so, sh)], rest['ankle'])}
    css = []
    for part, (values, (ox, oy)) in parts.items():
        name = f'{a.name}-{part}'
        stops = ''.join(f'{100 * i / a.steps:.3f}%{{transform:rotate({v:.2f}deg)}}' for i, v in enumerate(values))
        css.append(f'.{name}{{transform-box:view-box;transform-origin:{ox:.1f}px {oy:.1f}px;'
                   f'animation:{name} {rig["period_s"]}s linear infinite}}')
        css.append(f'@keyframes {name}{{{stops}}}')
    cx, cy = rig['crank_center']
    css.append(f'.{a.name}-crank{{transform-box:view-box;transform-origin:{cx}px {cy}px;'
               f'animation:{a.name}-crank {rig["period_s"]}s linear infinite}}'
               f'@keyframes {a.name}-crank{{to{{transform:rotate({360 * rig["facing"]}deg)}}}}')
    print('/* rest pose to draw the limb shapes in: */')
    for k in ('hip', 'knee', 'ankle', 'pedal'):
        print(f'/*   {k:6s} {rest[k][0]:.1f},{rest[k][1]:.1f} */')
    print(f'/*   thigh {rest["thigh"]:.1f} deg, shin {rest["shin"]:.1f} deg, sole {rest["sole"]:.1f} deg */')
    print('\n'.join(css))


def cmd_overlay(rig, a):
    from stack_reference import aligned_frame
    frames = [int(v) for v in a.frames.split(',')]
    xs = [rig['hip'][0], rig['crank_center'][0]]
    ys = [rig['hip'][1], rig['crank_center'][1]]
    reach = rig['thigh'] + rig['crank'] + 60
    box = (int(min(xs) - reach), int(min(ys) - 60), int(max(xs) + reach), int(max(ys) + rig['crank'] + 90))
    scale = a.scale
    tiles = []
    for fr in frames:
        t = cv2.resize(aligned_frame(a.work, fr, box), None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        P = lambda p: (int((p[0] - box[0]) * scale), int((p[1] - box[1]) * scale))
        phi = frame_phase(rig, fr)
        for ph, col in ((phi, (0, 255, 0)), (phi + 180, (255, 0, 255))):
            j = solve(rig, ph)
            for p, q in (('hip', 'knee'), ('knee', 'ankle'), ('ankle', 'pedal')):
                cv2.line(t, P(j[p]), P(j[q]), col, 2)
            cv2.line(t, P(rig['crank_center']), P(j['pedal']), (0, 0, 255), 2)
            cv2.circle(t, P(j['knee']), 5, col, -1)
        cv2.putText(t, f'{fr} {phi:.0f}', (5, 22), cv2.FONT_HERSHEY_SIMPLEX, .7, (0, 0, 0), 2)
        tiles.append(t)
    cols = a.columns
    while len(tiles) % cols:
        tiles.append(np.full_like(tiles[0], 255))
    cv2.imwrite(a.out, np.vstack([np.hstack(tiles[i:i + cols]) for i in range(0, len(tiles), cols)]))
    print(f'green = near leg, magenta = far leg, red = cranks; wrote {a.out}')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('rig')
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('solve'); p.add_argument('--phase', type=float, default=0)
    p = sub.add_parser('fit')
    p.add_argument('--knee-y', required=True, help='highest,lowest knee y seen in the video')
    p.add_argument('--knee-x', required=True, help='farthest forward knee x seen in the video')
    for opt in ('--hip-x', '--hip-y', '--thigh', '--shin'):
        p.add_argument(opt, help='search range A:B:STEP')
    p = sub.add_parser('keyframes')
    p.add_argument('--name', required=True); p.add_argument('--phase', type=float, default=0)
    p.add_argument('--steps', type=int, default=36)
    p = sub.add_parser('overlay')
    p.add_argument('work'); p.add_argument('--frames', required=True); p.add_argument('--out', required=True)
    p.add_argument('--scale', type=float, default=1.3); p.add_argument('--columns', type=int, default=5)
    a = ap.parse_args()
    rig = load(a.rig)
    {'solve': cmd_solve, 'fit': cmd_fit, 'keyframes': cmd_keyframes, 'overlay': cmd_overlay}[a.cmd](rig, a)


if __name__ == '__main__':
    main()
