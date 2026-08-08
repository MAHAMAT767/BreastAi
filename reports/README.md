# reports/

Rapports d'évaluation du modèle.

**Contenu non versionné.**

## Où sont les comptes rendus d'analyse ?

Les rapports PDF produits par la plateforme ne sont **pas** écrits ici. Ils sont
archivés avec les images de l'analyse à laquelle ils se rapportent, sous
`UPLOAD_DIR` :

```
<UPLOAD_DIR>/<patient_id>/<analysis_id>/
├── original.<ext>    # fichier déposé, tel quel
├── processed.png     # image prétraitée, vue par le modèle
├── gradcam.png       # superposition Grad-CAM
└── rapport.pdf       # compte rendu
```

Les regrouper évite qu'un rapport survive à la suppression des images sur
lesquelles il s'appuie, ou l'inverse.

Chaque rapport porte une empreinte HMAC-SHA256 vérifiable via
`GET /api/v1/analyses/{id}/report/verify`.

En production, ce stockage doit être remplacé par un stockage objet chiffré avec
accès contrôlé et journalisé : un compte rendu contient l'identité de la patiente.
Voir [../docs/PRODUCTION_CHECKLIST.md](../docs/PRODUCTION_CHECKLIST.md).
