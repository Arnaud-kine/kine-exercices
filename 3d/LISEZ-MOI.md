# Personnage 3D (rendus d'illustration des exercices)

- `base_makehuman_CC0.obj` : corps de base du projet MakeHuman, publié en **CC0** (domaine public) en septembre 2020 : aucune restriction, aucune mention obligatoire.
- `mannequin_anatomique_build.py` : script Blender (4.0) qui importe ce corps, retire les éléments d'aide, ajoute un haut et un short (coupes nettes), l'éclairage, la caméra, et produit un rendu.
  Commande : `blender -b -P mannequin_anatomique_build.py -- <échantillons> <largeur> <sortie.png> <vue: tq|face|profil>`
- `mannequin_anatomique.blend` : le fichier Blender obtenu.
- `mannequin_build.py` / `mannequin.blend` : première version (mannequin simplifié), abandonnée.

## Les quatre personnages (femme/homme, adulte/senior)
- `fabriquer_personnage.py` : applique à `base_makehuman_CC0.obj` les réglages de morphologie de MakeHuman (sexe, âge, carrure), qui sont aussi en CC0. Ils se récupèrent par :
  `git clone --depth 1 --filter=blob:none --sparse https://github.com/makehumancommunity/makehuman.git mhrepo` puis `git sparse-checkout set makehuman/data/targets/macrodetails`
  (106 Mo, non copiés ici). Âges retenus : adulte 40 ans, senior 80 ans (poids légèrement supérieur).
- `mannequin_anatomique_build.py` : arguments `-- <échantillons> <largeur> <sortie.png> <vue> <fichier.obj> <couleur du haut> <F|M> <adulte|senior>`.
  Les vêtements sont colorés par zone selon la position de repos des points (bords nets, stables quand le corps bouge). Cheveux, sourcils et yeux sont fabriqués par le script (les coiffures de MakeHuman ne sont pas téléchargeables depuis l'espace de travail).

## Animation (squelette, poses, vidéo)
- `rig_lib.py` : reconstruit le personnage à partir du fichier .obj, le dote du squelette standard de MakeHuman (163 os) et de ses poids de peau (fichiers `default.mhskel` et `default_weights.mhw`, CC0, dossier `makehuman/data/rigs` du même dépôt).
- `pose_lib.py` : outils de pose (orienter un os, calcul de coude/genou à deux os).
- `exercice_bird_dog.py` : premier exercice, pose calculée à partir des longueurs réelles de bras et de jambes. Arguments : `-- <obj> <dossier> <échantillons> <largeur> <hauteur> <u1,u2,...> <F|M> <adulte|senior> <couleur du haut> <profil|tq>` (u = avancement du mouvement de 0 à 1 ; variable START pour reprendre la numérotation).
- `assembler_video.py` : assemble les images en vidéo avec légendes (départ, tendre, tenir, revenir), 3 répétitions.
- Contraintes mesurées (1 processeur, pas de réduction du grain) : environ 25 s par image en 640x480 avec 48 échantillons ; un rendu en arrière-plan s'arrête à la fin de l'étape en cours, il faut donc rendre par lots de moins de 4 minutes.
