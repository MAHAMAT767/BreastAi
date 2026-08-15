# notebooks/

Exploration des données, prototypage de modèles, analyse d'erreurs.

Les notebooks servent à explorer, pas à produire : tout code destiné à tourner
en production est repris dans `backend/app/ai/`.

## Notebooks

| Fichier | Objet |
|---------|-------|
| `01_entrainement_mias_colab.ipynb` | Itération intérimaire sur mini-MIAS (115 images) — **conservé comme trace**, voir ci-dessous |
| `02_entrainement_miniddsm_colab.ipynb` | Entraînement sur Mini-DDSM (JPEG-8), ~1 350 images — notebook courant |

### Pourquoi `01_` reste dans le dépôt

Le notebook mini-MIAS a servi à valider la mécanique d'entraînement — import du
prétraitement de production, découpage par patiente, relecture du checkpoint par
`load_checkpoint` — sur un jeu de 115 images lésionnelles. Il n'est plus le
chemin à suivre pour produire un modèle, mais il documente l'itération qui a
mené au socle repris par `02_`, et le modèle `efficientnet_b0-mini-mias-v1`
qu'il a produit reste identifiable dans les analyses déjà rendues.

`02_` reprend ce socle et en diffère sur ce que change le dataset : pas de
fichier d'annotations (l'étiquette vient de l'arborescence), regroupement par
cas lu dans le nom de fichier, et pas de conversion d'images — les JPEG
Mini-DDSM sont déjà dans un format que le pipeline sait lire. Le dossier
`Normal` y est écarté pour la même raison que les clichés normaux de mini-MIAS :
le contrat de sortie n'a que deux classes.

L'étiquetage y est en revanche **asymétrique**, et c'est délibéré : un cas
Mini-DDSM regroupe les deux seins, dont un souvent sain. Seuls les clichés
portant un masque de lésion sont étiquetés `malignant` ; les cas bénins gardent
toutes leurs vues. Poser `malignant` sur un sein sain apprendrait au modèle à
voir du cancer là où il n'y en a pas, tandis que `benign` sur un sein sain reste
juste pour le triage — bénin et normal disent tous deux « pas de cancer ». Le
raisonnement complet est à l'étape 2 bis du notebook, et le décompte de ce qui
est écarté figure dans la fiche modèle.

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

## Rejouer un notebook d'entraînement en local

Les deux notebooks acceptent `BREASTAI_SMOKE=1` : quelques images, une époque.
De quoi vérifier la mécanique avant de lancer une session Colab.

```bash
BREASTAI_SMOKE=1 BREASTAI_MINIDDSM_ROOT=/chemin/vers/MINI-DDSM-Complete-JPEG-8 \
  python -m nbconvert --to notebook --execute \
  --output /tmp/execute.ipynb notebooks/02_entrainement_miniddsm_colab.ipynb
```

Le chemin du dataset se règle par `BREASTAI_MIAS_ROOT` (`01_`) ou
`BREASTAI_MINIDDSM_ROOT` (`02_`), jamais en éditant le notebook.
