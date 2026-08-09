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
| `GET` | `/analyses` | Historique et recherche — voir ci-dessous. |
| `GET` | `/analyses/{id}` | Consulter une analyse. |
| `GET` | `/analyses/{id}/image` | Image `processed` (défaut), `original` ou `gradcam`. |
| `POST` | `/analyses/{id}/infer` | Rejouer l'inférence sur le cliché archivé. |
| `PATCH` | `/analyses/{id}/review` | Commentaire et validation du médecin. |
| `GET` | `/analyses/{id}/report` | Télécharger le compte rendu PDF (produit à la demande). |
| `POST` | `/analyses/{id}/report` | Régénérer le rapport, renvoie l'empreinte. |
| `GET` | `/analyses/{id}/report/verify` | Contrôler l'empreinte du rapport archivé. |

### Historique et recherche

`GET /analyses` accepte les critères suivants, cumulables :

| Paramètre | Effet |
|-----------|-------|
| `patient_id` | Restreint à un dossier. |
| `search` | Code, prénom ou nom du patient, sans distinction de casse. |
| `prediction` | `benign` ou `malignant`. Toute autre valeur : `422`. |
| `status` | `pending`, `processing`, `completed`, `failed`. |
| `date_from` / `date_to` | Bornes de date, **incluses toutes les deux**. |
| `doctor_validated` | `true` / `false`. |
| `limit` / `offset` | Pagination, 100 éléments au maximum par page. |

Deux points d'implémentation qui évitent des bugs classiques :

- **`date_to` est inclusive.** La borne haute est posée au lendemain minuit, en
  strict. Une borne posée au jour même à minuit ferait disparaître toute la
  journée demandée — une analyse de 14 h ne serait jamais trouvée.
- **Le tri départage à identifiant égal** (`created_at DESC, id`). Sans cela,
  deux analyses de même horodatage peuvent changer de place entre deux pages, et
  l'une d'elles n'apparaître sur aucune.

Le comptage et la liste partagent exactement les mêmes conditions : les séparer
finit toujours par produire un total qui ne correspond pas aux lignes affichées.

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
Les transfer syntax compressées (JPEG Lossless, JPEG 2000, RLE) sont décodées via
`pylibjpeg`.

La version de la chaîne est enregistrée dans `preprocessing_version` : sans elle,
impossible de savoir a posteriori si une analyse ancienne est comparable à une
analyse récente.

### Inférence

L'inférence tourne de façon synchrone dans la requête de dépôt : entre 500 et
1500 ms par analyse sur CPU. L'analyse passe `pending` → `processing` →
`completed`. Un échec du modèle met le statut à `failed` avec `error_message` :
l'image reste archivée et l'inférence reste rejouable, car perdre une
mammographie parce que le modèle a échoué serait bien pire que rendre une analyse
sans prédiction.

| Champ | Sens |
|-------|------|
| `prediction` | `benign` ou `malignant` |
| `probability` | Probabilité de la classe **maligne**, quelle que soit la classe prédite |
| `confidence` | Probabilité de la classe effectivement prédite |
| `inference_time_ms` | Durée du passage avant |
| `model_version` | Modèle ayant produit ce résultat |

Le seuil de décision vient du modèle, pas d'un `0.5` codé en dur : en dépistage,
il se règle sur la sensibilité voulue.

> ### ⛔ Modèle actuellement déployé : placeholder sans valeur clinique
>
> Aucun jeu de mammographies annotées n'étant disponible, le modèle chargé est un
> EfficientNet-B0 à **poids ImageNet**, dont la tête de classification est
> initialisée au hasard (avec une graine fixe, pour que les sorties soient au
> moins reproductibles). **Il n'a jamais vu de mammographie.**
>
> Ses prédictions, probabilités et cartes Grad-CAM sont des valeurs arbitraires.
> Elles ne servent qu'à valider la chaîne technique de bout en bout.
>
> Toute réponse concernée porte :
> - `is_placeholder_model: true`
> - `model_version` préfixé par `placeholder-`
> - `model_warning` avec un texte explicite
>
> Le préfixe est stocké en base : une analyse produite par le placeholder reste
> reconnaissable comme telle même après le déploiement d'un vrai modèle.

