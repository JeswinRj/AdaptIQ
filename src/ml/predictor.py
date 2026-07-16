"""Load the trained Decision Tree once and predict content_level."""
import joblib

from src.preprocessing.features import encode_for_ml

_cache = {}


def load_model(model_path):
    key = str(model_path)
    if key not in _cache:
        _cache[key] = joblib.load(model_path)
    return _cache[key]


def predict_content_level(features: dict, model_path) -> str:
    """features: the feature dictionary from build_feature_dict."""
    bundle = load_model(model_path)
    vector = encode_for_ml(features)
    return str(bundle["model"].predict([vector])[0])
