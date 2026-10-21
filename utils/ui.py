"""
LifeLink design system: global CSS and small reusable HTML components.

Palette (from the brand brief)
  page #F6F8F2 · card #FFFFFF · pale blue #EAF5FB · mint #DDEFE4 · ivory #FFFDF7
  ocean #2878B8 (hover #21679D) · sage #527C67 · teal #75B9B4
  headings #29445A · body #475569 · secondary text #66756D · border #E3EAE3
  amber #FFF1C7 · restrained urgent accent #C96B62
"""

from __future__ import annotations

import base64
import html
from pathlib import Path

import streamlit as st

from config.constants import BRAND_NAME, BRAND_TAGLINE, EMERGENCY_NUMBER_IN

ASSETS = Path(__file__).resolve().parent.parent / "assets"

# ── Icons (24×24 outline paths) ──────────────────────────────────────────────
_ICONS = {
    "heart": "M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z",
    "drop": "M12 22a7 7 0 0 0 7-7c0-2-1-3.9-3-5.5s-3.5-4-4-6.5c-.5 2.5-2 4.9-4 6.5C6 11.1 5 13 5 15a7 7 0 0 0 7 7z",
    "users": "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2 M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z M22 21v-2a4 4 0 0 0-3-3.87 M16 3.13a4 4 0 0 1 0 7.75",
    "userplus": "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2 M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z M19 8v6 M22 11h-6",
    "search": "M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16z M21 21l-4.3-4.3",
    "link": "M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71 M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71",
    "shield": "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z",
    "check": "M22 11.08V12a10 10 0 1 1-5.93-9.14 M22 4 12 14.01l-3-3",
    "pin": "M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 0 1 16 0z M12 13a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
    "chat": "M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z",
    "chart": "M18 20V10 M12 20V4 M6 20v-6",
    "lock": "M5 11h14v10H5z M8 11V7a4 4 0 0 1 8 0v4",
    "clock": "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z M12 6v6l4 2",
    "file": "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6 M8 13h8 M8 17h8",
    "alert": "M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z M12 9v4 M12 17h.01",
    "info": "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z M12 16v-4 M12 8h.01",
    "eyeoff": "M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94 M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19 M1 1l22 22",
    "activity": "M22 12h-4l-3 9L9 3l-3 9H2",
}


def icon(name: str, size: int = 20, color: str = "currentColor") -> str:
    path = _ICONS.get(name, _ICONS["heart"])
    paths = []
    for i, p in enumerate(path.split(" M")):
        paths.append(f'<path d="{p if i == 0 else "M" + p}"/>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" '
            f'fill="none" stroke="{color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" '
            f'aria-hidden="true">{"".join(paths)}</svg>')


def fmt_dt(value, fmt: str = "%d %b %Y, %I:%M %p") -> str:
    """Format a datetime in Indian Standard Time (stored values are UTC)."""
    import datetime as _dt
    from zoneinfo import ZoneInfo
    if not isinstance(value, _dt.datetime):
        return "—"
    return value.astimezone(ZoneInfo("Asia/Kolkata")).strftime(fmt)


def esc(value) -> str:
    return html.escape(str(value if value is not None else ""))


def _html(block: str) -> str:
    """Flatten an HTML block so Markdown never mistakes indentation for a code block."""
    return "\n".join(line.strip() for line in block.splitlines() if line.strip())


def render(block: str) -> None:
    st.markdown(_html(block), unsafe_allow_html=True)


def _data_uri(filename: str) -> str:
    raw = (ASSETS / filename).read_bytes()
    return "data:image/svg+xml;base64," + base64.b64encode(raw).decode()


