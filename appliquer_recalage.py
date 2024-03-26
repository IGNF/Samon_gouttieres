import os
import geopandas as gpd
from tqdm import tqdm
import argparse
import numpy as np
from goutiere import Goutiere_proj
from bati import Bati
import random
from shapely import Polygon, MultiLineString, convex_hull, MultiPoint
from association_bati_BD_UNI import construire_geoseries
from batiRecalage import Bati_2D, Bati_gouttieres_2D, charger_bati, charger_bati_gouttieres, charger_bati_gouttieres_rapide


def association(bati_goutieres, bati_bd_uni, geoseries):
    # On parcourt chaque shapefile
    geoserie = geoseries["goutieres"]
    for b_uni in bati_bd_uni:
        


        if geoserie.intersects(b_uni.polygon).any():
            
            intersection = geoserie.intersection(b_uni.polygon)
            aire_commune = intersection.area
            bati_homologue = bati_goutieres[aire_commune.argmax()]
            if b_uni.id_origine == "BATIMENT0000000259384974":
                print("a")
                print(bati_homologue.id_origine, bati_homologue.TX)
            b_uni.TX = bati_homologue.TX
            b_uni.TY = bati_homologue.TY
            b_uni.a = bati_homologue.a
            b_uni.b = bati_homologue.b
            b_uni.nb_points = bati_homologue.nb_points
            b_uni.mean = bati_homologue.mean
            b_uni.res_max = bati_homologue.res_max

            
def recalculer_points(bati_bd_uni):
    for b_uni in bati_bd_uni:
        
        points = []
        if b_uni.TX is not None:
            
            
            TX = b_uni.TX
            TY = b_uni.TY
            a = b_uni.a
            b = b_uni.b
            k = b_uni.a**2 + b_uni.b**2
            if abs(k-1) < 0.2:
                rot = np.array([[b, a], [-a, b]])
                T = np.array([[TX], [TY]])
                rot_1 = np.linalg.inv(rot)
                for point in b_uni.polygon.boundary.coords:
                    X = np.array([[point[0]], [point[1]]])
                    Y = rot_1 @ (X - T)
                    points.append((Y[0,0], Y[1,0]))
        if len(points) > 2:
            b_uni.polygon = Polygon(points)


def get_id_max(chemin):
    id_max = -1
    gdf = gpd.read_file(chemin)
    for geometry in gdf.iterfeatures():
        id_max = max(id_max, geometry["properties"]["id"])
    return [[] for i in range(id_max+1)]


def sauvegarde_projection(bati_bd_uni, output):
    polygones = []
    nb_points = []
    mean = []
    res_max = []
    for bati in bati_bd_uni:
        polygones.append(bati.polygon)
        nb_points.append(bati.nb_points)
        mean.append(bati.mean)
        res_max.append(bati.res_max)
    
    d = {"nb_points":nb_points, "mean":mean, "res_max":res_max, "geometry": polygones}
    gdf = gpd.GeoDataFrame(d, crs="EPSG:2154")
    gdf.to_file(os.path.join(output, "emprise_finale.shp"))


def appliquer_recalage(input_gouttieres, input_BD_Uni, output):

    if not os.path.exists(output):
        os.makedirs(output)

    liste_id = get_id_max(input_gouttieres)
    bati_goutieres = charger_bati_gouttieres_rapide(input_gouttieres, "id", liste_id=liste_id)
    bati_bd_uni = charger_bati(input_BD_Uni, "cleabs")

    batis_par_shapefile = [{"shapefile":"goutieres", "batis":bati_goutieres}, {"shapefile":"bd_uni", "batis":bati_bd_uni}]
    geoseries = construire_geoseries(batis_par_shapefile)

    association(bati_goutieres, bati_bd_uni, geoseries)
    recalculer_points(bati_bd_uni)
    sauvegarde_projection(bati_bd_uni, output)




if __name__=="__main__":

    parser = argparse.ArgumentParser(description="On trouve les 4 paramètres pour le recalage de la BD Uni sur la BD Ortho")
    parser.add_argument('--input_gouttieres', help='Répertoire où se trouvent les résultats de recalage.py')
    parser.add_argument('--input_BD_Uni', help='Répertoire contenant les bâtiments de la BD Uni à recaler')
    parser.add_argument('--output', help='Répertoire où sauvegarder les résultats')
    args = parser.parse_args()


    input_gouttieres = args.input_gouttieres
    input_BD_Uni = args.input_BD_Uni
    output = args.output

    appliquer_recalage(input_gouttieres, input_BD_Uni, output)