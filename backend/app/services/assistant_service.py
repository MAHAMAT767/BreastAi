"""Assistant conversationnel : explication en langage naturel d'une analyse.

## Ce que le modèle voit, et ce qu'il ne voit pas

Le contexte transmis au fournisseur contient les sorties du modèle d'analyse,
l'âge et le sexe. Il ne contient **ni nom, ni code dossier, ni date de naissance,
ni téléphone, ni adresse, ni commentaire du médecin**.

L'âge et le sexe sont conservés parce qu'ils conditionnent la lecture d'une
mammographie ; seuls, ils n'identifient personne. Le commentaire du médecin est
volontairement exclu bien qu'il soit cliniquement le plus riche : c'est du texte
libre, et rien n'empêche un praticien d'y écrire un nom. Le faire sortir vers un
service tiers pour améliorer une réponse ne vaut pas ce risque.

## Ce qui ne dépend pas du modèle

Les avertissements ne sont **pas** confiés au modèle de langage. Ils sont ajoutés
par le code, avant et après sa réponse.

Ce n'est pas de la prudence excessive : à la mise au point, interrogé sur un
résultat chiffré avec une consigne système explicite, le modèle a omis de
signaler le caractère de démonstration une fois sur deux, et a accepté la
prémisse fausse « pourquoi cette image est-elle suspecte ? » alors que la
classification produite était bénigne. Un garde-fou qu'on demande poliment n'est
pas un garde-fou.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Final

import httpx

from app.ai.inference import is_placeholder_version
from app.config import settings
from app.disclaimer import (
    GRADCAM_DISCLAIMER,
    MEDICAL_DISCLAIMER,
    ModelStatus,
    derive_model_status,
    model_warning_for,
)
from app.models.analysis import Analysis, AnalysisStatus
from app.models.patient import Patient

logger = logging.getLogger(__name__)

MAX_QUESTION_LENGTH: Final[int] = 1000


class AssistantError(Exception):
    """Échec générique de l'assistant."""


class AssistantDisabledError(AssistantError):
    """Aucun jeton n'est configuré : la fonctionnalité est éteinte."""


class AssistantQuotaError(AssistantError):
    """Le crédit du fournisseur est épuisé (HTTP 402) ou le débit dépassé (429)."""


class AssistantUnavailableError(AssistantError):
    """Le fournisseur n'a pas répondu à temps, ou a renvoyé une erreur serveur."""


@dataclass(frozen=True, slots=True)
class AssistantMessage:
    role: str
    content: str


@dataclass(frozen=True, slots=True)
class AssistantAnswer:
    #: Texte complet : avertissements compris. C'est celui à copier ou à citer.
    answer: str
    #: Réponse brute du modèle, sans les avertissements. Permet à l'interface de
    #: les présenter avec leur mise en forme propre plutôt que noyés dans un
    #: bloc de texte — sans jamais avoir à les redécouper à partir de `answer`.
    answer_body: str
    model: str
    disclaimer: str = MEDICAL_DISCLAIMER
    is_placeholder_model: bool = False
    clinically_validated: bool = False
    model_warning: str | None = None
    context_sent: str = ""
    usage: dict[str, int] = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Consigne système
# --------------------------------------------------------------------------- #

#: Les règles sont écrites une par ligne, en concaténation implicite, pour tenir
#: dans la largeur du fichier sans introduire de retours à la ligne au milieu
#: d'une phrase du prompt.
SYSTEM_PROMPT: Final[str] = "\n".join(
    [
        "Tu es l'assistant de BreastAI, une plateforme d'aide au dépistage du "
        "cancer du sein.",
        "",
        "Ton rôle : expliquer à un professionnel de santé ce que le modèle "
        "d'analyse a produit, et ce que ces sorties signifient. Tu es un outil "
        "pédagogique, pas un avis médical.",
        "",
        "RÈGLES ABSOLUES",
        "1. Tu ne poses aucun diagnostic et ne recommandes aucune conduite "
        "thérapeutique, aucun examen complémentaire, aucun délai de contrôle.",
        "2. Tu ne parles que de ce qui figure dans le contexte fourni. Si la "
        "question demande une information absente, tu réponds que le contexte "
        "ne permet pas de l'affirmer.",
        "3. Si une question présuppose un fait que le contexte contredit, tu "
        "corriges la prémisse avant de répondre. Exemple : si l'on demande "
        "pourquoi une image est « suspecte » alors que la classification "
        "produite est bénigne, tu commences par le signaler.",
        "4. La carte Grad-CAM indique les régions ayant influencé la décision "
        "du modèle, jamais l'emplacement d'une lésion. Ne laisse jamais "
        "entendre le contraire.",
        "5. Une probabilité n'est pas un pourcentage de risque pour la "
        "patiente : c'est la sortie numérique d'un classifieur.",
        "6. Tu réponds en français, dans un registre professionnel, en cinq "
        "phrases au maximum.",
        "7. Tu ne t'adresses jamais à la patiente : ton interlocuteur est un "
        "soignant.",
    ]
)

