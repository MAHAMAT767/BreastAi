# Checklist avant mise en production

BreastAI manipule des données de santé à caractère personnel et produit des
sorties susceptibles d'influencer une décision médicale. Cette liste recense ce
qui doit être traité **avant** toute exposition à des patientes réelles.

Rien de ce qui suit n'est théorique : chaque point correspond à un choix assumé
pendant le développement, pris pour avancer, et qui devient inacceptable en
production.

Statut : ⛔ bloquant · ⚠️ à traiter · 📋 à documenter

---

## Modèle et validité clinique

| | Point | Situation actuelle |
|---|-------|--------------------|
| ⛔ | **Aucun modèle entraîné sur mammographies** | Le modèle chargé est un placeholder à poids ImageNet, tête initialisée au hasard. Ses sorties sont du bruit. Voir `backend/app/ai/inference/loader.py`. |
| ⛔ | Validation sur un jeu de test indépendant | Aucune métrique mesurée : ni sensibilité, ni spécificité, ni ROC-AUC. |
| ⛔ | Seuil de décision choisi sur la sensibilité | Fixé à 0,5 par défaut. En dépistage, un faux négatif coûte infiniment plus qu'un faux positif : le seuil se règle sur la sensibilité voulue, pas sur l'accuracy. |
| ⛔ | Découpage des données par patient | À vérifier au moment de l'entraînement : deux clichés d'une même patiente répartis entre train et test gonflent artificiellement les métriques. |
| ⛔ | Validation sur la population cible | Un modèle entraîné sur des données nord-américaines ou européennes n'est pas validé sur une population tchadienne, ni sur le parc de mammographes réellement utilisé. |
| ⚠️ | Fiche modèle publiée | Format décrit dans `models/README.md`, à remplir pour tout modèle déployé. |
| ⚠️ | Statut réglementaire | Le logiciel n'est certifié comme dispositif médical dans aucune juridiction. Vérifier ce qu'exige la réglementation tchadienne avant tout usage clinique. |

## Protection des données

| | Point | Situation actuelle |
|---|-------|--------------------|
| ⛔ | **Stockage des images non chiffré** | Les mammographies, les images Grad-CAM et les rapports PDF — qui contiennent l'identité de la patiente — sont écrits en clair sur le disque local du conteneur (`app/services/storage_service.py`). Ni chiffrés au repos, ni sauvegardés. À remplacer par un stockage objet chiffré, avec accès contrôlé et journalisé. |
| ⛔ | Chiffrement des données patients en base | Nom, date de naissance, antécédents et téléphone sont stockés en clair. À chiffrer au niveau colonne, ou à défaut chiffrer le volume. |
| ⛔ | Sauvegardes chiffrées et restauration testée | Aucune sauvegarde configurée. Une sauvegarde jamais restaurée n'est pas une sauvegarde. |
| ⚠️ | Purge et durée de conservation | Aucune politique définie. La suppression des dossiers est logique : rien n'est jamais réellement effacé. |
| ⚠️ | Anonymisation pour le rôle chercheur | Le rôle existe et est refusé sur les dossiers nominatifs, mais aucune vue anonymisée n'est encore proposée. |
| 📋 | Registre de traitement, information des patientes, consentement | À établir selon le cadre juridique applicable. |

## Sécurité applicative

| | Point | Situation actuelle |
|---|-------|--------------------|
| ⛔ | `SECRET_KEY` généré et hors du dépôt | La valeur par défaut est explicitement non sûre. `python -c "import secrets; print(secrets.token_urlsafe(64))"` |
| ⛔ | Mots de passe par défaut changés | `POSTGRES_PASSWORD`, compte administrateur initial. |
| ⛔ | HTTPS obligatoire | Les jetons JWT et les images transitent en clair sans TLS. |
| ⚠️ | **Compteurs de quota partagés** | La limitation de débit stocke ses compteurs en mémoire, par processus. Avec N workers ou N répliques, un attaquant obtient N fois le quota. Basculer `storage_uri` sur Redis dans `app/auth/rate_limit.py`, ou déployer avec un seul worker. |
| ⚠️ | Envoi des e-mails de réinitialisation | Le jeton est actuellement écrit dans les journaux du serveur. |
| ⚠️ | Taille des dépôts contrôlée en flux | Un fichier est entièrement chargé en mémoire avant d'être mesuré : N dépôts simultanés de 50 Mo saturent la mémoire du processus. |
| ⚠️ | Origine des checkpoints maîtrisée | `torch.load` désérialise du pickle : un fichier `.pt` hostile exécute du code arbitraire au chargement. Ne charger que des modèles produits en interne. |
| ⚠️ | **Signature des rapports sans valeur probante** | L'empreinte HMAC-SHA256 imprimée sur les comptes rendus détecte une altération, mais ne constitue pas une signature électronique qualifiée : ni certificat, ni autorité, ni horodatage opposable. Pour une valeur juridique, passer à une signature PAdES (eIDAS) avec certificat du praticien ou de l'établissement. |
| ⚠️ | Rotation de `SECRET_KEY` | La clé sert aussi à signer les rapports : la changer invalide l'empreinte de **tous** les rapports déjà émis. Prévoir un versionnement des clés avant toute rotation. |
| 📋 | Journaux sans données patients | Vérifié par construction, à revalider à chaque phase. |
| 📋 | Revue des dépendances | `pip-audit` / `npm audit` dans la CI (Phase 8). |

## Exploitation

| | Point | Situation actuelle |
|---|-------|--------------------|
| ⚠️ | Uvicorn sans `--reload` en production | Le Dockerfile est réglé pour le développement. |
| ⚠️ | Inférence synchrone dans la requête HTTP | Mesurée entre 500 et 1500 ms par analyse sur CPU. À passer en tâche de fond si le volume augmente. |
| ⚠️ | Surveillance et alertes | Aucune. Au minimum : taux d'erreur, latence d'inférence, espace disque. |
| 📋 | Procédure de retrait d'un modèle défaillant | `POST /analyses/{id}/infer` permet de réévaluer une analyse après remplacement du modèle. La procédure elle-même reste à écrire. |

## Interface et usage

| | Point | Situation actuelle |
|---|-------|--------------------|
| ⛔ | Avertissement médical visible sur chaque écran de résultat | Présent côté API (`disclaimer`, `model_warning`, `gradcam_disclaimer`). À rendre impossible à manquer côté frontend en Phase 6. |
| ⛔ | Aucun résultat placeholder montré à une patiente | Tant que `is_placeholder_model` vaut `true`, aucune sortie ne doit quitter le cadre technique. Les rapports PDF portent bandeau et filigrane sur chaque page dans ce cas. |
| ⚠️ | Devenir des rapports imprimés | Un PDF sorti de l'application n'est plus contrôlé : ni révocable, ni traçable. Définir qui peut exporter, et ce qu'il advient des copies. |
| ⚠️ | Formation des utilisateurs | Ce qu'est une carte Grad-CAM, ce qu'elle n'est pas, et comment lire une probabilité. |
| 📋 | Traçabilité de la lecture médicale | `doctor_validated` et `doctor_comment` existent ; leur usage doit être inscrit dans le protocole de service. |
