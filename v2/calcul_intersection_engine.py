from v2.groupe_segments import GroupeSegments
from typing import List
from tqdm import tqdm

class CalculIntersectionEngine:

    def __init__(self, groupe_segments:List[GroupeSegments]):
        self.groupe_segments:List[GroupeSegments] = groupe_segments

    
    def run(self):
        print("On calcule les intersections pour chaque groupe de segments")
        for groupe_segment in tqdm(self.groupe_segments):
            groupe_segment.compute_equations_plans()
            groupe_segment.moindres_carres()
            groupe_segment.distance_moyenne()

        print("On met à jour les voisins de chaque groupe de segments")
        for groupe_segment in tqdm(self.groupe_segments):
            if groupe_segment.is_valid():
                groupe_segment.update_voisins()

