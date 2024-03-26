import shapely

class Polygon:

    def __init__(self, id, segments) -> None:
        self.segments = segments
        self.id = id

    def relier_segments(self):
        for segment in self.segments:
            segment.set_poly(self)

    def possede_segment(self, segmentQuery):
        for segment in self.segments:
            if segment.egal(segmentQuery.P0, segmentQuery.P1):
                return segment
        return None

    def replace(self, segments_a_supprimer, nouveaux_segments):
        segments = []
        ajoute = False
        for segment in self.segments:
            if segment in segments_a_supprimer:
                if not ajoute:
                    for s in nouveaux_segments:
                        segments.append(s)
                    ajoute = True
            else:
                segments.append(segment)
        self.segments = segments

    def set_segments(self, segments):
        self.segments = segments

    def supprimer(self, segments_a_supprimer):
        segments = []
        for segment in self.segments:
            
            if not self.in_liste(segment, segments_a_supprimer):
                segments.append(segment)
            
        self.segments = segments

    def in_liste(self, segment, liste):
        for s in liste:
            if s.egal(segment.P0, segment.P1):
                return True
        return False

    
    def get_segment_par_extremite(self, P, segment):
        for s in self.segments:
            if s != segment:
                if s.P0 == P or s.P1 == P:
                    return s

    def make_valid(self, polygon):
        polygon = shapely.make_valid(polygon)

        if isinstance(polygon, shapely.MultiPolygon):
            polygones = []
            for p in list(polygon.geoms):
                polygones.append(p)
        elif isinstance(polygon, shapely.Polygon):
            polygones = [polygon]
        elif isinstance(polygon, shapely.LineString):
            polygones = []
        elif isinstance(polygon, shapely.GeometryCollection):
            polygones = []
            for p in list(polygon.geoms):
                if isinstance(p, shapely.Polygon):
                    polygones.append(p)
        else:
            print("cas non traité : ", polygon)
            polygones = []
        return polygones


    def export_shapely(self):
        points = []
        P0_init = self.segments[0].P0
        points.append(P0_init)
        P1 = self.segments[0].get_autre_extremite(P0_init)
        points.append(P1)
        segment_actuel = self.segments[0]
        iteration = 0
        while P1 != P0_init and iteration < 500:
            segment_suivant = self.get_segment_par_extremite(P1, segment_actuel)
            autre_extremite = segment_suivant.get_autre_extremite(P1)
            points.append(autre_extremite)

            P1 = autre_extremite
            segment_actuel = segment_suivant
            iteration += 1
        
        polygon = shapely.Polygon(points)
        if not polygon.is_valid:
            polygones = self.make_valid(polygon)
        else:
            polygones = [polygon]
        return polygones