# ── Global CSS ───────────────────────────────────────────────────────────────
_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
:root{
  --bg:#F6F8F2; --card:#FFFFFF; --blue-soft:#EAF5FB; --mint:#DDEFE4; --ivory:#FFFDF7;
  --ocean:#2878B8; --ocean-hover:#21679D; --sage:#527C67; --teal:#75B9B4;
  --head:#29445A; --body:#475569; --muted:#66756D; --border:#E3EAE3;
  --amber:#FFF1C7; --urgent:#C96B62; --urgent-soft:#F7E4E1;
  --shadow:0 1px 2px rgba(41,68,90,.04),0 6px 20px rgba(41,68,90,.06);
}
html,body,.stApp,[data-testid="stAppViewContainer"],button,input,textarea,select{
  font-family:'Inter','Segoe UI',system-ui,-apple-system,Roboto,Arial,sans-serif;
}
.stApp{background:var(--bg);color:var(--body);}
[data-testid="stHeader"]{background:transparent;}
#MainMenu,footer,[data-testid="stToolbar"] [data-testid="stMainMenu"]{visibility:hidden;}
.block-container{max-width:1160px;padding:2.2rem 2rem 3rem;}
h1,h2,h3,h4{color:var(--head);letter-spacing:-.01em;font-weight:700;}
p,li,label,[data-testid="stMarkdownContainer"]{color:var(--body);}
a{color:var(--ocean);}
:focus-visible{outline:3px solid rgba(40,120,184,.45)!important;outline-offset:2px;border-radius:8px;}

/* ── sidebar ── */
[data-testid="stSidebar"]{background:var(--ivory);border-right:1px solid var(--border);}
[data-testid="stSidebarNavLink"]{border-radius:12px;padding:.55rem .8rem;margin:2px 0;color:var(--head);font-weight:500;}
[data-testid="stSidebarNavLink"]:hover{background:var(--blue-soft);}
[data-testid="stSidebarNavLink"][aria-current="page"]{background:var(--mint);color:var(--sage);font-weight:700;}
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"]{border-radius:12px;padding:.55rem .8rem;margin:2px 0;color:var(--head);font-weight:500;}
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"]:hover{background:var(--blue-soft);}
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"][aria-current="page"]{background:var(--mint);color:var(--sage);font-weight:700;}
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"] p{color:inherit;}
[data-testid="stSidebar"] hr{border-color:var(--border);}
.ll-side-note{font-size:.82rem;color:var(--muted);line-height:1.5;padding:.2rem .4rem;}

