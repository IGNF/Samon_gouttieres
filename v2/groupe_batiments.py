from v2.batiment import Batiment
from typing import List
from v2.groupe_segments import GroupeSegments
import numpy as np
from shapely import Point, Polygon, polygonize

class GroupeBatiments:

    identifiant_global = 0

    def __init__(self, batiments:List[Batiment]):
        self.batiments = batiments

        self.identifiant:int = GroupeBatiments.identifiant_global
        GroupeBatiments.identifiant_global += 1


        self.estim_z:float=None

        # A chaque bâtiment, on complète l'attribut qui indique à quel groupe de bâtiment il appartient
        for batiment in self.batiments:
            batiment.groupe_batiment = self

        self.groupes_segments:List[GroupeSegments] = []

        self.geometrie_fermee:Polygon = None


    def compute_z_mean(self):
        estim_z_sum = 0
        compte = 0
        for i1 in range(len(self.batiments)):
            for i2 in range(i1+1, len(self.batiments)):
                b1 = self.batiments[i1]
                b2 = self.batiments[i2]
                if b1.shot.image != b2.shot.image:
                    score = b1.correlation_score(b2)
                    if score < 0.2:
                        estim_z_sum += b1.compute_estim_z(b2)["delta_z"]
                        compte += 1
        if compte==0:
            estim_z_final = 10
        else:
            estim_z_final = estim_z_sum/compte
        if estim_z_final<0 or estim_z_final >= 20:
            estim_z_final = 10
        self.estim_z = estim_z_final

    def update_geometry_terrain(self):
        for batiment in self.batiments:
            batiment.compute_ground_geometry(estim_z=self.estim_z)

    def get_identifiant(self)->int:
        return self.identifiant


    def create_segments(self)->None:
        for batiment in self.batiments:
            batiment.create_segments()
            batiment.create_numpy_array()

    def get_batiments(self)->List[Batiment]:
        return self.batiments
    

    def update_groupe_segments(self)->None:
        groupes_segments:List[GroupeSegments] = []
        for batiment in self.batiments:
            for segment in batiment.get_segments():
                groupe_segments = segment.get_groupe_segments()
                if groupe_segments is not None and groupe_segments not in groupes_segments:
                    groupes_segments.append(groupe_segments)
        self.groupes_segments = groupes_segments


    def ajuster_intersection(self):
        for groupe_segment in self.groupes_segments:
            for voisin in groupe_segment.voisins:
                if voisin.is_valid() and not voisin._supprime:
                    ps = groupe_segment.compute_produit_scalaire(voisin)
                    if ps < 0.8:
                        intersection_x, intersection_y = groupe_segment.intersection(voisin)
                        z1 = groupe_segment.calcul_z(intersection_x)
                        z2 = voisin.calcul_z(intersection_x)
                        z_mean = (z1+z2)/2
                        if not np.isnan(z_mean):
                            intersection = Point(intersection_x, intersection_y, z_mean)
                            # On ajoute le point d'intersection à l'attribut intersections de segment et de voisin
                            groupe_segment.ajouter_intersection(intersection, voisin)
                            voisin.ajouter_intersection(intersection, groupe_segment)

        for groupe_segment in self.groupes_segments:
            if len(groupe_segment.intersections)==1:
                i = groupe_segment.intersections[0]["point"]
                d1 = groupe_segment.distance_point(groupe_segment.p1, i)
                d2 = groupe_segment.distance_point(groupe_segment.p2, i)
                if d1 < d2:
                    groupe_segment.set_p1(i)
                else:
                    groupe_segment.set_p2(i)
                groupe_segment.calcule_a_b()
            
            elif len(groupe_segment.intersections)==2:
                i1 = groupe_segment.intersections[0]["point"]
                i2 = groupe_segment.intersections[1]["point"]

                c1, c2 = groupe_segment.p_proches_points(i1, i2)
                groupe_segment.set_p1(c1[1])
                groupe_segment.set_p2(c2[1])
                groupe_segment.calcule_a_b()

            elif len(groupe_segment.intersections)>2:
                

                i1 = groupe_segment.intersections[0]["point"]
                i2 = groupe_segment.intersections[1]["point"]

                c1, c2 = groupe_segment.p_proches_points(i1, i2)
                groupe_segment.set_p1(c1[1])
                groupe_segment.set_p2(c2[1])
                groupe_segment.calcule_a_b()

                intersections_sorted = groupe_segment.sort_by_intersection()
                for i in range(1, len(intersections_sorted)):
                    i1 = intersections_sorted[i-1]["intersection"]
                    i2 = intersections_sorted[i]["intersection"]
                    p1 = i1["point"]
                    p2 = i2["point"]

                    new_groupe_segments:GroupeSegments = GroupeSegments.from_p1_p2(groupe_segment.segments, p1, p2)
                
                    v0:GroupeSegments = i1["groupe_segments"]
                    v1:GroupeSegments = i2["groupe_segments"]
                    new_groupe_segments.voisins = [v0, v1]


                    self.replace_id_voisins(v0, groupe_segment, new_groupe_segments)
                    self.replace_id_voisins(v1, groupe_segment, new_groupe_segments)
                    self.groupes_segments.append(new_groupe_segments)
                groupe_segment._supprime = True


    def replace_id_voisins(self, groupe_segment:GroupeSegments, old_voisin:GroupeSegments, new_voisin:GroupeSegments)->None:
        if old_voisin in groupe_segment.voisins:
            groupe_segment.voisins.remove(old_voisin)

        if new_voisin not in groupe_segment.voisins:
            groupe_segment.voisins.append(new_voisin)

    
    def fermer_geometrie(self):
        linestrings = []
        for segment in self.groupes_segments:
            if not segment._supprime:
                linestrings.append(segment.get_geometrie())
        self.geometrie_fermee = polygonize(linestrings)

    def get_geometrie_fermee(self)->Polygon:
        return self.geometrie_fermee