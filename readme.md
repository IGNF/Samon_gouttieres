

# Retrouver les contours des toits des bâtiments en 3D


## Mise en place d'un chantier

Dans un répertoire chantier doit se trouver :
* Un répertoire "Gouttieres" contenant un répertoire "predictions_FFL" avec les prédictions du Frame Field Learning sous format shapefile
* Un répertoire "mnt" contenant un fichier vrt
* Un répertoire "orientation" contenant le TA sous format xml. Il se trouve généralement dans store-ref/ortho-images/ImagesOrientees/FD[departement]/annee/[...]_AERO/AERO/[...]/*_adjust.XML
* Un répertoire "raf" contenant la grille RAF

Eventuellement, il peut s'y trouver :
* un fichier shapefile de l'emprise du chantier qui nous intéresse.
* un fichier contenant les bâtiments de la BD Uni à recaler.


## Installation

Création de l'environnement conda : 
```
mamba env create -f environment.yaml
```




## Lignes de commandes

Pour trouver les contours de bâtiments :
```
sh run.sh chemin/chantier
```

Pour trouver les contours de bâtiments dans une zone délimitée par une emprise :
```
sh run.sh chemin/chantier chemin/emprise
```


Pour recaler les bâtiments de la BD Uni :
```
sh run_recalage.sh chemin/chantier chemin/bd_uni
```

Pour recaler les bâtiments de la BD Uni dans une zone délimitée par une emprise :
```
sh run_recalage.sh chemin/chantier chemin/bd_uni chemin/emprise
```



# A faire

* Supprimer la bibliothèque Pysocle
* Mettre au propre les chantiers sur store-echange.
* Vérifier l'environnement.
* Description des résultats obtenus





# Description de la chaîne de traitement 

## Inférences de FFL

ssh CHuet-Admin@SMLPSLURMMFT1
cd /mnt/common/hdd/home/CHuet-Admin/FFL
sbatch /mnt/stores/store-DAI/pocs/saisie_monoscopique/chantiers_tests/run.sh


## nettoyage.py

A l'issue du Frame Field Learning, il y a quelques petites imperfections dans la géométrie au regard de la suite de l'algorithme :
* un côté de bâtiment peut être divisé en plusieurs segments
* des bâtiments sont côte à côte

Avant de lancer ce script, il faut appliquer l'outil Vecteur/Outils de geotraitement/Regrouper de QGis avec l'option "garder les entités disjointes séparées" sur les résultats du Frame Field Learning. Cela permet de regrouper en un seul bâtiment les bâtiments adjacents.

Ce script prend chaque polygone et fusionne les segments du polygone dans le cas où ils se suivent et que le produit scalaire est suypérieur à un seuil.

Dans le cas où l'outils GQIS n'a pas été appliqué auparavant, ce script identifie les côtés communs à plusieurs polygones. Ces côtés sont alors nettoyé suivant la même règle que ci-dessus. Dans l'étape suivante, on applique le nettoyage sur toutes les formes en ajoutant la contrainte qu'un segment commun à plusieurs polygones ne peut être modifié lors de cette étape. Sans cela, le nettoyage des segments communs sera fait différemment selon les polygones et on se retrouvera avec un nombre doublé de segments qui ne se superposent pas et qui viendront perturber la suite. Toutefois, il y a encore un ou deux petits défauts dans cette fonctionnalité. Il est donc préférable d'appliquer auparavant l'outils QGIS

## association_bati.py

Pour chaque pva, on dispose des polygones nettoyés. Il faut ensuite faire correspondre les polygones entre les pvas.

Pour cela, on projette sur le MNT chaque polygone. Pour chaque polygone, on regarde la surface de l'intersection entre ce polygone et les polygones des autres pvas. On associe le polygone avec celui avec lequel il partage la plus grande surface. Cette opération se fait dans les deux sens et pour chaque couple de pvas. Cela crée un graphe où un noeud représente un bâtiment et une arête représente une association. On cherche les composantes connexes et on attribue le même identifiant à tous les bâtiments d'un même groupe connexe.

Les bâtiments sont sauvegardés en format shapefile en coordonnées images et en coordonnées terrain.

## association_segments.py

Dans les shapefiles, tous les bâtiments possédant le même identifiant représentent le même bâtiment dans la réalité. Il faut maintenant associer les segments des bâtiments.

Pour chaque bâtiment réel, on dispose d'un certain nombre de bâtiments de pvas. On prend deux bâtiments de pvas. On fait un premier appariement des segments avec trois conditions en projection terrain 2D : 
* produit scalaire supérieur à un certain seuil
* distance des barycentres inférieures à la moitié de la longueur d'un segment
* distance d'un barycentre à l'autre segment inférieure à un certain seuil (5 mètres)

On conserve les appariements non ambigus, c'est-à-dire qui n'implique qu'exactement deux segments. Sur ces appariements non ambigus, on calcule une translation (dx, dy) qui doit permettre de superposer "parfaitement" les deux emprises au sol.

Puis on refait une deuxième association en appliquant la translation et où la distance d'un barycentre à l'autre segment doit être inférieure à un seuil très restreint (1 mètre). 

Passer par cette étape de calcul de translation permet notamment de supprimer les défauts en "dents de scie" sur les prédictions de frame field learning et d'éviter que les segments d'une façade ne soient associés à ceux de l'autre façade.

Puis, avec le même système de graphe connexe, on associe un même identifiant à tous les segments représentant un même bord de toit.

Les segments sont sauvegardés en format shapefile en coordonnées images et en coordonnées terrain.


## intersection_plan.py

On récupère tous les segments ayant le même identifiant. Pour chaque segment, on construit le plan passant par le sommet de prise de vue et le segment. On fait une intersection de plans par moindres carrés. Puis on détermine les extrémités de la droite. On fait cela sur tous les segments.

Les résultats sont sauvegardés sous format shapefile et sous format xyz (nuage de points) pour pouvoir être superposés avec le Lidar HD.


# Recalage de la BD Uni

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