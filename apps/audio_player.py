"""
音频播放器 —— 播放 WAV / 原始 PCM 数据。

特性:
  · WAV:自动解析头部(采样率/位深/通道)
  · PCM 裸数据:手动设置采样率、位深(8/16/24/32)、通道数
  · 可拖动进度条 seek
  · 波形显示(QPainter 绘制,点击波形可跳转)
  · 播放引擎基于 sounddevice;未安装或无声卡时自动降级(仍可解析/看波形)
"""
from __future__ import annotations

import threading
import wave
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QVBoxLayout, QWidget,
)

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
        if self.finished:      # 播完后再点播放:从头开始(复用旧流时也要回卷)
            self.seek_fraction(0)
        if self._stream is not None:
            self._stream.start()
            return True
        try:
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
        # 注意:流播到末尾不会自动停(回调持续输出静音),不能用 is_playing 判断
        return self.data is not None and len(self.data) > 0 and self._pos >= len(self.data)


# ---------------- 波形控件 ----------------

class WaveformWidget(QWidget):
    """波形显示:峰值竖线绘制,已播放部分高亮,点击跳转。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(120)
        self.setMinimumWidth(100)
        self.setCursor(Qt.PointingHandCursor)
        self._peaks = None        # numpy:每像素峰值幅度 0~1
        self._fraction = 0.0
        self.on_seek = None       # 回调: on_seek(fraction)
        self.on_resize = None     # 回调: 宽度变化后重算峰值

    def set_peaks(self, peaks):
        self._peaks = peaks
        self.update()

    def set_fraction(self, frac: float):
        self._fraction = frac
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.fillRect(self.rect(), _BG)
        w, h = self.width(), self.height()
        mid = h // 2
        p.fillRect(0, mid, w, 1, _LINE_MID)
        if self._peaks is None or len(self._peaks) == 0 or w < 10:
            p.end()
            return
        peaks = self._peaks
        n = min(len(peaks), w)
        played_x = int(self._fraction * w)
        amp = h / 2 - 4
        for x in range(n):
            yv = int(mid - float(peaks[x]) * amp)
            p.fillRect(x, yv, 1, mid - yv, _PLAYED if x <= played_x else _UNPLAYED)
        p.end()

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton and self.width() > 0 and self.on_seek:
            self.on_seek(max(0.0, min(1.0, ev.position().x() / self.width())))

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        if self.on_resize:
            self.on_resize()


_BG = QColor("#171a21")
_LINE_MID = QColor("#2a2f3a")
_PLAYED = QColor("#4f8cff")
_UNPLAYED = QColor("#3a4150")


def _clear_bg(widget: QWidget) -> None:
    """容器自身背景透明,但用 objectName 选择器限定作用范围。

    直接用 setStyleSheet("background: transparent;")(无选择器)会级联到
    所有子控件并覆盖应用级 QSS——按钮/下拉框会变透明,hover/pressed
    反馈全部失效。Qt 作用域规则:父控件样式表优先于应用样式表。
    """
    widget.setObjectName("apClearBg")
    widget.setStyleSheet("QWidget#apClearBg { background: transparent; }")


# ---------------- UI ----------------

class AudioPlayerApp(ToolApp):
    def build(self, root: QWidget) -> None:
        self.engine = PlaybackEngine()
        self._file_path: str | None = None
        cfg = self.env.get_config({"samplerate": "44100", "bit_depth": "16", "channels": "1"})

        wrap = QWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(12, 8, 12, 8)
        outer.addWidget(wrap)

        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        # -- 文件行 --
        row1 = QWidget()
        _clear_bg(row1)
        r1 = QHBoxLayout(row1)
        r1.setContentsMargins(0, 0, 0, 0)
        self.file_label = QLabel("未加载文件")
        self.file_label.setStyleSheet("color: #9aa3b5; font-size: 13px;")
        r1.addWidget(self.file_label, 1)
        open_btn = QPushButton("📂 打开 WAV / PCM")
        open_btn.clicked.connect(self._open_file)
        r1.addWidget(open_btn)
        lay.addWidget(row1)

        # -- 参数设置(网格对齐:第一行标签,第二行下拉,按钮/信息与下拉底对齐) --
        row2 = QFrame()
        row2.setObjectName("panel")
        r2 = QGridLayout(row2)
        r2.setContentsMargins(12, 10, 12, 10)
        r2.setHorizontalSpacing(12)
        r2.setVerticalSpacing(4)
        self.sr_combo = self._combo(r2, 0, "采样率", SAMPLE_RATES, cfg.get("samplerate", "44100"))
        self.bd_combo = self._combo(r2, 1, "位深", BIT_DEPTHS, cfg.get("bit_depth", "16"))
        self.ch_combo = self._combo(r2, 2, "通道", CHANNELS, cfg.get("channels", "1"))
        reparse_btn = QPushButton("按此参数重新解析")
        reparse_btn.clicked.connect(self._reparse)
        r2.addWidget(reparse_btn, 0, 3, Qt.AlignBottom)
        self.info_label = QLabel("")
        self.info_label.setStyleSheet("color: #8a93a6; font-size: 12px;")
        r2.addWidget(self.info_label, 0, 4, Qt.AlignBottom | Qt.AlignLeft)
        r2.setColumnStretch(4, 1)
        lay.addWidget(row2)

        # -- 波形 --
        self.wave = WaveformWidget()
        self.wave.on_seek = self._wave_seek
        self.wave.on_resize = self._update_wave_peaks
        lay.addWidget(self.wave)

        # -- 进度条 --
        row3 = QWidget()
        _clear_bg(row3)
        r3 = QHBoxLayout(row3)
        r3.setContentsMargins(0, 0, 0, 0)
        self.time_label = QLabel("00:00")
        r3.addWidget(self.time_label)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 1000)
        self.slider.sliderMoved.connect(self._on_slider_move)
        self.slider.sliderReleased.connect(self._on_slider_release)
        r3.addWidget(self.slider, 1)
        self.dur_label = QLabel("00:00")
        r3.addWidget(self.dur_label)
        lay.addWidget(row3)

        # -- 控制按钮 --
        row4 = QWidget()
        _clear_bg(row4)
        r4 = QHBoxLayout(row4)
        r4.setContentsMargins(0, 0, 0, 0)
        r4.setSpacing(8)
        self.play_btn = QPushButton("▶ 播放")
        self.play_btn.setFixedWidth(100)
        self.play_btn.clicked.connect(self._toggle_play)
        r4.addWidget(self.play_btn)
        stop_btn = QPushButton("⏹ 停止")
        stop_btn.setFixedWidth(80)
        stop_btn.clicked.connect(self._stop)
        r4.addWidget(stop_btn)
        self.dev_label = QLabel(
            "" if HAS_SD else "⚠ 未安装 sounddevice,无法播放(仍可解析波形)")
        self.dev_label.setStyleSheet("color: #c8a04f; font-size: 11px;")
        r4.addWidget(self.dev_label)
        r4.addStretch(1)
        lay.addWidget(row4)

        self._dragging = False
        self._tick = QTimer(wrap)
        self._tick.setInterval(200)
        self._tick.timeout.connect(self._tick_update)

        if not HAS_NP:
            self._set_info("⚠ 未安装 numpy,请先 pip install numpy")

    def _combo(self, grid, col, label, values, current):
        box = QWidget()
        _clear_bg(box)
        vl = QVBoxLayout(box)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(2)
        lab = QLabel(label)
        lab.setStyleSheet("color: #8a93a6; font-size: 12px;")
        vl.addWidget(lab)
        cb = QComboBox()
        cb.addItems(values)
        cb.setMinimumWidth(100)
        cb.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        if current in values:
            cb.setCurrentText(current)
        vl.addWidget(cb)
        grid.addWidget(box, 0, col, Qt.AlignBottom)
        return cb

    # ---- 文件 ----
    def _halt_playback(self):
        """数据将变更(加载/重解析)时:停止流和计时器,按钮回到"播放",进度归零。"""
        self.engine.stop()
        self._tick.stop()
        self._dragging = False
        self._set_play_text(False)
        self.slider.setValue(0)
        self.wave.set_fraction(0.0)

    def _open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self.wave.window(), "选择音频文件", "",
            "音频文件 (*.wav *.pcm *.raw);;WAV (*.wav);;原始 PCM (*.pcm *.raw);;所有文件 (*)")
        if path:
            self._load_file(path)

    def _load_file(self, path: str):
        self._file_path = path
        self._halt_playback()
        p = Path(path)
        self.file_label.setText(f"🎵 {p.name}")
        self._save_cfg()
        try:
            if p.suffix.lower() == ".wav":
                data, sr, ch, bd = read_wav(p)
                self.sr_combo.setCurrentText(str(sr))
                self.ch_combo.setCurrentText(str(ch))
                self.bd_combo.setCurrentText(str(bd))
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
        self._update_wave_peaks()
        self._update_time_ui()

    def _reparse(self):
        """按当前参数设置重新解析(用于 PCM 裸数据,或 WAV 参数改判)。"""
        if not self._file_path:
            self._set_info("请先打开文件")
            return
        if not HAS_NP:
            self._set_info("需要 numpy")
            return
        self._halt_playback()
        p = Path(self._file_path)
        try:
            sr = int(self.sr_combo.currentText())
            bd = int(self.bd_combo.currentText())
            ch = int(self.ch_combo.currentText())
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
            self._update_wave_peaks()
            self._update_time_ui()
        except Exception as e:
            self._set_info(f"❌ 解析失败: {e}")
            self.log.error("reparse failed: %s", e)

    def _save_cfg(self):
        self.env.update_config(samplerate=self.sr_combo.currentText(),
                               bit_depth=self.bd_combo.currentText(),
                               channels=self.ch_combo.currentText())

    def _set_info(self, text):
        self.info_label.setText(text)

    # ---- 波形 ----
    def _update_wave_peaks(self):
        """按当前控件宽度重算峰值;宽度变化时也会重算(paintEvent 只做绘制)。"""
        if not HAS_NP or self.engine.data is None:
            self.wave.set_peaks(None)
            return
        data = self.engine.data
        mono = data.mean(axis=1) if data.ndim == 2 and data.shape[1] > 1 else data[:, 0]
        n = len(mono)
        w = max(self.wave.width(), 100)
        step = max(1, n // w)
        idx = np.arange(0, n - step + 1, step)
        if len(idx) == 0:
            self.wave.set_peaks(None)
            return
        peaks = np.maximum.reduceat(np.abs(mono), idx)
        self.wave.set_peaks(peaks)
        self.wave.set_fraction(self.engine.fraction)

    def _wave_seek(self, frac: float):
        self.engine.seek_fraction(frac)
        self.wave.set_fraction(self.engine.fraction)
        self._update_time_ui()

    # ---- 进度条 ----
    def _on_slider_move(self, value: int):
        self._dragging = True
        if self.engine.data is not None:
            self.engine.seek_fraction(value / 1000.0)
            self.wave.set_fraction(self.engine.fraction)
            self._update_time_ui()

    def _on_slider_release(self):
        self._dragging = False

    def _update_time_ui(self):
        pos, dur = self.engine.position, self.engine.duration
        self.time_label.setText(fmt_time(pos))
        self.dur_label.setText(fmt_time(dur))
        if not self._dragging:
            self.slider.setValue(int(self.engine.fraction * 1000))
        self.wave.set_fraction(self.engine.fraction)

    # ---- 播放 ----
    def _toggle_play(self):
        if self.engine.data is None:
            self._set_info("请先加载文件")
            return
        if self.engine.is_playing:
            self.engine.pause()
            self._set_play_text(False)
            self._tick.stop()
        else:
            if self.engine.finished:
                self.engine.seek_fraction(0)
            if self.engine.play():
                self._set_play_text(True)
                self._tick.start()
            else:
                self._set_info("⚠ 无法打开音频输出设备(无声卡或未装 sounddevice)")

    def _set_play_text(self, playing: bool):
        self.play_btn.setText("⏸ 暂停" if playing else "▶ 播放")

    def _tick_update(self):
        self._update_time_ui()
        if self.engine.finished:
            self._set_play_text(False)
            self.engine.stop()
            self._update_time_ui()
            self._tick.stop()

    def _stop(self):
        self.engine.stop()
        self._tick.stop()
        self._set_play_text(False)
        self._update_time_ui()

    def on_close(self):
        self.engine.stop()
        self._save_cfg()
        self.log.info("audio player closed")
