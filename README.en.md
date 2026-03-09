<div align="center">

# CHAT-BOT-AI

_Elevate Conversations, Unlock Knowledge Instantly_

![GitHub last commit](https://img.shields.io/github/last-commit/LoiNV68/Chat-bot-AI?style=flat)
![GitHub top language](https://img.shields.io/github/languages/top/LoiNV68/Chat-bot-AI?style=flat)
![GitHub language count](https://img.shields.io/github/languages/count/LoiNV68/Chat-bot-AI?style=flat)

_Built with the following tools and technologies:_

![JSON](https://img.shields.io/badge/JSON-%23000000.svg?style=flat-square&logo=JSON&logoColor=white)
![Markdown](https://img.shields.io/badge/Markdown-%23000000.svg?style=flat-square&logo=markdown&logoColor=white)
![npm](https://img.shields.io/badge/npm-%23CB3837.svg?style=flat-square&logo=npm&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-%23D71F00.svg?style=flat-square&logo=sqlalchemy&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-%23323330.svg?style=flat-square&logo=javascript&logoColor=%23F7DF1E)
![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat-square&logo=fastapi)
![LangChain](https://img.shields.io/badge/LangChain-%23005571.svg?style=flat-square&logo=langchain)
<br>
![React](https://img.shields.io/badge/React-%2320232a.svg?style=flat-square&logo=react&logoColor=%2361DAFB)
![Pytest](https://img.shields.io/badge/Pytest-%230A9EDC.svg?style=flat-square&logo=pytest&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-%230db7ed.svg?style=flat-square&logo=docker&logoColor=white)
![Python](https://img.shields.io/badge/Python-3670A0?style=flat-square&logo=python&logoColor=ffdd54)
![TypeScript](https://img.shields.io/badge/TypeScript-%23007ACC.svg?style=flat-square&logo=typescript&logoColor=white)
![Vite](https://img.shields.io/badge/Vite-%23646CFF.svg?style=flat-square&logo=vite&logoColor=white)
![Pandas](https://img.shields.io/badge/pandas-%23150458.svg?style=flat-square&logo=pandas&logoColor=white)

</div>

<div align="center">
  <strong>[Tiếng Việt](README.md) | [English](README.en.md)</strong>
</div>

---

## Table of Contents

- [Overview](#overview)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Usage (Production Deployment)](#usage-production-deployment)
  - [Testing (Local Development Environment)](#testing-local-development-environment)
- [Architecture](#architecture)

---

## Overview

**chat-bot-ai** is a comprehensive platform for developing secure, scalable AI chatbots tailored for educational institutions. It integrates document management, vector search, and conversational AI in a containerized application architecture, allowing seamless deployment and real-time interaction.

### Why choose chat-bot-ai?

This project empowers developers to build intelligent offline university chatbots with features such as:

- 🧩 **Modularity**: A modular microservices architecture supporting flexible scaling (Multi-stage NGINX Build, Ultra-lightweight Frontend ~25MB).
- 🚀 **Performance**: RAG (Retrieval-Augmented Generation) for accurate, context-aware answers (Deterministic RAG, 100% absolute accuracy).
- 🗄️ **Document Management**: Advanced document ingestion, normalization, and search capabilities (Preserves Markdown Tables format).
- 🔒 **Security**: Strong user authentication and role-based access control.
- 💬 **Conversational AI**: Real-time chat with continuous feedback and learning loops.
- ⚙️ **Automation**: Automated startup scripts streamlining development and testing (Integrated PaddleOCR for auto-correcting stuck characters).

---

## Getting Started

### Prerequisites

This project requires the following dependencies:

- **Programming Languages:** Python 3.11, TypeScript
- **Package Managers:** Pip, Npm
- **Container Environment:** Docker, Docker Compose

### Installation

Build chat-bot-ai from source and install libraries:

1. Clone the repository:

```bash
> git clone https://github.com/LoiNV68/Chat-bot-AI.git
```

2. Navigate into the project directory:

```bash
> cd Chat-bot-AI
```

### Usage (Production Deployment)

Using Docker:

```bash
> docker-compose up -d --build
```

_The system will automatically build the Frontend & Backend, load the Database (Postgres, Qdrant), and start._

- **Chatbot Interface:** `http://localhost:5173` (or `http://localhost:80`)

### Testing (Local Development Environment)

The project is configured to run in Hybrid mode: Database on Linux (WSL) and Code running directly on Windows.

1. Start the Database services (Using Docker on any machine):

```bash
> docker-compose -f docker-compose.db.yml up -d
```

2. Start the Backend & Frontend (Windows Terminal):

```powershell
> .\run.ps1
```

---

## Architecture

Please refer to our technical analysis and architecture documentation:

- [MASTER_DESIGN.md](./MASTER_DESIGN.md): Detailed Data Pipeline and Offline DPO Training Strategy.
- [SERVICE_BASE.md](./backend/SERVICE_BASE.md): Directory structure, Backend workflows, and RAG Engine.
- [REQUIREMENT.md](./backend/REQUIREMENT.md): System requirements specification.
