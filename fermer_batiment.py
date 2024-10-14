from goutiereCalculee import GoutiereCalculee
import os
import geopandas as gpd
from shapely import Polygon
import numpy as np
from batiment import Batiment
from typing import List
import argparse






def get_id_bati_max(shapefileDir):
    """
    Récupère la liste des identifiants de goutières qui existent dans les différents shapefiles, ainsi que l'identifiant maximum
    """
    liste_id_bati = []
    max_id_bati = 0
    max_id_chantier = 0
    #shapefiles = [i for i in os.listdir(shapefileDir) if i[-4:] == ".shp"]
    shapefiles = ["goutiere.shp"]
    # On parcourt les shapefiles
    for shapefile in shapefiles:
        # On parcourt toutes les géométries présentes dans le shapefile 
        gdf = gpd.read_file(os.path.join(shapefileDir, shapefile))
        for geometry in gdf.iterfeatures():
            id_bati = geometry["properties"]["id_bati"]
            id = geometry["properties"]["id"]
            if id_bati != -1:
                # Si l'id n'est pas dans la liste, alors on l'ajoute
                if id_bati not in liste_id_bati:
                    liste_id_bati.append(id_bati)
                    max_id_bati = max(max_id_bati, id_bati)
                max_id_chantier = max(max_id_chantier, id)
    return max_id_bati, max_id_chantier



def charger_goutieres(shapefileDir, max_id_bati, max_id_chantier, emprise=None):
    liste_bati = [[] for i in range(max_id_bati+1)]
    liste_goutieresCalculees = [[] for i in range(max_id_chantier+1)]
    shapefiles = [i for i in os.listdir(shapefileDir) if i[-4:] == ".shp"]
    shapefiles = ["goutiere.shp"]
    # On parcourt les shapefiles
    for shapefile in shapefiles:
        # On parcourt toutes les géométries présentes dans le shapefile 
        gdf = gpd.read_file(os.path.join(shapefileDir, shapefile))
        for geometry in gdf.iterfeatures():
            x1 = geometry["properties"]["x1"]
            y1 = geometry["properties"]["y1"]
            z1 = geometry["properties"]["z1"]
            x2 = geometry["properties"]["x2"]
            y2 = geometry["properties"]["y2"]
            z2 = geometry["properties"]["z2"]
            id_segment = geometry["properties"]["id"]
            id_bati = geometry["properties"]["id_bati"]
            goutiereCalculee = GoutiereCalculee(x1, y1, z1, x2, y2, z2, id_bati, id_segment)

            continuer = True
            if emprise is not None:
                if not goutiereCalculee.emprise_sol().within(emprise).any():
                    continuer = False
            if continuer:
                liste_bati[id_bati].append(goutiereCalculee)
                liste_goutieresCalculees[id_segment].append(goutiereCalculee)
                for i in range(8):
                    v = geometry["properties"]["v_{}".format(i)]
                    if v is not None and int(v) != id_segment:
                        goutiereCalculee.id_voisins.append(int(v))
    
    batiments = []
    for i, bati in enumerate(liste_bati):
        if len(bati) > 0:
            batiment = Batiment(bati)
            batiments.append(batiment)

    return liste_bati, liste_goutieresCalculees, batiments


def sauvegarde_shapefile(batiments, resultat):
    id = []
    geometries = []
    for batiment in batiments:
        if batiment.get_id() == 2886:
            print(len(batiment.batiments_fermes[0]))
        if len(batiment.batiments_fermes[0]) > 1:
            for i, bati_ferme in enumerate(batiment.batiments_fermes):
                if not None in bati_ferme:
                    #print(batiment.get_id())
                    #print(bati_ferme)
                    id.append(batiment.get_id())
                    #geometries.append(LineString(bati_ferme))
                    geometries.append(Polygon(bati_ferme))
        
    d = {"id":id, "geometry":geometries}
    gdf = gpd.GeoDataFrame(d, crs="EPSG:2154")
    gdf.to_file(os.path.join(resultat, "batiments_fermes.shp"))



def gerer_cas_particuliers(batiment:Batiment):
    # Gestion des cas particuliers : petits bâtiments avec une configuration particulière (souvent, ce sont des rectangles où il manque un ou deux côtés)
    
    # Le bâtiment est constitué de deux droites parallèles
    batiment.cas_2_paralleles()

    # Le bâtiment est constitué de deux droites perpendicualaires
    batiment.cas_2_perpendiculaires()

    # Le bâtiment est constitué de trois côtés (et un seul est manquant)
    batiment.cas_3_segments()

    # Pour chaque segment du bâtiment, on associe les côtés voisins
    batiment.completer_voisins()


