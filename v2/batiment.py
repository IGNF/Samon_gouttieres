from __future__ import annotations
from shapely import Polygon, LineString, Point, MultiPolygon, intersection, union, buffer
import numpy as np
from typing import List
from v2.shot import Shot, MNT
from numpy import linalg as LA
from shapely.validation import make_valid
from v2.segments import Segment

class Batiment:

    identifiant_global = 0
    seuil_ps = 0.99

    def __init__(self, geometrie:Polygon, shot:Shot, mnt:MNT):
        self.geometrie_image:Polygon = geometrie
        self.identifiant:int = Batiment.identifiant_global
        self.shot:Shot = shot
        self.mnt:MNT = mnt
        Batiment.identifiant_global += 1

        self.valide:bool = True # Indique si le bâtiment est utilisable
        self.geometrie_terrain:Polygon = None # Géométrie du bâtiment projetée sur le mnt

        self.batiments_homologues:List[Batiment] = [] # Liste des bâtiments issus d'autres images mais représentant le même bâtiment

        self.segments:List[Segment] = [] # Liste des segments constituants le bâtiment


        self._marque = False
        self.groupe_batiment = None # Groupe de bâtiment auquel appartient ce bâtiment

        # tableau numpy contenant les informations relatives aux segments
        self.array:np.array = None
        self.u:np.array = None
        self.barycentre:np.array = None
        self.equation_droite:np.array = None
        self.d_max:np.array = None


    def lisser_geometries(self):
        """
        Lisse les polygones pour qu'un segment corresponde à un côté de bâtiment (et non pas à un morceau de côté de bâtiment)
        """

        # On divise le polygone en un ensemble de lignes
        x, y = self.geometrie_image.exterior.xy
        segments:List[LineString] = []
        for i in range(len(x)-1):
            ls = LineString([[x[i], y[i]], [x[i+1], y[i+1]]])
            if ls.length!=0:
                segments.append(LineString([[x[i], y[i]], [x[i+1], y[i+1]]]))

        liste_segments_poly:List[LineString] = []
        nb_segments = len(segments)
        
        s0 = segments[0]
        x0 = s0.xy[0][0]
        y0 = s0.xy[1][0]
        x1 = s0.xy[0][1]
        y1 = s0.xy[1][1]
        
        # On parcourt tous les segments
        for i in range(1, nb_segments):
            
            # On calcule le produit scalaire entre le segment et le segment précédent
            s1 = segments[i]
            x2 = s1.xy[0][1]
            y2 = s1.xy[1][1]
            u1 = np.array([[x1-x0], [y1-y0]])
            u1 = u1 / np.linalg.norm(u1)
            u2 = np.array([[x2-x1], [y2-y1]])
            u2 = u2 / np.linalg.norm(u2)
            ps = np.sum(u1*u2)
            
            # Si le prduit scalaire est supérieur au seuil, alors on fusionne les deux segments car ils sont presque alignés
            if ps > Batiment.seuil_ps:
                x1 = x2
                y1 = y2
            else:
                # Sinon, on enregistre le segment précédent
                linestring = LineString([[x0, y0], [x1, y1]])
                liste_segments_poly.append(linestring)
                x0 = s1.xy[0][0]
                y0 = s1.xy[1][0]
                x1 = x2
                y1 = y2
                s0 = segments[i]
        
        # Si on n'a aucun segment reconstruit (est-ce possible ?)
        if len(liste_segments_poly)==0:
            linestring = LineString([[x0, y0], [x2, y2]])
            liste_segments_poly.append(linestring)
        # Sinon, on regarde si le dernier segment est aligné avec le premier segment
        else:
            x,y = liste_segments_poly[0].xy
            x2 = x[1]
            y2 = y[1]
            u1 = np.array([[x1-x0], [y1-y0]])
            u1 = u1 / np.linalg.norm(u1)
            u2 = np.array([[x2-x1], [y2-y1]])
            u2 = u2 / np.linalg.norm(u2)
            ps = np.sum(u1*u2)
            if ps > Batiment.seuil_ps:
                del(liste_segments_poly[0])
                linestring = LineString([[x0, y0], [x2, y2]])
                liste_segments_poly.append(linestring)
            else:
                linestring = LineString([[x0, y0], [x1, y1]])
                liste_segments_poly.append(linestring)


        if len(liste_segments_poly)<=3:
            self.valide = False
            return False
        self.geometrie_image = self.linestrings_to_polygon(liste_segments_poly)
        return True


    def is_valid(self)->bool:
        return self.valide
    
    def get_image_geometrie(self)->Polygon:
        return self.geometrie_image
    
    def get_geometrie_terrain(self)->Polygon:
        return self.geometrie_terrain

    def get_identifiant(self)->int:
        return self.identifiant
    
    def linestrings_to_polygon(self, linestrings:List[LineString])->Polygon:
        points:List[Point] = []
        for i, linestring in enumerate(linestrings):
            x, y = linestring.xy
            if i==0:
                points.append(Point(x[0], y[0]))
            points.append(Point(x[1], y[1]))
        return Polygon(points)
    
    

    def compute_ground_geometry(self, estim_z=0)->None:
        """
        Calcule l'emprise au sol du bâtiment, projeté sur un MNT
        """

        x, y = self.geometrie_image.exterior.coords.xy
        
        c = []
        l = []
        for i in range(len(x)):
            c.append(x[i])
            l.append(-y[i])

        x, y, z = self.shot.image_to_world(np.array(c), np.array(l), self.mnt, estim_z=estim_z)
        ground_points = []
        for i in range(len(x)):
            ground_points.append([x[i], y[i], z[i]])
        geometrie_terrain = Polygon(ground_points) 
        if not geometrie_terrain.is_valid:
            valid_geometry = make_valid(geometrie_terrain)
            if isinstance(valid_geometry, MultiPolygon):
                geometrie_terrain = list(valid_geometry.geoms)[0]
            else:
                geometrie_terrain = valid_geometry
        self.geometrie_terrain = geometrie_terrain
        

    def add_homologue(self, batiment:Batiment)->None:
        if batiment not in self.batiments_homologues:
            self.batiments_homologues.append(batiment)

    def get_homologues(self)->List[Batiment]:
        return self.batiments_homologues
    


    def compute_estim_z(self, b2:Batiment):
        """
        On essaye d'estimer la hauteur du bâtiment
        """

        # On récupère les sommets de prise de vue des deux bâtiments
        s1 = self.shot.get_sommet()
        s2 = b2.shot.get_sommet()
        s1_numpy = np.array([s1.x, s1.y, s1.z])
        s2_numpy = np.array([s2.x, s2.y, s2.z])

        # On récupère les barycentres des emprises au sol
        barycentre_1 = self.get_geometrie_terrain().centroid
        barycentre_2 = b2.get_geometrie_terrain().centroid
        b1_coords = self.get_geometrie_terrain().exterior.coords
        
        # Bidouille car shapely ne sait pas récupérer le z des barycentres...
        sum_z = 0
        compte = 0
        for p in b1_coords:
            sum_z += p[2]
            compte += 1
        
        barycentre_1_z = sum_z/compte
        barycentre_1_numpy = np.array([barycentre_1.x, barycentre_1.y, barycentre_1_z])
        
        
        b2_coords = self.get_geometrie_terrain().exterior.coords
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
    

    def correlation_score(self, b2:Batiment):
        """
        On retourne un score de corrélation géométrique qui prend en compte :
            - le nombre de sommets des deux polygones
            - le ratio de la surface entre les deux polygones
            - la cohérence géométrique en récupérant le "résidu" du calcul de l'estimation du z
        """
        nb_sommets_b1 = len(self.get_geometrie_terrain().exterior.coords)
        nb_sommets_b2 = len(b2.get_geometrie_terrain().exterior.coords)

        surface_b1 = self.get_geometrie_terrain().area
        surface_b2 = b2.get_geometrie_terrain().area
        if surface_b1>surface_b2:
            ratio_surface = surface_b1/surface_b2
        else:
            ratio_surface = surface_b2/surface_b1
        
        estim_z = self.compute_estim_z(b2)

        return abs(nb_sommets_b1-nb_sommets_b2) + (ratio_surface-1) + abs(estim_z["dist"])
    

    def get_groupe_batiment_id(self)->int:
        """
        Renvoie l'identifiant du groupe de bâtiments
        """
        if self.groupe_batiment is not None:
            return self.groupe_batiment.identifiant
        raise ValueError(f"Le bâtiment {self.identifiant} n'est associé à aucun groupe de bâtiment")
        
    def get_z_mean(self)->float:
        if self.groupe_batiment is not None:
            return self.groupe_batiment.estim_z
        raise ValueError(f"Le bâtiment {self.identifiant} n'est associé à aucun groupe de bâtiment")
    

    def set_voisins(self):
        segments = self.get_segments()
        for i in range(1, len(segments)-1):
            g1 = segments[i]
            g0 = segments[i-1]
            g2 = segments[i+1]
            g1.voisin_1 = g0
            g1.voisin_2 = g2
            g0.voisin_2 = g1
            g2.voisin_1 = g1
        segments[0].voisin_1 = segments[-1]
        segments[-1].voisin_2 = segments[0]


    def create_segments(self)->None:
        x, y = self.geometrie_image.exterior.xy
        segments:List[LineString] = []
        for i in range(len(x)-1):
            linestring = LineString([[x[i], y[i]], [x[i+1], y[i+1]]])
            segments.append(Segment(linestring, self.mnt, self.shot, self))
        self.segments = segments
        self.set_voisins()


    def get_image(self)->str:
        return self.shot.image
    
    def compute_iou(self, batiment_2:Batiment)->float:
        footprint_1 = self.get_geometrie_terrain()
        footprint_2 = batiment_2.get_geometrie_terrain()
        intersection_area = intersection(footprint_1, footprint_2).area
        union_area = union(footprint_1, footprint_2).area
        return intersection_area / union_area
    
    def get_segments(self)->List[Segment]:
        return self.segments
    

    def create_numpy_array(self, dx:float=0, dy:float=0):

        nb_segments = len(self.segments)

        
        # Dans un premier tableau numpy, on met les coordonnées des extrémités des goutières en coordonnées du monde
        array = np.zeros((nb_segments, 4))
        for i, segment in enumerate(self.segments):
            world_line = segment.world_line
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
        self.array = array
        self.u = u
        self.barycentre = barycentre
        self.equation_droite = equation_droite
        self.d_max = d_max

    def get_segment_i(self, i:int)->Segment:
        return self.segments[i]
    
    def distance_sommet(self, point:Point):
        sommet = self.shot.get_sommet()
        return np.sqrt((point.x-sommet.x)**2 + (point.y-sommet.y)**2)
    

    def get_points_samon(self)->List[Point, float]:
        geometry_buffer = buffer(self.geometrie_terrain, -2)
        if isinstance(geometry_buffer, Polygon) and not geometry_buffer.is_empty:
            dictionnaire = []
            x, y = geometry_buffer.exterior.coords.xy
            for i in range(len(x)):
                point = Point(x[i], y[i])
                distance = self.distance_sommet(point)
                dictionnaire.append({"point":point, "distance":distance, "shot":self.shot})
                
            return dictionnaire

        else:
            return None