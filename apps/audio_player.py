"""
音频播放器 —— 播放 WAV / 原始 PCM 数据。

特性:
  · WAV:自动解析头部(采样率/位深/通道)
  · PCM 裸数据:手动设置采样率、位深(8/16/24/32)、通道数
  · 可拖动进度条 seek
  · 波形显示(PIL 不需要,纯 Canvas)
  · 播放引擎基于 sounddevice;未安装或无声卡时自动降级(仍可解析/看波形)
"""
from __future__ import annotations

import threading
import time
import wave
from pathlib import Path

import tkinter as tk
from tkinter import filedialog

try:
    import customtkinter as ctk
    HAS_CTK = True
except ImportError:
    HAS_CTK = False

try:
    import numpy as np
    HAS_NP = True
except ImportError:
    HAS_NP = False

try:
    import sounddevice as sd
    HAS_SD = True
except Exception:
    HAS_SD = False

from core.base_app import ToolApp

SAMPLE_RATES = ["8000", "11025", "16000", "22050", "32000", "44100", "48000", "96000"]
BIT_DEPTHS = ["8", "16", "24", "32"]
CHANNELS = ["1", "2"]


# ---------------- PCM 解码(与设备无关,可独立测试) ----------------

def pcm_to_float32(raw: bytes, bit_depth: int, channels: int):
    """原始 PCM 字节 → float32 numpy 数组,形状 (frames, channels)。"""
    if not HAS_NP:
        raise RuntimeError("需要 numpy: pip install numpy")
    if bit_depth == 8:
        # WAV 惯例:8bit 为无符号
        a = np.frombuffer(raw, dtype=np.uint8).astype(np.float32)
        a = (a - 128.0) / 128.0
    elif bit_depth == 16:
        a = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    elif bit_depth == 32:
        a = np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2147483648.0
    elif bit_depth == 24:
        n = len(raw) // 3
        b = np.frombuffer(raw[: n * 3], dtype=np.uint8).reshape(n, 3).astype(np.int32)
        v = b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16)
        v = np.where(v & 0x800000, v - (1 << 24), v)  # 符号扩展
        a = v.astype(np.float32) / 8388608.0
    else:
        raise ValueError(f"不支持的位深: {bit_depth}")
    frames = len(a) // channels
    return a[: frames * channels].reshape(frames, channels)


def read_wav(path: str | Path):
    """读 WAV,返回 (float32数组, samplerate, channels, bit_depth)。"""
    with wave.open(str(path), "rb") as w:
        ch, sw, sr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(n)
    data = pcm_to_float32(raw, sw * 8, ch)
    return data, sr, ch, sw * 8


def fmt_time(sec: float) -> str:
    sec = max(0.0, sec)
    m, s = divmod(int(sec), 60)
    return f"{m:02d}:{s:02d}"


# ---------------- 播放引擎 ----------------

class PlaybackEngine:
    """sounddevice 回调式播放,支持 seek。无音频设备时 open 会失败,调用方需容错。"""

    def __init__(self):
        self.data = None          # float32 (frames, ch)
        self.samplerate = 44100
        self.channels = 1
        self._pos = 0             # 当前帧
        self._stream = None
        self._lock = threading.Lock()

    # -- 数据装载(无设备也可用,便于测试) --
    def load(self, data, samplerate: int, channels: int):
        self.stop()
        self.data = data
        self.samplerate = int(samplerate)
        self.channels = int(channels)
        self._pos = 0

    @property
    def duration(self) -> float:
        if self.data is None or self.samplerate <= 0:
            return 0.0
        return len(self.data) / self.samplerate

    @property
    def position(self) -> float:
        return self._pos / self.samplerate if self.samplerate else 0.0

    @property
    def fraction(self) -> float:
        d = self.duration
        return min(1.0, self.position / d) if d > 0 else 0.0

    def seek_fraction(self, frac: float):
        if self.data is None:
            return
        with self._lock:
            self._pos = max(0, min(len(self.data) - 1, int(frac * len(self.data))))

    # -- 播放控制 --
    def _callback(self, outdata, frames, _time, _status):
        with self._lock:
            start = self._pos
            end = min(start + frames, len(self.data))
            chunk = self.data[start:end]
            n = len(chunk)
            self._pos = end
        outdata[:n] = chunk
        if n < frames:
            outdata[n:] = 0.0

    def play(self) -> bool:
        if not HAS_SD or self.data is None:
            return False
        if self._stream is not None:
            self._stream.start()
            return True
        try:
            if self._pos >= len(self.data):
                self._pos = 0
            self._stream = sd.OutputStream(
                samplerate=self.samplerate, channels=self.channels,
                dtype="float32", callback=self._callback)
            self._stream.start()
            return True
        except Exception:
            self._stream = None
            return False

    def pause(self):
        if self._stream is not None:
            try:
                self._stream.stop()
            except Exception:
                pass

    def stop(self):
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        with self._lock:
            self._pos = 0

    @property
    def is_playing(self) -> bool:
        return self._stream is not None and self._stream.active

    @property
    def finished(self) -> bool:
        return self.data is not None and self._pos >= len(self.data) and not self.is_playing


