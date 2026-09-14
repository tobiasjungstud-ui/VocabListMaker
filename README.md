# VocabListMaker

Aus der Excel-Wortliste eines Lehrmittels entstehen zwei fertige Vokabeltests
als Word-Datei: **Test 1** und **Test 2** mit je 30 Wörtern, jeweils mit
deutscher Übersetzung und Beispielsatz — im Layout der bestehenden Vorlage.

Der Arbeitsablauf besteht aus vier Schritten:

1. Excel-Datei auswählen
2. Unit angeben, z. B. „Unit 4“
3. auf **Tests erstellen** klicken
4. Word-Datei herunterladen

---

## Was die Anwendung leistet

| Anforderung | Umsetzung |
|---|---|
| Nur Vokabular der gewählten Unit | Doppelte Unit-Erkennung über Blocküberschriften **und** die Spalte `Section`; Seitenangaben wie `Starter Unit, p.4` werden korrekt als Seite und nicht als Unit gelesen. Zusatzbereiche (`Culture 4`, `Curriculum extra 4`, `Project 4`, `Songs 4`, `Extra Listening and Speaking Unit 4`) zählen zur jeweiligen Unit; `--nur-hauptteil` beschränkt auf den Block `Unit 4`. |
| Zu einfache Wörter aussortieren | Abgleich mit einem mitgelieferten A1/A2-Grundwortschatz, Häufigkeitsanalyse (Zipf-Wert), Erkennung von Wörtern aus früheren Units sowie von Internationalismen wie `Protein`/`Protein`, die deutschsprachigen Lernenden nichts beibringen. |
| Ersatzwörter statt Lücken | Fällt zu viel weg, sucht die Anwendung thematisch passende Begriffe auf B1–B2-Niveau, die dieselben Prüfungen durchlaufen wie das Originalmaterial. |
| Keine Doppelungen | Vier Stufen: identische Stichwörter, Wortfamilien (`recycle`/`recycling`/`recycled`, `pollute`/`pollution`), gleiche deutsche Bedeutung (`convince` und `persuade` sind beide „überzeugen“) und semantische Nähe durch das Sprachmodell. |
| Test 1 und Test 2 gleich schwer | Verteilung nach Wortart, anschliessend Tauschoptimierung auf gleiche mittlere Schwierigkeit, Streuung, Lernwert und Themenmischung. |
| Beispielsätze, die nicht die Lösung verraten | Definitionsmuster („A villain **is a** bad person …“), deutsche Wörter im Satz und Paraphrasen werden erkannt und der Satz wird neu erzeugt. |
| Layout der Vorlage | Seitenränder, Tabellenbreite (9520 dxa), Spaltenbreiten (435 / 2511 / 2024 / 4550), nur waagerechte Linien, Century Gothic, fette rechtsbündige Nummerierung und fett gesetztes Zielwort im Beispielsatz. |
| Jede Liste auf einer A4-Seite | Die Höhe wird vor der Ausgabe berechnet. Bei 11 pt liefen 30 Einträge mit zweizeiligen Beispielsätzen auf eine zweite Seite, deshalb sind 10 pt und Zeilenhöhe 340 voreingestellt (Auslastung rund 92 %). Test 2 beginnt immer auf einer neuen Seite. |
| Qualitätskontrolle vor der Ausgabe | Mehrere Prüfrunden mit automatischer Reparatur und ein abschliessender Gesamtblick auf beide Listen. |

---

## Installation

Voraussetzung ist Python 3.10 oder neuer.

```bash
git clone https://github.com/tobiasjungstud-ui/VocabListMaker.git
cd VocabListMaker

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
pip install -e .
```

### API-Schlüssel hinterlegen (empfohlen)

Ohne Schlüssel funktioniert die Anwendung vollständig, erzeugt die Beispielsätze
aber aus festen Mustern — sie sind grammatikalisch korrekt, aber inhaltlich
blass („We talked about a pendant in our lesson last week.“). **Für
unterrichtsfertige Sätze, Ersatzwörter und die inhaltliche Schlusskontrolle
wird ein Schlüssel benötigt.**

```bash
cp .env.example .env
# ANTHROPIC_API_KEY=sk-ant-... eintragen
export ANTHROPIC_API_KEY=sk-ant-...
```

Einen Schlüssel gibt es unter <https://console.anthropic.com>.

---

## Nutzung

### Arbeitsweise A: Inhalte im Chat mit Claude erstellen (aktuell verwendet)

Für Unterrichtsmaterial ist das der Weg mit der besten Qualität: Die Anwendung
übernimmt Auswahl, Prüfung und Layout, die Beispielsätze entstehen im Gespräch
mit Claude und werden dort auch gegengelesen. Es wird kein API-Schlüssel
benötigt.

