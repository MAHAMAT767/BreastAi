# Architecture de BreastAI

## Vue d'ensemble

```
┌──────────────┐   HTTPS/JSON   ┌──────────────┐        ┌──────────────┐
│   Frontend   │ ─────────────► │   FastAPI    │ ─────► │  PostgreSQL  │
│ React + TS   │ ◄───────────── │  (backend)   │ ◄───── │              │
└──────────────┘                └──────┬───────┘        └──────────────┘
                                       │
                                       ▼
                              ┌──────────────────┐
                              │   Service IA     │
                              │ PyTorch / ONNX   │
                              └──────────────────┘
```

## Couches du backend

| Couche | Dossier | Responsabilité |
|--------|---------|----------------|
| API | `app/api/` | Routes HTTP, validation d'entrée, codes de statut. Aucune logique métier. |
| Services | `app/services/` | Logique métier, orchestration, transactions. |
| Modèles | `app/models/` | Entités SQLAlchemy et schémas Pydantic. |
| Base | `app/database/` | Moteur, session, base déclarative. |
| Auth | `app/auth/` | JWT, hachage bcrypt, contrôle des rôles. |
| IA | `app/ai/` | Prétraitement, entraînement, inférence, explicabilité, évaluation. |

Règle de dépendance : `api → services → models/ai/database`. Un service n'importe
jamais un routeur ; un module IA n'importe jamais FastAPI.

## Pipeline d'analyse

```
1. Upload          POST /api/v1/analyses  (DICOM, PNG, JPG, JPEG)
2. Validation      type MIME, taille, en-tête DICOM
3. Prétraitement   niveaux de gris → débruitage → CLAHE → resize 384 → normalisation
4. Inférence       EfficientNet → logits → softmax → (label, probabilité, confiance)
5. Explicabilité   Grad-CAM sur la dernière couche convolutive → heatmap → superposition
6. Persistance     enregistrement de l'analyse et des chemins d'images
7. Rapport         PDF : patient, image originale, Grad-CAM, résultat, signature
8. Assistant       questions en langage naturel sur l'analyse, disclaimer systématique
```

## Modèle de données

Clés primaires en `UUID`. Les valeurs contraintes (rôle, sexe, statut, prédiction)
sont des colonnes `String` assorties d'une `CHECK` plutôt que des `ENUM` natifs
PostgreSQL : les enums natifs alourdissent chaque migration sans rien apporter ici.

```
User (id, email unique, hashed_password, full_name, role, is_active,
      password_changed_at, last_login_at, created_at, updated_at)
  └─ CHECK role ∈ {admin, doctor, researcher}

Patient (id, code unique, first_name, last_name, birth_date, sex, phone, email,
         address, medical_history, notes, is_deleted, deleted_at,
         created_by_id → User, created_at, updated_at)
  └─ CHECK sex ∈ {F, M, O}
  └─ suppression logique uniquement

Analysis (id, patient_id → Patient, created_by_id → User,
          original_filename, image_path, processed_image_path, gradcam_path,
          report_path, image_format, file_size_bytes,
          status, prediction, probability, confidence, inference_time_ms,
          model_version, error_message,
          doctor_comment, doctor_validated, created_at, updated_at)
  └─ CHECK status ∈ {pending, processing, completed, failed}
  └─ CHECK prediction ∈ {benign, malignant} ou NULL
  └─ CHECK probability et confidence dans [0, 1]

AuditLog (id, user_id → User, action, resource_type, resource_id,
          ip_address, detail, created_at)
```

Trois choix méritent d'être explicités :

- **`Patient.is_deleted`** — un dossier rattaché à des analyses déjà rendues ne
  doit jamais être effacé physiquement ; il doit rester reconstituable.
- **`Analysis.doctor_validated`** — la lecture du médecin est distincte de la
  sortie du modèle. C'est elle qui fait foi cliniquement.
- **`User.password_changed_at`** — embarqué dans les jetons, il sert de mécanisme
  de révocation globale (voir `docs/API.md`).

Les migrations sont dans `backend/app/database/migrations/`, avec `alembic.ini`
à la racine de `backend/`. L'URL de connexion vient de `app.config.settings`,
jamais du fichier ini.

## Sécurité

- Mots de passe hachés avec bcrypt ; jamais stockés ni journalisés en clair.
- JWT courts (30 min) + refresh token ; secret issu de l'environnement.
- Contrôle des rôles par dépendance FastAPI sur chaque route sensible.
- Journalisation des accès aux dossiers patients et des exports (`AuditLog`).
- Aucune donnée patient dans les journaux applicatifs ni dans les messages d'erreur.
- CORS restreint aux origines déclarées.

## Positionnement clinique

BreastAI est un outil d'aide à la décision, pas un dispositif de diagnostic. Trois
conséquences sur l'architecture :

1. Le disclaimer médical est porté par le backend (`app.main.MEDICAL_DISCLAIMER`)
   et par le frontend (`MedicalDisclaimer`), et accompagne toute réponse de l'assistant.
2. La sensibilité prime sur l'accuracy : le seuil de décision est un paramètre
   explicite du modèle, jamais laissé implicitement à 0,5.
3. Toute analyse conserve la trace du `model_version` qui l'a produite, afin de
   pouvoir réinterpréter a posteriori un résultat rendu par un modèle antérieur.

## Déploiement

| Composant | Cible | Notes |
|-----------|-------|-------|
| API | Railway | Image `docker/Dockerfile.backend`, sans `--reload` |
| Frontend | Vercel | Build Vite depuis `frontend/` |
| Base | PostgreSQL managé | Sauvegardes chiffrées |
| CI | GitHub Actions | Phase 8 |
