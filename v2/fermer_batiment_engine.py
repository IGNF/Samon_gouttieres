from typing import List
from v2.groupe_batiments import GroupeBatiments
from tqdm import tqdm

class FermerBatimentEngine:

    seuil_ps = 0.8

    def __init__(self, groupes_batiments:List[GroupeBatiments]):
        self.groupes_batiments = groupes_batiments


    def run(self):

        print("On récupère pour chaque groupe bâtiment les groupes de segments")
        for groupe_batiment in tqdm(self.groupes_batiments):
            groupe_batiment.update_groupe_segments()  

        print("On ajuste pour chaque bâtiment les intersections des bords de toit")
        for groupe_batiment in tqdm(self.groupes_batiments):
            for groupe_segment in groupe_batiment.groupes_segments:
                groupe_segment.update_voisins_ps(FermerBatimentEngine.seuil_ps)

            groupe_batiment.ajuster_intersection()
            groupe_batiment.fermer_geometrie()
            
            
    