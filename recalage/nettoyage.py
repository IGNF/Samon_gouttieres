import os
import geopandas as gpd
import numpy as np
from shapely import LineString, Point
from tqdm import tqdm
from segment import Segment
from polygon import Polygon
import argparse
from typing import List



def create_segment(liste_segments, P0, P1):
    segment = Segment(P0, P1)
    liste_segments.append(segment)
    return segment, liste_segments
    


def create_polygons(input, shapefile):
    
    liste_segments = []
    liste_polygons = []
    gdf = gpd.read_file(os.path.join(input, shapefile))
    s = gdf.geometry.make_valid()
    query = s.sindex.query(s, predicate="touches")

    for geometry in gdf.iterfeatures():
        # On parcourt toutes les géométries
        liste_segments_poly = []
        coordinates = geometry["geometry"]["coordinates"][0]
        if isinstance(coordinates[0][0], tuple):
            coordinates = coordinates[0]
        id_polygon = geometry["id"]
        nb_points = len(coordinates)
        # On parcourt les segments
        for i in range(nb_points-1):
            x0 = coordinates[i][0]
            y0 = coordinates[i][1]
            z0 = coordinates[i][2]
            x1 = coordinates[i+1][0]
            y1 = coordinates[i+1][1]
            z1 = coordinates[i+1][2]
            # Pour chaque segment, s'il existe déjà, on le récupère, sinon on le crée
            segment, liste_segments = create_segment(liste_segments, Point(x0, y0, z0), Point(x1, y1, z1))
            liste_segments_poly.append(segment) 
        # Pour chaque segment du polygone, on indique que le segment appartient à ce polygone
        polygon = Polygon(id_polygon, liste_segments_poly)
        polygon.level_1 = geometry["properties"]["level_1"]
        #polygon.relier_segments()
        liste_polygons.append(polygon)
    return liste_polygons, liste_segments, query


def lisser(segments, seuil_ps):
    nouveaux_segments = []
    liste_segments_poly = []
    nb_segments = len(segments)
    if nb_segments <= 1:
        for segment in segments:
            segment.immobile = True
            nouveaux_segments.append(segment)
        return nouveaux_segments
    s0 = segments[0]
    x0 = s0.P0.x
    y0 = s0.P0.y
    z0 = s0.P0.z
    x1 = s0.P1.x
    y1 = s0.P1.y
    z1 = s0.P1.z
    
    for i in range(1, nb_segments):
        
        s1 = segments[i]
        x2 = s1.P1.x
        y2 = s1.P1.y
        z2 = s1.P1.z
        u1 = np.array([[x1-x0], [y1-y0]])
        u1 = u1 / np.linalg.norm(u1)
        u2 = np.array([[x2-x1], [y2-y1]])
        u2 = u2 / np.linalg.norm(u2)
        ps = np.sum(u1*u2)
        if ps > seuil_ps and not s1.immobile and not s0.immobile:
            x1 = x2
            y1 = y2
            z1 = z2
        else:
            linestring = LineString([[x0, y0, z0], [x1, y1, z1]])
            liste_segments_poly.append(linestring)
            x0 = s1.P0.x
            y0 = s1.P0.y
            x1 = x2
            y1 = y2
            z1 = z2
            s0 = segments[i]
    
    if len(liste_segments_poly)==0:
        linestring = LineString([[x0, y0, z0], [x2, y2, z2]])
        liste_segments_poly.append(linestring)
    else:
        xyz = list(liste_segments_poly[0].coords)
        x2 = xyz[1][0]
        y2 = xyz[1][1]
        z2 = xyz[1][2]
        u1 = np.array([[x1-x0], [y1-y0]])
        u1 = u1 / np.linalg.norm(u1)
        u2 = np.array([[x2-x1], [y2-y1]])
        u2 = u2 / np.linalg.norm(u2)
        ps = np.sum(u1*u2)
        if ps > seuil_ps and not segments[0].immobile and not segments[-1].immobile:
            del(liste_segments_poly[0])
            linestring = LineString([[x0, y0, z0], [x2, y2, z2]])
            liste_segments_poly.append(linestring)
        else:
            linestring = LineString([[x0, y0, z0], [x1, y1, z1]])
            liste_segments_poly.append(linestring)

    for segment in liste_segments_poly:
        xyz = segment.coords
        nouveaux_segments.append(Segment(Point(xyz[0][0], xyz[0][1], xyz[0][2]), Point(xyz[1][0], xyz[1][1], xyz[1][2]), immobile=True))
    return nouveaux_segments



def sauvegarde(liste_polygons:List[Polygon], output, shapefile):
    id = []
    polygones = []
    level_1 = []
    compte_id = 0

    for polygone in liste_polygons:
        for p in polygone.export_shapely():
            polygones.append(p)
            
            id.append(compte_id)
            compte_id += 1
            level_1.append(polygone.level_1)

    d = {"id": id, "id_g": None, "geometry": polygones, "level_1":level_1}
    gdf = gpd.GeoDataFrame(d, crs="EPSG:2154")
    gdf.to_file(os.path.join(output, shapefile))



def nettoyage(input, output):

    seuil_ps = 0.99

    if not os.path.exists(output):
        os.makedirs(output)

    shapefiles = sorted([i for i in os.listdir(input) if i[-5:]==".gpkg"])
    for shapefile in tqdm(shapefiles):
        # On crée les géométries
        liste_polygons, liste_segments, query = create_polygons(input, shapefile)

        for polygon in liste_polygons:
            nouveaux_segments = lisser(polygon.segments, seuil_ps)
            polygon.set_segments(nouveaux_segments)
        
        
        sauvegarde(liste_polygons, output, shapefile)



if __name__=="__main__":

    parser = argparse.ArgumentParser(description="On nettoie les géométries de manière à ce qu'un segment corresponde à un mur")
    parser.add_argument('--input', help='Répertoire où se trouvent les géométries regroupées')
    parser.add_argument('--output', help='Répertoire où sauvegarder les résultats')
    args = parser.parse_args()

    input = args.input
    output = args.output

    nettoyage(input, output)
    


    