def fermer_batiment_2(batiment:Batiment):
    """
    Première méthode
    """
    
    # On supprime tous les segments qui n'ont qu'un seul voisin
    # Si après cette nouvelle suppression, de nouveaux segments n'ont qu'un seul voisin, on les supprime
    # Et ainsi de suite jusqu'à ce que tous les segments qui restent ont au moins deux voisins
    for i in range(15):
        # On supprime les segments avec un seul voisin
        batiment.supprimer_segment_un_seul_voisin()
        # On initialise pour tous les segments les voisins
        batiment.initialiser_voisins()
        # Pour chaque segment du bâtiment, on associe les côtés voisins
        batiment.completer_voisins()
    
    # Pour tous les segments fictifs, on détermine les coordonnées de leurs extrémités
    batiment.mise_a_jour_segments_fictifs()

    # On supprime les doublons fictifs
    batiment.supprimer_fictif_doublons()

    # Dans les deux étapes précédentes, certains segments ont été supprimés
    # On relance le calcul des voisins
    batiment.completer_voisins()
    for i in range(15):
        batiment.supprimer_segment_un_seul_voisin()
        batiment.initialiser_voisins()
        batiment.completer_voisins()
    
    # On ferme le bâtiment
    batiment.fermer_batiment()


def fermer_batiments(batiments:List[Batiment]):
    nouveaux_batiments = []

    # On parcourt les bâtiments
    for batiment in batiments:
        # On gère les cas particuliers
        gerer_cas_particuliers(batiment)
        composantes_connexes = batiment.composantes_connexes()

        # S'il y a au moins deux composantes connexes
        if len(composantes_connexes) >= 2:
            # Le bâtiment regroupe désormais les segments de la première composante connexe
            batiment.segments = composantes_connexes[0]
            # On relance le calcul des cas particuliers sur ce batiment
            gerer_cas_particuliers(batiment)

            # Pour toutes les autres composante connexes, on crée un bâtiment et on effectue le calcul des cas particuliers
            for i in range(1, len(composantes_connexes)):
                nouveau_batiment = Batiment(composantes_connexes[i])
                gerer_cas_particuliers(nouveau_batiment)
                nouveaux_batiments.append(nouveau_batiment)

    # On ajoute à la liste des bâtiments tous les nouveaux bâtiments dus aux composantes connexes multiples
    for nouveau_batiment in nouveaux_batiments:
        gerer_cas_particuliers(nouveau_batiment)
        batiments.append(nouveau_batiment)



    # On passe à l'étape de fermeture des bâtiments
    for batiment in batiments:
        # Application de la première méthode 
        fermer_batiment_2(batiment)

        # Si la première méthode est un échec
        if len(batiment.batiments_fermes)==0:
            # On essaye de relier les extrémités
            batiment.tentative_relier_extremite()
            fermer_batiment_2(batiment)
        
        # Si cela n'a toujours pas marché, alors on essaye de retrouver la chaîne de segments la plus longue
        if len(batiment.batiments_fermes)==0:
            batiment.tentative_plus_longue_chaine()

        batiment.verifier_coherence()



def sauvegarder_points(batiments, path_xyz, resolution):
    for batiment in batiments:
        for bati_ferme in batiment.batiments_fermes:
            if len(batiment.batiments_fermes[0]) > 1:
                for i in range(len(bati_ferme)-1):
                    p1 = np.array([[bati_ferme[i].x], [bati_ferme[i].y], [bati_ferme[i].z]])
                    p2 = np.array([[bati_ferme[i+1].x], [bati_ferme[i+1].y], [bati_ferme[i+1].z]])
                    u = p2 - p1
                    norm_u = np.linalg.norm(u)
                    if norm_u > 0 and norm_u < 200:
                        u_norm = u / norm_u
                        nb_points = int(norm_u / resolution)

                        with open(path_xyz, "a") as f:
                            for i in range(nb_points):
                                p = p1 + i * resolution * u_norm
                                f.write("{} {} {}\n".format(p[0, 0], p[1, 0], p[2, 0]))

def fermer_batiment_main(shapefileDir, resultat):
    path_xyz= os.path.join(resultat, "batis_fermes.xyz")

    resolution = 0.05

    if not os.path.exists(resultat):
        os.makedirs(resultat)

    if os.path.exists(path_xyz):
        os.remove(path_xyz)

    # On récupère les identifiants max
    max_id, max_id_chantier = get_id_bati_max(shapefileDir)

    # On charge les goutières
    liste_bati, liste_goutieresCalculees, batiments = charger_goutieres(shapefileDir, max_id, max_id_chantier)

    fermer_batiments(batiments)


    sauvegarde_shapefile(batiments, resultat)
    sauvegarder_points(batiments, path_xyz, resolution)


if __name__=="__main__":

    parser = argparse.ArgumentParser(description="On ferme les bâtiments")
    parser.add_argument('--input', help='Répertoire où se trouvent le résultat de intersection_plan')
    parser.add_argument('--output', help='Répertoire où sauvegarder les résultats')
    args = parser.parse_args()

    # répertoire contenant les résultats du script association_segments.py
    shapefileDir = args.input
    resultat = args.output

    fermer_batiment_main(shapefileDir, resultat)