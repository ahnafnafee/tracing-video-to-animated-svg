# Drawing, rigging, and shipping

## Generator structure

One Python module per subsystem (the body and parts, the figure, the cloth), each appending strings
to shared `defs`, `body`, and `css` lists, plus a build script that assembles, namespaces, and writes
the SVG. Gradient ids come from a counter. Name each measured number where it is used
(`tube(SEAT_CLUSTER, REAR, 11.5)  # seat stay`). The build is deterministic, so a regenerated file
must hash the same until the inputs change.

## Shading recipes

**Tube (frame, strut, fork).** Stroke the centerline with a linear gradient across the tube, oriented
toward the light, then add a thin specular streak.

```python
def tube(p1, p2, w, pal):
    (x1, y1), (x2, y2) = p1, p2
    ux, uy = unit(x2 - x1, y2 - y1)
    nx, ny = -uy, ux
    if ny > 0:                      # normal points up, toward the light
        nx, ny = -nx, -ny
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    g = lin_grad([(0, pal['hi']), (.22, pal['lit']), (.55, pal['mid']), (.85, pal['low']), (1, pal['edge'])],
                 mx + nx * w / 2, my + ny * w / 2, mx - nx * w / 2, my - ny * w / 2)   # userSpaceOnUse
    body.append(f'<path d="M{x1} {y1}L{x2} {y2}" stroke="url(#{g})" stroke-width="{w}" stroke-linecap="round"/>')
    o = w * .24                     # specular streak on the lit side
    body.append(f'<path d="M{x1 + nx*o} {y1 + ny*o}L{x2 + nx*o} {y2 + ny*o}" stroke="{pal["spec"]}" '
                f'stroke-opacity=".55" stroke-width="{max(1.2, w * .13)}" stroke-linecap="round"/>')
```

**Wheel.**
- Tire: a stroked circle with a diagonal gradient, lighter at the upper left.
- Rim: a darker ring with a 1.4-unit highlight ring just inside it.
- Hub: a radial gradient.
- Spokes: one path in a rotating group. 32 spokes with alternating ±16° offsets read as 2-cross lacing.

**Traced fairing or body panel.**
1. A vertical gradient from the lit, middle, and shadow samples.
2. The same path again, with a horizontal alpha gradient for form shadow.
3. Soft clipped overlays for creases and decals.
4. A faint top-edge highlight stroke.

**Garments.** Fill with a gradient across the body, then clip soft shadow masses (radial gradients
with alpha) inside the garment. Drawn fold lines read as cartoon at display size; use at most one or
two at 13% opacity.

**Skin.** Shade across the limb, from the lit front edge to the shadowed back edge. The far limb uses
a darker ramp of the same hue.

**No outlines.** Darken edges inside the shape instead. A black stroke around shapes is the fastest
cartoon tell.

## Painter's order: rider on a bike, facing right

1. Far leg and far crank
2. Wheels
3. Tail and rear body
4. Frame
5. Chain, chainring, and near crank
6. Saddle and handlebar
7. Cowling, engine, and propeller
8. Near leg
9. **Seat of the shorts:** a static piece that covers the hip joint
10. **Shirt:** its hem overlaps the waistband
11. Head
12. Near arm and glove

Give the shirt and the shorts clearly different values, so the waist reads while the thigh swings.
Render at least six phases side by side and look at every joint.

## Limbs

Draw each segment in world coordinates at the rest pose. Build it from a profile of the front and
back half-widths along the bone, closed with a Catmull-Rom curve. Round each end and let neighboring
segments overlap at the joint, so rotation never opens a gap.

```python
THIGH = [(-26, -8, 12), (0, -41, 43), (80, -39, 37), (160, -29, 28), (210, -6, 8)]  # (x along bone, front, back)
```

## Rigging with CSS

Nest the segments so each one rotates about its own joint:

```html
<g class="leg-near-thigh">  <path .../>  <!-- thigh, and the shorts leg over it -->
  <g class="leg-near-shin"> <path .../>  <!-- shin, sock -->
    <g class="leg-near-foot"> <path .../> </g>  <!-- shoe, pedal -->
  </g>
</g>
```

- Each group rotates by a relative angle: the thigh by its change from rest, the shin by
  (shin minus thigh), and the foot by (sole minus shin).
- Unwrap the angles so a cycle never jumps 360 degrees.
- Use 36 steps with `linear` timing.
- `two_bone_rig.py keyframes` writes all of this, including
  `transform-box: view-box; transform-origin: <x>px <y>px`. Without `view-box`, the origin is
  resolved against the element's own box and the joint drifts.

**Foot model.** The ankle and the pedal spindle are fixed points in the shoe's sole frame. The sole
is nearly flat over the top of the stroke and points toward the ground through the back of it. Fit
the hip and bone lengths to the measured knee extremes with `two_bone_rig.py fit`; it rejects a leg
that locks straight (reach above 0.96).

