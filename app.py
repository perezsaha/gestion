# -*- coding: utf-8 -*-
"""
Application de gestion d'étudiants (CRUD) - Backend Flask
---------------------------------------------------------
Contraintes respectées :
  - un seul fichier (app.py)
  - AUCUNE classe définie : uniquement des fonctions (def)
  - AUCUN ORM : requêtes SQL directes avec mysql-connector-python
  - le tri (rapide et fusion), l'export PDF et la page d'impression
    sont réalisés ici, en Python
"""

# ============================================================
# 1. IMPORTS
# ============================================================
import io
import re
import unicodedata
from datetime import datetime

from flask import Flask, render_template, request, jsonify, send_file
import mysql.connector
from mysql.connector import Error

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                Paragraph, Spacer)

# ============================================================
# 2. CONFIGURATION DE LA CONNEXION MYSQL (WampServer)
# ============================================================
MYSQL_HOTE = "localhost"
MYSQL_PORT = 3306
MYSQL_UTILISATEUR = "root"
MYSQL_MOT_DE_PASSE = ""          # vide par défaut sur WampServer
MYSQL_BASE = "gestion_etudiants"

# Niveaux acceptés et longueurs maximales (identiques à la table SQL)
NIVEAUX_VALIDES = ["L1", "L2", "L3", "M1", "M2"]
LONGUEUR_MAX = {"matricule": 20, "nom": 50, "prenom": 50}

# Options de tri acceptées
ALGORITHMES_VALIDES = ["rapide", "fusion"]
CHAMPS_TRI_VALIDES = ["matricule", "nom", "prenom", "niveau"]
ORDRES_VALIDES = ["asc", "desc"]

# Noms des mois en français (pour la date affichée dans le PDF et l'impression)
MOIS_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
           "août", "septembre", "octobre", "novembre", "décembre"]

app = Flask(__name__)


# ============================================================
# 3. FONCTIONS UTILITAIRES
# ============================================================
def obtenir_connexion():
    """Ouvre et retourne une connexion MySQL (lève Error en cas d'échec)."""
    return mysql.connector.connect(
        host=MYSQL_HOTE,
        port=MYSQL_PORT,
        user=MYSQL_UTILISATEUR,
        password=MYSQL_MOT_DE_PASSE,
        database=MYSQL_BASE,
        charset="utf8mb4",
    )


def nettoyer_donnees(donnees):
    """Retourne un dictionnaire propre (valeurs en texte, espaces retirés)."""
    donnees = donnees or {}
    propre = {}
    for champ in ("matricule", "nom", "prenom", "niveau"):
        valeur = donnees.get(champ, "")
        propre[champ] = str(valeur).strip() if valeur is not None else ""
    return propre


def valider_etudiant(donnees):
    """
    Validation côté serveur.
    Retourne une liste de messages d'erreur (liste vide = données valides).
    """
    erreurs = []
    for champ, libelle in (("matricule", "Le matricule"),
                           ("nom", "Le nom"),
                           ("prenom", "Le prénom")):
        if not donnees[champ]:
            erreurs.append(libelle + " est obligatoire.")
        elif len(donnees[champ]) > LONGUEUR_MAX[champ]:
            erreurs.append(libelle + " ne doit pas dépasser "
                           + str(LONGUEUR_MAX[champ]) + " caractères.")
    if donnees["niveau"] not in NIVEAUX_VALIDES:
        erreurs.append("Le niveau doit être l'un de : "
                       + ", ".join(NIVEAUX_VALIDES) + ".")
    return erreurs


def reponse_erreur(message, code):
    """Construit une réponse JSON d'erreur."""
    return jsonify({"succes": False, "message": message}), code


def reponse_erreur_mysql(erreur):
    """Traduit une erreur MySQL en réponse JSON compréhensible."""
    if erreur.errno == 1062:                      # clé primaire dupliquée
        return reponse_erreur("Ce matricule existe déjà.", 409)
    if erreur.errno in (2002, 2003, 2006, 2013, 1045, 1049):
        return reponse_erreur(
            "Connexion à MySQL impossible. Vérifiez que WampServer est "
            "démarré (icône verte) et que la base « gestion_etudiants » existe.",
            503)
    return reponse_erreur("Erreur de base de données : " + str(erreur), 500)


