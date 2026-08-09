"""Entraînement et fine-tuning du classifieur. Module encore vide.

Transfer learning depuis EfficientNet pré-entraîné sur ImageNet, tête de
classification remplacée par une sortie à 2 classes (`app.ai.CLASS_NAMES`).

Trois exigences propres au domaine, à ne pas perdre de vue le jour où ce module
sera écrit :

- séparation train/val/test **par patient**, jamais par image : deux clichés
  d'une même patiente de part et d'autre créent une fuite de données et des
  métriques trompeuses ;
- déséquilibre des classes à corriger, par pondération de la perte ou par
  échantillonnage ;
- le rappel sur la classe maligne prime sur l'accuracy globale — un faux négatif
  coûte infiniment plus cher qu'un faux positif.
"""
