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
├── app.py              # interface Streamlit Findici (routeur à écrans + connexion + admin)
├── pdf_input.py         # conversion PDF -> image (1ère page) pour réutiliser le même pipeline
├── config.py             # types de documents, mots-clés, formats de numéros, seuils IA
├── preprocessing.py       # redressement, réduction du bruit (OpenCV)
├── ocr.py                  # lecture du texte (Tesseract)
├── classifier.py            # identification du type de document (règles)
├── extractor.py              # extraction des champs (nom, numéro, dates...)
├── zones.py                   # lecture OCR par zones (mise en page connue)
├── validator.py                 # contrôle de cohérence avant enregistrement
├── ai_vision.py                  # complément IA de vision optionnel (Mistral) — voir "IA de vision"
├── storage.py                     # SQLite ou Postgres (voir "Base de données persistante") : comptes, documents, déclarations, rapprochement
├── notifications.py                # notifications par email optionnelles — voir "Notifications par email"
├── .streamlit/
│   └── secrets.toml.example          # modèle de configuration (base de données, SMTP, IA) — à copier en secrets.toml
├── tests/
│   ├── test_pipeline.py            # tests unitaires (classification, extraction, validation)
│   ├── test_storage.py             # tests unitaires (comptes, rapprochement, listes, admin)
│   ├── test_pdf_input.py           # tests unitaires (conversion PDF -> image, pipeline sur PDF)
│   ├── test_ai_vision.py           # tests unitaires du complément IA de vision (client simulé)
│   ├── test_main_ai_fallback.py    # tests d'intégration du branchement IA dans analyze_document()
│   ├── test_notifications.py       # tests unitaires des notifications par email
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

## IA de vision (optionnel, gratuit)

Le pipeline de détection reste, par défaut, entièrement local et gratuit :
prétraitement d'image (OpenCV) + OCR (Tesseract) + règles de classification/
extraction écrites à la main (voir `classifier.py`/`extractor.py`). Aucune
IA générative n'est nécessaire pour que l'application fonctionne.

En complément facultatif, `ai_vision.py` peut solliciter un modèle de
vision (Mistral AI) pour **compléter** la lecture quand l'OCR local semble
peu fiable sur un document donné — jamais pour la remplacer. Mistral a été
choisi plutôt que Google Gemini (initialement envisagé) parce que le palier
gratuit de Google AI Studio s'est révélé inaccessible depuis le Cameroun au
moment de la mise en place (blocage constaté malgré un pays officiellement
supporté par Google — probablement une vérification de compte/IP), alors
que Mistral AI (entreprise française) n'a pas cette restriction :

- **Déclenchement ciblé** (`main.analyze_document`) : l'IA n'est appelée que
  si elle est configurée ET qu'au moins un champ n'a pas pu être lu par
  l'OCR, ou que la confiance de classification du document est faible
  (sous `AI_FALLBACK_CONFIDENCE_THRESHOLD`, 60 % par défaut — voir
  `config.py`). Sur un document déjà bien lu par Tesseract, l'IA n'est
  jamais sollicitée : ça évite de gaspiller inutilement le quota gratuit.
- **Complément, jamais d'écrasement** : l'IA ne remplit que les champs
  restés vides après l'OCR — un champ déjà lu n'est jamais remplacé
  silencieusement par sa réponse, pour rester transparent sur l'origine de
  chaque donnée. Chaque champ complété par l'IA est signalé par une alerte
  explicite ("Champ « ... » complété par l'IA de vision (Mistral) — à
  vérifier."), à vérifier manuellement comme n'importe quelle alerte du
  pipeline.
- **Auto-évaluation intégrée** : au-delà de la simple lecture, le modèle
  reçoit pour instruction de signaler lui-même les incohérences qu'il
  repère sur l'image (date d'expiration antérieure à la date de naissance,
  numéro visiblement mal formaté, texte flou ou coupé...) — ces remarques
  sont ajoutées telles quelles aux alertes du document, même sur des champs
  que l'OCR avait déjà correctement lus. C'est ce comportement de
  vérification active, au-delà d'une lecture brute one-shot, qui en fait un
  petit "agent" plutôt qu'un simple appel d'API.
- **Jamais bloquant** : si la clé n'est pas configurée, si le paquet
  `mistralai` n'est pas installé, ou si l'appel échoue pour une raison
  quelconque (réseau, quota dépassé, réponse mal formée...),
  `ai_vision.extract_fields_with_ai()` renvoie toujours `None` — l'analyse
  se termine normalement avec le seul résultat de l'OCR, sans jamais
  planter ni bloquer l'utilisateur.

