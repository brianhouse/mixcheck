"""Measurements. Everything here returns numbers; nothing prints or plots."""

import numpy as np
import soundfile as sf
from scipy import signal

import constants as k

# NumPy 2.0 renamed trapz to trapezoid and removed the old name, so code
# written for either version breaks on the other. Bind once.
_integrate = getattr(np, "trapezoid", None) or np.trapz


# ---------------------------------------------------------------- loading

def load(path):
    """Return (samples [n, ch], sample_rate). Mono files become one column."""
    data, sr = sf.read(path, always_2d=True)
    return data, sr


def channels(data):
    """Return (left, right, mid, side). Mono input is duplicated."""
    if data.shape[1] == 1:
        left = right = data[:, 0]
    else:
        left, right = data[:, 0], data[:, 1]
    return left, right, (left + right) / 2.0, (left - right) / 2.0


def db(value, floor=1e-12):
    return 20.0 * np.log10(np.maximum(np.abs(value), floor))


def rms(x):
    return float(np.sqrt(np.mean(np.square(x))))


# ---------------------------------------------------------------- loudness

def _shelf(sr):
    """BS.1770 stage 1: high-shelf, as an RBJ biquad at this sample rate."""
    amp = 10.0 ** (k.SHELF_GAIN_DB / 40.0)
    w0 = 2.0 * np.pi * k.SHELF_FC / sr
    alpha = np.sin(w0) / (2.0 * k.SHELF_Q)
    cos0 = np.cos(w0)
    two_sqrt_a_alpha = 2.0 * np.sqrt(amp) * alpha

    b = np.array([
        amp * ((amp + 1) + (amp - 1) * cos0 + two_sqrt_a_alpha),
        -2.0 * amp * ((amp - 1) + (amp + 1) * cos0),
        amp * ((amp + 1) + (amp - 1) * cos0 - two_sqrt_a_alpha),
    ])
    a = np.array([
        (amp + 1) - (amp - 1) * cos0 + two_sqrt_a_alpha,
        2.0 * ((amp - 1) - (amp + 1) * cos0),
        (amp + 1) - (amp - 1) * cos0 - two_sqrt_a_alpha,
    ])
    return b / a[0], a / a[0]


def _highpass(sr):
    """BS.1770 stage 2: RLB high-pass."""
    w0 = 2.0 * np.pi * k.HIGHPASS_FC / sr
    alpha = np.sin(w0) / (2.0 * k.HIGHPASS_Q)
    cos0 = np.cos(w0)

    b = np.array([(1 + cos0) / 2.0, -(1 + cos0), (1 + cos0) / 2.0])
    a = np.array([1 + alpha, -2.0 * cos0, 1 - alpha])
    return b / a[0], a / a[0]


def k_weight(x, sr):
    b1, a1 = _shelf(sr)
    b2, a2 = _highpass(sr)
    return signal.lfilter(b2, a2, signal.lfilter(b1, a1, x))


def _block_loudness(data, sr, block_s, hop_s):
    """Per-block loudness in LKFS, and the block start times."""
    weighted = np.column_stack([k_weight(data[:, c], sr)
                                for c in range(data.shape[1])])
    win = int(round(block_s * sr))
    hop = max(1, int(round(hop_s * sr)))
    if len(weighted) < win:
        return np.array([]), np.array([])

    starts = np.arange(0, len(weighted) - win + 1, hop)
    out = np.empty(len(starts))
    for i, s in enumerate(starts):
        chunk = weighted[s:s + win]
        # Stereo channel weights are both 1.0 in BS.1770.
        mean_square = np.mean(np.square(chunk), axis=0).sum()
        out[i] = -0.691 + 10.0 * np.log10(max(mean_square, 1e-20))
    return out, starts / sr


def _gated_mean(levels):
    """Apply the BS.1770 absolute then relative gate, return integrated LUFS."""
    keep = levels[levels > k.ABSOLUTE_GATE_LUFS]
    if keep.size == 0:
        return float("nan")
    power = 10.0 ** ((keep + 0.691) / 10.0)
    threshold = -0.691 + 10.0 * np.log10(power.mean()) + k.RELATIVE_GATE_LU
    keep = keep[keep > threshold]
    if keep.size == 0:
        return float("nan")
    power = 10.0 ** ((keep + 0.691) / 10.0)
    return float(-0.691 + 10.0 * np.log10(power.mean()))


def loudness(data, sr):
    """Integrated LUFS, loudness range, and the short-term curve."""
    hop = k.BLOCK_S * (1.0 - k.BLOCK_OVERLAP)
    blocks, _ = _block_loudness(data, sr, k.BLOCK_S, hop)
    integrated = _gated_mean(blocks)

    short, short_t = _block_loudness(data, sr, k.SHORT_TERM_S, k.SHORT_TERM_HOP_S)
    lra = float("nan")
    if short.size:
        keep = short[short > k.ABSOLUTE_GATE_LUFS]
        if keep.size:
            power = 10.0 ** ((keep + 0.691) / 10.0)
            threshold = (-0.691 + 10.0 * np.log10(power.mean())
                         + k.LRA_RELATIVE_GATE_LU)
            keep = keep[keep > threshold]
            if keep.size:
                lra = float(np.percentile(keep, k.LRA_HIGH_PCT)
                            - np.percentile(keep, k.LRA_LOW_PCT))

    return {
        "integrated_lufs": integrated,
        "lra_lu": lra,
        "short_term": short,
        "short_term_t": short_t,
    }


