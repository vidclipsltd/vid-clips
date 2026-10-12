#!/usr/bin/env python
"""Local CPU Audio Analyser entry point for the VidClips Electron editor.

Media is read from a local filesystem path. Results are emitted as one JSON line
prefixed with VIDCLIPS_AUDIO_RESULT for the Electron IPC wrapper.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def emit(payload: dict[str, Any]) -> None:
    print("VIDCLIPS_AUDIO_RESULT:" + json.dumps(payload, ensure_ascii=False, default=str), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze local audio/video media on CPU.")
    parser.add_argument("--media", required=True, help="Path to a local audio or video file")
    args = parser.parse_args()
    source = Path(args.media).expanduser().resolve()
    if not source.is_file():
        emit({"ok": False, "error": f"Media file does not exist: {source}"})
        return 2

    output_root = Path(os.environ.get("VIDCLIPS_OUTPUTS_DIR", ROOT / "outputs")) / "audio"
    output_root.mkdir(parents=True, exist_ok=True)
    safe_stem = "".join(c if c.isalnum() or c in "-_." else "_" for c in source.stem)[:80] or "audio"
    wav_path = output_root / f"{safe_stem}_analysis.wav"
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        emit({"ok": False, "error": "FFmpeg is unavailable. Reinstall the VidClips desktop dependencies."})
        return 2

    try:
        print("Extracting local audio…", flush=True)
        command = [ffmpeg, "-y", "-v", "error", "-i", str(source), "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", str(wav_path)]
        result = subprocess.run(command, capture_output=True, text=True, timeout=3600)
        if result.returncode or not wav_path.is_file():
            emit({"ok": False, "error": "Could not extract an audio stream. " + (result.stderr[-700:] if result.stderr else "This file may not contain audio.")})
            return 1

        import librosa
        import numpy as np

        print("Analyzing waveform, silence and beats…", flush=True)
        signal, sample_rate = librosa.load(str(wav_path), sr=16000, mono=True)
        if not len(signal):
            emit({"ok": False, "error": "No audio samples were found."})
            return 1
        rms = librosa.feature.rms(y=signal, frame_length=2048, hop_length=512)[0]
        times = librosa.frames_to_time(np.arange(len(rms)), sr=sample_rate, hop_length=512)
        floor = max(float(np.percentile(rms, 15)) * 0.8, 0.004)
        silent = rms < floor
        silence_segments = []
        start_idx = None
        for idx, is_silent in enumerate(silent):
            if is_silent and start_idx is None:
                start_idx = idx
            if start_idx is not None and (not is_silent or idx == len(silent) - 1):
                end_idx = idx if not is_silent else idx + 1
                start_sec = float(times[start_idx])
                end_sec = float(times[min(end_idx, len(times) - 1)])
                if end_sec - start_sec >= 0.3:
                    silence_segments.append({"start_sec": round(start_sec, 3), "end_sec": round(end_sec, 3), "duration_sec": round(end_sec - start_sec, 3), "threshold": round(floor, 5)})
                start_idx = None

        tempo, beat_frames = librosa.beat.beat_track(y=signal, sr=sample_rate)
        tempo_value = float(np.asarray(tempo).reshape(-1)[0]) if np.asarray(tempo).size else 0.0
        beat_times = librosa.frames_to_time(beat_frames, sr=sample_rate)
        transcript: dict[str, Any] = {"language": None, "text": "", "segments": [], "status": "not_run"}
        try:
            print("Loading local Whisper speech model (first run may download it)…", flush=True)
            import whisper
            model = whisper.load_model("base", device="cpu")
            transcription = model.transcribe(str(wav_path), verbose=False, word_timestamps=True, fp16=False)
            segments = []
            for seg in transcription.get("segments", []):
                words = []
                for word in seg.get("words", []) or []:
                    words.append({
                        "text": str(word.get("word", "")).strip(),
                        "start_sec": round(float(word.get("start", 0)), 3),
                        "end_sec": round(float(word.get("end", 0)), 3),
                        "confidence": round(float(word.get("probability", 0)), 4) if word.get("probability") is not None else None,
                    })
                segments.append({
                    "start_sec": round(float(seg.get("start", 0)), 3),
                    "end_sec": round(float(seg.get("end", 0)), 3),
                    "text": str(seg.get("text", "")).strip(),
                    "words": words,
                })
            transcript = {"language": transcription.get("language"), "text": str(transcription.get("text", "")).strip(), "segments": segments, "status": "complete"}
        except Exception as exc:
            transcript = {"language": None, "text": "", "segments": [], "status": "unavailable", "error": str(exc)}
            print("Transcription unavailable: " + str(exc), flush=True)

        # Lightweight energy/spectral transient candidates, not semantic labels.
        print("Detecting prominent sound transients…", flush=True)
        flux = librosa.onset.onset_strength(y=signal, sr=sample_rate)
        onset_frames = librosa.onset.onset_detect(onset_envelope=flux, sr=sample_rate, units="frames", backtrack=False)
        events = []
        onset_times = librosa.frames_to_time(onset_frames, sr=sample_rate)
        for frame in onset_frames[:500]:
            time_sec = float(librosa.frames_to_time([frame], sr=sample_rate)[0])
            events.append({"label": "sound transient", "start_sec": round(max(0, time_sec - 0.05), 3), "end_sec": round(time_sec + 0.25, 3), "confidence": None, "method": "onset-energy heuristic"})
        output = {
            "has_audio": True,
            "source_path": str(source),
            "audio_path": str(wav_path),
            "duration_sec": round(len(signal) / sample_rate, 3),
            "transcript": transcript,
            "silence_segments": silence_segments,
            "music": {"estimated_bpm": round(tempo_value, 2), "beat_timestamps_sec": [round(float(t), 3) for t in beat_times]},
            "volume": {"rms_mean": round(float(np.sqrt(np.mean(signal ** 2))), 5), "peak": round(float(np.max(np.abs(signal))), 5)},
            "sound_events": events,
            "classification": {"status": "heuristic_only", "note": "Speech/music/effect semantic classification requires a dedicated model and is not inferred from transient detections."},
            "separation": {"status": "not_configured", "stems": [], "note": "Install and configure a compatible local Demucs model to generate real separated stems."},
            "notes": ["Runs locally on CPU; source media is not uploaded.", "Sound-event candidates are generic transients, not reliable semantic event labels."]
        }
        emit({"ok": True, "local": True, "uploaded": False, "device": "cpu", "analysis": output})
        return 0
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        emit({"ok": False, "error": str(exc), "details": traceback.format_exc(limit=8)})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
