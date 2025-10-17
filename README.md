# ⚙️ PyServe AI API  
**Lightweight ML Model Serving API Template for Fast Deployments**

PyServe AI API is a minimal yet production-ready backend designed for serving machine learning models over RESTful endpoints. Built with **FastAPI 3.x**, it includes authentication, automated testing, and Dockerized deployment — making it ideal for quickly deploying regression, classification, or NLP models in production environments.

---

## 📘 Overview

PyServe AI API provides a clean and scalable architecture for model inference services. It minimizes boilerplate code while retaining production-quality practices such as **auth security**, **type safety**, and **CI/CD** integration.

### ✅ Ideal Use Cases
- Hosting scikit-learn, PyTorch, or TensorFlow models  
- Building REST APIs for NLP or image inference  
- Learning ML-API design and CI/CD integration  

---

## 🚀 Features

- ⚡ **Fast Inference Endpoints** – Asynchronous FastAPI routes for quick predictions  
- 🔒 **API Key & JWT Authentication** – Secure endpoint access for client applications  
- 🧪 **Built-In Testing** – Includes `pytest`, `mypy`, and `flake8` for type-safe, clean code  
- 🐳 **Dockerized & CI-Ready** – GitHub Actions workflow pre-configured for continuous deployment  
- 🔁 **Customizable Model Service** – Plug and play scikit-learn, PyTorch, or TensorFlow models  
- 📊 **Logging & Monitoring** – Uvicorn middleware for detailed request and response logs  

---

## 🏗️ Tech Stack

| Component     | Tools & Libraries                          |
|--------------|---------------------------------------------|
| Language      | Python 3.11                                 |
| Framework     | FastAPI                                     |
| Data Models   | Pydantic                                    |
| Server        | Uvicorn                                     |
| Deployment    | Docker · Poetry                             |
| Testing       | pytest · mypy · flake8                      |
| CI/CD         | GitHub Actions                              |

---

## ⚙️ Installation

### 1. Clone the Repository
```bash
git clone https://github.com/Himanshusekharsahoo/PyServe-AI-API.git
cd PyServe-AI-API
```

### 2. Install Dependencies
```bash
poetry install
```

### 3. Run the Application
```bash
uvicorn app.main:app --reload
```

Once running, access the interactive API documentation at:  
👉 [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🧩 Usage

### Step-by-Step

1. **Place Model File**  
   Add your pre-trained model under the `models/` directory  
   Example: `models/sentiment.pkl`

2. **Configure Model Logic**  
   Edit `app/services/model_service.py`:
   ```python
   def load_model():
       with open("models/sentiment.pkl", "rb") as f:
           return pickle.load(f)

   def predict(input_text: str):
       result = model.predict([input_text])
       return {"sentiment": result, "confidence": 0.93}
   ```

3. **Start Server**
   ```bash
   uvicorn app.main:app
   ```

4. **Test Endpoint**
   - **Endpoint:** `POST /predict`  
   - **Request JSON:**
     ```json
     {
       "text": "The product quality was excellent!"
     }
     ```
   - **Response:**
     ```json
     {
       "sentiment": "Positive",
       "confidence": 0.93
     }
     ```

---

---

## 🧠 Endpoint Workflow

1. Client sends request to `/predict`  
2. FastAPI validates input using Pydantic  
3. Model Service loads and runs prediction  
4. API returns JSON response with confidence score  

---

## 🔐 Authentication Overview

- Supports **API Key Authentication** for external clients  
- Optional **JWT Auth** for advanced use cases  
- Set `API_KEY` in `.env` or environment variables for secure deployment  

---

## 🧰 CI/CD Pipeline

- ✅ **Lint & Type Check** – `flake8` and `mypy` run on pre-commit  
- 🧪 **Test Automation** – `pytest` runs unit tests on push  
- 🐳 **Container Deployment** – Docker image built and published via GitHub Actions  

---

## 📊 Monitoring & Logging

- Integrated logging via **Uvicorn middleware**  
- Logs request payloads, status codes, and latency  
- Extendable to **Prometheus**, **Grafana**, or **ELK Stack**  

---

## 📚 Future Improvements

- Add **Prometheus** metrics for latency and throughput  
- Support **FastAPI background tasks** for batch inference  
- Enable serverless deployment on **Render**, **AWS Lambda**, or **Railway**  

---

## 🌟 Why PyServe AI API Stands Out

- Clean and scalable **API architecture**  
- Seamless **ML model serving** with DevOps integration  
- Professional-grade structure for your **backend portfolio**  
- Ideal for learning **Python APIs**, **FastAPI**, and **AI microservices**  

---

## 🧑‍💻 Contribution

Contributions are welcome!  
Open an issue for feature requests or bug fixes, then submit a pull request:

```bash
git checkout -b feature/your-feature
git commit -m "Add new model endpoint"
git push origin feature/your-feature
```

---

## 📜 License

This project is licensed under the **MIT License** — feel free to use, modify, and distribute.
```
