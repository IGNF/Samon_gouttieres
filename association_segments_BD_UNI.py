import os
import geopandas as gpd
import argparse
import numpy as np
from goutiere import Goutiere_proj
from association_segments import association, reorganiser_goutieres_par_shapefile, sauvegarde_projection
from bati import BatiProjete


parser = argparse.ArgumentParser(description="On associe le même identifiant à tous les segments représentant un même mur")
parser.add_argument('--input', help='Répertoire où se trouvent les résultats de association_bati_BD_UNI.py')
parser.add_argument('--output', help='Répertoire où sauvegarder les résultats')
args = parser.parse_args()


input = args.input
output = args.output




def get_id_bati_max():
    liste_id = []
    max_id = 0
    shapefiles = [i for i in os.listdir(input) if i[-4:] == ".shp"]
    for shapefile in shapefiles:
        # On parcourt toutes les géométries présentes dans le shapefile 
        gdf = gpd.read_file(os.path.join(input, shapefile))
        for geometry in gdf.iterfeatures():
            id = geometry["properties"]["id"]
            if id != -1:
                # Si l'id n'est pas dans la liste, alors on l'ajoute
                if id not in liste_id:
                    liste_id.append(id)
                    max_id = max(max_id, id)
    return liste_id, max_id


def create_goutieres(max_id):
    """
    On retire de la liste des shots tous les shots dont les pvas correspondantes sont manquantes
    """
    id_unique = 0
    batis = [[] for i in range(max_id+1)]
    pvas = [i.split(".")[0] for i in os.listdir(input) if i[-4:]==".shp"]

    # On parcouirt toutes les pvas du ta
    for pva in pvas:

        # On ouvre le fichier shapefile
        gdf = gpd.read_file(os.path.join(input, pva+".shp"))
                    
        # On parcourt les géométries
        for geometry in gdf.iterfeatures():
            id = int(geometry["properties"]["id"])

            if geometry["geometry"]["type"] == "MultiLineString":
                segments = geometry["geometry"]["coordinates"]
            else:
                points = geometry["geometry"]["coordinates"]
                segments = []
                for i in range(len(points)-1):
                    segments.append([points[i], points[i+1]])



            goutieres = []
            for segment in segments:
               
                            
                world_line = np.array([[segment[0][0], segment[0][1], segment[0][2]], [segment[1][0], segment[1][1], segment[1][2]]])
                    
                # On crée la goutière
                goutiere = Goutiere_proj(os.path.join(input, pva+".shp"), id, pva)
                            
                # On calcule les paramètres du plan passant par le sommet de prise de vue et la goutière
                goutiere.world_line = world_line
                goutiere.id_bati = id
                goutiere.id_unique = id_unique
                id_unique += 1
                            
                goutieres.append(goutiere)

            bati = BatiProjete(goutieres)
            bati.id = id

            # Pour chaque goutière du bati, on indique par un identifiant ses voisins
            #bati.set_voisins()
            bati.numpy_array = bati.create_numpy_array()

            batis[bati.id].append(bati)     
    return batis




if not os.path.exists(output):
    os.makedirs(output)


# Récupère l'identifiant maximum présent dans le bati
liste_id, max_id = get_id_bati_max()
batis = create_goutieres(max_id)

#for bati in batis:
#    print(bati)

association(batis, minimum_batiment=2)
goutieres_par_shapefile = reorganiser_goutieres_par_shapefile(batis)

sauvegarde_projection(goutieres_par_shapefile, output, save_voisin=False)