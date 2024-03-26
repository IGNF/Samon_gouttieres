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
dissolve(bduni, os.path.join(gouttieres, "BD_Uni_regroupee"))

ajuster_intersections(
    os.path.join(gouttieres, "intersection_plan"),
    os.path.join(gouttieres, "intersections_ajustees"), 
    emprise
)

association_bati_bd_uni(
    os.path.join(gouttieres, "intersections_ajustees"), 
    os.path.join(gouttieres, "BD_Uni_regroupee"), 
    os.path.join(gouttieres, "association_bati_BD_Uni")
)

association_segments_bd_uni(
    os.path.join(gouttieres, "association_bati_BD_Uni"), 
    os.path.join(gouttieres, "association_segments_BD_Uni")
)
recalage(
    os.path.join(gouttieres, "association_segments_BD_Uni"), 
    os.path.join(gouttieres, "recalage")
)
appliquer_recalage(
    os.path.join(gouttieres, "recalage"),
    bduni,
    os.path.join(gouttieres, "BD_Uni_recalee")
)