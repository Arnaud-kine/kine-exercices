# Personnage 3D (rendus d'illustration des exercices)

- `base_makehuman_CC0.obj` : corps de base du projet MakeHuman, publié en **CC0** (domaine public) en septembre 2020 : aucune restriction, aucune mention obligatoire.
- `mannequin_anatomique_build.py` : script Blender (4.0) qui importe ce corps, retire les éléments d'aide, ajoute un haut et un short (coupes nettes), l'éclairage, la caméra, et produit un rendu.
  Commande : `blender -b -P mannequin_anatomique_build.py -- <échantillons> <largeur> <sortie.png> <vue: tq|face|profil>`
- `mannequin_anatomique.blend` : le fichier Blender obtenu.
- `mannequin_build.py` / `mannequin.blend` : première version (mannequin simplifié), abandonnée.