def true_peak(data, sr):
    """Per-channel true peak in dBTP, via oversampling."""
    peaks = []
    for c in range(data.shape[1]):
        up = signal.resample_poly(data[:, c], k.TRUE_PEAK_OVERSAMPLE, 1)
        peaks.append(float(db(np.max(np.abs(up)))))
    return peaks


# ---------------------------------------------------------------- faults

def faults(data, sr):
    out = {"channels": [], "lr_rms_delta_db": None}
    for c in range(data.shape[1]):
        ch = data[:, c]
        hot = np.abs(ch) >= 10.0 ** (-0.05 / 20.0)
        runs = 0
        if hot.any():
            edges = np.diff(hot.astype(np.int8))
            ups = np.where(edges == 1)[0]
            downs = np.where(edges == -1)[0]
            if ups.size and downs.size:
                downs = downs[downs > ups[0]]
                ups = ups[:len(downs)]
                runs = int(np.max(downs - ups)) if len(downs) else 0
        out["channels"].append({
            "peak_db": float(db(np.max(np.abs(ch)))),
            "rms_db": float(db(rms(ch))),
            "crest_db": float(db(np.max(np.abs(ch))) - db(rms(ch))),
            "dc_offset": float(np.mean(ch)),
            "hot_samples": int(hot.sum()),
            "longest_hot_run": runs,
        })
    if data.shape[1] >= 2:
        out["lr_rms_delta_db"] = float(db(rms(data[:, 0])) - db(rms(data[:, 1])))
    return out


# ---------------------------------------------------------------- spectrum

def third_octave_centres():
    lo, hi = k.THIRD_OCTAVE_EXPONENTS
    return 1000.0 * 2.0 ** (np.arange(lo, hi) / 3.0)


