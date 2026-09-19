# Findici — Tesseract : rôle dans le projet et guide d'installation complet

Ce document a un seul but : permettre à quelqu'un qui n'a **jamais touché au projet** d'installer
Findici de zéro, sur son ordinateur, et d'arriver à un résultat qui fonctionne réellement — en
comprenant au passage ce que fait Tesseract, le moteur qui lit le texte sur les photos.

> Ce guide remplace `GUIDE_PADDLEOCR_INSTALLATION.md` : le projet est passé un temps par PaddleOCR
> (moteur OCR par deep learning), puis est **revenu à Tesseract** à la demande explicite du porteur
> du projet — Tesseract est donc de nouveau le moteur utilisé en production. Voir
> `ocr_benchmark/RAPPORT_PaddleOCR_vs_Tesseract.md` pour la comparaison qui avait été faite entre les
> deux moteurs, à titre de contexte historique uniquement.

Suivre les étapes dans l'ordre, du début à la fin.

---

## 1. Tesseract, en une minute

Findici prend une photo (ou un PDF scanné) d'un document administratif — CNI, passeport, permis de
conduire, acte de naissance — et doit :

1. **Deviner de quel document il s'agit** (classification) ;
2. **Lire le texte écrit dessus** (nom, numéro, dates...) ;
3. **Enregistrer ces informations** dans une base de données.

L'étape 2 est celle qui a besoin de Tesseract. **Tesseract OCR** est un moteur de reconnaissance de
caractères open source (créé par HP, puis maintenu par Google) : il transforme une image contenant
du texte en texte réellement exploitable (une chaîne de caractères), en s'appuyant sur des règles et
des modèles de langue entraînés par langue.

Deux choses importantes à savoir avant d'installer quoi que ce soit :

- Contrairement à une bibliothèque Python pure, Tesseract **est un programme séparé installé au
  niveau du système d'exploitation** (comme un logiciel classique) : `pytesseract`, le paquet Python
  utilisé par Findici, n'est qu'une fine couche qui appelle ce programme en ligne de commande. Il
  faut donc installer **deux choses distinctes** : le moteur Tesseract lui-même (paquet système), et
  `pytesseract` (paquet Python). Oublier la première est la cause n°1 des erreurs d'installation.
- **Aucune connexion Internet n'est nécessaire après l'installation** : contrairement à un moteur par
  deep learning qui télécharge ses modèles au premier lancement, les modèles de langue de Tesseract
  sont installés une fois pour toutes avec le paquet système (`tesseract-ocr-fra` pour le français).
  L'application peut ensuite fonctionner totalement hors ligne pour la partie OCR.
