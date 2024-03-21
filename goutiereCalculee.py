from shapely import Point, LineString
import numpy as np
from troncon import Troncon
from typing import List


class GoutiereCalculee:

    def __init__(self, x1, y1, z1, x2, y2, z2, id_bati, id_segment, fictive=False) -> None:
        self.p1 = Point(x1, y1, z1)
        self.p2 = Point(x2, y2, z2)
        self.id_bati = id_bati
        self.id_segment = id_segment
        self.id_voisins = []
        self.voisins:List[GoutiereCalculee] = []
        self.fictive = fictive
        self.intersections = []
        self.troncons = []

        self.a = None
        self.b = None
        self.u = None

        self.supprime = False

        self.calcule_a_b()

    def mettre_a_jour_extremites(self):
        """
        Si le segment a exactement deux voisins
        """
        if len(self.voisins) == 2:
            v1 = self.voisins[0]
            v2 = self.voisins[1]

            # On considère que les deux extrémités sont les deux points les plus proches des deux voisins
            p1, p2 = v1.p_proches(v2)[0]
            self.p1 = p1
            self.p2 = p2

            # On calcule les paramètres de la droite
            self.calcule_a_b()
        else:
            self.supprime = True


    def distance_goutiere(self, point):
        d1 = self.distance_point(self.p1, point)
        d2 = self.distance_point(self.p2, point)
        if d1 < d2:
            return d1, 1
        else:
            return d2, 2

    def p_proches(self, s2):
        """
        Renvoie deux couples de points.
        Le premier couple est constitué des points de self et de s2 qui sont les plus proches
        Le deuxième sont les deux autres points
        """
        minimum = 1e10
        
        d11 = self.distance_point(self.p1, s2.p1)
        minimum = min(d11, minimum)
        d12 = self.distance_point(self.p1, s2.p2)
        minimum = min(d12, minimum)
        d21 = self.distance_point(self.p2, s2.p1)
        minimum = min(d21, minimum)
        d22 = self.distance_point(self.p2, s2.p2)
        minimum = min(d22, minimum)
        if d11 == minimum:
            return (self.p1, s2.p1), (self.p2, s2.p2)
        if d12 == minimum:
            return (self.p1, s2.p2), (self.p2, s2.p1)
        if d21 == minimum:
            return (self.p2, s2.p1), (self.p1, s2.p2)
        if d22 == minimum:
            return (self.p2, s2.p2), (self.p1, s2.p1)


    def p_proches_points(self, p1, p2):
        """
        Renvoie deux couples de points en réunissant les plus proches.
        Le premier couple est constitué du point self.p1
        Le deuxième sont les deux autres points
        """
        minimum = 1e10
        
        d11 = self.distance_point(self.p1, p1)
        minimum = min(d11, minimum)
        d12 = self.distance_point(self.p1, p2)
        minimum = min(d12, minimum)
        d21 = self.distance_point(self.p2, p1)
        minimum = min(d21, minimum)
        d22 = self.distance_point(self.p2, p2)
        minimum = min(d22, minimum)
        if d11 == minimum:
            return (self.p1, p1), (self.p2, p2)
        if d12 == minimum:
            return (self.p1, p2), (self.p2, p1)
        if d21 == minimum:
            return (self.p1, p2), (self.p2, p1)
        if d22 == minimum:
            return (self.p1, p1), (self.p2, p2)



    def calcule_a_b(self):
        ux0 = self.p2.x - self.p1.x
        uy0 = self.p2.y - self.p1.y
        uz0 = self.p2.z - self.p1.z

        u = np.array([[ux0], [uy0], [uz0]])
        self.u = u / np.linalg.norm(u)

        u_plani = np.array([[ux0], [uy0]])
        self.u_plani = u_plani / np.linalg.norm(u_plani)

        if ux0 == 0:
            self.a = 0
            self.b = self.p1.y
        else:
            self.a = uy0 / ux0
            self.b = self.p1.y - self.p1.x / ux0 * uy0


    def distance_point(self, p1, p2):
        return np.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2 + (p1.z - p2.z)**2)


    def intersection(self, s2):
        if s2.a == self.a:
            print(s2.a, self.a)
            print(s2, self)
        x = -(s2.b - self.b) / (s2.a - self.a)
        y = self.a * x + self.b
        return x, y

    def produit_scalaire(self, s2):
        return np.abs(np.sum(self.u_plani*s2.u_plani))


    def calcul_z(self, x):
        l = (x-self.p1.x) / self.u[0,0]
        z = self.p1.z + l * self.u[2,0]
        return z


    def autre_voisin(self, voisin):
        autres_voisins = []
        for v in self.voisins:
            if v != voisin:
                autres_voisins.append(v)
        return autres_voisins


    def nb_voisins_non_supprimes(self):
        """
        Renvoie le nombre de voisins non supprimés
        """
        compte = 0
        for voisin in self.voisins:
            if not voisin.supprime:
                compte += 1
        return compte

    def get_voisins_non_supprime(self):
        for voisin in self.voisins:
            if not voisin.supprime:
                return voisin


    def decouper_troncons(self):
        """
        On découpe le segment en tronçons. Deux tronçons ne peuvent se superposer

        Un tronçon est délimité par deux intersections avec des segments voisins
        """
        points = []
        for point in self.intersections:
            # l indique la distance de l'intersection par rapport à self.p1
            l = (point.x - self.p1.x) / self.u[0,0]
            points.append({"p":point, "l":l})

        # On trie les points en fonction de l
        points_tries = sorted(points, key=lambda item: item["l"])
        
        # On crée un tronçon pour chaque couple de points
        for i in range(1, len(points_tries)):
            troncon = Troncon(points_tries[i-1]["p"], points_tries[i]["p"], self.id_segment)
            self.troncons.append(troncon)
        

    def ajouter_intersection(self, intersection):
        """
        Ajoute intersection à self.intersections si l'intersection n'y est pas déjà.

        Suite à des erreurs d'arrondis, on vérifie que l'intersection n'est pas déjà présente via un calcul de distance
        """
        ajout = True
        epsilon = 0.1
        for i in self.intersections:
            if self.distance_point(i, intersection) < epsilon:
                ajout = False
        if ajout:
            self.intersections.append(intersection)


    def ajuster_intersection(self):
        if len(self.voisins) == 2:
            v1 = self.voisins[0]
            v2 = self.voisins[1]

            # On considère que les deux extrémités sont les deux points les plus proches des deux voisins
            p1, p2 = v1.p_proches(v2)[0]
            self.p1 = p1
            self.p2 = p2

            # On calcule les paramètres de la droite
            self.calcule_a_b()
        else:
            self.supprime = True


    def emprise_sol(self):
        return LineString([self.p1, self.p2])
        



