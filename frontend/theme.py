"""Shared visual primitives for the mobile-first Streamlit frontend."""
import streamlit as st


def apply_theme():
    st.markdown(
        """
        <style>
        :root {
            --fresh-berry: #b8324b;
            --fresh-berry-dark: #8f2439;
            --fresh-leaf: #287c58;
            --fresh-leaf-soft: #e7f3eb;
            --fresh-cream: #fffaf3;
            --fresh-ink: #252321;
            --fresh-muted: #6d6862;
        }
        .stApp {
            background: var(--fresh-cream);
            color: var(--fresh-ink);
        }
        [data-testid="stHeader"] {
            background: transparent;
        }
        .block-container {
            max-width: 760px;
            padding: 1.25rem 1rem 4rem;
        }
        .fresh-brand {
            display: flex;
            align-items: center;
            gap: .75rem;
            margin: .25rem 0 1.5rem;
        }
        .fresh-brand-mark {
            display: grid;
            place-items: center;
            width: 2.75rem;
            height: 2.75rem;
            border-radius: 1rem;
            background: var(--fresh-berry);
            color: white;
            font-size: 1.35rem;
            box-shadow: 0 6px 16px rgba(184, 50, 75, .2);
        }
        .fresh-brand h1 {
            margin: 0;
            color: var(--fresh-ink);
            font-size: clamp(1.45rem, 6vw, 2rem);
            line-height: 1.1;
            letter-spacing: -.03em;
        }
        .fresh-brand p, .fresh-section p {
            color: var(--fresh-muted);
            margin: .25rem 0 0;
            font-size: .92rem;
        }
        .fresh-section {
            margin: 1.25rem 0 .75rem;
        }
        .fresh-eyebrow {
            color: var(--fresh-leaf);
            font-size: .72rem;
            font-weight: 800;
            letter-spacing: .12em;
            text-transform: uppercase;
        }
        .fresh-section h2 {
            margin: .2rem 0 0;
            color: var(--fresh-ink);
            font-size: 1.35rem;
            letter-spacing: -.02em;
        }
        [data-testid="stTabs"] button {
            min-height: 2.8rem;
            font-weight: 700;
        }
        [data-testid="stTabs"] button[aria-selected="true"] {
            color: var(--fresh-berry);
        }
        [data-testid="stTabs"] [data-baseweb="tab-highlight"] {
            background: var(--fresh-berry);
        }
        [data-testid="stButton"] > button,
        [data-testid="stLinkButton"] > a {
            min-height: 2.85rem;
            border-radius: .85rem;
            font-weight: 700;
            border-color: var(--fresh-berry);
        }
        [data-testid="stButton"] > button[kind="primary"] {
            background: var(--fresh-berry);
            color: white;
        }
        [data-testid="stButton"] > button:hover,
        [data-testid="stLinkButton"] > a:hover {
            border-color: var(--fresh-berry-dark);
            color: var(--fresh-berry-dark);
        }
        [data-testid="stMetric"] {
            padding: .8rem 1rem;
            border: 1px solid rgba(40, 124, 88, .18);
            border-radius: 1rem;
            background: var(--fresh-leaf-soft);
        }
        [data-testid="stMetricLabel"] {
            color: var(--fresh-muted);
        }
        [data-testid="stMetricValue"] {
            color: var(--fresh-leaf);
        }
        [data-testid="stExpander"] {
            border-color: rgba(37, 35, 33, .14);
            border-radius: 1rem;
            background: rgba(255, 255, 255, .54);
        }
        @media (max-width: 480px) {
            .block-container {
                padding: .8rem .75rem 3rem;
            }
            .fresh-brand {
                margin-bottom: 1rem;
            }
            [data-testid="stHorizontalBlock"] {
                gap: .5rem;
            }
            [data-testid="stDataFrame"] {
                font-size: .85rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def brand_header(title, subtitle):
    st.markdown(
        f"""
        <header class="fresh-brand">
            <div class="fresh-brand-mark" aria-hidden="true">✦</div>
            <div>
                <h1>{title}</h1>
                <p>{subtitle}</p>
            </div>
        </header>
        """,
        unsafe_allow_html=True,
    )


def section_header(eyebrow, title, description=None):
    description_markup = f"<p>{description}</p>" if description else ""
    st.markdown(
        f"""
        <div class="fresh-section">
            <div class="fresh-eyebrow">{eyebrow}</div>
            <h2>{title}</h2>
            {description_markup}
        </div>
        """,
        unsafe_allow_html=True,
    )
