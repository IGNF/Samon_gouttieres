import os
import geopandas as gpd
from shapely import LineString
import numpy as np
from batiment import Batiment
import argparse
from fermer_batiment import get_id_bati_max, charger_goutieres

parser = argparse.ArgumentParser(description="On ferme les bâtiments")
parser.add_argument('--input', help='Répertoire où se trouvent le résultat de intersection_plan')
parser.add_argument('--emprise', help='Répertoire où sauvegarder les résultats')
parser.add_argument('--output', help='Répertoire où sauvegarder les résultats')
args = parser.parse_args()

# répertoire contenant les résultats du script association_segments.py
shapefileDir = args.input
resultat = args.output
chemin_emprise = args.emprise

resolution = 0.5

if not os.path.exists(resultat):
    os.makedirs(resultat)



def charger_emprise(chemin_emprise):
    gdf = None
    if chemin_emprise != "None":
        gdf = gpd.read_file(chemin_emprise).geometry
    return gdf


def ajuster(batiment:Batiment):
    batiment.completer_voisins()
    for i in range(25):
        
        # On supprime les segments avec un seul voisin
        batiment.supprimer_segment_zero_voisin()
        # On initialise pour tous les segments les voisins
        batiment.initialiser_voisins()
        # Pour chaque segment du bâtiment, on associe les côtés voisins
        batiment.completer_voisins()
    batiment.ajuster_intersection()


def sauvegarde_shapefile(batiments):
    id = []
    geometries = []
    for batiment in batiments:
        for segment in batiment.segments:
            id.append(batiment.get_id())
            geometries.append(LineString([segment.p1, segment.p2]))
        
    d = {"id":id, "geometry":geometries}
    gdf = gpd.GeoDataFrame(d, crs="EPSG:2154")
    gdf.to_file(os.path.join(resultat, "intersections_ajustees.shp"))


def sauvegarder_points(batiments):
    for batiment in batiments:
        for segment in batiment.segments:
                    p1 = np.array([[segment.p1.x], [segment.p1.y], [segment.p1.z]])
                    p2 = np.array([[segment.p2.x], [segment.p2.y], [segment.p2.z]])
                    u = p2 - p1
                    norm_u = np.linalg.norm(u)
                    if norm_u > 0 and norm_u < 200:
                        u_norm = u / norm_u
                        nb_points = int(norm_u / resolution)

                        with open(os.path.join(resultat, "intersections_ajustees.txt"), "a") as f:
                            for i in range(nb_points):
                                p = p1 + i * resolution * u_norm
                                f.write("{} {} {}\n".format(p[0, 0], p[1, 0], p[2, 0]))


max_id, max_id_chantier = get_id_bati_max(shapefileDir)

emprise = charger_emprise(chemin_emprise)

# On charge les goutières
liste_bati, liste_goutieresCalculees, batiments = charger_goutieres(shapefileDir, max_id, max_id_chantier, emprise=emprise)

for batiment in batiments:
    ajuster(batiment)


sauvegarde_shapefile(batiments)
sauvegarder_points(batiments)
    
