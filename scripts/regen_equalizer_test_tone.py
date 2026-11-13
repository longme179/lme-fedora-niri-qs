#!/usr/bin/env python3
"""One-shot generator for assets/equalizer-test.wav (the ChannelTestTone synthesis, verbatim).

L 660 Hz, R 880 Hz, then both 770 Hz with 15 ms fades — the equalizer.sh test port. The
native eqTest ships this file instead of synthesizing it (quickshell 0.3.2 cannot write
files); regeneration is deterministic, so the asset never drifts.
"""
# SPDX-License-Identifier: GPL-3.0-or-later
import math
import wave
from pathlib import Path

RATE = 48000
SEGMENTS = ((0.75, 660, 0), (0.18, 0, 0), (0.75, 0, 880), (0.18, 0, 0), (1.0, 770, 770))


def main():
    target = Path(__file__).resolve().parents[1] / "assets" / "equalizer-test.wav"
    with wave.open(str(target), "wb") as stream:
        stream.setnchannels(2)
        stream.setsampwidth(2)
        stream.setframerate(RATE)
        for duration, left_hz, right_hz in SEGMENTS:
            for index in range(int(duration * RATE)):
                fade = min(1.0, index / (RATE * 0.015), (duration * RATE - index) / (RATE * 0.015))

                def sample(freq):
                    return int(9000 * fade * math.sin(2 * math.pi * freq * index / RATE)) if freq else 0

                stream.writeframesraw(sample(left_hz).to_bytes(2, "little", signed=True)
                                      + sample(right_hz).to_bytes(2, "little", signed=True))
    print(target, target.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
