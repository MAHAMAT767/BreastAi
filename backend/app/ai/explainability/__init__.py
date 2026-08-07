"""Explicabilité : Grad-CAM et cartes thermiques (Phase 4).

Grad-CAM pondère les cartes d'activation de la dernière couche convolutive par
le gradient du score de la classe prédite, produisant une carte de chaleur qui
localise les régions ayant motivé la décision du réseau.

Limite à rappeler dans l'interface et dans les rapports : la carte indique où le
modèle a regardé, pas où se trouve une lésion. Elle appuie la lecture du médecin,
elle ne la remplace pas.

Modules prévus :
    gradcam.py  — implémentation Grad-CAM (hooks sur la couche cible)
    heatmap.py  — colormap et normalisation de la carte
    overlay.py  — superposition carte/image originale, export PNG
"""
