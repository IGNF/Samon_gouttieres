from v2.prediction import Prediction


def traiter_lissage(prediction:Prediction)->Prediction:
    prediction.lisser_geometries()
    return prediction


def compute_ground_geometrie(prediction:Prediction)->Prediction:
    prediction.compute_ground_geometry()
    return prediction