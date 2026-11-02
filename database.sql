-- ============================================================
-- Script de création de la base de données : gestion_etudiants
-- À exécuter dans phpMyAdmin (onglet SQL) ou en ligne de commande
-- ============================================================

CREATE DATABASE IF NOT EXISTS gestion_etudiants
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_general_ci;

USE gestion_etudiants;

-- Table des étudiants
CREATE TABLE IF NOT EXISTS etudiant (
    matricule VARCHAR(20)  NOT NULL,
    nom       VARCHAR(50)  NOT NULL,
    prenom    VARCHAR(50)  NOT NULL,
    niveau    VARCHAR(10)  NOT NULL,
    PRIMARY KEY (matricule)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Données d'exemple (facultatif)
INSERT IGNORE INTO etudiant (matricule, nom, prenom, niveau) VALUES
    ('ETU001', 'Mbarga',  'Joseph', 'L1'),
    ('ETU002', 'Nkoulou', 'Aïcha',  'L2'),
    ('ETU003', 'Fotso',   'Marie',  'L3'),
    ('ETU004', 'Atangana','Pierre', 'M1'),
    ('ETU005', 'Tchoumi', 'Esther', 'M2');
