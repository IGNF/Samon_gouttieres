from v2.prediction import Prediction
from v2.groupe_batiments import GroupeBatiments


def traiter_lissage(prediction:Prediction)->Prediction:
    prediction.lisser_geometries()
    return prediction


def compute_ground_geometrie(prediction:Prediction)->Prediction:
    prediction.compute_ground_geometry()
    return prediction

def compute_estim_z(groupe_batiment:GroupeBatiments)->GroupeBatiments:
    groupe_batiment.compute_z()
    return groupe_batiment