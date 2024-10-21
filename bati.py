from __future__ import annotations
from goutiere import Goutiere_image, Goutiere_proj
from shapely import Polygon, MultiPolygon, MultiLineString, intersection, union
from shapely.validation import make_valid
import numpy as np
from typing import List
from shot import Shot
from numpy import linalg as LA

class Bati:

    def __init__(self, id_origine, image_geometry, shot:Shot, dem, compute_gouttiere=True, unique_id=None, estim_z=0) -> None:
        self.image_geometry = image_geometry
        self.ground_geometry = None
        self.shot = shot
        self.dem = dem

        self.marque = False
        self.homologue = []
        self.id_origine = id_origine

        self.estim_z = []
        self.estim_z_finale = estim_z

        self.keep = False
        self.score = None
        self.dist_finale = None


        self.numpy_array = None
        self.numpy_array_translation = None
        self.parametres_recalage = [None, None, None, None]

        self.goutieres:List[Goutiere_image] = []

        if compute_gouttiere:
            self.compute_gouttieres(unique_id)

        self.compute_ground_geometry()



    def compute_ground_geometry(self):
        image_points = self.image_geometry["coordinates"][0]
        c = []
        l = []
        for image_point in image_points:
            c.append(image_point[0])
            l.append(-image_point[1])
        try:
            x, y, z = self.shot.image_to_world(np.array(c), np.array(l), self.dem, estim_z=self.estim_z_finale)
            ground_points = []
            for i in range(len(x)):
                ground_points.append([x[i], y[i], z[i]]) 
            self.ground_geometry = Polygon(ground_points)
            if not self.ground_geometry.is_valid:
                valid_geometry = make_valid(self.ground_geometry)
                if isinstance(valid_geometry, MultiPolygon):
                    self.ground_geometry = list(valid_geometry.geoms)[0]
                else:
                    self.ground_geometry = valid_geometry
        except:
            print("Out dem : ", c, l)
            self.ground_geometry = None

    
    def compute_gouttieres(self, unique_id):
        points = self.image_geometry["coordinates"][0]
        for i in range(len(points)-1):
            # On crée la gouttière
            goutiere = Goutiere_image(self.shot, "test", self.dem, self.id_origine, estim_z=self.estim_z_finale)
            
            # On calcule les paramètres du plan passant par le sommet de prise de vue et la goutière
            image_line = np.array([[points[i][0], -points[i][1]], [points[i+1][0], -points[i+1][1]]])
            goutiere.set_image_line(image_line, compute_equation_plan=True)
            goutiere.id_bati = self.id_origine
            
            if unique_id is not None:
                goutiere.id_unique = unique_id
                unique_id += 1
            
            self.goutieres.append(goutiere)


    def emprise_sol(self):
        return self.ground_geometry

    def add_homologue(self, homologue):
        if homologue not in self.homologue:
            self.homologue.append(homologue)


    def emprise_image(self):
        return Polygon(self.image_geometry["coordinates"][0])

    def pva(self):
        return self.goutieres[0].get_image()

    
    def set_voisins(self):
        for i in range(1, len(self.goutieres)-1):
            g1 = self.goutieres[i]
            g0 = self.goutieres[i-1]
            g2 = self.goutieres[i+1]
            g1.voisin_1 = g0
            g1.voisin_2 = g2
            g0.voisin_2 = g1
            g2.voisin_1 = g1
        self.goutieres[0].voisin_1 = self.goutieres[-1]
        self.goutieres[-1].voisin_2 = self.goutieres[0]

        
    def create_numpy_array(self, dx=0, dy=0):

        nb_goutieres = len(self.goutieres)

        
        # Dans un premier tableau numpy, on met les coordonnées des extrémités des goutières en coordonnées du monde
        array = np.zeros((nb_goutieres, 4))
        for i, goutiere in enumerate(self.goutieres):
            world_line = goutiere.world_line
            array[i,:] = np.array([world_line[0,0]+dx, world_line[0,1]+dy, world_line[1,0]+dx, world_line[1,1]+dy])
            
        # On calcule le vecteur directeur normalisé des goutières (en 2d)
        dx = (array[:,2]-array[:,0])
        dy = (array[:,3]-array[:,1])
        u = np.concatenate((dx.reshape((-1, 1)), dy.reshape((-1, 1))), axis=1)
        norm = np.linalg.norm(u, axis=1)
        u = u / np.tile(norm.reshape((-1, 1)), (1, 2))
        
        # On calcule le barycentre de la goutière (en 2d)
        barycentre_x = (array[:,2]+array[:,0])/2
        barycentre_y = (array[:,3]+array[:,1])/2
        barycentre = np.concatenate((barycentre_x.reshape((-1, 1)), barycentre_y.reshape((-1, 1))), axis=1)
        
        # On calcule les paramètres de la droite de la goutière (en 2d)
        a = dy
        b = -dx
        c = dx * array[:,1] - dy * array[:,0]
        racine = np.sqrt(a**2 + b**2)
        equation_droite = np.concatenate((a.reshape((-1, 1)), b.reshape((-1, 1)), c.reshape((-1, 1)), racine.reshape((-1, 1))), axis=1)
        
        # On calcule la moitié de la longueur de la goutière
        d_max = 0.5 * np.sqrt(dx**2+dy**2)
        
        # On réunit tous les tableaux dans un dictionnaire
        return {"array":array, "u":u, "barycentre":barycentre, "equation_droite":equation_droite, "d_max":d_max}


    def linestring(self):
        points = []
        for s in self.goutieres:
            points.append([s.P0(), s.P1()])
        return MultiLineString(points)
    

    def compute_IoU(self, b2:Bati):
        footprint_1 = self.emprise_sol()
        footprint_2 = b2.emprise_sol()
        intersection_area = intersection(footprint_1, footprint_2).area
        union_area = union(footprint_1, footprint_2).area
        return intersection_area / union_area
    

    def compute_estim_z(self, b2:Bati):
        """
        On essaye d'estimer la hauteur du bâtiment
        """

        # On récupère les sommets de prise de vue des deux bâtiments
        s1 = self.shot.get_sommet()
        s2 = b2.shot.get_sommet()
        s1_numpy = np.array([s1.x, s1.y, s1.z])
        s2_numpy = np.array([s2.x, s2.y, s2.z])

        # On récupère les barycentres des emprises au sol
        barycentre_1 = self.emprise_sol().centroid
        barycentre_2 = b2.emprise_sol().centroid
        b1_coords = self.emprise_sol().exterior.coords
        
        # Bidouille car shapely ne sait pas récupérer le z des barycentres...
        sum_z = 0
        compte = 0
        for p in b1_coords:
            sum_z += p[2]
            compte += 1
        
        barycentre_1_z = sum_z/compte
        barycentre_1_numpy = np.array([barycentre_1.x, barycentre_1.y, barycentre_1_z])
        
        
        b2_coords = self.emprise_sol().exterior.coords
        sum_z = 0
        compte = 0
        for p in b2_coords:
            sum_z += p[2]
            compte += 1
        barycentre_2_z = sum_z/compte
        barycentre_2_numpy = np.array([barycentre_2.x, barycentre_2.y, barycentre_2_z])

        
        # On détermine le plan qui passe par les deux sommets de prise de vue et un des deux barycentres
        ux = s1.x - s2.x
        uy = s1.y - s2.y
        uz = s1.z - s2.z

        vx = s1.x - barycentre_1.x
        vy = s1.y - barycentre_1.y
        vz = s1.z - barycentre_1_z

        u_cross_v = [uy*vz-uz*vy, uz*vx-ux*vz, ux*vy-uy*vx]

        normal = np.array(u_cross_v)
        normal = normal / LA.norm(normal)

        # On calcule la distance du deuxième barycentre au plan 
        w = barycentre_2_numpy-s1_numpy
        dist = np.sum(w*normal)

        # A l'aide du théorème de Thalès, on récupère l'altitude moyenne du bâtiment
        delta_x = np.sqrt(np.sum((barycentre_1_numpy-barycentre_2_numpy)**2))
        delta_l = np.sqrt(np.sum((s1_numpy-s2_numpy)**2))
        h = (s1.z+s2.z)/2

        delta_z = delta_x * h / delta_l

        # On renvoie l'altitude du bâtiment et la distance du deuxième barycentre au plan qui permet d'avoir une 
        # idée de la fiabilité du résultat (en théorie, dans un monde parfait, dist=0)
        return {"delta_z":delta_z, "dist":dist}
    

    def correlation_score(self, b2:Bati):
        """
        On retourne un score de corrélation géométrique qui prend en compte :
            - le nombre de sommets des deux polygones
            - le ratio de la surface entre les deux polygones
            - la cohérence géométrique en récupérant le "résidu" du calcul de l'estimation du z
        """
        nb_sommets_b1 = len(self.emprise_sol().exterior.coords)
        nb_sommets_b2 = len(b2.emprise_sol().exterior.coords)

        surface_b1 = self.emprise_sol().area
        surface_b2 = b2.emprise_sol().area
        if surface_b1>surface_b2:
            ratio_surface = surface_b1/surface_b2
        else:
            ratio_surface = surface_b2/surface_b1
        
        estim_z = self.compute_estim_z(b2)

        return abs(nb_sommets_b1-nb_sommets_b2) + (ratio_surface-1) + abs(estim_z["dist"])
    

    @staticmethod
    def mean_z_estim(estim_z_list):
        """
        Calcule une moyenne des hauteurs des bâtiments pondérée par la distance d'un des deux barycentres au plan
        """
        sum = 0
        weights = 0
        for estim in estim_z_list:
            if estim["dist"] <= 0.2:
                sum += estim["delta_z"] / estim["dist"]
                weights += 1/estim["dist"]
        if weights==0:
            return 10
        if sum/weights<0 or sum/weights>20:# sécurité pour ne pas avoir des résultats aberrants
            return 10
        return sum/weights
    

    @staticmethod
    def find_best_couple(batis:List[Bati]):
        best_couple = None
        best_score = 1e15
        for i1 in range(len(batis)):
            for i2 in range(i1+1, len(batis)):
                b1 = batis[i1]
                b2 = batis[i2]
                if b1.shot.image != b2.shot.image:
                    score = b1.correlation_score(b2)
                    if score < best_score:
                        best_score = score
                        best_couple = (b1, b2)
        return best_couple, best_score
    

    @staticmethod
    def mean_z_estim_v2(batis:List[Bati]):
        estim_z_sum = 0
        compte = 0
        for i1 in range(len(batis)):
            for i2 in range(i1+1, len(batis)):
                b1 = batis[i1]
                b2 = batis[i2]
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
        for bati in batis:
            bati.estim_z_finale = estim_z_final
        


    


class BatiProjete(Bati):

    def __init__(self, goutieres:Goutiere_proj) -> None:
        self.goutieres = goutieres