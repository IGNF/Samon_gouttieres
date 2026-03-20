from v2.prediction import Prediction
from v2.groupe_batiments import GroupeBatiments
from v2.groupe_pate_maisons import GroupePatesMaisons
from typing import List


def traiter_lissage(prediction:Prediction)->Prediction:
    prediction.lisser_geometries()
    return prediction


def compute_ground_geometrie(groupe_pate_maison:GroupePatesMaisons)->GroupePatesMaisons:
    groupe_pate_maison.compute_ground_geometry()
    return groupe_pate_maison

def compute_estim_z(groupe_batiment:GroupeBatiments)->GroupeBatiments:
    groupe_batiment.compute_z()
    return groupe_batiment

def create_segments(groupe_batiment:GroupeBatiments)->GroupeBatiments:
    groupe_batiment.create_segments()
    return groupe_batiment


def load_predictions(prediction:Prediction)->Prediction:
    prediction.read_file()
    return prediction

def create_predictions(args)->Prediction:
    shot, path, mnt, emprise = args
    prediction = Prediction(shot, path, mnt, emprise)
    prediction.associate_batiment_pate()
    return prediction

def compute_pate_maison_ground_geometrie(prediction:Prediction)->Prediction:
    prediction.compute_ground_geometry_pate_maison()
    return prediction

def compute_pate_maisons_association(args):
    prediction:Prediction = args[0]
    predictions:List[Prediction] = args[1]
    prediction.association_pates_maisons(predictions)
    return prediction