def ltas(x, sr, nperseg=32768):
    """Third-octave band ENERGY, normalised to 1 kHz.

    Band energy (not density) is the right measure against a tilt target:
    pink noise has equal energy per octave, so it reads flat on this axis.
    """
    nperseg = min(nperseg, len(x))
    freqs, power = signal.welch(x, sr, nperseg=nperseg, noverlap=nperseg // 2)
    centres = third_octave_centres()
    levels = np.full(len(centres), np.nan)
    for i, fc in enumerate(centres):
        band = (freqs >= fc / 2 ** (1 / 6)) & (freqs < fc * 2 ** (1 / 6))
        if band.any():
            energy = _integrate(power[band], freqs[band])
            levels[i] = 10.0 * np.log10(max(energy, 1e-20))
    ref = levels[np.nanargmin(np.abs(centres - k.TILT_REF_HZ))]
    return centres, levels - ref


def target_curve(centres, tilt=k.DEFAULT_TILT):
    return tilt * np.log2(centres / k.TILT_REF_HZ)


def deviation(centres, levels, tilt=k.DEFAULT_TILT):
    """Mix minus target. Positive is excess energy, negative is a deficit."""
    return levels - target_curve(centres, tilt)


def fitted_tilt(centres, levels):
    band = ((centres >= k.SCORE_LO_HZ) & (centres <= k.SCORE_HI_HZ)
            & np.isfinite(levels))
    slope, _ = np.polyfit(np.log2(centres[band] / k.TILT_REF_HZ),
                          levels[band], 1)
    return float(slope)


def narrow_features(x, sr, fine=24, broad=2, nperseg=65536):
    """Local peaks and dips relative to the surrounding trend.

    Both measures use mean power DENSITY so the comparison is independent of
    bandwidth - comparing band energies across different widths is wrong and
    produces a spurious tilt.
    """
    nperseg = min(nperseg, len(x))
    freqs, power = signal.welch(x, sr, nperseg=nperseg, noverlap=nperseg // 2)
    centres = 1000.0 * 2.0 ** (np.arange(-136, 105) / 24.0)

    def density(frac):
        out = np.full(len(centres), np.nan)
        for i, fc in enumerate(centres):
            band = (freqs >= fc / 2 ** (1 / (2 * frac))) & \
                   (freqs < fc * 2 ** (1 / (2 * frac)))
            if band.any():
                out[i] = 10.0 * np.log10(max(power[band].mean(), 1e-20))
        return out

    return centres, density(fine) - density(broad)


# ---------------------------------------------------------------- stereo

def _bandpass(x, sr, lo, hi, order=4):
    hi = min(hi, sr / 2.0 - 1.0)
    sos = signal.butter(order, [lo, hi], btype="band", fs=sr, output="sos")
    return signal.sosfilt(sos, x)


def stereo(left, right, sr):
    rows = []
    for lo, hi in k.STEREO_BANDS:
        if lo >= sr / 2.0:
            continue
        lb, rb = _bandpass(left, sr, lo, hi), _bandpass(right, sr, lo, hi)
        stereo_energy = np.sqrt(np.mean(lb ** 2) + np.mean(rb ** 2))
        mono_energy = np.sqrt(2.0 * np.mean(((lb + rb) / 2.0) ** 2))
        rows.append({
            "lo": lo, "hi": hi,
            "correlation": float(np.corrcoef(lb, rb)[0, 1]),
            "mono_delta_db": float(db(mono_energy) - db(stereo_energy)),
        })
    return rows


def width(left, right):
    mid, side = (left + right) / 2.0, (left - right) / 2.0
    return {
        "correlation": float(np.corrcoef(left, right)[0, 1]),
        "mid_db": float(db(rms(mid))),
        "side_db": float(db(rms(side))),
        "side_over_mid_db": float(db(rms(side)) - db(rms(mid))),
    }


# ---------------------------------------------------------------- timeline

def timeline(x, sr, window_s=1.0, hop_s=0.5):
    """Per-band RMS over time, plus the broadband curve and crest factor."""
    win, hop = int(window_s * sr), int(hop_s * sr)
    starts = np.arange(0, max(1, len(x) - win), hop)
    times = starts / sr

    curves = {}
    for name, lo, hi in k.TIMELINE_BANDS:
        if lo >= sr / 2.0:
            continue
        y = _bandpass(x, sr, lo, hi)
        curves[name] = np.array([db(rms(y[s:s + win])) for s in starts])

    broadband = np.array([db(rms(x[s:s + win])) for s in starts])
    crest = np.array([db(np.max(np.abs(x[s:s + win]))) - db(rms(x[s:s + win]))
                      for s in starts])
    return times, curves, broadband, crest


def section_changes(times, curves, probe="mid", compare_s=4.0, top=3):
    """Find the largest sustained rises in `probe` and report every band's step.

    This is what catches an element entering and pushing everything else down.
    """
    if probe not in curves:
        return []
    hop = times[1] - times[0] if len(times) > 1 else 1.0
    span = max(1, int(compare_s / hop))
    probe_curve = curves[probe]

    rise = np.full(len(probe_curve), -np.inf)
    for i in range(span, len(probe_curve) - span):
        rise[i] = (np.median(probe_curve[i:i + span])
                   - np.median(probe_curve[i - span:i]))

    found, used = [], []
    order = np.argsort(rise)[::-1]
    for idx in order:
        if not np.isfinite(rise[idx]) or rise[idx] <= 0:
            break
        if any(abs(idx - u) < span * 2 for u in used):
            continue
        used.append(idx)
        found.append({
            "time_s": float(times[idx]),
            "probe_rise_db": float(rise[idx]),
            "bands": {n: float(np.median(c[idx:idx + span])
                               - np.median(c[idx - span:idx]))
                      for n, c in curves.items()},
        })
        if len(found) >= top:
            break
    return found


# ---------------------------------------------------------------- transients

def transients(x, sr, detect=(2000, 6000), prominence_db=8.0, window_s=0.040):
    """Where do the track's transients put their energy?

    Returns the median per-band change across the onset, which answers
    'would this show up on an analyser, and where'.
    """
    y = _bandpass(x, sr, *detect)
    envelope = np.abs(signal.hilbert(y))
    decim = 20
    env = signal.decimate(envelope, decim, zero_phase=True).clip(1e-9)
    env_sr = sr / decim
    peaks, _ = signal.find_peaks(db(env), prominence=prominence_db,
                                 distance=int(0.2 * env_sr))

    win = int(window_s * sr)
    deltas = {b: [] for b in k.TRANSIENT_BANDS}
    shares = {b: [] for b in k.TRANSIENT_BANDS}

    def band_power(start):
        chunk = x[start:start + win] * np.hanning(win)
        freqs = np.fft.rfftfreq(win, 1.0 / sr)
        power = np.abs(np.fft.rfft(chunk)) ** 2
        return freqs, power

    def integrate(freqs, power, lo, hi):
        band = (freqs >= lo) & (freqs < hi)
        if not band.any():
            return -200.0
        return 10.0 * np.log10(max(_integrate(power[band], freqs[band]), 1e-20))

    for p in peaks:
        at = int(p / env_sr * sr)
        if at - win < 0 or at + win >= len(x):
            continue
        f_before, p_before = band_power(at - win)
        f_at, p_at = band_power(at)
        total = integrate(f_at, p_at, 20, min(20000, sr / 2 - 1))
        for band in k.TRANSIENT_BANDS:
            deltas[band].append(integrate(f_at, p_at, *band)
                                - integrate(f_before, p_before, *band))
            shares[band].append(integrate(f_at, p_at, *band) - total)

    return {
        "count": len(peaks),
        "per_second": len(peaks) / (len(x) / sr) if len(x) else 0.0,
        "bands": [{"lo": b[0], "hi": b[1],
                   "jump_db": float(np.median(deltas[b])) if deltas[b] else float("nan"),
                   "share_db": float(np.median(shares[b])) if shares[b] else float("nan")}
                  for b in k.TRANSIENT_BANDS],
    }
