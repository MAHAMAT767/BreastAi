# notebooks/

Exploration des données, prototypage de modèles, analyse d'erreurs.

Les notebooks servent à explorer, pas à produire : tout code destiné à tourner
en production est repris dans `backend/app/ai/`.

## Notebooks

| Fichier | Objet |
|---------|-------|
| `01_entrainement_mias_colab.ipynb` | Entraînement intermédiaire sur mini-MIAS, en attendant Mini-DDSM |

## Convention de nommage

```
01_exploration_dataset.ipynb
02_preprocessing_comparaison.ipynb
03_baseline_efficientnet.ipynb
04_analyse_erreurs.ipynb
```

Videz les sorties des cellules avant de committer : elles peuvent contenir des
images de mammographies.

## Entraînement : ne pas recopier le prétraitement

Un notebook qui entraîne un modèle destiné à être chargé par l'API **importe**
`app.ai.preprocessing` et `app.ai.CLASS_NAMES` depuis `backend/`, au lieu d'en
refaire une version locale. Une chaîne de prétraitement recopiée finit toujours
par diverger de celle de l'inférence, et le modèle produit alors des prédictions
fausses sans qu'aucune erreur ne soit levée.

Pour la même raison, un notebook d'entraînement se termine en rechargeant son
propre checkpoint avec `app.ai.inference.loader.load_checkpoint` : le contrat se
vérifie sur le poste qui a entraîné le modèle, pas au démarrage du serveur.
