# Arbeitsanweisungen für dieses Repository

## Wie die Inhalte entstehen

Die Beispielsätze und die endgültige Wortauswahl werden **im Chat vom Modell
selbst geschrieben**, nicht von der Anwendung erzeugt. Der regelbasierte
Mustersatz-Modus (`sentences.build_sentence`) ist ausdrücklich **nicht** für
Unterrichtsmaterial gedacht — er ist nur eine Notfallebene und liefert Sätze
wie „We talked about a pendant in our lesson last week.“

Ablauf je Durchlauf:

1. `vocablistmaker <excel> "Unit N" --no-llm --export-auswahl kuratiert/unit_N.json`
2. Die Felder `satz` im Chat ausfüllen — natürlich, idiomatisch,
   abwechslungsreich, B1.2–B2.1, mit erschliessbarem Kontext, ohne die Lösung
   zu verraten, grammatikalisch fehlerfrei.
3. Die eigenen Sätze anschliessend selbst noch einmal auf Grammatik,
   Natürlichkeit, Niveau und verratene Lösung durchsehen.
4. `vocablistmaker --aus-datei kuratiert/unit_N.json -o Vocabulary_Unit_N.docx --herkunft <excel>`

## Pflicht: Herkunft immer im Chat berichten

Bei **jedem** Durchlauf gehört in die Chat-Antwort, ohne dass danach gefragt
werden muss:

* **Weggelassen** — welche Wörter der Unit nicht in die Tests kamen, gruppiert
  nach Grund (zu einfach, Kognat, Grundwortschatz, früher gelernt, …).
* **Ersetzt** — welches Wort durch welches ersetzt wurde und warum.
* **Herkunftsabschnitt** — aus welchem Abschnitt jedes Wort stammt. „Steht in
  der Excel-Datei“ genügt nicht: Ein Wort aus `Songs 7` oder `Culture 7` ist
  etwas anderes als eines aus dem Hauptteil `Unit 7`, auch wenn beide zur
  selben Unit zählen.
* **Eigene Ergänzungen** — als **eindeutige Tabelle** (Englisch | Deutsch),
  mit Anteil in Prozent. Steht keines darin, wird das ausdrücklich gesagt.
* **Geänderte Übersetzungen** — jede Abweichung von der deutschen Glosse der
  Excel-Datei, mit Vorher/Nachher.

`vocablistmaker --aus-datei … --herkunft <excel>` erzeugt genau diese
Aufstellung (`provenance.py`). Die Angaben stammen aus dem Abgleich mit der
Excel-Datei, nicht aus dem Gedächtnis.

## Umfang einer Unit — verbindlich: nur der Hauptteil

Es zählt **ausschliesslich der Hauptteil** einer Unit, also der Block
`Unit N` mit seinem zusammenhängenden Seitenbereich (Unit 7: S. 68–77,
Unit 8: S. 78–87). `Culture N`, `Curriculum extra N`, `Project N`, `Songs N`
und `Extra Listening and Speaking Unit N` gehören **nicht** dazu.
Immer mit `--nur-hauptteil` bzw. `VLM_CORE_ONLY=true` arbeiten.

Der Hauptteil liefert nie 60 brauchbare Wörter (Unit 7: 41, Unit 8: 33).
Die Lücke wird **im Chat mit selbst erfundenen Wörtern gefüllt**. Diese
müssen:

* zum Thema der Unit passen (Unit 7: Bürgerrechte und Engagement,
  Unit 8: Filme und Geschichten),
* im Englischen wirklich gebräuchlich sein (Zipf etwa 3,0–4,6),
* für B1.2–B2.1 einen echten Zugewinn für den sprachlichen Ausdruck bieten,
* mit keinem vorhandenen Wort kollidieren.

**Höchstens 40 % der 60 Wörter dürfen ergänzt sein** (also maximal 24).
Reicht das nicht, werden zuerst Grenzfälle aus dem Hauptteil wieder
zugelassen, bevor weiter ergänzt wird.

## Layout

Jede Liste muss auf **eine A4-Seite** passen. Voreingestellt sind 10 pt und
Zeilenhöhe 340; `check_page_fit` rechnet das vorher aus und meldet Überlauf
als Fehler. Beispielsätze möglichst unter 55 Zeichen halten.

## Tests

`pytest` und `ruff check src tests app.py` müssen grün sein. Die mitgelieferten
Listen unter `kuratiert/` werden mitgeprüft und dürfen keine Fehler zeigen.
