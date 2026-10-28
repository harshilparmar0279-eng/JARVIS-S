"""
core/speaker_id.py — Speaker Identification, Biometrics & Gender Detection.

Features:
1. Owner Biometrics (Voice Verification for "Harshil").
2. Multi-Speaker Detection: Identifies whether the speaker is the owner or someone else.
3. Pitch & Gender Detection: Detects fundamental vocal frequency (F0).
   - High pitch (>175 Hz): Female voice detected.
   - Low pitch (<=175 Hz): Male voice detected.
4. Intelligent Intervention:
   - Unknown male voice: "Sir, kya ye aapka dost baat kar raha hai?"
   - Unknown female voice: "Sir, koi female voice detect hui hai, kya main inki command follow karu?"
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional, Tuple
import numpy as np

_BASE_DIR = Path(__file__).resolve().parent.parent
PROFILES_FILE = _BASE_DIR / "config" / "speaker_profiles.json"


def estimate_pitch(pcm_data: np.ndarray, sr: int = 16000) -> float:
    """
    Estimate fundamental frequency (F0) pitch using normalized autocorrelation.
    Returns estimated pitch in Hz, or 0.0 if unvoiced or silence.
    """
    if len(pcm_data) < int(sr * 0.04):
        return 0.0
    x = pcm_data.astype(np.float32)
    x = x - np.mean(x)
    max_amp = np.max(np.abs(x))
    if max_amp < 80.0:
        return 0.0

    # Bounds: 60 Hz to 420 Hz
    min_lag = max(1, int(sr / 420))
    max_lag = min(len(x) - 1, int(sr / 60))

    if max_lag <= min_lag:
        return 0.0

    corr = np.correlate(x, x, mode="full")
    corr = corr[len(corr) // 2 :]

    if len(corr) <= max_lag:
        return 0.0

    search_region = corr[min_lag:max_lag]
    if len(search_region) == 0:
        return 0.0

    peak_idx = min_lag + int(np.argmax(search_region))
    if corr[0] > 0 and (corr[peak_idx] / corr[0]) > 0.25:
        return float(sr / peak_idx)
    return 0.0


def extract_acoustic_embedding(pcm_data: np.ndarray, sr: int = 16000) -> np.ndarray:
    """
    Extracts a 16-dimensional normalized acoustic fingerprint:
    - Band energy distribution (4 sub-bands)
    - Spectral centroid & roll-off (85%)
    - Zero crossing rate
    - Pitch statistics
    - Relative harmonic distribution
    """
    if len(pcm_data) < 256:
        return np.zeros(16, dtype=np.float32)

    x = pcm_data.astype(np.float32)
    x = x - np.mean(x)

    # 1. Zero crossing rate
    zcr = np.mean(np.abs(np.diff(np.sign(x + 1e-6))))

    # 2. FFT & power spectrum
    fft_vals = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    freqs = np.fft.rfftfreq(len(x), 1.0 / sr)
    total_energy = np.sum(fft_vals) + 1e-6

    # 3. Spectral centroid
    spectral_centroid = np.sum(freqs * fft_vals) / total_energy

    # 4. Energy in 4 acoustic frequency bands
    b1 = np.sum(fft_vals[(freqs >= 80) & (freqs < 500)]) / total_energy
    b2 = np.sum(fft_vals[(freqs >= 500) & (freqs < 1500)]) / total_energy
    b3 = np.sum(fft_vals[(freqs >= 1500) & (freqs < 3000)]) / total_energy
    b4 = np.sum(fft_vals[(freqs >= 3000) & (freqs < 6000)]) / total_energy

    # 5. Pitch
    pitch = estimate_pitch(pcm_data, sr)

    vec = np.array([
        float(zcr * 10.0),
        float(spectral_centroid / 3000.0),
        float(b1),
        float(b2),
        float(b3),
        float(b4),
        float(pitch / 250.0),
        float(np.std(fft_vals[:100]) / total_energy),
        float(np.mean(fft_vals[:50]) / total_energy),
        float(np.mean(fft_vals[50:150]) / total_energy),
        float(np.mean(fft_vals[150:300]) / total_energy),
        float(np.percentile(fft_vals, 90) / total_energy),
        float(np.percentile(fft_vals, 75) / total_energy),
        float(np.percentile(fft_vals, 50) / total_energy),
        float(np.max(np.abs(x)) / 32768.0),
        float(np.std(x) / 32768.0),
    ], dtype=np.float32)

    norm = np.linalg.norm(vec) + 1e-6
    return vec / norm


class SpeakerIdentifier:
    """Manages voice verification and multi-speaker classification for JARVIS."""

    def __init__(self):
        self.owner_name = "Harshil"
        self._owner_embedding: Optional[np.ndarray] = None
        self._similarity_threshold = 0.68
        self._load_profiles()

    def _load_profiles(self):
        if PROFILES_FILE.is_file():
            try:
                data = json.loads(PROFILES_FILE.read_text(encoding="utf-8"))
                owner_data = data.get(self.owner_name)
                if owner_data and "embedding" in owner_data:
                    self._owner_embedding = np.array(owner_data["embedding"], dtype=np.float32)
                    print(f"[SpeakerID] Loaded voice biometrics for {self.owner_name}.")
            except Exception as e:
                print(f"[SpeakerID] Profile load warning: {e}")

    def save_profiles(self):
        try:
            PROFILES_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {}
            if self._owner_embedding is not None:
                data[self.owner_name] = {
                    "name": self.owner_name,
                    "embedding": self._owner_embedding.tolist()
                }
            PROFILES_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"[SpeakerID] Profile save warning: {e}")

    def enroll_owner(self, pcm_data: np.ndarray, sr: int = 16000) -> bool:
        """Enrolls or dynamically adapts the owner's voice embedding."""
        emb = extract_acoustic_embedding(pcm_data, sr)
        if self._owner_embedding is None:
            self._owner_embedding = emb
        else:
            # Exponential moving average
            self._owner_embedding = 0.85 * self._owner_embedding + 0.15 * emb
            self._owner_embedding /= (np.linalg.norm(self._owner_embedding) + 1e-6)
        self.save_profiles()
        return True

    def verify_speaker(self, pcm_data: np.ndarray, sr: int = 16000) -> dict:
        """
        Analyzes audio chunk and identifies speaker, gender, and intervention message.
        """
        pitch = estimate_pitch(pcm_data, sr)
        emb = extract_acoustic_embedding(pcm_data, sr)

        # Determine gender based on vocal fundamental frequency (F0)
        # Female speech generally centers between 175-260 Hz; male speech 85-165 Hz.
        gender = "female" if pitch >= 175.0 else "male"

        similarity = 1.0
        is_owner = True

        if self._owner_embedding is not None:
            similarity = float(np.dot(self._owner_embedding, emb))
            # Harshil is male; if pitch is high female, it cannot be Harshil
            if gender == "female" and pitch > 185.0:
                is_owner = False
            else:
                is_owner = (similarity >= self._similarity_threshold)
        else:
            # First run: auto-enroll as owner
            self.enroll_owner(pcm_data, sr)
            is_owner = True
            similarity = 1.0

        if is_owner:
            return {
                "is_owner": True,
                "speaker": self.owner_name,
                "gender": gender,
                "pitch_hz": pitch,
                "confidence": similarity,
                "intervention_msg": None,
            }

        # Non-owner detected
        if gender == "female":
            speaker_label = "Guest Female"
            intervention = "Sir, koi female voice detect hui hai, kya main inki command follow karu?"
        else:
            speaker_label = "Guest Male"
            intervention = "Sir, kya ye aapka dost baat kar raha hai?"

        return {
            "is_owner": False,
            "speaker": speaker_label,
            "gender": gender,
            "pitch_hz": pitch,
            "confidence": similarity,
            "intervention_msg": intervention,
        }


_speaker_id_instance: Optional[SpeakerIdentifier] = None


def get_speaker_identifier() -> SpeakerIdentifier:
    global _speaker_id_instance
    if _speaker_id_instance is None:
        _speaker_id_instance = SpeakerIdentifier()
    return _speaker_id_instance
