import json
from pathlib import Path

DESIGN_DIR = Path(__file__).resolve().parent.parent.parent / "design"
TOKENS_FILE = DESIGN_DIR / "design-tokens.json"

_tokens_cache = None


def load_tokens():
    global _tokens_cache
    if _tokens_cache is None:
        with open(TOKENS_FILE, "r") as f:
            _tokens_cache = json.load(f)
    return _tokens_cache


def _val(token):
    if isinstance(token, dict) and "$value" in token:
        return token["$value"]
    return token


def _color(tokens, *path):
    node = tokens["color"]
    for key in path:
        node = node[key]
    return _val(node)


def _prop(tokens, group, *path):
    node = tokens[group]
    for key in path:
        node = node[key]
    return _val(node)


def score_color(score: float) -> str:
    if score < 2:
        return _color(load_tokens(), "score", "bad")
    elif score < 3:
        return _color(load_tokens(), "score", "poor")
    elif score < 4:
        return _color(load_tokens(), "score", "fair")
    elif score < 4.5:
        return _color(load_tokens(), "score", "good")
    else:
        return _color(load_tokens(), "score", "excellent")


def score_grade(score: float) -> str:
    if score < 2:
        return "Bad"
    elif score < 3:
        return "Poor"
    elif score < 4:
        return "Fair"
    elif score < 4.5:
        return "Good"
    else:
        return "Excellent"


def score_description(score: float) -> str:
    if score < 2:
        return "噪音轰鸣"
    elif score < 3:
        return "勉强能听"
    elif score < 4:
        return "还行"
    elif score < 4.5:
        return "清晰舒服"
    else:
        return "纯净透亮"


def generate_qss() -> str:
    t = load_tokens()
    bg = _color(t, "base", "background")
    surface = _color(t, "base", "surface")
    elevated = _color(t, "base", "elevated")
    overlay = _color(t, "base", "overlay")
    glass_tint = _color(t, "glass", "tint")
    glass_border = _color(t, "glass", "border")
    txt_primary = _color(t, "text", "primary")
    txt_secondary = _color(t, "text", "secondary")
    txt_tertiary = _color(t, "text", "tertiary")
    accent_primary = _color(t, "accent", "primary")
    accent_secondary = _color(t, "accent", "secondary")
    accent_tertiary = _color(t, "accent", "tertiary")
    hover = _color(t, "interactive", "hover")
    active = _color(t, "interactive", "active")
    focus = _color(t, "interactive", "focus")
    disabled = _color(t, "interactive", "disabled")
    border_default = _color(t, "border", "default")
    border_muted = _color(t, "border", "muted")
    border_emphasis = _color(t, "border", "emphasis")
    font_default = "Helvetica Neue"
    font_mono = "Menlo"
    fs_xs = _prop(t, "typography", "fontSize", "xs")
    fs_sm = _prop(t, "typography", "fontSize", "sm")
    fs_md = _prop(t, "typography", "fontSize", "md")
    fs_lg = _prop(t, "typography", "fontSize", "lg")
    fs_xl = _prop(t, "typography", "fontSize", "xl")
    fw_light = _prop(t, "typography", "fontWeight", "light")
    fw_normal = _prop(t, "typography", "fontWeight", "normal")
    fw_medium = _prop(t, "typography", "fontWeight", "medium")
    fw_semibold = _prop(t, "typography", "fontWeight", "semibold")
    fw_bold = _prop(t, "typography", "fontWeight", "bold")
    rad_sm = _prop(t, "borderRadius", "sm")
    rad_md = _prop(t, "borderRadius", "md")
    rad_lg = _prop(t, "borderRadius", "lg")

    return f"""
QMainWindow {{
    background: {bg};
    color: {txt_primary};
    font-family: {font_default};
    font-size: {fs_md};
}}

QWidget {{
    background: {bg};
    color: {txt_primary};
    font-family: {font_default};
}}

QFrame#glassPanel {{
    background: {glass_tint};
    border: 1px solid {glass_border};
    border-radius: {rad_lg};
}}

QLabel {{
    color: {txt_primary};
    background: transparent;
    border: none;
}}

QLabel#secondary {{
    color: {txt_secondary};
}}

QLabel#tertiary {{
    color: {txt_tertiary};
}}

QLabel#accent {{
    color: {accent_primary};
}}

QPushButton {{
    background: {hover};
    color: {txt_primary};
    border: none;
    border-radius: {rad_sm};
    padding: 8px 16px;
    font-size: {fs_sm};
    font-weight: {fw_medium};
}}

QPushButton:hover {{
    background: {active};
}}

QPushButton:pressed {{
    background: {focus};
}}

QPushButton#ghost {{
    background: transparent;
    color: {txt_secondary};
    border: 1px solid {border_default};
}}

QPushButton#ghost:hover {{
    background: rgba(48,54,61,0.4);
    border-color: {border_emphasis};
}}

QLineEdit {{
    background: {elevated};
    color: {txt_primary};
    border: 1px solid {border_default};
    border-radius: {rad_sm};
    padding: 8px 12px;
    font-size: {fs_sm};
}}

QLineEdit:focus {{
    border-color: {accent_primary};
}}

QComboBox {{
    background: {elevated};
    color: {txt_primary};
    border: 1px solid {border_default};
    border-radius: {rad_sm};
    padding: 8px 12px;
    font-size: {fs_sm};
}}

QComboBox:focus {{
    border-color: {accent_primary};
}}

QComboBox::drop-down {{
    border: none;
    width: 20px;
}}

QComboBox QAbstractItemView {{
    background: {elevated};
    color: {txt_primary};
    border: 1px solid {border_default};
    selection-background-color: rgba(88,166,255,0.15);
    selection-color: {accent_primary};
}}

QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background: {border_emphasis};
    border-radius: 4px;
    min-height: 30px;
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QToolTip {{
    background: {elevated};
    color: {txt_primary};
    border: 1px solid {border_default};
    border-radius: {rad_sm};
    padding: 6px;
}}
"""
