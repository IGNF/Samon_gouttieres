from typing import List
from v2.groupe_batiments import GroupeBatiments



class AmeliorationBDTopoEngine:

    seuil_iou = 0.3

    def __init__(self, groupes_batiments:List[GroupeBatiments]):
        self.groupes_batiments = groupes_batiments


    def run(self):
        for groupe_batiments in self.groupes_batiments:
            geometrie_amelioree = None
            origine = ""
            batiments_bd_topo, acquisition_plani = groupe_batiments.get_batiments_bd_topo()
            if batiments_bd_topo is None:
                groupe_batiments.set_geometrie_amelioree_bd_topo(geometrie_amelioree, origine)
                continue
            geometrie_fermee = groupe_batiments.get_geometrie_fermee()
            if not geometrie_fermee.is_valid:
                continue
            intersection = batiments_bd_topo.intersection(geometrie_fermee).area
            union = batiments_bd_topo.union(geometrie_fermee).area
            iou = intersection/union
            if iou > AmeliorationBDTopoEngine.seuil_iou:
                if acquisition_plani=="Photogrammétrie":
                    geometrie_amelioree = batiments_bd_topo
                    origine = "BD Topo"
                else:
                    geometrie_amelioree = geometrie_fermee
                    origine = "Samon"
            groupe_batiments.set_geometrie_amelioree_bd_topo(geometrie_amelioree, origine)


