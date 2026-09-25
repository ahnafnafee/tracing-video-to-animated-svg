# Measuring and tracing

Everything here reads the work directory that `scripts/stack_reference.py` writes. Coordinates are
SVG units: source pixels times the scale, from the reconstruction window's top-left.

## Building the reference

**Reference frame.** Pick a frame where the whole subject is in shot, near the middle of the clip.

**Template.** A rigid, well-textured patch of 150 to 250 source pixels: the frame plus the torso,
a cockpit, a chassis. Keep limbs, wheels, propellers, and cloth out of it; they move on the body and
bias the tracking. A correlation score of at least .6 marks a usable frame.

**Window.** The region to reconstruct, including towed or trailing parts. It defaults to the bounding
box of everything that differs from the plate in the reference frame. Pass `--window` when water,
shadows, or other movers inflate it.

**Scale.** Use 4. Source 1080p footage of a subject about 380 px wide becomes about 1520 units.
Higher scales add file size, not information.

**Motion model.** A constant-velocity flyby fits a straight line with about 0.7 px RMS residual; the
tracker's own jitter from limbs inside the template accounts for most of it. The script drops
outliers (frames partly out of shot) and follows per-frame offsets only when the RMS exceeds 1 px,
which means a curved path or acceleration.

**Validity.** Early and late frames cover only part of the window. Their out-of-shot pixels are
masked out of every statistic, so a towed banner stays sharp even though half the stack never saw it.

**Outputs:**

| File | Use |
|---|---|
| `ref.png` | Trace and measure everything static from this; it is sharper than any frame |
| `spread.png` | Bright where parts move on the body; decides what gets rigged, and shows each part's range |
| `matte.png` | Share of frames where a pixel is subject; masks use at least 110 of 255 |
| `bg.png` | The background behind the window, used as the backdrop for comparisons |
| `motion.json` | Offsets and fit; `aligned_frame(work, n)` warps any frame into SVG units on demand |

Check the grade. If the site ships its own background image, fit a per-channel gain and offset
between it and the plate. A ratio near 1.0 means the palette sampled from the video can be used as is.

## Reading coordinates

`zoom.py WORK X0,Y0,X1,Y1 out.png --scale 2.5` draws minor lines every 20 units and labeled major
lines every 100. Read endpoints, joint centers, and outline corners to about 2 units. Use
`--frame N` for a moving part at one instant; the median blurs it.

## Colors

`measure.py colors WORK name=X,Y ...` averages a 5x5 patch. For every material, sample the lit side,
the middle, and the shadow side, then build gradients from those three values. A single flat color
per part is the fastest way to look cartoonish.

## Materials and silhouettes

Default HSV ranges (OpenCV: H 0 to 180) are blue, black, white, skin, yellow, and red. Override them
with `--material-def name=hmin,hmax,smin,smax,vmin,vmax`; when hmin is greater than hmax, the range
wraps through red. Run `measure.py classes WORK map.png` first; if the map mislabels a part, fix the
range before tracing.

`measure.py trace WORK --material blue --box ... --open 19` takes the largest blob of that material in
the box and returns a smoothed, simplified closed path. Parameters:

- `--open K` removes thin parts that cross the shape, such as struts and spokes. K is about 5 source
  pixels times the scale.
- `--close K` fills small gaps.
- `--sigma 2.5 --step 5 --eps 1.2` smooths, resamples, and simplifies. Lower `eps` keeps more corners.
- `--tension .9` makes round shapes read round from few points; .5 is classic Catmull-Rom.

Always open the overlay PNG. Where an occluder crossed the shape (a strut over a cowling, an arm over
the torso), correct the outline in the generator; the trace follows the occluder.

## Lettering

If the face is a known font, match it: render candidates over the reference and compare. Otherwise
trace it:

1. Pick the color channel that separates ink from cloth the most. For red ink on yellow cloth that is
   green (about 0 against 169).
2. Set `--split` halfway between the two values.
3. Run `measure.py glyphs WORK --box ... --channel g --split 84 --eps 4`. It traces at 2x, keeps the
   counters as holes, and snaps nearly straight edges within 7 degrees.
4. Fill the result with `fill-rule="evenodd"`.

Traced paths also survive an `<img>` embed, where the page's web fonts are unavailable.

## Cycles: period and phase

**Period.** `measure.py period WORK --box <region around the moving part> --frames A:B` finds the lag
at which the region looks like itself again. Two-legged pedaling also dips at half the cycle, when the
legs have swapped places. That dip is shallower because the far leg is shaded differently, so confirm
the choice against frames.

**Tracking.** `measure.py track` follows one blob; it warns when crossing parts make it switch. Use
it for isolated parts only.

**Phase.** Find a frame where the reference part is at a known position (the near pedal at the top).
`two_bone_rig.py RIG.json overlay WORK --frames ...` draws the rig on ten phases; adjust `top_frame`
and `period_frames` until every skeleton sits on its limb.

**Animation period.** The animation's period can differ from the footage's (a slightly faster cadence
reads livelier). When comparing, match by phase, not by time.

## What to measure, by part

| Part | Measure | Tool |
|---|---|---|
| Wheel | Hub center; tire outer and inner radius; rim radius; spoke count | `circle`, radial profile, zoom |
| Tube frame | Joint centers and widths | zoom |
| Crank | Center; radius from the extremes of the pedal track | zoom on frames, `track` |
| Leg | Hip; the knee's highest, lowest, and farthest-forward points | zoom on frames, then `two_bone_rig.py fit` |
| Propeller seen edge-on | Hub; blade length (from `spread.png`) | zoom |
| Fairing, body, clothing | Outline | `trace` |
| Cloth banner | Rectangle; sway amplitude at the free end; wavelength | zoom on frames, `spread.png` |
| Every material | Lit, middle, and shadow color | `colors` |
