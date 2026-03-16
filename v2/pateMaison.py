from __future__ import annotations
from shapely import Polygon, MultiPolygon
import numpy as np
from typing import List
from v2.shot import Shot, MNT
from shapely.validation import make_valid
from v2.batiment import Batiment



class PateMaison:

    identifiant_global = 0

    def __init__(self, geometrie:Polygon, shot:Shot, mnt:MNT):
        self.geometrie_image = geometrie
        self.shot = shot
        self.mnt = mnt
        self.identifiant:int = PateMaison.identifiant_global
        PateMaison.identifiant_global += 1

        self.batiments:List[Batiment] = []
        self.geometrie_terrain:Polygon = None
        self.homologues:List[PateMaison] = []

        self.id_groupe_pate_maison:int = None

        self._marque = False

    def add_batiment(self, batiment):
        self.batiments.append(batiment)

    def set_id_groupe_pate_maison(self, id):
        self.id_groupe_pate_maison = id
        for bati in self.batiments:
            bati.set_groupe_pate_maison_identifiant(id)


    def get_id_groupe_pate_maison(self):
        return self.id_groupe_pate_maison


    def compute_ground_geometry(self, estim_z=None)->None:
        """
        Calcule l'emprise au sol du pâté de maison, projeté sur un MNT
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

    def get_geometrie_terrain(self):
        return self.geometrie_terrain
    
    def get_identifiant(self):
        return self.identifiant
    
    def add_homologue(self, pm_homologue):
        if pm_homologue not in self.homologues:
            self.homologues.append(pm_homologue)

    def get_homologues(self)->List[PateMaison]:
        return self.homologues