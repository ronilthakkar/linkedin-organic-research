#!/usr/bin/env python3
"""Download YouTube transcripts listed in youtube_urls.csv as Markdown files."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from youtube_transcript_api import YouTubeTranscriptApi


DEFAULT_INPUT = Path("youtube_urls.csv")
DEFAULT_OUTPUT_DIR = Path("research/youtube-transcripts")


def extract_video_id(url: str) -> str:
    parsed = urlparse(url.strip())

    if parsed.hostname in {"youtu.be", "www.youtu.be"}:
        return parsed.path.strip("/")

    if parsed.hostname and parsed.hostname.endswith("youtube.com"):
        query_id = parse_qs(parsed.query).get("v", [""])[0]
        if query_id:
            return query_id

        path_parts = [part for part in parsed.path.split("/") if part]
        if len(path_parts) >= 2 and path_parts[0] in {"embed", "shorts", "live"}:
            return path_parts[1]

    raise ValueError(f"Could not extract a YouTube video ID from: {url}")


def safe_path_part(value: str, fallback: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*]', "", value.strip())
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or fallback


def safe_filename(value: str, fallback: str) -> str:
    cleaned = safe_path_part(value, fallback).lower()
    cleaned = re.sub(r"[^a-z0-9]+", "-", cleaned)
    cleaned = cleaned.strip("-")
    return f"{cleaned or fallback}.md"


def transcript_text(fetched_transcript) -> str:
    lines: list[str] = []
    for snippet in fetched_transcript:
        if hasattr(snippet, "text"):
            text = snippet.text
        else:
            text = snippet.get("text", "")
        text = " ".join(text.split())
        if text:
            lines.append(text)
    return "\n".join(lines)


def markdown_document(title: str, author: str, video_url: str, transcript: str) -> str:
    return (
        f"# {title}\n\n"
        f"Author: {author}\n\n"
        f"Video URL: {video_url}\n\n"
        "## Transcript\n\n"
        f"{transcript}\n"
    )


def download_transcripts(input_csv: Path, output_dir: Path) -> int:
    if not input_csv.exists():
        print(f"Input CSV not found: {input_csv}", file=sys.stderr)
        return 1

    ytt_api = YouTubeTranscriptApi()
    failures = 0

    with input_csv.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        required_columns = {"expert_name", "youtube_url"}
        missing_columns = required_columns - set(reader.fieldnames or [])
        if missing_columns:
            print(
                f"Missing required CSV columns: {', '.join(sorted(missing_columns))}",
                file=sys.stderr,
            )
            return 1

        for row_number, row in enumerate(reader, start=2):
            expert_name = (row.get("expert_name") or "").strip()
            video_url = (row.get("youtube_url") or "").strip()
            video_title = (row.get("video_title") or "").strip()
            author = (row.get("author") or "").strip()

            if not expert_name or not video_url:
                print(f"Skipping row {row_number}: expert_name and youtube_url are required.")
                continue

            try:
                video_id = extract_video_id(video_url)
                title = video_title or video_id
                byline = author or expert_name

                fetched_transcript = ytt_api.fetch(video_id)
                transcript = transcript_text(fetched_transcript)

                expert_dir = output_dir / safe_path_part(expert_name, "unknown-expert")
                expert_dir.mkdir(parents=True, exist_ok=True)

                output_path = expert_dir / safe_filename(title, video_id)
                output_path.write_text(
                    markdown_document(title, byline, video_url, transcript),
                    encoding="utf-8",
                )
                print(f"Saved: {output_path}")
            except Exception as exc:
                failures += 1
                print(f"Failed row {row_number} ({video_url}): {exc}", file=sys.stderr)

    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download YouTube transcripts from youtube_urls.csv."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"CSV file to read. Defaults to {DEFAULT_INPUT}.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Transcript output directory. Defaults to {DEFAULT_OUTPUT_DIR}.",
    )
    args = parser.parse_args()

    return download_transcripts(args.input, args.output_dir)


if __name__ == "__main__":
    raise SystemExit(main())
