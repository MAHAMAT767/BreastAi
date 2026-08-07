# docker/

Images de la plateforme. Le fichier `docker-compose.yml` se trouve à la racine
du dépôt ; le **contexte de build de chaque image est la racine**, ce qui permet
de partager un seul `.dockerignore`.

| Fichier | Rôle | Cibles |
|---------|------|--------|
| `Dockerfile.backend` | API FastAPI (Python 3.11-slim) | `base` |
| `Dockerfile.frontend` | Frontend Vite/React | `dev`, `build`, `production` |

## Commandes

```bash
docker compose up --build          # pile complète en développement
docker compose logs -f backend     # journaux de l'API
docker compose exec backend pytest # tests dans le conteneur
docker compose down -v             # arrêt + suppression des volumes
```

## Production

- Backend : la cible `base` sert au développement (`--reload`). Pour Railway,
  retirer `--reload` et fixer `--workers`.
- Frontend : construire la cible `production` (nginx) ou déployer sur Vercel
  directement depuis `frontend/`.
