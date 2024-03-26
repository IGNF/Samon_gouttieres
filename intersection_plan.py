from calculGoutieres import CalculGoutieres
import os
import argparse
from tools import get_mnt, get_raf, get_ta_xml


def intersection_plan(shapefile, mnt, ta_xml, raf, resultats):

    mnt = get_mnt(mnt)
    ta_xml = get_ta_xml(ta_xml)
    raf = get_raf(raf)



    if not os.path.exists(resultats):
        os.makedirs(resultats)

    calculGoutieres = CalculGoutieres(ta_xml, shapefile, mnt, raf, resultats)
    calculGoutieres.run()


if __name__=="_main__":
    parser = argparse.ArgumentParser(description="On calcule la position des goutières")
    parser.add_argument('--input', help='Répertoire où se trouvent les résultats de association_segments')
    parser.add_argument('--mnt', help='Répertoire contenant le mnt sous format vrt')
    parser.add_argument('--ta_xml', help="Répertoire contenant le tableau d'assemblage sous format xml")
    parser.add_argument('--raf', help="Répertoire contenant la grille raf sous format tif")
    parser.add_argument('--output', help='Répertoire où sauvegarder les résultats')
    args = parser.parse_args()

    shapefile = args.input
    resultats = args.output
    mnt = args.mnt
    ta_xml = args.ta_xml
    raf = args.raf
    pva = args.pvas

    intersection_plan(shapefile, mnt, ta_xml, raf, resultats)
