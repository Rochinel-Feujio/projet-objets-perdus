"""
Validation de cohérence des champs extraits avant enregistrement.
Ne bloque jamais l'enregistrement : ajoute des alertes à revoir manuellement.
"""

from datetime import datetime


def _parse_date(date_str):
    if not date_str:
        return None
    for fmt in ("%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def validate(doc_type: str, fields: dict) -> list:
    """Retourne une liste d'alertes (chaînes) ; liste vide = rien à signaler."""
    alerts = []
    today = datetime.now()

    if doc_type == "CNI":
        numero = fields.get("numero")
        if not numero or len(numero) != 17 or not numero.isdigit():
            alerts.append("Numéro CNI (NIU) absent ou ne comporte pas 17 chiffres.")

    if doc_type == "RECEPISSE":
        numero = fields.get("numero_recepisse")
        if not numero or len(numero) != 20:
            alerts.append("Numéro de récépissé absent ou ne comporte pas 20 caractères.")

    if doc_type == "PASSEPORT":
        if not fields.get("mrz"):
            alerts.append("Zone MRZ non détectée — confirmer qu'il s'agit bien d'un passeport.")

    if doc_type == "PERMIS":
        if not fields.get("categories"):
            alerts.append("Aucune catégorie (A/B/C/D/E) détectée sur le permis.")

    for date_field in ("date_naissance", "date_delivrance", "date_expiration"):
        raw = fields.get(date_field)
        if raw:
            parsed = _parse_date(raw)
            if parsed is None:
                alerts.append(f"Champ '{date_field}' = '{raw}' n'est pas une date valide (jj/mm/aaaa attendu).")
            elif date_field != "date_expiration" and parsed > today:
                alerts.append(f"Champ '{date_field}' = '{raw}' est dans le futur.")

    if not fields.get("nom"):
        alerts.append("Nom non détecté — photo à reprendre ou vérification manuelle nécessaire.")

    return alerts
