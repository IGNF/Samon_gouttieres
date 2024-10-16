import os
import geopandas as gpd
import numpy as np
from tqdm import tqdm
from bati import Bati
from goutiere import Goutiere_image
from typing import List, Dict
import statistics
import argparse
from tools import get_mnt, get_raf, get_ta_xml, get_shots
from sklearn.feature_extraction.image import extract_patches_2d
from shot import MNT, RAF


seuil_ps = 0.85
seuil_distance = 5
seuil_longueure_goutiere = 2
seuil_distance_droite_1 = 5
seuil_distance_droite_2 = 1



def get_id_bati_max(shapefileDir):
    liste_id = []
    max_id = 0
    shapefiles = [i for i in os.listdir(shapefileDir) if i[-4:] == ".shp"]
    for shapefile in shapefiles:
        # On parcourt toutes les géométries présentes dans le shapefile 
        gdf = gpd.read_file(os.path.join(shapefileDir, shapefile))
        for geometry in gdf.iterfeatures():
            id = geometry["properties"]["id"]
            if id != -1:
                # Si l'id n'est pas dans la liste, alors on l'ajoute
                if id not in liste_id:
                    liste_id.append(id)
                    max_id = max(max_id, id)
    return liste_id, max_id
    



def create_goutieres(shots, max_id, mnt, shapefileDir):
    """
    On retire de la liste des shots tous les shots dont les pvas correspondantes sont manquantes
    """
    id_unique = 0
    batis = [[] for i in range(max_id+1)]
    pvas = [i.split(".")[0] for i in os.listdir(shapefileDir)]
    # On parcouirt toutes les pvas du ta
    for shot in shots:
        # Si pour la pva on a un fichier shapefile avec des goutières :
        if shot.image in pvas:
            # On ouvre le fichier shapefile
            gdf = gpd.read_file(os.path.join(shapefileDir, shot.image+".shp"))
                    
            # On parcourt les géométries
            print("Chargement de l'image {}".format(shot.image))
            for feature in tqdm(gdf.iterfeatures()):
                id = int(feature["properties"]["id"])
                estim_z = float(feature["properties"]["estim_z"])

                bati = Bati(id, feature["geometry"], shot, mnt, compute_gouttiere=True, unique_id=id_unique, estim_z=estim_z)
                id_unique = bati.goutieres[-1].id_unique

                # Pour chaque goutière du bati, on indique par un identifiant ses voisins
                bati.set_voisins()
                bati.numpy_array = bati.create_numpy_array()

                batis[bati.id_origine].append(bati)     
    
    return batis


def premier_appariement(b1:Bati, b2:Bati):
    for goutiere in b1.goutieres:
        u1 = goutiere.u_directeur_world().reshape((1, 2))
        barycentre_1 = goutiere.barycentre_world().reshape((1, 2))
        
        # On calcule le produit scalaire
        u = b2.numpy_array["u"]
        ps = np.abs(np.sum(u1* u, axis=1))

        # On calcule la distance du barycentre à la droite
        equation_droite = b2.numpy_array["equation_droite"]
        d_droite = np.abs(equation_droite[:,0]*barycentre_1[0,0] + equation_droite[:,1]*barycentre_1[0,1] + equation_droite[:,2]) / equation_droite[:,3]

        # Calcule de la distance entre les deux barycentres 
        barycentre = b2.numpy_array["barycentre"]
        d_max = b2.numpy_array["d_max"]
        distance = np.sqrt(np.sum((barycentre - barycentre_1)**2, axis=1))



        condition = np.where(np.logical_and(np.logical_and(ps > seuil_ps, d_droite <seuil_distance_droite_1), distance < d_max))
                
        if condition[0].shape[0] != 0:

            # Parmi les goutières qui restent, on prend celle pour laquelle la distance entre les deux barycentres est la plus petite
            barycentre_filtre_ps = barycentre[condition, :].squeeze()
            distance = np.sqrt(np.sum((barycentre_filtre_ps - barycentre_1)**2, axis=1))
            goutiere_homologue = b2.goutieres[condition[0][np.argmin(distance)]]


            goutiere_homologue.append_homologue_1(goutiere)
            goutiere.append_homologue_1(goutiere_homologue)