/* ── buttons ── */
.stButton>button,.stFormSubmitButton>button,.stDownloadButton>button,[data-testid="stBaseButton-secondary"],[data-testid="stBaseButton-primary"],[data-testid="stBaseButton-secondaryFormSubmit"],[data-testid="stBaseButton-primaryFormSubmit"]{
  border-radius:999px;font-weight:600;min-height:2.9rem;padding:.55rem 1.4rem;transition:background .15s,border-color .15s,color .15s;
}
[data-testid="stBaseButton-primary"],[data-testid="stBaseButton-primaryFormSubmit"]{background:var(--ocean);border:1px solid var(--ocean);color:#fff;}
[data-testid="stBaseButton-primary"]:hover,[data-testid="stBaseButton-primaryFormSubmit"]:hover{background:var(--ocean-hover);border-color:var(--ocean-hover);color:#fff;}
[data-testid="stBaseButton-secondary"],[data-testid="stBaseButton-secondaryFormSubmit"]{background:transparent;border:1.5px solid var(--ocean);color:var(--ocean);}
[data-testid="stBaseButton-secondary"]:hover,[data-testid="stBaseButton-secondaryFormSubmit"]:hover{background:var(--blue-soft);border-color:var(--ocean-hover);color:var(--ocean-hover);}

[data-testid="stBaseButton-primary"] p,[data-testid="stBaseButton-primaryFormSubmit"] p,[data-testid="stBaseButton-primary"] span,[data-testid="stBaseButton-primaryFormSubmit"] span{color:#fff!important;}
[data-testid="stBaseButton-secondary"] p,[data-testid="stBaseButton-secondaryFormSubmit"] p{color:var(--ocean)!important;}
.st-key-banner [data-testid="stBaseButton-primary"] p{color:var(--sage)!important;}
.st-key-banner [data-testid="stBaseButton-secondary"] p{color:#fff!important;}
/* ── inputs ── */
[data-baseweb="input"],[data-baseweb="select"]>div,[data-baseweb="textarea"],.stNumberInput [data-baseweb="input"]{border-radius:12px!important;background:#fff!important;border-color:var(--border)!important;}
[data-baseweb="input"]:focus-within,[data-baseweb="textarea"]:focus-within,[data-baseweb="select"]>div:focus-within{border-color:var(--ocean)!important;box-shadow:0 0 0 3px rgba(40,120,184,.15)!important;}
input,textarea{color:var(--head)!important;}
[data-testid="stWidgetLabel"] p{color:var(--head);font-weight:600;font-size:.92rem;}

/* ── forms & containers as cards ── */
[data-testid="stForm"]{background:var(--card);border:1px solid var(--border);border-radius:22px;padding:1.6rem 1.7rem;box-shadow:var(--shadow);}
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"] .ll-resultcard){background:var(--card);border:1px solid var(--border)!important;border-radius:18px;box-shadow:var(--shadow);}
[data-testid="stExpander"]{background:var(--card);border:1px solid var(--border);border-radius:14px;}
[data-testid="stMetric"]{background:var(--card);border:1px solid var(--border);border-radius:16px;padding:.9rem 1.1rem;box-shadow:var(--shadow);}
[data-testid="stMetricLabel"] p{color:var(--muted);font-weight:500;}
[data-testid="stMetricValue"]{color:var(--head);font-weight:700;}
[data-testid="stAlert"]{border-radius:14px;}
[data-testid="stDataFrame"]{border:1px solid var(--border);border-radius:14px;overflow:hidden;}
.stTabs [data-baseweb="tab-list"]{gap:.4rem;border-bottom:1px solid var(--border);}
.stTabs [data-baseweb="tab"]{border-radius:10px 10px 0 0;color:var(--muted);font-weight:600;padding:.6rem 1rem;}
.stTabs [aria-selected="true"]{color:var(--ocean);}
.stTabs [data-baseweb="tab-highlight"]{background:var(--ocean);}

/* ── chat ── */
[data-testid="stChatMessage"]{border-radius:18px;padding:.9rem 1.1rem;margin:.35rem 0;border:1px solid var(--border);background:var(--mint);}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]),[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]){background:var(--blue-soft);}
[data-testid="stChatInput"]{border-radius:18px;}

/* ── custom components ── */
.ll-pagehead{display:flex;gap:1rem;align-items:center;margin:0 0 1.4rem;}
.ll-pagehead .chip{width:52px;height:52px;border-radius:16px;background:var(--mint);color:var(--sage);display:grid;place-items:center;flex:none;}
.ll-pagehead h1{margin:0;font-size:1.9rem;line-height:1.2;}
.ll-pagehead p{margin:.2rem 0 0;color:var(--muted);font-size:1rem;}
.ll-card{background:var(--card);border:1px solid var(--border);border-radius:20px;padding:1.4rem 1.5rem;box-shadow:var(--shadow);height:100%;}
.ll-card h3{margin:.7rem 0 .35rem;font-size:1.08rem;}
.ll-card p{margin:0;font-size:.95rem;line-height:1.6;}
.ll-card .chip{width:44px;height:44px;border-radius:14px;display:grid;place-items:center;background:var(--blue-soft);color:var(--ocean);}
.ll-card .chip.sage{background:var(--mint);color:var(--sage);}
.ll-card.ivory{background:var(--ivory);}
.ll-grid{display:grid;gap:1.1rem;}
.ll-grid.c4{grid-template-columns:repeat(4,1fr);} .ll-grid.c3{grid-template-columns:repeat(3,1fr);} .ll-grid.c2{grid-template-columns:repeat(2,1fr);}
.ll-stat{background:var(--card);border:1px solid var(--border);border-radius:20px;padding:1.2rem 1.3rem;box-shadow:var(--shadow);display:flex;gap:.9rem;align-items:center;}
.ll-stat .chip{width:46px;height:46px;border-radius:14px;display:grid;place-items:center;flex:none;background:var(--blue-soft);color:var(--ocean);}
.ll-stat .chip.sage{background:var(--mint);color:var(--sage);}
.ll-stat b{display:block;font-size:1.75rem;line-height:1.1;color:var(--head);font-weight:800;}
.ll-stat span{font-size:.88rem;color:var(--muted);}
.ll-step{position:relative;}
.ll-step .num{width:34px;height:34px;border-radius:50%;background:var(--ocean);color:#fff;font-weight:700;display:grid;place-items:center;font-size:.95rem;}
.ll-step h3{margin:.8rem 0 .3rem;font-size:1.05rem;} .ll-step p{margin:0;font-size:.93rem;line-height:1.6;}
.ll-pill{display:inline-flex;align-items:center;gap:.35rem;padding:.2rem .7rem;border-radius:999px;font-size:.8rem;font-weight:600;line-height:1.5;white-space:nowrap;}
.ll-pill.ok{background:var(--mint);color:#2F5A45;} .ll-pill.info{background:var(--blue-soft);color:#1F5F95;}
.ll-pill.warn{background:var(--amber);color:#7A5A00;} .ll-pill.urgent{background:var(--urgent-soft);color:#9B4A42;}
.ll-pill.neutral{background:#EEF1EC;color:var(--muted);}
.ll-badge{display:inline-flex;gap:.45rem;align-items:center;background:var(--mint);color:var(--sage);padding:.35rem .9rem;border-radius:999px;font-weight:600;font-size:.88rem;}
.ll-hero h1{font-size:3.1rem;line-height:1.12;margin:.9rem 0 .8rem;font-weight:800;}
.ll-hero p.lead{font-size:1.12rem;line-height:1.7;max-width:34rem;color:var(--body);margin:0 0 1.2rem;}
.st-key-hero{background:linear-gradient(135deg,var(--blue-soft) 0%,var(--ivory) 70%);border:1px solid var(--border);border-radius:28px;padding:2.2rem 2.4rem;box-shadow:var(--shadow);}
.st-key-banner{background:var(--sage);border-radius:26px;padding:2rem 2.4rem;}
.st-key-banner h2,.st-key-banner p{color:#fff!important;margin:0 0 .4rem;}
.st-key-banner [data-testid="stBaseButton-primary"]{background:#fff;color:var(--sage);border-color:#fff;}
.st-key-banner [data-testid="stBaseButton-primary"]:hover{background:var(--mint);color:var(--sage);}
.st-key-banner [data-testid="stBaseButton-secondary"]{border-color:#fff;color:#fff;}
.st-key-banner [data-testid="stBaseButton-secondary"]:hover{background:rgba(255,255,255,.14);color:#fff;}
.ll-hero-img{width:100%;height:auto;display:block;}
.ll-section{margin:2.6rem 0 1rem;} .ll-section h2{font-size:1.65rem;margin:0 0 .3rem;} .ll-section p{margin:0;color:var(--muted);}
.ll-notice{display:flex;gap:.8rem;align-items:flex-start;border-radius:16px;padding:.9rem 1.1rem;font-size:.93rem;line-height:1.55;margin:.4rem 0 1rem;border:1px solid transparent;}
.ll-notice .ic{flex:none;margin-top:2px;}
.ll-notice.info{background:var(--blue-soft);color:#24506F;border-color:#D3E7F3;}
.ll-notice.ok{background:var(--mint);color:#2F5A45;border-color:#C6E2D0;}
.ll-notice.warn{background:var(--amber);color:#6B5000;border-color:#F3E1A4;}
.ll-notice.urgent{background:var(--urgent-soft);color:#8A3F38;border-color:#EBCBC7;}
.ll-empty{text-align:center;background:var(--card);border:1px dashed #CBD8CE;border-radius:22px;padding:2.4rem 1.5rem;}
.ll-empty .chip{width:60px;height:60px;border-radius:20px;background:var(--mint);color:var(--sage);display:grid;place-items:center;margin:0 auto 1rem;}
.ll-empty h3{margin:0 0 .3rem;} .ll-empty p{margin:0 auto;max-width:30rem;color:var(--muted);}
.ll-footer{margin-top:3rem;padding:1.6rem 0 .5rem;border-top:1px solid var(--border);color:var(--muted);font-size:.86rem;line-height:1.6;}
.ll-footer b{color:var(--head);}
.ll-idbox{background:var(--ivory);border:1px dashed var(--teal);border-radius:16px;padding:1rem 1.2rem;margin:.6rem 0;}
.ll-idbox code{font-size:1.25rem;font-weight:700;color:var(--head);background:transparent;letter-spacing:.06em;}
.ll-kv{display:flex;flex-wrap:wrap;gap:.5rem 1.4rem;color:var(--body);font-size:.92rem;margin:.35rem 0;}
.ll-kv span b{color:var(--head);font-weight:600;}
.ll-score{font-size:1.7rem;font-weight:800;color:var(--head);line-height:1;} .ll-score small{font-size:.8rem;color:var(--muted);font-weight:500;}
.ll-bar{height:8px;background:#EEF1EC;border-radius:99px;overflow:hidden;margin:.25rem 0 .6rem;} .ll-bar i{display:block;height:100%;background:var(--ocean);border-radius:99px;}
.ll-bar.sage i{background:var(--sage);} .ll-bar.teal i{background:var(--teal);}
.ll-bgrid{display:grid;grid-template-columns:repeat(4,1fr);gap:.6rem;} .ll-bgrid .cell{background:var(--blue-soft);border-radius:14px;padding:.7rem;text-align:center;}
.ll-bgrid .cell b{display:block;font-size:1.25rem;color:var(--head);} .ll-bgrid .cell span{font-size:.8rem;color:var(--muted);}

/* ── responsive ── */
@media (max-width: 900px){
  .ll-grid.c4{grid-template-columns:repeat(2,1fr);} .ll-grid.c3{grid-template-columns:1fr;}
  .ll-hero h1{font-size:2.3rem;} .st-key-hero{padding:1.5rem 1.3rem;} .st-key-banner{padding:1.5rem 1.3rem;}
}
@media (max-width: 640px){
  .block-container{padding:1.2rem 1rem 2.5rem;}
  .ll-grid.c4,.ll-grid.c2{grid-template-columns:1fr;} .ll-bgrid{grid-template-columns:repeat(2,1fr);}
  .ll-hero h1{font-size:1.95rem;} .ll-pagehead h1{font-size:1.5rem;}
  [data-testid="stForm"]{padding:1.1rem;} .stButton>button,.stFormSubmitButton>button{width:100%;min-height:3.1rem;}
}
@media (prefers-reduced-motion: reduce){*{transition:none!important;animation:none!important;}}
"""


def inject_css() -> None:
    st.markdown(f"<style>{_CSS}</style>", unsafe_allow_html=True)


def setup_chrome() -> None:
    """Sidebar logo — call once from the entry script."""
    try:
        st.logo(str(ASSETS / "logo.svg"), icon_image=str(ASSETS / "icon.svg"), size="large")
    except Exception:  # very old Streamlit: no st.logo
        pass


# ── Components ───────────────────────────────────────────────────────────────

def page_header(title: str, subtitle: str = "", icon_name: str = "heart") -> None:
    render(f"""
    <div class="ll-pagehead"><div class="chip">{icon(icon_name, 26)}</div>
    <div><h1>{esc(title)}</h1>{f'<p>{esc(subtitle)}</p>' if subtitle else ''}</div></div>""")


def section(title: str, subtitle: str = "") -> None:
    render(f'<div class="ll-section"><h2>{esc(title)}</h2>{f"<p>{esc(subtitle)}</p>" if subtitle else ""}</div>')


def card(title: str, body: str, icon_name: str = "heart", tone: str = "blue", extra_class: str = "") -> str:
    """Returns HTML for a card (body is trusted HTML)."""
    chip = "sage" if tone == "sage" else ""
    return (f'<div class="ll-card {extra_class}"><div class="chip {chip}">{icon(icon_name, 22)}</div>'
            f'<h3>{esc(title)}</h3><p>{body}</p></div>')


def card_grid(cards_html: list[str], cols: int = 3) -> None:
    render(f'<div class="ll-grid c{cols}">{"".join(cards_html)}</div>')


def stat_cards(items: list[tuple[str, object, str, str]]) -> None:
    """items: (label, value, icon_name, tone 'blue'|'sage')"""
    cells = "".join(
        f'<div class="ll-stat"><div class="chip {"sage" if tone == "sage" else ""}">{icon(ic, 22)}</div>'
        f'<div><b>{esc(f"{value:,}" if isinstance(value, int) else value)}</b><span>{esc(label)}</span></div></div>'
        for label, value, ic, tone in items
    )
    render(f'<div class="ll-grid c4">{cells}</div>')


def pill(text: str, kind: str = "neutral") -> str:
    return f'<span class="ll-pill {kind}">{esc(text)}</span>'


def status_pill(status: str) -> str:
    kind = {"Open": "info", "In Progress": "warn", "Fulfilled": "ok", "Cancelled": "neutral",
            "Pending Contact": "warn", "Contacted": "info", "Completed": "ok", "Failed": "neutral"}.get(status, "neutral")
    return pill(status, kind)


def urgency_pill(urgency: str) -> str:
    kind = ("urgent" if urgency.startswith("Critical") else "warn" if urgency.startswith("Urgent")
            else "info" if urgency.startswith("Moderate") else "ok")
    return pill(urgency, kind)


def score_pill(score: float) -> str:
    if score >= 80:
        return pill("Strong match", "ok")
    if score >= 60:
        return pill("Acceptable", "info")
    return pill("Needs review", "warn")


def notice(kind: str, text: str, title: str = "") -> None:
    ic = {"info": "info", "ok": "check", "warn": "alert", "urgent": "alert"}.get(kind, "info")
    head = f"<b>{esc(title)}</b> " if title else ""
    render(f'<div class="ll-notice {kind}"><span class="ic">{icon(ic, 20)}</span><div>{head}{esc(text)}</div></div>')


def empty_state(title: str, text: str, icon_name: str = "search") -> None:
    render(f'<div class="ll-empty"><div class="chip">{icon(icon_name, 28)}</div><h3>{esc(title)}</h3><p>{esc(text)}</p></div>')


def emergency_notice() -> None:
    notice("warn",
           f"LifeLink is a coordination tool. In an emergency, call {EMERGENCY_NUMBER_IN} or contact the treating "
           "hospital first — do not wait for a match here.", "Emergency?")


def medical_disclaimer() -> None:
    notice("info",
           "Match scores are generated by software to help coordinators prioritise. They are not medical approval. "
           "Blood compatibility, screening and cross-matching must be confirmed by qualified healthcare professionals.")


def id_box(label: str, value: str) -> str:
    return f'<div class="ll-idbox"><div style="color:var(--muted);font-size:.85rem">{esc(label)}</div><code>{esc(value)}</code></div>'


def progress_bar(value: float, tone: str = "") -> str:
    pct = max(0, min(100, float(value)))
    return f'<div class="ll-bar {tone}"><i style="width:{pct}%"></i></div>'


def hero_image() -> str:
    return f'<img class="ll-hero-img" alt="Two hands gently holding a heart with a blood drop" src="{_data_uri("hero.svg")}"/>'


def footer() -> None:
    render(f"""
    <div class="ll-footer"><b>{BRAND_NAME}</b> — {esc(BRAND_TAGLINE)}<br>
    LifeLink is a coordination tool and does not provide medical advice. Always follow the guidance of qualified
    healthcare professionals. In an emergency call {EMERGENCY_NUMBER_IN} or contact the treating hospital.</div>""")