# ---------------- UI ----------------

class AudioPlayerApp(ToolApp):
    def build(self, root: tk.Misc) -> None:
        self.engine = PlaybackEngine()
        self._file_path: str | None = None
        self._dragging = False
        self._tick_id = None
        cfg = self.env.get_config({"samplerate": "44100", "bit_depth": "16", "channels": "1"})

        wrap = ctk.CTkFrame(root, fg_color="transparent") if HAS_CTK else tk.Frame(root)
        wrap.pack(fill="both", expand=True, padx=12, pady=8)

        # -- 文件行 --
        row1 = ctk.CTkFrame(wrap, fg_color="transparent") if HAS_CTK else tk.Frame(wrap)
        row1.pack(fill="x", pady=(0, 8))
        self.file_label = self._label(row1, "未加载文件", 13, "#9aa3b5")
        self.file_label.pack(side="left", fill="x", expand=True)
        self._button(row1, "📂 打开 WAV / PCM", self._open_file).pack(side="right", padx=(8, 0))

        # -- 参数设置 --
        row2 = ctk.CTkFrame(wrap, corner_radius=10, fg_color="#1e222c") if HAS_CTK else tk.LabelFrame(wrap, text="参数")
        row2.pack(fill="x", pady=(0, 8))
        self.sr_var = tk.StringVar(value=cfg.get("samplerate", "44100"))
        self.bd_var = tk.StringVar(value=cfg.get("bit_depth", "16"))
        self.ch_var = tk.StringVar(value=cfg.get("channels", "1"))
        self.sr_combo = self._combo(row2, "采样率", SAMPLE_RATES, self.sr_var)
        self.bd_combo = self._combo(row2, "位深", BIT_DEPTHS, self.bd_var)
        self.ch_combo = self._combo(row2, "通道", CHANNELS, self.ch_var)
        self._button(row2, "按此参数重新解析", self._reparse).pack(side="left", padx=12, pady=10)
        self.info_label = self._label(row2, "", 12, "#8a93a6")
        self.info_label.pack(side="left", padx=8)

        # -- 波形 --
        self.canvas = tk.Canvas(wrap, height=120, bg="#171a21", highlightthickness=0)
        self.canvas.pack(fill="x", pady=(0, 8))
        self.canvas.bind("<Configure>", lambda _e: self._draw_wave())
        self.canvas.bind("<Button-1>", self._canvas_seek)

        # -- 进度条 --
        row3 = ctk.CTkFrame(wrap, fg_color="transparent") if HAS_CTK else tk.Frame(wrap)
        row3.pack(fill="x")
        self.time_label = self._label(row3, "00:00", 12)
        self.time_label.pack(side="left")
        self.slider = ctk.CTkSlider(row3, from_=0, to=1000, number_of_steps=1000,
                                    command=self._on_slider) if HAS_CTK else tk.Scale(row3, from_=0, to=1000, orient="horizontal", command=self._on_slider)
        self.slider.pack(side="left", fill="x", expand=True, padx=10)
        if HAS_CTK:
            self.slider.bind("<Button-1>", lambda _e: setattr(self, "_dragging", True))
            self.slider.bind("<ButtonRelease-1>", self._on_slider_release)
        self.dur_label = self._label(row3, "00:00", 12)
        self.dur_label.pack(side="right")

        # -- 控制按钮 --
        row4 = ctk.CTkFrame(wrap, fg_color="transparent") if HAS_CTK else tk.Frame(wrap)
        row4.pack(fill="x", pady=(10, 0))
        self.play_btn = self._button(row4, "▶ 播放", self._toggle_play, width=100)
        self.play_btn.pack(side="left", padx=(0, 8))
        self._button(row4, "⏹ 停止", self._stop, width=80).pack(side="left")
        self.dev_label = self._label(row4, "" if HAS_SD else "⚠ 未安装 sounddevice,无法播放(仍可解析波形)", 11, "#c8a04f")
        self.dev_label.pack(side="left", padx=16)

        if not HAS_NP:
            self._set_info("⚠ 未安装 numpy,请先 pip install numpy")

        self._draw_wave()

    # ---- 控件工厂(兼容降级) ----
    def _label(self, parent, text, size=12, color=None):
        if HAS_CTK:
            kw = {"font": ctk.CTkFont(size=size)}
            if color:
                kw["text_color"] = color
            return ctk.CTkLabel(parent, text=text, **kw)
        return tk.Label(parent, text=text)

    def _button(self, parent, text, cmd, width=None):
        if HAS_CTK:
            kw = {"command": cmd, "corner_radius": 8}
            if width:
                kw["width"] = width
            return ctk.CTkButton(parent, text=text, **kw)
        return tk.Button(parent, text=text, command=cmd)

    def _combo(self, parent, label, values, var):
        if HAS_CTK:
            f = ctk.CTkFrame(parent, fg_color="transparent")
            f.pack(side="left", padx=(12, 0), pady=10)
            ctk.CTkLabel(f, text=label, font=ctk.CTkFont(size=12),
                         text_color="#8a93a6").pack(anchor="w")
            cb = ctk.CTkComboBox(f, values=values, variable=var, width=100)
            cb.pack()
            return cb
        f = tk.Frame(parent)
        f.pack(side="left", padx=8)
        tk.Label(f, text=label).pack()
        cb = tk.OptionMenu(f, var, *values)
        cb.pack()
        return cb

    # ---- 文件 ----
    def _open_file(self):
        path = filedialog.askopenfilename(
            title="选择音频文件",
            filetypes=[("音频文件", "*.wav *.pcm *.raw"), ("WAV", "*.wav"),
                       ("原始 PCM", "*.pcm *.raw"), ("所有文件", "*.*")])
        if path:
            self._load_file(path)

    def _load_file(self, path: str):
        self._file_path = path
        p = Path(path)
        self.file_label.configure(text=f"🎵 {p.name}") if HAS_CTK else self.file_label.config(text=p.name)
        self._save_cfg()
        try:
            if p.suffix.lower() == ".wav":
                data, sr, ch, bd = read_wav(p)
                self.sr_var.set(str(sr)); self.ch_var.set(str(ch)); self.bd_var.set(str(bd))
                self.engine.load(data, sr, ch)
                self._set_info(f"WAV · {sr} Hz · {bd} bit · {ch} ch · {fmt_time(len(data)/sr)}")
            else:
                self._reparse()
                return
        except Exception as e:
            self._set_info(f"❌ 解析失败: {e}")
            self.log.error("load failed: %s", e)
            return
        self.log.info("loaded %s", path)
        self._draw_wave()
        self._update_time_ui()

    def _reparse(self):
        """按当前参数设置重新解析(用于 PCM 裸数据,或 WAV 参数改判)。"""
        if not self._file_path:
            self._set_info("请先打开文件")
            return
        if not HAS_NP:
            self._set_info("需要 numpy")
            return
        p = Path(self._file_path)
        try:
            sr = int(self.sr_var.get()); bd = int(self.bd_var.get()); ch = int(self.ch_var.get())
        except ValueError:
            self._set_info("参数必须是数字")
            return
        try:
            raw = p.read_bytes()
            if p.suffix.lower() == ".wav":
                with wave.open(str(p), "rb") as w:
                    raw = w.readframes(w.getnframes())
            data = pcm_to_float32(raw, bd, ch)
            self.engine.load(data, sr, ch)
            self._set_info(f"PCM · {sr} Hz · {bd} bit · {ch} ch · {fmt_time(self.engine.duration)}")
            self._save_cfg()
            self._draw_wave()
            self._update_time_ui()
        except Exception as e:
            self._set_info(f"❌ 解析失败: {e}")
            self.log.error("reparse failed: %s", e)

    def _save_cfg(self):
        self.env.update_config(samplerate=self.sr_var.get(),
                               bit_depth=self.bd_var.get(),
                               channels=self.ch_var.get())

    def _set_info(self, text):
        if HAS_CTK:
            self.info_label.configure(text=text)
        else:
            self.info_label.config(text=text)

    # ---- 波形 ----
    def _draw_wave(self):
        c = self.canvas
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        if w < 10 or not HAS_NP or self.engine.data is None:
            return
        data = self.engine.data
        mono = data.mean(axis=1) if data.ndim == 2 and data.shape[1] > 1 else data[:, 0]
        n = len(mono)
        step = max(1, n // w)
        idx = np.arange(0, n - step + 1, step)[:w]
        if len(idx) == 0:
            return
        peaks_max = np.maximum.reduceat(np.abs(mono), idx)
        ys = (h / 2 - peaks_max * (h / 2 - 4)).astype(int)
        mid = h // 2
        c.create_line(0, mid, w, mid, fill="#2a2f3a")
        # 已播放部分高亮
        played_x = int(self.engine.fraction * w)
        for x in range(len(idx)):
            col = "#4f8cff" if x <= played_x else "#3a4150"
            c.create_line(x, mid, x, ys[x], fill=col)

    def _canvas_seek(self, event):
        w = self.canvas.winfo_width()
        if w > 0 and self.engine.data is not None:
            self.engine.seek_fraction(event.x / w)
            self._draw_wave()
            self._update_time_ui()

    # ---- 进度条 ----
    def _on_slider(self, value):
        if self._dragging and self.engine.data is not None:
            v = float(value) / 1000.0
            self.engine.seek_fraction(v)
            self._draw_wave()
            self._update_time_ui()

    def _on_slider_release(self, _e):
        self._dragging = False

    def _update_time_ui(self):
        pos, dur = self.engine.position, self.engine.duration
        if HAS_CTK:
            self.time_label.configure(text=fmt_time(pos))
            self.dur_label.configure(text=fmt_time(dur))
            if not self._dragging:
                self.slider.set(self.engine.fraction * 1000)
        else:
            self.time_label.config(text=fmt_time(pos))
            self.dur_label.config(text=fmt_time(dur))

    # ---- 播放 ----
    def _toggle_play(self):
        if self.engine.data is None:
            self._set_info("请先加载文件")
            return
        if self.engine.is_playing:
            self.engine.pause()
            self._set_play_text(False)
        else:
            if self.engine.finished:
                self.engine.seek_fraction(0)
            if self.engine.play():
                self._set_play_text(True)
                self._start_tick()
            else:
                self._set_info("⚠ 无法打开音频输出设备(无声卡或未装 sounddevice)")

    def _set_play_text(self, playing: bool):
        text = "⏸ 暂停" if playing else "▶ 播放"
        if HAS_CTK:
            self.play_btn.configure(text=text)
        else:
            self.play_btn.config(text=text)

    def _start_tick(self):
        if self._tick_id:
            return
        def tick():
            self._tick_id = None
            self._update_time_ui()
            self._draw_wave()
            if self.engine.finished:
                self._set_play_text(False)
                self.engine.stop()
                self._update_time_ui()
                self._draw_wave()
                return
            if self.engine.is_playing:
                self._tick_id = self.canvas.after(200, tick)
        self._tick_id = self.canvas.after(200, tick)

    def _stop(self):
        self.engine.stop()
        self._set_play_text(False)
        self._update_time_ui()
        self._draw_wave()

    def on_close(self):
        self.engine.stop()
        self._save_cfg()
        self.log.info("audio player closed")