```bash
# 1. Geprüfte Wortauswahl als Gerüst ausgeben - mit Platzhaltern für
#    zusätzliche Einzelwörter und Ausdrücke
vocablistmaker wordlist.xlsx "Unit 7" --no-llm --nur-hauptteil \
    --zusatz-woerter 12 --zusatz-ausdruecke 9 \
    --export-auswahl kuratiert/unit_7.json

# 2. Die Felder "satz" im Chat mit Claude ausfüllen lassen

# 3. Word-Datei bauen - alle Prüfungen laufen über die fertigen Inhalte
vocablistmaker --aus-datei kuratiert/unit_7.json -o Vocabulary_Unit_7.docx
```

Schritt 3 prüft die von Hand geschriebenen Inhalte genauso streng wie
automatisch erzeugte: Doppelungen, Niveau, Balance, Zielwort im Satz,
verratene Lösung – und zusätzlich, ob jede Liste auf eine A4-Seite passt.

**Herkunftsnachweis.** Mit `--herkunft wordlist.xlsx` gleicht die Anwendung
die fertige Liste gegen die Excel-Datei ab und zeigt, welche Wörter
weggelassen wurden (gruppiert nach Grund), welche entgegen der automatischen
Prüfung behalten wurden, bei welchen die deutsche Übersetzung geändert wurde
und – am wichtigsten – **welche Wörter gar nicht in der Excel-Datei stehen**:

```bash
vocablistmaker --aus-datei kuratiert/unit_7.json -o Unit_7.docx \
    --herkunft wordlist.xlsx
```

So ist jederzeit nachprüfbar, ob eine Liste stillschweigend um erfundene
Begriffe ergänzt wurde.

Fertige, geprüfte Listen liegen unter `kuratiert/` (aktuell Unit 7 und Unit 8).

> **Mustersätze abschalten:** `--keine-mustersaetze` lässt die Anwendung
> abbrechen, statt Beispielsätze aus festen Mustern zu erzeugen. So kann kein
> blasser Füllsatz unbemerkt in den Unterricht gelangen.

### Arbeitsweise B: Weboberfläche (der übliche Weg)

```bash
streamlit run app.py
```

Der Browser öffnet <http://localhost:8501>. Dort die Excel-Datei hochladen,
die Unit im Auswahlfeld wählen, **Tests erstellen** klicken und die Word-Datei
herunterladen. Vor dem Download zeigen drei Reiter beide Tests und den
Qualitätsbericht.

Wer keinen Schlüssel in der Umgebung hinterlegen möchte, kann ihn in der
Seitenleiste für die laufende Sitzung eingeben; er wird nicht gespeichert.

### Kommandozeile

```bash
# Welche Units enthält die Datei?
vocablistmaker wordlist.xlsx --list-units

# Tests für Unit 4 erzeugen
vocablistmaker wordlist.xlsx "Unit 4" -o Vocabulary_Unit_4.docx

# Mit Qualitätsbericht und ohne Sprachmodell
vocablistmaker wordlist.xlsx 4 --report bericht.md --json bericht.json --no-llm
```

| Option | Bedeutung |
|---|---|
| `-o`, `--output` | Zieldatei (Standard: `Vocabulary_Unit_<N>.docx`) |
| `--report` | Qualitätsbericht als Markdown |
| `--json` | Qualitätsbericht als JSON |
| `--no-llm` | rein regelbasiert arbeiten |
| `--model` | anderes Modell (Standard `claude-opus-5`) |
| `--seed` | Zufallsstartwert für reproduzierbare Auswahl |
| `--list-units` | vorhandene Units anzeigen |
| `--export-auswahl` | geprüfte Wortauswahl als JSON-Gerüst schreiben |
| `--aus-datei` | Word-Datei aus kuratierter JSON-Datei bauen |
| `--herkunft` | Abgleich gegen die Excel-Datei: weggelassen, ersetzt, ergänzt |
| `--keine-mustersaetze` | abbrechen statt Mustersätze zu erzeugen |
| `--nur-hauptteil` | nur den Block `Unit N`, ohne Culture/Songs/Project/Extra |
| `--zusatz-woerter` | Anzahl zusätzlicher Einzelwörter |
| `--zusatz-ausdruecke` | Anzahl zusätzlicher Ausdrücke (`stand up for`) |
| `-v` | Fortschritt anzeigen |

Der Rückgabewert ist `0`, wenn keine Fehler gefunden wurden, sonst `1` — damit
lässt sich der Aufruf in Skripten prüfen.

