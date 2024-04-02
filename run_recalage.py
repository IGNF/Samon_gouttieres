import argparse
import os
from run import run
from dissolve import dissolve
from ajuster_intersection import ajuster_intersections
from association_bati_BD_UNI import association_bati_bd_uni
from association_segments_BD_UNI import association_segments_bd_uni
from recalage import recalage
from appliquer_recalage import appliquer_recalage


parser = argparse.ArgumentParser(description="Exécuter la recherche de gouttières")
parser.add_argument('--chantier', help='Répertoire du chantier')
parser.add_argument('--bduni', help='Répertoire du chantier')
parser.add_argument('--emprise', help='Chemin du fichier emprise', default=None)
args = parser.parse_args()

chantier = args.chantier
bduni = args.bduni
emprise = args.emprise

gouttieres = os.path.join(chantier, "gouttieres")

run(chantier, emprise)

print("Regroupement des géométries jointives dans la BD Uni")
dissolve(bduni, os.path.join(gouttieres, "BD_Uni_regroupee"))

print("Ajustement des intersections sur les gouttières calculées")
ajuster_intersections(
    os.path.join(gouttieres, "intersection_plan"),
    os.path.join(gouttieres, "intersections_ajustees"), 
    emprise
)

print("Association des bâtiments gouttières / BD Uni")
association_bati_bd_uni(
    os.path.join(gouttieres, "intersections_ajustees"), 
    os.path.join(gouttieres, "BD_Uni_regroupee"), 
    os.path.join(gouttieres, "association_bati_BD_Uni")
)

print("Association des segments gouttières / BD Uni")
association_segments_bd_uni(
    os.path.join(gouttieres, "association_bati_BD_Uni"), 
    os.path.join(gouttieres, "association_segments_BD_Uni")
)

print("Calcul des paramètres pour recaler la BD Uni")
recalage(
    os.path.join(gouttieres, "association_segments_BD_Uni"), 
    os.path.join(gouttieres, "recalage")
)

print("Application des paramètres sur la BD Uni")
appliquer_recalage(
    os.path.join(gouttieres, "recalage"),
    bduni,
    os.path.join(gouttieres, "BD_Uni_recalee")
)