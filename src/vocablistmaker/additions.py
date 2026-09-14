"""Planung der Ergänzungen: wie viele Einzelwörter, wie viele Ausdrücke.

Der Hauptteil einer Unit liefert selten 60 brauchbare Wörter. Die Lücke wird
im Chat gefüllt — getrennt nach zwei Arten, weil sie unterschiedlich viel
bringen:

* **Einzelwörter** (``prejudice``, ``refugee``) erweitern den Wortschatz.
* **Ausdrücke** (``stand up for``, ``make a difference``) sind für Lernende
  oft wertvoller: Ihre Bedeutung lässt sich nicht aus den Bestandteilen
  ableiten, und sie verbessern den sprachlichen Ausdruck unmittelbar.
* **Chunks** (``What stood out to me was …``) sind Satzrahmen mit offener
  Stelle. Sie bestehen aus lauter Alltagswörtern, sind aber genau das, was
  Lernenden beim freien Sprechen und Schreiben fehlt. Ihr Beispielsatz
  *vervollständigt* den Rahmen, statt ihn nur zu enthalten.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Höchstanteil selbst ergänzter Einträge an einer Liste.
MAX_ADDITION_SHARE = 0.40


class AdditionPlanError(ValueError):
    """Die gewünschte Aufteilung ist nicht umsetzbar."""


@dataclass(frozen=True)
class AdditionPlan:
    """Wie sich eine Liste zusammensetzt."""

    target: int
    from_workbook: int
    extra_words: int
    extra_expressions: int
    extra_chunks: int = 0
    warnings: tuple[str, ...] = ()

    @property
    def extra_total(self) -> int:
        return self.extra_words + self.extra_expressions + self.extra_chunks

    @property
    def share(self) -> float:
        return self.extra_total / self.target if self.target else 0.0

    @property
    def within_cap(self) -> bool:
        return self.share <= MAX_ADDITION_SHARE + 1e-9

    def describe(self) -> str:
        return (
            f"{self.target} Einträge: {self.from_workbook} aus dem Hauptteil, "
            f"{self.extra_words} ergänzte Einzelwörter, "
            f"{self.extra_expressions} ergänzte Ausdrücke, "
            f"{self.extra_chunks} ergänzte Chunks "
            f"({self.share:.0%} ergänzt)"
        )


def max_additions(target: int) -> int:
    """Wie viele Einträge einer Liste höchstens ergänzt sein dürfen."""
    return int(target * MAX_ADDITION_SHARE)


def plan_additions(
    available: int,
    target: int,
    extra_words: int | None = None,
    extra_expressions: int | None = None,
    extra_chunks: int | None = None,
) -> AdditionPlan:
    """Bestimmt die Zusammensetzung einer Liste.

    ``available`` ist die Zahl geprüfter Wörter aus dem Hauptteil.
    Sind alle drei Mengenangaben ``None``, wird nur die Lücke gefüllt und
    nicht nach Art getrennt (alles gilt als Einzelwort). Ist mindestens eine
    gesetzt, bestimmen die Vorgaben die Aufteilung — notfalls rücken dafür
    weniger Wörter aus dem Hauptteil nach.

    Ein Anteil über 40 % ist zulässig, wird aber als Warnung vermerkt.
    """
    if target <= 0:
        raise AdditionPlanError("Die Liste muss mindestens einen Eintrag haben.")

    deficit = max(0, target - available)
    cap = max_additions(target)

    def cap_warning(total: int) -> tuple[str, ...]:
        if total <= cap:
            return ()
        return (
            f"{total} von {target} Einträgen sind ergänzt "
            f"({total / target:.0%}). Das liegt über der Richtgrösse von "
            f"{MAX_ADDITION_SHARE:.0%} ({cap} Einträge). Der Hauptteil gibt "
            f"nur {available} brauchbare Wörter her.",
        )

    if extra_words is None and extra_expressions is None and extra_chunks is None:
        return AdditionPlan(
            target, target - deficit, deficit, 0, 0, cap_warning(deficit)
        )

    words = max(0, extra_words or 0)
    expressions = max(0, extra_expressions or 0)
    chunks = max(0, extra_chunks or 0)
    total = words + expressions + chunks

    if total > target:
        raise AdditionPlanError(
            f"{total} Ergänzungen passen nicht in eine Liste mit {target} Einträgen."
        )
    if total < deficit:
        raise AdditionPlanError(
            f"Der Hauptteil liefert nur {available} von {target} Einträgen. "
            f"Es fehlen {deficit}, angefordert sind aber nur {total} "
            "Ergänzungen. Bitte die Anzahl erhöhen."
        )

    return AdditionPlan(
        target, target - total, words, expressions, chunks, cap_warning(total)
    )


def classify(english: str) -> str:
    """``"Chunk"``, ``"Ausdruck"`` oder ``"Wort"``."""
    from .normalize import headword, is_chunk

    if is_chunk(english):
        return "Chunk"
    return "Ausdruck" if len(headword(english).split()) > 1 else "Wort"
