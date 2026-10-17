"""界面主题：现代深色 + 圆角卡片风格（QSS）。"""

from __future__ import annotations

COLORS = {
    "bg": "#11141a",
    "surface": "#171b23",
    "surface_alt": "#1e232d",
    "border": "#2a3140",
    "text": "#e8ecf3",
    "text_dim": "#9aa5b6",
    "accent": "#4c8dff",
    "accent_hover": "#6ba1ff",
    "accent_press": "#357ae0",
    "success": "#3ddc97",
    "warning": "#ffb454",
    "danger": "#ff6b6b",
}

QSS = f"""
* {{
    font-family: "Microsoft YaHei UI", "Segoe UI", "PingFang SC", sans-serif;
    font-size: 13px;
    color: {COLORS['text']};
}}
QWidget#Root {{ background: {COLORS['bg']}; }}

QLabel#Title {{ font-size: 20px; font-weight: 600; }}
QLabel#Subtitle {{ color: {COLORS['text_dim']}; font-size: 12px; }}
QLabel#SectionTitle {{ font-size: 13px; font-weight: 600; color: {COLORS['text']}; }}
QLabel#Hint {{ color: {COLORS['text_dim']}; font-size: 12px; }}
QLabel#Value {{ color: {COLORS['accent']}; font-weight: 600; }}
QLabel#DropHint {{ color: {COLORS['text_dim']}; font-size: 13px; }}

QFrame#Card {{
    background: {COLORS['surface']};
    border: 1px solid {COLORS['border']};
    border-radius: 14px;
}}
QFrame#Divider {{ background: {COLORS['border']}; max-height: 1px; border: none; }}

QListWidget {{
    background: {COLORS['surface_alt']};
    border: 1px dashed {COLORS['border']};
    border-radius: 10px;
    padding: 6px;
    outline: none;
}}
QListWidget::item {{ padding: 7px 8px; border-radius: 7px; }}
QListWidget::item:selected {{ background: {COLORS['accent']}; color: #ffffff; }}
QListWidget::item:hover {{ background: #232a36; }}

QPushButton {{
    background: {COLORS['surface_alt']};
    border: 1px solid {COLORS['border']};
    border-radius: 9px;
    padding: 7px 14px;
}}
QPushButton:hover {{ background: #262d3a; border-color: #39435a; }}
QPushButton:pressed {{ background: #202634; }}
QPushButton:disabled {{ color: {COLORS['text_dim']}; background: #1a1f28; }}

QPushButton#Primary {{
    background: {COLORS['accent']};
    border: none;
    color: #ffffff;
    font-weight: 600;
    padding: 10px 22px;
    border-radius: 10px;
}}
QPushButton#Primary:hover {{ background: {COLORS['accent_hover']}; }}
QPushButton#Primary:pressed {{ background: {COLORS['accent_press']}; }}
QPushButton#Primary:disabled {{ background: #2b3444; color: {COLORS['text_dim']}; }}

QPushButton#Ghost {{ background: transparent; border: 1px solid {COLORS['border']}; }}

QComboBox, QSpinBox, QLineEdit {{
    background: {COLORS['surface_alt']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    padding: 6px 9px;
    min-height: 18px;
}}
QComboBox:hover, QSpinBox:hover, QLineEdit:hover {{ border-color: #39435a; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background: {COLORS['surface_alt']};
    border: 1px solid {COLORS['border']};
    selection-background-color: {COLORS['accent']};
    outline: none;
}}
QSpinBox::up-button, QSpinBox::down-button {{ width: 16px; border: none; background: transparent; }}

QSlider::groove:horizontal {{ height: 5px; background: #2a3140; border-radius: 3px; }}
QSlider::sub-page:horizontal {{ background: {COLORS['accent']}; border-radius: 3px; }}
QSlider::handle:horizontal {{
    background: #ffffff; border: 2px solid {COLORS['accent']};
    width: 13px; height: 13px; margin: -6px 0; border-radius: 8px;
}}
QSlider::handle:horizontal:hover {{ background: {COLORS['accent_hover']}; }}

QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px; border-radius: 5px;
    border: 1px solid {COLORS['border']}; background: {COLORS['surface_alt']};
}}
QCheckBox::indicator:checked {{ background: {COLORS['accent']}; border-color: {COLORS['accent']}; }}
QCheckBox::indicator:hover {{ border-color: {COLORS['accent']}; }}

QProgressBar {{
    background: {COLORS['surface_alt']};
    border: none; border-radius: 7px;
    height: 14px; text-align: center;
    color: {COLORS['text_dim']}; font-size: 11px;
}}
QProgressBar::chunk {{ background: {COLORS['accent']}; border-radius: 7px; }}

QPlainTextEdit {{
    background: #0d1016;
    border: 1px solid {COLORS['border']};
    border-radius: 10px;
    padding: 8px;
    color: {COLORS['text_dim']};
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 12px;
}}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #333c4d; border-radius: 5px; min-height: 28px; }}
QScrollBar::handle:vertical:hover {{ background: #445066; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; }}
QScrollBar::handle:horizontal {{ background: #333c4d; border-radius: 5px; min-width: 28px; }}

QToolTip {{
    background: {COLORS['surface_alt']};
    border: 1px solid {COLORS['border']};
    border-radius: 6px; padding: 6px 8px; color: {COLORS['text']};
}}
"""

#: 质量档位下拉的显示文案
LEVEL_LABELS = (
    "0 · 极致压缩（72 dpi / 质量 45）",
    "1 · 强压缩（96 dpi / 质量 55）",
    "2 · 推荐（120 dpi / 质量 70）",
    "3 · 轻压缩（150 dpi / 质量 85）",
    "4 · 高质量（300 dpi / 质量 95）",
    "5 · 近无损（600 dpi / 质量 100）",
    "6 · 仅清理（1200 dpi / 质量 100）",
)
CUSTOM_LABEL = "自定义参数"
