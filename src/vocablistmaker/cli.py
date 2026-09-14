"""Kommandozeile: ``vocablistmaker wordlist.xlsx "Unit 4"``."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from . import __version__
from .additions import AdditionPlanError, plan_additions
from .config import Settings
from .curated import export_selection, load_curated
from .docx_writer import check_page_fit, suggested_filename, write_docx
from .excel_reader import parse_unit_input, read_workbook
from .llm import LLMClient
from .pipeline import generate_tests
from .provenance import analyse
from .report import summary_line, to_json, to_markdown


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vocablistmaker",
        description="Erzeugt aus einer Excel-Wortliste zwei Vokabeltests als Word-Datei.",
    )
    parser.add_argument(
        "excel", type=Path, nargs="?", default=None,
        help="Pfad zur Excel-Wortliste (.xlsx)",
    )
    parser.add_argument("unit", nargs="?", default=None, help='Unit, z. B. "Unit 4" oder "4"')
    parser.add_argument("-o", "--output", type=Path, default=None, help="Zieldatei (.docx)")
    parser.add_argument("--report", type=Path, default=None, help="Qualitätsbericht als Markdown")
    parser.add_argument("--json", type=Path, default=None, help="Qualitätsbericht als JSON")
    parser.add_argument("--model", default=None, help="Modellname (Standard: claude-opus-5)")
    parser.add_argument(
        "--no-llm", action="store_true",
        help="Nur regelbasiert arbeiten, ohne Sprachmodell.",
    )
    parser.add_argument("--list-units", action="store_true", help="Vorhandene Units anzeigen")
    parser.add_argument(
        "--export-auswahl", type=Path, default=None, metavar="DATEI",
        help="Geprüfte Wortauswahl als JSON-Gerüst schreiben, Satzfelder bleiben leer.",
    )
    parser.add_argument(
        "--aus-datei", type=Path, default=None, metavar="DATEI",
        help="Word-Datei aus einer kuratierten JSON-Datei bauen (ohne Excel).",
    )
    parser.add_argument(
        "--keine-mustersaetze", action="store_true",
        help="Abbrechen statt Beispielsätze aus festen Mustern zu erzeugen.",
    )
    parser.add_argument(
        "--zusatz-woerter", type=int, default=None, metavar="N",
        help="Wie viele zusätzliche Einzelwörter ergänzt werden sollen.",
    )
    parser.add_argument(
        "--zusatz-ausdruecke", type=int, default=None, metavar="N",
        help=(
            "Wie viele zusätzliche Ausdrücke ergänzt werden sollen "
            "(Wendungen wie 'stand up for', 'make a difference')."
        ),
    )
    parser.add_argument(
        "--zusatz-chunks", type=int, default=None, metavar="N",
        help=(
            "Wie viele zusätzliche Chunks ergänzt werden sollen - Satzrahmen "
            "mit offener Stelle wie 'What stood out to me was …'."
        ),
    )
    parser.add_argument(
        "--nur-hauptteil", action="store_true",
        help=(
            "Nur den Hauptteil einer Unit verwenden, ohne Culture, Songs, "
            "Project und Curriculum extra."
        ),
    )
    parser.add_argument(
        "--herkunft", type=Path, default=None, metavar="EXCEL",
        help=(
            "Zusammen mit --aus-datei: gegen diese Excel-Datei prüfen, welche "
            "Wörter weggelassen, ersetzt oder frei ergänzt wurden."
        ),
    )
    parser.add_argument("--seed", type=int, default=None, help="Zufallsstartwert")
    parser.add_argument("-v", "--verbose", action="store_true", help="Ausführliche Ausgabe")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(message)s",
    )

    settings = Settings()
    if args.model:
        settings.model = args.model
    if args.no_llm:
        settings.use_llm = False
    if args.seed is not None:
        settings.seed = args.seed
    if args.keine_mustersaetze:
        settings.allow_template_sentences = False
    if getattr(args, "nur_hauptteil", False):
        settings.core_sections_only = True
    settings.extra_words = getattr(args, "zusatz_woerter", None)
    settings.extra_expressions = getattr(args, "zusatz_ausdruecke", None)
    settings.extra_chunks = getattr(args, "zusatz_chunks", None)
    if args.export_auswahl:
        # Beim Export interessieren nur die Wörter - Sätze kommen später.
        settings.allow_template_sentences = True

    # --- Kuratierte Datei: kein Excel nötig ---
    if args.aus_datei:
        if not args.aus_datei.exists():
            print(f"Die Datei '{args.aus_datei}' wurde nicht gefunden.", file=sys.stderr)
            return 2
        try:
            pair = load_curated(args.aus_datei, settings)
        except ValueError as exc:
            print(f"Fehler: {exc}", file=sys.stderr)
            return 1
        output = args.output or Path(suggested_filename(pair))
        write_docx(pair, output, settings)
        print(f"Word-Datei geschrieben: {output}")
        for name, items in (("Test 1", pair.test1), ("Test 2", pair.test2)):
            print(f"  {name}: {check_page_fit(items, settings).describe()}")
        if args.herkunft:
            if not args.herkunft.exists():
                print(f"Die Datei '{args.herkunft}' wurde nicht gefunden.", file=sys.stderr)
                return 2
            book = read_workbook(args.herkunft)
            print()
            print(analyse(pair, book, pair.unit, settings.core_sections_only).to_markdown())
        if args.report:
            args.report.write_text(to_markdown(pair), encoding="utf-8")
            print(f"Bericht geschrieben:    {args.report}")
        if args.json:
            args.json.write_text(to_json(pair), encoding="utf-8")
        print(summary_line(pair))
        for issue in pair.report.errors:
            print(f"  FEHLER {issue.code}: {issue.message}", file=sys.stderr)
        return 1 if pair.report.errors else 0

    if args.excel is None:
        print("Bitte eine Excel-Datei oder --aus-datei angeben.", file=sys.stderr)
        return 2
    if not args.excel.exists():
        print(f"Die Datei '{args.excel}' wurde nicht gefunden.", file=sys.stderr)
        return 2

    if args.list_units:
        book = read_workbook(args.excel)
        print(f"Tabellenblatt: {book.sheet}")
        for unit in book.units:
            print(f"  {book.unit_label(unit):14s} {len(book.unit_entries(unit)):4d} Vokabeln")
        return 0

    if not args.unit:
        print('Bitte eine Unit angeben, z. B. "Unit 4".', file=sys.stderr)
        return 2

    client = LLMClient(settings)
    if not client.available and not args.no_llm:
        print(
            "Hinweis: Kein ANTHROPIC_API_KEY gefunden - es wird rein regelbasiert "
            "gearbeitet. Die Beispielsätze sind dann sehr schlicht.",
            file=sys.stderr,
        )

    try:
        unit = parse_unit_input(args.unit)
        result = generate_tests(
            args.excel, unit, settings, client,
            progress=(lambda m, f: print(f"[{f * 100:3.0f}%] {m}")) if args.verbose else None,
        )
    except ValueError as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1

    pair = result.pair

    if args.export_auswahl:
        available = int(
            pair.report.stats.get(
                "aus_pool_ohne_lockerung", len(pair.test1) + len(pair.test2)
            )
        )
        try:
            plan = plan_additions(
                available, settings.target_total,
                settings.extra_words, settings.extra_expressions,
                settings.extra_chunks,
            )
        except AdditionPlanError as exc:
            print(f"Fehler: {exc}", file=sys.stderr)
            return 1
        export_selection(pair, args.export_auswahl, plan=plan)
        print(f"Wortauswahl geschrieben: {args.export_auswahl}")
        print(f"  Hauptteil liefert {available} geprüfte Wörter.")
        print(f"  {plan.describe()}")
        for warning in plan.warnings:
            print(f"  WARNUNG: {warning}", file=sys.stderr)
        if plan.extra_total:
            print(
                f"  {plan.extra_total} Platzhalter sind auszufüllen: "
                f"{plan.extra_words}x 'ZU ERGÄNZEN (Wort)', "
                f"{plan.extra_expressions}x 'ZU ERGÄNZEN (Ausdruck)', "
                f"{plan.extra_chunks}x 'ZU ERGÄNZEN (Chunk)'."
            )
        print(
            "Jetzt die Felder ausfüllen und danach mit "
            f"--aus-datei {args.export_auswahl} die Word-Datei erzeugen."
        )
        return 0

    output = args.output or Path(suggested_filename(pair))
    write_docx(pair, output, settings)
    print(f"Word-Datei geschrieben: {output}")

    if args.report:
        args.report.write_text(to_markdown(pair), encoding="utf-8")
        print(f"Bericht geschrieben:    {args.report}")
    if args.json:
        args.json.write_text(to_json(pair), encoding="utf-8")
        print(f"JSON geschrieben:       {args.json}")

    print(summary_line(pair))
    for issue in pair.report.errors:
        print(f"  FEHLER {issue.code}: {issue.message}", file=sys.stderr)
    return 1 if pair.report.errors else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
