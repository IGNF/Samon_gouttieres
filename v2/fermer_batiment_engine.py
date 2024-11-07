from typing import List
from v2.groupe_batiments import GroupeBatiments, id_debug
from tqdm import tqdm
from v2.segments import Segment
from v2.groupe_segments import GroupeSegments


class FermerBatimentEngine:

    seuil_ps = 0.8

    def __init__(self, groupes_batiments:List[GroupeBatiments]):
        self.groupes_batiments = groupes_batiments


    def fermer_deuxieme_tentative(self, groupe_batiment:GroupeBatiments):
        """
        Deuxième tentative pour fermer les bâtiments qui ne veulent pas se fermer
        """

        # On récupère le bâtiment qui est le plus proche du nadir et le plus grand en surface
        batiment_principal = groupe_batiment.get_batiment_nearest_nadir()
        if groupe_batiment.get_identifiant()==id_debug:
            print("batiment_principal : ", batiment_principal.shot.image, batiment_principal.identifiant)

        # On parcourt tous les segments qui constituent ce batiment et on récupère l'altitude moyenne du segment
        segment_sans_estimation_z:List[Segment] = []
        altitudes_moyennes = []
        if groupe_batiment.get_identifiant()==id_debug:
            print("len(batiment_principal.get_segments()) : ", len(batiment_principal.get_segments()))
        for segment in batiment_principal.get_segments():
            groupe_segment = groupe_batiment.get_groupe_segments_one_segment(segment)
            if groupe_segment is None or not groupe_segment.is_valid():
                segment_sans_estimation_z.append(segment)
                continue

            altitude_moyenne = groupe_segment.altitude_moyenne()
            if altitude_moyenne is None:
                segment_sans_estimation_z.append(segment)
                continue
            altitudes_moyennes.append(altitude_moyenne)
            segment.estim_z_bati_ferme = altitude_moyenne

        if groupe_batiment.get_identifiant()==id_debug:
            print("altitudes_moyennes : ", altitudes_moyennes)
        if len(altitudes_moyennes)==0:
            return False
        
        # On calcule l'altitude moyenne des segments
        altitude_moyenne_bati = 0
        for alt in altitudes_moyennes:
            altitude_moyenne_bati += alt
        altitude_moyenne_bati = altitude_moyenne_bati / len(altitudes_moyennes)
        if groupe_batiment.get_identifiant()==id_debug:
            print("altitude_moyenne_bati : ", altitude_moyenne_bati)

        # Pour chaque segment, on calcule sa projection sur l'altitude définie par (dans l'ordre de priorité) :
        # - altitude du segment calculé par intersection de plans
        # - altitude des voisins
        # - altitude moyenne du bâtiment
        for segment in batiment_principal.get_segments():
            segment.compute_ground_geometry_fermer_bati_2(altitude_moyenne_bati)


        # On met dans l'état supprimé tous les groupeSegments déjà existants
        for groupe_segment in groupe_batiment.groupes_segments:
            groupe_segment._supprime = True
        
        # On ajoute des groupes segments créés à partir uniquement des segments du bâtiment principal
        for segment in batiment_principal.get_segments():
            groupe_batiment.groupes_segments.append(GroupeSegments.from_one_segment(segment))


        # Il ne reste plus qu'à mettre à jour les voisins et à ajuster les intersections
        for groupe_segment in groupe_batiment.groupes_segments:
            groupe_segment.update_voisins()

        # On ajuste les intersections avec les nouveaux groupes de segments
        groupe_batiment.ajuster_intersection(seuil_ps=1.0)

        # On ferme la géométrie
        groupe_batiment.fermer_geometrie()
        if groupe_batiment.get_identifiant()==id_debug:
            print("groupe_batiment.get_geometrie_fermee() : ", groupe_batiment.get_geometrie_fermee())
        if len(groupe_batiment.get_geometrie_fermee().geoms)!=0:
            groupe_batiment.set_methode_fermeture("projection")



    def run(self):

        print("On récupère pour chaque groupe bâtiment les groupes de segments")
        for groupe_batiment in tqdm(self.groupes_batiments):
            groupe_batiment.update_groupe_segments()  

        print("On ajuste pour chaque bâtiment les intersections des bords de toit")
        for groupe_batiment in tqdm(self.groupes_batiments):
            for groupe_segment in groupe_batiment.groupes_segments:
                if groupe_segment.is_valid():
                    # Deux segments ne doivent pas être presque parallèle pour être considérés comme voisins par la suite
                    groupe_segment.update_voisins_ps(FermerBatimentEngine.seuil_ps)

            groupe_batiment.ajuster_intersection()
            groupe_batiment.fermer_geometrie()

            if groupe_batiment.get_identifiant()==id_debug:
                print("len(groupe_batiment.get_geometrie_fermee().geoms) : ", len(groupe_batiment.get_geometrie_fermee().geoms))
            
            # Si le bâtiment n'a pas pu être fermé, alors on fait une deuxième tentative en projettant une prédiction du FFL sur le MNT + estimation de la hauteur
            if not groupe_batiment.geometrie_fermee_valide():
                self.fermer_deuxieme_tentative(groupe_batiment)
            else:
                groupe_batiment.set_methode_fermeture("photogrammetrie")

            
            
    