from typing import List
from v2.prediction import Prediction
from tqdm import tqdm
import geopandas as gpd
from v2.groupe_batiments import GroupeBatiments

class AssociationBatimentEngine:

    """
    Algorithme pour associer les bâtiments entre eux
    """

    def __init__(self, predictions:List[Prediction]):
        self.predictions:List[Prediction] = predictions

        self.groupe_batiments:List[GroupeBatiments] = None



    def run(self)->List[GroupeBatiments]:
        print("Calcul des géométries terrain")
        for prediction in self.predictions:
            prediction.compute_ground_geometry()
        
        print("Calcul des géoséries")
        for prediction in self.predictions:
            prediction.create_geodataframe()

        print("calcul des associations")
        self.association()

        self.groupe_batiments = self.graphe_connexe()

        print("Calcul du z moyen du bâtiment")
        self.compute_z_mean()

        return self.groupe_batiments



    def association(self):
        # On parcourt les shapefile
        for prediction_1 in self.predictions:
            
            # On parcourt les autres shapefile
            for prediction_2 in self.predictions:
                if prediction_1!=prediction_2:
                    # On récupère la géosérie du deuxième shapefile
                    geoserie_1:gpd.GeoDataFrame = prediction_1.get_geodataframe().geometry
                    geoserie_2:gpd.GeoDataFrame = prediction_2.get_geodataframe().geometry

                    intersections = geoserie_2.sindex.query(geoserie_1, predicate="intersects")

                    for i in tqdm(range(geoserie_1.shape[0])):
                        bati_1 = prediction_1.get_batiment_i(i)
                        
                        bati_1_emprise = bati_1.get_geometrie_terrain()
                        area_max = 0
                        id_max = None
                        for j in range(intersections.shape[1]):# On pourrait gagner du temps en faisant un np.where pour n'itérer que sur les cases intéressantes ?
                            if intersections[0,j]==i:
                                
                                bati_2_emprise = prediction_2.get_batiment_i(intersections[1,j])
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
    

    def compute_z_mean(self):
        """
        On calcule le z moyen de chaque groupe de bâtiment, et on met à jour la projection au sol des bâtiments
        """
        for groupe in tqdm(self.groupe_batiments):
            groupe.compute_z_mean()
            groupe.update_geometry_terrain()