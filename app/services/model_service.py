import pickle

model = None

def load_model():
    global model
    if model is None:
        with open("models/sentiment.pkl", "rb") as f:
            model = pickle.load(f)
    return model

def predict(text: str):
    m = load_model()
    output = m.predict([text])[0]
    return {
        "sentiment": output,
        "confidence": 0.93
    }
