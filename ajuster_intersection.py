import os
import geopandas as gpd
from shapely import LineString, polygonize
import numpy as np
from batiment import Batiment
import argparse
from fermer_batiment import get_id_bati_max, charger_goutieres
from typing import List







def charger_emprise(chemin_emprise):
    gdf = None
    if chemin_emprise != "None" and chemin_emprise is not None:
        gdf = gpd.read_file(chemin_emprise).geometry
    return gdf


def ajuster(batiment:Batiment):
    batiment.completer_voisins()
    for i in range(25):
        
        # On supprime les segments avec un seul voisin
        batiment.supprimer_segment_zero_un_voisin()
        # On initialise pour tous les segments les voisins
        batiment.initialiser_voisins()
        # Pour chaque segment du bâtiment, on associe les côtés voisins
        batiment.completer_voisins()
    batiment.ajuster_intersection()


def sauvegarde_shapefile(batiments:List[Batiment], resultat):
    id_bati = []
    id_segment = []
    geometries = []
    for batiment in batiments:
        for segment in batiment.segments:
            if not segment.supprime:
                id_bati.append(batiment.get_id())
                id_segment.append(segment.id_segment)
                geometries.append(LineString([segment.p1, segment.p2]))
        
    d = {"id_bati":id_bati, "id_segment":id_segment, "geometry":geometries}
    gdf = gpd.GeoDataFrame(d, crs="EPSG:2154")
    gdf.to_file(os.path.join(resultat, "intersections_ajustees.shp"))


def save_polygons(batiments:List[Batiment], resultat):
    """
    Transforme une liste de lignes en polygones et les sauvegarde
    """
    polygons = []
    id_bati = []
    for batiment in batiments:
        linestrings = []
        for segment in batiment.segments:
            if not segment.supprime:
                linestrings.append(LineString([segment.p1, segment.p2]))
        polygone = polygonize(linestrings)
        for geom in polygone.geoms:
            polygons.append(geom)
            id_bati.append(batiment.get_id())
    d = {"id_bati":id_bati, "geometry":polygons}
    gdf = gpd.GeoDataFrame(d, crs="EPSG:2154")
    gdf.to_file(os.path.join(resultat, "polygones.shp"))


def ajuster_intersections(shapefileDir, resultat, chemin_emprise):

    resolution = 0.5

    if not os.path.exists(resultat):
        os.makedirs(resultat)

    max_id, max_id_chantier = get_id_bati_max(shapefileDir)

    emprise = charger_emprise(chemin_emprise)

    # On charge les goutières
    liste_bati, liste_goutieresCalculees, batiments = charger_goutieres(shapefileDir, max_id, max_id_chantier, emprise=emprise)

    for batiment in batiments:
        ajuster(batiment)


    sauvegarde_shapefile(batiments, resultat)
    save_polygons(batiments, resultat)


if __name__=="__main__":
    parser = argparse.ArgumentParser(description="On ferme les bâtiments")
    parser.add_argument('--input', help='Répertoire où se trouvent le résultat de intersection_plan')
    parser.add_argument('--emprise', help='Répertoire où sauvegarder les résultats')
    parser.add_argument('--output', help='Répertoire où sauvegarder les résultats')
    args = parser.parse_args()

    # répertoire contenant les résultats du script association_segments.py
    shapefileDir = args.input
    resultat = args.output
    chemin_emprise = args.emprise

    ajuster_intersections(shapefileDir, resultat, chemin_emprise)



    
