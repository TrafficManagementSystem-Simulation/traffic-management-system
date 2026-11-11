"""Accessibility audit (Likhita): TMS-NF-004, test case TC-UX-01 (WCAG 2.1 AA, the checks a script can do).

Page structure is checked on every page of the console. Colour contrast is calculated from the style sheet
for both the light and the dark theme. Manual checks (screen reader, keyboard walk) are in docs/accessibility.md.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

from tms.ui.routes import PAGES

CSS = Path(__file__).resolve().parents[3] / "src" / "tms" / "ui" / "static" / "style.css"
PATHS = [path for path, _title, _template in PAGES]


class Audit(HTMLParser):
    def __init__(self):
        super().__init__()
        self.lang = self.title = None
        self.in_title = False
        self.ids, self.labelled_for, self.fields, self.problems = set(), set(), [], []
        self.stack, self.headings, self.landmarks = [], [], set()
        self.first_focusable = None
        self.button_text, self.in_button, self.button_attrs = "", False, {}
        self.tables = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self.stack.append(tag)
        if tag == "html":
            self.lang = a.get("lang")
        if tag == "title":
            self.in_title = True
        if "id" in a:
            self.ids.add(a["id"])
        if tag in ("main", "nav", "header"):
            self.landmarks.add(tag)
        if tag == "label" and a.get("for"):
            self.labelled_for.add(a["for"])
        if tag in ("input", "select", "textarea") and a.get("type") != "hidden":
            wrapped = "label" in self.stack
            self.fields.append((tag, a.get("id"), wrapped or bool(a.get("aria-label")) or bool(a.get("aria-labelledby"))))
        if tag == "img" and "alt" not in a:
            self.problems.append("img without alt")
        if a.get("tabindex") not in (None, "0", "-1"):
            self.problems.append(f"positive tabindex on {tag}")
        if tag in ("a", "button", "input", "select", "textarea") and self.first_focusable is None and a.get("type") != "hidden":
            self.first_focusable = a.get("href") if tag == "a" else tag
        if tag in ("h1", "h2", "h3", "h4"):
            self.headings.append(int(tag[1]))
        if tag == "button":
            self.in_button, self.button_text, self.button_attrs = True, "", a
        if tag == "th":
            self.tables.append(a.get("scope"))
        if tag == "a" and not a.get("href"):
            self.problems.append("a without href")

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        if tag == "button" and self.in_button:
            self.in_button = False
            if not (self.button_text.strip() or self.button_attrs.get("aria-label")):
                self.problems.append("button without a name")
        while self.stack and self.stack.pop() != tag:
            pass

    def handle_data(self, data):
        if self.in_title:
            self.title = (self.title or "") + data
        if self.in_button:
            self.button_text += data


@pytest.fixture(scope="module", params=PATHS)
def audit(request):
    from fastapi.testclient import TestClient
    from tms.common.config import Settings
    from tms.main import create_app

    with TestClient(create_app(Settings(database_url="sqlite://", autotick=False))) as client:
        page = Audit()
        page.feed(client.get(request.param).text)
        page.path = request.param
        return page


def test_language_title_and_landmarks(audit):
    assert audit.lang == "en"
    assert audit.title and audit.title.strip()
    assert {"main", "nav", "header"} <= audit.landmarks


def test_keyboard_users_can_skip_the_navigation(audit):
    assert audit.first_focusable == "#main" and "main" in audit.ids


def test_every_field_has_a_label(audit):
    for tag, field_id, named in audit.fields:
        assert named or field_id in audit.labelled_for, f"{audit.path}: unlabelled {tag} {field_id}"


def test_headings_do_not_skip_levels(audit):
    levels = audit.headings
    assert levels and levels[0] == 1
    for previous, current in zip(levels, levels[1:]):
        assert current <= previous + 1, f"{audit.path}: h{previous} then h{current}"


def test_table_headers_say_whether_they_are_for_columns_or_rows(audit):
    assert all(scope in ("col", "row") for scope in audit.tables), audit.path


def test_no_other_structural_problems(audit):
    assert audit.problems == []


# ---------- colour contrast (WCAG 1.4.3 text 4.5:1, 1.4.11 controls and borders 3:1) ----------

def _theme_blocks():
    css = CSS.read_text()
    light = re.search(r":root\s*\{([^}]*)\}", css).group(1)
    dark = re.search(r"prefers-color-scheme:\s*dark\)\s*\{\s*:root\s*\{([^}]*)\}", css).group(1)
    parse = lambda block: dict(re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{6})", block))
    return {"light": parse(light), "dark": {**parse(light), **parse(dark)}}


def _luminance(hex_color):
    channels = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(first, second):
    high, low = sorted((_luminance(first), _luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_text_colours_meet_4_5_to_1(theme):
    c = _theme_blocks()[theme]
    pairs = [("text", "bg"), ("text", "panel"), ("muted", "bg"), ("muted", "panel"), ("accent-text", "accent"),
             ("accent", "bg"), ("good", "bg"), ("warn", "bg"), ("bad", "bg"), ("good", "panel"), ("warn", "panel"), ("bad", "panel")]
    for foreground, background in pairs:
        assert contrast(c[foreground], c[background]) >= 4.5, f"{theme}: {foreground} on {background} = {contrast(c[foreground], c[background]):.2f}"


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_borders_and_focus_ring_meet_3_to_1(theme):
    c = _theme_blocks()[theme]
    assert contrast(c["line"], c["bg"]) >= 3.0
    assert contrast(c["accent"], c["bg"]) >= 3.0           # the focus outline uses the accent colour
