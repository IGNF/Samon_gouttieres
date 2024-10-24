import os
import geopandas as gpd
from tqdm import tqdm
from bati import Bati
import argparse
from tools import get_mnt, get_raf, get_ta_xml, get_shots
from shot import MNT, RAF


def charger_emprise(chemin_emprise):
    gdf = None
    if chemin_emprise != "None" and chemin_emprise is not None:
        gdf = gpd.read_file(chemin_emprise).geometry
    return gdf



def create_goutieres(shots, emprise, mnt, shapefileDir):
    """
    On retire de la liste des shots tous les shots dont les pvas correspondantes sont manquantes
    """
    batis_par_shapefile = []
    pvas = [i.split(".")[0] for i in os.listdir(shapefileDir)]
    # On parcourt toutes les pvas du ta
    for shot in shots:
        # Si pour la pva on a un fichier shapefile avec des goutières :
        if shot.image in pvas:
            print("Chargement de l'image {}".format(shot.image))

            batis = []
            # On ouvre le fichier shapefile
            gdf = gpd.read_file(os.path.join(shapefileDir, shot.image+".shp"))
            # On parcourt les géométries
            for feature in tqdm(gdf.iterfeatures()):
                # On parcourt les points de la géométrie
                id = int(feature["properties"]["id"])

                bati = Bati(id, feature["geometry"], shot, mnt, compute_gouttiere=False)

                # Si une emprise a été définie, alors on ajoute le bâtiment seulement s'il est à l'intérieur de l'emprise
                if emprise is not None and bati.emprise_sol() is not None:
                    if bati.emprise_sol().within(emprise).any():
                        batis.append(bati)
                                
                else:
                    batis.append(bati)

            # Dans goutieres_par_shapefile, les goutières sont stockées par shapefile  
            batis_par_shapefile.append({"shapefile":shot.image, "batis":batis})                            
    
    return batis_par_shapefile


def construire_geoseries(batis_par_shapefile):
    """
    Pour chaque image, on construit une géosérie contenant les emprises au sol des bâtiments.
    Cela facilitera la recherche d'intersection pour la suite.
    """
    geoseries = {}
    for shapefile in batis_par_shapefile:
        geometries = []
        for bati in shapefile["batis"]:
            if bati.emprise_sol() is not None:
                geometries.append(bati.emprise_sol())

        if len(geometries) > 0:
            geoseries[shapefile["shapefile"]] = gpd.GeoSeries(geometries)

    return geoseries


def association(batis_par_shapefile, geoseries):
    # On parcourt les shapefile
    for shapefile in batis_par_shapefile:
        print(shapefile["shapefile"])
        # On parcourt les bâtiments d'un shapefile
        
        # On parcourt les autres shapefile
        for s2 in batis_par_shapefile:
            if s2["shapefile"] != shapefile["shapefile"] and s2["shapefile"] in geoseries.keys():
                # On récupère la géosérie du deuxième shapefile
                geoserie_1:gpd.GeoSeries = geoseries[s2["shapefile"]]
                geoserie_0:gpd.GeoSeries = geoseries[shapefile["shapefile"]]

                intersections = geoserie_0.sindex.query(geoserie_1, predicate="intersects")

                for i in tqdm(range(geoserie_1.shape[0])):
                    bati_1:Bati = s2["batis"][i]
                    bati_1_emprise = bati_1.emprise_sol()
                    area_max = 0
                    id_max = None
                    for j in range(intersections.shape[1]):# On pourrait gagner du temps en faisant un np.where pour n'itérer que sur les cases intéressantes ?
                        if intersections[0,j]==i:
                            
                            bati_2_emprise:Bati = shapefile["batis"][intersections[1,j]]
                            aire_commune = bati_1_emprise.intersection(bati_2_emprise.emprise_sol()).area
                            if aire_commune > area_max:
                                area_max = aire_commune
                                id_max = bati_2_emprise
                    if id_max is not None:
                        bati_1.add_homologue(id_max)
                        id_max.add_homologue(bati_1) 
                             

def graphe_connexe(batis_par_shapefile):
    id_bati = 0
    for shapefile in batis_par_shapefile:
        bati : Bati
        for bati in tqdm(shapefile["batis"]):
            if not bati.marque:
                batis = [bati]
                liste = [bati]
                bati.id = id_bati
                bati.marque = True

                while len(liste) > 0:
                    b = liste.pop()
                    for homologue in b.homologue:
                        if not homologue.marque:
                            homologue.id = id_bati
                            homologue.marque = True
                            if homologue not in liste:
                                batis.append(homologue)
                                liste.append(homologue)

                Bati.mean_z_estim_v2(batis)
                id_bati += 1
                            


