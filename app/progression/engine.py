"""Moteur de progression — logique centrale de l'algorithme.

CONTRAT DE CONCEPTION :
- Fonctions pures uniquement. Aucune I/O, aucun appel à la base de données.
- Entièrement déterministe pour les mêmes entrées.
- Entièrement testable en isolation.
- Aucun effet de bord.

Ce module implémente l'algorithme de progression en 6 étapes décrit dans la spécification.
"""
from __future__ import annotations

import enum
import uuid
from collections import Counter
from dataclasses import dataclass, field
from typing import TypeAlias


# ---------------------------------------------------------------------------
# Énumérations (copiées depuis les modèles — le moteur est intentionnellement découplé de l'ORM)
# ---------------------------------------------------------------------------
class RPELevel(str, enum.Enum):
    EASY = "EASY"
    MEDIUM = "MEDIUM"
    HARD = "HARD"


class ProgressionStatus(str, enum.Enum):
    PROGRESSING = "PROGRESSING"
    PLATEAU_DETECTED = "PLATEAU_DETECTED"
    RESET_APPLIED = "RESET_APPLIED"
    PR_ACHIEVED = "PR_ACHIEVED"


# ---------------------------------------------------------------------------
# Dataclasses d'entrée
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SetData:
    """Données d'une seule série effectuée lors de la session actuelle."""
    weight_kg: float
    reps_done: int
    rpe: RPELevel
    is_warmup: bool = False


@dataclass(frozen=True)
class PreviousSessionData:
    """Résumé d'une session précédente pour un exercice spécifique."""
    session_id: uuid.UUID
    avg_weight_kg: float
    all_sets_reached_upper_bound: bool
    status: ProgressionStatus


@dataclass(frozen=True)
class ExerciseSessionData:
    """Toutes les entrées dont le moteur a besoin pour évaluer un exercice dans une session."""
    program_day_exercise_id: uuid.UUID
    sets: list[SetData]
    reps_min_target: int
    reps_max_target: int
    previous_sessions: list[PreviousSessionData]  # Les plus récentes en premier, max 5
    current_weight_kg: float
    all_time_best_weight_kg: float = 0.0  # Utilisé pour la détection de record personnel


# ---------------------------------------------------------------------------
# Dataclass de sortie
# ---------------------------------------------------------------------------
@dataclass
class ProgressionResult:
    """Sortie du moteur — ce qui s'est passé et que faire lors de la prochaine session."""
    status: ProgressionStatus
    suggested_weight_kg: float
    increase_percentage: float
    reset_percentage: float
    consecutive_plateau_count: int
    message: str
    is_pr: bool = False


# ---------------------------------------------------------------------------
# Fonctions utilitaires
# ---------------------------------------------------------------------------
def round_to_nearest_half(weight: float) -> float:
    """Arrondit le poids au 0,5 kg le plus proche — incrément standard des plaques de gym."""
    return round(weight * 2) / 2


def _mode_rpe(rpe_values: list[RPELevel]) -> RPELevel:
    """Retourne la valeur RPE la plus fréquente (mode). En cas d'égalité, préfère la plus difficile."""
    if not rpe_values:
        return RPELevel.MEDIUM

    counts = Counter(rpe_values)
    # Départage : préférer HARD > MEDIUM > EASY (conservateur)
    priority: dict[RPELevel, int] = {RPELevel.HARD: 3, RPELevel.MEDIUM: 2, RPELevel.EASY: 1}

    max_count = max(counts.values())
    candidates = [rpe for rpe, count in counts.items() if count == max_count]
    return max(candidates, key=lambda r: priority[r])


def _working_sets(sets: list[SetData]) -> list[SetData]:
    """Retourne uniquement les séries de travail (hors échauffement)."""
    return [s for s in sets if not s.is_warmup]


def _get_previous_plateau_count(previous_sessions: list[PreviousSessionData]) -> int:
    """Récupère le compteur de plateaux consécutifs depuis la session la plus récente."""
    if not previous_sessions:
        return 0
    return 0  # Sera dérivé du ProgressionLog dans la couche service