def deuxieme_appariement(b1:Bati, b2:Bati, dx, dy):
    b2.numpy_array_translation = b2.create_numpy_array(dx=dx, dy=dy)

    for goutiere in b1.goutieres:
        u1 = goutiere.u_directeur_world().reshape((1, 2))
        barycentre_1 = goutiere.barycentre_world().reshape((1, 2))
        
        # On calcule le produit scalaire
        u = b2.numpy_array_translation["u"]
        ps = np.abs(np.sum(u1* u, axis=1))

        # On calcule la distance du barycentre à la droite
        equation_droite = b2.numpy_array_translation["equation_droite"]
        d_droite = np.abs(equation_droite[:,0]*barycentre_1[0,0] + equation_droite[:,1]*barycentre_1[0,1] + equation_droite[:,2]) / equation_droite[:,3]
        
        # Calcule de la distance entre les deux barycentres 
        barycentre = b2.numpy_array_translation["barycentre"]
        d_max = b2.numpy_array_translation["d_max"]
        distance = np.sqrt(np.sum((barycentre - barycentre_1)**2, axis=1))

        condition = np.where(np.logical_and(np.logical_and(ps > seuil_ps, d_droite <seuil_distance_droite_2), distance < d_max))
                
        if condition[0].shape[0] != 0:

            # Parmi les goutières qui restent, on prend celle pour laquelle la distance entre les deux barycentres est la plus petite
            barycentre_filtre_ps = barycentre[condition, :].squeeze()
            distance = np.sqrt(np.sum((barycentre_filtre_ps - barycentre_1)**2, axis=1))
            goutiere_homologue = b2.goutieres[condition[0][np.argmin(distance)]]

            goutiere_homologue.append_homologue_2(goutiere)
            goutiere.append_homologue_2(goutiere_homologue)



def composante_connexe(b1, homologue_1=True):
    composantes_connexes = []

    
    for goutiere in b1.goutieres:
        if not goutiere.marque:
            liste_connexe = [goutiere]
            liste = [goutiere]
            goutiere.marque = True
            while len(liste) > 0:
                g = liste.pop()

                
                if homologue_1:
                    l = g.homologue_1
                else:
                    l = g.homologue_2
                for homologue in l:
                    if not homologue.marque:
                        homologue.marque = True
                        if homologue not in liste:
                            liste.append(homologue)
                        if homologue not in liste_connexe:
                            liste_connexe.append(homologue)
            
            if len(liste_connexe) >= 2:
                composantes_connexes.append(liste_connexe)
    
    return composantes_connexes


def distance(P0, P1):
    return np.sqrt((P0.x - P1.x)**2 + (P0.y - P1.y)**2)


def segments_meme_taille(composante_connexe):
    dictionnaire = {}
    for segment in composante_connexe:
        if segment.image not in dictionnaire.keys():
            dictionnaire[segment.image] = [segment]
        else:
            dictionnaire[segment.image].append(segment)
        
    if len(dictionnaire.keys()) != 2:
        print("Erreur dictionnaire : ", dictionnaire)
        return None   
    distance_minimale = 2
    couple_minimal = None
    for b in list(dictionnaire.values())[1]:
        for g in list(dictionnaire.values())[0]:
            difference = abs(b.get_longueur() - g.get_longueur())
            if difference < distance_minimale:
                distance_minimale = difference
                couple_minimal = [g, b]
    return couple_minimal
    


def calculer_translation(composantes_connexes):
    liste_dx = []
    liste_dy = []
    for composante_connexe in composantes_connexes:
        if len(composante_connexe) >= 3:
            composante_connexe_temp = segments_meme_taille(composante_connexe)
            if composante_connexe_temp is not None:
                composante_connexe = composante_connexe_temp
        if len(composante_connexe) == 2:
            g0 = composante_connexe[0]
            g1 = composante_connexe[1]
            if abs(g0.get_longueur()-g1.get_longueur()) < 2:
                P0 = g0.P0_sol()
                P1 = g0.P1_sol()

                
                if distance(P0, g1.P0_sol()) < distance(P0, g1.P1_sol()):
                    liste_dx.append(g1.P0_sol().x - P0.x)
                    liste_dx.append(g1.P1_sol().x - P1.x)
                    liste_dy.append(g1.P0_sol().y - P0.y)
                    liste_dy.append(g1.P1_sol().y - P1.y)
                else:
                    liste_dx.append(g1.P0_sol().x - P1.x)
                    liste_dx.append(g1.P1_sol().x - P0.x)
                    liste_dy.append(g1.P0_sol().y - P1.y)
                    liste_dy.append(g1.P1_sol().y - P0.y)

    if len(liste_dx) == 0:
        dx = 0
        dy = 0
    else:
        # On prend la médiane pour être moins sensible au bruit
        dx = statistics.median(liste_dx)
        dy = statistics.median(liste_dy)
    return dx, dy


