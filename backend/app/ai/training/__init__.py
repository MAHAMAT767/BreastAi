"""Entraînement et fine-tuning du classifieur (Phase 4+).

Approche : transfer learning depuis EfficientNet pré-entraîné sur ImageNet,
tête de classification remplacée par une sortie à 2 classes
(`app.ai.CLASS_NAMES`). Évolutions envisagées : ConvNeXt, Swin Transformer.

Points d'attention propres au domaine médical :
    - séparation train/val/test **par patient**, jamais par image, sous peine de
      fuite de données et de métriques trompeuses ;
    - déséquilibre des classes : pondération de la perte ou échantillonnage ;
    - le rappel (recall) sur la classe maligne prime sur l'accuracy globale —
      un faux négatif coûte infiniment plus cher qu'un faux positif.

Modules prévus :
    dataset.py    — `MammographyDataset`, découpage par patient
    model.py      — construction du réseau et remplacement de la tête
    train.py      — boucle d'entraînement, early stopping, journalisation
    validate.py   — évaluation par époque
    checkpoint.py — sauvegarde/restauration des poids vers `models/`
"""