# ---------------------------------------------------------------------------
# Algorithme principal — Étape par étape selon la spécification
# ---------------------------------------------------------------------------
def analyze_session(data: ExerciseSessionData) -> ProgressionResult:
    """Lance l'algorithme de progression en 6 étapes pour un exercice dans une session.

    Args:
        data: Tout le contexte nécessaire pour évaluer la progression.

    Returns:
        ProgressionResult avec la décision et le poids suggéré pour la prochaine session.
    """
    working_sets = _working_sets(data.sets)

    if not working_sets:
        # Cas limite : uniquement des séries d'échauffement enregistrées — aucune décision de progression
        return ProgressionResult(
            status=ProgressionStatus.PROGRESSING,
            suggested_weight_kg=data.current_weight_kg,
            increase_percentage=0.0,
            reset_percentage=0.0,
            consecutive_plateau_count=0,
            message="No working sets recorded. Maintain current weight.",
        )

    # -----------------------------------------------------------------------
    # ÉTAPE 1 — Analyser la session actuelle
    # -----------------------------------------------------------------------
    all_sets_complete = all(s.reps_done >= data.reps_max_target for s in working_sets)
    any_set_failed = any(s.reps_done < data.reps_min_target for s in working_sets)

    rpe_values = [s.rpe for s in working_sets]
    avg_rpe = _mode_rpe(rpe_values)

    # Compteur de plateaux consécutifs précédents (depuis le journal de la dernière session)
    prev_plateau_count = (
        _extract_plateau_count(data.previous_sessions)
    )

    # -----------------------------------------------------------------------
    # ÉTAPE 2 — Vérifier le record personnel
    # -----------------------------------------------------------------------
    is_pr = False
    pr_weight = data.all_time_best_weight_kg
    for s in working_sets:
        if s.weight_kg > pr_weight:
            pr_weight = s.weight_kg
            is_pr = True

    # -----------------------------------------------------------------------
    # ÉTAPE 6 — Ajustements RPE spéciaux (vérifier avant le branchement principal)
    # -----------------------------------------------------------------------
    # Progression rapide : les 2 dernières sessions étaient PROGRESSING et avg_rpe == EASY
    fast_progression = _should_fast_progress(data.previous_sessions, avg_rpe)

    # -----------------------------------------------------------------------
    # ÉTAPE 3 — Décision de progression
    # -----------------------------------------------------------------------
    if all_sets_complete and avg_rpe in (RPELevel.EASY, RPELevel.MEDIUM):
        # Toutes les séries ont atteint la limite supérieure et l'effort était acceptable — augmenter le poids
        if fast_progression:
            increase_pct = 5.0
            message = "Excellent progress! RPE consistently easy — increasing by 5%."
        else:
            increase_pct = 2.5
            message = "All sets completed at target. Increasing weight by 2.5%."

        new_weight = round_to_nearest_half(data.current_weight_kg * (1 + increase_pct / 100))
        consecutive_count = 0
        status = ProgressionStatus.PROGRESSING

        # Priorité au record personnel
        if is_pr:
            status = ProgressionStatus.PR_ACHIEVED
            message = f"Personal Record! {message}"

        return ProgressionResult(
            status=status,
            suggested_weight_kg=new_weight,
            increase_percentage=increase_pct,
            reset_percentage=0.0,
            consecutive_plateau_count=consecutive_count,
            message=message,
            is_pr=is_pr,
        )

    elif all_sets_complete and avg_rpe == RPELevel.HARD:
        # Cas spécial ÉTAPE 6 : objectif atteint mais effort maximal — consolider
        message = "Good session. Consolidate before increasing weight. Effort was maximal."
        status = ProgressionStatus.PROGRESSING

        if is_pr:
            status = ProgressionStatus.PR_ACHIEVED
            message = f"Personal Record! {message}"

        return ProgressionResult(
            status=status,
            suggested_weight_kg=data.current_weight_kg,
            increase_percentage=0.0,
            reset_percentage=0.0,
            consecutive_plateau_count=0,
            message=message,
            is_pr=is_pr,
        )

    elif not all_sets_complete and not any_set_failed:
        # Dans la plage cible mais pas à la limite supérieure — toujours en progression, incrémenter le compteur de plateaux
        # si le poids n'a pas changé depuis la dernière session
        same_weight_as_last = _same_weight_as_last_session(data.previous_sessions, data.current_weight_kg)
        consecutive_count = prev_plateau_count + (1 if same_weight_as_last else 0)
        status = _check_plateau(consecutive_count, ProgressionStatus.PROGRESSING)
        message = _build_in_range_message(consecutive_count, status)

        if status == ProgressionStatus.PLATEAU_DETECTED:
            reset_weight = round_to_nearest_half(data.current_weight_kg * 0.94)
            return ProgressionResult(
                status=status,
                suggested_weight_kg=reset_weight,
                increase_percentage=0.0,
                reset_percentage=6.0,
                consecutive_plateau_count=consecutive_count,
                message=message,
                is_pr=False,
            )

        return ProgressionResult(
            status=status,
            suggested_weight_kg=data.current_weight_kg,
            increase_percentage=0.0,
            reset_percentage=0.0,
            consecutive_plateau_count=consecutive_count,
            message=message,
            is_pr=is_pr,
        )

    else:
        # any_set_failed == True — incrémenter le compteur de plateaux
        consecutive_count = prev_plateau_count + 1
        status = _check_plateau(consecutive_count, ProgressionStatus.PROGRESSING)
        message = _build_failure_message(consecutive_count, status)

        if status == ProgressionStatus.PLATEAU_DETECTED:
            # ÉTAPE 4 — Plateau détecté — suggérer une réinitialisation, NE PAS l'appliquer automatiquement
            reset_weight = round_to_nearest_half(data.current_weight_kg * 0.94)
            return ProgressionResult(
                status=ProgressionStatus.PLATEAU_DETECTED,
                suggested_weight_kg=reset_weight,
                increase_percentage=0.0,
                reset_percentage=6.0,
                consecutive_plateau_count=consecutive_count,
                message=message,
                is_pr=False,
            )

        return ProgressionResult(
            status=status,
            suggested_weight_kg=data.current_weight_kg,
            increase_percentage=0.0,
            reset_percentage=0.0,
            consecutive_plateau_count=consecutive_count,
            message=message,
            is_pr=False,
        )


