from typing import List
from v2.prediction import Prediction
from tqdm import tqdm
import geopandas as gpd
from v2.groupe_batiments import GroupeBatiments
import numpy as np
from v2.samon.infosResultats import InfosResultats
from v2.shot import MNT, RAF, Shot
from v2.parallelisation import compute_ground_geometrie, compute_estim_z
from concurrent.futures import ProcessPoolExecutor, as_completed

class AssociationBatimentEngine:

    """
    Algorithme pour associer les bâtiments entre eux
    """

    def __init__(self, predictions:List[Prediction], emprise:gpd.GeoDataFrame, pompei:bool, nb_cpus:int, pva_path:str, mnt:MNT, raf:RAF, shots:List[Shot]):
        self.predictions:List[Prediction] = predictions

        self.groupe_batiments:List[GroupeBatiments] = None

        self.emprise = emprise

        self.pompei = pompei

        self.nb_cpus = nb_cpus

        self.pva_path = pva_path
        self.mnt = mnt
        self.raf = raf
        self.shots = shots



    def run(self)->List[GroupeBatiments]:

        cs = int(len(self.predictions)/(10*self.nb_cpus)+1)
            
        with ProcessPoolExecutor(max_workers=self.nb_cpus) as executor:
            results = list(tqdm(
            executor.map(compute_ground_geometrie, self.predictions, chunksize=cs), 
            total=len(self.predictions),
            desc="Calcul des géométries terrain"
        ))
        self.predictions = results

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

                    groupe_batiments.append(GroupeBatiments(batis, self.pva_path, prediction.mnt, self.raf, self.shots, self.pompei))
        
        return groupe_batiments
    
    def get_mnt(self)->MNT:
        return self.predictions[0].mnt
    

    def compute_z_mean(self):
        """
        On calcule le z moyen de chaque groupe de bâtiment, et on met à jour la projection au sol des bâtiments
        """

        cs = int(len(self.groupe_batiments)/(10*self.nb_cpus)+1)
            
        with ProcessPoolExecutor(max_workers=self.nb_cpus) as executor:
            results = list(tqdm(
            executor.map(compute_estim_z, self.groupe_batiments, chunksize=cs), 
            total=len(self.groupe_batiments),
            desc="Estimation des hauteurs de bâtiment"
        ))

        self.groupe_batiments = results

        statistiques = {
            "Barycentre":0,
            "Points":0,
            "Samon":0,
            "Echec":0
        }

        for groupe in tqdm(self.groupe_batiments):
            statistiques[groupe.get_methode_estimation_hauteur()] += 1
            
        print("Méthode utilisée pour estimer la hauteur des bâtiments")
        for key, value in statistiques.items():
            print(f"{key} : {value}")

