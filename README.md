# ImageLab — Image Processing Microservice

Production-oriented microservice for asynchronous image processing, designed as part of a distributed system.

Built to handle high-load image pipelines with clear separation of responsibilities and scalability in mind.

---

## 🚀 What This Is

This service is responsible for:

- image transformation and processing
- asynchronous job handling
- integration with a larger microservice-based system

It was developed as part of a real production platform and reflects practical architectural decisions rather than a demo project.

---

## 🧠 Why It Exists

In the original system, image processing was tightly coupled with a monolithic application, which created:

- performance bottlenecks
- limited scalability
- high failure impact

This service extracts image processing into an isolated component with:

- independent scaling
- fault isolation
- asynchronous execution

---

## 🏗 Architecture

Core design principles:

- **Microservice isolation** — single responsibility (image processing only)
- **Asynchronous processing** — via message queue (RabbitMQ)
- **Stateless workers** — horizontal scalability
- **Decoupling from legacy system** — clean integration layer

High-level flow:

1. Request is sent to the system
2. Task is pushed into a queue
3. Worker processes the image
4. Result is returned or stored

---

## ⚙️ Tech Stack

- Python
- FastAPI
- RabbitMQ
- Docker

---

## 🔑 Key Design Decisions

### 1. Asynchronous processing over sync APIs
Image processing is resource-intensive and unpredictable in duration.  
Queue-based execution prevents blocking and improves system stability.

### 2. Service isolation
Processing logic is fully separated from business logic.  
This reduces coupling and allows independent scaling.

### 3. Horizontal scalability
Workers can be scaled independently depending on load.

---

## ⚖️ Trade-offs

- Added system complexity due to message queues
- Eventual consistency instead of immediate results
- Requires monitoring and queue management

---

## 🧪 Running Locally

```bash
docker-compose up --build
