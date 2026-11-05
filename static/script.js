/* ============================================================
   Gestion des étudiants - Interface (JavaScript vanilla)
   Le tri, l'export PDF et la page d'impression sont réalisés
   par le serveur Python (app.py) : ici on ne fait qu'afficher
   et envoyer les choix de l'utilisateur.
   ============================================================ */

"use strict";

// ---------- État de l'application ----------
let etudiants = [];            // liste reçue du serveur (déjà triée en Python)
let matriculeEnEdition = null; // null = mode ajout
let matriculeASupprimer = null;

// ---------- Références DOM ----------
const formulaire = document.getElementById("formulaire-etudiant");
const champs = {
    matricule: document.getElementById("matricule"),
    nom: document.getElementById("nom"),
    prenom: document.getElementById("prenom"),
    niveau: document.getElementById("niveau"),
};
const boutonValider = document.getElementById("bouton-valider");
const boutonAnnuler = document.getElementById("bouton-annuler");
const boutonPdf = document.getElementById("bouton-pdf");
const boutonImprimer = document.getElementById("bouton-imprimer");
const corpsTableau = document.getElementById("corps-tableau");
const messageVide = document.getElementById("message-vide");
const compteur = document.getElementById("compteur");
const titreFormulaire = document.getElementById("titre-formulaire");
const zoneMessages = document.getElementById("messages");
const dialogue = document.getElementById("dialogue-suppression");
const texteSuppression = document.getElementById("texte-suppression");

const NIVEAUX_VALIDES = ["L1", "L2", "L3", "M1", "M2"];


/* ============================================================
   1. OPTIONS DE TRI (envoyées au serveur Python)
   ============================================================ */

/** Construit la partie d'adresse ?algorithme=...&champ=...&ordre=... */
function parametresTri() {
    const parametres = new URLSearchParams({
        algorithme: document.querySelector('input[name="algorithme"]:checked').value,
        champ: document.getElementById("champ-tri").value,
        ordre: document.getElementById("ordre-tri").value,
    });
    return parametres.toString();
}


/* ============================================================
   2. AFFICHAGE
   ============================================================ */

/** Reconstruit le tableau HTML à partir de la liste `etudiants`. */
function afficherTableau() {
    corpsTableau.textContent = "";

    etudiants.forEach(function (etudiant) {
        const ligne = document.createElement("tr");

        ["matricule", "nom", "prenom", "niveau"].forEach(function (champ) {
            const cellule = document.createElement("td");
            cellule.textContent = etudiant[champ];   // textContent : pas d'injection HTML
            ligne.appendChild(cellule);
        });

        const cellActions = document.createElement("td");
        cellActions.className = "colonne-actions";
        cellActions.appendChild(creerBouton("Modifier", "bouton-secondaire", function () {
            demarrerEdition(etudiant);
        }));
        cellActions.appendChild(creerBouton("Supprimer", "bouton-danger", function () {
            demanderSuppression(etudiant);
        }));
        ligne.appendChild(cellActions);

        corpsTableau.appendChild(ligne);
    });

    const vide = etudiants.length === 0;
    messageVide.hidden = !vide;
    compteur.textContent = etudiants.length;

    // Les boutons PDF et Imprimer sont désactivés si le tableau est vide
    boutonPdf.disabled = vide;
    boutonImprimer.disabled = vide;
}

function creerBouton(texte, classe, action) {
    const bouton = document.createElement("button");
    bouton.type = "button";
    bouton.className = "bouton bouton-petit " + classe;
    bouton.textContent = texte;
    bouton.addEventListener("click", action);
    return bouton;
}

/** Affiche un message de succès ou d'erreur pendant quelques secondes. */
function afficherMessage(texte, type) {
    const message = document.createElement("div");
    message.className = "message message-" + type;
    message.textContent = texte;
    zoneMessages.appendChild(message);
    setTimeout(function () { message.remove(); }, 5000);
}


/* ============================================================
   3. COMMUNICATION AVEC LE SERVEUR (API Flask)
   ============================================================ */

/** Envoie une requête et retourne la réponse JSON (ou une erreur lisible). */
async function appelerApi(url, options) {
    try {
        const reponse = await fetch(url, options);
        const donnees = await reponse.json();
        return { ok: reponse.ok && donnees.succes, donnees: donnees };
    } catch (erreur) {
        return {
            ok: false,
            donnees: { message: "Impossible de joindre le serveur Flask. Vérifiez qu'il est lancé." },
        };
    }
}

/** Demande au serveur la liste triée selon les options choisies. */
async function chargerEtudiants() {
    const resultat = await appelerApi("/api/etudiants?" + parametresTri());
    if (resultat.ok) {
        etudiants = resultat.donnees.etudiants;
        afficherTableau();
    } else {
        afficherMessage(resultat.donnees.message, "erreur");
    }
}


/* ============================================================
   4. FORMULAIRE : validation, ajout, modification
   ============================================================ */

function afficherErreurChamp(nom, texte) {
    document.getElementById("erreur-" + nom).textContent = texte;
    champs[nom].closest(".champ").classList.toggle("champ-invalide", texte !== "");
}