PLACEHOLDER_SYSTEM_RULE: Final[str] = "\n" + (
    "8. IMPORTANT : le modèle qui a produit ces résultats est un modèle de "
    "DÉMONSTRATION, jamais entraîné sur des mammographies. Sa classification, "
    "sa probabilité et sa carte Grad-CAM sont des valeurs arbitraires. Tu ne "
    "dois jamais expliquer ces chiffres comme s'ils décrivaient le cliché. Si "
    "l'on t'interroge dessus, tu commences par rappeler qu'ils n'ont aucune "
    "valeur."
)

#: Consigne du cas intermédiaire. Le risque n'est pas le même que pour le
#: placeholder : ici les sorties dépendent bien du cliché, ce qui les rend
#: crédibles. L'assistant doit donc pouvoir les commenter, mais jamais les
#: présenter comme un résultat fiable.
UNVALIDATED_SYSTEM_RULE: Final[str] = "\n" + (
    "8. IMPORTANT : le modèle qui a produit ces résultats est entraîné mais "
    "n'a fait l'objet d'AUCUNE VALIDATION CLINIQUE. Il a appris sur un jeu de "
    "données restreint et ses performances réelles sont inconnues. Tu peux "
    "expliquer ce qu'il a produit, mais tu rappelles que ces sorties sont à "
    "visée académique et démonstrative, et tu ne les présentes jamais comme un "
    "élément fiable pour la prise en charge."
)

#: Règle système à ajouter selon l'état du modèle. Un modèle validé n'en reçoit
#: aucune : les règles 1 à 7 et `MEDICAL_DISCLAIMER` s'appliquent toujours.
SYSTEM_RULE_BY_STATUS: Final[dict[ModelStatus, str]] = {
    "placeholder": PLACEHOLDER_SYSTEM_RULE,
    "trained_unvalidated": UNVALIDATED_SYSTEM_RULE,
    "validated": "",
}


# --------------------------------------------------------------------------- #
# Contexte
# --------------------------------------------------------------------------- #


def _age(birth_date: date | None) -> int | None:
    if birth_date is None:
        return None
    today = date.today()
    years = today.year - birth_date.year
    if (today.month, today.day) < (birth_date.month, birth_date.day):
        years -= 1
    return years if years >= 0 else None


def build_context(analysis: Analysis, patient: Patient) -> str:
    """Compose le contexte clinique transmis au modèle.

    Aucun identifiant direct n'y figure : ni nom, ni code dossier, ni date de
    naissance, ni coordonnées, ni texte libre saisi par le médecin.
    """
    sex_labels = {"F": "féminin", "M": "masculin", "O": "autre"}
    prediction_labels = {"benign": "bénin", "malignant": "malin"}

    lines = ["Contexte de l'analyse en cours de consultation :"]

    age = _age(patient.birth_date)
    lines.append(f"- Patiente : {age} ans" if age is not None else "- Âge non renseigné")
    lines.append(f"- Sexe : {sex_labels.get(patient.sex, 'non précisé')}")

    lines.append(f"- Format du cliché : {(analysis.image_format or 'inconnu').upper()}")
    lines.append(f"- Chaîne de prétraitement : {analysis.preprocessing_version or 'inconnue'}")

    if analysis.status != AnalysisStatus.COMPLETED.value:
        lines.append(f"- Statut : analyse non terminée ({analysis.status})")
        if analysis.error_message:
            lines.append("- L'analyse a échoué, aucun résultat n'est disponible.")
        return "\n".join(lines)

    lines.append(
        f"- Classification produite : {prediction_labels.get(analysis.prediction, 'aucune')}"
    )
    if analysis.probability is not None:
        lines.append(f"- Probabilité de malignité : {analysis.probability * 100:.1f} %")
    if analysis.confidence is not None:
        lines.append(f"- Score de confiance : {analysis.confidence * 100:.1f} %")
    if analysis.inference_time_ms is not None:
        lines.append(f"- Temps d'inférence : {analysis.inference_time_ms:.0f} ms")

    lines.append(f"- Modèle : {analysis.model_version or 'inconnu'}")

    if analysis.region_width:
        lines.append(
            f"- Zone Grad-CAM la plus activée : rectangle de {analysis.region_width} × "
            f"{analysis.region_height} pixels, à ({analysis.region_x}, {analysis.region_y}) "
            "dans l'image prétraitée de 384 × 384 pixels"
        )
    elif analysis.gradcam_path:
        lines.append("- Une carte Grad-CAM existe, sans zone saillante identifiée.")

    lines.append(f"- Rappel sur la carte Grad-CAM : {GRADCAM_DISCLAIMER}")
    return "\n".join(lines)


