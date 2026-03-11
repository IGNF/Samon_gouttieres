from v2.prediction import Prediction


def traiter_lissage(prediction:Prediction)->Prediction:
    prediction.lisser_geometries()
    return prediction