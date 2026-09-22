"""Fixed tables and defaults for mixcheck."""

# ---------------------------------------------------------------- target

DEFAULT_TILT = -1.0          # dB per octave, referenced to 1 kHz
TILT_REF_HZ = 1000.0

# Range over which the tilt is fitted and scored. Below this the content is
# usually gone and the ratio stops meaning anything.
SCORE_LO_HZ = 40.0
SCORE_HI_HZ = 16000.0

# ---------------------------------------------------------------- bands

# Third-octave centres, 25 Hz to 16 kHz.
THIRD_OCTAVE_EXPONENTS = (-16, 13)

# Wide bands used for the timeline and the stereo table.
TIMELINE_BANDS = (
    ("sub", 20, 60),
    ("bass", 60, 120),
    ("lowmid", 120, 300),
    ("mid", 300, 2000),
    ("high", 2000, 8000),
    ("air", 8000, 16000),
)

STEREO_BANDS = (
    (20, 60), (60, 120), (120, 250), (250, 500), (500, 1000),
    (1000, 2000), (2000, 4000), (4000, 8000), (8000, 16000),
)

TRANSIENT_BANDS = (
    (60, 200), (200, 600), (600, 1200),
    (1200, 2500), (2500, 5000), (5000, 10000),
)

# ---------------------------------------------------------------- loudness

# ITU-R BS.1770-4 K-weighting, specified as two biquads by their analogue
# parameters so they can be realised at any sample rate.
SHELF_GAIN_DB = 3.999843853973347
SHELF_Q = 0.7071752369554196
SHELF_FC = 1681.974450955533

HIGHPASS_Q = 0.5003270373238773
HIGHPASS_FC = 38.13547087602444

BLOCK_S = 0.400             # gating block, BS.1770
BLOCK_OVERLAP = 0.75
ABSOLUTE_GATE_LUFS = -70.0
RELATIVE_GATE_LU = -10.0

SHORT_TERM_S = 3.0          # EBU Tech 3342, for loudness range
SHORT_TERM_HOP_S = 1.0
LRA_RELATIVE_GATE_LU = -20.0
LRA_LOW_PCT = 10.0
LRA_HIGH_PCT = 95.0

TRUE_PEAK_OVERSAMPLE = 4

# ---------------------------------------------------------------- thresholds
# Only used to decide what gets called out in the text report. Deliberately
# loose: these flag things worth looking at, not things that are wrong.

DEVIATION_NOTE_DB = 4.0     # call out a third-octave band off target by this
MONO_LOSS_NOTE_DB = 3.0     # call out a band that loses this much summed to mono
CORRELATION_NOTE = 0.3      # call out a low-frequency band below this
SECTION_CHANGE_DB = 2.5     # call out a band that steps by this across a section

# ---------------------------------------------------------------- display

# Sequential ramp on |deviation|: neutral at zero, deep red at the cap.
# Direction is carried by position relative to the zero line, not by hue, so
# this stays a magnitude encoding rather than a diverging one.
RAMP_NEUTRAL = "#dcd9d4"
RAMP_MID = "#d4766a"
RAMP_FULL = "#9e1b2f"
RAMP_CAP_DB = 12.0

INK = "#1c1c1c"
INK_MUTED = "#7a7a7a"
GRID = "#d8d8d8"
ZERO_LINE = "#4a7c8c"

PLOT_TICKS = (50, 100, 200, 500, 1000, 2000, 5000, 10000)
PLOT_TICK_LABELS = ("50", "100", "200", "500", "1k", "2k", "5k", "10k")

# Axis ranges are FIXED, not fitted to the data, so two runs can be compared
# visually without the scale shifting under them. An autoscaled A/B is
# misleading: the same curve looks different because the frame moved.
# Anything outside the frame is clipped and reported, never silently dropped.
PLOT_YLIM = (-24.0, 12.0)
PLOT_XLIM = (25.0, 17000.0)

TIMELINE_BAND_YLIM = (-48.0, -8.0)
TIMELINE_BROADBAND_YLIM = (-36.0, -6.0)
