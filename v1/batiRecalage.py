import geopandas as gpd
from shapely import Polygon, convex_hull, MultiPoint, MultiLineString


class Bati:

    def __init__(self, id_origine) -> None:
        self.id_origine = id_origine
        self.id = None
        self.marque = False
        self.homologue = []
        self.TX = None
        self.TY = None
        self.a = None
        self.b = None

    
    def add_homologue(self, homologue):
        if homologue not in self.homologue:
            self.homologue.append(homologue)





class Bati_2D(Bati):
    def __init__(self, polygon, id_origine, ) -> None:
        super().__init__(id_origine)

        self.polygon = polygon
        self.id_origine = id_origine

        self.nb_points = 0
        self.mean = 0
        self.res_max = 0

    def emprise_sol(self):
        return self.polygon

    
    def linestring(self):
        return self.polygon.boundary
        

        


class Bati_gouttieres_2D(Bati):

    def __init__(self, segments, id_origine) -> None:
        self.segments = segments
        self.id_origine = id_origine
        self.homologue = []

        self.id = None
        self.marque = False

        self.compute_polygone()


    def compute_polygone(self):
        points = []
        for s in self.segments:
            points.append(s[0])
            points.append(s[1])



        self.polygon = convex_hull(MultiPoint(points))

    def emprise_sol(self):
        return self.polygon


    def linestring(self):
        points = []
        for s in self.segments:
            points.append([s[0], s[1]])
        return MultiLineString(points)




def charger_bati(chemin, clef_id):
    batis = []
    gdf = gpd.read_file(chemin)
    for geometry in gdf.iterfeatures():
        id = geometry["properties"][clef_id]
        if geometry["geometry"]["type"] == "Polygon":
            points = geometry["geometry"]["coordinates"]
        else:
            points = geometry["geometry"]["coordinates"][0][0]

        try:
            bati = Bati_2D(Polygon(points), id)
            batis.append(bati)
        except:
            bati = Bati_2D(Polygon(points[0]), id)
            batis.append(bati)

    return batis


def charger_bati_gouttieres(chemin, clef_id, liste_id):
    batis = []
    gdf = gpd.read_file(chemin)
    for geometry in gdf.iterfeatures():
        id = geometry["properties"]["id"]
        segment = geometry["geometry"]["coordinates"]
        liste_id[id].append(segment)
    

    for i, liste in enumerate(liste_id):
        if len(liste)>0:
            bati = Bati_gouttieres_2D(liste, i)
            batis.append(bati)
    return batis


def charger_bati_gouttieres_rapide(chemin, clef_id, liste_id):
    batis = []
    gdf = gpd.read_file(chemin)
    for geometry in gdf.iterfeatures():
        id = geometry["properties"]["id"]
        if geometry["geometry"]["type"] == "LineString":
            segment = [geometry["geometry"]["coordinates"]]
        else:
            segment = geometry["geometry"]["coordinates"]
        bati = Bati_gouttieres_2D(segment, id)
        bati.TX = geometry["properties"]["TX"]
        bati.TY = geometry["properties"]["TY"]
        bati.a = geometry["properties"]["a"]
        bati.b = geometry["properties"]["b"]
        bati.nb_points = geometry["properties"]["nb_points"]
        bati.mean = geometry["properties"]["mean"]
        bati.res_max = geometry["properties"]["res_max"]
        batis.append(bati)
    return batis
