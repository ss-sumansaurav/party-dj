"""DJ sound effects, made from scratch with maths (no recorded audio): vinyl scratches,
a build-up riser and a drop impact. The DJ page plays them over transitions."""
from __future__ import annotations

import math
import random
import struct
import wave
from pathlib import Path

RATE = 22050


def _save(path: Path, samples: list[float]):
    peak = max(1e-9, max(abs(x) for x in samples))
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b"".join(struct.pack("<h", int(x / peak * 0.85 * 32767)) for x in samples))


def _vowel(seconds: float, pitch: float = 190.0) -> list[float]:
    """A short sung "ahh", the classic sound to scratch."""
    n = int(RATE * seconds)
    out = []
    formants = ((750, 90), (1150, 110), (2600, 200))
    harmonics = [(k, sum(math.exp(-((k * pitch - f) / bw) ** 2) for f, bw in formants) + 0.15 / k)
                 for k in range(1, int(4000 / pitch))]
    for i in range(n):
        t = i / RATE
        p = pitch * (1 + 0.02 * math.sin(2 * math.pi * 5.5 * t))
        out.append(sum(a * math.sin(2 * math.pi * k * p * t) for k, a in harmonics))
    return out


def make_scratch(path: Path, style: str = "baby", seed: int = 1) -> Path:
    """Move a virtual record back and forth over the "ahh" sample."""
    if path.exists():
        return path
    rng = random.Random(seed)
    base = _vowel(0.7)
    strokes = {
        "baby": [0.11, 0.11, 0.09, 0.09, 0.14, 0.14],
        "chirp": [0.08, 0.08, 0.08, 0.08, 0.2],
        "transformer": [0.22, 0.22, 0.12, 0.12],
    }[style]
    out, pos = [], 0.08 * RATE
    for s, length in enumerate(strokes):
        n = int(RATE * length)
        direction = 1 if s % 2 == 0 else -1
        for i in range(n):
            x = i / n
            speed = math.sin(math.pi * x) * 1.6 * direction  # hand speeds up then slows
            pos = min(max(pos + speed, 0), len(base) - 2)
            j = int(pos)
            v = base[j] + (base[j + 1] - base[j]) * (pos - j)
            gate = 1.0
            if style == "transformer":
                gate = 1.0 if int(x * 6) % 2 == 0 else 0.0  # fader cuts
            elif style == "chirp":
                gate = max(0.0, 1 - x * 1.4)  # fader closes as the record moves
            crackle = (rng.random() - 0.5) * 0.04
            out.append((v * abs(speed) * 0.8 + crackle) * gate)
        out += [0.0] * int(RATE * 0.01)
    _save(path, out)
    return path


def make_riser(path: Path, seconds: float = 4.0) -> Path:
    """Rising white noise and a sweeping tone, the build-up before a drop (trance style)."""
    if path.exists():
        return path
    rng = random.Random(7)
    n = int(RATE * seconds)
    out, lp, phase = [], 0.0, 0.0
    for i in range(n):
        x = i / n
        lp += (0.02 + 0.6 * x * x) * ((rng.random() * 2 - 1) - lp)  # filter opens up
        hz = 150 * (10 ** x)  # 150 Hz to 1.5 kHz
        phase += 2 * math.pi * hz / RATE
        out.append((lp * 0.9 + 0.25 * math.sin(phase)) * (x ** 1.6))
    _save(path, out)
    return path


def make_impact(path: Path) -> Path:
    """A deep boom with a burst of noise, for the moment the next song drops in."""
    if path.exists():
        return path
    rng = random.Random(3)
    n = int(RATE * 1.4)
    out, phase = [], 0.0
    for i in range(n):
        t = i / RATE
        hz = 35 + 55 * math.exp(-t * 6)
        phase += 2 * math.pi * hz / RATE
        boom = math.sin(phase) * math.exp(-t * 2.6)
        hit = (rng.random() * 2 - 1) * math.exp(-t * 22) * 0.6
        out.append(boom + hit)
    _save(path, out)
    return path


def make_all(folder: Path) -> list[str]:
    names = []
    for style, seed in (("baby", 1), ("chirp", 2), ("transformer", 3)):
        names.append(make_scratch(folder / f"fx_scratch_{style}.wav", style, seed).name)
    make_riser(folder / "fx_riser.wav")
    make_impact(folder / "fx_impact.wav")
    return names
