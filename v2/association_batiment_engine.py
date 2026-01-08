from typing import List
from v2.prediction import Prediction
from tqdm import tqdm
import geopandas as gpd
from v2.groupe_batiments import GroupeBatiments
import numpy as np
from v2.samon.monoscopie import Monoscopie
from v2.samon.infosResultats import InfosResultats
from v2.shot import MNT

class AssociationBatimentEngine:

    """
    Algorithme pour associer les bâtiments entre eux
    """

    def __init__(self, predictions:List[Prediction], monoscopie:Monoscopie, emprise:gpd.GeoDataFrame, pompei:bool):
        self.predictions:List[Prediction] = predictions
        self.monoscopie:Monoscopie = monoscopie

        self.groupe_batiments:List[GroupeBatiments] = None

        self.emprise = emprise

        self.pompei = pompei



    def run(self)->List[GroupeBatiments]:
        print("Calcul des géométries terrain")
        # On projette chaque prédiction du FFL sur le MNT
        for prediction in tqdm(self.predictions):
            prediction.compute_ground_geometry()

        if self.emprise is not None:
            print("On ne conserve que les bâtiments à l'intérieur de l'emprise")
            for prediction in tqdm(self.predictions):
                prediction.check_in_emprise(self.emprise)

        
        print("Calcul des géoséries")
        # Pour chaque prédictions du FFL, on crée des tableaux numpy qui permettront d'accélérer le calcul pour associer des bâtiments
        for prediction in tqdm(self.predictions):
            prediction.create_geodataframe()

        print("Calcul des associations")
        # Pour chaque bâtiment, on cherche sur les autres prédictions le bâtiment avec lequel il se superpose le plus
        self.association()

        # On crée le graphe connexe qui regroupe tous les bâtiments qui ont été associés
        self.groupe_batiments = self.graphe_connexe()

        print("Calcul du z moyen du bâtiment")
        # On calcule une estimation de la hauteur du bâtiment
        self.compute_z_mean()


        groupes_batiments_2 = []
        print("Division des grands groupes de bâtiments")
        for groupe_batiment in tqdm(self.groupe_batiments):
            batiments = groupe_batiment.get_batiments()
            if len(batiments)>100:
                for batiment in batiments:
                    batiment.init()
                groupe_batiment.estim_z = None
                groupe_batiment.nb_images_z_estim = None
            else:
                groupes_batiments_2.append(groupe_batiment)
            
        print("Calcul des géoséries des grands groupes de bâtiments")
        for prediction in tqdm(self.predictions):
            prediction.create_geodataframe()

        print("Calcul des associations des grands groupes de bâtiments")
        # Pour chaque bâtiment, on cherche sur les autres prédictions le bâtiment avec lequel il se superpose le plus
        self.association()

        # On crée le graphe connexe qui regroupe tous les bâtiments qui ont été associés
        groupes_batiments_2 += self.graphe_connexe()
        self.groupe_batiments = groupes_batiments_2
        
        print("Calcul du z moyen des grands groupes de bâtiments")
        # On calcule une estimation de la hauteur du bâtiment
        self.compute_z_mean()


        return self.groupe_batiments
    

    def init(self):
        self.groupe_batiments = []
        
        for prediction in tqdm(self.predictions):
            prediction.delete_homol()



    def association(self):
        # On parcourt les shapefile
        for prediction_1 in tqdm(self.predictions):
            
            # On parcourt les autres shapefile
            for prediction_2 in self.predictions:
                if prediction_1!=prediction_2:
                    # On récupère la géosérie du deuxième shapefile
                    geoserie_1:gpd.GeoDataFrame = prediction_1.get_geodataframe().geometry
                    geoserie_2:gpd.GeoDataFrame = prediction_2.get_geodataframe().geometry

                    if geoserie_1.shape[0]==0 or geoserie_2.shape[0]==0:
                        continue

                    # On récupère les intersections entre les géométries terrain des bâtiments
                    intersections = geoserie_2.sindex.query(geoserie_1, predicate="intersects")

                    for i in range(geoserie_1.shape[0]):
                        
                        # Pour chaque bâtiment, on récupère parmi les bâtiments qu'il intersecte celui avec lequel il partage la plus grande aire
                        bati_1 = prediction_1.get_batiment_i(i)
                        
                        bati_1_emprise = bati_1.get_geometrie_terrain()
                        area_max = 0
                        id_max = None

                        indices = np.where(intersections[0,:]==i)[0]
                        for j in range(indices.shape[0]):
                            indice = indices[j]                                
                            bati_2_emprise = prediction_2.get_batiment_i(intersections[1,indice])
                            aire_commune = bati_1_emprise.intersection(bati_2_emprise.get_geometrie_terrain()).area
                            if aire_commune > area_max:
                                area_max = aire_commune
                                id_max = bati_2_emprise
                        if id_max is not None:
                            bati_1.add_homologue(id_max)
                            id_max.add_homologue(bati_1)


    def graphe_connexe(self)->List[GroupeBatiments]:
        """
        On réunit tous les bâtiments qui représentent un même bâtiment dans la réalité
        """
        groupe_batiments = []
        for prediction in self.predictions:
            for bati in prediction.get_batiments():
                if not bati._marque:
                    batis = [bati]
                    liste = [bati]
                    bati._marque = True

                    while len(liste) > 0:
                        b = liste.pop()
                        for homologue in b.get_homologues():
                            if not homologue._marque:
                                homologue._marque = True
                                if homologue not in liste:
                                    batis.append(homologue)
                                    liste.append(homologue)

                    
                    groupe_batiments.append(GroupeBatiments(batis))
        
        return groupe_batiments
    
    def get_mnt(self)->MNT:
        return self.predictions[0].mnt
    

    def compute_z_mean_samon(self, dictionnaires, nb_shots:int):
        """
        On calcule tous les points contenus dans dictionnaire avec Samon. On s'arrête dès qu'un point semble satisfaisant (suffisamment d'images utilisées pour le calculer)
        """
        for i, dictionnaire in enumerate(dictionnaires):
            if i > 4:
                break
            infos_resultats:InfosResultats = self.monoscopie.run(dictionnaire["point"], dictionnaire["shot"])
            if infos_resultats.reussi:
                if nb_shots >=3 and infos_resultats.nb_images<3:
                    continue 
                else:
                    point_3d = infos_resultats.point3d
                    return point_3d[2], infos_resultats.nb_images
        return None, None
    

    def compute_z_mean(self):
        """
        On calcule le z moyen de chaque groupe de bâtiment, et on met à jour la projection au sol des bâtiments
        """

        statistiques = [0,0,0,0]

        for groupe in tqdm(self.groupe_batiments):
            if len(groupe.batiments)<=1:
                continue
            if groupe.estim_z is not None:
                continue
            estim_z = groupe.compute_z_mean()
            if estim_z is not None:
                groupe.estim_z = estim_z
                statistiques[0]+=1
                groupe.set_methode_estimation_hauteur("Barycentre")
            
            
            else:

                # Estimation rapide de la hauteur du bâtiment, seulement dans le cas de Pompei
                if self.pompei:
                    estim_z, nb_points = groupe.compute_z_mean_v2()
                else:
                    nb_points = 0
                
                # Si on n'est pas parvenu à avoir une estimation du z avec la méthode rapide
                if nb_points!=0:
                    groupe.estim_z = estim_z
                    groupe.nb_images_z_estim = nb_points
                    statistiques[1]+=1
                    groupe.set_methode_estimation_hauteur("Points")
                else:
                    # On récupère tous les points qui se trouvent sur le bâtiment
                    # Pour cela, sur chaque polygone issus de pvas différentes, on applique un buffer de -2 mètres et on récupère tous les sommets du polygones
                    dictionnaires = groupe.get_point_samon()
                    # On récupère une estimation de la hauteur du bâtiment
                    z_mean, nb_images = self.compute_z_mean_samon(dictionnaires, groupe.get_nb_shots())
                    #z_mean, nb_images = 10, -1 # Cette ligne est utile pour les tests si on ne veut pas utiliser Samon qui rallonge sensiblement les calculs
                    if z_mean is not None:
                        groupe.estim_z = z_mean
                        groupe.nb_images_z_estim = nb_images
                        groupe.set_methode_estimation_hauteur("Samon")
                        statistiques[2]+=1
                    else:
                        # Si cela n'a pas marché, alors on fixe arbitrairement la hauteur du bâtiment à 10 mètres
                        centroid = groupe.batiments[0].geometrie_terrain.centroid
                        z = groupe.batiments[0].mnt.get(centroid.x, centroid.y)+10
                        groupe.estim_z = z
                        groupe.nb_images_z_estim = -1
                        groupe.set_methode_estimation_hauteur("Echec")
                        statistiques[3]+=1
                    
            
            groupe.update_geometry_terrain()
        print("Méthode utilisée pour estimer la hauteur des bâtiments")
        print("Barycentre : ", statistiques[0])
        print("Points : ", statistiques[1])
        print("Samon : ", statistiques[2])
        print("Echec : ", statistiques[3])