### Remplacer le modèle

Déposer un checkpoint dans `MODEL_PATH`. Aucune autre modification n'est
nécessaire — ni dans l'inférence, ni dans les services, ni dans l'API.

```python
torch.save(
    {
        "architecture": "efficientnet_b0",     # ou efficientnet_b3
        "class_names": ["benign", "malignant"],
        "preprocessing_version": "v1",
        "threshold": 0.5,
        "version": "efficientnet_b0-cbis-ddsm-v1",
        "state_dict": model.state_dict(),
    },
    "models/breastai_efficientnet.pt",
)
```

Les métadonnées sont **vérifiées** au chargement et un écart fait échouer le
démarrage. C'est délibéré : un ordre de classes inversé ou un prétraitement
différent produirait des prédictions silencieusement fausses, ce qui est bien
pire qu'un service qui refuse de démarrer. Le préfixe `placeholder-` est refusé
pour un modèle entraîné, afin que ce marqueur de provenance reste fiable.

`POST /analyses/{id}/infer` rejoue l'inférence sur une analyse existante, à
partir du cliché archivé : les analyses déjà rendues peuvent être réévaluées
après remplacement du modèle, sans redemander la mammographie.

### Grad-CAM

La carte est calculée sur la dernière couche convolutive pour la classe prédite,
puis superposée à l'image prétraitée — celle **vue par le modèle**, et non
l'originale : afficher la carte sur un autre support laisserait croire à une
correspondance géométrique qui n'existe pas.

`suspicious_region` donne le rectangle englobant la zone la plus activée, en
pixels dans l'image 384×384.

> La carte indique **où le modèle a regardé**, pas où se trouve une lésion. Un
> modèle qui se trompe produit une carte tout aussi nette qu'un modèle qui a
> raison. Ce rappel est renvoyé dans `gradcam_disclaimer`.

### Accès aux images

Les images transitent par l'API, jamais par un service de fichiers statiques :
une mammographie ne doit pas être accessible sans contrôle d'accès. Les réponses
portent `Cache-Control: private, no-store`.

Les chemins de stockage sont construits uniquement à partir d'UUID générés par le
serveur. Le nom de fichier fourni par le client est désinfecté et conservé pour
l'affichage seul — il n'entre jamais dans la construction d'un chemin.

## Assistant conversationnel — `/assistant`

| Méthode | Chemin | Description |
|---------|--------|-------------|
| `GET` | `/assistant/status` | Assistant configuré ou non, modèle en service. |
| `POST` | `/assistant/analyses/{id}` | Poser une question sur une analyse. |

Réservé aux rôles cliniques : l'assistant parle d'un dossier précis, il reste
donc fermé au rôle `researcher`. Quota de 10 questions par minute et par IP —
ici autant une protection budgétaire qu'une protection contre les abus.

Le serveur **ne stocke aucune conversation**. L'historique est renvoyé par le
client à chaque question, tronqué à `ASSISTANT_HISTORY_TURNS` tours : chaque tour
conservé est refacturé à chaque nouvelle question.

### Modèle retenu : `Qwen/Qwen2.5-7B-Instruct`

Le choix a été fait en appelant réellement l'API, pas sur catalogue. Ce qui a été
mesuré, avec le jeton du projet :

| Modèle | Résultat |
|--------|----------|
| `mistralai/Mistral-7B-Instruct-v0.3` | **Indisponible** — « is not a chat model » sur le routeur |
| `mistralai/Mistral-7B-Instruct-v0.2`, `Mistral-Small-24B` | Indisponibles sur les fournisseurs actifs |
| `google/gemma-2-9b-it` | Indisponible |
| `meta-llama/Llama-3.1-8B-Instruct` | Disponible, mais **refuse de répondre** |
| `Qwen/Qwen2.5-7B-Instruct` | Disponible, répond, ~1,8 s |

