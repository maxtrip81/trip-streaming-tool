"""DSP: 10-band graphic equalizer, compressor and level metering."""

from __future__ import annotations

import math

import numpy as np

try:
    from scipy.signal import sosfilt
except ImportError:  # pragma: no cover - scipy is a declared dependency
    sosfilt = None

EQ_BANDS = [31, 62, 125, 250, 500, 1000, 2000, 4000, 8000, 16000]

EQ_PRESETS = {
    "flat": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    "voice": [-6, -4, -2, 0, 2, 3, 3, 2, 0, -2],
    "bass": [6, 5, 4, 2, 0, 0, 0, 0, 0, 0],
    "treble": [0, 0, 0, 0, 0, 1, 2, 4, 5, 6],
    "loudness": [5, 4, 2, 0, -1, -1, 0, 2, 4, 5],
    "radio": [-4, 2, 3, 1, 0, 1, 2, 3, 2, -2],
}


def db_to_lin(db: float) -> float:
    return 10.0 ** (db / 20.0)


def lin_to_db(value: float, floor: float = -90.0) -> float:
    return 20.0 * math.log10(value) if value > 1e-9 else floor


def peaking_sos(freq: float, gain_db: float, samplerate: int, q: float = 1.41) -> np.ndarray:
    """RBJ cookbook peaking filter as a single second-order section."""
    freq = min(freq, samplerate * 0.45)
    a = 10 ** (gain_db / 40.0)
    w0 = 2 * math.pi * freq / samplerate
    alpha = math.sin(w0) / (2 * q)
    cos_w0 = math.cos(w0)
    b0, b1, b2 = 1 + alpha * a, -2 * cos_w0, 1 - alpha * a
    a0, a1, a2 = 1 + alpha / a, -2 * cos_w0, 1 - alpha / a
    return np.array([b0 / a0, b1 / a0, b2 / a0, 1.0, a1 / a0, a2 / a0])


class Equalizer:
    def __init__(self, samplerate: int, channels: int):
        self.samplerate = samplerate
        self.channels = channels
        self.gains = [0.0] * len(EQ_BANDS)
        self._sos = None
        self._zi = None

    def set_gains(self, gains) -> None:
        gains = [float(g) for g in gains]
        if gains == self.gains and self._sos is not None:
            return
        self.gains = gains
        active = [(f, g) for f, g in zip(EQ_BANDS, gains) if abs(g) > 0.01]
        if not active:
            self._sos = None
            self._zi = None
            return
        sos = np.vstack([peaking_sos(f, g, self.samplerate) for f, g in active])
        if self._zi is None or self._zi.shape[0] != sos.shape[0]:
            self._zi = np.zeros((sos.shape[0], 2, self.channels))
        self._sos = sos

    def process(self, block: np.ndarray) -> np.ndarray:
        if self._sos is None or sosfilt is None:
            return block
        out, self._zi = sosfilt(self._sos, block, axis=0, zi=self._zi)
        return out.astype(np.float32)


class Compressor:
    """Feed-forward peak compressor working on small sub-blocks (vectorised)."""

    SUB = 32

    def __init__(self, samplerate: int):
        self.samplerate = samplerate
        self.threshold_db = -20.0
        self.ratio = 4.0
        self.attack_ms = 10.0
        self.release_ms = 200.0
        self.makeup_db = 0.0
        self._env_db = -90.0
        self._last_gain = 1.0
        self.gain_reduction_db = 0.0

    def configure(self, threshold_db, ratio, attack_ms, release_ms, makeup_db) -> None:
        self.threshold_db = float(threshold_db)
        self.ratio = max(1.0, float(ratio))
        self.attack_ms = max(0.1, float(attack_ms))
        self.release_ms = max(1.0, float(release_ms))
        self.makeup_db = float(makeup_db)

    def process(self, block: np.ndarray) -> np.ndarray:
        frames = block.shape[0]
        if frames == 0:
            return block
        sub = self.SUB
        n_sub = (frames + sub - 1) // sub
        pad = n_sub * sub - frames
        mags = np.abs(block).max(axis=1)
        if pad:
            mags = np.concatenate([mags, np.zeros(pad, dtype=mags.dtype)])
        peaks = mags.reshape(n_sub, sub).max(axis=1)
        peaks_db = 20 * np.log10(np.maximum(peaks, 1e-9))
        dt = sub / self.samplerate
        att = math.exp(-dt / (self.attack_ms / 1000.0))
        rel = math.exp(-dt / (self.release_ms / 1000.0))
        makeup = db_to_lin(self.makeup_db)
        gains = np.empty(n_sub)
        env = self._env_db
        thr, ratio = self.threshold_db, self.ratio
        for i, level in enumerate(peaks_db):
            coef = att if level > env else rel
            env = coef * env + (1 - coef) * level
            over = env - thr
            gains[i] = 10 ** ((-over * (1 - 1 / ratio)) / 20) if over > 0 else 1.0
        self._env_db = env
        self.gain_reduction_db = -lin_to_db(gains[-1], 0.0) if gains[-1] < 1 else 0.0
        # linear interpolation between sub-block gains for click-free output
        points = np.concatenate([[self._last_gain], gains])
        x = np.arange(frames) / sub
        g = np.interp(x, np.arange(n_sub + 1), points)
        self._last_gain = gains[-1]
        return (block * (g[:, None] * makeup)).astype(np.float32)


def levels_db(block: np.ndarray) -> tuple[list[float], list[float]]:
    """Return (peak_db, rms_db) per channel."""
    if block.size == 0:
        return [-90.0] * block.shape[1], [-90.0] * block.shape[1]
    peak = np.abs(block).max(axis=0)
    rms = np.sqrt(np.mean(np.square(block, dtype=np.float64), axis=0))
    return [lin_to_db(float(p)) for p in peak], [lin_to_db(float(r)) for r in rms]
