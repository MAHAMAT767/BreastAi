"""Évaluation des performances du modèle.

Métriques calculées :
    - accuracy, precision, recall, F1-score
    - ROC-AUC et courbe ROC
    - matrice de confusion
    - sensibilité et spécificité, à la terminologie clinique

En dépistage, la métrique décisive est la **sensibilité** (recall sur la classe
maligne) : manquer un cancer est la défaillance la plus grave du système. Le
seuil de décision doit être choisi sur cette base, et non laissé à 0,5 par défaut.

Modules prévus :
    metrics.py           — calcul des métriques
    confusion.py         — matrice de confusion et export graphique
    threshold.py         — choix du seuil (Youden, contrainte de sensibilité)
    report.py            — synthèse d'évaluation vers `reports/`
"""
