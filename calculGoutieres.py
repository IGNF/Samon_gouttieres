from pysocle.photogrammetry.ta import Ta
import os
from goutiere import Goutiere, Goutiere_image
import numpy as np
from typing import List
import geopandas
from shapely import LineString
import geopandas as gpd
from goutiereChantier import GoutiereChantier
from tqdm import tqdm

class CalculGoutieres:

    def __init__(self, ta_xml: str, shapefileDir: str, mnt: str, raf: str, pva:str, resultats:str, save_points_cloud=True) -> None:
        """
        ta_xml : tableau d'assemblage de la prise de vue
        shapefileDir : répertoire contenant les shapefiles par pvas avec les goutières sur chaque pva
        mnt : modèle numérique de terrain de la zone
        raf : grille raf
        pva : répertoire contenant les pvas
        resultats : répertoire où enregistrer les résultats
        save_points_cloud : sauvegarder les goutières sous format xyz (dans self.resultats/goutieres.xyz)

        Dans les fichiers shapefile, les segments représentant une même goutière doivent avoir le même id
        
        """
        
        self.ta_xml = ta_xml
        self.shapefileDir = shapefileDir
        self.mnt = mnt
        self.raf = raf
        self.pva = pva
        self.resultats = resultats
        self.liste_id = None
        self.save_points_cloud = save_points_cloud
        self.path_saved_points_cloud = os.path.join(self.resultats, "goutieres.xyz")

        #On supprime le fichier où sauvegarder les goutières sous forme de nuage de points
        if os.path.exists(self.path_saved_points_cloud):
            os.remove(self.path_saved_points_cloud)

        self.goutieres:List[Goutiere] = []

        # On charge le tableau d'assemblage avec PySocle
        self.ta = Ta.from_xml(self.ta_xml)
        print("Fichier xml chargé")

        # On ajoute le mnt à Pysocle
        self.ta.project.add_dem(self.mnt)
        print("MNT ajouté")

        # Dans les fichiers TA, ce sont des hauteurs ellipsoïdales. Il faut les convertir en altitude
        self.ta.project.conversion_elevation(self.raf, "a")

        # On récupère la liste des identifiants et l'identifiant maximum de goutières qui existent dans les différents shapefiles
        self.liste_id, self.max_id, self.max_id_unique = self.get_id()

    
    def get_id(self):
        """
        Récupère la liste des identifiants de goutières qui existent dans les différents shapefiles, ainsi que l'identifiant maximum
        """
        liste_id = []
        max_id = 0
        max_id_unique = 0
        shapefiles = [i for i in os.listdir(self.shapefileDir) if i[-4:] == ".shp"]
        # On parcourt les shapefiles
        for shapefile in shapefiles:
            # On parcourt toutes les géométries présentes dans le shapefile 
            gdf = gpd.read_file(os.path.join(self.shapefileDir, shapefile))
            for geometry in gdf.iterfeatures():
                id = geometry["properties"]["id"]
                id_unique = geometry["properties"]["id_unique"]
                if id != -1:
                    # Si l'id n'est pas dans la liste, alors on l'ajoute
                    if id not in liste_id:
                        liste_id.append(id)
                        max_id = max(max_id, id)
                max_id_unique = max(max_id_unique, id_unique)
        return liste_id, max_id, max_id_unique

    def sauvegarde(self, id, distance_moyenne, nb_plans, geometry, x1, y1, z1, x2, y2, z2, nb_plans_init, id_batiment, dict_voisins):
        """
        On sauvegarde les goutières dans un fichier shapefile
        Pour chaque goutière, on enregistre :
        - la distance moyenne entre les droites des goutières avec les faisceaux
        - le nombre de plans qui ont servi à déterminer les paramètres de la droite
        - l'altitude des deux extrémités
        """
        d = {"id": id, "dist_mean": distance_moyenne, "nb_plans": nb_plans, "x1": x1, "y1": y1, "z1": z1, "x2":x2, "y2":y2, "z2": z2, "nb_plans_init":nb_plans_init, "id_bati":id_batiment, "geometry": geometry}
        for key in dict_voisins.keys():
            d[key] = dict_voisins[key]
        gdf = geopandas.GeoDataFrame(d, crs="EPSG:2154")
        gdf.to_file(os.path.join(self.resultats, "goutiere.shp"))


    def charger_goutieres(self):
        """
        Crée un objet goutière pour chaque objet présent dans un des fichiers shapefiles 
        """
        pvas = [i.split(".")[0] for i in os.listdir(self.shapefileDir)]

        # liste contient n listes vides avec n = nombre maximum d'identifiant
        liste = [[] for i in range(self.max_id+1)]

        liste_id_unique = [[] for i in range(self.max_id_unique+1)]

        # On parcourt tous les shots du ta
        for flight in self.ta.project.get_flights():
            for strip in flight.get_strips():
                for shot in strip.get_shots():
                    # Si pour le shot, on a un fichier shapefile de goutières
                    if shot.image in pvas:
                        # On parcourt toutes les géométries du fichier shapefile
                        gdf = gpd.read_file(os.path.join(self.shapefileDir, shot.image+".shp"))
                        for geometry in gdf.iterfeatures():
                            # On crée un objet goutière
                            id = int(geometry["properties"]["id"])
                            if id != -1:
                                coordinates = geometry["geometry"]["coordinates"]
                                image_line = np.array([[coordinates[0][0], -coordinates[0][1]], [coordinates[1][0], -coordinates[1][1]]])       
                                goutiere = Goutiere_image(shot, os.path.join(self.shapefileDir, shot.image+".shp"), self.ta.project.dem, id)
                                goutiere.set_image_line(image_line, compute_equation_plan=True)
                                goutiere.id_bati = geometry["properties"]["id_bati"]
                                id_unique = geometry["properties"]["id_unique"]
                                goutiere.id_unique = id_unique
                                goutiere.voisin_1 = geometry["properties"]["voisin_1"]
                                goutiere.voisin_2 = geometry["properties"]["voisin_2"]
                                # On ajoute la goutière dans la liste à la position de son id
                                liste[id].append(goutiere)
                                #print(id_unique, len(liste_id_unique))
                                liste_id_unique[id_unique].append(goutiere)
        return liste, liste_id_unique
                        



    def run(self):

        liste_id = []
        distance_moyenne = []
        nb_plans = []
        geometry = []
        x1 = []
        y1 = []
        z1 = []
        x2 = []
        y2 = []
        z2 = []

        dict_voisins = {}
        for i in range(8):
            dict_voisins["v_{}".format(i)] = []

        nb_plans_init = []
        id_batiment = []

        chantiers, liste_id_unique = self.charger_goutieres()

        # On parcourt tous les id présents dans les shapefile
        for chantier_goutieres in tqdm(chantiers):
            if len(chantier_goutieres) >= 2:
                print("")
                print("")
                id = chantier_goutieres[0].id
                print("Chantier {}".format(id))
                # On crée un objet chantier
                chantier = GoutiereChantier(id, self.ta, self.shapefileDir, chantier_goutieres, methode="grand")
                nb_plans_initiaux = len(chantier.goutieres)
                # On calcule l'intersection des segments par moindres carrés
                chantier.moindres_carres()

                # On calcule les extrémités de la droite ainsi que la distance moyenne entre la droite et les faisceaux (sommet de prise de vue, extrémité de chaque segment)
                chantier.distance_moyenne()

                # On récupère l'identifiant des chantiers voisins
                voisins = chantier.get_voisins(liste_id_unique)

                

                if len(chantier.goutieres) >= 2:

                    # On enregistre les résultats dans un fichier shapefile
                    nb_plans_init.append(nb_plans_initiaux)
                    liste_id.append(id)
                    distance_moyenne.append(chantier.d_mean)
                    nb_plans.append(len(chantier.goutieres))
                    x1.append(chantier.p1[0,0])
                    y1.append(chantier.p1[1,0])
                    z1.append(chantier.p1[2,0])
                    x2.append(chantier.p2[0,0])
                    y2.append(chantier.p2[1,0])
                    z2.append(chantier.p2[2,0])
                    id_batiment.append(chantier.goutieres[0].id_bati)

                    for i in range(8):
                        if i < len(voisins):
                            dict_voisins["v_{}".format(i)].append(voisins[i])
                        else:
                            dict_voisins["v_{}".format(i)].append(None)
                    
                    geometry.append(LineString([
                        (chantier.p1[0,0], chantier.p1[1,0]), 
                        (chantier.p2[0,0], chantier.p2[1,0])]))
                    
                    # On sauvegarde les résultats dans un fichier xyz
                    if self.save_points_cloud:
                        chantier.save_points_cloud(self.path_saved_points_cloud)
        
        # On enregistre le résultat dans un fichier shapefile
        self.sauvegarde(liste_id, distance_moyenne, nb_plans, geometry, x1, y1, z1, x2, y2, z2, nb_plans_init, id_batiment, dict_voisins)


        







