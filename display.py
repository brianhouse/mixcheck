"""Text report and plots. Nothing here measures anything."""

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

import constants as k

RAMP = LinearSegmentedColormap.from_list(
    "deviation", [k.RAMP_NEUTRAL, k.RAMP_MID, k.RAMP_FULL])


def _rule(title):
    return f"\n{title}\n{'-' * len(title)}"


def _fmt(value, spec="+6.1f", nan="  n/a"):
    return nan if value is None or not np.isfinite(value) else format(value, spec)


# ---------------------------------------------------------------- text

def report(res, tilt, ylim=k.PLOT_YLIM):
    """Assemble the whole text report as a string."""
    out = [f"mixcheck  -  {res['path']}",
           f"{res['duration_s']:.1f} s   {res['sr']} Hz   "
           f"{res['n_channels']} ch   target tilt {tilt:+.1f} dB/oct"]

    loud = res["loudness"]
    out.append(_rule("LOUDNESS"))
    out.append(f"  integrated      {_fmt(loud['integrated_lufs'], '+6.1f')} LUFS")
    out.append(f"  loudness range  {_fmt(loud['lra_lu'], '6.1f')} LU")
    for i, peak in enumerate(res["true_peak"]):
        out.append(f"  true peak ch{i + 1}    {_fmt(peak, '+6.2f')} dBTP")
    if np.isfinite(loud["lra_lu"]) and loud["lra_lu"] < 3.0:
        out.append("  note: loudness range under 3 LU - the track is heavily "
                   "levelled, so anything added has to come out of something else")

    out.append(_rule("LEVELS AND FAULTS"))
    for i, ch in enumerate(res["faults"]["channels"]):
        out.append(f"  ch{i + 1}  peak {ch['peak_db']:+6.2f}  "
                   f"rms {ch['rms_db']:+6.2f}  crest {ch['crest_db']:5.2f} dB  "
                   f"dc {ch['dc_offset']:+.1e}  hot {ch['hot_samples']}")
    delta = res["faults"]["lr_rms_delta_db"]
    if delta is not None:
        out.append(f"  L/R rms difference {delta:+.2f} dB")
        if abs(delta) > 0.5:
            out.append("  note: consistent channel imbalance, not a moment")
    worst = max((c["longest_hot_run"] for c in res["faults"]["channels"]),
                default=0)
    if worst > 2:
        out.append(f"  note: {worst} consecutive samples at full scale - "
                   "that's clipping, not just a hot peak")

    out.append(_rule("SPECTRUM vs TARGET  (+ is excess, - is a deficit)"))
    out.append(f"  fitted tilt {res['fitted_tilt']:+.2f} dB/oct "
               f"against a {tilt:+.1f} target")
    out.append("")
    for fc, dev in zip(res["centres"], res["deviation"]):
        if not np.isfinite(dev) or fc < 25:
            continue
        span = int(min(abs(dev), 20) * 1.6)
        bar = ("-" * span).rjust(32) if dev < 0 else "|" + "+" * span
        mark = "  <<" if abs(dev) >= k.DEVIATION_NOTE_DB else ""
        out.append(f"  {fc:8.0f} Hz {dev:+6.1f}  {bar}{mark}")

    over = clipped_bands(res["centres"], res["deviation"], ylim)
    if over:
        out.append("")
        out.append(f"  outside the fixed plot frame ({ylim[0]:+.0f} to "
                   f"{ylim[1]:+.0f} dB) - shown clipped on the graph:")
        for fq, value in over:
            out.append(f"      {fq:8.0f} Hz {value:+6.1f}")

    out.append(_rule("STEREO"))
    wid = res["width"]
    out.append(f"  correlation {wid['correlation']:+.3f}   "
               f"side/mid {wid['side_over_mid_db']:+.1f} dB")
    out.append(f"  {'band':>14}  {'corr':>7}  {'mono sum':>9}")
    for row in res["stereo"]:
        flag = ""
        if row["mono_delta_db"] < -k.MONO_LOSS_NOTE_DB:
            flag = "  << cancels in mono"
        elif row["hi"] <= 250 and row["correlation"] < k.CORRELATION_NOTE:
            flag = "  << low end not mono"
        out.append(f"  {row['lo']:6d}-{row['hi']:<7d}  "
                   f"{row['correlation']:+7.3f}  "
                   f"{row['mono_delta_db']:+8.2f} dB{flag}")

    out.append(_rule("SECTION CHANGES"))
    if not res["sections"]:
        out.append("  none found")
    for sec in res["sections"]:
        mins, secs = divmod(int(sec["time_s"]), 60)
        out.append(f"  at {mins}:{secs:02d}  "
                   f"(mid band rises {sec['probe_rise_db']:+.1f} dB)")
        for name, change in sec["bands"].items():
            flag = "  <<" if abs(change) >= k.SECTION_CHANGE_DB else ""
            out.append(f"      {name:<8}{change:+6.1f} dB{flag}")

    tr = res["transients"]
    out.append(_rule("TRANSIENTS"))
    out.append(f"  {tr['count']} detected  ({tr['per_second']:.2f}/s)")
    out.append(f"  {'band':>14}  {'jump':>7}  {'level below full band':>22}")
    for row in tr["bands"]:
        out.append(f"  {row['lo']:6d}-{row['hi']:<7d}  "
                   f"{_fmt(row['jump_db'], '+6.1f')}  "
                   f"{_fmt(row['share_db'], '+21.1f')}")

    return "\n".join(out)