# ============================================================
# 4. FONCTIONS / PROCÉDURES CRUD (une par opération)
# ============================================================
def ajouter_etudiant(matricule, nom, prenom, niveau):
    """CREATE : insère un étudiant. Lève Error si le matricule existe déjà."""
    connexion = obtenir_connexion()
    try:
        curseur = connexion.cursor()
        curseur.execute(
            "INSERT INTO etudiant (matricule, nom, prenom, niveau) "
            "VALUES (%s, %s, %s, %s)",
            (matricule, nom, prenom, niveau),
        )
        connexion.commit()
        curseur.close()
    finally:
        connexion.close()


def lister_etudiants():
    """READ : retourne la liste de tous les étudiants (liste de dictionnaires)."""
    connexion = obtenir_connexion()
    try:
        curseur = connexion.cursor(dictionary=True)
        curseur.execute(
            "SELECT matricule, nom, prenom, niveau FROM etudiant "
            "ORDER BY matricule")
        lignes = curseur.fetchall()
        curseur.close()
        return lignes
    finally:
        connexion.close()


def modifier_etudiant(matricule, nom, prenom, niveau):
    """
    UPDATE : modifie nom, prénom et niveau d'un étudiant.
    Retourne True si l'étudiant existe, False sinon.
    """
    connexion = obtenir_connexion()
    try:
        curseur = connexion.cursor()
        curseur.execute("SELECT 1 FROM etudiant WHERE matricule = %s",
                        (matricule,))
        existe = curseur.fetchone() is not None
        if existe:
            curseur.execute(
                "UPDATE etudiant SET nom = %s, prenom = %s, niveau = %s "
                "WHERE matricule = %s",
                (nom, prenom, niveau, matricule),
            )
            connexion.commit()
        curseur.close()
        return existe
    finally:
        connexion.close()


def supprimer_etudiant(matricule):
    """DELETE : supprime un étudiant. Retourne True si une ligne a été supprimée."""
    connexion = obtenir_connexion()
    try:
        curseur = connexion.cursor()
        curseur.execute("DELETE FROM etudiant WHERE matricule = %s",
                        (matricule,))
        connexion.commit()
        supprime = curseur.rowcount > 0
        curseur.close()
        return supprime
    finally:
        connexion.close()


# ============================================================
# 5. ALGORITHMES DE TRI (écrits from scratch, sans sorted() ni .sort())
# ============================================================
def normaliser_texte(texte):
    """Met un texte en minuscules et sans accents pour comparer équitablement."""
    decompose = unicodedata.normalize("NFD", str(texte))
    sans_accents = "".join(c for c in decompose
                           if unicodedata.category(c) != "Mn")
    return sans_accents.casefold()


def cle_de_tri(etudiant, champ):
    """
    Construit la clé de comparaison d'un étudiant pour un champ donné.
    Les nombres contenus dans le texte sont comparés comme des nombres
    (ETU2 passe avant ETU10).
    """
    texte = normaliser_texte(etudiant[champ])
    morceaux = re.split(r"(\d+)", texte)          # alterne texte / nombre
    cle = []
    for position, morceau in enumerate(morceaux):
        if position % 2 == 1:                     # positions impaires = chiffres
            cle.append(int(morceau))
        else:
            cle.append(morceau)
    return cle


def comparer(a, b, champ, ordre):
    """
    Compare deux étudiants : retourne -1 (a avant b), 0 (équivalents)
    ou 1 (a après b). L'ordre décroissant inverse le résultat.
    """
    cle_a = cle_de_tri(a, champ)
    cle_b = cle_de_tri(b, champ)
    if cle_a < cle_b:
        resultat = -1
    elif cle_a > cle_b:
        resultat = 1
    else:
        resultat = 0
    return -resultat if ordre == "desc" else resultat


