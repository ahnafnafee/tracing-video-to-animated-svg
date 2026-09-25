"""Crop a region of the reference (or of one aligned video frame) with a labeled coordinate grid.

Grid lines are in SVG units, so a coordinate read off the image goes straight into the SVG. Minor
lines every --step units, labeled major lines every five steps.

usage:
  python zoom.py WORK X0,Y0,X1,Y1 OUT.png [--scale 2.5] [--step 20] [--frame N | --image PATH]
"""
import argparse

import cv2

from stack_reference import aligned_frame


def gridded(crop, x0, y0, scale, step):
    """Upscale a crop whose top-left sits at SVG (x0, y0) and draw the SVG-unit grid over it."""
    h, w = crop.shape[:2]
    x1, y1 = x0 + w, y0 + h
    crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    over = crop.copy()
    for g in range((x0 // step + 1) * step, x1, step):
        px = int((g - x0) * scale)
        major = g % (step * 5) == 0
        cv2.line(over, (px, 0), (px, over.shape[0]), (0, 0, 255) if major else (0, 200, 255), 1)
        if major:
            cv2.putText(over, str(g), (px + 2, 12), cv2.FONT_HERSHEY_SIMPLEX, .4, (0, 0, 180), 1)
    for g in range((y0 // step + 1) * step, y1, step):
        py = int((g - y0) * scale)
        major = g % (step * 5) == 0
        cv2.line(over, (0, py), (over.shape[1], py), (0, 0, 255) if major else (0, 200, 255), 1)
        if major:
            cv2.putText(over, str(g), (2, py - 2), cv2.FONT_HERSHEY_SIMPLEX, .4, (0, 0, 180), 1)
    return cv2.addWeighted(crop, .62, over, .38, 0)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('work')
    ap.add_argument('box', help='X0,Y0,X1,Y1 in SVG units')
    ap.add_argument('out')
    ap.add_argument('--scale', type=float, default=2.5)
    ap.add_argument('--step', type=int, default=20)
    src = ap.add_mutually_exclusive_group()
    src.add_argument('--frame', type=int, help='use this video frame, aligned, instead of ref.png')
    src.add_argument('--image', help='use any image already in SVG units (a render, matte.png, ...)')
    a = ap.parse_args()
    x0, y0, x1, y1 = map(int, a.box.split(','))
    if a.frame:
        crop = aligned_frame(a.work, a.frame, (x0, y0, x1, y1))
    else:
        crop = cv2.imread(a.image or f'{a.work}/ref.png')[y0:y1, x0:x1]
    cv2.imwrite(a.out, gridded(crop, x0, y0, a.scale, a.step))


if __name__ == '__main__':
    main()
