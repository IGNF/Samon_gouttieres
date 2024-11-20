from v2.groupe_segments import GroupeSegments
from typing import List
from tqdm import tqdm

class CalculIntersectionEngine:

    def __init__(self, groupe_segments:List[GroupeSegments]):
        self.groupe_segments:List[GroupeSegments] = groupe_segments

    
    def run(self):
        print("On calcule les intersections pour chaque groupe de segments")
        for groupe_segment in tqdm(self.groupe_segments):
            # Pour chaque côté de bâtiment de prédictions FFL, on calcule les paramètres du plan qui passent par le sommet de prise de vue et par ce segment
            groupe_segment.compute_equations_plans()
            # On vérifie la configuration des sommets de prise de vue
            groupe_segment.check_configurations()

            if groupe_segment.is_valid():
                # On calcule l'intersection des plans d'un même groupe de segments par moindres carrés. On obtient une droite
                groupe_segment.moindres_carres()
                # On calcule le distance moyenne entre la droite et les plans
                groupe_segment.distance_moyenne()
                # On vérifie que le résultat est valide (pas aberrant en altitude par exemple)
                groupe_segment.verifier_resultat_valide()

        print("On met à jour les voisins de chaque groupe de segments")
        for groupe_segment in tqdm(self.groupe_segments):
            if groupe_segment.is_valid():
                groupe_segment.update_voisins()

