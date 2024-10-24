import numpy as np
from shapely import LineString

class Segment:

    def __init__(self, P0, P1, immobile=False) -> None:
        self.P0 = P0
        self.P1 = P1
        self.polygones = []
        self.immobile = immobile
        
    def __str__(self) -> str:
        return "({}, {})".format(self.P0, self.P1)

    def egal(self, P0, P1):
        if (self.P0 == P0 and self.P1 == P1) or (self.P0 == P1 and self.P1 == P0):
            return True
        return False

    def set_poly(self, polygone):
        self.polygones.append(polygone)


    def get_u(self):
        u = np.array([[self.P1.x-self.P0.x], [self.P1.y-self.P0.y]])
        return u / np.linalg.norm(u)

    def to_linestring(self):
        return LineString([[self.P0.x, self.P0.y], [self.P1.x, self.P1.y]])

    def contigu(self, s):
        if self.P0 == s.P0 or self.P0 == s.P1 or self.P1 == s.P0 or self.P1 == s.P1:
            return True
        return False

    def get_autre_extremite(self, P):
        if P == self.P0:
            return self.P1
        elif P == self.P1:
            return self.P0
        return None


    