def calculer_translation_save(composantes_connexes):
    liste_dx = []
    liste_dy = []
    # //TODO : mettre une contrainte sur la longueur des segments pour qu'ils aient à peu près la même taille ?
    for composante_connexe in composantes_connexes:
        if len(composante_connexe) == 2:
            g0 = composante_connexe[0]
            g1 = composante_connexe[1]
            P0 = g0.P0_sol()
            P1 = g0.P1_sol()

            if distance(P0, g1.P0_sol()) < distance(P0, g1.P1_sol()):
                liste_dx.append(g1.P0_sol().x - P0.x)
                liste_dx.append(g1.P1_sol().x - P1.x)
                liste_dy.append(g1.P0_sol().y - P0.y)
                liste_dy.append(g1.P1_sol().y - P1.y)
            else:
                liste_dx.append(g1.P0_sol().x - P1.x)
                liste_dx.append(g1.P1_sol().x - P0.x)
                liste_dy.append(g1.P0_sol().y - P1.y)
                liste_dy.append(g1.P1_sol().y - P0.y)

    if len(liste_dx) == 0:
        dx = 0
        dy = 0
    else:
        # On prend la médiane pour être moins sensible au bruit
        dx = statistics.median(liste_dx)
        dy = statistics.median(liste_dy)
    return dx, dy



def demarque_goutieres(bati):
    for goutiere in bati.goutieres:
        goutiere.marque = False
        goutiere.homologue_1 = []



def composante_connexe_bati(bati:List[Bati]):
    composantes_connexes = []
    for b in bati:
        for goutiere in b.goutieres:
            if not goutiere.marque:
                liste_connexe = [goutiere]
                liste = [goutiere]
                goutiere.marque = True
                while len(liste) > 0:
                    g = liste.pop()
                    for homologue in g.homologue_2:
                        if not homologue.marque:
                            homologue.marque = True
                            if homologue not in liste:
                                liste.append(homologue)
                            if homologue not in liste_connexe:
                                liste_connexe.append(homologue)
                
                if len(liste_connexe) >= 2:
                    composantes_connexes.append(liste_connexe)
    return composantes_connexes


def compute_correlation(rasterized_b1, rasterized_b2, centre_b1, centre_b2):
    n, m = rasterized_b2.shape
    patches = extract_patches_2d(rasterized_b1, (n, m))
    print(patches.shape)


                
def association(batis:List[List[Bati]], minimum_batiment=2):
    #On parcourt tous les groupes de bâtiments. Un groupe : ensemble de bâtiments ayant le même identifiant 
    id_segment = 0
    for bati in tqdm(batis):
        #S'il y a au moins deux bâtiments dans le groupe
        if len(bati) >= minimum_batiment:
            #On compare les bâtiments deux à deux s'ils sont issus de pvas différentes
            for i, b1 in enumerate(bati):
                for j in range(i+1, len(bati)):
                    b2 = bati[j]
                    # Il faut que les deux bâtiments ne soient pas issus de la même pva et qu'ils se recouvrent suffisamment en géométrie terrain
                    if b1.pva() != b2.pva() and b1.compute_IoU(b2)>0.5:

                        # On effectue un premier appariement avec une tolérance de 5 mètres sur la distance du barycentre à la goutière
                        # Les goutières de b1 sont associées à une seule goutière de b2, mais rien n'empêche une 
                        # goutière de b2 d'être apparié à plusieurs goutières de b1
                        premier_appariement(b1, b2)
                        # Même chose mais dans l'autre sens
                        premier_appariement(b2, b1)
                        # On rassemble les goutières qui sont connexes
                        composantes_connexes = composante_connexe(b1)
                        
                        # A partir des groupes connexes avec exactement deux goutières, on calcule une translation dx, dy de l'emprise au sol
                        dx, dy = calculer_translation(composantes_connexes)
                        
                        # Lors de la recherche des composantes connexes, on a eu besoin de marquer les goutières. Ici on les démarques
                        demarque_goutieres(b1)
                        demarque_goutieres(b2)
                        
                        # On effectue un deuxième appariement avec une tolérance beaucoup plus faible sur la distance du barycentre à la goutière
                        deuxieme_appariement(b1, b2, -dx, -dy)
                        deuxieme_appariement(b2, b1, dx, dy)

            # On rassemble les goutières qui sont connexes sur l'ensemble des bâtiments du groupe
            composantes_connexes = composante_connexe_bati(bati)
            
            # On affecte des identifiants : tous les segments connexes possèdent le même identifiant
            for cc in composantes_connexes:
                for goutiere in cc:
                    goutiere.id_chantier = id_segment
                id_segment += 1

