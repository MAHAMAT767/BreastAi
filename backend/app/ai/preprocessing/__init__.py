"""Prétraitement des mammographies (Phase 3).

Chaîne appliquée à chaque image avant l'inférence :

1. Décodage       — DICOM (pydicom) ou image standard (PNG/JPG/JPEG via OpenCV)
2. Mise en niveaux de gris et application du VOI LUT pour le DICOM
3. Suppression du bruit  — filtre médian / non-local means
4. Amélioration du contraste — CLAHE (contrast limited adaptive histogram equalization)
5. Redimensionnement — vers `app.ai.IMAGE_SIZE`, en conservant le ratio
6. Normalisation  — statistiques ImageNet (`IMAGENET_MEAN`, `IMAGENET_STD`)

Le même prétraitement doit être appliqué à l'entraînement et à l'inférence.
L'augmentation (Albumentations) ne s'applique qu'à l'entraînement.

Modules prévus :
    loaders.py       — `load_image(path) -> np.ndarray` (DICOM/PNG/JPG)
    transforms.py    — `resize`, `normalize`, `denoise`, `enhance_contrast`
    augmentation.py  — pipelines Albumentations d'entraînement
    pipeline.py      — `preprocess_for_inference(...)` composant le tout
"""
