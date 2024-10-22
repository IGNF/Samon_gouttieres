from __future__ import annotations
from shapely import Polygon, LineString, Point, MultiPolygon
import numpy as np
from typing import List
from v2.shot import Shot, MNT
from numpy import linalg as LA
from shapely.validation import make_valid

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


        self._marque = False
        self.groupe_batiment = None # Groupe de bâtiment auquel appartient ce bâtiment


    def lisser_geometries(self):
        """
        Lisse les polygones pour qu'un segment corresponde à un côté de bâtiment (et non pas à un morceau de côté de bâtiment)
        """

        # On divise le polygone en un ensemble de lignes
        x, y = self.geometrie_image.exterior.xy
        segments:List[LineString] = []
        for i in range(len(x)-1):
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