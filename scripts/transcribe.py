#!/usr/bin/env python3
"""
Local audio transcription helper using OpenAI Whisper.

Runs entirely locally — no API calls, no cost.
Supports: .m4a, .mp3, .wav, .mp4, .ogg, .flac, .webm

Usage:
    python scripts/transcribe.py audio.m4a
    python scripts/transcribe.py audio.m4a --model small
    python scripts/transcribe.py dataset/demo/    # transcribe all audio in a folder

Install:
    pip install openai-whisper
"""

import argparse
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

SUPPORTED_FORMATS = {".m4a", ".mp3", ".wav", ".mp4", ".ogg", ".flac", ".webm"}
DEFAULT_MODEL = "base"


def transcribe_file(audio_path: Path, model_name: str = DEFAULT_MODEL, save: bool = True) -> str:
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    if audio_path.suffix.lower() not in SUPPORTED_FORMATS:
        raise ValueError(
            f"Unsupported format: {audio_path.suffix}. "
            f"Supported: {', '.join(SUPPORTED_FORMATS)}"
        )

    try:
        import whisper  # type: ignore
    except ImportError:
        raise ImportError(
            "openai-whisper is not installed.\n"
            "Install with: pip install openai-whisper"
        )

    logger.info(f"Loading Whisper model: {model_name}")
    model = whisper.load_model(model_name)

    logger.info(f"Transcribing: {audio_path.name}")
    result = model.transcribe(str(audio_path))
    text = result["text"].strip()

    if save:
        out_path = audio_path.with_suffix(".txt")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text)
        logger.info(f"Saved transcript to: {out_path}")

    return text


def transcribe_folder(folder: Path, model_name: str = DEFAULT_MODEL) -> dict:
    """Transcribe all audio files in a folder. Skips files that already have a .txt."""
    results = {}
    audio_files = [
        f for f in folder.iterdir()
        if f.is_file() and f.suffix.lower() in SUPPORTED_FORMATS
    ]

    if not audio_files:
        logger.warning(f"No audio files found in {folder}")
        return results

    logger.info(f"Found {len(audio_files)} audio file(s) in {folder}")

    for audio_file in sorted(audio_files):
        txt_path = audio_file.with_suffix(".txt")
        if txt_path.exists():
            logger.info(f"Skipping {audio_file.name} — .txt already exists")
            with open(txt_path) as f:
                results[str(audio_file)] = f.read()
            continue

        try:
            text = transcribe_file(audio_file, model_name=model_name, save=True)
            results[str(audio_file)] = text
        except Exception as e:
            logger.error(f"Failed to transcribe {audio_file.name}: {e}")
            results[str(audio_file)] = None

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Local audio transcription via Whisper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/transcribe.py audio.m4a
  python scripts/transcribe.py audio.m4a --model small
  python scripts/transcribe.py dataset/demo/

Model sizes (speed vs accuracy):
  tiny   — fastest
  base   — default, good balance
  small  — better accuracy
  medium — high accuracy, slower
  large  — best accuracy, most RAM
        """
    )
    parser.add_argument("input", help="Audio file or folder path")
    parser.add_argument(
        "--model", default=DEFAULT_MODEL,
        choices=["tiny", "base", "small", "medium", "large"],
        help=f"Whisper model size (default: {DEFAULT_MODEL})"
    )
    parser.add_argument("--no-save", action="store_true", help="Print to stdout only")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(message)s"
    )

    input_path = Path(args.input)

    if input_path.is_dir():
        results = transcribe_folder(input_path, model_name=args.model)
        print(f"\nTranscribed {sum(1 for v in results.values() if v)} file(s).")
    elif input_path.is_file():
        text = transcribe_file(input_path, model_name=args.model, save=not args.no_save)
        if args.no_save:
            print(text)
        else:
            print(f"\nTranscript saved to: {input_path.with_suffix('.txt')}")
    else:
        logger.error(f"Input not found: {input_path}")
        sys.exit(1)


if __name__ == "__main__":
    main()