**Other periodic parts:**

| Part | How |
|---|---|
| Crank and chainring | `rotate(360deg)` over one cadence period |
| Chain | Build a path from the outer tangents of the chainring and cog. Animate a dashed stroke's `stroke-dashoffset` by a whole multiple of the dash period per revolution, so the loop has no jump |
| Wheels | Rotate the spoke group; the period is the cadence divided by the gear ratio |
| Propeller seen edge-on | `scaleY` swinging along a cosine over 16 steps, about the hub |
| Body bob | The body and towed parts share one period; the towed part lags about 0.9 rad with a larger amplitude |
| Line between two moving parts | Its own keyframes: translate for one end, plus skewY for the slope set by both ends |

## Cloth with lettering

Put the whole print in `<defs>`. Draw it through N vertical slices (24 across about 1700 units). Each
slice has its own translateY and skewY keyframes, so its left and right edges follow a traveling wave
and neighboring slices stay joined:

```python
def sway(x, t):                       # free end on the left, tow end at X1
    s = (X1 - x) / (X1 - X0)
    a = AMP * max(0.0, s) ** 1.4      # amplitude grows toward the free end
    ph = 2 * pi * ((X1 - x) / WAVELENGTH - t / PERIOD)
    return a * (sin(ph) + 0.22 * sin(2 * ph + 0.7))

for i in range(SLICES):
    xl, xr = left + i * w, left + (i + 1) * w
    frames = [f'translateY({sway(xl, t):.2f}px) skewY({degrees(atan2(sway(xr, t) - sway(xl, t), w)):.2f}deg)'
              for t in (PERIOD * k / STEPS for k in range(STEPS + 1))]
    # rule: transform-box:view-box; transform-origin:{xl}px {mid}px; animation:bw{i} PERIOD linear infinite
    # markup: <g class="bw{i}"><g opacity=".999" clip-path="url(#slice{i})"><use href="#banner-art"/></g></g>
    # the slice clip rect overlaps its neighbors by 1.5 units on each side
```

For a moving highlight, draw a repeating linear gradient (`spreadMethod="repeat"`) inside the art,
clipped to the cloth, and translate it by one wavelength per wave period.

## Verifying

- **Freeze a pose:** append `*{animation-delay:-Ts!important;animation-play-state:paused!important}`.
  `render_compare.py --at T` does this.
- **Read the blend:** doubled edges mean an offset, a colored halo means the palette is off, and a
  soft ghost means the part is moving in the footage (use `--frame`).
- **Review at display size:** use `--display <page width>` and screenshots of the real page. Do this
  before calling any part done.
- **Measure frame time:** with `perf_probe.py`, the baseline is the display's refresh interval.
  Masks, filters, and large blurred shapes inside animated groups are the usual extra cost;
  `clip-path` with an isolated group is cheap.

## Shipping inline

**Inline or `<img>`.** Inline art is needed for scripting, pointer interaction, and the page's web
fonts. An `<img>` isolates CSS and ids. Both run CSS animations.

**Namespacing.** `namespace_svg.py IN OUT --prefix rb- --root-id NAME` prefixes every id, class, and
keyframe name. It deliberately does not scope class rules under the root, because `<use>` copies
live in a shadow tree where ancestor selectors never match. Only class-less rules (`*`, `path`)
get scoped.

**Anchors.** Publish geometry from the generator rather than copying it into page code:
- CSS custom properties on the root, such as `--bike-anchor: 80.21%`.
- `data-*` attributes on groups: the cloth rectangle, pivot, and tow points.

Page code reads them, and scales them by `rect.width / svg.viewBox.baseVal.width`.

**Sizing gotcha.** `SVGSVGElement` has no `offsetWidth`; use `getBoundingClientRect()`.

**Scroll choreography.** Derive the start and the end of the flight from readability:
- **Start:** the whole subject is in view.
- **End:** the lettering is fully readable. When a copy card overlaps the banner's vertical band,
  center the banner in the free sky beside the card. If the banner is too wide for that gap, align it
  just past the card, so the text shows and the trailing flags crop instead.

Check 1916x815 (a short desktop frame), 1440x900, 1280x720, 1024x768, 800x900, 390x844, and 320x568.

**Pointer interaction.**
- Run springs in SVG units.
- Change `playbackRate` on the CSS animations from `svg.getAnimations({subtree: true})`, skipping the
  bob. Animations inside `<use>` shadow trees are not returned, which is fine.
- Stop all of it when `prefers-reduced-motion` matches.

**Reduced motion.** Add a media query that sets `animation: none` on `#root *` and on
`[class^="rb-"], [class*=" rb-"]`. The attribute selectors reach the `<use>` copies.
