from v2.pateMaison import PateMaison
from typing import List
import numpy as np

class GroupePatesMaisons:

    identifiant_global = 0

    def __init__(self, pates_maisons:List[PateMaison]):
        self.pates_maisons = pates_maisons

        self.identifiant:int = PateMaison.identifiant_global
        PateMaison.identifiant_global += 1

        for pm in self.pates_maisons:
            pm.set_id_groupe_pate_maison(self.identifiant)
        self.gdf = None

    def create_geodataframe(self):
        for pm in self.pates_maisons:
            pm.create_geodataframe()
        

    def get_geodataframe(self):
        return self.gdf
    
    def get_pate_maisons_i(self, i)->PateMaison:
        return self.pates_maisons[i]
    
    def compute_ground_geometry(self):
        for pm in self.pates_maisons:
            pm.compute_ground_geometry_bati()


    def check_in_emprise(self, emprise):
        for pm in self.pates_maisons:
            pm.check_in_emprise(emprise)


    def association(self):
        for pm1 in self.pates_maisons:
            geoserie_1 = pm1.get_geodataframe().geometry
            if geoserie_1.shape[0]==0:
                continue
            for pm2 in self.pates_maisons:
                if pm1.identifiant == pm2.identifiant:
                    continue
            
                geoserie_2 = pm2.get_geodataframe().geometry
                if geoserie_2.shape[0]==0:
                    continue

                intersections = geoserie_2.sindex.query(geoserie_1, predicate="intersects")
                for i in range(geoserie_1.shape[0]):
                    # Pour chaque bâtiment, on récupère parmi les bâtiments qu'il intersecte celui avec lequel il partage la plus grande aire
                    bati_1 = pm1.get_batiment_i(i)
                        
                    bati_1_emprise = bati_1.get_geometrie_terrain()
                    area_max = 0
                    bati_max = None

                    indices = np.where(intersections[0,:]==i)[0]
                    for j in range(indices.shape[0]):
                        indice = indices[j]                                
                        bati_2 = pm2.get_batiment_i(intersections[1,indice])
                        aire_commune = bati_1_emprise.intersection(bati_2.get_geometrie_terrain()).area
                        if aire_commune > area_max:
                            area_max = aire_commune
                            bati_max = bati_2
                    if bati_max is not None:
                        bati_1.add_homologue(bati_max.identifiant)
                        bati_max.add_homologue(bati_1.identifiant)
        