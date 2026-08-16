"""Agrégats pour le tableau de bord.

Tout est calculé en base : rapatrier les analyses pour les compter côté client
ne tiendrait pas au-delà de quelques centaines de lignes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import Select, and_, extract, func, select
from sqlalchemy.orm import Session

from app.ai import CLASS_NAMES
from app.ai.inference import is_placeholder_version
from app.models.analysis import Analysis, AnalysisStatus
from app.models.patient import Patient

logger = logging.getLogger(__name__)

MONTHS_SHOWN = 12


@dataclass(frozen=True, slots=True)
class MonthlyBucket:
    month: str
    total: int
    benign: int
    malignant: int


@dataclass(frozen=True, slots=True)
class DashboardStats:
    total_patients: int
    total_analyses: int
    completed_analyses: int
    pending_analyses: int
    failed_analyses: int
    benign_count: int
    malignant_count: int
    average_inference_time_ms: float | None
    doctor_validated_count: int
    doctor_validation_rate: float | None
    model_versions: list[str]
    is_placeholder_model: bool
    clinically_validated: bool
    monthly: list[MonthlyBucket] = field(default_factory=list)


def _completed() -> Select:
    return select(Analysis).where(Analysis.status == AnalysisStatus.COMPLETED.value)


def _all_analyses_validated(db: Session) -> bool:
    """Aucune analyse terminée ne provient-elle d'un modèle non validé ?

    Formulé par la négative — on cherche un contre-exemple — pour que le cas
    incertain retombe du côté prudent.
    """
    unvalidated = db.scalar(
        select(func.count())
        .select_from(Analysis)
        .where(
            Analysis.status == AnalysisStatus.COMPLETED.value,
            Analysis.clinically_validated.is_(False),
        )
    )
    return not unvalidated


def _count(db: Session, *conditions) -> int:
    statement = select(func.count()).select_from(Analysis)
    if conditions:
        statement = statement.where(and_(*conditions))
    return db.scalar(statement) or 0


def _month_range(reference: datetime, months: int = MONTHS_SHOWN) -> list[tuple[int, int]]:
    """Les `months` derniers mois, du plus ancien au plus récent, bornes incluses."""
    year, month = reference.year, reference.month
    buckets: list[tuple[int, int]] = []

    for offset in range(months - 1, -1, -1):
        total_months = year * 12 + (month - 1) - offset
        buckets.append((total_months // 12, total_months % 12 + 1))

    return buckets


def _monthly_counts(db: Session, reference: datetime) -> list[MonthlyBucket]:
    """Répartition mensuelle des analyses terminées.

    `extract` est utilisé plutôt que `date_trunc` (PostgreSQL) ou `strftime`
    (SQLite) : SQLAlchemy le traduit pour les deux, et les tests tournent sur
    SQLite alors que la production tourne sur PostgreSQL.
    """
    rows = db.execute(
        select(
            extract("year", Analysis.created_at).label("year"),
            extract("month", Analysis.created_at).label("month"),
            Analysis.prediction,
            func.count().label("total"),
        )
        .where(Analysis.status == AnalysisStatus.COMPLETED.value)
        .group_by("year", "month", Analysis.prediction)
    ).all()

    # (année, mois) -> {prédiction: total}
    tally: dict[tuple[int, int], dict[str, int]] = {}
    for year, month, prediction, total in rows:
        key = (int(year), int(month))
        tally.setdefault(key, {})[prediction or ""] = int(total)

    buckets: list[MonthlyBucket] = []
    for year, month in _month_range(reference):
        counts = tally.get((year, month), {})
        benign = counts.get(CLASS_NAMES[0], 0)
        malignant = counts.get(CLASS_NAMES[1], 0)
        buckets.append(
            MonthlyBucket(
                month=f"{year:04d}-{month:02d}",
                total=sum(counts.values()),
                benign=benign,
                malignant=malignant,
            )
        )

    return buckets


def build_dashboard(db: Session, *, now: datetime | None = None) -> DashboardStats:
    """Assemble les indicateurs du tableau de bord."""
    reference = now or datetime.now(UTC)

    total_patients = (
        db.scalar(
            select(func.count()).select_from(Patient).where(Patient.is_deleted.is_(False))
        )
        or 0
    )

    completed_condition = Analysis.status == AnalysisStatus.COMPLETED.value

    total_analyses = _count(db)
    completed = _count(db, completed_condition)
    pending = _count(
        db,
        Analysis.status.in_(
            [AnalysisStatus.PENDING.value, AnalysisStatus.PROCESSING.value]
        ),
    )
    failed = _count(db, Analysis.status == AnalysisStatus.FAILED.value)

    benign = _count(db, completed_condition, Analysis.prediction == CLASS_NAMES[0])
    malignant = _count(db, completed_condition, Analysis.prediction == CLASS_NAMES[1])

    average_time = db.scalar(
        select(func.avg(Analysis.inference_time_ms)).where(
            completed_condition, Analysis.inference_time_ms.is_not(None)
        )
    )

    validated = _count(db, completed_condition, Analysis.doctor_validated.is_(True))

    versions = [
        version
        for version in db.scalars(
            select(Analysis.model_version)
            .where(Analysis.model_version.is_not(None))
            .distinct()
        )
        if version
    ]

    return DashboardStats(
        total_patients=total_patients,
        total_analyses=total_analyses,
        completed_analyses=completed,
        pending_analyses=pending,
        failed_analyses=failed,
        benign_count=benign,
        malignant_count=malignant,
        average_inference_time_ms=float(average_time) if average_time is not None else None,
        doctor_validated_count=validated,
        # Taux de relecture, et non taux d'exactitude : voir la note portée par
        # le schéma de réponse.
        doctor_validation_rate=(validated / completed) if completed else None,
        model_versions=sorted(versions),
        is_placeholder_model=any(is_placeholder_version(version) for version in versions),
        # `all` et non `any` : il suffit d'une analyse issue d'un modèle non
        # validé pour que le tableau de bord doive porter l'avertissement. Un
        # tableau vide n'est pas non plus une validation — d'où le `and`.
        clinically_validated=bool(completed) and _all_analyses_validated(db),
        monthly=_monthly_counts(db, reference),
    )
