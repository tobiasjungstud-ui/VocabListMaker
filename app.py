"""Weboberfläche: Excel hochladen, Unit wählen, Tests erzeugen, Word herunterladen."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Erlaubt den Start als "streamlit run app.py" ohne vorherige Installation.
sys.path.insert(0, str(Path(__file__).parent / "src"))

import streamlit as st  # noqa: E402

from vocablistmaker import __version__  # noqa: E402
from vocablistmaker.config import Settings  # noqa: E402
from vocablistmaker.docx_writer import suggested_filename, to_bytes  # noqa: E402
from vocablistmaker.excel_reader import read_workbook  # noqa: E402
from vocablistmaker.llm import LLMClient  # noqa: E402
from vocablistmaker.pipeline import generate_tests  # noqa: E402
from vocablistmaker.report import summary_line, to_json, to_markdown  # noqa: E402

st.set_page_config(page_title="VocabListMaker", page_icon="📘", layout="wide")


def resolve_api_key() -> str | None:
    """Schlüssel aus den Streamlit-Secrets oder der Umgebung."""
    try:
        value = st.secrets.get("ANTHROPIC_API_KEY")  # type: ignore[attr-defined]
        if value:
            return str(value)
    except Exception:
        pass
    return os.environ.get("ANTHROPIC_API_KEY") or None


st.title("📘 VocabListMaker")
st.caption(
    "Aus der Excel-Wortliste des Lehrmittels werden zwei Vokabeltests mit je "
    "30 Wörtern und Beispielsätzen - fertig als Word-Datei."
)

settings = Settings()
api_key = resolve_api_key()

with st.sidebar:
    st.header("Einstellungen")
    use_llm = st.toggle(
        "Sprachmodell verwenden",
        value=bool(api_key),
        help=(
            "Mit Sprachmodell entstehen unterrichtsfertige Beispielsätze, passende "
            "Ersatzwörter und eine inhaltliche Schlusskontrolle. Ohne Schlüssel "
            "arbeitet die Anwendung rein regelbasiert."
        ),
    )
    if use_llm and not api_key:
        api_key = st.text_input(
            "ANTHROPIC_API_KEY", type="password",
            help="Wird nur für diese Sitzung verwendet und nicht gespeichert.",
        ) or None
    if use_llm and api_key:
        st.success("Sprachmodell ist einsatzbereit.")
    elif use_llm:
        st.warning("Ohne Schlüssel läuft nur der regelbasierte Modus.")

    words_per_test = st.number_input(
        "Wörter pro Test", min_value=5, max_value=60, value=settings.words_per_test, step=5
    )
    with st.expander("Weitere Optionen"):
        model = st.text_input("Modell", value=settings.model)
        heading1 = st.text_input("Überschrift Test 1", value=settings.heading_test1)
        heading2 = st.text_input("Überschrift Test 2", value=settings.heading_test2)
        font = st.text_input("Schriftart", value=settings.font_name)
        bold_target = st.checkbox("Zielwort im Beispielsatz fett", value=True)
        seed = st.number_input("Zufallsstartwert", value=settings.seed, step=1)

    st.caption(f"Version {__version__}")

uploaded = st.file_uploader(
    "1. Excel-Wortliste auswählen", type=["xlsx", "xlsm"],
    help="Die Datei mit dem Vokabular aller Units.",
)

if uploaded is None:
    st.info(
        "Bitte zuerst die Excel-Datei des Lehrmittels hochladen. Erwartet werden "
        "Spalten für das englische Wort, die deutsche Übersetzung und die "
        "Sektion bzw. Unit."
    )
    st.stop()

try:
    workbook = read_workbook(uploaded)
except ValueError as exc:
    st.error(str(exc))
    st.stop()

for warning in workbook.warnings:
    st.warning(warning)

units = workbook.units
if not units:
    st.error("In der Datei wurden keine Units erkannt.")
    st.stop()

labels = {workbook.unit_label(u): u for u in units}
default_label = next(
    (label for label in labels if label != "Starter Unit"), list(labels)[0]
)

col_left, col_right = st.columns([2, 1])
with col_left:
    chosen_label = st.selectbox(
        "2. Unit wählen", list(labels), index=list(labels).index(default_label)
    )
with col_right:
    unit = labels[chosen_label]
    st.metric("Vokabeln in dieser Unit", len(workbook.unit_entries(unit)))

start = st.button("3. Tests erstellen", type="primary", use_container_width=True)

if start:
    settings.words_per_test = int(words_per_test)
    settings.model = model
    settings.heading_test1 = heading1
    settings.heading_test2 = heading2
    settings.font_name = font
    settings.bold_target_word = bold_target
    settings.seed = int(seed)
    settings.use_llm = bool(use_llm and api_key)
    settings.api_key = api_key

    progress = st.progress(0.0, text="Start …")

    def report_progress(message: str, fraction: float) -> None:
        progress.progress(min(max(fraction, 0.0), 1.0), text=message)

    try:
        uploaded.seek(0)
        result = generate_tests(
            uploaded, unit, settings, LLMClient(settings), progress=report_progress
        )
    except ValueError as exc:
        progress.empty()
        st.error(str(exc))
        st.stop()
    except Exception as exc:  # pragma: no cover - Anzeige unerwarteter Fehler
        progress.empty()
        st.error(f"Unerwarteter Fehler: {exc}")
        st.stop()

    progress.empty()
    st.session_state["result"] = result

result = st.session_state.get("result")
if result is None:
    st.stop()

pair = result.pair
report = pair.report

st.divider()
if report.errors:
    st.error(f"4. Ergebnis - {summary_line(pair)}")
else:
    st.success(f"4. Ergebnis - {summary_line(pair)}")

st.download_button(
    "📄 Word-Datei herunterladen",
    data=to_bytes(pair, settings),
    file_name=suggested_filename(pair),
    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    type="primary",
    use_container_width=True,
)

metrics = st.columns(4)
metrics[0].metric("Test 1", f"{len(pair.test1)} Wörter")
metrics[1].metric("Test 2", f"{len(pair.test2)} Wörter")
metrics[2].metric(
    "Schwierigkeitsdifferenz", f"{report.stats.get('schwierigkeit_differenz', 0):.3f}"
)
metrics[3].metric("Modellaufrufe", report.stats.get("modellaufrufe", 0))

if report.stats.get("gesamturteil"):
    st.info(f"**Gesamturteil:** {report.stats['gesamturteil']}")

tab1, tab2, tab3 = st.tabs(["Test 1", "Test 2", "Qualitätsbericht"])
for tab, items in ((tab1, pair.test1), (tab2, pair.test2)):
    with tab:
        st.dataframe(
            [
                {
                    "Nr.": i.number,
                    "Deutsch": i.german,
                    "English": i.english,
                    "Example sentence": i.sentence,
                }
                for i in items
            ],
            hide_index=True,
            use_container_width=True,
        )

with tab3:
    if not report.issues:
        st.success("Keine Beanstandungen.")
    for issue in report.errors:
        st.error(f"**{issue.code}** — {issue.message}")
    for issue in report.warnings:
        st.warning(f"**{issue.code}** — {issue.message}")
    with st.expander(f"Notizen zum Ablauf ({len(report.issues) - len(report.errors) - len(report.warnings)})"):
        for issue in report.issues:
            if issue.severity.value == "info":
                st.write(f"- **{issue.code}**: {issue.message}")

    st.download_button(
        "Bericht als Markdown",
        data=to_markdown(pair),
        file_name=f"Qualitaetsbericht_{pair.unit_label.replace(' ', '_')}.md",
        mime="text/markdown",
    )
    st.download_button(
        "Bericht als JSON",
        data=to_json(pair),
        file_name=f"Qualitaetsbericht_{pair.unit_label.replace(' ', '_')}.json",
        mime="application/json",
    )
