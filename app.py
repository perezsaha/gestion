# -*- coding: utf-8 -*-
"""
Application de gestion d'étudiants (CRUD) - Backend Flask
---------------------------------------------------------
Contraintes respectées :
  - un seul fichier (app.py)
  - AUCUNE classe : uniquement des fonctions (def)
  - AUCUN ORM : requêtes SQL directes avec mysql-connector-python
"""

# ============================================================
# 1. IMPORTS
# ============================================================
from flask import Flask, render_template, request, jsonify
import mysql.connector
from mysql.connector import Error

# ============================================================
# 2. CONFIGURATION DE LA CONNEXION MYSQL (WampServer)
# ============================================================
MYSQL_HOTE = "localhost"
MYSQL_PORT = 3306
MYSQL_UTILISATEUR = "root"
MYSQL_MOT_DE_PASSE = ""          # vide par défaut sur WampServer
MYSQL_BASE = "etudiants"

# Niveaux acceptés et longueurs maximales (identiques à la table SQL)
NIVEAUX_VALIDES = ["L1", "L2", "L3", "M1", "M2"]
LONGUEUR_MAX = {"matricule": 20, "nom": 50, "prenom": 50}

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
            "démarré (icône verte) et que la base «etudiants » existe.",
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
# 5. ROUTES FLASK (elles appellent les fonctions ci-dessus)
# ============================================================
@app.route("/")
def page_accueil():
    """Affiche la page principale."""
    return render_template("index.html")


@app.route("/api/etudiants", methods=["GET"])
def route_lister():
    try:
        return jsonify({"succes": True, "etudiants": lister_etudiants()})
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


# ============================================================
# 6. POINT D'ENTRÉE
# ============================================================
if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
