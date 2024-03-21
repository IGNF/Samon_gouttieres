import os
import geopandas as gpd
from tqdm import tqdm
import argparse
import numpy as np
from goutiere import Goutiere_proj
from bati import BatiProjete
import random


parser = argparse.ArgumentParser(description="On trouve les 4 paramètres pour le recalage de la BD Uni sur la BD Ortho")
parser.add_argument('--input', help='Répertoire où se trouvent les résultats de association_segments_BD_UNI.py')
parser.add_argument('--output', help='Répertoire où sauvegarder les résultats')
args = parser.parse_args()


input = args.input
output = args.output

seuil = 1


def get_id_bati_max():
    liste_id = []
    max_id = 0
    shapefiles = [i for i in os.listdir(input) if i[-4:] == ".shp"]
    for shapefile in shapefiles:
        # On parcourt toutes les géométries présentes dans le shapefile 
        gdf = gpd.read_file(os.path.join(input, shapefile))
        for geometry in gdf.iterfeatures():
            id = geometry["properties"]["id_bati"]
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
    batis = [[] for i in range(max_id+1)]
    pvas = [i.split(".")[0] for i in os.listdir(input) if i[-4:]==".shp"]
    # On parcouirt toutes les pvas du ta
    for pva in pvas:
        batis_goutieres = [[] for i in range(max_id+1)]

        # On ouvre le fichier shapefile
        gdf = gpd.read_file(os.path.join(input, pva+".shp"))
                    
        # On parcourt les gouttières
        for geometry in gdf.iterfeatures():
            id = int(geometry["properties"]["id"])
            id_bati = int(geometry["properties"]["id_bati"])
            points = geometry["geometry"]["coordinates"]
            for i in range(len(points)-1):
                            
                world_line = np.array([[points[i][0], points[i][1], points[i][2]], [points[i+1][0], points[i+1][1], points[i+1][2]]])
                # On crée la goutière
                goutiere = Goutiere_proj(os.path.join(input, pva+".shp"), id, pva)
                            
                # On calcule les paramètres du plan passant par le sommet de prise de vue et la goutière
                goutiere.world_line = world_line
                goutiere.id_bati = id_bati
                            
            batis_goutieres[id_bati].append(goutiere)


        for k, goutieres in enumerate(batis_goutieres):
            if len(goutieres) > 0:
                batis[k].append(BatiProjete(goutieres))
        
    
    return batis



def separer_bati(batis):
    # On sépare les bâtiments en fonction de leur origine (bd uni ou bien reconstruction)
    batis_bd_uni = []
    batis_gouttieres = []
    for bati in batis:
        if "bd_uni" in bati.pva():
            batis_bd_uni.append(bati)
        else:
            batis_gouttieres.append(bati)
    return batis_bd_uni, batis_gouttieres

def get_gouttiere_selon_identifiant(batis_gouttieres, id):
    segments = []
    for segment in batis_gouttieres.goutieres:
        if segment.id == id:
            segments.append(segment)
    return segments


def in_liste(liste_points, couple):
    for points in liste_points:
        if couple[0] in points and couple[1] in points:
            return True
    return False
    


def creer_liste_points(batis_bd_uni, batis_gouttieres):
    liste_points = []
    # On parcourt les bâtiments de la BD Uni (idéalement il n'y en a qu'un seul)
    for b_bd_uni in batis_bd_uni:
        # On parcourt les gouttières du bâtiment
        for s_bd_uni in b_bd_uni.goutieres:
            # On parcourt les bâtiments trouvés
            for b_gouttiere in batis_gouttieres:
                # On récupère les gouttières qui possèdent le même identifiant que s_bd_uni
                s_gouttieres = get_gouttiere_selon_identifiant(b_gouttiere, s_bd_uni.id)
                for s_gouttiere in s_gouttieres:
                    # pour chaque couple  (s_gouttiere, s_bd_uni), on regroupe les extrémités ensemble et on ajoute à la liste de points
                    couple0, couple1 = s_bd_uni.p_proches(s_gouttiere)
                    if not in_liste(liste_points, couple0):
                        liste_points.append(couple0)
                    if not in_liste(liste_points, couple1):
                        liste_points.append(couple1)
    return liste_points


