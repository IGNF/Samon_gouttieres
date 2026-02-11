from typing import List
from v2.groupe_batiments import GroupeBatiments, id_debug
from tqdm import tqdm
from v2.segments import SegmentImageOrientee
from shapely import Polygon, GeometryCollection, LineString, make_valid, MultiPolygon
from shapely.ops import polygonize_full
from shapely.geometry.base import BaseGeometry


class FermerBatimentEngine:

    seuil_ps = 0.8

    def __init__(self, groupes_batiments:List[GroupeBatiments]):
        self.groupes_batiments = groupes_batiments


    def fermer_deuxieme_tentative(self, groupe_batiment:GroupeBatiments):
        """
        Deuxième tentative pour fermer les bâtiments qui ne veulent pas se fermer
        """

        # On récupère le bâtiment qui est le plus proche du nadir et le plus grand en surface
        batiment_principal = groupe_batiment.get_batiment_nearest_nadir()

        # Cas où il n'y a que de la BD Topo dans le groupe
        if batiment_principal is None:
            return
        

        if groupe_batiment.get_identifiant()==id_debug:
            print("batiment_principal : ", batiment_principal.shot.image, batiment_principal.identifiant)

        # On récupère tous les bâtiments issu de la même pva que le bâtiment principal
        batiments_principaux = groupe_batiment.get_all_bati_same_PVA(batiment_principal)

        polygones = []
        # Pour chaque bâtiment, on va récupérer sa géométrie terrain et l'ajouter à polygones
        for batiment_principal in batiments_principaux:

            segments:List[SegmentImageOrientee] = []

            # On calcule l'altitude moyenne des segments. Cela servira à fixer une altitude aux segments dont le calcul d'intersection de plans a échoué
            altitudes_moyennes = []
            for segment in batiment_principal.get_segments_orientes():
                groupe_segment = groupe_batiment.get_groupe_segments_one_segment(segment)
                if groupe_segment is not None and groupe_segment.is_valid():
                    altitude_moyenne = groupe_segment.altitude_moyenne()
                    if altitude_moyenne is not None:
                        altitudes_moyennes.append(altitude_moyenne)
                        segment.estim_z_bati_ferme = altitude_moyenne
            if len(altitudes_moyennes)==0:
                continue
            altitude_moyenne_bati = sum(altitudes_moyennes)/len(altitudes_moyennes)

            # Pour chaque segment, on calcule sa projection au sol. 
            # On utilise en priorité l'altitude moyenne du résultat de l'intersection de plans
            # Puis l'altitude de ses voisins
            # Et sinon l'altitude moyenne du bâtiment
            for segment in batiment_principal.get_segments_orientes():
                segment.compute_ground_geometry_fermer_bati_2(altitude_moyenne_bati)
                segments.append(segment)
            
            # Pour chaque segment, on calcule la pseudo-intersection avec ses deux segments voisins
            segments = [segments[-1]] + segments + [segments[0]]
            adjusted_segments = []
            for i in range(1, len(segments)-1):
                p1 = segments[i].compute_pseudo_intersection(segments[i-1])
                p2 = segments[i].compute_pseudo_intersection(segments[i+1])
                adjusted_segments.append(LineString([p1, p2]))

            # On transforme l'ensemble de segments en polygones
            geometrie_fermee, _, _, invalids = polygonize_full(adjusted_segments)
       
            # Si cela ne marche pas, c'est sans doute parce que le Polygone créé serait invalide
            # Donc on applique make_valid sur le polygone
            if len(geometrie_fermee.geoms)==0:
                if isinstance(invalids, GeometryCollection) and len(invalids.geoms)>0:# généralement une collection de LineString
                    # Si c'est une collection de géométries, on ne prend que la première car c'est possible que les deux géométries représentent la même chose 
                    # On pourrait faire un peu plus propre
                    lines = invalids.geoms[0] 
                
                    if isinstance(lines, LineString):
                        geometrie_fermee = GeometryCollection(make_valid(Polygon(lines)))

            polygones.append(geometrie_fermee)

        # On récupère une GeometryCollection de Polygon
        groupe_batiment.geometrie_fermee = GeometryCollection(self.extract_polygons(GeometryCollection(polygones)))



    def extract_polygons(self, geom:BaseGeometry)->List[Polygon]:
        """
        Récupère récursivement tous les polygones contenus dans une géométrie.
        - geom : instance shapely.geometry (Polygon, MultiPolygon, GeometryCollection, etc.)
        - retourne une liste de Polygons
        """
        polygons = []
        
        if isinstance(geom, Polygon):
            polygons.append(geom)
        
        elif isinstance(geom, MultiPolygon):
            # Décomposer en polygones simples
            for poly in geom.geoms:
                polygons.append(poly)
        
        elif isinstance(geom, GeometryCollection):
            # Appel récursif pour chaque géométrie de la collection
            for subgeom in geom.geoms:
                polygons.extend(self.extract_polygons(subgeom))
        
        # Ignorer les autres types (Point, LineString, etc.)
        return polygons


    def run(self):

        print("On récupère pour chaque groupe bâtiment les groupes de segments")
        for groupe_batiment in tqdm(self.groupes_batiments):
            groupe_batiment.update_groupe_segments()  

        print("On ajuste pour chaque bâtiment les intersections des bords de toit")
        fermeture_valide = [0,0]
        for groupe_batiment in tqdm(self.groupes_batiments):
            for groupe_segment in groupe_batiment.groupes_segments:
                if groupe_segment.is_valid():
                    # Deux segments ne doivent pas être presque parallèle pour être considérés comme voisins par la suite
                    groupe_segment.update_voisins_ps(FermerBatimentEngine.seuil_ps)
            
            self.fermer_deuxieme_tentative(groupe_batiment)
            if groupe_batiment.geometrie_fermee_valide():
                groupe_batiment.set_methode_fermeture("Photogrammetrie")
                fermeture_valide[0]+=1
            else:
                fermeture_valide[1]+=1
                groupe_batiment.projection_FFL()

        print(f"Fermeture projection : {fermeture_valide[0]}")
        print(f"Fermeture ratée : {fermeture_valide[1]}")

            
            
    