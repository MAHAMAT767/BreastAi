"""Grille de délai de prise en charge.

Ces tests verrouillent la grille telle qu'elle est *aujourd'hui*. Elle n'est pas
validée cliniquement (voir la docstring de `app.followup`) : le jour où un
médecin l'arrête, ces valeurs attendues changeront avec elle. Ce fichier n'est
pas là pour figer une vérité médicale, mais pour garantir qu'aucune modification
de la règle ne passe inaperçue.
"""

from __future__ import annotations

import pytest

from app.followup import (
    CLOSE_FOLLOWUP_THRESHOLD,
    FOLLOWUP_LABELS,
    FOLLOWUP_NOTICE,
    SURVEILLANCE_THRESHOLD,
    URGENT_THRESHOLD,
    derive_followup_urgency,
    followup_label_for,
)


class TestTranches:
    """Les quatre tranches de la grille par défaut."""

    def test_malin_tres_probable_est_urgent(self):
        assert derive_followup_urgency("malignant", 0.93) == "urgent"

    def test_malin_probable_est_rapproche(self):
        assert derive_followup_urgency("malignant", 0.64) == "rapproche"

    def test_benin_douteux_est_surveillance(self):
        assert derive_followup_urgency("benign", 0.31) == "surveillance"

    def test_benin_franc_est_routine(self):
        assert derive_followup_urgency("benign", 0.04) == "routine"


class TestBornes:
    """Bornes exactes : chaque seuil appartient à la tranche la plus prudente.

    Une borne rangée du mauvais côté ne se voit pas à l'œil — elle ne concerne
    qu'une valeur sur mille — mais c'est précisément celle qui décide entre
    « sous 4 semaines » et « dans 6 mois ».
    """

    def test_080_bascule_en_urgent(self):
        assert derive_followup_urgency("malignant", URGENT_THRESHOLD) == "urgent"

    def test_juste_sous_080_reste_rapproche(self):
        assert derive_followup_urgency("malignant", 0.7999) == "rapproche"

    def test_050_bascule_en_rapproche(self):
        assert derive_followup_urgency("malignant", CLOSE_FOLLOWUP_THRESHOLD) == "rapproche"

    def test_juste_sous_050_est_surveillance_si_benin(self):
        assert derive_followup_urgency("benign", 0.4999) == "surveillance"

    def test_020_bascule_en_surveillance(self):
        assert derive_followup_urgency("benign", SURVEILLANCE_THRESHOLD) == "surveillance"

    def test_juste_sous_020_est_routine(self):
        assert derive_followup_urgency("benign", 0.1999) == "routine"

    def test_zero_et_un_sont_ranges(self):
        assert derive_followup_urgency("benign", 0.0) == "routine"
        assert derive_followup_urgency("malignant", 1.0) == "urgent"


class TestSansResultat:
    """Une analyse sans résultat ne reçoit aucun délai.

    Un délai « par défaut » sur une analyse en attente ou en échec serait une
    affirmation sortie de nulle part — et la plus rassurante des quatre.
    """

    @pytest.mark.parametrize(
        ("prediction", "probability"),
        [(None, None), (None, 0.9), ("malignant", None), ("benign", None)],
    )
    def test_renvoie_none(self, prediction, probability):
        assert derive_followup_urgency(prediction, probability) is None

    def test_pas_de_libelle_sans_niveau(self):
        assert followup_label_for(None) is None


class TestPredictionMaligneSousLeSeuil:
    """Le seuil de décision du modèle n'est pas forcément 0,50.

    `ModelBundle.threshold` est porté par le checkpoint. Un modèle réglé à 0,35
    classe « malignant » une image à 0,42 : les seules bornes de probabilité la
    rangeraient en surveillance, ce qui contredirait la sortie du modèle dans le
    sens imprudent.
    """

    def test_maligne_sous_050_ne_descend_pas_sous_rapproche(self):
        assert derive_followup_urgency("malignant", 0.42) == "rapproche"

    def test_maligne_tres_basse_ne_descend_pas_non_plus(self):
        assert derive_followup_urgency("malignant", 0.05) == "rapproche"

    def test_benigne_au_dessus_de_050_suit_la_probabilite(self):
        # Modèle à seuil haut : la probabilité prime, dans le sens prudent.
        assert derive_followup_urgency("benign", 0.72) == "rapproche"


class TestLibelles:
    def test_chaque_niveau_a_son_libelle(self):
        for urgency in ("urgent", "rapproche", "surveillance", "routine"):
            assert followup_label_for(urgency) == FOLLOWUP_LABELS[urgency]
            assert FOLLOWUP_LABELS[urgency].strip()

    def test_les_libelles_recommandent_sans_prescrire(self):
        # « recommandée », jamais « à réaliser » : l'outil ne prescrit pas.
        for label in FOLLOWUP_LABELS.values():
            assert "recommand" in label.lower() or "routine" in label.lower()

    def test_la_mention_rappelle_que_le_medecin_decide(self):
        assert "non prescriptif" in FOLLOWUP_NOTICE
        assert "médecin" in FOLLOWUP_NOTICE


class TestOrdreDesSeuils:
    """Garde-fou sur la grille elle-même, pas sur son application.

    Elle est faite pour être modifiée par un médecin. Des seuils réordonnés par
    erreur rendraient une tranche inatteignable sans qu'aucun autre test ne
    tombe.
    """

    def test_les_seuils_sont_strictement_decroissants(self):
        assert URGENT_THRESHOLD > CLOSE_FOLLOWUP_THRESHOLD > SURVEILLANCE_THRESHOLD

    def test_les_seuils_sont_des_probabilites(self):
        for threshold in (URGENT_THRESHOLD, CLOSE_FOLLOWUP_THRESHOLD, SURVEILLANCE_THRESHOLD):
            assert 0.0 < threshold < 1.0
