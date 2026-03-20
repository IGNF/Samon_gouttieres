from typing import List
from v2.prediction import Prediction
from tqdm import tqdm
import geopandas as gpd
from v2.groupe_pate_maisons import GroupePatesMaisons
import numpy as np
from concurrent.futures import ProcessPoolExecutor
from v2.parallelisation import compute_pate_maison_ground_geometrie
import multiprocessing

class AssociationPateMaisonEngine:

    """
    Algorithme pour associer les bâtiments entre eux
    """

    def __init__(self, predictions:List[Prediction], emprise:gpd.GeoDataFrame, nb_cpus:int):
        self.predictions:List[Prediction] = predictions
        self.groupe_pates_maisons:List[GroupePatesMaisons] = None
        self.emprise = emprise
        self.nb_cpus = nb_cpus




    def run(self)->List[GroupePatesMaisons]:

        cs = int(len(self.predictions)/(10*self.nb_cpus)+1)
            
        with multiprocessing.Pool(processes=self.nb_cpus) as pool:
            results = list(tqdm(
            pool.imap_unordered(compute_pate_maison_ground_geometrie, self.predictions, chunksize=cs), 
            total=len(self.predictions),
            desc="Calcul des géométries terrain"
        ))        
        self.predictions = results

        if self.emprise is not None:
            print("On ne conserve que les bâtiments à l'intérieur de l'emprise")
            for prediction in tqdm(self.predictions, desc="Filtrage des pâtés de maisons par emprise terrain"):
                prediction.check_in_emprise_pate_maisons(self.emprise)

        
        print("Calcul des géoséries")
        # Pour chaque prédictions du FFL, on crée des tableaux numpy qui permettront d'accélérer le calcul pour associer des bâtiments
        for prediction in tqdm(self.predictions):
            prediction.create_geodataframe_pates_maisons()

        print("Calcul des associations")
        # Pour chaque bâtiment, on cherche sur les autres prédictions le bâtiment avec lequel il se superpose le plus
        self.association()

        # On crée le graphe connexe qui regroupe tous les bâtiments qui ont été associés
        self.groupes_pates_maisons = self.graphe_connexe()

        return self.groupes_pates_maisons
   

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
                    geoserie_1:gpd.GeoDataFrame = prediction_1.get_geodataframe_pate_maison().geometry
                    geoserie_2:gpd.GeoDataFrame = prediction_2.get_geodataframe_pate_maison().geometry

                    if geoserie_1.shape[0]==0 or geoserie_2.shape[0]==0:
                        continue

                    # On récupère les intersections entre les géométries terrain des bâtiments
                    intersections = geoserie_2.sindex.query(geoserie_1, predicate="intersects")

                    for i in range(geoserie_1.shape[0]):
                        
                        # Pour chaque bâtiment, on récupère parmi les bâtiments qu'il intersecte celui avec lequel il partage la plus grande aire
                        pm_1 = prediction_1.get_pate_maison_i(i)
                        
                        pm_1_emprise = pm_1.get_geometrie_terrain()
                        area_max = 0
                        id_max = None

                        indices = np.where(intersections[0,:]==i)[0]
                        for j in range(indices.shape[0]):
                            indice = indices[j]                                
                            pm_2_emprise = prediction_2.get_pate_maison_i(intersections[1,indice])
                            aire_commune = pm_1_emprise.intersection(pm_2_emprise.get_geometrie_terrain()).area
                            if aire_commune > area_max:
                                area_max = aire_commune
                                id_max = pm_2_emprise
                        if id_max is not None:
                            pm_1.add_homologue(id_max)
                            id_max.add_homologue(pm_1)


    def graphe_connexe(self)->List[GroupePatesMaisons]:
        """
        On réunit tous les bâtiments qui représentent un même bâtiment dans la réalité
        """
        groupe_pates_maisons = []
        for prediction in self.predictions:
            for pm in prediction.get_pates_maisons():
                if not pm._marque:
                    pms = [pm]
                    liste = [pm]
                    pm._marque = True

                    while len(liste) > 0:
                        b = liste.pop()
                        for homologue in b.get_homologues():
                            if not homologue._marque:
                                homologue._marque = True
                                if homologue not in liste:
                                    pms.append(homologue)
                                    liste.append(homologue)

                    groupe_pates_maisons.append(GroupePatesMaisons(pms))
        
        return groupe_pates_maisons

