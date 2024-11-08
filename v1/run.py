import argparse
import os
from nettoyage import nettoyage
from association_bati import association_bati
from association_segments import association_segments
from intersection_plan import intersection_plan
from fermer_batiment import fermer_batiment_main
from ajuster_intersection import ajuster_intersections


def run(chantier, emprise):

    gouttieres = os.path.join(chantier, "gouttieres")

    print("Nettoyage des géométries")
    nettoyage(os.path.join(gouttieres, "predictions_FFL"), os.path.join(gouttieres, "nettoye"))
    
    print("Association d'un même identifiant aux bâtiments")
    association_bati(
        os.path.join(gouttieres, "nettoye"),
        os.path.join(chantier, "mnt"),
        os.path.join(chantier, "orientation"),
        os.path.join(chantier, "raf"),
        emprise,
        os.path.join(gouttieres, "association_bati")
    )

    print("Association d'un même identifiant aux murs")
    association_segments(
        os.path.join(gouttieres, "association_bati"),
        os.path.join(chantier, "mnt"),
        os.path.join(chantier, "orientation"),
        os.path.join(chantier, "raf"),
        os.path.join(gouttieres, "association_segments")
    )

    print("Calcul des gouttières")
    intersection_plan(
        os.path.join(gouttieres, "association_segments"),
        os.path.join(chantier, "mnt"),
        os.path.join(chantier, "orientation"),
        os.path.join(chantier, "raf"),
        os.path.join(gouttieres, "intersection_plan")
    )

    print("Fermeture des bâtiments")
    fermer_batiment_main(
        os.path.join(gouttieres, "intersection_plan"),
        os.path.join(gouttieres, "batiments_fermes")
    )

    print("Ajustement des intersections sur les gouttières calculées")
    ajuster_intersections(
        os.path.join(gouttieres, "intersection_plan"),
        os.path.join(gouttieres, "intersections_ajustees"), 
        emprise
    )


if __name__=="__main__":
    parser = argparse.ArgumentParser(description="Exécuter la recherche de gouttières")
    parser.add_argument('--chantier', help='Répertoire du chantier')
    parser.add_argument('--emprise', help='Chemin du fichier emprise', default=None)
    args = parser.parse_args()

    chantier = args.chantier
    emprise = args.emprise

    run(chantier, emprise)