### Mise en place avec Mistral AI — gratuit, sans carte bancaire

1. Va sur [console.mistral.ai](https://console.mistral.ai), crée un compte
   (email + numéro de téléphone à vérifier par SMS — **aucune carte
   bancaire requise**).
2. Dans les paramètres de facturation ("Billing" / "Plans"), active le
   palier **"Experiment"** (gratuit) si ce n'est pas déjà fait par défaut.
3. Va dans **"API Keys"** → crée une nouvelle clé → copie-la immédiatement
   (elle ne sera plus jamais réaffichée en clair).
4. Dans `.streamlit/secrets.toml` (le même fichier que pour
   `DATABASE_URL`/`SMTP_*`), ajoute :
   ```toml
   MISTRAL_API_KEY = "ta_cle_generee"
   ```
5. Une fois l'app déployée, ajoute la même clé dans les **Secrets** de
   l'app sur Streamlit Community Cloud.
6. Installe la dépendance si ce n'est pas déjà fait (déjà listée dans
   `requirements.txt`) :
   ```bash
   pip install -r requirements.txt
   ```

Sans `MISTRAL_API_KEY` configurée, l'application continue de fonctionner
exactement comme avant, uniquement avec l'OCR local — cette fonctionnalité
n'est jamais requise pour utiliser le projet.

⚠️ Le palier gratuit "Experiment" de Mistral a un **quota limité** (visible
dans ton tableau de bord une fois connecté, sur la page des limites) et les
données envoyées via ce palier peuvent être utilisées par Mistral pour
améliorer ses modèles (voir leurs conditions) — à garder en tête si des
documents contenant des données personnelles y transitent. Suffisant pour
un prototype avec peu d'utilisateurs ; au-delà, il faudrait passer à un
palier payant (toujours très bon marché, mais plus une carte bancaire à
ajouter, et sans cette clause de réutilisation des données).

## Base de données persistante (PostgreSQL)

Par défaut, l'application stocke tout dans un fichier SQLite local
(`documents.db`) — pratique pour développer, mais **ce fichier ne doit pas
être considéré comme un stockage définitif** : si l'app est un jour
déployée sur un service comme Streamlit Community Cloud, ce type
d'hébergement redémarre périodiquement le conteneur applicatif et en efface
le disque à chaque redémarrage/redéploiement — tout ce qui a été enregistré
depuis le dernier déploiement (comptes, documents, déclarations) serait
alors perdu.

**En restant en stockage local uniquement** (choix actuel du projet), pense
à sauvegarder régulièrement : l'écran **Profil** propose un bouton
"Exporter mes données (JSON)" qui télécharge une copie de tous les
documents, déclarations et comptes (hors mots de passe) — utile avant une
réinstallation, un changement de machine, ou simplement de temps en temps
par précaution. Ce n'est qu'un export de sauvegarde, pas encore de fonction
de restauration automatique.

Pour une vraie persistance, l'application sait aussi se connecter à une
base **PostgreSQL** hébergée : dès qu'une chaîne de connexion est fournie
(voir ci-dessous), `storage.py` bascule automatiquement dessus — le reste
du code (app.py, main.py) n'a besoin d'aucune modification, et rien ne
change dans son fonctionnement.

### Mise en place avec Supabase (offre gratuite)

