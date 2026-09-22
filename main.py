#!venv/bin/python
"""mixcheck - measure a mix against a target tilt.

    python3 main.py mix.wav
    python3 main.py mix.wav --tilt -0.8 --out ./reports
"""

import argparse
import os
import sys

import numpy as np

import analysis
import constants as k
import display


def run(path, tilt=k.DEFAULT_TILT, out_dir=None, limit_s=None,
        ylim=k.PLOT_YLIM):
    data, sr = analysis.load(path)
    if limit_s:
        data = data[:int(limit_s * sr)]
    left, right, mid, _ = analysis.channels(data)

    centres, levels = analysis.ltas(mid, sr)
    times, curves, broadband, crest = analysis.timeline(mid, sr)

    res = {
        "path": os.path.basename(path),
        "sr": sr,
        "n_channels": data.shape[1],
        "duration_s": len(data) / sr,
        "loudness": analysis.loudness(data, sr),
        "true_peak": analysis.true_peak(data, sr),
        "faults": analysis.faults(data, sr),
        "centres": centres,
        "levels": levels,
        "deviation": analysis.deviation(centres, levels, tilt),
        "fitted_tilt": analysis.fitted_tilt(centres, levels),
        "width": analysis.width(left, right),
        "stereo": analysis.stereo(left, right, sr),
        "sections": analysis.section_changes(times, curves),
        "transients": analysis.transients(mid, sr),
        "crest": crest,
    }

    text = display.report(res, tilt, ylim)

    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        stem = os.path.splitext(os.path.basename(path))[0]
        display.plot_deviation(centres, res["deviation"], tilt,
                               os.path.join(out_dir, f"{stem}_spectrum.png"),
                               ylim=ylim)
        display.plot_timeline(times, curves, broadband, res["sections"],
                              os.path.join(out_dir, f"{stem}_timeline.png"))
        with open(os.path.join(out_dir, f"{stem}_report.txt"), "w") as handle:
            handle.write(text + "\n")

    return res, text


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Measure a mix against a target spectral tilt.")
    parser.add_argument("wav", help="audio file to analyse")
    parser.add_argument("--tilt", type=float, default=k.DEFAULT_TILT,
                        help=f"target dB per octave (default {k.DEFAULT_TILT})")
    parser.add_argument("--out", default=None,
                        help="directory for plots and the report file")
    parser.add_argument("--limit", type=float, default=None,
                        help="only analyse the first N seconds")
    parser.add_argument("--ylim", type=float, nargs=2, metavar=("LO", "HI"),
                        default=k.PLOT_YLIM,
                        help="spectrum plot range in dB; fixed by default "
                             f"({k.PLOT_YLIM[0]:+.0f} {k.PLOT_YLIM[1]:+.0f}) "
                             "so runs stay visually comparable")
    args = parser.parse_args(argv)

    if not os.path.exists(args.wav):
        parser.error(f"no such file: {args.wav}")

    _, text = run(args.wav, args.tilt, args.out, args.limit,
                  tuple(args.ylim))
    print(text)
    if args.out:
        print(f"\nwrote plots and report to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
