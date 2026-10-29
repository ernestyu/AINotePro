"""Managed, collection-free MP3 preview playback.

The temporary file remains present until the Qt player reaches EndOfMedia,
reports an error, or the Audio dialog explicitly stops playback on close.
No fixed-duration unlink timer is used.
"""
from __future__ import annotations

import os
import tempfile

_ACTIVE = set()


class PreviewUnavailable(RuntimeError):
    pass


def play_preview(data: bytes):
    if not data:
        raise PreviewUnavailable("Preview audio is empty")
    try:
        from aqt.qt import QUrl
        from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
    except ImportError as exc:
        raise PreviewUnavailable("Qt Multimedia is unavailable in this Anki runtime") from exc

    stop_previews()
    fd, path = tempfile.mkstemp(prefix="ainotepro-preview-", suffix=".mp3")
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
        session = _PreviewSession(path, QMediaPlayer, QAudioOutput)
        _ACTIVE.add(session)
        session.player.setSource(QUrl.fromLocalFile(path))
        session.player.play()
    except Exception:
        if "session" in locals():
            session.close()
        else:
            try:
                os.unlink(path)
            except OSError:
                pass
        raise


def stop_previews():
    for session in tuple(_ACTIVE):
        session.close()


class _PreviewSession:
    def __init__(self, path, media_player_class, audio_output_class):
        self.path = path
        self.closed = False
        self.player = media_player_class()
        self.output = audio_output_class(self.player)
        self.player.setAudioOutput(self.output)
        self.player.mediaStatusChanged.connect(self._status)
        self.player.errorOccurred.connect(self._error)

    def _status(self, status):
        from PyQt6.QtMultimedia import QMediaPlayer
        if status in (QMediaPlayer.MediaStatus.EndOfMedia,
                      QMediaPlayer.MediaStatus.InvalidMedia):
            self.close()

    def _error(self, *_):
        self.close()

    def close(self):
        if self.closed:
            return
        self.closed = True
        _ACTIVE.discard(self)
        try:
            self.player.stop()
            self.player.deleteLater()
        finally:
            try:
                os.unlink(self.path)
            except FileNotFoundError:
                pass
            except OSError as exc:
                print(f"[AINotePro Audio] preview cleanup: {exc}")
