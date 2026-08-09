"""Logique métier, indépendante du transport HTTP.

Les routeurs de `app.api` restent minces : validation, appel du service, réponse.
Les services orchestrent les modèles, la base de données et les modules IA.
"""
