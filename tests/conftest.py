"""Gemeinsame Testhilfen: eine synthetische Wortliste im Format des Lehrmittels."""

from __future__ import annotations

from io import BytesIO

import pytest
from openpyxl import Workbook as XlsxWorkbook

# (Oxford, English, German, Section)
_ROWS: list[tuple[str, str, str, str]] = [
    ("Starter unit", "", "", ""),
    ("*", "afternoon", "Nachmittag", "Starter Unit, p.4"),
    ("*", "cook", "kochen", "Starter Unit, p.4"),
    ("", "headphones", "Kopfhörer", "Starter Unit, p.4"),
    ("Unit 1", "", "", ""),
]

_UNIT1_WORDS = [
    ("persuade", "überzeugen"), ("rubbish", "Abfall"), ("waterproof", "wasserdicht"),
    ("caterpillar", "Raupe"), ("jewellery", "Schmuck"), ("pendant", "Anhänger"),
    ("negotiate", "verhandeln"), ("queue", "Warteschlange"), ("pesticide", "Pestizid"),
    ("ecological", "ökologisch"), ("falcon", "Falke"), ("plantation", "Plantage"),
    ("toothpaste", "Zahnpasta"), ("headache", "Kopfschmerzen"), ("packet", "Paket"),
    ("bin", "Mülleimer"), ("nail", "Nagel"), ("noise", "Geräusch"),
    ("useless", "nutzlos"), ("farming", "Landwirtschaft"), ("habit", "Gewohnheit"),
    ("label", "Etikett"), ("summary", "Zusammenfassung"), ("convince", "überzeugen"),
    ("pollution", "Verschmutzung"), ("pollute", "verschmutzen"),
    ("recycle", "wiederverwerten"), ("recycling", "Wiederverwertung"),
    ("sensitive", "empfindlich"), ("practical", "praktisch"), ("rating", "Bewertung"),
    ("destroy", "zerstören"), ("afford", "(sich etw.) leisten"), ("branch", "Zweig"),
    ("battery", "Batterie"), ("marine animal", "Meerestier"), ("soap", "Seife"),
    ("cocoa", "Kakao"), ("slogan", "Slogan"), ("regularly", "regelmässig"),
    ("automatic", "automatisch"), ("unwanted", "unerwünscht"), ("jackal", "Schakal"),
    ("light bulb", "Glühbirne"), ("survey", "Umfrage"), ("profit", "Gewinn"),
    ("aluminium", "Aluminium"), ("shampoo", "Shampoo"), ("deodorant", "Deodorant"),
    ("intellect", "Verstand"), ("affect", "beeinflussen"), ("worried", "besorgt"),
    ("blow down", "umblasen"), ("typically", "normalerweise"), ("item", "Gegenstand"),
    ("tube", "Tube"), ("knife", "Messer"), ("resource", "Ressource"),
    ("solar", "Solar"), ("protein", "Protein"), ("autumn", "Herbst"),
    ("increase", "ansteigen"), ("exchange", "austauschen"), ("fix", "reparieren"),
    ("world", "Welt"), ("house", "Haus"), ("dog", "Hund"), ("sun", "Sonne"),
    ("star", "Stern"), ("big", "gross"),
    # weiteres B1/B2-Material, damit die Unit zwei volle Tests hergibt
    ("landfill", "Mülldeponie"), ("greenhouse gas", "Treibhausgas"),
    ("charity shop", "Wohltätigkeitsladen"), ("wrapping", "Verpackung"),
    ("leftover", "Rest, Übriggebliebenes"), ("disposable", "Einweg-"),
    ("durable", "haltbar, langlebig"), ("scarce", "knapp"),
    ("thrifty", "sparsam"), ("mend", "flicken, ausbessern"),
    ("swap", "tauschen"), ("donate", "spenden"),
    ("footprint", "Fussabdruck"), ("emission", "Ausstoss"),
    ("renewable", "erneuerbar"), ("landscape", "Landschaft"),
    ("harvest", "Ernte"), ("drought", "Dürre"),
    ("shortage", "Knappheit, Mangel"), ("awareness", "Bewusstsein"),
    ("campaign", "Kampagne, Aktion"), ("volunteer", "Freiwillige(r)"),
    ("consumer", "Verbraucher(in)"), ("packaging", "Verpackung"),
    ("wasteful", "verschwenderisch"), ("reusable", "wiederverwendbar"),
]


def _build_rows() -> list[tuple[str, str, str, str]]:
    rows = list(_ROWS)
    for index, (en, de) in enumerate(_UNIT1_WORDS):
        rows.append(("*" if index % 3 == 0 else "", en, de, f"Unit 1, p.{10 + index % 5}"))
    rows.append(("Culture", "", "", ""))
    rows.append(("", "car boot sale", "Kofferraumverkauf", "Culture 1"))
    rows.append(("", "second-hand", "gebraucht", "Culture 1"))
    rows.append(("Unit 2", "", "", ""))
    for en, de in [("sequel", "Fortsetzung"), ("villain", "Bösewicht")]:
        rows.append(("", en, de, "Unit 2, p.22"))
    return rows


@pytest.fixture(scope="session")
def wordlist_bytes() -> bytes:
    """Eine Excel-Datei mit demselben Aufbau wie die Lehrmittelliste."""
    book = XlsxWorkbook()
    sheet = book.active
    sheet.title = "Sheet1"
    sheet.append([None, None, None, None])
    sheet.append(["German Wordlist", None, None, None])
    sheet.append(["Oxford 3000\n * = yes", "English", "Translation", "Section"])
    for oxford, english, german, section in _build_rows():
        sheet.append([oxford or None, english or None, german or None, section or None])
    buffer = BytesIO()
    book.save(buffer)
    return buffer.getvalue()


@pytest.fixture
def wordlist(wordlist_bytes: bytes) -> BytesIO:
    return BytesIO(wordlist_bytes)
