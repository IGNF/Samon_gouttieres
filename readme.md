

# Retrouver les contours des toits des bâtiments en 3D

Ce répertoire permet de :
* reconstruire en 3D les contours de toit (script SamonGouttiere.py)
* recaler les bâtiments de la BD Uni sur les contours de toit trouvés précédemment (script run_recalage.py) => non maintenu


![Alt text](Mont_Dauphin.png "Mont Dauphin")


## Mise en place d'un chantier

Dans un répertoire chantier doit se trouver :
* Un répertoire "gouttieres" contenant un répertoire "predictions_FFL" avec les prédictions du Frame Field Learning sous format shapefile
* Un répertoire "mnt" contenant un fichier vrt
* Un répertoire "orientation" contenant le TA sous format xml. Il se trouve généralement dans store-ref/ortho-images/ImagesOrientees/FD[departement]/annee/[...]_AERO/AERO/[...]/*_adjust.XML
* Un répertoire "raf" contenant la grille RAF

Eventuellement, il peut s'y trouver :
* un fichier shapefile (ou geojson) de l'emprise du chantier qui nous intéresse.
* un fichier contenant les bâtiments de la BD Uni à recaler.
* un répertoire contenant le lidar de la zone pour contrôler les résultats


## Chantiers disponibles

Plusieurs chantiers sont disponibles dans store-echange/CelestinHuet/Samon_gouttieres/Chantiers

### 05_2022

Forteresse de Mont-Dauphin. Ce chantier ne fonctionne qu'avec la commande run.py car la BD Uni n'est pas présente dans ce chantier (donc pas de recalage possible)

Exemple de commande : 
```
python SamonGouttiere.py --input chantiers/05_2022/
```


### 49_2022

Martigné-Briand. Ce chantier ne fonctionne qu'avec la commande run.py car la BD Uni n'est pas présente dans ce chantier (donc pas de recalage possible)

Exemple de commande : 
```
python SamonGouttiere.py --input chantiers/49_2022/
```


### 02_2021

Craonne. Ce chantier ne fonctionne qu'avec la commande run.py car la BD Uni n'est pas présente dans ce chantier (donc pas de recalage possible)

Exemple de commande : 
```
python SamonGouttiere.py --input chantiers/02_2021/
```


### sv3d

20 zones dans l'Aisne, les Côtes d'Armor, le Bas-Rhin et les Yvelines






## Installation

Création de l'environnement conda : 
```
mamba env create -f environment.yaml
conda activate samon
```

Ou bien 
```
conda env create -f environment.yaml
conda activate samon
```



## Les fichiers résultats

Dans plusieurs répertoires, on trouve deux types de fichiers shapefile : avec ou sans le suffixe "_proj". Ceux sans le suffixe sont dans la géométrie image, ceux avec le suffixe sont projetés sur le MNT et permet de superposer les shapefiles issus d'images différentes. 

Dans chantiers/gouttieres :
* nettoye : prédictions du FFL où chaque segment correspond à un mur (sans points intermédiaires dans la géométrie)
* association_batiment : un bâtiment possède le même identifiant dans les différents fichiers shapefile
* association_segments : un bord de toit possède le même identifiant dans les différents fichiers shapefile
* intersections : position 3D des bords de toit.
* batiments_fermes : on ferme les bâtiments à partir des bords de toit trouvés à l'étape précédente. intersections.gpkg contient les bords de toit ajustés lorsqu'ils intersectent d'autres bords de toit. batiments_fermes.gpkg contient les batiments fermés (après regroupement des bords de toit)




## Détail de certains fichiers

### gouttieres/intersections/intersections.gpkg


Dans le fichier geopackage, on trouve :
* d_mean : la distance moyenne entre le bord de toit calculé et les plans qui ont été utilisés pour le calcul
* nb_segments : le nombre de plans utilisés pour calculer le bord de toit


# Description de la chaîne de traitement 

## Inférences de FFL

ssh CHuet-Admin@SMLPSLURMMFT1
cd /mnt/common/hdd/home/CHuet-Admin/FFL
sbatch /mnt/stores/store-DAI/pocs/saisie_monoscopique/chantiers_tests/run.sh


## nettoyage

A l'issue du Frame Field Learning, il y a quelques petites imperfections dans la géométrie au regard de la suite de l'algorithme :
* un côté de bâtiment peut être divisé en plusieurs segments
* des bâtiments sont côte à côte

Avant de lancer ce script, il faut appliquer l'outil Vecteur/Outils de geotraitement/Regrouper de QGis avec l'option "garder les entités disjointes séparées" sur les résultats du Frame Field Learning. Cela permet de regrouper en un seul bâtiment les bâtiments adjacents.

Ce script prend chaque polygone et fusionne les segments du polygone dans le cas où ils se suivent et que le produit scalaire est suypérieur à un seuil.


## association_bati

Pour chaque pva, on dispose des polygones nettoyés. Il faut ensuite faire correspondre les polygones entre les pvas.

Pour cela, on projette sur le MNT chaque polygone. Pour chaque polygone, on regarde la surface de l'intersection entre ce polygone et les polygones des autres pvas. On associe le polygone avec celui avec lequel il partage la plus grande surface. Cette opération se fait dans les deux sens et pour chaque couple de pvas. Cela crée un graphe où un noeud représente un bâtiment et une arête représente une association. On cherche les composantes connexes et on attribue le même identifiant à tous les bâtiments d'un même groupe connexe.

Pour chaque bâtiment d'un même groupe connexe, on essaye d'évaluer la hauteur du bâtiment. La projection au sol des bâtiments est alors mise à jour sur MNT+hauteur estimée. Dans un monde parfait, les bâtiments d'un même groupe se superposeraient parfaitement, ce qui facilite l'association de segments (plus facile d'associer les segments s'ils sont séparés d'1 mètre au lieu de 5 mètres).

L'évaluation de la hauteur des bâtiments est calculée à partir des formes géométriques des différentes emprises des bâtiments sur les pvas. Si cette méthode rapide ne fonctionne pas, alors on utilise Samon en calculant la hauteur d'un point proche d'un bord de toit.

Les bâtiments sont sauvegardés en format geopackage en coordonnées terrain dans association_batiment.

## association_segments

Dans les geopackages, tous les bâtiments possédant le même identifiant représentent le même bâtiment dans la réalité. Il faut maintenant associer les segments des bâtiments.

Pour chaque bâtiment réel, on dispose d'un certain nombre de bâtiments de pvas. On prend deux bâtiments de pvas. On fait un premier appariement des segments avec trois conditions en projection terrain 2D : 
* produit scalaire supérieur à un certain seuil
* distance des barycentres inférieures à la moitié de la longueur d'un segment
* distance d'un barycentre à l'autre segment inférieure à un certain seuil (5 mètres)

On conserve les appariements non ambigus, c'est-à-dire qui n'implique qu'exactement deux segments. Sur ces appariements non ambigus, on calcule une translation (dx, dy) qui doit permettre de superposer "parfaitement" les deux emprises au sol.

Puis on refait une deuxième association en appliquant la translation et où la distance d'un barycentre à l'autre segment doit être inférieure à un seuil très restreint (1 mètre). 

Passer par cette étape de calcul de translation permet notamment de supprimer les défauts en "dents de scie" sur les prédictions de frame field learning et d'éviter que les segments d'une façade ne soient associés à ceux de l'autre façade.

Puis, avec le même système de graphe connexe, on associe un même identifiant à tous les segments représentant un même bord de toit.

Les segments sont sauvegardés en format geopackage en coordonnées terrain dans association_segments.


## intersection_plan

On récupère tous les segments ayant le même identifiant. Pour chaque segment, on construit le plan passant par le sommet de prise de vue et le segment. On fait une intersection de plans par moindres carrés. Puis on détermine les extrémités de la droite. On fait cela sur tous les segments.

Les résultats sont sauvegardés sous format geopackage dans intersections


## fermeture des bâtiments

Pour chaque segment, on calcule l'intersection avec ses segments voisins et on modifie la géométrie en conséquence. Puis à partir de tous les segments d'un même groupe de bâtiments, on récupère un polygone en 3 dimensions.

La fermeture peut ne pas fonctionner, souvent parce qu'il manque un segment qui n'a pas été correctement calculé. Dans ce cas, on récupère la pva sur laquelle le bâtiment est le plus proche du nadir. Sur cette pva, on récupère l'emprise du bâtiment. Pour chaque segment de cette emprise, on le projette sur le MNT+une estimation de la hauteur du bords de toit. cette hauteur est obtenu à partir des calculs d'intersections de plans.

Les résultats sont sauvegardés sous format geopackage dans batiments_fermes.












# Recalage de la BD Uni

Cette partie n'est plus maintenue. Elle permettait de recaler des bâtiments de la BD Uni sur les positions des segments 3D retrouvés

Appliquer d'abord le dissolve sur la BD Uni.

## ajuster_intersection.py

On ne tient pas compte ici des bâtiments fermés. On reprend le résultat d'intersection des plans.
Pour deux gouttières voisines, on calcule les intersections et on modifie les gouttières pour qu'elles s'arrêtent aux intersections.

## association_bati_BD_UNI.py

On associe ensemble les bâtiments de la BD Uni et le plus petit polygone convexe qui réunit les segments d'un même bâtiment

## association_segments_BD_UNI.py

On associe ensemble les segments de la BD Uni avec les intersections de plans ajustés

## recalage.py

On calcule pour chaque bâtiment les paramètres d'Helmert pour déplacer les bâtiments de la BD Uni

## appliquer_recalage.py

On déplace les bâtiments de la BD Uni

### Marseille

Quatre zones de Marseille. Il était possible de l'utiliser pour le recalage (non maintenu). Le répertoire BD_Uni_verite_terrain contient la BD Uni parfaitement recalée (saisie dans le cadre d'un autre projet il y a quelques années), mais sans la contrainte d'appliquer une rotation, une translation et un facteur d'échelle.

Les zones sont : 
* zone 1 : espace périurbain.
* zone 2 : zone industrielle
* zone 3 et zone 4 : centre-ville de Marseille. Ces deux zones fonctionnent très mal avec cet algorithme.

Exemple de commande : 
```
python run_recalage.py --chantier chantiers/Marseille_zone_1/ --bduni chantiers/Marseille_zone_1/BDUNI/ --emprise chantiers/Marseille_zone_1/zone_periurbaine_1.geojson 
```


Dans le cas de run_recalage.py, on trouve en plus :
* BD_Uni_regroupee : BD Uni après avoir regroupé en une seule géométrie les géométries jointives
* intersections_ajustees : lorsque deux segments voisins s'intersectent, on modifie leurs extrémités de façon à ce qu'elles correspondent à l'intersection
* association_bati_BD_Uni : chaque bâtiment possède le même identifiant entre ce qui vient de la BD Uni et ce qui vient du calcul des gouttières
* association_segments_BD_Uni : chaque bord de toit possède le même identifiant entre ce qui vient de la BD Uni et ce qui vient du calcul des gouttières
* recalage : résultat des paramètres à appliquer (rotation, translation, facteur d'échelle) sur la BD Uni
* BD_Uni_recalee : BD Uni recalée


### recalage

* TX, TY, a, b : les paramètres de la transformation à l'issue du calcul
* nb_points : nombre de points utilisés pour calculer la transformation
* mean : écart moyen entre les points issus des bords de toits et après application de la transformation sur la BD Uni
* res_max : écart maximal entre les points issus des bords de toits et après application de la transformation sur la BD Uni