Llama-3.1-8B est disqualifié par son propre alignement : interrogé sur « pourquoi
cette image est-elle suspecte ? », il répond *« Je ne peux pas fournir
d'information médicale »*, et sur la signification d'un score : *« Je ne peux pas
fournir d'informations qui pourraient être utilisées pour diagnostiquer ou
traiter un cancer »*. Le vocabulaire oncologique déclenche un refus systématique,
alors même que la question porte sur le fonctionnement d'un classifieur.

Qwen2.5-7B-Instruct répond, en français correct, trois fois plus vite, suit la
consigne de correction des prémisses fausses, et ses poids sont ouverts
(Apache-2.0) — ce qui compte pour un outil médical : le modèle reste auditable et
substituable. Fenêtre de contexte de 32 k jetons, très au-delà des ~1 300 jetons
qu'atteint une conversation de trois tours ici.

`ASSISTANT_MODEL` permet d'en changer sans toucher au code.

### ⚠️ Limites du tier gratuit — mesurées, pas estimées

L'API historique `api-inference.huggingface.co` **n'existe plus** (le nom de
domaine ne résout pas). Les appels passent par
`https://router.huggingface.co/v1`, compatible avec l'API OpenAI, qui redirige
vers un fournisseur tiers — `together` dans nos essais.

| Point | Constat |
|-------|---------|
| **Crédit mensuel** | Très faible. **Épuisé après une quinzaine d'appels** de mise au point, avec un HTTP `402` : *« You have depleted your monthly included credits »*. |
| **Débit** | Aucun `429` rencontré avant l'épuisement du crédit ; c'est le crédit qui limite, pas la cadence. |
| **En-têtes de quota** | Aucun. Impossible de connaître le solde autrement qu'en recevant un `402`. |
| **Coût par question** | ~700 à 1 400 jetons d'entrée selon la longueur de l'historique, ~100 de sortie. Le contexte de l'analyse pèse à lui seul ~600 jetons. |
| **Latence** | 1,5 à 2 s par réponse. |

**Conséquence pratique : l'assistant s'arrêtera de fonctionner rapidement sur un
compte gratuit.** Il faut soit créditer le compte Hugging Face, soit souscrire à
PRO (20 × le quota inclus), soit pointer `ASSISTANT_BASE_URL` vers un autre
fournisseur compatible OpenAI.

L'application traite ce cas explicitement : un `402` ou un `429` du fournisseur
devient un `503` avec le message *« Le quota du service d'assistance est épuisé.
L'analyse et le rapport restent disponibles sans l'assistant. »* Le reste de la
plateforme continue de fonctionner.

### Ce qui est transmis au fournisseur

**Transmis** : âge, sexe, format du cliché, version de prétraitement,
classification, probabilité, score de confiance, temps d'inférence, version du
modèle, rectangle Grad-CAM.

**Jamais transmis** : nom, prénom, code dossier, date de naissance, téléphone,
adresse postale, adresse e-mail, antécédents, **et le commentaire du médecin**.

Ce dernier point est un arbitrage. Le commentaire du médecin est cliniquement la
donnée la plus riche, mais c'est du texte libre : rien n'empêche un praticien d'y
écrire un nom. Le faire sortir vers un service tiers pour améliorer une réponse
ne vaut pas ce risque.

Le contexte exact est renvoyé dans `context_sent` et affiché dans l'interface,
sous « Contexte transmis au service » : l'utilisateur peut vérifier ce qui est
sorti de l'établissement.

### Les avertissements ne dépendent pas du modèle

Chaque réponse est encadrée **par le code** : l'avertissement de modèle de
démonstration devant, l'avertissement médical derrière. Ils sont dans le champ
`answer` — donc ils suivent le texte s'il est copié ailleurs — et disponibles
séparément (`answer_body`, `model_warning`, `disclaimer`) pour que l'interface
les mette en forme.