# ---------------------------------------------------------------- plots

def clipped_bands(centres, dev, ylim=k.PLOT_YLIM):
    """Bands falling outside the fixed plot frame, so they can be reported."""
    good = np.isfinite(dev) & (centres >= k.PLOT_XLIM[0])
    lo, hi = ylim
    out = [(float(f), float(d)) for f, d in zip(centres[good], dev[good])
           if d < lo or d > hi]
    return out


def plot_deviation(centres, dev, tilt, path, title=None, ylim=k.PLOT_YLIM):
    """The main plot: mix minus target.

    Deficit reads as a trough, excess as a peak, and red intensity tracks
    distance from the target in either direction. Direction is carried by
    position, so colour is a pure magnitude encoding.
    """
    good = np.isfinite(dev) & (centres >= 25)
    fc, dv = centres[good], dev[good]

    fig, ax = plt.subplots(figsize=(12, 4.6))
    ax.set_facecolor("#fbfaf8")

    # Fill each segment with a colour taken from |deviation|.
    fine_f = np.geomspace(fc[0], fc[-1], 600)
    fine_d = np.interp(np.log(fine_f), np.log(fc), dv)
    for i in range(len(fine_f) - 1):
        level = min(abs(fine_d[i:i + 2]).mean() / k.RAMP_CAP_DB, 1.0)
        ax.fill_between(fine_f[i:i + 2], 0, fine_d[i:i + 2],
                        color=RAMP(level), linewidth=0)

    ax.semilogx(fine_f, fine_d, color=k.INK, lw=2.0, solid_capstyle="round")
    ax.axhline(0, color=k.ZERO_LINE, ls=(0, (1, 2)), lw=1.6)

    # Below the working floor a band can be near-empty, which makes the ratio
    # to target large and meaningless. Mark it rather than scoring it.
    ax.axvspan(25, k.SCORE_LO_HZ, color="#efece7", zorder=0)
    ax.text(np.sqrt(25 * k.SCORE_LO_HZ), 0.975, "below\nworking floor",
            transform=ax.get_xaxis_transform(), va="top", ha="center",
            color=k.INK_MUTED, fontsize=7.5, linespacing=1.4)

    # Fixed frame - see constants. Never autoscale: it breaks visual A/B.
    ax.set_xlim(*k.PLOT_XLIM)
    ax.set_ylim(*ylim)
    over = clipped_bands(centres, dev, ylim)
    if over:
        ax.text(0.995, 0.965,
                f"{len(over)} band(s) clipped at the frame edge - see report",
                transform=ax.transAxes, ha="right", va="top",
                color=k.RAMP_FULL, fontsize=8.5)
    ax.set_xticks(k.PLOT_TICKS)
    ax.set_xticklabels(k.PLOT_TICK_LABELS)
    ax.minorticks_off()
    ax.grid(axis="y", color=k.GRID, lw=0.7)
    ax.grid(axis="x", color=k.GRID, lw=0.7)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(k.GRID)
    ax.tick_params(colors=k.INK_MUTED)
    ax.set_ylabel("dB from target", color=k.INK_MUTED)
    ax.set_title(title or f"Energy relative to a {tilt:+.1f} dB/oct target",
                 color=k.INK, loc="left")
    ax.text(0.995, 0.03, "below the line = missing energy",
            transform=ax.transAxes, ha="right", va="bottom",
            color=k.INK_MUTED, fontsize=9)

    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def plot_timeline(times, curves, broadband, sections, path):
    fig, ax = plt.subplots(2, 1, figsize=(12.5, 7), sharex=True,
                           gridspec_kw={"height_ratios": [3, 1]})
    smooth = max(1, int(1.5 / (times[1] - times[0]))) if len(times) > 1 else 1
    kernel = np.ones(smooth) / smooth

    for name, curve in curves.items():
        ax[0].plot(times, np.convolve(curve, kernel, mode="same"),
                   lw=1.3, label=name)
    for sec in sections:
        for axis in ax:
            axis.axvline(sec["time_s"], color=k.INK_MUTED, ls="--", lw=1)
    ax[0].legend(ncol=6, fontsize=8, frameon=False)
    ax[0].set_ylabel("band RMS (dBFS)", color=k.INK_MUTED)
    ax[0].set_ylim(*k.TIMELINE_BAND_YLIM)
    ax[0].set_title("Per-band level over the arrangement", color=k.INK, loc="left")

    ax[1].plot(times, np.convolve(broadband, kernel, mode="same"),
               color=k.INK, lw=1.3)
    ax[1].set_ylabel("broadband", color=k.INK_MUTED)
    ax[1].set_ylim(*k.TIMELINE_BROADBAND_YLIM)
    ax[1].set_xlabel("time (s)", color=k.INK_MUTED)

    for axis in ax:
        axis.set_facecolor("#fbfaf8")
        axis.grid(color=k.GRID, lw=0.7)
        for side in ("top", "right"):
            axis.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            axis.spines[side].set_color(k.GRID)
        axis.tick_params(colors=k.INK_MUTED)

    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
