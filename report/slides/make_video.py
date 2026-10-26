import subprocess, wave
from pathlib import Path
import imageio_ffmpeg
FF = imageio_ffmpeg.get_ffmpeg_exe()
D = Path(__file__).resolve().parent
seg = D / "segments"; seg.mkdir(exist_ok=True)
lst = []
for i in range(1, 10):
    png, wav = D / "png" / f"slide{i:02d}.png", D / "audio" / f"s{i:02d}.wav"
    with wave.open(str(wav)) as w:
        dur = w.getnframes() / w.getframerate() + 1.0
    out = seg / f"seg{i:02d}.mp4"
    subprocess.run([FF, "-y", "-loglevel", "error", "-loop", "1", "-framerate", "30", "-i", str(png), "-i", str(wav),
                    "-filter_complex", "[1:a]apad=pad_dur=1.0,adelay=300|300[a]", "-map", "0:v", "-map", "[a]",
                    "-t", f"{dur + 0.3:.2f}", "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p",
                    "-vf", "scale=1920:1080", "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2", str(out)], check=True)
    lst.append(f"file '{out}'")
(seg / "list.txt").write_text("\n".join(lst) + "\n")
final = D / "When Do AI Graders Collude - presentation.mp4"
subprocess.run([FF, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(seg / "list.txt"), "-c", "copy",
                str(final)], check=True)
print(final, final.stat().st_size)