def reorganiser_goutieres_par_shapefile(batis:List[List[Bati]]):
    dictionnaire = {}
    for bati in batis:
        for b in bati:
            pva = b.pva()
            if pva not in dictionnaire.keys():
                dictionnaire[pva] = []
            for goutiere in b.goutieres:
                dictionnaire[pva].append(goutiere)
    return dictionnaire



def sauvegarde(dictionnaire, output):
    for shapefile in dictionnaire.keys():
        geometries = []
        liste_id = []
        liste_id_bati = []
        liste_id_unique = []
        liste_voisin_1 = []
        liste_voisin_2 = []
        goutiere : Goutiere_image
        for goutiere in dictionnaire[shapefile]:
            if goutiere.id_chantier is not None:
                geometries.append(goutiere.get_image_geometry(superpose_pva=True))
                liste_id.append(goutiere.id_chantier)
                liste_id_bati.append(goutiere.id_bati)
                liste_id_unique.append(goutiere.id_unique)
                liste_voisin_1.append(goutiere.voisin_1.id_unique)
                liste_voisin_2.append(goutiere.voisin_2.id_unique)
            
        
        d = {"id": liste_id, "id_bati": liste_id_bati, "id_unique":liste_id_unique, "voisin_1":liste_voisin_1, "voisin_2":liste_voisin_2, "geometry": geometries}
        gdf = gpd.GeoDataFrame(d, crs="EPSG:2154")
        gdf.to_file(os.path.join(output, shapefile+".shp"))


def sauvegarde_projection(dictionnaire:Dict[str, Goutiere_image], output, save_voisin=True):
    for shapefile in dictionnaire.keys():
        geometries = []
        liste_id = []
        liste_id_bati = []
        liste_id_unique = []
        liste_voisin_1 = []
        liste_voisin_2 = []
        goutiere : Goutiere_image
        for goutiere in dictionnaire[shapefile]:
            if goutiere.id_chantier is not None:
                geometries.append(goutiere.get_projection())
                liste_id.append(goutiere.id_chantier)
                liste_id_bati.append(goutiere.id_bati)
                liste_id_unique.append(goutiere.id_unique)
                if save_voisin:
                    liste_voisin_1.append(goutiere.voisin_1.id_unique)
                    liste_voisin_2.append(goutiere.voisin_2.id_unique)
            
        if save_voisin:
            d = {"id": liste_id, "id_bati": liste_id_bati, "id_unique":liste_id_unique, "voisin_1":liste_voisin_1, "voisin_2":liste_voisin_2, "geometry": geometries}
        else:
            d = {"id": liste_id, "id_bati": liste_id_bati, "id_unique":liste_id_unique, "geometry": geometries}

        gdf = gpd.GeoDataFrame(d, crs="EPSG:2154")
        gdf.to_file(os.path.join(output, shapefile+"_projection.shp"))


def association_segments(shapefileDir, mnt_path, ta_xml, raf_path, output):
    if not os.path.exists(output):
        os.makedirs(output)

    mnt_path = get_mnt(mnt_path)
    ta_xml = get_ta_xml(ta_xml)
    raf_path = get_raf(raf_path)

    mnt = MNT(mnt_path)
    raf = RAF(raf_path)

    shots = get_shots(ta_xml, shapefileDir, raf)

    # Récupère l'identifiant maximum présent dans le bati
    liste_id, max_id = get_id_bati_max(shapefileDir)

    # Crée les goutières et les batis
    batis = create_goutieres(shots, max_id, mnt, shapefileDir)

    # Associe les segments des goutières entre eux
    association(batis)


    goutieres_par_shapefile = reorganiser_goutieres_par_shapefile(batis)

    sauvegarde_projection(goutieres_par_shapefile, output)

    sauvegarde(goutieres_par_shapefile, output)


if __name__=="__main__":

    parser = argparse.ArgumentParser(description="On associe le même identifiant à tous les segments représentant un même mur")
    parser.add_argument('--input', help='Répertoire où se trouve le résultat de association_bati')
    parser.add_argument('--mnt', help='Répertoire contenant le mnt sous format vrt')
    parser.add_argument('--ta_xml', help="Répertoire contenant le tableau d'assemblage sous format xml")
    parser.add_argument('--raf', help="Répertoire contenant la grille raf sous format tif")
    parser.add_argument('--output', help='Répertoire où sauvegarder les résultats')
    args = parser.parse_args()

    shapefileDir = args.input
    output = args.output
    mnt_path = args.mnt
    ta_xml = args.ta_xml
    raf_path = args.raf

    association_segments(shapefileDir, mnt_path, ta_xml, raf_path, output)

    