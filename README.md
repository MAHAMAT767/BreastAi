# BreastAI

**Plateforme web d'aide au dépistage du cancer du sein par intelligence artificielle.**

BreastAI assiste les médecins et radiologues dans la lecture des mammographies :
classification bénin/malin, carte de chaleur Grad-CAM localisant la zone suspecte,
rapport PDF structuré et assistant conversationnel. La plateforme est conçue en
priorité pour le contexte tchadien, où la pénurie de radiologues et l'accès limité
à l'expertise en imagerie médicale hors des grands centres retardent le diagnostic.

---

## Dédicace

> *À la mémoire de **Mouna Abakar**, meilleure amie de ma mère, emportée par le cancer du sein.*
>
> *Ce projet lui est dédié. Puisse-t-il aider à ce que d'autres soient diagnostiquées à temps.*

---

## ⚠️ Avertissement médical

BreastAI est un **outil d'aide à la décision**. Il ne pose aucun diagnostic et ne
remplace en aucun cas l'avis, l'examen et la décision d'un professionnel de santé
qualifié. Toute sortie du système (probabilité, carte thermique, rapport, réponse de
l'assistant) doit être interprétée et validée par un médecin. Le logiciel n'a fait
l'objet d'aucune certification en tant que dispositif médical.

> **⛔ Le modèle actuellement livré est un placeholder sans aucune valeur clinique.**
> Faute de jeu de mammographies annotées, il s'agit d'un EfficientNet-B0 à poids
> ImageNet dont la tête de classification est initialisée au hasard : **il n'a
> jamais vu de mammographie**. Ses prédictions sont des valeurs arbitraires,
> destinées uniquement à valider la chaîne technique. Voir
> [docs/PRODUCTION_CHECKLIST.md](docs/PRODUCTION_CHECKLIST.md).

---

## Architecture

```
React (Vite + TS)  →  FastAPI  →  Service IA  →  PyTorch  →  PostgreSQL
```

Pipeline d'analyse :

```
Upload → Prétraitement → EfficientNet → Classification → Grad-CAM → LLM → Rapport PDF
```

## Stack technique

| Couche       | Technologies |
|--------------|--------------|
| Frontend     | React, TypeScript, Tailwind CSS, React Query, React Router, Recharts |
| Backend      | FastAPI, SQLAlchemy, Alembic, JWT, Pydantic |
| IA           | PyTorch, TorchVision, OpenCV, Albumentations, Grad-CAM, ONNX Runtime |
| Base de données | PostgreSQL |
| Déploiement  | Docker, GitHub Actions, Railway (API), Vercel (frontend) |

## Arborescence

```
BreastAI/
├── frontend/          # Application React (Vite + TypeScript + Tailwind)
├── backend/
│   └── app/
│       ├── api/       # Routes HTTP (FastAPI)
│       ├── services/  # Logique métier
│       ├── models/    # Modèles SQLAlchemy + schémas Pydantic
│       ├── database/  # Session, moteur, base déclarative
│       ├── auth/      # JWT, hachage bcrypt, rôles
│       └── ai/
│           ├── training/         # Entraînement et fine-tuning
│           ├── inference/        # Chargement du modèle et prédiction
│           ├── preprocessing/    # Redimensionnement, normalisation, débruitage
│           ├── explainability/   # Grad-CAM, heatmaps, superposition
│           └── evaluation/       # Accuracy, F1, ROC-AUC, matrice de confusion
├── datasets/          # Données de mammographies (non versionnées)
├── models/            # Poids entraînés .pt / .onnx (non versionnés)
├── reports/           # Rapports PDF générés (non versionnés)
├── notebooks/         # Exploration et expérimentations
├── tests/             # Tests backend et end-to-end
├── docs/              # Documentation technique
└── docker/            # Dockerfiles
```

## Démarrage rapide

### Avec Docker (recommandé)

```bash
cp .env.example .env          # ajustez les secrets
docker compose up --build
```

| Service   | URL |
|-----------|-----|
| Frontend  | http://localhost:5173 |
| API       | http://localhost:8000 |
| Docs API  | http://localhost:8000/docs |
| PostgreSQL| localhost:5432 |

### En local, sans Docker

**Backend**

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux / macOS
pip install -r requirements.txt -r requirements-dev.txt
uvicorn app.main:app --reload
```

**Frontend**

```bash
cd frontend
npm install
npm run dev
```

## Base de données

```bash
# 1. Appliquer les migrations
cd backend
alembic upgrade head

# 2. Créer le compte administrateur initial (idempotent)
#    FIRST_ADMIN_EMAIL et FIRST_ADMIN_PASSWORD doivent être définis dans .env
python -m app.database.init_db
```

Sans cet administrateur, aucun compte ne peut être créé : c'est l'amorçage de la
plateforme. Les migrations vivent dans `backend/app/database/migrations/`.

```bash
alembic revision --autogenerate -m "description"   # nouvelle migration
alembic downgrade -1                               # revenir en arrière
alembic check                                      # dérive modèles / schéma
```

## Tests

```bash
# Backend (depuis la racine du dépôt)
pip install -r backend/requirements.txt -r backend/requirements-dev.txt
pytest

# Frontend
cd frontend && npm test
```

## Feuille de route

- [x] **Phase 1** — Scaffolding, docker-compose, README
- [x] **Phase 2** — Auth JWT, modèles SQLAlchemy (User, Patient, Analysis), migrations Alembic
- [x] **Phase 3** — CRUD patients, upload mammographies (DICOM/PNG/JPG), prétraitement
- [x] **Phase 4** — Inférence EfficientNet + Grad-CAM *(modèle placeholder — voir l'avertissement)*
- [x] **Phase 5** — Génération de rapports PDF
- [ ] **Phase 6** — Frontend React complet + tableau de bord Recharts
- [ ] **Phase 7** — Assistant IA conversationnel avec disclaimer médical
- [ ] **Phase 8** — Historique, recherche, tests end-to-end, CI

## Confidentialité des données

Les mammographies et les données patients sont des données de santé à caractère
personnel. Les dossiers `datasets/`, `models/` et `reports/` sont exclus du contrôle
de version. **N'ajoutez jamais de données patients réelles au dépôt.**

## Licence

À définir.
