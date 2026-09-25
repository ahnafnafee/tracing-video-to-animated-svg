"""Build a clean, super-resolved reference of a moving subject from a video.

Extracts every frame, estimates the static background plate (per-pixel median over time), tracks
the subject by template matching, fits its motion, warps every usable frame into the subject's rest
pose at an upscaled resolution, and median-stacks them. The stack cancels compression noise and
recovers detail no single frame has. Writes, in --out:

  frames/f0001.png ...  every decoded frame (the other scripts reuse them)
  plate.png             the background with the subject removed (full source frame)
  motion.json           window, scale, per-frame offsets and scores, and the fitted motion
  ref.png               median of the aligned frames: the tracing reference
  matte.png             share of frames in which each pixel differs from the plate (subject coverage)
  spread.png            per-pixel spread across the stack: bright = parts that move on the body
  bg.png                the plate cut to the window at the same scale (backdrop for render_compare.py)

Output coordinates are SVG units: source pixels times --scale, origin at the window's top-left in
the reference frame. Use them directly as the SVG's user space (viewBox 0 0 W*scale H*scale).

usage:
  python stack_reference.py VIDEO --out WORK --template X0,Y0,X1,Y1 --ref-frame N
         [--window X,Y,W,H] [--frames A:B] [--scale 4] [--threshold 16] [--min-score .6]

--template  a rigid, well-textured part of the subject in the reference frame (source pixels);
            avoid limbs, wheels, propellers and cloth, which move on the body.
--window    the region to reconstruct around the subject in the reference frame; defaults to the
            bounding box of everything that differs from the plate in that frame.
"""
import argparse
import json
import subprocess
import warnings
from pathlib import Path

import cv2
import numpy as np

MAX_PLATE_FRAMES = 48
MAX_STACK_FRAMES = 96
STRIP_ROWS = 48


def frame_path(work, i):
    return Path(work) / 'frames' / f'f{i:04d}.png'


def frame_count(work):
    return len(list((Path(work) / 'frames').glob('f*.png')))


def load_motion(work):
    return json.loads((Path(work) / 'motion.json').read_text())


def offset(motion, i):
    """Subject offset of frame i relative to the reference frame, in source pixels."""
    if motion['fit'] and not motion['per_frame']:
        a, b, c, d = motion['fit']
        return a * i + b, c * i + d
    dx, dy, _ = motion['offsets'][str(i)]
    return dx, dy


def warp(img, dx, dy, motion, box=None, interp=cv2.INTER_LANCZOS4, border=cv2.BORDER_REPLICATE):
    """Warp a source frame into SVG units, optionally only the SVG-unit box (x0, y0, x1, y1)."""
    wx, wy, ww, wh = motion['window']
    s = motion['scale']
    x0, y0, x1, y1 = box or (0, 0, ww * s, wh * s)
    m = np.float32([[s, 0, -(wx + dx) * s - x0], [0, s, -(wy + dy) * s - y0]])
    return cv2.warpAffine(img, m, (int(x1 - x0), int(y1 - y0)), flags=interp, borderMode=border)


def warp_valid(shape, dx, dy, motion, box):
    """Mask of warped pixels that came from inside the source frame (the subject was in shot)."""
    inside = np.ones(shape[:2], np.uint8)
    return warp(inside, dx, dy, motion, box, cv2.INTER_NEAREST, cv2.BORDER_CONSTANT) > 0


def aligned_frame(work, i, box=None):
    """Frame i of the video warped into the subject's rest pose, in SVG units."""
    motion = load_motion(work)
    return warp(cv2.imread(str(frame_path(work, i))), *offset(motion, i), motion, box)


