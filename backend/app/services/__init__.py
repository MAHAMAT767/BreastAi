"""Logique métier, indépendante du transport HTTP.

Les routeurs de `app.api` restent minces : validation, appel du service, réponse.
Les services orchestrent les modèles, la base de données et les modules IA.

Modules prévus :
    patient_service.py    — Phase 3, CRUD et historique médical
    analysis_service.py   — Phase 3-4, upload → prétraitement → inférence → Grad-CAM
    report_service.py     — Phase 5, génération du rapport PDF
    assistant_service.py  — Phase 7, dialogue LLM avec disclaimer obligatoire
    audit_service.py      — journalisation des actions sensibles
"""