### Als Bibliothek

```python
from vocablistmaker.config import Settings
from vocablistmaker.docx_writer import write_docx
from vocablistmaker.pipeline import generate_tests

result = generate_tests("wordlist.xlsx", unit=4, settings=Settings())
write_docx(result.pair, "Vocabulary_Unit_4.docx")

print(result.pair.report.stats["schwierigkeit_differenz"])
for issue in result.pair.report.errors:
    print(issue)
```

---

## Aufbau der Excel-Datei

Erwartet wird ein Tabellenblatt mit einer Kopfzeile, die diese Spalten enthält:

| Spalte | Erkannte Bezeichnungen | Pflicht |
|---|---|---|
| englisches Wort | `English`, `Englisch`, `Word` | ja |
| deutsche Übersetzung | `Translation`, `Deutsch`, `Übersetzung` | ja |
| Herkunft | `Section`, `Unit`, `Abschnitt` | empfohlen |
| Oxford-3000-Markierung | `Oxford 3000` | nein |

Titelzeilen oberhalb der Kopfzeile und Blocküberschriften wie `Unit 4` oder
`Culture` innerhalb der Tabelle werden erkannt und übersprungen. Fehlt die
Spalte `Section`, greift die Anwendung auf die Blocküberschriften zurück.

---

## Ablauf im Detail

```
Excel einlesen  →  Unit bestimmen  →  bewerten  →  fachlich beurteilen
      →  Doppelungen entfernen  →  60 Wörter wählen  →  ggf. Ersatzwörter
      →  auf zwei gleich schwere Tests aufteilen  →  Beispielsätze
      →  Sätze prüfen und reparieren  →  Schlusskontrolle  →  Word-Datei
```

Jeder Schritt schreibt in den Qualitätsbericht. Der Bericht unterscheidet
**Fehler** (müssen angesehen werden), **Hinweise** (Randbemerkungen) und
**Notizen** (was die Anwendung selbst entschieden hat, etwa welches Wort
zugunsten eines anderen entfallen ist).

### Grenzen, die bewusst gesetzt sind

* Wörter aus dem mitgelieferten A1/A2-Grundwortschatz (`sun`, `house`, `dog`,
  `star`, …) gelangen **nie** in einen Test — auch dann nicht, wenn eine Unit
  dadurch zu wenig Material hätte. In dem Fall meldet die Anwendung, dass die
  Unit zu klein ist, statt die Qualität stillschweigend zu senken.
* Reicht das Material knapp nicht, rücken grenzwertige Wörter nach. Jedes
  nachgerückte Wort steht namentlich im Bericht.
* Ohne API-Schlüssel entstehen Beispielsätze aus Mustern. Der Bericht weist
  ausdrücklich darauf hin.

---

## Anpassungen

Alles lässt sich über Umgebungsvariablen steuern (siehe `.env.example`):

| Variable | Standard | Wirkung |
|---|---|---|
| `ANTHROPIC_API_KEY` | – | Zugang zum Sprachmodell |
| `VLM_MODEL` | `claude-opus-5` | verwendetes Modell |
| `VLM_EFFORT` | `high` | Gründlichkeit des Modells |
| `VLM_USE_LLM` | `true` | Sprachmodell abschalten |
| `VLM_WORDS_PER_TEST` | `30` | Wörter je Test |
| `VLM_REPAIR_ROUNDS` | `3` | Reparaturrunden |
| `VLM_SEED` | `20240607` | Zufallsstartwert |
| `VLM_CORE_ONLY` | `false` | nur den Hauptteil einer Unit verwenden |
| `VLM_FONT` | `Century Gothic` | Schriftart der Tabelle |
| `VLM_FONT_SIZE` | `10` | Schriftgrad der Tabelle in Punkt |
| `VLM_ROW_HEIGHT` | `340` | Mindesthöhe einer Tabellenzeile in Twips |
| `VLM_PAGE_BREAK` | `true` | Test 2 auf neuer Seite beginnen |
| `VLM_ALLOW_TEMPLATE_SENTENCES` | `true` | Mustersätze als Rückfallebene zulassen |

Der A1/A2-Grundwortschatz steht in
`src/vocablistmaker/data/a1_a2_core.txt` und kann ergänzt werden — ein Wort
pro Zeile oder mehrere durch Leerzeichen getrennt. Wörter auf dieser Liste
gelten als bekannt und erscheinen nicht in den Tests.

---

## Bereitstellung

### Streamlit Community Cloud (kostenlos, am einfachsten)

