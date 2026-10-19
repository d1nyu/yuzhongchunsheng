"""Visual system for the Yuzhong Chunsheng desktop app."""

from __future__ import annotations


BACKGROUND = "#F8F5F5"
CARD = "#FFFFFF"
RESULT_CARD = "#FFF9F8"
BORDER = "#ECE5E4"
TEXT = "#211D1E"
MUTED = "#786D6F"
FAINT = "#A09597"
ACCENT = "#D9364B"
ACCENT_DARK = "#AD1D33"
ACCENT_SOFT = "#FCEBEF"
GREEN = "#0FA968"
RED = "#D93A46"


APP_QSS = f"""
* {{
    font-family: "Microsoft YaHei UI", "Segoe UI", "PingFang SC";
    color: {TEXT};
    outline: none;
}}

QMainWindow, QWidget#Window {{
    background: {BACKGROUND};
}}

QWidget {{
    font-size: 13px;
}}

QLabel {{
    background: transparent;
}}

QLabel#AppName {{
    font-size: 25px;
    font-weight: 700;
    letter-spacing: 1px;
}}

QLabel#AppTagline {{
    font-size: 11px;
    color: {MUTED};
    letter-spacing: 0.5px;
}}

QLabel#PageTitle {{
    font-size: 17px;
    font-weight: 600;
}}

QLabel#CardTitle {{
    font-size: 14px;
    font-weight: 600;
}}

QLabel#Muted {{
    color: {MUTED};
}}

QLabel#Faint {{
    color: {FAINT};
    font-size: 11px;
}}

QLabel#Hint {{
    color: {MUTED};
    font-size: 12px;
}}

QLabel#ErrorText {{
    color: {RED};
}}

QLabel#Badge {{
    background: {ACCENT_SOFT};
    color: {ACCENT_DARK};
    border-radius: 7px;
    padding: 2px 8px;
    font-size: 10px;
    font-weight: 600;
}}

QLabel#ProviderBadge {{
    background: #F0F4FA;
    color: {MUTED};
    border-radius: 7px;
    padding: 2px 8px;
    font-size: 10px;
}}

QLabel#EnginePill {{
    background: {ACCENT_SOFT};
    color: {ACCENT_DARK};
    border: 1px solid #F0D3D9;
    border-radius: 11px;
    padding: 4px 10px;
    font-size: 11px;
    font-weight: 600;
}}

QLabel#SpeechEnginePill {{
    background: #F1F6F4;
    color: #247A59;
    border: 1px solid #DDEDE5;
    border-radius: 10px;
    padding: 3px 9px;
    font-size: 10px;
}}

QFrame#Card {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 17px;
}}

QFrame#ResultCard {{
    background: {RESULT_CARD};
    border: 1px solid #F0DBDE;
    border-radius: 17px;
}}

QFrame#VoiceStage {{
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 1,
        stop: 0 #FFFCFB,
        stop: 0.55 #FFF6F6,
        stop: 1 #FBECEF
    );
    border: 1px solid #F1DDE1;
    border-radius: 20px;
}}

QFrame#Separator {{
    background: {BORDER};
    max-height: 1px;
    min-height: 1px;
    border: none;
}}

QComboBox {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 8px 12px;
    min-height: 20px;
    selection-background-color: {ACCENT_SOFT};
    selection-color: {TEXT};
}}

QComboBox:hover {{
    border-color: #DFC8CC;
}}

QComboBox:focus {{
    border-color: #E7AAB6;
}}

QComboBox::drop-down {{
    border: none;
    width: 26px;
}}

QComboBox QAbstractItemView {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 5px;
    selection-background-color: {ACCENT_SOFT};
    selection-color: {TEXT};
    outline: none;
}}

QTextEdit {{
    background: transparent;
    border: none;
    padding: 2px 0;
    selection-background-color: #F7CBD3;
    selection-color: {TEXT};
}}

QTextEdit#SourceEdit {{
    font-size: 18px;
}}

QTextEdit#ResultEdit {{
    font-size: 18px;
    color: #3B2428;
}}

QTextEdit#VoiceSourceEdit {{
    font-size: 15px;
}}

QTextEdit#VoiceResultEdit {{
    font-size: 15px;
    color: #3B2428;
}}

QPushButton {{
    border: none;
    border-radius: 10px;
    padding: 7px 12px;
    background: transparent;
}}

QPushButton:hover {{
    background: #F8EEEE;
}}

QPushButton:pressed {{
    background: #F0E1E1;
}}

QPushButton#PrimaryButton {{
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 1,
        stop: 0 #E9505F,
        stop: 1 #C51F39
    );
    color: #FFFFFF;
    border-radius: 12px;
    padding: 0 26px;
    min-height: 44px;
    font-size: 14px;
    font-weight: 600;
}}

QPushButton#PrimaryButton:hover {{
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 1,
        stop: 0 #E24656,
        stop: 1 #B81A31
    );
}}

QPushButton#PrimaryButton:pressed {{
    background: #A91B30;
}}

QPushButton#PrimaryButton:disabled {{
    background: #E3BAC1;
    color: #FFF7F8;
}}

QPushButton#SecondaryButton {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 7px 13px;
    color: #4B3A3D;
}}

QPushButton#SecondaryButton:hover {{
    background: #FFFAFA;
    border-color: #E3C8CC;
}}

QPushButton#GhostButton {{
    color: {MUTED};
    padding: 6px 8px;
}}

QPushButton#GhostButton:hover {{
    color: {TEXT};
    background: #F8EEEE;
}}

QPushButton#ModeButton {{
    background: transparent;
    color: #7E7072;
    border-radius: 9px;
    padding: 7px 18px;
    font-size: 12px;
    font-weight: 600;
}}

QPushButton#ModeButton:hover {{
    color: #4B3236;
}}

QPushButton#ModeButton:checked {{
    background: {CARD};
    color: {ACCENT_DARK};
}}

QPushButton#IconButton {{
    background: transparent;
    border-radius: 9px;
    padding: 0;
}}

QPushButton#IconButton:hover {{
    background: #F8EEEE;
}}

QPushButton#SwapButton {{
    background: {ACCENT_SOFT};
    border: 1px solid #F0D1D8;
    border-radius: 17px;
}}

QPushButton#SwapButton:hover {{
    background: #F8D9DF;
}}

QPushButton#SettingsButton {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 12px;
    padding: 0;
}}

QPushButton#SettingsButton:hover {{
    background: #FFFAFA;
    border-color: #E3CACE;
}}

QFrame#ModeSwitch {{
    background: #F0E9E9;
    border-radius: 12px;
}}

QCheckBox {{
    spacing: 7px;
    color: {MUTED};
    font-size: 11px;
}}

QCheckBox:hover {{
    color: #5A4246;
}}

QCheckBox::indicator {{
    width: 30px;
    height: 17px;
    border-radius: 9px;
    background: #E4DADB;
    border: 1px solid #D8C9CB;
}}

QCheckBox::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
}}

QCheckBox::indicator:disabled {{
    background: #F0E8E8;
}}

QCheckBox::indicator:checked:disabled {{
    background: #E4C0C7;
    border-color: #DDB3BB;
}}

QCheckBox:disabled {{
    color: #B0A3A5;
}}

QLineEdit, QPlainTextEdit {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 9px;
    padding: 9px 11px;
    selection-background-color: #F7CBD3;
}}

QLineEdit:focus, QPlainTextEdit:focus {{
    border-color: #E7AAB6;
}}

QLineEdit:disabled {{
    background: #FAF6F6;
    color: #A99C9E;
}}

QDialog {{
    background: {BACKGROUND};
}}

QFrame#DialogCard {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 16px;
}}

QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 2px;
}}

QScrollBar::handle:vertical {{
    background: #D5C8CA;
    border-radius: 4px;
    min-height: 28px;
}}

QScrollBar::handle:vertical:hover {{
    background: #BFAEB1;
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent;
}}

QFrame#Toast {{
    background: #2A2022;
    border-radius: 11px;
}}

QFrame#Toast[kind="error"] {{
    background: #A92F39;
}}

QLabel#ToastText {{
    color: #FFFFFF;
    font-size: 12px;
}}

QToolTip {{
    background: #2A2022;
    color: #FFFFFF;
    border: none;
    padding: 6px 9px;
    border-radius: 6px;
}}
"""

