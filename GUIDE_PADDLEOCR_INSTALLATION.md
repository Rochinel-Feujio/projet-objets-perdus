# Findici — PaddleOCR : rôle dans le projet et guide d'installation complet

Ce document a un seul but : permettre à quelqu'un qui n'a **jamais touché au projet** d'installer
Findici de zéro, sur son ordinateur, et d'arriver à un résultat qui fonctionne réellement — en
comprenant au passage ce que fait PaddleOCR, le moteur qui lit le texte sur les photos.

> Ce guide remplace `GUIDE_TESSERACT_INSTALLATION.md` : Findici utilisait auparavant Tesseract,
> remplacé depuis par PaddleOCR (moteur par deep learning, nettement plus robuste sur des photos
> réelles imparfaites — angle, flou, faible luminosité — voir
> `ocr_benchmark/RAPPORT_PaddleOCR_vs_Tesseract.md` pour les chiffres qui ont motivé ce choix).

Suivre les étapes dans l'ordre, du début à la fin.

---

## 1. PaddleOCR, en une minute

Findici prend une photo (ou un PDF scanné) d'un document administratif — CNI, passeport, permis de
conduire, acte de naissance — et doit :

1. **Deviner de quel document il s'agit** (classification) ;
2. **Lire le texte écrit dessus** (nom, numéro, dates...) ;
3. **Enregistrer ces informations** dans une base de données.

L'étape 2 est celle qui a besoin de PaddleOCR. **PaddleOCR** est une bibliothèque Python open
source (développée par Baidu) qui utilise des réseaux de neurones entraînés pour transformer une
image contenant du texte en texte réellement exploitable (une chaîne de caractères) — un peu comme
Tesseract, mais avec une bien meilleure tolérance aux photos imparfaites, puisqu'elle a appris sur
des millions d'images réelles plutôt que d'appliquer des règles fixes.

Deux choses importantes à savoir avant d'installer quoi que ce soit :

- Contrairement à Tesseract, PaddleOCR **est une bibliothèque Python comme les autres** : pas de
  programme séparé à installer sur la machine, pas de PATH à configurer. `pip install` suffit.
- **Une connexion Internet est nécessaire au tout premier lancement** (et seulement à ce
  moment-là) : PaddleOCR télécharge alors ses modèles de reconnaissance (quelques dizaines de Mo)
  depuis l'un de ses serveurs (HuggingFace, ModelScope, AIStudio ou BOS). Ils sont ensuite mis en
  cache localement sur la machine — les lancements suivants n'ont plus besoin d'Internet pour
  l'OCR lui-même.
- Contrairement à Tesseract qui pouvait lire deux langues en même temps (`fra+eng`), PaddleOCR
  utilise un seul code de langue par appel. Findici utilise `"fr"`, qui charge un modèle pour
  l'alphabet latin élargi (accents français inclus) reconnaissant les caractères un par un plutôt
  que des mots d'un dictionnaire figé — les mots anglais mélangés aux documents camerounais
  bilingues (ex. « NOM/SURNAME ») restent donc lisibles aussi.

---

## 2. Prérequis

Avant de commencer, il faut avoir sur l'ordinateur :

- **Python 3.10 ou plus récent** — vérifier avec `python3 --version` (ou `python --version` sur
  Windows). Si absent : [python.org/downloads](https://www.python.org/downloads/).
- Un accès à un terminal (Invite de commandes / PowerShell sous Windows, Terminal sous Mac/Linux).
- Une connexion Internet active **au moins pour le tout premier lancement** de l'application (voir
  section 1).
- Le code du projet Findici (récupéré via `git clone`, ou un dossier ZIP téléchargé et décompressé).

Aucun logiciel système à installer séparément (pas d'équivalent à l'ancien `tesseract-ocr`) : tout
passe par `pip install -r requirements.txt`, à l'étape suivante.

---

## 3. Étape 1 — Récupérer le projet et installer les dépendances Python

```bash
# Si le projet n'est pas encore sur la machine :
git clone https://github.com/Rochinel-Feujio/projet-objets-perdus.git
cd projet-objets-perdus

# Créer un environnement virtuel (recommandé, évite les conflits avec d'autres projets Python)
python3 -m venv venv

# L'activer :
source venv/bin/activate        # macOS / Linux
venv\Scripts\activate           # Windows (PowerShell ou Invite de commandes)

# Installer toutes les dépendances Python du projet (dont paddlepaddle et paddleocr)
pip install -r requirements.txt
```

Cette dernière commande installe notamment `paddlepaddle` (le moteur de calcul), `paddleocr` (la
bibliothèque d'OCR elle-même), `opencv-python-headless`, `Pillow`, `streamlit` et les autres
bibliothèques listées dans `requirements.txt` — tout ce dont le code Python a besoin.

`paddlepaddle` et `paddleocr` sont des paquets volumineux : cette installation peut prendre
plusieurs minutes selon la connexion.

---

## 4. Étape 2 — Lancer l'application (et laisser PaddleOCR télécharger ses modèles)

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

**Lors de la toute première analyse d'un document** (photo ou PDF envoyé sur l'écran « Déclarer
trouvé »), un temps d'attente supplémentaire de quelques secondes à quelques dizaines de secondes
est normal : c'est le moment où PaddleOCR télécharge ses modèles. Les analyses suivantes seront
nettement plus rapides, les modèles étant alors déjà en cache sur la machine.

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
PaddleOCR, Python et le pipeline complet de Findici fonctionnent ensemble correctement.

