from __future__ import annotations
from shapely import LineString, Point
from v2.shot import MNT, Shot
import numpy as np
from typing import List

class Segment:

    identifiant_global = 0

    def __init__(self, geometrie_image:LineString, mnt:MNT, shot:Shot, batiment):
        self.geometrie_image:LineString = geometrie_image
        self.mnt:MNT = mnt
        self.shot:Shot = shot
        self.batiment = batiment
        self.identifiant:int = Segment.identifiant_global
        Segment.identifiant_global += 1

        self.geometrie_terrain:LineString = None
        self.world_line:np.array = None

        self.segments_homologues_1:List[Segment] = [] # Liste des segments homologues
        self.segments_homologues_2:List[Segment] = [] # Liste des segments homologues

        self._marque = False
        self.groupe_segments = None

        self.voisin_1:Segment = None
        self.voisin_2:Segment = None

        self.param_plan:np.array = None #Paramètres du plan passant par le sommet de prise de vue et le segment

        self.estim_z_bati_ferme = None # Approximation de l'altitude du segment. A n'utiliser que dans la deuxième tentative pour fermer les bâtiments

        self.compute_ground_geometry()

    def get_estim_z(self)->float:
        return self.batiment.get_z_mean()


    def compute_ground_geometry(self)->None:
        """
        Calcule l'emprise au sol du bâtiment, projeté sur un MNT
        """

        x, y = self.geometrie_image.coords.xy
        
        c = []
        l = []
        for i in range(len(x)):
            c.append(x[i])
            l.append(-y[i])

        x, y, z = self.shot.image_to_world(np.array(c), np.array(l), self.mnt, estim_z=self.get_estim_z())
        ground_points = []
        for i in range(len(x)):
            ground_points.append([x[i], y[i], z[i]])
        self.geometrie_terrain = LineString(ground_points)
        self.world_line = np.array([[x[0], y[0], z[0]], [x[1], y[1], z[1]]])


    def compute_ground_geometry_fermer_bati_2(self, altitude_moyenne_bati:float)->None:
        """
        Calcule la géométrie terrain du segment

        On utilise self.estim_z_bati_ferme issu du calcul initial d'intersection de plans dans l'espace
        Si cette valeur n'existe pas, alors on utilise celle des segments voisins
        Si les voisins n'en ont pas non plus, alors on utilise la valeur moyenne du bâtiment
        """
        x, y = self.geometrie_image.coords.xy
        
        c = []
        l = []
        for i in range(len(x)):
            c.append(x[i])
            l.append(-y[i])

        if self.estim_z_bati_ferme is not None:
            estim_z = self.estim_z_bati_ferme
        else:
            v1_estim_z = self.voisin_1.estim_z_bati_ferme
            v2_estim_z = self.voisin_2.estim_z_bati_ferme
            if v1_estim_z is not None and v2_estim_z is not None:
                estim_z = (v1_estim_z + v2_estim_z)/2
            else:
                if v1_estim_z is not None:
                    estim_z = v1_estim_z
                elif v2_estim_z is not None:
                    estim_z = v2_estim_z
                else:
                    estim_z = altitude_moyenne_bati

        x, y, z = self.shot.image_to_world(np.array(c), np.array(l), self.mnt, estim_z=estim_z)
        ground_points = []
        for i in range(len(x)):
            ground_points.append([x[i], y[i], z[i]])
        self.geometrie_terrain = LineString(ground_points)
        self.world_line = np.array([[x[0], y[0], z[0]], [x[1], y[1], z[1]]])



    def u_directeur_world(self):
        u = self.world_line[0,:2] - self.world_line[1,:2]
        return u / np.linalg.norm(u)
    
    def barycentre_world(self):
        return (self.world_line[0,:2] + self.world_line[1,:2]) / 2
    
    def add_homologue_1(self, segment:Segment)->None:
        if segment not in self.segments_homologues_1:
            self.segments_homologues_1.append(segment)

    def add_homologue_2(self, segment:Segment)->None:
        if segment not in self.segments_homologues_2:
            self.segments_homologues_2.append(segment)

    def get_image(self)->str:
        return self.batiment.get_image()
    
    def get_longueur(self):
        return np.sqrt(np.sum((self.world_line[0,:]-self.world_line[1,:])**2))
    
    def P0_sol(self):
        return Point(self.world_line[0,0], self.world_line[0, 1])

    def P1_sol(self):
        return Point(self.world_line[1,0], self.world_line[1, 1])
    
    def get_geometrie_terrain(self)->LineString:
        return self.geometrie_terrain
    
    def get_identifiant(self)->int:
        return self.identifiant
    
    def get_identifiant_groupe(self)->int:
        if self.groupe_segments is not None:
            return self.groupe_segments.get_identifiant()
        return -1
    
    def get_groupe_segments(self):
        return self.groupe_segments
    
    def get_identifiant_batiment(self)->int:
        return self.batiment.get_groupe_batiment_id()
    
    def get_voisin_1(self)->Segment:
        return self.voisin_1
    
    def get_voisin_2(self)->Segment:
        return self.voisin_2
    

    def get_sommet_prise_de_vue(self)->np.array:
        """
        Retourne les coordonnées du sommet de prise de vue
        """
        image_conical = self.shot
        return np.array([[image_conical.x_pos, image_conical.y_pos, image_conical.z_pos.item()]])
    

    def get_sommet_prise_de_vue_shapely(self)->Point:
        """
        Retourne les coordonnées du sommet de prise de vue
        """
        image_conical = self.shot
        return Point(image_conical.x_pos, image_conical.y_pos, image_conical.z_pos.item())
    

    def compute_equation_plan(self):
        """
        Calcule les paramètres du plan passant par le sommet de prise de vue et par la goutière
        """
        vec1 = self.world_line[0] - self.get_sommet_prise_de_vue()
        vec1 = vec1 / np.linalg.norm(vec1)
        vec2 = self.world_line[1] - self.get_sommet_prise_de_vue()
        vec2 = vec2 / np.linalg.norm(vec2)
        normale = np.cross(vec1, vec2)
        d = -(normale[0,0] * self.world_line[0,0] + normale[0,1] * self.world_line[0,1] + normale[0,2] * self.world_line[0,2])
        self.param_plan = np.concatenate((normale, np.array([[d]])), axis=1)

    
    def distance_point_plan(self, point:Point)->float:
        a = self.param_plan[0,0]
        b = self.param_plan[0,1]
        c = self.param_plan[0,2]
        d = self.param_plan[0,3]
        distance = abs(a*point.x + b*point.y + c*point.z + d) / np.sqrt(a**2 + b**2 + c**2)
        return distance


    
    def points_plus_proche(self, X1:np.array, u1:np.array)->List[np.array, np.array, float, float]:
        """
        Renvoie pour chacune des extrémités du segment le point appartenant à la droite calculée le plus proche de la droite (sommet de prise de vue, point au sol)
        """

        point0, d0 = self.point_plus_proche(X1, u1, self.world_line[0].reshape((3,1)))
        point1, d1 = self.point_plus_proche(X1, u1, self.world_line[1].reshape((3,1)))
        return point0, point1, d0, d1
    
    
    
    
    def point_plus_proche(self, X1, u1, X2):
        """
        Renvoie le point de la droite (X1, u1) le plus proche de la droite (sommet de prise de vue, point au sol de l'extrémité du segment sur la pva (X2))
        """

       
        u2 = self.get_sommet_prise_de_vue().reshape((3,1)) - X2
        u2 = u2 / np.linalg.norm(u2)
        u1 = u1 / np.linalg.norm(u1)


        X2X1 = X2 - X1
        u1u2 = np.sum(u1*u2)
        u2u2 = np.sum(u2*u2)
        u1u1 = np.sum(u1*u1)
    
        n1 = u1 - u1u2/u2u2 * u2
        n2 = u2 - u1u2/u1u1 * u1

        l1 = (np.sum(X2X1 * n1))/(np.sum(u1*n1))
        l2 = -(np.sum(X2X1 * n2))/(np.sum(u2*n2))

        p1 = X1 + l1 * u1
        p2 = X2 + l2 * u2

        return X1 + l1 * u1, np.sqrt(np.sum((p1-p2)**2))
    

    def compute_pseudo_intersection(self, segment:Segment)->Point:
        """
        Renvoie la pseudo-intersection en géométrie terrain entre self et segment
        """
        P1 = self.world_line[0]
        P2 = segment.world_line[0]

        d1 = self.world_line[1]-self.world_line[0]
        d2 = segment.world_line[1]-segment.world_line[0]

        w = P1 - P2
        a = np.dot(d1, d1)
        b = np.dot(d1, d2)
        c = np.dot(d2, d2)
        d = np.dot(d1, w)
        e = np.dot(d2, w)

        denom = a * c - b * b
        if denom == 0:
            # Droites parallèles, pas d'intersection unique
            t1 = 0
            t2 = d / b if b != 0 else 0
        else:
            t1 = (b * e - c * d) / denom
            t2 = (a * e - b * d) / denom

        Q1 = P1 + t1 * d1
        Q2 = P2 + t2 * d2
        Q = (Q1 + Q2) / 2
        return Point(Q[0], Q[1], Q[2])