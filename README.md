# Enterprise RAG Platform

This repository contains a production-ready, multi-tenant Retrieval-Augmented Generation (RAG) system. The platform allows users to upload private documents and query them using generative AI, with strict data isolation, asynchronous processing, and full system observability.

## System Architecture & Tech Stack

The application is built using a microservices architecture orchestrated via Docker Compose:

* **API:** FastAPI (Python) for routing, authentication, and serving requests.
* **Worker:** Celery for asynchronous document ingestion (chunking & embedding).
* **Metadata Database:** PostgreSQL for managing user accounts and document status.
* **Vector Database:** Qdrant for storing and querying text embeddings.
* **Cache & Message Broker:** Redis for caching LLM responses and queueing Celery tasks.
* **Observability:** Prometheus (metrics scraping) and Grafana (dashboard visualization).
* **Embeddings:** `all-MiniLM-L6-v2` (SentenceTransformers).

## Key Features Implemented
* **Strict Multi-Tenancy:** All vector searches and database queries are hard-filtered by `tenant_id` via JWT payloads to ensure complete data isolation.
* **Async Ingestion:** Document processing doesn't block the API. Files are handed off to a Celery worker, and clients can poll the `/status` endpoint.
* **Response Caching:** Repeated queries are cached in Redis with a 1-hour TTL, verified via custom `X-Cache-Hit` headers to reduce LLM costs.
* **Auto-Provisioned Monitoring:** Grafana automatically spins up with a pre-configured dashboard tracking request latency, traffic, and custom AI token usage metrics.

---

## Local Setup Instructions

### 1. Configure Environment Variables
You need to set up your local environment variables before building the containers. 
Copy the provided example file to create your active `.env` file:
```bash
cp .env.example .env

```

*(Open the `.env` file and fill in any placeholder passwords or API keys as needed).*

### 2. Build and Start the Containers

Make sure Docker daemon is running on your machine, then execute:

```bash
docker-compose up --build -d

```

This will download the necessary images, build the custom API and Worker images, and start all 7 services in the background. It may take a few minutes the first time as it downloads the NLP embedding model.

### 3. Verify Health

Check that all containers are healthy:

```bash
docker-compose ps

```

Alternatively, you can hit the health check endpoint in your browser: `http://localhost:8000/health`

---

## How to Use the API

You can test the entire flow using the automatically generated Swagger UI by navigating to:
**👉 http://localhost:8000/docs**

### Standard Testing Flow:

1. **Register/Login:** * `POST /auth/register` to create an account.
* `POST /auth/login` to get your JWT access token. (Click the "Authorize" padlock in Swagger UI and paste your token).


2. **Upload a Document:**
* `POST /api/v1/documents` -> Upload a text file. You will receive a `document_id`.


3. **Check Status:**
* `GET /api/v1/documents/{document_id}/status` -> Wait for the status to change from `processing` to `completed`.


4. **Query the System:**
* `POST /api/v1/query` -> Ask a question. The API will search Qdrant, pass the context to the LLM, and return a synthesized answer with sources.



---

## Monitoring & Observability

The system exposes metrics that are automatically scraped and visualized.

* **Grafana Dashboard:** `http://localhost:3000`
* **Login:** `admin` / `admin`
* Navigate to *Dashboards -> General -> RAG API Metrics* to view real-time traffic, latency, and AI token usage.


* **Prometheus Targets:** `http://localhost:9090`
* **Raw Metrics Endpoint:** `http://localhost:8000/metrics`

---

## Running Tests

To verify the core API logic, a test suite is included in the `/tests` directory.
If you are running locally (with the required pip packages installed), you can execute:

```bash
pytest tests/

```

## Shutting Down

To stop the application and clean up the containers:

```bash
docker-compose down

```