---

## 5. Où PaddleOCR intervient exactement dans le code

Pour comprendre ou modifier le projet plus tard :

| Fichier | Rôle vis-à-vis de PaddleOCR |
|---|---|
| `ocr.py` | Contient toute la logique d'appel à PaddleOCR (fonction `extract_text`, et `get_engine()` qui crée puis met en cache l'objet `PaddleOCR` — sa création est coûteuse, il ne faut pas la refaire à chaque appel). C'est le seul fichier qui importe `paddleocr` directement. |
| `ocr.py` (`DEFAULT_LANG`) | Fixe la langue de lecture à `"fr"` (voir section 1 pour l'explication du choix, différent du `"fra+eng"` de Tesseract). |
| `main.py` (étape 3 du pipeline) | Appelle `extract_text()` une première fois sur l'image entière, juste après le nettoyage/redressement de la photo (`preprocessing.py`) et avant la classification du type de document. |
| `zones.py` | Une fois le type de document connu, rappelle `extract_text()` séparément sur chaque zone découpée (nom, numéro, dates...). Le paramètre `psm` hérité de Tesseract est conservé dans la signature pour ne rien casser, mais n'a plus d'effet : PaddleOCR détecte lui-même les lignes de texte quelle que soit la mise en page. |
| `preprocessing.py` (`_orientation_score`) | Réutilise le même moteur PaddleOCR (via `get_engine()`, partagé avec `ocr.py`) pour détecter si une photo a été prise « de travers » (90°/180°/270°) avant le reste du traitement, en comptant les mots reconnus dans chaque orientation candidate. |
| `requirements.txt` | Liste `paddlepaddle` et `paddleocr` (remplace l'ancien `pytesseract`). |
| `packages.txt` | Vide : contrairement à Tesseract, PaddleOCR ne nécessite aucun paquet système à installer sur Streamlit Community Cloud. |

En résumé : PaddleOCR est une **bibliothèque Python**, `ocr.py` est le **point d'entrée principal**
qui la pilote (et la partage avec `preprocessing.py` via un cache), et elle est appelée à trois
moments — une fois pour l'orientation, une fois globalement, une fois par petite zone une fois le
type de document identifié.

---

## 6. Dépannage — erreurs les plus fréquentes

**`Exception: No available model hosting platforms detected. Please check your network connection.`**
→ PaddleOCR n'a pas pu télécharger ses modèles lors du premier lancement : la machine n'a pas accès
à Internet, ou un pare-feu/proxy bloque les serveurs de modèles (HuggingFace, ModelScope, AIStudio,
BOS). Vérifier la connexion Internet, ou — sur un réseau d'entreprise filtré — vérifier qu'au moins
un de ces quatre domaines est joignable.

**`ModuleNotFoundError: No module named 'paddleocr'` (ou `paddlepaddle`, ou un autre module)**
→ L'environnement virtuel n'est pas activé, ou `pip install -r requirements.txt` n'a pas été
exécuté (ou a échoué). Revenir à l'étape 3.

**`ValueError: No models are available for lang='...'`**
→ Un code de langue invalide a été utilisé. Findici utilise `"fr"` par défaut (voir section 1) ;
si ce code a été modifié dans `ocr.py`, vérifier qu'il s'agit bien d'un code de langue individuel
supporté par PaddleOCR (pas d'un nom de regroupement interne comme `"latin"`).

**`streamlit: command not found`**
→ L'environnement virtuel n'est pas activé, ou les dépendances ne sont pas installées (étape 3).

**Le tout premier document analysé met beaucoup plus de temps que les suivants**
→ Comportement normal (voir section 4) : c'est le téléchargement des modèles PaddleOCR, qui ne se
produit qu'une seule fois par langue utilisée.

**Ça fonctionne mais la lecture reste imparfaite sur une vraie photo de téléphone (floue, mal
éclairée, très abîmée)**
→ Ce n'est pas un problème d'installation : aucun moteur OCR n'est infaillible sur des photos très
dégradées. PaddleOCR reste toutefois nettement plus robuste que Tesseract sur ce type de photos —
voir le rapport `ocr_benchmark/RAPPORT_PaddleOCR_vs_Tesseract.md` du projet pour les chiffres.

---

## 7. Pour aller plus loin

Ce guide couvre uniquement ce qu'il faut pour que Findici tourne en local avec PaddleOCR. Le
`README.md` complet du projet couvre en plus : la base de données persistante en ligne
(PostgreSQL/Supabase), l'IA de vision de secours (Mistral AI), les notifications par email, les
comptes utilisateurs et le compte administrateur, le déploiement sur Streamlit Community Cloud.