def analyse_residus(points, A, B, x_chap, V):
    """
    On calcule l'erreur moyenne sur les résidus, les résidus normalisés et le résidu maximal.
    Pour chaque point, on ajoute un champ résidu.
    """

    n = A.shape[0]
    sigma_0 = V.T @ V / (n - 4)
    try:
        var_V = sigma_0 * (np.eye(n) - A @ np.linalg.inv(A.T @ A) @ A.T)
        V_norm_2 = np.abs(V.squeeze()/np.sqrt(np.diag(var_V)))
        print("V_norm_2 : ", V_norm_2)    
        print("Nombre de points : ", len(points))
        print("Erreur moyenne : ", np.mean(np.abs(V)))
        print("residus max : ", np.max(np.abs(V)))
        return len(points), np.mean(np.abs(V)), np.max(np.abs(V)), np.max(V_norm_2), np.argmax(V_norm_2)
    except:
        return len(points), np.mean(np.abs(V)), np.max(np.abs(V)), None, np.argmax(np.abs(V))


def calculer_inliers(parametres, points, seuil):
    """
    On calcule le nombre d'inliers avec ces paramètres.
    Chaque ville ne peut être représentée qu'une seule fois dans les inliers
    """
    nb_inliers = 0
    inliers = []

    TX = parametres[0]
    TY = parametres[1]
    a = parametres[2]
    b = parametres[3]


    # On parcourt tous les points
    for point in points:
        # On calcule le résidu entre le résultat de la transformation et la position "réelle" des points
        XB_chap = TX + b*point[1].x + a*point[1].y
        YB_chap = TY - a*point[1].x + b*point[1].y
        distance = np.sqrt((XB_chap-point[0].x)**2 + (YB_chap-point[0].y)**2)
        
        # Si la distance est inférieure à un seuil, alors on conserve le point
        if distance <= seuil:
            nb_inliers += 1
            inliers.append(point)
    return nb_inliers, inliers


def compute_k(a, b):
    return np.sqrt(a**2 + b**2)

def ransac(points, iteration):
    """
    On applique un Ransac pour déterminer une première estimation des paramètres de la transformation de Helmert et supprimer les points faux
    """
    nb_inliers_max = 0
    diff_k_max = 1e15
    inliers_max = []

    # pour chaque itération
    for i in range(iteration):


        # On récupère deux points au hasard dans la liste
        indice_point1 = random.randint(0, len(points)-1)
        indice_point2 = random.randint(0, len(points)-1)
        while indice_point2==indice_point1:
            indice_point2 = random.randint(0, len(points)-1)
        point1 = points[indice_point1]
        point2 = points[indice_point2]

        # On met ces deux points sous la forme d'un tableau Numpy
        liste_numpy = []
        for point in [point1, point2]:
            new_line = [point[1].x, point[1].y, point[0].x, point[0].y]
            if new_line not in liste_numpy:
                liste_numpy.append(new_line)
        points_numpy = np.array(liste_numpy)
        
        # On calcule les paramètres via la méthode des moindres carrés
        parametres, _,_,_,_ = calculer_parametres_moindres_carres(points_numpy)

        # On calcule le nombre d'inliers à partir de ces paramètres
        nb_inliers, inliers = calculer_inliers(parametres, points, seuil)
        
        # On calcule k, le facteur d'échelle
        k = compute_k(parametres[2], parametres[3])
        # On impose que k soit compris entre 0.8 et 1.2
        if abs(1-k) < 0.2:
            # On conserve cette transformation dans le cas où le nombre d'inliers trouvés est strictement supérieur au maximum précédent
            # En cas d'égalité, on conserve la transformation avec le facteur d'échelle le plus proche de 1
            if nb_inliers > nb_inliers_max or (nb_inliers==nb_inliers_max and abs(1-k) < diff_k_max):
                nb_inliers_max = nb_inliers
                diff_k_max = abs(1-k)
                inliers_max = inliers

    return inliers_max


def build_A_B(points_numpy):
    n = points_numpy.shape[0]
    A = np.zeros((n*2, 4))
    B = np.zeros((n*2, 1))

    for i in range(n):
        A[2*i,0] = 1
        A[2*i,2] = points_numpy[i,1]
        A[2*i,3] = points_numpy[i,0]
        A[2*i+1,1] = 1
        A[2*i+1,2] = -points_numpy[i,0]
        A[2*i+1,3] = points_numpy[i,1]
        B[2*i,0] = points_numpy[i,2]
        B[2*i+1,0] = points_numpy[i,3]

    return A, B