def tri_rapide(liste, champ, ordre):
    """
    TRI RAPIDE (Quick Sort) : pivot au milieu, partition en trois groupes
    (plus petits, égaux, plus grands), puis tri récursif des deux extrêmes.
    Retourne une NOUVELLE liste triée.
    """
    if len(liste) <= 1:
        return liste[:]
    pivot = liste[len(liste) // 2]
    plus_petits = []
    egaux = []
    plus_grands = []
    for element in liste:
        c = comparer(element, pivot, champ, ordre)
        if c < 0:
            plus_petits.append(element)
        elif c > 0:
            plus_grands.append(element)
        else:
            egaux.append(element)
    return (tri_rapide(plus_petits, champ, ordre)
            + egaux
            + tri_rapide(plus_grands, champ, ordre))


def fusionner(gauche, droite, champ, ordre):
    """Fusionne deux listes déjà triées en une seule liste triée."""
    resultat = []
    i = 0
    j = 0
    while i < len(gauche) and j < len(droite):
        if comparer(gauche[i], droite[j], champ, ordre) <= 0:
            resultat.append(gauche[i])
            i += 1
        else:
            resultat.append(droite[j])
            j += 1
    while i < len(gauche):
        resultat.append(gauche[i])
        i += 1
    while j < len(droite):
        resultat.append(droite[j])
        j += 1
    return resultat


def tri_fusion(liste, champ, ordre):
    """
    TRI FUSION (Merge Sort) : coupe la liste en deux, trie chaque moitié
    récursivement, puis fusionne. Tri stable. Retourne une NOUVELLE liste.
    """
    if len(liste) <= 1:
        return liste[:]
    milieu = len(liste) // 2
    gauche = tri_fusion(liste[:milieu], champ, ordre)
    droite = tri_fusion(liste[milieu:], champ, ordre)
    return fusionner(gauche, droite, champ, ordre)


def trier_etudiants(liste, algorithme, champ, ordre):
    """Applique l'algorithme choisi ("rapide" ou "fusion") sur la liste."""
    if algorithme == "fusion":
        return tri_fusion(liste, champ, ordre)
    return tri_rapide(liste, champ, ordre)


def lire_parametres_tri():
    """
    Lit les options de tri dans l'adresse (?algorithme=...&champ=...&ordre=...).
    Retourne (algorithme, champ, ordre, erreurs).
    """
    algorithme = request.args.get("algorithme", "rapide")
    champ = request.args.get("champ", "matricule")
    ordre = request.args.get("ordre", "asc")
    erreurs = []
    if algorithme not in ALGORITHMES_VALIDES:
        erreurs.append("Algorithme de tri invalide.")
    if champ not in CHAMPS_TRI_VALIDES:
        erreurs.append("Champ de tri invalide.")
    if ordre not in ORDRES_VALIDES:
        erreurs.append("Ordre de tri invalide.")
    return algorithme, champ, ordre, erreurs


# ============================================================
# 6. DATES, EXPORT PDF ET IMPRESSION
# ============================================================
def date_lisible():
    """Date du jour en français, par exemple « 3 novembre 2026 »."""
    maintenant = datetime.now()
    return (str(maintenant.day) + " " + MOIS_FR[maintenant.month - 1]
            + " " + str(maintenant.year))


def date_iso():
    """Date du jour au format AAAA-MM-JJ (pour le nom du fichier PDF)."""
    return datetime.now().strftime("%Y-%m-%d")


def generer_pdf(etudiants):
    """
    Construit le PDF de la liste (déjà triée) et le retourne dans un
    tampon mémoire : titre, date, en-tête du tableau et toutes les lignes.
    """
    tampon = io.BytesIO()
    document = SimpleDocTemplate(tampon, pagesize=A4,
                                 title="Liste des étudiants",
                                 leftMargin=40, rightMargin=40,
                                 topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    elements = [
        Paragraph("Liste des étudiants", styles["Title"]),
        Paragraph("Généré le " + date_lisible(), styles["Normal"]),
        Spacer(1, 16),
    ]

    donnees = [["Matricule", "Nom", "Prénom", "Niveau"]]
    for etudiant in etudiants:
        donnees.append([etudiant["matricule"], etudiant["nom"],
                        etudiant["prenom"], etudiant["niveau"]])

    tableau = Table(donnees, repeatRows=1, colWidths=[110, 170, 170, 65])
    tableau.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1B2A41")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#999999")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#F1F4F8")]),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(tableau)

    document.build(elements)
    tampon.seek(0)
    return tampon


# ============================================================
# 7. ROUTES FLASK (elles appellent les fonctions ci-dessus)
# ============================================================
@app.route("/")
def page_accueil():
    """Affiche la page principale."""
    return render_template("index.html")


@app.route("/api/etudiants", methods=["GET"])
def route_lister():
    algorithme, champ, ordre, erreurs = lire_parametres_tri()
    if erreurs:
        return reponse_erreur(" ".join(erreurs), 400)
    try:
        liste = trier_etudiants(lister_etudiants(), algorithme, champ, ordre)
        return jsonify({"succes": True, "etudiants": liste})
    except Error as erreur:
        return reponse_erreur_mysql(erreur)


@app.route("/api/etudiants", methods=["POST"])
def route_ajouter():
    donnees = nettoyer_donnees(request.get_json(silent=True))
    erreurs = valider_etudiant(donnees)
    if erreurs:
        return reponse_erreur(" ".join(erreurs), 400)
    try:
        ajouter_etudiant(donnees["matricule"], donnees["nom"],
                         donnees["prenom"], donnees["niveau"])
        return jsonify({"succes": True,
                        "message": "Étudiant ajouté avec succès."}), 201
    except Error as erreur:
        return reponse_erreur_mysql(erreur)


@app.route("/api/etudiants/<matricule>", methods=["PUT"])
def route_modifier(matricule):
    donnees = nettoyer_donnees(request.get_json(silent=True))
    donnees["matricule"] = matricule.strip()      # le matricule ne change pas
    erreurs = valider_etudiant(donnees)
    if erreurs:
        return reponse_erreur(" ".join(erreurs), 400)
    try:
        if not modifier_etudiant(donnees["matricule"], donnees["nom"],
                                 donnees["prenom"], donnees["niveau"]):
            return reponse_erreur("Étudiant introuvable.", 404)
        return jsonify({"succes": True,
                        "message": "Étudiant modifié avec succès."})
    except Error as erreur:
        return reponse_erreur_mysql(erreur)


@app.route("/api/etudiants/<matricule>", methods=["DELETE"])
def route_supprimer(matricule):
    try:
        if not supprimer_etudiant(matricule.strip()):
            return reponse_erreur("Étudiant introuvable.", 404)
        return jsonify({"succes": True,
                        "message": "Étudiant supprimé avec succès."})
    except Error as erreur:
        return reponse_erreur_mysql(erreur)


@app.route("/api/etudiants/pdf", methods=["GET"])
def route_pdf():
    """Télécharge la liste triée au format PDF."""
    algorithme, champ, ordre, erreurs = lire_parametres_tri()
    if erreurs:
        return reponse_erreur(" ".join(erreurs), 400)
    try:
        liste = trier_etudiants(lister_etudiants(), algorithme, champ, ordre)
    except Error as erreur:
        return reponse_erreur_mysql(erreur)
    if not liste:
        return reponse_erreur("Aucun étudiant à exporter.", 400)
    return send_file(generer_pdf(liste), mimetype="application/pdf",
                     as_attachment=True,
                     download_name="liste_etudiants_" + date_iso() + ".pdf")


@app.route("/imprimer", methods=["GET"])
def route_imprimer():
    """Page d'impression : titre, date et tableau trié (la boîte d'impression s'ouvre seule)."""
    algorithme, champ, ordre, erreurs = lire_parametres_tri()
    if erreurs:
        return " ".join(erreurs), 400
    try:
        liste = trier_etudiants(lister_etudiants(), algorithme, champ, ordre)
    except Error as erreur:
        return "Erreur de base de données : " + str(erreur), 503
    if not liste:
        return "Aucun étudiant à imprimer.", 400
    return render_template("impression.html", etudiants=liste,
                           date=date_lisible())


# ============================================================
# 8. POINT D'ENTRÉE
# ============================================================
if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
