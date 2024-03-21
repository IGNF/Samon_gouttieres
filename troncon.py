from typing import List
import numpy as np

class Troncon:

    def __init__(self, p1, p2, id) -> None:
        self.p1 = p1
        self.p2 = p2
        self.compte = None
        self.id = id

        self.precedents:List[Troncon] = []

        self.voisins:List[Troncon] = []

    #def __str__(self) -> str:
    #    return "{}, {}".format(self.p1, self.p2)


    def sont_voisins(self, t):
        """
        Indique si self et t sont voisins, ie si self et t ont un point en commun
        """
        if self.p1 == t.p1 or self.p1 == t.p2 or self.p2 == t.p1 or self.p2 == t.p2:
            return True
        return False

    def distance_points(self, p1, p2):
        return np.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2 + (p1.z - p2.z)**2)

    def remonter(self, t_1):
        """
        Renvoie le tronçon dans self.precedents avec la valeur de compte la plus élevée
        """
        compte_max = -1
        t_max = None

        for t in self.precedents:
            if t != t_1:
                if t.compte > compte_max:
                    compte_max = t.compte
                    t_max = t
        return t_max

    def remonter_0(self):
        compte_max = -1
        t_max = None

        for t in self.voisins:
            if t.compte is not None:
                if t.compte > compte_max:
                    compte_max = t.compte
                    t_max = t
        return t_max

    def has_point(self, p):
        if self.p1 == p or self.p2 == p:
            return True
        return False

    def autre_point(self, p):
        if p == self.p1:
            return self.p2
        if p == self.p2:
            return self.p1
        #print("Erreur")
        
