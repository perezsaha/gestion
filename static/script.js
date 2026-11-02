/* ============================================================
   Gestion des étudiants - Logique frontend (JavaScript vanilla)
   ============================================================ */

"use strict";

// ---------- État de l'application ----------
let etudiants = [];            // données brutes reçues du serveur
let affichage = [];            // données triées = ce qui est à l'écran
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
   1. ALGORITHMES DE TRI (écrits from scratch, sans .sort())
   ============================================================ */

/**
 * Compare deux étudiants sur un champ donné.
 * Retourne un nombre négatif, 0 ou positif (le sens dépend de l'ordre).
 * Note : localeCompare sert uniquement à comparer deux textes
 * (gestion des accents) ; la logique de tri est entièrement écrite ici.
 */
function comparer(a, b, champ, ordre) {
    const resultat = String(a[champ]).localeCompare(String(b[champ]), "fr", {
        numeric: true,
        sensitivity: "base",
    });
    return ordre === "desc" ? -resultat : resultat;
}

/**
 * TRI RAPIDE (Quick Sort) - partition en trois groupes
 * (< pivot, = pivot, > pivot) pour bien gérer les valeurs répétées
 * (ex. plusieurs étudiants du même niveau).
 * Retourne un NOUVEAU tableau trié.
 */
function triRapide(tableau, champ, ordre) {
    if (tableau.length <= 1) {
        return tableau.slice();
    }
    const pivot = tableau[Math.floor(tableau.length / 2)];
    const plusPetits = [];
    const egaux = [];
    const plusGrands = [];

    for (let i = 0; i < tableau.length; i++) {
        const c = comparer(tableau[i], pivot, champ, ordre);
        if (c < 0) {
            plusPetits.push(tableau[i]);
        } else if (c > 0) {
            plusGrands.push(tableau[i]);
        } else {
            egaux.push(tableau[i]);
        }
    }
    return triRapide(plusPetits, champ, ordre)
        .concat(egaux, triRapide(plusGrands, champ, ordre));
}

/**
 * TRI FUSION (Merge Sort) - on coupe en deux, on trie chaque moitié,
 * puis on fusionne. Tri stable.
 * Retourne un NOUVEAU tableau trié.
 */
function triFusion(tableau, champ, ordre) {
    if (tableau.length <= 1) {
        return tableau.slice();
    }
    const milieu = Math.floor(tableau.length / 2);
    const gauche = triFusion(tableau.slice(0, milieu), champ, ordre);
    const droite = triFusion(tableau.slice(milieu), champ, ordre);
    return fusionner(gauche, droite, champ, ordre);
}

/** Fusionne deux tableaux déjà triés en un seul tableau trié. */
function fusionner(gauche, droite, champ, ordre) {
    const resultat = [];
    let i = 0;
    let j = 0;
    while (i < gauche.length && j < droite.length) {
        if (comparer(gauche[i], droite[j], champ, ordre) <= 0) {
            resultat.push(gauche[i]);
            i++;
        } else {
            resultat.push(droite[j]);
            j++;
        }
    }
    while (i < gauche.length) { resultat.push(gauche[i]); i++; }
    while (j < droite.length) { resultat.push(droite[j]); j++; }
    return resultat;
}

/** Applique le tri choisi par l'utilisateur sur les données. */
function appliquerTri() {
    const algorithme = document.querySelector('input[name="algorithme"]:checked').value;
    const champ = document.getElementById("champ-tri").value;
    const ordre = document.getElementById("ordre-tri").value;

    affichage = (algorithme === "rapide")
        ? triRapide(etudiants, champ, ordre)
        : triFusion(etudiants, champ, ordre);

    afficherTableau();
}


/* ============================================================
   2. AFFICHAGE
   ============================================================ */

/** Reconstruit le tableau HTML à partir du tableau `affichage`. */
function afficherTableau() {
    corpsTableau.textContent = "";

    affichage.forEach(function (etudiant) {
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

    const vide = affichage.length === 0;
    messageVide.hidden = !vide;
    compteur.textContent = affichage.length;

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

/** Recharge la liste depuis la base puis réapplique le tri courant. */
async function chargerEtudiants() {
    const resultat = await appelerApi("/api/etudiants");
    if (resultat.ok) {
        etudiants = resultat.donnees.etudiants;
        appliquerTri();
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

/** Validation côté client. Retourne true si tout est correct. */
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
   6. EXPORT PDF (jsPDF + jsPDF-AutoTable)
   ============================================================ */

/** Date locale au format YYYY-MM-DD (pour le nom du fichier). */
function dateIso() {
    const d = new Date();
    const mois = String(d.getMonth() + 1).padStart(2, "0");
    const jour = String(d.getDate()).padStart(2, "0");
    return d.getFullYear() + "-" + mois + "-" + jour;
}

/** Date lisible en français (pour le titre du PDF et l'impression). */
function dateLisible() {
    return new Date().toLocaleDateString("fr-FR", {
        day: "numeric", month: "long", year: "numeric",
    });
}

/**
 * Génère le PDF à partir du tableau `affichage` :
 * il respecte donc le tri et l'ordre actuellement appliqués.
 */
function exporterPdf() {
    if (affichage.length === 0) { return; }
    if (!window.jspdf || !window.jspdf.jsPDF) {
        afficherMessage("La bibliothèque jsPDF n'est pas chargée (vérifiez la connexion Internet).", "erreur");
        return;
    }

    const doc = new window.jspdf.jsPDF();

    doc.setFontSize(18);
    doc.text("Liste des étudiants", 14, 20);
    doc.setFontSize(11);
    doc.text("Généré le " + dateLisible(), 14, 28);

    doc.autoTable({
        startY: 34,
        head: [["Matricule", "Nom", "Prénom", "Niveau"]],
        body: affichage.map(function (e) {
            return [e.matricule, e.nom, e.prenom, e.niveau];
        }),
        headStyles: { fillColor: [27, 42, 65] },
        styles: { fontSize: 10 },
    });

    doc.save("liste_etudiants_" + dateIso() + ".pdf");
}


/* ============================================================
   7. IMPRESSION (window.print + @media print dans style.css)
   ============================================================ */

function imprimerListe() {
    if (affichage.length === 0) { return; }
    window.print();
}

// La date est mise à jour juste avant l'impression
// (aussi quand l'utilisateur fait Ctrl+P)
window.addEventListener("beforeprint", function () {
    document.getElementById("date-impression").textContent = "Généré le " + dateLisible();
});


/* ============================================================
   8. INITIALISATION
   ============================================================ */

formulaire.addEventListener("submit", soumettreFormulaire);
boutonAnnuler.addEventListener("click", reinitialiserFormulaire);
boutonPdf.addEventListener("click", exporterPdf);
boutonImprimer.addEventListener("click", imprimerListe);
dialogue.addEventListener("close", confirmerSuppression);

// Tout changement d'option de tri réapplique le tri immédiatement
document.querySelectorAll('input[name="algorithme"]').forEach(function (radio) {
    radio.addEventListener("change", appliquerTri);
});
document.getElementById("champ-tri").addEventListener("change", appliquerTri);
document.getElementById("ordre-tri").addEventListener("change", appliquerTri);

chargerEtudiants();
