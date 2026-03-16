from v2.pateMaison import PateMaison
from typing import List

class GroupePatesMaisons:

    identifiant_global = 0

    def __init__(self, pates_maisons:List[PateMaison]):
        self.pates_maisons = pates_maisons

        self.identifiant:int = PateMaison.identifiant_global
        PateMaison.identifiant_global += 1

        for pm in self.pates_maisons:
            pm.set_id_groupe_pate_maison(self.identifiant)


        