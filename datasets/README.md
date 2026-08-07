# datasets/

Jeux de données de mammographies utilisés pour l'entraînement et l'évaluation.

**Le contenu de ce dossier n'est pas versionné.** Les images médicales sont des
données de santé à caractère personnel : elles ne doivent jamais être poussées
sur un dépôt distant.

## Organisation attendue

```
datasets/
├── raw/            # données brutes, telles que reçues (DICOM ou images)
├── processed/      # images prétraitées, prêtes pour l'entraînement
└── splits/         # fichiers CSV de découpage train/val/test, par patient
```

## Règle de découpage

Le découpage train/val/test se fait **par patient**, jamais par image. Deux
clichés d'une même patiente répartis entre train et test créent une fuite de
données et gonflent artificiellement les métriques.

## Sources publiques envisageables

| Jeu de données | Contenu | Accès |
|----------------|---------|-------|
| CBIS-DDSM | Mammographies numérisées, masses et calcifications annotées | Public (TCIA) |
| INbreast | Mammographies numériques pleine résolution | Sur demande |
| MIAS / mini-MIAS | Petit jeu historique, utile pour prototyper | Public |
| VinDr-Mammo | Mammographies avec annotations BI-RADS | PhysioNet, accord requis |

Documentez ici la provenance, la licence et la date de récupération de tout jeu
de données ajouté.
