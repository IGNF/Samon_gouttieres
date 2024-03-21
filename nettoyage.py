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
    


def create_polygons(shapefile):
    
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
            x1 = coordinates[i+1][0]
            y1 = coordinates[i+1][1]
            # Pour chaque segment, s'il existe déjà, on le récupère, sinon on le crée
            segment, liste_segments = create_segment(liste_segments, Point(x0, y0), Point(x1, y1))
            liste_segments_poly.append(segment) 
        # Pour chaque segment du polygone, on indique que le segment appartient à ce polygone
        polygon = Polygon(id_polygon, liste_segments_poly)
        #polygon.relier_segments()
        liste_polygons.append(polygon)
    return liste_polygons, liste_segments, query


def lisser(segments):
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
    x1 = s0.P1.x
    y1 = s0.P1.y
    
    for i in range(1, nb_segments):
        
        s1 = segments[i]
        x2 = s1.P1.x
        y2 = s1.P1.y
        u1 = np.array([[x1-x0], [y1-y0]])
        u1 = u1 / np.linalg.norm(u1)
        u2 = np.array([[x2-x1], [y2-y1]])
        u2 = u2 / np.linalg.norm(u2)
        ps = np.sum(u1*u2)
        if ps > seuil_ps and not s1.immobile and not s0.immobile:
            x1 = x2
            y1 = y2
        else:
            linestring = LineString([[x0, y0], [x1, y1]])
            liste_segments_poly.append(linestring)
            x0 = s1.P0.x
            y0 = s1.P0.y
            x1 = x2
            y1 = y2
            s0 = segments[i]
    
    if len(liste_segments_poly)==0:
        linestring = LineString([[x0, y0], [x2, y2]])
        liste_segments_poly.append(linestring)
    else:
        x,y = liste_segments_poly[0].xy
        x2 = x[1]
        y2 = y[1]
        u1 = np.array([[x1-x0], [y1-y0]])
        u1 = u1 / np.linalg.norm(u1)
        u2 = np.array([[x2-x1], [y2-y1]])
        u2 = u2 / np.linalg.norm(u2)
        ps = np.sum(u1*u2)
        if ps > seuil_ps and not segments[0].immobile and not segments[-1].immobile:
            del(liste_segments_poly[0])
            linestring = LineString([[x0, y0], [x2, y2]])
            liste_segments_poly.append(linestring)
        else:
            linestring = LineString([[x0, y0], [x1, y1]])
            liste_segments_poly.append(linestring)

    for segment in liste_segments_poly:
        x, y = segment.xy
        nouveaux_segments.append(Segment(Point(x[0], y[0]), Point(x[1], y[1]), immobile=True))
    return nouveaux_segments



def simplifier_geometry(poly1, poly2):
    segments1 = []
    segments2 = []
    for segment1 in poly1.segments:
        segment2 = poly2.possede_segment(segment1)
        if segment2 is not None:
            segments1.append(segment1)
            segments2.append(segment2)
    nouveau_segments = lisser(segments1)
    poly1.replace(segments1, nouveau_segments)
    poly2.replace(segments2, nouveau_segments)
    


def sauvegarde(liste_polygons:List[Polygon]):
    id = []
    polygones = []
    compte_id = 0

    for polygone in liste_polygons:
        for p in polygone.export_shapely():
            polygones.append(p)
            
            id.append(compte_id)
            compte_id += 1

    d = {"id": id, "id_g": None, "geometry": polygones}
    gdf = gpd.GeoDataFrame(d, crs="EPSG:2154")
    gdf.to_file(os.path.join(output, shapefile))




if __name__=="__main__":

    parser = argparse.ArgumentParser(description="On nettoie les géométries de manière à ce qu'un segment corresponde à un mur")
    parser.add_argument('--input', help='Répertoire où se trouvent les géométries regroupées')
    parser.add_argument('--output', help='Répertoire où sauvegarder les résultats')
    args = parser.parse_args()

    input = args.input
    output = args.output
    seuil_ps = 0.99
    seuil_area = 5


    if not os.path.exists(output):
        os.makedirs(output)

    shapefiles = sorted([i for i in os.listdir(input) if i[-4:]==".shp"])
    for shapefile in tqdm(shapefiles):
        print(shapefile)
        # On crée les géométries
        liste_polygons, liste_segments, query = create_polygons(shapefile)

        for polygon in liste_polygons:
            nouveaux_segments = lisser(polygon.segments)
            polygon.set_segments(nouveaux_segments)
        
        
        sauvegarde(liste_polygons)

