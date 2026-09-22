# mixcheck

Measures a mix against a target spectral tilt and reports what's objectively
checkable. It does not listen, and it has no opinion about whether the mix is
good — it tells you what's there.

```
python3 main.py mix.wav
python3 main.py mix.wav --tilt -0.8 --out ./reports
python3 main.py mix.wav --limit 60          # first minute only
```

Needs `numpy`, `scipy`, `soundfile`, `matplotlib`.

## The model

- **The target is a tilt**, in dB per octave, referenced to 1 kHz. Default
  `-1.0`. Everything is measured as **deviation from it**: positive is excess
  energy, negative is a deficit.
- **Third-octave band *energy*, not density.** Pink noise has equal energy per
  octave, so it reads flat on this axis — which is what makes a tilt target
  meaningful. Comparing band *densities* across different bandwidths adds a
  spurious 3 dB/octave and is the easy mistake here.
- **Below the working floor (40 Hz) nothing is scored.** A near-empty band
  produces a huge ratio to target that means nothing. The plot shades it.

## The plot

`*_spectrum.png` shows deviation, not correction. A deficit is a trough, an
excess is a peak, and red intensity tracks distance from target in either
direction. Direction is carried by position relative to the zero line, so
colour is doing one job — magnitude — rather than two.

This is deliberately the inverse of what a corrective EQ would draw. Reading a
correction curve invites you to apply it; reading a deviation curve tells you
what the mix is doing and leaves the decision separate. Not everything missing
should be boosted — if a band is empty, EQ raises noise and leakage, and the
answer is a source.

`*_timeline.png` shows per-band level over the arrangement with detected
section changes marked. This is what catches an element entering and pushing
everything else down.

## What it measures

| Section | What it tells you |
|---|---|
| Loudness | Integrated LUFS, loudness range, true peak. A loudness range under ~3 LU means the track is heavily levelled, so anything added has to come out of something else. |
| Levels and faults | Peak, RMS, crest, DC offset, consecutive full-scale samples, L/R balance. |
| Spectrum vs target | Third-octave deviation, fitted tilt, with bands off by more than 4 dB flagged. |
| Stereo | Correlation and mono-sum change per band. Flags cancellation and a non-mono low end. |
| Section changes | Finds sustained rises in the mid band and reports what every other band did across the same boundary. |
| Transients | Where the track's transients actually put their energy, and how far below the full-band total they sit. Answers "why doesn't this show on an analyser". |

## Verification

The BS.1770-4 loudness implementation is built from the analogue filter
parameters rather than hard-coded 48 kHz coefficients, so it's correct at any
sample rate. Checked against `ffmpeg`'s `ebur128`:

| | mixcheck | ffmpeg |
|---|---|---|
| Integrated | −11.8 LUFS | −11.7 LUFS |
| Loudness range | 1.8 LU | 1.9 LU |
| True peak | −0.09 dBTP | −0.1 dBFS |

## Layout

- `main.py` — CLI
- `analysis.py` — measurement; returns numbers, never prints
- `display.py` — text report and plots; measures nothing
- `constants.py` — bands, thresholds, target defaults, colours

## Known limits

- The section detector probes the mid band (300 Hz–2 kHz), so it finds
  elements entering *there*. A section change that's purely rhythmic or purely
  low-end won't trigger it.
- It can't separate "the compressor pulled this band down" from "the part
  changed at that bar". Bounce with the bus processing bypassed and compare
  the two reports.
- Narrow-feature detection (`analysis.narrow_features`) is implemented but not
  in the report yet — at 1/24 octave it mostly resolves individual harmonic
  partials below about 1 kHz, which isn't useful without further work.
# mixcheck
