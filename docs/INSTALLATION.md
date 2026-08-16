# Guide d'installation — BreastAI

Ce guide décrit l'installation complète de BreastAI en local, de zéro jusqu'au lancement de l'application (backend + frontend).

## Prérequis

| Outil | Version | Vérifier avec |
|---|---|---|
| Python | 3.11 | `python --version` |
| Node.js | 18+ | `node --version` |
| PostgreSQL | 16 | `psql --version` |
| Git | récent | `git --version` |

**Important (retour d'expérience) :** clone le projet dans un dossier **hors synchronisation cloud** (OneDrive, Google Drive, Dropbox…), par exemple `C:\Dev\BreastAI`. Un dépôt Git à l'intérieur d'un dossier synchronisé cause des verrous de fichiers aléatoires pendant les opérations Git (checkout, suppression de branche) et peut corrompre l'arbre de travail.

## 1. Cloner le projet

```bash
git clone https://github.com/MAHAMAT767/BreastAi.git C:\Dev\BreastAI
cd C:\Dev\BreastAI
```

## 2. Base de données PostgreSQL

Créer le rôle et la base dédiés :

```sql
-- Dans psql, connecté en superutilisateur
CREATE ROLE breastai WITH LOGIN PASSWORD 'un_mot_de_passe_fort';
CREATE DATABASE breastai OWNER breastai;
```

## 3. Configuration (`.env`)

Copier le modèle et le remplir :

```powershell
Copy-Item .env.example .env
```

Variables clés à renseigner dans `.env` (à la racine du projet) :

```
DATABASE_URL=postgresql+psycopg://breastai:un_mot_de_passe_fort@localhost:5432/breastai
MODEL_PATH=./models/breastai_efficientnet_b0_miniddsm-v1_20260816.pt

# Administrateur initial (créé une seule fois au premier lancement)
FIRST_ADMIN_EMAIL=admin@breastai.local
FIRST_ADMIN_PASSWORD=change-moi-avant-toute-mise-en-ligne
FIRST_ADMIN_NAME=Administrateur BreastAI
```

**Sécurité :** `FIRST_ADMIN_PASSWORD` est stocké en clair uniquement dans ce fichier local (jamais commité — `.env` est dans `.gitignore`). Le mot de passe réel de l'administrateur, une fois le compte créé en base, est haché (bcrypt) et non récupérable en clair. Change cette valeur avant tout déploiement accessible publiquement.

## 4. Backend (FastAPI)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt
```

Appliquer les migrations de base de données :

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
```

Créer le compte administrateur initial (lit `FIRST_ADMIN_EMAIL` / `FIRST_ADMIN_PASSWORD` depuis `.env`) :

```powershell
.\.venv\Scripts\python.exe -m app.database.init_db
```

Placer le checkpoint du modèle entraîné dans `backend/models/` (nom de fichier = valeur de `MODEL_PATH` dans `.env`).

Lancer le serveur :

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

L'API est accessible sur `http://localhost:8000` (documentation interactive sur `http://localhost:8000/docs`).

Vérifier que tout fonctionne :

```powershell
cd ..
.\backend\.venv\Scripts\python.exe -m pytest -q
```

## 5. Frontend (React + Vite)

```powershell
cd frontend
Copy-Item .env.example .env
npm install
npm run dev
```

L'application est accessible sur `http://localhost:5173` (ou le port indiqué dans le terminal). Vérifie que `frontend/.env` pointe bien vers l'URL de l'API backend (`http://localhost:8000`).

Lancer les tests frontend :

```powershell
npm test
```

## 6. Connexion

Ouvrir `http://localhost:5173`, se connecter avec `FIRST_ADMIN_EMAIL` / `FIRST_ADMIN_PASSWORD` défini à l'étape 3.

## Dépannage

**`Copy-Item` ou `git` échoue avec des erreurs de verrou de fichier / suppression de dossier en boucle (y/n)**
Le projet est probablement dans un dossier synchronisé par un client cloud (OneDrive, etc.). Déplace-le en dehors (voir prérequis) et recommence.

**`psql` : rôle ou mot de passe refusé**
Vérifie le rôle PostgreSQL créé à l'étape 2, et que `DATABASE_URL` dans `.env` correspond exactement (utilisateur, mot de passe, port).

**`tsc` / `npm run build` échoue avec une erreur `TS5103` sur `ignoreDeprecations`**
La valeur doit correspondre à la version de TypeScript réellement installée (voir `frontend/package.json`). Pour TypeScript 5.9.x, utiliser `"5.0"` et non `"6.0"`.

**Espace disque insuffisant pendant `npm install` ou `pip install`**
PyTorch et les dépendances Node consomment plusieurs Go. Vérifie l'espace libre avant installation (`Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'"`).

**Le modèle refuse de charger un checkpoint ("backbone non entraîné détecté")**
C'est une protection volontaire : le loader refuse tout checkpoint dont les poids sont identiques à un modèle ImageNet non entraîné (garde-fou contre une corruption silencieuse pendant l'entraînement). Vérifie que le bon fichier `.pt` est utilisé et qu'il provient d'un entraînement réellement terminé.