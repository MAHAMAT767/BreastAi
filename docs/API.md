# API BreastAI — référence

Base : `/api/v1`. Documentation interactive : `http://localhost:8000/docs`.

## Authentification

Tous les endpoints protégés attendent un en-tête :

```
Authorization: Bearer <access_token>
```

### Jetons

| Jeton | Durée | Contenu | Usage |
|-------|-------|---------|-------|
| `access` | 30 min | `sub`, `role`, `pwd_at`, `jti` | Accès aux ressources |
| `refresh` | 7 jours | `sub`, `jti` | Obtenir un nouvel `access` |
| `reset` | 30 min | `sub`, `pwd_at` | Réinitialiser un mot de passe |

Le champ `type` distingue les trois : un `refresh` présenté comme jeton d'accès
est rejeté. Le champ `pwd_at` porte l'horodatage du dernier changement de mot de
passe ; toute modification du mot de passe invalide instantanément les jetons
émis auparavant. C'est le seul mécanisme de révocation — il n'y a pas de liste
noire de jetons.

### Endpoints

| Méthode | Chemin | Accès | Description |
|---------|--------|-------|-------------|
| `POST` | `/auth/login` | public | Formulaire OAuth2 (`username` = e-mail). Renvoie la paire de jetons. |
| `POST` | `/auth/refresh` | public | Échange un `refresh` contre une nouvelle paire. |
| `POST` | `/auth/logout` | connecté | Journalise la déconnexion. |
| `GET` | `/auth/me` | connecté | Profil du compte courant. |
| `POST` | `/auth/password/change` | connecté | Change le mot de passe (exige l'ancien). |
| `POST` | `/auth/password-reset/request` | public | Génère un jeton de réinitialisation. |
| `POST` | `/auth/password-reset/confirm` | public | Applique le nouveau mot de passe. |

## Comptes — `/users`

Réservé au rôle `admin`.

| Méthode | Chemin | Description |
|---------|--------|-------------|
| `POST` | `/users` | Créer un compte (`409` si l'e-mail existe). |
| `GET` | `/users` | Lister les comptes. |
| `GET` | `/users/{id}` | Consulter un compte. |
| `PATCH` | `/users/{id}` | Modifier nom, rôle, activation. |

Un administrateur ne peut ni se désactiver ni changer son propre rôle : sans
cette règle, la plateforme peut se retrouver sans administrateur actif.

## Patients — `/patients`

Réservé aux rôles cliniques (`admin`, `doctor`). Le rôle `researcher` reçoit `403` :
il n'a pas vocation à consulter des dossiers nominatifs.

| Méthode | Chemin | Description |
|---------|--------|-------------|
| `POST` | `/patients` | Créer un dossier (`409` si le code existe). |
| `GET` | `/patients` | Rechercher — `search` (code, prénom, nom), `limit`, `offset`. |
| `GET` | `/patients/{id}` | Consulter un dossier. Consultation journalisée. |
| `PATCH` | `/patients/{id}` | Mise à jour partielle. |
| `DELETE` | `/patients/{id}` | Suppression **logique**. |

Le code patient est normalisé en majuscules sans espaces de bord. La suppression
est logique : les analyses déjà rendues restent rattachées, un compte rendu remis
à une patiente doit rester reconstituable.

## Analyses — `/analyses`

| Méthode | Chemin | Description |
|---------|--------|-------------|
| `POST` | `/analyses` | Déposer une mammographie (`multipart` : `patient_id`, `file`). |
| `GET` | `/analyses` | Lister — `patient_id`, `limit`, `offset`. |
| `GET` | `/analyses/{id}` | Consulter une analyse. |
| `GET` | `/analyses/{id}/image` | Image `processed` (défaut) ou `original`. |
| `PATCH` | `/analyses/{id}/review` | Commentaire et validation du médecin. |

### Validation d'un dépôt

Trois couches, de la moins chère à la plus chère :

1. **Extension** — `.dcm`, `.dicom`, `.png`, `.jpg`, `.jpeg`, et taille sous la limite
   (`MAX_UPLOAD_SIZE_MB`, 50 Mo par défaut). Rejet en `400`.
2. **Octets magiques** — `\x89PNG`, `\xff\xd8\xff`, ou `DICM` à l'offset 128.
   L'extension ne fait pas foi : un exécutable renommé en `.png` est rejeté en `400`.
3. **Décodage effectif** — un fichier de bon type mais illisible est rejeté en `422`.

Aucune ligne n'est écrite en base tant que le prétraitement n'a pas abouti : une
analyse pointant vers des fichiers inexistants serait pire qu'une analyse absente.

### Prétraitement appliqué

`décodage → niveaux de gris → filtre médian 3×3 → CLAHE → redimensionnement 384×384
(ratio conservé, remplissage noir) → normalisation ImageNet, 3 canaux`

Pour le DICOM : la VOI LUT du constructeur est appliquée et les images
`MONOCHROME1` sont inversées. Les images 12 ou 16 bits sont ramenées sur 8 bits.

Le statut reste `pending` : l'inférence arrive en Phase 4.

### Accès aux images

Les images transitent par l'API, jamais par un service de fichiers statiques :
une mammographie ne doit pas être accessible sans contrôle d'accès. Les réponses
portent `Cache-Control: private, no-store`.

Les chemins de stockage sont construits uniquement à partir d'UUID générés par le
serveur. Le nom de fichier fourni par le client est désinfecté et conservé pour
l'affichage seul — il n'entre jamais dans la construction d'un chemin.

## Limitation de débit

| Endpoint | Quota par défaut | Variable |
|----------|------------------|----------|
| `POST /auth/login` | 10 / minute / IP | `LOGIN_RATE_LIMIT` |
| `POST /auth/password-reset/request` | 5 / minute / IP | `PASSWORD_RESET_RATE_LIMIT` |

Les réponses portent `X-RateLimit-Limit`, `X-RateLimit-Remaining` et
`X-RateLimit-Reset`. Dépassement : `429` avec un message générique.

La clé de comptage est l'adresse d'origine, lue dans `X-Forwarded-For` quand elle
est présente — derrière un reverse proxy, compter sur l'IP du proxy ferait
partager un unique quota à tous les utilisateurs.

> ### ⚠️ À traiter avant tout déploiement multi-instance
>
> Le stockage des compteurs est **en mémoire, par processus** (`storage_uri="memory://"`).
> Avec N répliques ou N workers uvicorn, chaque processus compte séparément : un
> attaquant obtient en pratique N fois le quota annoncé, et un redémarrage remet
> les compteurs à zéro.
>
> Avant de passer à plus d'une instance, basculer `storage_uri` sur un backend
> partagé — Redis ou Memcached — dans `app/auth/rate_limit.py`. En attendant,
> déployer avec un seul worker, ou considérer que la protection est indicative.

## Rôles

| Rôle | Portée |
|------|--------|
| `admin` | Gestion des comptes, accès complet. |
| `doctor` | Patients et analyses — usage clinique. |
| `researcher` | Données agrégées et anonymisées, pas de dossier nominatif. |

## Règles de sécurité appliquées

- Mots de passe hachés avec bcrypt, 12 caractères minimum, 72 octets maximum
  (limite de bcrypt : un mot de passe plus long est refusé plutôt que tronqué en silence).
- `POST /auth/login` renvoie le même message pour une adresse inconnue et pour un
  mot de passe faux, et le temps de réponse est égalisé — impossible d'énumérer les comptes.
- `POST /auth/password-reset/request` répond toujours la même chose, que l'adresse
  existe ou non, et **ne renvoie jamais le jeton**.
- Un jeton cesse de fonctionner dès que le compte est désactivé : le compte est
  relu en base à chaque requête.
- Les actions sensibles sont journalisées dans `audit_logs`.

## Limites connues

| Limite | Conséquence | Phase visée |
|--------|-------------|-------------|
| Pas d'envoi d'e-mail | Le jeton de réinitialisation est écrit dans les journaux serveur | 8 |
| Compteurs de quota en mémoire | Quota multiplié par le nombre d'instances (voir l'encadré ci-dessus) | avant déploiement |
| `logout` ne révoque pas le jeton | Le client doit l'effacer ; changer le mot de passe coupe toutes les sessions | — |
| `EmailStr` refuse les TLD réservés | Une adresse en `.local` interne serait rejetée | à arbitrer |
| DICOM compressés non pris en charge | Sans `pylibjpeg` ni `gdcm`, un DICOM en JPEG/JPEG2000 est rejeté en `422` | à arbitrer |
| Stockage sur disque local, non chiffré | Les mammographies ne sont ni sauvegardées ni chiffrées au repos | avant déploiement |
| Taille lue en mémoire avant contrôle | Un fichier de 50 Mo est intégralement chargé avant d'être mesuré | 8 |