Ce n'est pas de la prudence excessive. À la mise au point, avec une consigne
système explicite, le modèle a **omis l'avertissement de démonstration une fois
sur deux**, et a accepté la prémisse fausse « pourquoi cette image est-elle
suspecte ? » alors que la classification produite était bénigne. Un garde-fou
qu'on demande poliment n'est pas un garde-fou.

La consigne système reste utile — après renforcement, le modèle corrige
désormais la prémisse de lui-même : *« Cette image n'est pas suspecte car la
classification produite est bénigne »* — mais elle ne remplace pas la garantie.

## Tableau de bord — `/stats`

`GET /stats/dashboard` renvoie les agrégats affichés par le frontend : compteurs
patients et analyses, répartition bénin/malin, série mensuelle sur douze mois,
temps d'inférence moyen, versions de modèle en service.

Ouvert à **tous les rôles**, `researcher` compris : ces chiffres ne désignent
aucune patiente, et c'est précisément le périmètre de ce rôle, à qui les dossiers
nominatifs restent fermés.

Les mois sans activité sont renvoyés à zéro plutôt qu'omis : un axe temporel
troué se lit comme une baisse là où il n'y a qu'une absence de données.

### Aucune « précision du modèle » n'est publiée

La spécification d'origine demandait un taux de précision. L'API renvoie à la
place `accuracy_available: false` et une note explicative, pour une raison de
fond : **aucun taux d'exactitude n'est calculable.** Il faudrait un diagnostic de
référence par cas — biopsie, suivi — qui n'est pas enregistré.

Le seul taux exposé est `doctor_validation_rate`, nommé « analyses relues par un
médecin » dans l'interface. Il mesure l'activité de relecture, pas la justesse du
modèle. Afficher ce chiffre sous le nom de « précision » laisserait croire que la
performance a été mesurée alors qu'elle ne l'a jamais été — et, avec le modèle
placeholder actuel, ce serait doublement faux.

## Rapport PDF

`GET /analyses/{id}/report` produit le compte rendu s'il n'existe pas encore, puis
le sert. Réservé aux analyses **terminées** : un compte rendu sans résultat n'a
pas d'objet, et en produire un laisserait croire qu'une lecture a eu lieu (`409`).

Contenu : identité patient et antécédents, données de l'examen, résultat chiffré,
image d'origine décodée, superposition Grad-CAM, synthèse automatique, lecture du
médecin, avertissement médical, bloc de signature. Pagination et pied de page sur
chaque page.

### Avertissement placeholder sur le document

Tant que `model_version` porte le préfixe `placeholder-`, le rapport reçoit un
traitement **plus visible que l'API** :

- un bandeau rouge en tête de la première page, avant toute autre information ;
- un **filigrane diagonal répété sur chaque page** : `MODELE DE DEMONSTRATION - SANS VALEUR CLINIQUE` ;
- aucune synthèse automatique n'est rédigée — décrire un cliché à partir de
  sorties arbitraires serait pire que se taire.

Un rapport imprimé circule hors de l'application : il est transmis, photocopié,
photographié. Il doit se dénoncer seul, sans dépendre du contexte dans lequel il
a été produit. Ces éléments disparaissent d'eux-mêmes dès qu'un modèle entraîné
est déployé, sans intervention.

### Signature

Empreinte **HMAC-SHA256** dérivée de `SECRET_KEY`, imprimée sur le document et
stockée dans `report_signature`. Elle couvre :

`analysis_id · code patient · prédiction · probabilité · model_version ·
preprocessing_version · commentaire du médecin · validation · date d'établissement`

La lecture médicale est couverte au même titre que la sortie du modèle : c'est
elle qui fait foi cliniquement, et c'est elle qu'un tiers aurait le plus
d'intérêt à modifier.

