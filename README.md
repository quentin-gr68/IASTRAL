<div align="center">

<img src="logo-IASTRAL.jpg" alt="Logo IASTRAL" width="180"/>

# IASTRAL

**Outil de sauvegarde et migration de données Windows**

Sauvegardez vos dossiers, vos favoris et vos mots de passe de navigateur en quelques clics — avec vérification d'intégrité, mode simulation et rapport PDF automatique.

![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Plateforme-Windows-0078D6?logo=windows&logoColor=white)
![License](https://img.shields.io/badge/Licence-MIT-green)
![Status](https://img.shields.io/badge/Statut-Stable-brightgreen)

</div>

---

## 📋 Sommaire

- [Aperçu](#-aperçu)
- [Fonctionnalités](#-fonctionnalités)
- [Installation](#-installation)
- [Utilisation](#-utilisation)
- [Structure du projet](#-structure-du-projet)
- [Avertissement Windows SmartScreen](#️-avertissement-windows-smartscreen)
- [Sécurité](#-sécurité)
- [Roadmap](#-roadmap)
- [Licence](#-licence)

---

## 🔎 Aperçu

**IASTRAL** est une application de bureau Windows pensée pour migrer ou sauvegarder rapidement les données d'un poste : dossiers personnels (Bureau, Documents, Images...), favoris et mots de passe de navigateurs. Elle a été conçue pour être utilisable aussi bien par un particulier que par un technicien lors d'un dépannage ou d'une migration de poste.

Tout se passe dans une interface graphique simple, sans ligne de commande, avec un thème clair/sombre et une détection automatique des clés USB connectées.

---

## ✨ Fonctionnalités

### Sauvegarde & migration
- 📁 Sélection des dossiers Windows standards (Bureau, Documents, Téléchargements, Images, Musique, Vidéos)
- 🧪 **Mode simulation (dry-run)** — visualisez ce qui serait copié sans rien déplacer
- 🔐 **Vérification d'intégrité SHA-256** sur chaque fichier copié
- 🔁 **Système de retry automatique** (5 secondes) en cas de fichier verrouillé
- 🧰 **Filtre par extension** — ne copier que certains types de fichiers (`.pdf`, `.docx`, `.jpg`...)
- 💾 Vérification de l'espace disque disponible avant de démarrer

### Navigateurs
- 🌐 Détection automatique des profils installés : Chrome, Edge, Brave, Vivaldi, Firefox, Opera, Opera GX, Internet Explorer
- ⭐ Sauvegarde des favoris
- 🔑 Sauvegarde des mots de passe enregistrés
- ⚡ Boutons de sélection rapide (tout cocher / tout décocher)

### Périphériques & destination
- 🔌 Détection automatique des clés USB / disques amovibles connectés
- 📂 Choix manuel du dossier de destination

### Rapports & suivi
- 📊 Rapport PDF généré automatiquement en fin de migration (logo, statistiques, journal)
- 📄 Export du journal d'activité au format `.txt`
- 📈 Tableau de bord récapitulatif (fichiers copiés, ignorés, taille totale)

### Interface
- 🌗 Thème clair / sombre avec bascule manuelle
- 💡 Infobulles d'aide contextuelle sur les boutons principaux
- 🧷 Sauvegarde de vos préférences entre deux lancements (dossier de destination, cases cochées...)

---

## 🛠️ Installation

### Option 1 — Exécutable Windows (recommandé, aucune installation requise)

1. Rendez-vous dans l'onglet [**Releases**](../../releases) de ce dépôt
2. Téléchargez la dernière version de `IASTRAL.exe`
3. Lancez le fichier — aucune installation de Python n'est nécessaire

> ⚠️ Voir la section [Avertissement Windows SmartScreen](#️-avertissement-windows-smartscreen) ci-dessous au premier lancement.

### Option 2 — Depuis le code source (pour développeurs)

**Prérequis :** Python 3.10 ou supérieur, sous Windows.

```bash
git clone https://github.com/quentin-gr68/IASTRAL.git
cd IASTRAL
pip install customtkinter pillow matplotlib fpdf2 psutil
python main.py
```

---

## 🚀 Utilisation

1. **Choisissez une destination** — manuellement via "Parcourir", ou laissez IASTRAL détecter une clé USB connectée
2. **Cochez les dossiers et/ou navigateurs** à inclure dans la sauvegarde
3. *(Optionnel)* Renseignez un **filtre d'extension** si vous ne voulez copier que certains types de fichiers
4. Cliquez sur **ANALYSER** pour estimer la taille totale et vérifier l'espace disque disponible
5. Cliquez sur **SIMULATION** pour un essai à blanc, ou **DÉMARRER** pour lancer la copie réelle
6. À la fin, retrouvez votre **rapport PDF** et le **journal d'activité** dans le dossier de destination

---

## 📂 Structure du projet

```
IASTRAL/
├── main.py              # Application complète (UI + logique)
├── logo-IASTRAL.jpg     # Logo affiché dans l'application et les rapports PDF
├── .gitignore           # Fichiers exclus du suivi Git
└── README.md            # Ce fichier
```

> Le fichier `.iastral_state.json` (préférences utilisateur) est généré automatiquement au premier lancement et n'est volontairement pas suivi par Git.

---

## ⚠️ Avertissement Windows SmartScreen

Au premier lancement de `IASTRAL.exe`, Windows affichera probablement :

> **"Windows a protégé votre ordinateur"**

C'est un comportement **normal** pour tout exécutable non signé par un certificat payant, et non un signe de danger. Pour lancer l'application :

1. Cliquez sur **"Plus d'infos"**
2. Cliquez sur **"Exécuter quand même"**

---

## 🔒 Sécurité

- Les mots de passe de navigateurs sont copiés **tels que stockés par Windows** (chiffrés via DPAPI, liés au compte utilisateur). Ils restent illisibles sur une autre machine sans la clé du compte d'origine.
- Conservez vos sauvegardes contenant des mots de passe dans un endroit sûr (clé USB chiffrée, coffre-fort numérique).
- IASTRAL ne transmet **aucune donnée** sur Internet — tout le traitement est local.

---

## 🗺️ Roadmap

- [ ] Packaging avec installeur (.msi)
- [ ] Signature de code pour supprimer l'avertissement SmartScreen
- [ ] Chiffrement optionnel du dossier de migration par mot de passe
- [ ] Support multi-langue (FR / EN)

---

## 📄 Licence

Ce projet est distribué sous licence MIT — voir le fichier [LICENSE](LICENSE) pour plus de détails.

---

<div align="center">

Développé par **Quentin** — [github.com/quentin-gr68](https://github.com/quentin-gr68)

</div>
