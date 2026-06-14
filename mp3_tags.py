"""Write ID3 tags for exported audiobook section MP3 files."""

from __future__ import annotations

from pathlib import Path


def tag_audiobook_section(
    mp3_path: Path,
    *,
    track_number: int,
    total_tracks: int,
    title: str,
    album: str,
    artist: str = "Audiobook",
) -> None:
    """Apply standard audiobook ID3 tags (TRCK, TIT2, TALB, TPE1)."""
    try:
        from mutagen.id3 import ID3, TALB, TIT2, TRCK, TPE1, ID3NoHeaderError
        from mutagen.mp3 import MP3
    except ImportError:
        return

    try:
        audio = MP3(mp3_path, ID3=ID3)
    except ID3NoHeaderError:
        audio = MP3(mp3_path)
        audio.add_tags()

    audio.tags.delall("TIT2")
    audio.tags.delall("TRCK")
    audio.tags.delall("TALB")
    audio.tags.delall("TPE1")
    audio.tags.add(TIT2(encoding=3, text=title))
    audio.tags.add(TRCK(encoding=3, text=f"{track_number}/{total_tracks}"))
    audio.tags.add(TALB(encoding=3, text=album))
    audio.tags.add(TPE1(encoding=3, text=artist))
    audio.save()