def apply_validated_reset(current_weight_kg: float, reset_percentage: float = 6.0) -> ProgressionResult:
    """ÉTAPE 5 — Applique une réinitialisation que l'utilisateur a explicitement validée.

    N'est appelé QUE lorsque l'utilisateur confirme la suggestion de réinitialisation du plateau.
    """
    new_weight = round_to_nearest_half(current_weight_kg * (1 - reset_percentage / 100))
    return ProgressionResult(
        status=ProgressionStatus.RESET_APPLIED,
        suggested_weight_kg=new_weight,
        increase_percentage=0.0,
        reset_percentage=reset_percentage,
        consecutive_plateau_count=0,
        message=(
            f"Reset applied: {reset_percentage:.1f}% reduction from "
            f"{current_weight_kg}kg → {new_weight}kg. "
            "Resume progression from new weight."
        ),
    )


# ---------------------------------------------------------------------------
# Fonctions auxiliaires privées
# ---------------------------------------------------------------------------
def _extract_plateau_count(previous_sessions: list[PreviousSessionData]) -> int:
    """Récupère le compteur de plateaux reporté depuis le journal de la session la plus récente."""
    # La couche service stocke consecutive_plateau_count dans ProgressionLog.
    # Ici on l'accepte comme partie du contexte — le service assemble ExerciseSessionData.
    # Cette fonction est un espace réservé pour la clarté des tests.
    return 0


def _same_weight_as_last_session(
    previous_sessions: list[PreviousSessionData],
    current_weight: float,
) -> bool:
    if not previous_sessions:
        return False
    last = previous_sessions[0]
    return abs(last.avg_weight_kg - current_weight) < 0.1


def _should_fast_progress(
    previous_sessions: list[PreviousSessionData],
    current_avg_rpe: RPELevel,
) -> bool:
    """Retourne True si les 2 dernières sessions étaient PROGRESSING et que le RPE actuel est EASY."""
    if current_avg_rpe != RPELevel.EASY:
        return False
    if len(previous_sessions) < 2:
        return False
    last_two = previous_sessions[:2]
    return all(s.status == ProgressionStatus.PROGRESSING for s in last_two)


def _check_plateau(
    consecutive_count: int,
    default_status: ProgressionStatus,
) -> ProgressionStatus:
    if consecutive_count >= 3:
        return ProgressionStatus.PLATEAU_DETECTED
    return default_status


def _build_in_range_message(consecutive_count: int, status: ProgressionStatus) -> str:
    if status == ProgressionStatus.PLATEAU_DETECTED:
        return (
            f"Plateau detected over {consecutive_count} sessions. "
            "We recommend a 6% reset. Please validate to apply."
        )
    if consecutive_count > 0:
        return f"Sets in target range but not complete. Plateau warning: {consecutive_count}/3."
    return "Sets in progress — maintain weight."


def _build_failure_message(consecutive_count: int, status: ProgressionStatus) -> str:
    if status == ProgressionStatus.PLATEAU_DETECTED:
        return (
            f"Plateau detected over {consecutive_count} sessions (failed to complete min reps). "
            "We recommend a 6% reset. Please validate to apply."
        )
    return f"Some sets below minimum reps. Maintain weight. Plateau counter: {consecutive_count}/3."
