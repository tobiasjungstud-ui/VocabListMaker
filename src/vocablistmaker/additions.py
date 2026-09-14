"""Planung der Ergänzungen: wie viele Einzelwörter, wie viele Ausdrücke.

Der Hauptteil einer Unit liefert selten 60 brauchbare Wörter. Die Lücke wird
im Chat gefüllt — getrennt nach zwei Arten, weil sie unterschiedlich viel
bringen:

* **Einzelwörter** (``prejudice``, ``refugee``) erweitern den Wortschatz.
* **Ausdrücke** (``stand up for``, ``make a difference``) sind für Lernende
  oft wertvoller: Ihre Bedeutung lässt sich nicht aus den Bestandteilen
  ableiten, und sie verbessern den sprachlichen Ausdruck unmittelbar.
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

    @property
    def extra_total(self) -> int:
        return self.extra_words + self.extra_expressions

    @property
    def share(self) -> float:
        return self.extra_total / self.target if self.target else 0.0

    @property
    def within_cap(self) -> bool:
        return self.share <= MAX_ADDITION_SHARE + 1e-9

    def describe(self) -> str:
        return (
            f"{self.target} Wörter: {self.from_workbook} aus dem Hauptteil, "
            f"{self.extra_words} ergänzte Einzelwörter, "
            f"{self.extra_expressions} ergänzte Ausdrücke "
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
) -> AdditionPlan:
    """Bestimmt die Zusammensetzung einer Liste.

    ``available`` ist die Zahl geprüfter Wörter aus dem Hauptteil.
    Sind ``extra_words`` und ``extra_expressions`` beide ``None``, wird nur
    die Lücke gefüllt und nicht nach Art getrennt (alles gilt als Einzelwort).
    Ist mindestens einer der Werte gesetzt, bestimmen die Vorgaben die
    Aufteilung — notfalls rücken dafür weniger Wörter aus dem Hauptteil nach.
    """
    if target <= 0:
        raise AdditionPlanError("Die Liste muss mindestens einen Eintrag haben.")

    deficit = max(0, target - available)
    cap = max_additions(target)

    if extra_words is None and extra_expressions is None:
        if deficit > cap:
            raise AdditionPlanError(
                f"Der Hauptteil liefert nur {available} von {target} Wörtern. "
                f"Es müssten {deficit} ergänzt werden, erlaubt sind höchstens "
                f"{cap} ({MAX_ADDITION_SHARE:.0%}). Bitte Grenzfälle aus dem "
                "Hauptteil zulassen oder die Testgrösse verringern."
            )
        return AdditionPlan(target, target - deficit, deficit, 0)

    words = max(0, extra_words or 0)
    expressions = max(0, extra_expressions or 0)
    total = words + expressions

    if total > cap:
        raise AdditionPlanError(
            f"{total} Ergänzungen sind zu viele: Bei {target} Einträgen sind "
            f"höchstens {cap} erlaubt ({MAX_ADDITION_SHARE:.0%})."
        )
    if total < deficit:
        if deficit > cap:
            raise AdditionPlanError(
                f"Der Hauptteil liefert nur {available} von {target} Wörtern. "
                f"Die Lücke von {deficit} lässt sich nicht durch Ergänzungen "
                f"schliessen, weil höchstens {cap} erlaubt sind "
                f"({MAX_ADDITION_SHARE:.0%}). Es müssen mindestens "
                f"{target - cap - available} Grenzfälle aus dem Hauptteil "
                "wieder zugelassen werden."
            )
        raise AdditionPlanError(
            f"Der Hauptteil liefert nur {available} von {target} Wörtern. "
            f"Es fehlen {deficit}, angefordert sind aber nur {total} "
            "Ergänzungen. Bitte die Anzahl erhöhen."
        )
    if total > target:
        raise AdditionPlanError(
            f"{total} Ergänzungen passen nicht in eine Liste mit {target} Einträgen."
        )

    return AdditionPlan(target, target - total, words, expressions)


def classify(english: str) -> str:
    """``"Ausdruck"`` bei mehreren Wörtern, sonst ``"Wort"``."""
    from .normalize import headword

    return "Ausdruck" if len(headword(english).split()) > 1 else "Wort"
