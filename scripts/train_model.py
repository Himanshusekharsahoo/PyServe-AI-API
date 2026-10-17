"""Train and evaluate the UCI binary sentiment model reproducibly."""

import argparse
import tempfile
import urllib.request
import zipfile
from pathlib import Path

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    precision_recall_fscore_support,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

DATA_URL = (
    "https://archive.ics.uci.edu/static/public/331/" "sentiment+labelled+sentences.zip"
)
DATASET_DIR = "sentiment labelled sentences/"
FILES = ("amazon_cells_labelled.txt", "imdb_labelled.txt", "yelp_labelled.txt")


def train(dataset_dir: Path, artifact_path: Path) -> dict:
    texts, labels = [], []
    for filename in FILES:
        with (dataset_dir / filename).open(encoding="utf-8") as source:
            for line in source:
                text, label = line.rstrip("\n").rsplit("\t", 1)
                texts.append(text)
                labels.append("positive" if label == "1" else "negative")

    x_train, x_test, y_train, y_test = train_test_split(
        texts, labels, test_size=0.2, random_state=42, stratify=labels
    )
    model = Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True),
            ),
            ("classifier", LogisticRegression(max_iter=1000, random_state=42)),
        ]
    )
    model.fit(x_train, y_train)
    predicted = model.predict(x_test)
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_test,
        predicted,
        labels=["negative", "positive"],
        average="binary",
        pos_label="positive",
    )
    metrics = {
        "train_size": len(x_train),
        "test_size": len(x_test),
        "accuracy": accuracy_score(y_test, predicted),
        "precision_positive": precision,
        "recall_positive": recall,
        "f1_positive": f1,
        "confusion_matrix_labels_negative_positive": confusion_matrix(
            y_test, predicted, labels=["negative", "positive"]
        ).tolist(),
    }
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, artifact_path)

    import hashlib

    hasher = hashlib.sha256()
    with artifact_path.open("rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    metrics["model_sha256"] = hasher.hexdigest()
    return metrics


def safe_extract_zip(zipped: zipfile.ZipFile, target_dir: Path) -> None:
    """Safely extract all members from a zip archive, preventing path traversal."""
    resolved_target = target_dir.resolve()
    for member in zipped.infolist():
        dest = (resolved_target / member.filename).resolve()
        if not str(dest).startswith(str(resolved_target)):
            raise ValueError(
                f"Path traversal detected in zip archive member: {member.filename}"
            )
    zipped.extractall(target_dir)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset-dir", type=Path, help="Directory with original UCI .txt files"
    )
    parser.add_argument("--output", type=Path, default=Path("models/sentiment.pkl"))
    args = parser.parse_args()
    if args.dataset_dir:
        print(train(args.dataset_dir, args.output))
    else:
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "uci.zip"
            urllib.request.urlretrieve(DATA_URL, archive)
            with zipfile.ZipFile(archive) as zipped:
                safe_extract_zip(zipped, Path(temp))
            print(train(Path(temp) / DATASET_DIR, args.output))


if __name__ == "__main__":
    main()
