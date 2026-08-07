"""Inférence : chargement du modèle et prédiction (Phase 4).

Le modèle est chargé une seule fois au démarrage et réutilisé (singleton), le
chargement des poids étant coûteux au regard d'une requête HTTP.

Sortie attendue pour une mammographie :
    - `label`            : "benign" | "malignant"
    - `probability`      : probabilité de la classe maligne, dans [0, 1]
    - `confidence`       : score de confiance de la prédiction, dans [0, 1]
    - `inference_time_ms`: durée de l'inférence en millisecondes

Modules prévus :
    loader.py     — chargement du checkpoint PyTorch ou du modèle ONNX Runtime
    predictor.py  — `predict(image) -> PredictionResult`
    schemas.py    — dataclasses/schémas Pydantic du résultat
"""
