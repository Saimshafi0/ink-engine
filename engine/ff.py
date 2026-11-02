"""Find ffmpeg (system one, or the one shipped by imageio-ffmpeg on Windows)."""
import shutil

_FF = None


def ffmpeg():
    global _FF
    if _FF:
        return _FF
    p = shutil.which("ffmpeg")
    if not p:
        try:
            import imageio_ffmpeg
            p = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            p = "ffmpeg"
    _FF = p
    return p
