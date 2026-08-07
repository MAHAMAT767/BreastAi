"""Tests des modèles : contraintes, relations, valeurs par défaut."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.roles import UserRole
from app.models.analysis import Analysis, AnalysisStatus
from app.models.patient import Patient
from app.models.user import User
from app.services import user_service


def make_patient(db: Session, code: str = "TCD-2026-0001") -> Patient:
    patient = Patient(
        code=code,
        first_name="Amina",
        last_name="Ali",
        birth_date=date(1980, 5, 12),
        sex="F",
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


# --------------------------------------------------------------------------- #
# User
# --------------------------------------------------------------------------- #


def test_user_defaults(db: Session) -> None:
    user = user_service.create_user(
        db, email="a@breastai.td", password="MotDePasseTest-2026", full_name="A"
    )

    assert user.role == UserRole.DOCTOR
    assert user.is_active is True
    assert user.password_changed_at is not None
    assert user.created_at is not None


def test_email_is_stored_lowercase(db: Session) -> None:
    user = user_service.create_user(
        db, email="  MAJUSCULE@breastai.td ", password="MotDePasseTest-2026", full_name="A"
    )

    assert user.email == "majuscule@breastai.td"


def test_duplicate_email_raises(db: Session) -> None:
    user_service.create_user(
        db, email="a@breastai.td", password="MotDePasseTest-2026", full_name="A"
    )

    with pytest.raises(user_service.EmailAlreadyUsedError):
        user_service.create_user(
            db, email="a@breastai.td", password="MotDePasseTest-2026", full_name="B"
        )


def test_unknown_role_violates_the_check_constraint(db: Session) -> None:
    db.add(
        User(
            email="b@breastai.td",
            hashed_password="x",
            full_name="B",
            role="chef-de-service",
        )
    )

    with pytest.raises(IntegrityError):
        db.commit()


def test_password_is_never_stored_in_clear(db: Session) -> None:
    user = user_service.create_user(
        db, email="c@breastai.td", password="MotDePasseTest-2026", full_name="C"
    )

    assert "MotDePasseTest-2026" not in user.hashed_password


# --------------------------------------------------------------------------- #
# Patient
# --------------------------------------------------------------------------- #


def test_patient_full_name(db: Session) -> None:
    patient = make_patient(db)

    assert patient.full_name == "Amina Ali"


def test_patient_code_is_unique(db: Session) -> None:
    make_patient(db, "TCD-2026-0001")
    db.add(Patient(code="TCD-2026-0001", first_name="X", last_name="Y", sex="F"))

    with pytest.raises(IntegrityError):
        db.commit()


def test_unknown_sex_violates_the_check_constraint(db: Session) -> None:
    db.add(Patient(code="TCD-2026-0002", first_name="X", last_name="Y", sex="Z"))

    with pytest.raises(IntegrityError):
        db.commit()


def test_male_patient_is_allowed(db: Session) -> None:
    """Le cancer du sein masculin est rare mais réel : il ne doit pas être exclu."""
    db.add(Patient(code="TCD-2026-0003", first_name="Idriss", last_name="Ali", sex="M"))
    db.commit()

    assert db.scalar(select(Patient).where(Patient.sex == "M")) is not None


def test_patient_soft_delete_defaults_to_false(db: Session) -> None:
    assert make_patient(db).is_deleted is False


# --------------------------------------------------------------------------- #
# Analysis
# --------------------------------------------------------------------------- #


def test_analysis_starts_pending_without_result(db: Session) -> None:
    patient = make_patient(db)
    analysis = Analysis(
        patient_id=patient.id, original_filename="mammo.dcm", image_path="/uploads/mammo.dcm"
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    assert analysis.status == AnalysisStatus.PENDING
    assert analysis.prediction is None
    assert analysis.probability is None
    assert analysis.doctor_validated is False


def test_probability_outside_zero_one_is_refused(db: Session) -> None:
    """Une probabilité hors [0, 1] signale un bug d'inférence : la base doit le bloquer."""
    patient = make_patient(db)
    db.add(
        Analysis(
            patient_id=patient.id,
            original_filename="m.png",
            image_path="/uploads/m.png",
            probability=1.4,
        )
    )

    with pytest.raises(IntegrityError):
        db.commit()


def test_unknown_prediction_label_is_refused(db: Session) -> None:
    patient = make_patient(db)
    db.add(
        Analysis(
            patient_id=patient.id,
            original_filename="m.png",
            image_path="/uploads/m.png",
            prediction="peut-etre",
        )
    )

    with pytest.raises(IntegrityError):
        db.commit()


def test_valid_result_is_accepted(db: Session) -> None:
    patient = make_patient(db)
    analysis = Analysis(
        patient_id=patient.id,
        original_filename="m.png",
        image_path="/uploads/m.png",
        status=AnalysisStatus.COMPLETED.value,
        prediction="malignant",
        probability=0.87,
        confidence=0.87,
        inference_time_ms=142.5,
        model_version="efficientnet-b0-v0.1",
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    assert analysis.prediction == "malignant"
    assert analysis.model_version == "efficientnet-b0-v0.1"


def test_analyses_follow_their_patient(db: Session) -> None:
    patient = make_patient(db)
    db.add(
        Analysis(
            patient_id=patient.id, original_filename="m.png", image_path="/uploads/m.png"
        )
    )
    db.commit()
    db.refresh(patient)

    assert len(patient.analyses) == 1
    assert patient.analyses[0].patient is patient