`GET /analyses/{id}/report/verify` recalcule l'empreinte et la compare, en temps
constant. Si le dossier a été révisé depuis, la vérification échoue et le rapport
doit être régénéré — c'est le comportement voulu.

> **Ce n'est pas une signature électronique qualifiée.** Il n'y a ni certificat,
> ni autorité de certification, ni horodatage opposable. L'empreinte détecte
> qu'un rapport ne correspond plus à l'analyse enregistrée ; elle n'a aucune
> valeur probante face à un tiers. Une signature PAdES/eIDAS relève de la
> checklist avant production.

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

## Adresses e-mail

### En entrée : les domaines de réseau privé sont acceptés

Les schémas d'écriture utilisent `EmailAddress`
(`backend/app/models/email_address.py`) et non `EmailStr`. La différence tient à
une seule chose : les domaines à usage réservé qui désignent un réseau privé
sont acceptés.

| Domaine | Accepté | Raison |
|---------|---------|--------|
| `medecin@hopital.local` | ✅ | Réseau interne d'un établissement de soins |
| `medecin@hopital.internal` | ✅ | idem |
| `medecin@hopital.lan` | ✅ | idem |
| `medecin@hopital.td` | ✅ | Domaine public ordinaire |
| `medecin@hopital.test` | ❌ | Réservé aux tests, ne peut désigner aucune adresse réelle |
| `medecin@hopital.invalid` | ❌ | idem |
| `medecin@localhost` | ❌ | idem |
| `pas-un-email`, `sans-domaine@`, `medecin@hopital` | ❌ | Syntaxe invalide |

**Seule** la restriction sur ces trois TLD est levée. Toute la validation de
syntaxe d'`email-validator` reste en vigueur : arobase manquante, partie locale
ou domaine vide, domaine sans point, caractères interdits, arobases multiples.

`email-validator` 2.2 n'expose aucun paramètre par appel pour cela — ni
`allow_special_use_domains`, qui n'existe pas, ni `globally_deliverable=False`,
qui ne lève pas cette vérification. Le point d'extension prévu par la
bibliothèque est sa liste de module `SPECIAL_USE_DOMAIN_NAMES`, restreinte une
fois pour toutes au chargement.

Aucune résolution DNS n'est effectuée : interroger le DNS à chaque création de
dossier ajouterait de la latence et ferait échouer la saisie hors connexion.

### En sortie : aucune revalidation

Les schémas de lecture (`UserRead`, `PatientRead`) ne dérivent pas des schémas
d'écriture et déclarent `email: str`.

Revalider une adresse **en sortie** ne protège de rien — la donnée est déjà en
base — mais transforme le moindre écart en erreur 500. C'est exactement ce qui
se produisait avant ce correctif : un compte en `.local` pouvait se connecter,
mais `GET /auth/me` échouait en 500 et l'application restait inutilisable.

Règle générale : valider strictement ce qui entre, ne jamais revalider ce qui sort.

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
| Domaines `.test`, `.invalid`, `localhost` refusés | Une adresse de test ne peut pas entrer dans un dossier patient — voir la section « Adresses e-mail » | délibéré |
| Modèle placeholder | Aucune valeur clinique — voir l'encadré ci-dessus | dès qu'un dataset annoté est disponible |
| JPEG-LS non pris en charge | Nécessite `pyjpegls`, non installé. JPEG Lossless, JPEG 2000 et RLE fonctionnent | à arbitrer |
| Stockage sur disque local, non chiffré | Les mammographies ne sont ni sauvegardées ni chiffrées au repos | avant déploiement |
| Inférence synchrone | 500 à 1500 ms ajoutés à chaque dépôt | si le volume augmente |
| Taille lue en mémoire avant contrôle | Un fichier de 50 Mo est intégralement chargé avant d'être mesuré | 8 |

L'ensemble des points à traiter avant une exposition à des patientes réelles est
rassemblé dans [PRODUCTION_CHECKLIST.md](PRODUCTION_CHECKLIST.md).
