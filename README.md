# Findici — Module de détection automatique des documents — Prototype v1

Système de gestion des objets perdus et retrouvés. Ce prototype prend une
photo de document administratif camerounais en entrée (CNI, récépissé,
passeport, acte de naissance, diplôme, permis de conduire) et produit en
sortie une donnée structurée et validée, enregistrée en base.

L'application est organisée en 5 écrans (une fois connecté·e), accessibles
depuis la barre de navigation :

- **🏠 Accueil** : fil des documents retrouvés récemment (recherche par nom
  ou type de document, consultable par tout le monde).
- **📢 Déclarer perdu** : pas de photo obligatoire (le document est perdu) —
  la personne renseigne ce qu'elle en connaît (type, nom, numéro si elle s'en
  souvient...) et ses coordonnées. Possibilité d'utiliser une **ancienne
  photo** du document pour pré-remplir automatiquement le formulaire (la
  photo n'est pas enregistrée comme document retrouvé). Voir "Rapprochement
  déclarations ⟷ documents retrouvés" plus bas.
- **🔍 Déclarer trouvé** : dépôt d'une photo -> détection + extraction
  automatique (flux décrit ci-dessous), avec une **saisie manuelle** en
  repli si la détection automatique échoue ("on ne sait jamais").
- **🗂️ Mes déclarations** : tableau de bord personnel (onglets Perdus /
  Trouvés) listant les déclarations et documents de la personne connectée.
- **👤 Profil** : informations du compte et déconnexion.

Un document affiché sur l'écran "Accueil" ou dans "Mes déclarations" peut
être ouvert en détail, avec un bouton **"Voir les coordonnées"** qui révèle
le moyen de contact de la personne qui l'a retrouvé.

## Pourquoi une approche "sans dataset" pour cette v1

Entraîner un CNN nécessite un jeu d'images labellisées que nous n'avons pas
encore. Ce prototype utilise donc une approche **hybride basée sur des
règles** (format de l'image + mots-clés OCR), qui fonctionne dès maintenant,
sans données d'entraînement :

1. **Format de l'image** (ratio largeur/hauteur) : carte (CNI/permis), page
   A4 (acte de naissance/diplôme), page de passeport.
2. **Mots-clés OCR** : chaque type de document a un vocabulaire propre
   (« carte nationale », « permis de conduire », zone MRZ pour le passeport,
   tableau de catégories A/B/C/D/E pour le permis...).

Ces critères viennent directement du document *Critères de différenciation
des documents administratifs camerounais* transmis précédemment. Quand un
jeu de photos réelles sera disponible, cette v1 pourra être complétée par un
modèle de vision entraîné (transfer learning MobileNetV2/ResNet), sans
changer l'architecture globale — voir section "Évolution vers un CNN".

## Architecture

```
document_detector/
├── main.py            # point d'entrée : analyze_document() (pipeline sans écriture) + process_document() (pipeline + enregistrement)
├── app.py              # interface Streamlit Findici (routeur à 5 écrans + connexion)
├── pdf_input.py         # conversion PDF -> image (1ère page) pour réutiliser le même pipeline
├── config.py             # types de documents, mots-clés, formats de numéros
├── preprocessing.py       # redressement, réduction du bruit (OpenCV)
├── ocr.py                  # lecture du texte (Tesseract)
├── classifier.py            # identification du type de document (règles)
├── extractor.py              # extraction des champs (nom, numéro, dates...)
├── zones.py                   # lecture OCR par zones (mise en page connue)
├── validator.py                 # contrôle de cohérence avant enregistrement
├── storage.py                    # SQLite (prototype) : comptes, documents, déclarations, rapprochement
├── tests/
│   ├── test_pipeline.py            # tests unitaires (classification, extraction, validation)
│   ├── test_storage.py             # tests unitaires (comptes, rapprochement, listes)
│   ├── test_pdf_input.py           # tests unitaires (conversion PDF -> image, pipeline sur PDF)
│   └── generate_sample_images.py   # génère des images de test (gabarits texte)
└── requirements.txt
```

## Documents envoyés en PDF

En plus d'une photo (JPG/PNG), un document peut être envoyé au format **PDF**
(scan) — sur l'écran "Déclarer trouvé" (mode détection automatique) et sur
l'écran "Déclarer perdu" (ancienne photo pour pré-remplissage). La première
page du PDF est automatiquement convertie en image (`pdf_input.py`, via
PyMuPDF) puis traverse exactement le même pipeline qu'une photo classique —
aucune différence de traitement une fois converti.

- Si le PDF contient plusieurs pages, seule la **première** est analysée
  (les documents administratifs de ce prototype tiennent sur une seule
  page) ; une alerte le signale explicitement dans le résultat.
- L'aperçu visuel (`st.image`) n'est pas disponible pour un PDF dans
  l'interface — seul le résultat de l'analyse s'affiche.
- Dépendance ajoutée : `PyMuPDF` (voir `requirements.txt`) — pas de binaire
  système à installer séparément (contrairement à `pdf2image`/`poppler`),
  ce qui simplifie le déploiement sur Streamlit Community Cloud.

## Base de données persistante (PostgreSQL)

Par défaut, l'application stocke tout dans un fichier SQLite local
(`documents.db`) — pratique pour développer, mais **ce fichier ne doit pas
être considéré comme un stockage définitif** : si l'app est un jour
déployée sur un service comme Streamlit Community Cloud, ce type
d'hébergement redémarre périodiquement le conteneur applicatif et en efface
le disque à chaque redémarrage/redéploiement — tout ce qui a été enregistré
depuis le dernier déploiement (comptes, documents, déclarations) serait
alors perdu.

Pour une vraie persistance, l'application sait aussi se connecter à une
base **PostgreSQL** hébergée : dès qu'une chaîne de connexion est fournie
(voir ci-dessous), `storage.py` bascule automatiquement dessus — le reste
du code (app.py, main.py) n'a besoin d'aucune modification, et rien ne
change dans son fonctionnement.

### Mise en place avec Supabase (offre gratuite)

[Supabase](https://supabase.com) propose un hébergement PostgreSQL gratuit
amplement suffisant pour ce prototype :

1. Crée un compte sur supabase.com et un nouveau projet (choisis une
   région proche, ex. Europe, et note le mot de passe de base de données
   que tu définis à la création — il ne sera plus jamais réaffiché en
   clair).
2. Dans le projet, va dans **Project Settings → Database → Connection
   string**, onglet **URI**. Tu obtiens une chaîne du type :
   `postgresql://postgres:[MOT-DE-PASSE]@db.xxxxxxxxxxxx.supabase.co:5432/postgres`
3. Remplace `postgresql://` par `postgresql+psycopg2://` en tout début de
   chaîne (indique à SQLAlchemy quel pilote Python utiliser) et
   `[MOT-DE-PASSE]` par ton vrai mot de passe.
4. En local, copie `.streamlit/secrets.toml.example` en
   `.streamlit/secrets.toml` (même dossier) et colle-y cette chaîne comme
   valeur de `DATABASE_URL`. **Ce fichier `secrets.toml` ne doit jamais
   être commité** (il est déjà dans `.gitignore` — seul le `.example`,
   sans vraie valeur, est versionné).
5. Relance `streamlit run app.py` : l'application crée automatiquement les
   tables nécessaires (documents, déclarations, utilisateurs) sur Supabase
   au premier démarrage, et toutes les données créées ensuite y sont
   persistées.
6. Le jour où l'app est déployée sur Streamlit Community Cloud, ajoute la
   même clé `DATABASE_URL` dans les **Secrets** de l'application (menu de
   l'app déployée → Settings → Secrets) — même format TOML que le fichier
   local.

Sans `DATABASE_URL` configurée (ni en secret Streamlit, ni en variable
d'environnement), l'application continue de fonctionner exactement comme
avant, sur SQLite local — aucune configuration n'est obligatoire pour
simplement essayer le projet.

### Migration des données existantes

Comme il s'agissait jusqu'ici de données de test, il n'y a pas de script de
migration automatique de l'ancien `documents.db` local vers Postgres — la
base Postgres démarre vide. Si tu as des données locales précises à
reprendre, demande-le explicitement : c'est un script ponctuel simple à
écrire (lire les lignes SQLite, les réinsérer via `storage.save_document`/
`save_declaration`/`create_user`).

## Comptes utilisateurs et tableau de bord personnel

L'accès à l'application nécessite un compte (création directe depuis l'écran
de connexion : nom, email, téléphone, mot de passe). Le compte sert à :

- pré-remplir vos coordonnées dans les formulaires de déclaration ;
- associer les documents retrouvés et les déclarations de perte à votre
  compte, pour les retrouver dans **"Mes déclarations"** ;
- afficher un moyen de contact ("Voir les coordonnées") aux personnes qui
  retrouvent leur document dans le fil "Accueil".

⚠️ **Authentification de prototype** : les mots de passe sont hachés
(PBKDF2-HMAC-SHA256 salé, `storage._hash_password`) mais il n'y a **aucune
vérification d'email**, aucune limitation du nombre de tentatives de
connexion, aucune politique de robustesse du mot de passe au-delà d'une
longueur minimale (6 caractères), et aucune récupération de mot de passe
oublié. À remplacer par un vrai système d'authentification (bcrypt/argon2,
confirmation par email, limitation de débit...) avant tout usage en
production.

## Déclaration de perte et rapprochement automatique

Une personne qui a perdu un document n'a pas de photo à déposer. L'onglet
"📢 J'ai perdu un document" lui permet donc de renseigner directement ce
qu'elle sait (type de document, nom, numéro si connu — champs définis dans
`config.DECLARATION_FIELDS`), les circonstances de la perte, et ses
coordonnées (téléphone et/ou email, au moins un des deux obligatoire).

Chaque déclaration est enregistrée dans une table SQLite dédiée
(`declarations`, voir `storage.init_declarations_table`), séparée de la table
`documents` qui contient les documents effectivement retrouvés et scannés.

Le rapprochement (`storage._fields_match`) compare deux jeux de champs :
priorité à une correspondance exacte sur un champ numéro (`numero`,
`numero_recepisse` ou `numero_matricule`, sensible/fiable) ; à défaut, repli
sur le nom (comparaison insensible à la casse et aux espaces, moins fiable
en cas d'homonymie mais utile quand aucun numéro n'est connu). Il s'applique
dans les deux sens :

- **`find_matching_documents`** : au moment de la déclaration, si un document
  correspondant a déjà été retrouvé, la personne le voit immédiatement.
- **`find_matching_declarations`** : au moment où un document est scanné
  (onglet "retrouvé"), si une déclaration de perte en attente correspond, ses
  coordonnées de contact s'affichent aussitôt à la personne qui a retrouvé le
  document.

C'est un rapprochement de prototype (comparaison exacte champ par champ, pas
de tolérance aux fautes de frappe/OCR ni de score de similarité) — à faire
évoluer si le volume de déclarations grandit (ex. distance de Levenshtein sur
le nom, recherche floue sur le numéro).

## Installation sur le serveur Ubuntu

```bash
# Dépendances système (OCR)
sudo apt update
sudo apt install -y tesseract-ocr tesseract-ocr-fra

# Dépendances Python
cd document_detector
pip install -r requirements.txt
```

## Utilisation

```bash
python3 main.py chemin/vers/photo.jpg
```

Exemple de sortie :

```
Ceci est : Carte Nationale d'Identité (confiance : 64%)
  nom : NOM EXEMPLE
  numero : 12345678901234567
  date_naissance : 01/01/2000
  date_expiration : 01/01/2030
Informations enregistrées avec succès.
(id base de données : 1)

--- JSON structuré ---
{
  "type_document": "CNI",
  "nom": "NOM EXEMPLE",
  "numero": "12345678901234567",
  "date_naissance": "01/01/2000",
  "date_expiration": "01/01/2030"
}
```

Les documents enregistrés sont stockés dans `documents.db` (SQLite), table
`documents`, avec les champs extraits en JSON et les éventuelles alertes de
validation. Les déclarations de perte (onglet "perdu") sont dans la table
`declarations` de la même base — voir section précédente.

## Tests

```bash
# Tests unitaires (classification, extraction, validation, rapprochement
# déclarations <-> documents, comptes utilisateurs, listes personnelles —
# pas besoin d'image)
python3 -m pytest tests/ -v

# Génère des images de test (gabarits texte) puis teste le pipeline complet
python3 tests/generate_sample_images.py
python3 main.py tests/sample_images/cni_sample.png
python3 main.py tests/sample_images/permis_sample.png
python3 main.py tests/sample_images/passeport_sample.png
python3 main.py tests/sample_images/acte_naissance_sample.png
```

Ces 4 cas ont été validés lors du développement : classification correcte
à chaque fois (CNI, permis, passeport via MRZ, acte de naissance), extraction
des numéros/dates conforme, et le cas le plus ambigu (CNI vs permis, même
format de carte) est bien désambiguïsé grâce au tableau de catégories et aux
mots-clés OCR.

**Important :** `generate_sample_images.py` produit des gabarits texte, pas
des photos réalistes de documents — ils suffisent pour vérifier que le
pipeline fonctionne de bout en bout, mais **ne remplacent pas des tests sur
de vraies photos**, à faire dès que possible.

## Limites connues de cette v1

- L'extraction du nom (`_guess_name` dans `extractor.py`) est une heuristique
  simple (première ligne en majuscules qui n'est pas un en-tête administratif
  connu). Elle sera fragile sur des photos réelles bruitées — à renforcer
  avec la détection de zones (voir ci-dessous).
- Pas de détection de zones de texte : l'OCR lit toute l'image. Une detection
  de zones par gabarit (ou modèle dédié) améliorerait nettement la précision,
  surtout pour les diplômes (mise en page très variable).
- Les formats de numéro de passeport, d'acte de naissance et de permis ne
  sont pas strictement validés (pas de format national publiquement
  documenté) — validation actuellement limitée à la présence des champs.
- Le stockage SQLite (backend par défaut, sans configuration) reste un
  stockage de développement, non persistant en cas de déploiement sur un
  hébergement à disque éphémère — voir "Base de données persistante
  (PostgreSQL)" plus haut pour brancher une vraie base hébergée.
- Le rapprochement déclaration ⟷ document retrouvé est une comparaison
  exacte (numéro identique, ou nom identique aux espaces/casse près) : pas de
  tolérance aux fautes de frappe côté déclarant ni aux erreurs d'OCR côté
  document scanné. Pas encore de notification automatique (email/SMS) quand
  une correspondance apparaît après coup — pour l'instant, le rapprochement
  n'est affiché qu'au moment où l'une des deux parties utilise l'interface.
- Comptes utilisateurs : voir les limites détaillées dans la section
  "Comptes utilisateurs et tableau de bord personnel" ci-dessus (pas de
  vérification d'email, pas de récupération de mot de passe...).
- Le fil "Accueil" et le bouton "Voir les coordonnées" exposent le contact
  (téléphone) de la personne qui a retrouvé le document à **toute personne
  connectée**, sans vérification préalable qu'elle est bien la propriétaire
  légitime — acceptable pour un prototype, à encadrer (ex. vérification
  d'identité, messagerie interne anonymisée) avant un déploiement réel.
- La saisie manuelle sur l'écran "Déclarer trouvé" (repli si la détection
  automatique échoue) enregistre les documents avec `confidence = 1.0` et
  une alerte explicite ("Saisie manuelle") plutôt qu'un score OCR réel — à
  ne pas confondre avec une confiance de détection automatique lors de
  l'analyse des données.

## Évolution vers un CNN (v2)

Dès qu'un jeu de photos réelles labellisées est disponible (quelques
dizaines par type de document suffisent pour démarrer avec du transfer
learning) :

1. Entraîner un classifieur d'images (MobileNetV2/ResNet, fine-tuné) en
   remplacement/complément de `classifier.py`.
2. Conserver le signal OCR (mots-clés, MRZ, tableau de catégories) en
   renfort pour les cas ambigus (CNI vs permis).
3. Le reste du pipeline (`extractor.py`, `validator.py`, `storage.py`)
   reste inchangé.

## Déploiement (rappel du flux de travail)

```bash
git init
git add .
git commit -m "Prototype v1 : pipeline de détection de documents"
git remote add origin https://github.com/TON-USER/objets-perdus-detection.git
git push -u origin main
```