def extract(video, work):
    out = Path(work) / 'frames'
    if out.exists() and any(out.iterdir()):
        return
    out.mkdir(parents=True, exist_ok=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-i', str(video), str(out / 'f%04d.png')], check=True)


def median_by_strips(images, rows=120):
    h = images[0].shape[0]
    out = np.empty_like(images[0])
    for y in range(0, h, rows):
        out[y:y + rows] = np.median(np.stack([im[y:y + rows] for im in images]), axis=0)
    return out


def track(work, frames, template, ref_frame, min_score):
    ref = cv2.imread(str(frame_path(work, ref_frame)))
    x0, y0, x1, y1 = template
    tpl = ref[y0:y1, x0:x1]
    offsets = {}
    for i in frames:
        img = cv2.imread(str(frame_path(work, i)))
        res = cv2.matchTemplate(img, tpl, cv2.TM_CCOEFF_NORMED)
        _, score, _, (x, y) = cv2.minMaxLoc(res)
        sx, sy = float(x), float(y)
        # Parabolic subpixel refinement around the correlation peak.
        if 0 < x < res.shape[1] - 1:
            l, c, r = res[y, x - 1], res[y, x], res[y, x + 1]
            den = l - 2 * c + r
            sx += 0.5 * (l - r) / den if den else 0
        if 0 < y < res.shape[0] - 1:
            t, c, bt = res[y - 1, x], res[y, x], res[y + 1, x]
            den = t - 2 * c + bt
            sy += 0.5 * (t - bt) / den if den else 0
        offsets[i] = (float(sx - x0), float(sy - y0), float(score))
    good = [i for i in frames if offsets[i][2] >= min_score]
    return offsets, good


def fit_motion(offsets, good):
    """Straight-line fit of the offsets over frames, refit once without outliers.

    Frames where the subject is partly out of shot or occluded track poorly; they are dropped when
    their residual exceeds three times the median residual (and at least one pixel).
    """
    use = list(good)
    for _ in range(2):
        n = np.array(use, float)
        a_mat = np.stack([n, np.ones_like(n)], 1)
        fx, *_ = np.linalg.lstsq(a_mat, np.array([offsets[i][0] for i in use]), rcond=None)
        fy, *_ = np.linalg.lstsq(a_mat, np.array([offsets[i][1] for i in use]), rcond=None)
        res = {i: max(abs(offsets[i][0] - (fx[0] * i + fx[1])), abs(offsets[i][1] - (fy[0] * i + fy[1]))) for i in good}
        limit = max(1.0, 3 * float(np.median([res[i] for i in use])))
        use = [i for i in good if res[i] <= limit]
    rms = float(np.sqrt(np.mean([res[i] ** 2 for i in use])))
    return [float(fx[0]), float(fx[1]), float(fy[0]), float(fy[1])], rms, float(max(res[i] for i in use)), use


def auto_window(ref, plate, threshold, pad=12):
    d = np.abs(ref.astype(np.int16) - plate.astype(np.int16)).max(axis=2) > threshold * 2
    d = cv2.morphologyEx(d.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, _, stats, _ = cv2.connectedComponentsWithStats(d)
    keep = [k for k in range(1, n) if stats[k, cv2.CC_STAT_AREA] >= 40]
    if not keep:
        raise SystemExit('No subject found in the reference frame; pass --window.')
    x0 = min(stats[k, 0] for k in keep) - pad
    y0 = min(stats[k, 1] for k in keep) - pad
    x1 = max(stats[k, 0] + stats[k, 2] for k in keep) + pad
    y1 = max(stats[k, 1] + stats[k, 3] for k in keep) + pad
    h, w = ref.shape[:2]
    x0, y0 = max(0, x0), max(0, y0)
    return [int(x0), int(y0), int(min(w, x1) - x0), int(min(h, y1) - y0)]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('video')
    ap.add_argument('--out', required=True)
    ap.add_argument('--template', required=True, help='X0,Y0,X1,Y1 in source pixels of the reference frame')
    ap.add_argument('--ref-frame', type=int, required=True)
    ap.add_argument('--window', help='X,Y,W,H in source pixels of the reference frame')
    ap.add_argument('--frames', help='A:B inclusive frame range to track and stack (default: all)')
    ap.add_argument('--scale', type=int, default=4)
    ap.add_argument('--threshold', type=int, default=16, help='per-channel difference that counts as subject')
    ap.add_argument('--min-score', type=float, default=.6, help='template correlation needed to use a frame')
    ap.add_argument('--per-frame', action='store_true', help='use measured offsets even if a line fits')
    a = ap.parse_args()

    work = Path(a.out)
    extract(a.video, work)
    total = frame_count(work)
    first, last = (map(int, a.frames.split(':')) if a.frames else (1, total))
    frames = list(range(first, last + 1))

    step = -(-total // MAX_PLATE_FRAMES)
    plate = median_by_strips([cv2.imread(str(frame_path(work, i))) for i in range(1, total + 1, step)])
    cv2.imwrite(str(work / 'plate.png'), plate)

    template = [int(v) for v in a.template.split(',')]
    offsets, good = track(work, frames, template, a.ref_frame, a.min_score)
    if len(good) < 3:
        raise SystemExit(f'Only {len(good)} frames matched the template; lower --min-score or pick another template.')
    fit, rms, max_residual, inliers = fit_motion(offsets, good)
    # Limbs inside the template add about a pixel of jitter to each measurement; only a clearly
    # non-linear path (acceleration, a curve) is worth following frame by frame.
    per_frame = bool(a.per_frame or rms > 1.0)
    if not per_frame:
        good = inliers
    print(f'tracked {len(good)}/{len(frames)} frames; linear fit dx={fit[0]:.4f}*i{fit[1]:+.2f}, '
          f'dy={fit[2]:.4f}*i{fit[3]:+.2f}; residual rms {rms:.2f}px, max {max_residual:.2f}px'
          + ('; using per-frame offsets' if per_frame else ''))

    ref = cv2.imread(str(frame_path(work, a.ref_frame)))
    window = [int(v) for v in a.window.split(',')] if a.window else auto_window(ref, plate, a.threshold)
    motion = {'video': str(a.video), 'ref_frame': a.ref_frame, 'template': template, 'window': window,
              'scale': a.scale, 'fit': fit, 'rms_residual': rms, 'max_residual': max_residual, 'per_frame': per_frame,
              'good_frames': good, 'offsets': {str(i): list(offsets[i]) for i in frames}}
    (work / 'motion.json').write_text(json.dumps(motion, indent=1))
    print(f'window {window} -> SVG viewBox 0 0 {window[2] * a.scale} {window[3] * a.scale}')

    use = good[::-(-len(good) // MAX_STACK_FRAMES)]
    imgs = [cv2.imread(str(frame_path(work, i))) for i in use]
    offs = [offset(motion, i) for i in use]
    w_out, h_out = window[2] * a.scale, window[3] * a.scale
    ref_img = np.empty((h_out, w_out, 3), np.uint8)
    matte = np.empty((h_out, w_out), np.uint8)
    spread = np.empty((h_out, w_out), np.uint8)
    for y in range(0, h_out, STRIP_ROWS):
        box = (0, y, w_out, min(h_out, y + STRIP_ROWS))
        stack = np.stack([warp(im, dx, dy, motion, box) for im, (dx, dy) in zip(imgs, offs)]).astype(np.float32)
        backs = np.stack([warp(plate, dx, dy, motion, box, cv2.INTER_LINEAR) for dx, dy in offs]).astype(np.float32)
        # Pixels from frames where this part of the subject was out of shot are left out of every statistic.
        valid = np.stack([warp_valid(plate.shape, dx, dy, motion, box) for dx, dy in offs])
        stack[~valid] = np.nan
        with warnings.catch_warnings():
            # Pixels no frame covered produce all-NaN slices; they come out as 0 (black).
            warnings.simplefilter('ignore', RuntimeWarning)
            ref_img[box[1]:box[3]] = np.clip(np.nan_to_num(np.nanmedian(stack, axis=0)), 0, 255).astype(np.uint8)
            differs = np.where(valid, np.abs(stack - backs).max(axis=3) > a.threshold, np.nan)
            coverage = np.nan_to_num(np.nanmean(differs, axis=0))
            matte[box[1]:box[3]] = (coverage * 255).astype(np.uint8)
            # The background behind a moving subject changes from frame to frame, so its spread is
            # noise; only pixels the subject covers at least now and then are kept.
            moving = np.nan_to_num(np.nanstd(stack, axis=0)).mean(axis=2) * 4 * (coverage >= .1)
            spread[box[1]:box[3]] = np.clip(moving, 0, 255).astype(np.uint8)
    cv2.imwrite(str(work / 'ref.png'), ref_img)
    cv2.imwrite(str(work / 'matte.png'), matte)
    cv2.imwrite(str(work / 'spread.png'), cv2.applyColorMap(spread, cv2.COLORMAP_INFERNO))
    wx, wy, ww, wh = window
    bg = cv2.resize(plate[wy:wy + wh, wx:wx + ww], (w_out, h_out), interpolation=cv2.INTER_CUBIC)
    cv2.imwrite(str(work / 'bg.png'), bg)
    print(f'stacked {len(use)} frames into ref.png ({w_out}x{h_out})')


if __name__ == '__main__':
    main()
