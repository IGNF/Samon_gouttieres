from calculGoutieres import CalculGoutieres
import os
import argparse
from tools import get_mnt, get_raf, get_ta_xml


parser = argparse.ArgumentParser(description="On calcul la position des goutières")
parser.add_argument('--input', help='Répertoire où se trouvent les résultats de association_segments')
parser.add_argument('--mnt', help='Répertoire contenant le mnt sous format vrt')
parser.add_argument('--ta_xml', help="Répertoire contenant le tableau d'assemblage sous format xml")
parser.add_argument('--raf', help="Répertoire contenant la grille raf sous format tif")
parser.add_argument('--pvas', help="Répertoire contenant la grille raf sous format tif")
parser.add_argument('--output', help='Répertoire où sauvegarder les résultats')
args = parser.parse_args()

shapefile = args.input
resultats = args.output
mnt = get_mnt(args.mnt)
ta_xml = get_ta_xml(args.ta_xml)
raf = get_raf(args.raf)
pva = args.pvas


if not os.path.exists(resultats):
    os.makedirs(resultats)

calculGoutieres = CalculGoutieres(ta_xml, shapefile, mnt, raf, pva, resultats)
calculGoutieres.run()