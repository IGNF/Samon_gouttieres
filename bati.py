from goutiere import Goutiere_image, Goutiere_proj
from shapely import Polygon, MultiLineString
from shapely.validation import make_valid
import numpy as np
from typing import List

class Bati:

    def __init__(self, id_origine, image_geometry, shot, dem, compute_gouttiere=True, unique_id=None) -> None:
        self.image_geometry = image_geometry
        self.ground_geometry = None
        self.shot = shot
        self.dem = dem

        self.marque = False
        self.homologue = []
        self.id_origine = id_origine


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
            x, y, z = self.shot.image_to_world(np.array(c), np.array(l), self.dem)
            ground_points = []
            for i in range(len(x)):
                ground_points.append([x[i], y[i], z[i]]) 
            self.ground_geometry = Polygon(ground_points)
            if not self.ground_geometry.is_valid:
                self.ground_geometry = make_valid(self.ground_geometry)
        except:
            print("Out dem : ", c, l)
            self.ground_geometry = None

    
    def compute_gouttieres(self, unique_id):
        points = self.image_geometry["coordinates"][0]
        for i in range(len(points)-1):
            # On crée la gouttière
            goutiere = Goutiere_image(self.shot, "test", self.dem, self.id_origine)
            
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
    


class BatiProjete(Bati):

    def __init__(self, goutieres:Goutiere_proj) -> None:
        self.goutieres = goutieres