1. Repository auf GitHub veröffentlichen.
2. Auf <https://share.streamlit.io> anmelden und **New app** wählen.
3. Repository auswählen, als Hauptdatei `app.py` angeben.
4. Unter **Advanced settings → Secrets** eintragen:

   ```toml
   ANTHROPIC_API_KEY = "sk-ant-..."
   ```

5. **Deploy** — die Anwendung ist unter einer festen Adresse erreichbar.

### Docker

```bash
docker compose up --build
# oder ohne Compose:
docker build -t vocablistmaker .
docker run -p 8501:8501 -e ANTHROPIC_API_KEY=sk-ant-... vocablistmaker
```

### Eigener Server

```bash
pip install -r requirements.txt
streamlit run app.py --server.port 8501 --server.address 0.0.0.0
```

Für den Dauerbetrieb empfiehlt sich ein systemd-Dienst oder ein
Reverse-Proxy (nginx, Caddy) mit HTTPS davor.

---

## Entwicklung

```bash
pip install -r requirements-dev.txt
pytest          # Testlauf
ruff check .    # Linting
```

Die Tests decken die Unit-Erkennung samt Seitenzahlen-Falle, die
Niveaubewertung, alle vier Doppelungsstufen, die Satzprüfungen, das
Word-Layout gegen die Vorlagenmasse und den Gesamtablauf mit und ohne
Sprachmodell ab. Ein Sprachmodell wird für die Tests nicht benötigt.

### Projektstruktur

```
VocabListMaker/
├── app.py                        Weboberfläche (Streamlit)
├── src/vocablistmaker/
│   ├── config.py                 Einstellungen
│   ├── models.py                 Datenmodelle
│   ├── excel_reader.py           Einlesen und Unit-Erkennung
│   ├── normalize.py              Grundformen, Wortfamilien, Wortarten
│   ├── leveling.py               Niveau, Schwierigkeit, Lernwert
│   ├── dedup.py                  Doppelungen und Bedeutungsüberschneidungen
│   ├── selection.py              Auswahl und Aufteilung auf zwei Tests
│   ├── sentences.py              Beispielsätze und deren Prüfung
│   ├── llm.py                    Anbindung an die Claude-API
│   ├── schemas.py                Antwortformate des Sprachmodells
│   ├── enrich.py                 Ersatzwörter
│   ├── validation.py             Qualitätskontrolle
│   ├── layout.py                 Seitenberechnung (passt es auf A4?)
│   ├── curated.py                Kuratierte Inhalte aus dem Chat
│   ├── provenance.py             Herkunftsnachweis gegen die Excel-Datei
│   ├── docx_writer.py            Word-Ausgabe im Vorlagenlayout
│   ├── report.py                 Qualitätsbericht
│   ├── pipeline.py               Gesamtablauf
│   ├── cli.py                    Kommandozeile
│   └── data/                     Grundwortschatz, unzählbare Nomen
├── kuratiert/                    Geprüfte Wortlisten und Beispielsätze
└── tests/
```

---

## Häufige Fragen

**Die Anwendung meldet, eine Unit habe zu wenig Wörter.**
Die Unit enthält nach Abzug von Grundwortschatz und Doppelungen keine 60
geeigneten Einträge. Mit hinterlegtem API-Schlüssel füllt die Anwendung die
Liste mit passenden Ersatzwörtern auf. Alternativ lässt sich mit
`VLM_WORDS_PER_TEST` eine kleinere Testgrösse wählen.

**Die Beispielsätze wirken einförmig.**
Dann lief der regelbasierte Modus. Für Unterrichtsmaterial ist er nicht
gedacht. Es gibt zwei bessere Wege: die Sätze im Chat mit Claude schreiben
lassen (Arbeitsweise A, ohne Schlüssel) oder einen `ANTHROPIC_API_KEY`
hinterlegen. Mit `--keine-mustersaetze` bricht die Anwendung ab, statt
Mustersätze zu erzeugen.

**Passt eine Liste wirklich auf eine Seite?**
Die Anwendung rechnet die Tabellenhöhe vor der Ausgabe aus und meldet den
Füllgrad; über 100 % gibt es einen Fehler. Bei 10 pt und Sätzen bis rund
55 Zeichen liegt die Auslastung bei etwa 92 %.

**Ich möchte ein bestimmtes Wort nie in Tests sehen.**
Es in `src/vocablistmaker/data/a1_a2_core.txt` eintragen.

**Bekomme ich bei gleichem Vorgehen dasselbe Ergebnis?**
Im regelbasierten Modus ja — die Auswahl ist über `VLM_SEED` reproduzierbar.
Das Sprachmodell formuliert Sätze bei jedem Lauf neu.

---

## Lizenz

MIT — siehe [LICENSE](LICENSE).