def build_messages(
    context: str,
    question: str,
    history: list[AssistantMessage],
    status: ModelStatus,
) -> list[dict[str, str]]:
    """Assemble la conversation envoyée au fournisseur."""
    system = SYSTEM_PROMPT + SYSTEM_RULE_BY_STATUS[status]

    messages: list[dict[str, str]] = [{"role": "system", "content": system}]

    # L'historique est tronqué : chaque tour conservé est refacturé à chaque
    # nouvelle question, et au-delà de quelques échanges la réponse ne s'améliore
    # plus.
    kept = history[-settings.assistant_history_turns * 2 :] if history else []
    for message in kept:
        if message.role in {"user", "assistant"} and message.content.strip():
            messages.append({"role": message.role, "content": message.content})

    messages.append({"role": "user", "content": f"{context}\n\nQuestion : {question.strip()}"})
    return messages


# --------------------------------------------------------------------------- #
# Appel au fournisseur
# --------------------------------------------------------------------------- #


def _call_provider(messages: list[dict[str, str]]) -> tuple[str, dict[str, int]]:
    """Interroge le routeur Hugging Face, compatible avec l'API OpenAI."""
    try:
        response = httpx.post(
            f"{settings.assistant_base_url}/chat/completions",
            headers={"Authorization": f"Bearer {settings.huggingface_api_token}"},
            json={
                "model": settings.assistant_model,
                "messages": messages,
                "max_tokens": settings.assistant_max_tokens,
                "temperature": settings.assistant_temperature,
            },
            timeout=settings.assistant_timeout_seconds,
        )
    except httpx.TimeoutException as exc:
        raise AssistantUnavailableError(
            "Le service d'assistance n'a pas répondu dans le délai imparti."
        ) from exc
    except httpx.HTTPError as exc:
        logger.warning("Appel à l'assistant impossible : %s", exc)
        raise AssistantUnavailableError("Le service d'assistance est injoignable.") from exc

    if response.status_code in (402, 429):
        # 402 : crédit mensuel épuisé côté fournisseur. 429 : débit dépassé.
        # Les deux se règlent hors de l'application ; le message doit le dire.
        logger.warning(
            "Quota du fournisseur atteint (%s) : %s",
            response.status_code,
            response.text[:200],
        )
        raise AssistantQuotaError(
            "Le quota du service d'assistance est épuisé. "
            "L'analyse et le rapport restent disponibles sans l'assistant."
        )

    if response.status_code >= 400:
        logger.warning("Réponse %s du fournisseur : %s", response.status_code, response.text[:300])
        raise AssistantUnavailableError("Le service d'assistance a renvoyé une erreur.")

    try:
        body = response.json()
        answer = body["choices"][0]["message"]["content"].strip()
    except (ValueError, KeyError, IndexError) as exc:
        raise AssistantUnavailableError("Réponse illisible du service d'assistance.") from exc

    if not answer:
        raise AssistantUnavailableError("Le service d'assistance a renvoyé une réponse vide.")

    usage = body.get("usage") or {}
    return answer, {
        key: int(value)
        for key, value in usage.items()
        if isinstance(value, int | float) and key.endswith("tokens")
    }


def compose_answer(raw_answer: str, status: ModelStatus) -> str:
    """Encadre la réponse du modèle par les avertissements obligatoires.

    Ajoutés par le code et non demandés au modèle : à la mise au point, celui-ci
    a omis l'avertissement de démonstration une fois sur deux malgré une consigne
    système explicite. Les rattacher au texte lui-même — et pas seulement à un
    champ de la réponse — fait qu'ils suivent la réponse si elle est copiée
    ailleurs.

    `MEDICAL_DISCLAIMER` est ajouté dans les trois cas, y compris pour un modèle
    validé : il ne dépend pas de la provenance du modèle.
    """
    parts: list[str] = []
    warning = model_warning_for(status)
    if warning:
        parts.append(warning)
    parts.append(raw_answer)
    parts.append(MEDICAL_DISCLAIMER)
    return "\n\n".join(parts)


def ask(
    analysis: Analysis,
    patient: Patient,
    question: str,
    history: list[AssistantMessage] | None = None,
) -> AssistantAnswer:
    """Répond à une question portant sur une analyse."""
    if not settings.assistant_enabled:
        raise AssistantDisabledError(
            "L'assistant n'est pas configuré : aucun jeton de service n'est renseigné."
        )

    cleaned = question.strip()
    if not cleaned:
        raise AssistantError("La question est vide.")
    if len(cleaned) > MAX_QUESTION_LENGTH:
        raise AssistantError(
            f"La question dépasse {MAX_QUESTION_LENGTH} caractères."
        )

    is_placeholder = is_placeholder_version(analysis.model_version)
    status = derive_model_status(is_placeholder, analysis.clinically_validated)
    context = build_context(analysis, patient)
    messages = build_messages(context, cleaned, history or [], status)

    raw_answer, usage = _call_provider(messages)

    logger.info(
        "Assistant : réponse de %s sur l'analyse %s (%s jetons).",
        settings.assistant_model,
        analysis.id,
        usage.get("total_tokens", "?"),
    )

    return AssistantAnswer(
        answer=compose_answer(raw_answer, status),
        answer_body=raw_answer,
        model=settings.assistant_model,
        is_placeholder_model=is_placeholder,
        clinically_validated=analysis.clinically_validated,
        model_warning=model_warning_for(status),
        context_sent=context,
        usage=usage,
    )