/** Validation côté client (le serveur revalide ensuite). */
function validerFormulaire() {
    let valide = true;
    const regles = [
        ["matricule", "Le matricule est obligatoire."],
        ["nom", "Le nom est obligatoire."],
        ["prenom", "Le prénom est obligatoire."],
    ];

    regles.forEach(function (regle) {
        const vide = champs[regle[0]].value.trim() === "";
        afficherErreurChamp(regle[0], vide ? regle[1] : "");
        if (vide) { valide = false; }
    });

    const niveauOk = NIVEAUX_VALIDES.indexOf(champs.niveau.value) !== -1;
    afficherErreurChamp("niveau", niveauOk ? "" : "Choisissez un niveau.");
    if (!niveauOk) { valide = false; }

    return valide;
}

function reinitialiserFormulaire() {
    formulaire.reset();
    matriculeEnEdition = null;
    champs.matricule.disabled = false;
    titreFormulaire.textContent = "Ajouter un étudiant";
    boutonValider.textContent = "Ajouter l'étudiant";
    boutonAnnuler.hidden = true;
    Object.keys(champs).forEach(function (nom) { afficherErreurChamp(nom, ""); });
}

/** Passe le formulaire en mode modification (le matricule reste fixe). */
function demarrerEdition(etudiant) {
    matriculeEnEdition = etudiant.matricule;
    champs.matricule.value = etudiant.matricule;
    champs.matricule.disabled = true;
    champs.nom.value = etudiant.nom;
    champs.prenom.value = etudiant.prenom;
    champs.niveau.value = etudiant.niveau;
    titreFormulaire.textContent = "Modifier l'étudiant";
    boutonValider.textContent = "Enregistrer les modifications";
    boutonAnnuler.hidden = false;
    champs.nom.focus();
    formulaire.scrollIntoView({ behavior: "smooth", block: "center" });
}

async function soumettreFormulaire(evenement) {
    evenement.preventDefault();
    if (!validerFormulaire()) { return; }

    const corps = JSON.stringify({
        matricule: champs.matricule.value.trim(),
        nom: champs.nom.value.trim(),
        prenom: champs.prenom.value.trim(),
        niveau: champs.niveau.value,
    });
    const entetes = { "Content-Type": "application/json" };

    const resultat = (matriculeEnEdition === null)
        ? await appelerApi("/api/etudiants", { method: "POST", headers: entetes, body: corps })
        : await appelerApi("/api/etudiants/" + encodeURIComponent(matriculeEnEdition),
                           { method: "PUT", headers: entetes, body: corps });

    if (resultat.ok) {
        afficherMessage(resultat.donnees.message, "succes");
        reinitialiserFormulaire();
        await chargerEtudiants();
    } else {
        afficherMessage(resultat.donnees.message, "erreur");
    }
}


/* ============================================================
   5. SUPPRESSION AVEC CONFIRMATION
   ============================================================ */

function demanderSuppression(etudiant) {
    matriculeASupprimer = etudiant.matricule;
    texteSuppression.textContent =
        etudiant.prenom + " " + etudiant.nom + " (" + etudiant.matricule + ") sera supprimé définitivement.";
    dialogue.showModal();
}

async function confirmerSuppression() {
    if (dialogue.returnValue !== "confirmer" || matriculeASupprimer === null) { return; }

    const resultat = await appelerApi(
        "/api/etudiants/" + encodeURIComponent(matriculeASupprimer),
        { method: "DELETE" });

    if (resultat.ok) {
        afficherMessage(resultat.donnees.message, "succes");
        if (matriculeEnEdition === matriculeASupprimer) { reinitialiserFormulaire(); }
    } else {
        afficherMessage(resultat.donnees.message, "erreur");
    }
    matriculeASupprimer = null;
    await chargerEtudiants();
}


/* ============================================================
   6. EXPORT PDF ET IMPRESSION (réalisés par le serveur Python)
   ============================================================ */

/** Télécharge le PDF généré par Python, avec le tri actuellement choisi. */
function exporterPdf() {
    if (etudiants.length === 0) { return; }
    window.location.href = "/api/etudiants/pdf?" + parametresTri();
}

/** Ouvre la page d'impression générée par Python (la boîte d'impression s'ouvre seule). */
function imprimerListe() {
    if (etudiants.length === 0) { return; }
    window.open("/imprimer?" + parametresTri(), "_blank");
}


/* ============================================================
   7. INITIALISATION
   ============================================================ */

formulaire.addEventListener("submit", soumettreFormulaire);
boutonAnnuler.addEventListener("click", reinitialiserFormulaire);
boutonPdf.addEventListener("click", exporterPdf);
boutonImprimer.addEventListener("click", imprimerListe);
dialogue.addEventListener("close", confirmerSuppression);

// Tout changement d'option de tri redemande la liste triée au serveur
document.querySelectorAll('input[name="algorithme"]').forEach(function (radio) {
    radio.addEventListener("change", chargerEtudiants);
});
document.getElementById("champ-tri").addEventListener("change", chargerEtudiants);
document.getElementById("ordre-tri").addEventListener("change", chargerEtudiants);

chargerEtudiants();
