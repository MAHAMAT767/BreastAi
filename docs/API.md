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
| Pas de limitation de débit sur `/auth/login` | Attaque par force brute possible | 8 |
| `logout` ne révoque pas le jeton | Le client doit l'effacer ; changer le mot de passe coupe toutes les sessions | — |
| `EmailStr` refuse les TLD réservés | Une adresse en `.local` interne serait rejetée | à arbitrer |
