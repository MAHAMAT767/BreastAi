# models/

Poids des modèles entraînés. **Contenu non versionné** (fichiers volumineux).

## Convention de nommage

```
breastai_<architecture>_<version>_<date>.pt      # checkpoint PyTorch
breastai_<architecture>_<version>_<date>.onnx    # export ONNX Runtime
breastai_<architecture>_<version>_<date>.json    # métadonnées et métriques
```

## Fiche modèle

Chaque modèle publié doit être accompagné d'un fichier `.json` indiquant :

- architecture et poids de départ
- jeu de données d'entraînement, taille, découpage
- prétraitement appliqué (doit correspondre à `app.ai.preprocessing`)
- ordre des classes (`app.ai.CLASS_NAMES`)
- métriques sur le jeu de test : accuracy, precision, recall, F1, ROC-AUC
- seuil de décision retenu et justification
- limites connues et populations sur lesquelles le modèle n'a pas été validé
