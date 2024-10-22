from v2.batiment import Batiment
from typing import List

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