[Supabase](https://supabase.com) propose un hébergement PostgreSQL gratuit
amplement suffisant pour ce prototype :

1. Va sur [supabase.com](https://supabase.com) → **"Start your project"**
   (ou "Sign in" si tu reviens) → connecte-toi avec GitHub, Google, ou une
   adresse email (avec vérification par email dans ce dernier cas).
2. Une fois connecté, clique **"New project"**. Renseigne :
   - **Organization** : laisse "Personal" (proposé par défaut) ;
   - **Project name** : ce que tu veux, ex. "findici" ;
   - **Database password** : génère-le automatiquement (bouton dédié) ou
     choisis le tien — **note-le tout de suite quelque part de sûr**, il ne
     sera plus jamais réaffiché en clair ensuite (ce n'est pas ton mot de
     passe de connexion à supabase.com, c'est celui de la base elle-même) ;
   - **Region** : une région proche, ex. Europe (Frankfurt/Paris/London
     selon ce qui est proposé) ;
   - **Pricing plan** : le plan **Free** est déjà sélectionné par défaut,
     ne change rien ici.
   Clique **"Create new project"** et patiente 1 à 2 minutes le temps que
   Supabase provisionne la base.
3. Une fois le projet prêt, clique le bouton **"Connect"** en haut du
   tableau de bord du projet. Un panneau s'ouvre avec plusieurs onglets de
   type de connexion — choisis **"Transaction pooler"** (pas "Direct
   connection") et copie la chaîne **URI** affichée. Elle ressemble à :
   `postgresql://postgres.xxxxxxxxxxxx:[MOT-DE-PASSE]@aws-0-xxxxx.pooler.supabase.co:6543/postgres`

   ⚠️ Prends bien le **Transaction pooler**, pas la "Direct connection" :
   depuis début 2024, Supabase a rendu ses connexions directes
   (`db.xxxx.supabase.co`) accessibles uniquement en IPv6, sauf à payer une
   option IPv4 — et Streamlit Community Cloud ne garantit pas de connexion
   sortante en IPv6. Le "Transaction pooler" (port `6543`), lui, fonctionne
   normalement en IPv4 et convient très bien à ce type d'application web.
4. Remplace `postgresql://` par `postgresql+psycopg2://` en tout début de
   chaîne (indique à SQLAlchemy quel pilote Python utiliser) et
   `[MOT-DE-PASSE]` par le mot de passe de base de données noté à l'étape 2
   (pas ton mot de passe de compte Supabase).
5. En local, copie `.streamlit/secrets.toml.example` en
   `.streamlit/secrets.toml` (même dossier) et colle-y cette chaîne comme
   valeur de `DATABASE_URL`. **Ce fichier `secrets.toml` ne doit jamais
   être commité** (il est déjà dans `.gitignore` — seul le `.example`,
   sans vraie valeur, est versionné).
6. Relance `streamlit run app.py` : l'application crée automatiquement les
   tables nécessaires (documents, déclarations, utilisateurs) sur Supabase
   au premier démarrage, et toutes les données créées ensuite y sont
   persistées.
7. Le jour où l'app est déployée sur Streamlit Community Cloud, ajoute la
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

**Un seul compte par adresse email** : `create_user` refuse la création d'un
second compte avec une adresse déjà utilisée (vérification en base avant
insertion), et la colonne `email` de la table `users` porte en plus une
contrainte `UNIQUE` côté base de données — même en cas d'accès concurrent
(deux créations quasi simultanées), la base elle-même refuserait la
deuxième insertion. Ce n'est donc pas juste un message d'erreur côté
interface : il n'est pas possible de contourner cette règle.

## Notifications par email

À chaque événement important, l'application peut envoyer un email à une
adresse de surveillance (typiquement celle de la personne qui administre le
projet) : nouveau compte créé, nouvelle déclaration de perte enregistrée,
nouveau document retrouvé enregistré (que ce soit via la détection
automatique par photo ou la saisie manuelle). Voir `notifications.py`.

Comme pour `DATABASE_URL`, cette fonctionnalité est **entièrement
optionnelle** : si elle n'est pas configurée, l'application continue de
fonctionner exactement comme avant, sans jamais rien casser — l'envoi
d'email échoue silencieusement (aucune exception ne remonte jamais jusqu'à
l'interface) et personne ne reçoit de notification, c'est tout.

### Mise en place avec Gmail

1. Sur le compte Gmail qui enverra les notifications, active la validation
   en deux étapes (**Compte Google → Sécurité → Validation en deux
   étapes**) — obligatoire pour l'étape suivante.
2. Toujours dans **Sécurité**, cherche **"Mots de passe des applications"**
   (ou va directement sur
   [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)),
   crée-en un nouveau (nom libre, ex. "Findici"). Google affiche un code de
   16 caractères une seule fois — copie-le immédiatement.
   ⚠️ **Ce n'est pas ton mot de passe Gmail habituel** : n'utilise jamais
   ton vrai mot de passe ici, ni ailleurs dans ce projet.
3. Dans `.streamlit/secrets.toml` (le même fichier que pour `DATABASE_URL` —
   copie `.streamlit/secrets.toml.example` si ce n'est pas déjà fait),
   renseigne :
   ```toml
   SMTP_HOST = "smtp.gmail.com"
   SMTP_PORT = "465"
   SMTP_USER = "ton.adresse@gmail.com"
   SMTP_PASSWORD = "le-code-a-16-caracteres-de-l-etape-2"
   NOTIFY_EMAIL = "ton.adresse@gmail.com"
   ```
   `NOTIFY_EMAIL` est l'adresse qui **reçoit** les notifications — elle peut
   être différente de `SMTP_USER` (l'adresse qui les **envoie**) si tu
   préfères recevoir les alertes ailleurs. `SMTP_FROM` (optionnel) permet de
   personnaliser l'expéditeur affiché ; par défaut il reprend `SMTP_USER`.
4. Une fois l'app déployée (Streamlit Community Cloud), ajoute les mêmes
   clés dans les **Secrets** de l'application déployée (menu de l'app →
   Settings → Secrets), en plus de `DATABASE_URL` si tu l'utilises déjà.
5. Un autre fournisseur que Gmail fonctionne aussi tant qu'il propose un
   accès SMTP (change simplement `SMTP_HOST`/`SMTP_PORT`).

Sans ces clés (ni en secret Streamlit, ni en variable d'environnement),
`notifications.is_configured()` renvoie `False` et aucune tentative d'envoi
n'est faite.

## Compte administrateur

Un compte peut être marqué administrateur (colonne `is_admin` sur la table
`users`). Un compte administrateur voit apparaître un onglet **"🛡️ Admin"**
supplémentaire dans la navigation, avec :

- des statistiques globales (nombre total de documents retrouvés, de
  déclarations, de déclarations encore en attente, de comptes créés, et une
  répartition par type de document) ;
- la liste complète de tous les documents retrouvés, toutes les
  déclarations et tous les comptes, tous utilisateurs confondus (pas
  seulement les siens, contrairement à l'écran "Mes déclarations").

Il n'y a **aucun moyen de devenir administrateur depuis l'interface** — la
promotion se fait uniquement côté base de données, via `storage.set_admin`,
pour éviter qu'un utilisateur ne se l'attribue lui-même.

**En local (base SQLite)**, depuis la racine du projet :

```bash
python3 -c "import storage; storage.set_admin('eric.donnang@dsteams.com', True)"
```

**Sur une base en ligne (Supabase/Postgres)**, une fois `DATABASE_URL`
configurée (voir "Base de données persistante" ci-dessus) et le compte déjà
créé au moins une fois via l'écran de connexion de l'application : ouvre
dans Supabase **SQL Editor** et exécute :

```sql
UPDATE users SET is_admin = 1 WHERE email = 'eric.donnang@dsteams.com';
```

(Le compte doit exister au préalable — crée-le depuis l'écran de connexion
de l'application avant d'exécuter cette commande, sinon `UPDATE` ne trouve
aucune ligne à modifier.) Pour redescendre un compte au rang d'utilisateur
normal, refais la même commande avec `is_admin = 0`, ou en local
`storage.set_admin('email', False)`.

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
  document scanné. Une notification par email est envoyée à chaque
  déclaration/document enregistré (voir "Notifications par email"
  ci-dessus), mais ce n'est pas une alerte de correspondance ciblée — le
  rapprochement lui-même n'est affiché qu'au moment où l'une des deux
  parties utilise l'interface.
- Comptes utilisateurs : voir les limites détaillées dans la section
  "Comptes utilisateurs et tableau de bord personnel" ci-dessus (pas de
  vérification d'email, pas de récupération de mot de passe...). Un compte
  peut être promu administrateur (voir "Compte administrateur"), mais
  uniquement via une commande exécutée en dehors de l'application — il n'y a
  pas encore d'écran de gestion des rôles.
- Notifications par email : simple envoi SMTP synchrone (pas de file
  d'attente, pas de nouvelle tentative en cas d'échec temporaire) vers une
  unique adresse de surveillance — suffisant pour un prototype à un seul
  administrateur, à faire évoluer (file d'attente, plusieurs destinataires)
  si le nombre d'événements ou d'administrateurs augmente.
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
- IA de vision (voir "IA de vision" ci-dessus) : fonctionnalité optionnelle,
  désactivée tant que `MISTRAL_API_KEY` n'est pas configurée. Le palier
  gratuit "Experiment" de Mistral a un quota limité (adapté à un prototype à
  faible volume, pas à un usage à grande échelle) ; elle complète l'OCR
  champ par champ mais ne relit pas le document dans son ensemble comme le
  ferait un modèle entraîné spécifiquement dessus (voir "Évolution vers un
  CNN (v2)" ci-dessous pour cette étape ultérieure).

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

Le complément IA de vision (`ai_vision.py`, voir plus haut) est une étape
intermédiaire plus rapide à mettre en place qu'un CNN entraîné sur mesure
(aucun jeu de données à collecter/labelliser), mais les deux approches sont
complémentaires à terme : un CNN reste plus rapide et moins coûteux à
grande échelle une fois entraîné, tandis que l'IA de vision generative
s'adapte instantanément à n'importe quel document sans entraînement
préalable.

## Application mobile (Ajouter à l'écran d'accueil)

Streamlit ne permet pas de publier une vraie application native sur l'App
Store ou le Google Play Store — ce serait un projet technique séparé
(réécriture ou "emballage" de l'app avec un outil comme Capacitor, compte
développeur Apple à 99 $/an, validation par Apple, maintenance de deux
plateformes en plus du web). Ce n'est pas ce que fait ce prototype.

En revanche, Findici peut être **ajouté à l'écran d'accueil** du téléphone
(iOS Safari ou Android Chrome), ce qui donne une icône dédiée et un
lancement plus rapide que de retaper l'URL à chaque fois :

- **Safari (iPhone/iPad)** : ouvrir le lien de l'app → bouton de partage
  (carré avec une flèche vers le haut) → **"Sur l'écran d'accueil"**.
- **Chrome (Android)** : ouvrir le lien → menu ⋮ → **"Ajouter à l'écran
  d'accueil"** (ou **"Installer l'application"** si Chrome le propose).

Pour que cette icône soit personnalisée (logo et nom "Findici") plutôt que
le logo Streamlit par défaut, l'app injecte un manifest PWA et des balises
d'icône iOS (`static/manifest.json`, `static/icon-*.png`,
`.streamlit/config.toml` avec `enableStaticServing = true`, et la fonction
`_inject_pwa_head_tags()` dans `app.py`).

⚠️ **Support expérimental** : ça fonctionne correctement en local (vérifié),
mais des utilisateurs de Streamlit Community Cloud ont documenté un bug non
résolu côté Streamlit où le nom/l'icône reviennent à "Streamlit" par défaut
une fois l'app ajoutée à l'écran d'accueil depuis le lien hébergé — Streamlit
lui-même indique ne pas supporter officiellement les PWA (son architecture
repose sur une connexion WebSocket permanente entre le serveur Python et le
navigateur, ce qui limite ce qu'une PWA peut faire hors-ligne). Si l'icône
personnalisée ne s'affiche pas correctement sur le lien en ligne, "Ajouter à
l'écran d'accueil" fonctionne quand même — juste avec l'icône par défaut.

## Vitesse et disponibilité (Streamlit Community Cloud)

Deux causes distinctes peuvent rendre l'app "lente", à ne pas confondre :

**1. Mise en veille de l'app en ligne.** Streamlit Community Cloud (offre
gratuite) met en veille toute application n'ayant reçu aucune visite depuis
**12 heures**. La première visite qui suit réveille l'app, ce qui peut
prendre de 30 secondes à 1-2 minutes (réinstallation des dépendances,
redémarrage du serveur) — ce n'est pas un bug du code, c'est le
fonctionnement normal de l'offre gratuite. Ça n'affecte que le lien en
ligne, jamais l'exécution en local (`streamlit run app.py` sur ton PC).

**2. Latence réseau vers la base de données en ligne.** Une fois connectée
à Supabase (voir "Base de données persistante"), chaque connexion/action
qui lit ou écrit en base fait un aller-retour réseau réel — contre un accès
quasi instantané avec l'ancien fichier SQLite local. C'est un compromis
inhérent au choix d'une base persistante hébergée, pas quelque chose que le
code peut totalement supprimer ; ça se ressent davantage depuis une
connexion internet plus lente ou plus loin géographiquement du centre de
données choisi (Europe, dans la configuration Supabase de ce projet).

Pour limiter l'effet de la mise en veille sur le lien en ligne, une option
possible (non activée par défaut) est un déclencheur programmé qui visite
périodiquement l'app pour la maintenir éveillée — voir la discussion
Streamlit sur le sujet si tu veux mettre ça en place :
https://discuss.streamlit.io/t/how-to-prevent-the-app-enter-the-sleep-mode/87959.
Une simple requête HTTP ne suffit généralement pas (l'app ne la compte pas
comme une vraie visite) — il faut une visite qui charge réellement la page.

## Déploiement (rappel du flux de travail)

```bash
git init
git add .
git commit -m "Prototype v1 : pipeline de détection de documents"
git remote add origin https://github.com/TON-USER/objets-perdus-detection.git
git push -u origin main
```
