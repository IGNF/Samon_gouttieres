from v2.batiment import Batiment, BatimentImageOrientee, BatimentBDTopo
from typing import List, Tuple
from v2.groupe_segments import GroupeSegments
from v2.segments import Segment
import numpy as np
from shapely import Point, Polygon, make_valid, GeometryCollection, LineString, MultiPolygon
from v2.shot import Shot
import statistics
from shapely.ops import polygonize_full
import geopandas as gpd


id_debug = 618


class GroupeBatiments:

    identifiant_global = 0

    def __init__(self, batiments:List[Batiment]):
        self.batiments = batiments
        self.batimentsImageOrientee = [b for b in self.batiments if isinstance(b, BatimentImageOrientee)]

        self.identifiant:int = GroupeBatiments.identifiant_global
        GroupeBatiments.identifiant_global += 1


        self.estim_z:float|None=None

        # A chaque bâtiment, on complète l'attribut qui indique à quel groupe de bâtiment il appartient
        for batiment in self.batiments:
            batiment.groupe_batiment = self

        self.groupes_segments:List[GroupeSegments] = []

        self.geometrie_fermee:Polygon = None

        self.nb_images_z_estim = -1 # Nombre d'images utilisées par Samon pour déterminer la hauteur du bâtiment

        self.methode_fermeture = None
        self.methode_estimation_hauteur = None
        self.geometrie_amelioree_bd_topo = None
        self.origine_geometrie_amelioree_bd_topo = None


    def set_methode_fermeture(self, methode:str):
        """
        Méthode de fermeture des bâtiments : photogrammétrie ou projection d'un bâtiment
        """
        self.methode_fermeture = methode

    def set_geometrie_amelioree_bd_topo(self, geometrie_amelioree_bd_topo:str, origine):
        """
        Méthode de fermeture des bâtiments : photogrammétrie ou projection d'un bâtiment
        """
        self.geometrie_amelioree_bd_topo = geometrie_amelioree_bd_topo
        self.origine_geometrie_amelioree_bd_topo = origine

    def get_geometrie_amelioree_bd_topo(self)->Polygon:
        return self.geometrie_amelioree_bd_topo

    def get_methode_fermeture(self)->str:
        return self.methode_fermeture

    def set_methode_estimation_hauteur(self, methode:str):
        """
        Méthode de fermeture des bâtiments : photogrammétrie ou projection d'un bâtiment
        """
        self.methode_estimation_hauteur = methode

    def get_methode_estimation_hauteur(self)->str:
        return self.methode_estimation_hauteur
    
    def get_batiments_bd_topo(self):
        batis = [b for b in self.batiments if isinstance(b, BatimentBDTopo)]
        if len(batis)==0:
            return None, None
        acquisition_plani = "Photogrammétrie"
        for b in batis:
            if b.acquisition_plani != "Photogrammétrie":
                acquisition_plani = "Divers"
        batis_geometries = [b.geometrie_terrain for b in batis]
        return MultiPolygon(batis_geometries), acquisition_plani

    def compute_z_mean(self):
        estim_z_sum = 0
        compte = 0
        i_max = min(100, len(self.batimentsImageOrientee)) # Pour certains groupes, on peut avoir 2000 bâtiments, ce qui est très long à traiter... 
        for i1 in range(i_max):
            for i2 in range(i1+1, i_max):
                b1 = self.batimentsImageOrientee[i1]
                b2 = self.batimentsImageOrientee[i2]
                if b1.shot.image != b2.shot.image:
                    score = b1.correlation_score(b2)
                    if score < 0.2:
                        estim_z_sum += b1.compute_estim_z(b2)["delta_z"]
                        compte += 1
        if compte==0:
            estim_z_final = None
        else:
            estim_z_final = estim_z_sum/compte
            if estim_z_final<0 or estim_z_final >= 20:
                estim_z_final = None
        if estim_z_final is None:
            return None
        centroid = self.batimentsImageOrientee[0].geometrie_terrain.centroid
        z = self.batimentsImageOrientee[0].mnt.get(centroid.x, centroid.y)
        return estim_z_final + z


    def compute_z_mean_v2(self)->Tuple[float, int]:
        i_max = min(100, len(self.batimentsImageOrientee)) # Pour certains groupes, on peut avoir 2000 bâtiments, ce qui est très long à traiter... 
        distances = []
        z_mean = []

        centroid = self.batimentsImageOrientee[0].geometrie_terrain.centroid
        z = self.batimentsImageOrientee[0].mnt.get(centroid.x, centroid.y)

        # Pour chaque couple de bâtiments
        for i1 in range(i_max):
            for i2 in range(i1+1, i_max):
                b1 = self.batimentsImageOrientee[i1]
                b2 = self.batimentsImageOrientee[i2]
                # Si les deux bâtiments n'appartiennent pas au même couple
                if b1.shot.image != b2.shot.image:
                    # On calcule l'estimation de hauteur pour chaque couple de bâtiments
                    distances_couple, z_mean_couple = b1.compute_z_mean(b2, z)
                    distances+=distances_couple
                    z_mean += z_mean_couple
        
        # On calcule une moyenne pondérée de la hauteur du bâtiment. Les poids correspondent à l'inverse de la distance entre les droites (parallaxe)
        sum = 0
        weight = 0
        
        centroid = self.batimentsImageOrientee[0].geometrie_terrain.centroid
        z = self.batimentsImageOrientee[0].mnt.get(centroid.x, centroid.y)

        if len(distances)==0:
            return z+10, 0
        for i in range(len(distances)):
            sum += z_mean[i] / distances[i]
            weight += 1/distances[i]
        
        # On vérifie que la hauteur du bâtiment est cohérente
        hauteur_bati = sum/weight - z
        if hauteur_bati > 0 and hauteur_bati < 20:
            return sum/weight, len(distances)
        else:
            return z+10, 0



    def get_nb_shots(self)->int:
        """
        Renvoie le nombre de pva sur lesquelles se trouvent le bâtiment
        """
        shots = []
        for batiment in self.get_batiments_images_orientees():
            shot = batiment.shot
            if shot not in shots:
                shots.append(shot)
        return len(shots)


    def update_geometry_terrain(self):
        for batiment in self.batiments:
            batiment.update_ground_geometry(self.estim_z)

    def get_identifiant(self)->int:
        return self.identifiant


    def create_segments(self)->None:
        for batiment in self.batiments:
            batiment.create_segments()
            batiment.create_numpy_array()

    def get_batiments(self)->List[Batiment]:
        return self.batiments
    
    def get_batiments_images_orientees(self)->List[BatimentImageOrientee]:
        return self.batimentsImageOrientee
    

    def update_groupe_segments(self)->None:
        groupes_segments:List[GroupeSegments] = []
        for batiment in self.batiments:
            for segment in batiment.get_segments():
                groupe_segments = segment.get_groupe_segments()
                if groupe_segments is not None and groupe_segments not in groupes_segments:
                    groupes_segments.append(groupe_segments)
        self.groupes_segments = groupes_segments


    def ajuster_intersection(self, seuil_ps=0.8):
        """
        nb_segments : nombre minimum de segments constituant un groupe de segments pour que le groupe soit considéré comme valide
        Dans la deuxième tentative de fermeture, il faut qu'il soit égal à un car c'est un groupe de segments constitué d'un seul segment
        """
        for groupe_segment in self.groupes_segments:
            if groupe_segment.is_valid():
                for voisin in groupe_segment.voisins:
                    if voisin.is_valid():
                        ps = groupe_segment.compute_produit_scalaire(voisin)
                        if ps < seuil_ps:
                            intersection_x, intersection_y = groupe_segment.intersection(voisin)
                            z1 = groupe_segment.calcul_z(intersection_x)
                            z2 = voisin.calcul_z(intersection_x)
                            z_mean = (z1+z2)/2
                            if not np.isnan(z_mean):
                                intersection = Point(intersection_x, intersection_y, z_mean)
                                # On ajoute le point d'intersection à l'attribut intersections de segment et de voisin
                                groupe_segment.ajouter_intersection(intersection, voisin)
                                voisin.ajouter_intersection(intersection, groupe_segment)

        for groupe_segment in self.groupes_segments:
            if len(groupe_segment.intersections)==1:
                i = groupe_segment.intersections[0]["point"]
                d1 = groupe_segment.distance_point(groupe_segment.p1, i)
                d2 = groupe_segment.distance_point(groupe_segment.p2, i)
                if d1 < d2:
                    groupe_segment.set_p1(i)
                else:
                    groupe_segment.set_p2(i)
                groupe_segment.calcule_a_b()
            
            elif len(groupe_segment.intersections)==2:
                i1 = groupe_segment.intersections[0]["point"]
                i2 = groupe_segment.intersections[1]["point"]

                c1, c2 = groupe_segment.p_proches_points(i1, i2)
                groupe_segment.set_p1(c1[1])
                groupe_segment.set_p2(c2[1])
                groupe_segment.calcule_a_b()

            elif len(groupe_segment.intersections)>2:
                

                i1 = groupe_segment.intersections[0]["point"]
                i2 = groupe_segment.intersections[1]["point"]

                c1, c2 = groupe_segment.p_proches_points(i1, i2)
                groupe_segment.set_p1(c1[1])
                groupe_segment.set_p2(c2[1])
                groupe_segment.calcule_a_b()

                intersections_sorted = groupe_segment.sort_by_intersection()
                for i in range(1, len(intersections_sorted)):
                    i1 = intersections_sorted[i-1]["intersection"]
                    i2 = intersections_sorted[i]["intersection"]
                    p1 = i1["point"]
                    p2 = i2["point"]

                    new_groupe_segments:GroupeSegments = GroupeSegments.from_p1_p2(groupe_segment.segments, p1, p2)
                
                    v0:GroupeSegments = i1["groupe_segments"]
                    v1:GroupeSegments = i2["groupe_segments"]
                    new_groupe_segments.voisins = [v0, v1]


                    self.replace_id_voisins(v0, groupe_segment, new_groupe_segments)
                    self.replace_id_voisins(v1, groupe_segment, new_groupe_segments)
                    self.groupes_segments.append(new_groupe_segments)
                groupe_segment._supprime = True


    def replace_id_voisins(self, groupe_segment:GroupeSegments, old_voisin:GroupeSegments, new_voisin:GroupeSegments)->None:
        if old_voisin in groupe_segment.voisins:
            groupe_segment.voisins.remove(old_voisin)

        if new_voisin not in groupe_segment.voisins:
            groupe_segment.voisins.append(new_voisin)

    
    def fermer_geometrie(self):
        # On récupère toutes les lignes valides
        linestrings = []
        for segment in self.groupes_segments:
            if not segment._supprime:
                linestrings.append(segment.get_geometrie())
        
        # On essaye de fermer la géométrie
        self.geometrie_fermee, _, _, invalids = polygonize_full(linestrings)
       
        # Si cela ne marche pas, c'est sans doute parce que le Polygone créé serait invalide
        # Donc on applique make_valid sur le polygone
        if len(self.get_geometrie_fermee().geoms)==0:
            if isinstance(invalids, GeometryCollection) and len(invalids.geoms)>0:# généralement une collection de LineString
                # Si c'est une collection de géométries, on ne prend que la première car c'est possible que les deux géométries représentent la même chose 
                # On pourrait faire un peu plus propre
                lines = invalids.geoms[0] 
            
                if isinstance(lines, LineString):
                    self.geometrie_fermee = GeometryCollection(make_valid(Polygon(lines)))
            


    def get_geometrie_fermee(self)->Polygon:
        return self.geometrie_fermee
    

    def get_point_samon(self)->Tuple[Point, Shot]:
        """
        Récupère les points avec lesquels on pourrait obtenir une évaluation de la hauteur du bâtiment avec samon
        """
        dictionnaires = []
        for batiment in self.get_batiments_images_orientees():
            dict_batiment = batiment.get_points_samon() 
            if dict_batiment is not None:
                dictionnaires += batiment.get_points_samon()   
        dictionnaires_tries = sorted(dictionnaires, key=lambda d: d['distance'])
        return dictionnaires_tries
    

    def get_shots(self):
        shots = []
        for batiment in self.get_batiments():
            shot = batiment.shot
            if shot not in shots:
                shots.append(shot)
        return shots
    

    def get_batiment_nearest_nadir(self)->BatimentImageOrientee:
        if len(self.batimentsImageOrientee)==0:
            return None
        batiment_min = None
        distance_min = 1e15

        x = []
        y = []
        # On récupère le barycentre des barycentre des batiments projetés
        for batiment in self.batimentsImageOrientee:
            if batiment.geometrie_terrain is not None:
                barycentre = batiment.geometrie_terrain.centroid
                x.append(barycentre.x)
                y.append(barycentre.y)
        centre = Point(statistics.mean(x), statistics.mean(y))

        for batiment in self.batimentsImageOrientee:
            # On calcule la distance entre le barycentre des barycentres et le sommet de prise de vue, en plani
            distance = batiment.distance_sommet(centre)
            # On conserve le bâtiment pour lequel la distance est minimale
            # S'il y a plusieurs bâtiments appartenant à la même prise de vue, alors on conserve celui avec la plus grande surface
            if distance < distance_min or (distance_min==distance and batiment.geometrie_terrain.area > batiment_min.geometrie_terrain.area):
                batiment_min = batiment
                distance_min = distance
        return batiment_min
    

    def get_groupe_segments_one_segment(self, segment:Segment)->GroupeSegments:
        for groupe_segments in self.groupes_segments:
            if segment in groupe_segments.segments:
                return groupe_segments
        return None

    def geometrie_fermee_valide(self)->bool:
        """
        La géométrie fermée est considérée comme valide si elle n'est pas vide et que sa surface est assez proche de celles des projections au sol des bâtiments
        """
        if self.get_geometrie_fermee() is None:
            return False
        # Si la géométrie fermée est vide, on renvoie faux
        if len(self.get_geometrie_fermee().geoms)==0:
            return False
        areas = []
        for batiment in self.batiments:
            if batiment.geometrie_terrain.area is not None:
                areas.append(batiment.geometrie_terrain.area)
        area_fermee = self.get_geometrie_fermee().area
        area_max = max(areas)
        ratio = area_fermee / area_max
        if self.get_identifiant()==id_debug:
            print(self.get_geometrie_fermee())
            print(areas)
            print("area_fermee, area_mediane, ratio : ", area_fermee, area_max, ratio)
        if ratio < 0.2:
            return False
        return True

    def get_all_bati_same_PVA(self, bati:Batiment)->List[Batiment]:
        """
        Renvoie tous les bâtiments du groupe issus de la même pva
        """
        batiments = []
        for b in self.batimentsImageOrientee:
            if b.shot==bati.shot:
                batiments.append(b)
        return batiments
    


    def projection_FFL(self):
        batiment_principal = self.get_batiment_nearest_nadir()

        # On récupère tous les bâtiments issu de la même pva que le bâtiment principal
        batiments_principaux = self.get_all_bati_same_PVA(batiment_principal)

        polygones = []
        for p in batiments_principaux:
            p.compute_ground_geometry()
            polygones.append(p.geometrie_terrain)

        self.geometrie_fermee = MultiPolygon(polygones)
        self.set_methode_fermeture("Projection")


    def get_reference_bati(self):
        shots = {}
        for batiment in self.get_batiments():
            shot = batiment.shot
            if shot.image not in shots.keys():
                shots[shot.image] = [batiment.geometrie_terrain]
            else:
                shots[shot.image].append(batiment.geometrie_terrain)
        
        gdf_max = None
        area_max = 0
        for value in shots.values():
            union = gpd.GeoDataFrame({"geometry":value}).union_all()
            if isinstance(union, Polygon):
                polygons = [union]
            else:
                polygons = list(union.geoms)
            gdf = gpd.GeoDataFrame(
                geometry=polygons,
                crs=2154
            )
            x0, y0, x1, y1 = gdf.total_bounds
            area = Polygon.from_bounds(x0, y0, x1, y1).area
            if area > area_max:
                area_max = area
                gdf_max = gdf
        return gdf_max