- Les documents camerounais sont bilingues (ex. « NOM/SURNAME ») : Findici utilise donc la langue
  combinée `"fra+eng"`, qui lit le français et l'anglais dans la même passe — Tesseract sait combiner
  plusieurs langues en un seul appel (contrairement à certains moteurs par deep learning qui n'en
  acceptent qu'une à la fois).

---

## 2. Prérequis

Avant de commencer, il faut avoir sur l'ordinateur :

- **Python 3.10 ou plus récent** — vérifier avec `python3 --version` (ou `python --version` sur
  Windows). Si absent : [python.org/downloads](https://www.python.org/downloads/).
- Un accès à un terminal (Invite de commandes / PowerShell sous Windows, Terminal sous Mac/Linux),
  avec les droits administrateur pour installer un paquet système.
- Le code du projet Findici (récupéré via `git clone`, ou un dossier ZIP téléchargé et décompressé).

Contrairement à PaddleOCR, Tesseract demande **une installation système en plus** de l'installation
Python — c'est justement l'objet de l'étape suivante.

---

## 3. Étape 1 — Installer le moteur Tesseract (système)

### Sur Ubuntu / Debian (ex. le serveur de déploiement)

```bash
sudo apt update
sudo apt install -y tesseract-ocr tesseract-ocr-fra
```

`tesseract-ocr` installe le moteur et le paquet de langue anglais (inclus par défaut) ;
`tesseract-ocr-fra` ajoute le paquet de langue française, indispensable pour les documents
camerounais rédigés en français. Vérifier l'installation :

```bash
tesseract --version
tesseract --list-langs   # doit afficher au moins "eng" et "fra"
```

### Sur Windows

1. Télécharger l'installeur **UB-Mannheim** (le paquet Windows officieux mais de référence pour
   Tesseract) : [github.com/UB-Mannheim/tesseract/wiki](https://github.com/UB-Mannheim/tesseract/wiki).
2. Lancer l'installeur. **Pendant l'installation, cocher la langue « French »** dans la liste des
   paquets de langue additionnels (l'anglais est inclus par défaut).
3. Noter le dossier d'installation — par défaut `C:\Program Files\Tesseract-OCR\`.
4. Deux options pour que Python trouve Tesseract ensuite :
   - **Ajouter ce dossier au PATH Windows** (recommandé) : Paramètres → Système → À propos →
     Paramètres système avancés → Variables d'environnement → modifier `Path` → ajouter
     `C:\Program Files\Tesseract-OCR\`.
   - **Ou ne rien faire** : `ocr.py` détecte automatiquement ce chemin par défaut si le PATH n'a pas
     été modifié (voir section 5) — pratique si l'installeur a été utilisé avec les options par
     défaut.

### Sur macOS

```bash
brew install tesseract tesseract-lang
```

(`tesseract-lang` installe l'ensemble des paquets de langue, dont le français.)

---

## 4. Étape 2 — Récupérer le projet et installer les dépendances Python

```bash
# Si le projet n'est pas encore sur la machine :
git clone https://github.com/Rochinel-Feujio/projet-objets-perdus.git
cd projet-objets-perdus

# Créer un environnement virtuel (recommandé, évite les conflits avec d'autres projets Python)
python3 -m venv venv

# L'activer :
source venv/bin/activate        # macOS / Linux
venv\Scripts\activate           # Windows (PowerShell ou Invite de commandes)

# Installer toutes les dépendances Python du projet (dont pytesseract)
pip install -r requirements.txt
```

Cette dernière commande installe notamment `pytesseract` (la fine couche Python qui appelle le
programme Tesseract installé à l'étape 3), `opencv-python-headless`, `Pillow`, `streamlit` et les
autres bibliothèques listées dans `requirements.txt`.

---

## 5. Étape 3 — Lancer l'application

Findici est une application web (Streamlit). Une fois dans le dossier du projet, avec
l'environnement virtuel activé :

```bash
streamlit run app.py
```

Un navigateur doit s'ouvrir automatiquement sur `http://localhost:8501` avec l'interface de
Findici. Par défaut, sans configuration supplémentaire, les données sont enregistrées dans un
fichier local `documents.db` (SQLite) — aucune base de données externe n'est nécessaire pour que ça
fonctionne. (Une base PostgreSQL en ligne peut être branchée plus tard, voir le `README.md` complet
du projet, section « Base de données persistante ».)

### Alternative — tester en ligne de commande, sans interface

Utile pour vérifier rapidement que la lecture OCR fonctionne, sans passer par le navigateur :

```bash
python3 tests/generate_sample_images.py        # génère 4 images de test
python3 main.py tests/sample_images/cni_sample.png
```

Sortie attendue :

```
Ceci est : Carte Nationale d'Identité (confiance : 64%)
  nom : NOM EXEMPLE
  numero : 12345678901234567
  date_naissance : 01/01/2000
  date_expiration : 01/01/2030
Informations enregistrées avec succès.
```

Si ce texte s'affiche (avec les bonnes informations lues), l'installation est **fonctionnelle** :
Tesseract, Python et le pipeline complet de Findici fonctionnent ensemble correctement.

---

## 6. Où Tesseract intervient exactement dans le code

Pour comprendre ou modifier le projet plus tard :

| Fichier | Rôle vis-à-vis de Tesseract |
|---|---|
| `ocr.py` | Contient toute la logique d'appel à Tesseract via `pytesseract` (fonction `extract_text`). Détecte aussi automatiquement le chemin d'installation par défaut de Tesseract sous Windows (`_WINDOWS_DEFAULT_PATH`) si le PATH n'a pas été configuré manuellement. |
| `ocr.py` (`DEFAULT_LANG`) | Fixe la langue de lecture à `"fra+eng"` (français + anglais combinés en une seule passe, voir section 1). |
| `ocr.py` (`extract_text`, paramètre `psm`) | Pilote le *page segmentation mode* de Tesseract : `--psm 7` pour une seule ligne de texte (utilisé par `zones.py` sur de petits recadrages de champ), ou essai de plusieurs modes (`3` puis `6`) et conservation du résultat le plus long pour une lecture globale de document. |
| `main.py` (étape 3 du pipeline) | Appelle `extract_text()` une première fois sur l'image entière, juste après le nettoyage/redressement de la photo (`preprocessing.py`) et avant la classification du type de document. |
| `zones.py` | Une fois le type de document connu, rappelle `extract_text()` séparément sur chaque zone découpée (nom, numéro, dates...), avec `psm="7"` puisqu'il s'agit toujours d'une seule ligne de texte par zone. |
| `preprocessing.py` (`_orientation_score`) | Utilise directement `pytesseract.image_to_data()` (indépendamment de `ocr.py`) pour détecter si une photo a été prise « de travers » (90°/180°/270°) avant le reste du traitement, en comptant les mots reconnus avec une confiance suffisante dans chaque orientation candidate. |
| `requirements.txt` | Liste `pytesseract` (le paquet Python). |
| `packages.txt` | Liste `tesseract-ocr` et `tesseract-ocr-fra` — lus automatiquement par Streamlit Community Cloud au déploiement pour installer les paquets système nécessaires. |

En résumé : Tesseract est un **programme système**, `pytesseract` est le **pont Python** vers ce
programme, et `ocr.py` est le **point d'entrée principal** du projet qui pilote ce pont — appelé à
trois moments : une fois pour l'orientation (`preprocessing.py`), une fois globalement sur le
document entier, une fois par petite zone une fois le type de document identifié (`zones.py`).

---

## 7. Dépannage — erreurs les plus fréquentes

**`pytesseract.pytesseract.TesseractNotFoundError: tesseract is not installed or it's not in your PATH`**
→ Le moteur système n'a pas été installé (revenir à l'étape 3), ou il est installé mais pas trouvé :
sous Windows, vérifier que le dossier d'installation est bien dans le PATH, ou que le chemin par
défaut `C:\Program Files\Tesseract-OCR\tesseract.exe` correspond bien à l'installation réelle
(sinon, l'ajuster directement dans `ocr.py`, variable `_WINDOWS_DEFAULT_PATH`).

**`pytesseract.pytesseract.TesseractError: (1, 'Error opening data file ... fra.traineddata')`**
→ Le paquet de langue française n'est pas installé (`tesseract-ocr-fra` sur Ubuntu, langue « French »
cochée à l'installation sous Windows, ou `tesseract-lang` sous macOS). Revenir à l'étape 3.

**`ModuleNotFoundError: No module named 'pytesseract'`**
→ L'environnement virtuel n'est pas activé, ou `pip install -r requirements.txt` n'a pas été exécuté
(ou a échoué). Revenir à l'étape 4.

**`streamlit: command not found`**
→ L'environnement virtuel n'est pas activé, ou les dépendances ne sont pas installées (étape 4).

**Le texte lu est vide ou incohérent sur un document par ailleurs net**
→ Vérifier d'abord l'orientation (Tesseract lit très mal un texte tourné à 90°/180° — normalement
géré automatiquement par `preprocessing.py`), puis la langue effectivement utilisée (`fra+eng`) : un
document dans une langue non installée renvoie un texte vide ou aberrant plutôt qu'une erreur claire.

**Ça fonctionne mais la lecture reste imparfaite sur une vraie photo de téléphone (floue, mal
éclairée, prise de travers, très abîmée)**
→ Ce n'est pas un problème d'installation : Tesseract, comme tout moteur OCR par règles, est plus
sensible qu'un moteur par deep learning aux photos très dégradées (angle prononcé, flou important,
faible luminosité). C'est un compromis assumé du retour à Tesseract (voir
`ocr_benchmark/RAPPORT_PaddleOCR_vs_Tesseract.md` pour le contexte de cette comparaison) — le
pipeline compense autant que possible en amont via `preprocessing.py` (redressement, correction de
perspective, réduction du bruit) et via la détection de flou (`is_blurry()`), qui alerte l'utilisateur
plutôt que de renvoyer silencieusement un résultat peu fiable.

---

## 8. Pour aller plus loin

Ce guide couvre uniquement ce qu'il faut pour que Findici tourne en local avec Tesseract. Le
`README.md` complet du projet couvre en plus : la base de données persistante en ligne
(PostgreSQL/Supabase), l'IA de vision de secours (Mistral AI), les notifications par email, les
comptes utilisateurs et le compte administrateur, le déploiement sur Streamlit Community Cloud.
