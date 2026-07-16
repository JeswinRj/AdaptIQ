"""Train the Decision Tree content-level classifier (report §6.3).

Usage: python src/ml/train_model.py
Prints a real train/test evaluation and saves the model to src/ml/model.joblib.
"""
import sys
from pathlib import Path

import joblib
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import config
from src.data_ingestion import get_source
from src.preprocessing.features import (ML_FEATURE_COLUMNS, build_feature_dict,
                                        encode_for_ml)

CLASSES = ["basic", "intermediate", "advanced"]


def build_dataset(df):
    X, y = [], []
    for _, row in df.iterrows():
        feats = build_feature_dict(row.to_dict())
        X.append(encode_for_ml(feats))
        y.append(row["content_level"])
    return X, y


def main():
    df = get_source(config).load()
    if "content_level" not in df.columns:
        raise SystemExit("Training data needs a content_level label column.")
    X, y = build_dataset(df)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y)

    # max_depth capped for interpretability (a stated benefit in the report)
    model = DecisionTreeClassifier(max_depth=5, random_state=42)
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    acc = accuracy_score(y_test, preds)
    f1 = f1_score(y_test, preds, average="macro")
    print(f"Samples: {len(X)} (train {len(X_train)} / test {len(X_test)})")
    print(f"Test accuracy: {acc:.3f}")
    print(f"Macro F1:      {f1:.3f}")
    print(classification_report(y_test, preds))

    joblib.dump({"model": model, "feature_columns": ML_FEATURE_COLUMNS,
                 "classes": CLASSES}, config.MODEL_PATH)
    print(f"Saved model to {config.MODEL_PATH}")


if __name__ == "__main__":
    main()