def sauvegarde_image(batis_par_shapefile, output):
    for shapefile in batis_par_shapefile:
        id = []
        polygones = []
        estim_z = []
        scores = []
        distances = []
        bati : Bati
        for bati in tqdm(shapefile["batis"]):
            polygones.append(bati.emprise_image())
            
            id.append(bati.id)
            estim_z.append(bati.estim_z_finale)
            scores.append(bati.score)
            distances.append(bati.dist_finale)

        if len(id) == 0:
            print("pas de géométrie conservée pour l'image {}".format(shapefile["shapefile"]))
        else:
            d = {"id": id, "geometry": polygones, "estim_z":estim_z, "score":scores, "distance":distances}
            gdf = gpd.GeoDataFrame(d, crs="EPSG:2154")
            gdf.to_file(os.path.join(output, shapefile["shapefile"]+".shp"))


def sauvegarde_projection(batis_par_shapefile, output):
    for shapefile in batis_par_shapefile:
        id = []
        polygones = []
        estim_z = []
        scores = []
        distances = []
        bati : Bati
        for bati in tqdm(shapefile["batis"]):
            polygones.append(bati.emprise_sol())
            
            id.append(bati.id)
            estim_z.append(bati.estim_z_finale)
            scores.append(bati.score)
            distances.append(bati.dist_finale)

        if len(id) == 0:
            print("pas de géométrie conservée pour l'image {}".format(shapefile["shapefile"]))
        else:
            d = {"id": id, "geometry": polygones, "estim_z":estim_z, "score":scores, "distance":distances}
            gdf = gpd.GeoDataFrame(d, crs="EPSG:2154")
            gdf.to_file(os.path.join(output, shapefile["shapefile"]+"_projection.shp"))


def association_bati(shapefileDir, mnt_path, ta_xml, raf_path, chemin_emprise, output):

    if not os.path.exists(output):
        os.makedirs(output)

    mnt_path = get_mnt(mnt_path)
    ta_xml = get_ta_xml(ta_xml)
    raf_path = get_raf(raf_path)
    
    mnt = MNT(mnt_path)
    raf = RAF(raf_path)

    
    shots = get_shots(ta_xml, shapefileDir, raf)    
   

    # On charge l'emprise du chantier
    emprise = charger_emprise(chemin_emprise)

    # On crée les objets gouttières à partir des segments
    batis_par_shapefile = create_goutieres(shots, emprise, mnt, shapefileDir)
    print("Gouttières créées")

    # On construit pour chaque image une géosérie des bâtiments afin de faciliter la recherche d'intersections
    geoseries = construire_geoseries(batis_par_shapefile)
    print("géoséries créées")

    # On associe les bâtiments entre eux
    association(batis_par_shapefile, geoseries)
    print("Association terminée")

    # On établit un graphe connexe sur la relation : "je suis connecté au voisin avec lequel je partage la plus grande surface"
    graphe_connexe(batis_par_shapefile)
    print("Graphe connexe établi")

    # On sauvegarde les bâtiments en projection image et en projection terrain
    sauvegarde_image(batis_par_shapefile, output)
    sauvegarde_projection(batis_par_shapefile, output)



if __name__=="__main__":

    parser = argparse.ArgumentParser(description="On associe le même identifiant à tous les polygones représentant un même bâtiment")
    parser.add_argument('--input', help='Répertoire où se trouvent les géométries nettoyées')
    parser.add_argument('--mnt', help='Répertoire contenant le mnt sous format vrt')
    parser.add_argument('--ta_xml', help="Répertoire contenant le tableau d'assemblage sous format xml")
    parser.add_argument('--raf', help="Répertoire contenant la grille raf sous format tif")
    parser.add_argument('--emprise', help="Répertoire contenant la grille raf sous format tif", default=None)
    parser.add_argument('--output', help='Répertoire où sauvegarder les résultats')
    args = parser.parse_args()

    shapefileDir = args.input
    output = args.output
    mnt_path = args.mnt
    ta_xml = args.ta_xml
    raf_path = args.raf
    chemin_emprise = args.emprise

    association_bati(shapefileDir, mnt_path, ta_xml, raf_path, chemin_emprise, output)

    