def calculer_parametres_moindres_carres(points_numpy):
    """
    Calcule des paramètres à l'aide de la méthode des moindres carrés (https://v-assets.cdnsw.com/fs/Cours_techni/e1v0b-Adaptation_Helmert.pdf)
    Utilisé pour les moindres carrés
    """

    # On construit les matrices A et B
    A, B = build_A_B(points_numpy)

    # On résout le système
    x_chap, res, _, _ = np.linalg.lstsq(A, B, rcond=None)
    
    V = B - A @ x_chap
    TX = x_chap[0,0]
    TY = x_chap[1,0]
    a = x_chap[2,0]
    b = x_chap[3,0]
    return [TX, TY, a, b], A, B, x_chap, V



def moindres_carres(liste_points):
    suppression = True
    nb_points, mean, res_max = 0,0,0
    
    
    parametres = [None, None, None, None]
    # On itère tant qu'il reste au moins deux points et qu'une suppression d'un point a été effectuée
    while len(liste_points) > 2 and suppression==True:
        suppression = False
        
        # On met les points sous format d'un tableau Numpy
        liste_numpy = []
        for points in liste_points:
            new_line = [points[1].x, points[1].y, points[0].x, points[0].y]
            if new_line not in liste_numpy:
                liste_numpy.append(new_line)
        points_numpy = np.array(liste_numpy)

        
        # On calcule les paramètres avec la méthode des moindres carrés
        parametres, A, B, x_chap, V = calculer_parametres_moindres_carres(points_numpy)

        # On analyse les résidus
        nb_points, mean, res_max, res_norm_max, res_argmax = analyse_residus(liste_points, A, B, x_chap, V)
        # Si un des résidus normalisés est supérieur à 2, alors on supprime le point
        if res_norm_max > 2:
            suppression = True
            print("On supprime le point {}".format(res_argmax))
            del(liste_points[res_argmax//2])
    return parametres, nb_points, mean, res_max


def compute_recalage(batis):
    """
    batis est une liste de bâtiments qui proviennent de la BD Uni ou de la reconstruction
    """

    # On sépare les bâtiments contenus dans batis en fonction de leur origine
    batis_bd_uni, batis_gouttieres = separer_bati(batis)
    # On crée une liste de points à partir desquels on va calculer la transformation
    liste_points = creer_liste_points(batis_bd_uni, batis_gouttieres)
    # Avec du ransac, on supprime les points faux
    liste_points = ransac(liste_points, 100)
    # Avec les points restants, on calcule la transformation avec la méthode des moindres carrés
    parametres, nb_points, mean, res_max = moindres_carres(liste_points)
    if parametres is not None:
        for bati in batis_bd_uni:
            bati.parametres_recalage = parametres
            bati.nb_points = nb_points
            bati.mean = mean
            bati.res_max = res_max
    return batis_bd_uni


    
def sauvegarde_projection(batis_bd_uni):
    id = []
    polygones = []
    TX = []
    TY = []
    a = []
    b = []
    nb_points = []
    mean = []
    res_max = []
    for i, bati in enumerate(batis_bd_uni):
        
        polygones.append(bati.linestring())
        id.append(i)
        TX.append(bati.parametres_recalage[0])
        TY.append(bati.parametres_recalage[1])
        a.append(bati.parametres_recalage[2])
        b.append(bati.parametres_recalage[3])
        nb_points.append(bati.nb_points)
        mean.append(bati.mean)
        res_max.append(bati.res_max)

        d = {"id": id, "TX":TX, "TY":TY, "a":a, "b":b, "nb_points":nb_points, "mean":mean, "res_max":res_max,  "geometry": polygones}
        gdf = gpd.GeoDataFrame(d, crs="EPSG:2154")
        gdf.to_file(os.path.join(output, "recalage.shp"))



if not os.path.exists(output):
    os.makedirs(output)


# Récupère l'identifiant maximum présent dans le bati
liste_id, max_id = get_id_bati_max()
batis = create_goutieres(max_id)

batis_bd_uni = []

# On parcourt les bâtiments
for bati in tqdm(batis):

    if len(bati) >= 2:
        print("")
        print("")
        # On calcule le recalage
        bati_bd_uni = compute_recalage(bati)
        for b in bati_bd_uni:
            
            batis_bd_uni.append(b)

sauvegarde_projection(batis_bd_uni)

