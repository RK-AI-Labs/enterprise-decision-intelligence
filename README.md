# AI Template Python

> A modern, production-ready Python template for AI, Machine Learning, Data Science, and backend engineering projects.

![Python](https://img.shields.io/badge/Python-3.13-blue.svg)
![uv](https://img.shields.io/badge/Package%20Manager-uv-blueviolet)
![Ruff](https://img.shields.io/badge/Linter-Ruff-orange)
![Pytest](https://img.shields.io/badge/Testing-pytest-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## Overview

This repository provides a clean, reusable foundation for modern Python development.

It is designed to be the starting point for:

* AI & Generative AI applications
* Machine Learning projects
* Data Science projects
* FastAPI services
* LangGraph workflows
* RAG applications
* Automation scripts
* Research projects

Instead of repeatedly configuring development tools for every new project, this template provides a standardized engineering foundation.

---

# Features

* Python 3.13+
* uv package & dependency management
* Ruff linting and formatting
* pytest testing
* pre-commit hooks
* Docker support
* Dev Container support
* GitHub Actions CI
* VS Code configuration
* WSL2 optimized
* Modern `src` project layout

---

# Technology Stack

| Category        | Tool        |
| --------------- | ----------- |
| Language        | Python 3.13 |
| Package Manager | uv          |
| Formatter       | Ruff        |
| Linter          | Ruff        |
| Testing         | pytest      |
| Type Checking   | mypy        |
| Git Hooks       | pre-commit  |
| Containers      | Docker      |
| IDE             | VS Code     |
| Development     | WSL2 Ubuntu |

---

# Project Structure

```text
.
├── .devcontainer/
├── .github/
│   ├── workflows/
│   └── ISSUE_TEMPLATE/
├── .vscode/
├── assets/
├── configs/
├── data/
│   ├── external/
│   ├── processed/
│   └── raw/
├── docs/
├── examples/
├── models/
├── notebooks/
├── scripts/
├── src/
│   └── ai_template_python/
├── tests/
├── Dockerfile
├── docker-compose.yml
├── Makefile
├── pyproject.toml
└── README.md
```

---

# Prerequisites

* Python 3.13+
* uv
* Git
* Docker (optional)
* VS Code (recommended)
* WSL2 Ubuntu (recommended for Windows)

---

# Getting Started

Clone the repository.

```bash
git clone <repository-url>
cd ai-template-python
```

Install dependencies.

```bash
uv sync
```

Activate the virtual environment.

```bash
source .venv/bin/activate
```

Run the application.

```bash
uv run python main.py
```

---

# Development

Run tests.

```bash
uv run pytest
```

Lint the project.

```bash
uv run ruff check .
```

Format the project.

```bash
uv run ruff format .
```

Run pre-commit hooks.

```bash
uv run pre-commit run --all-files
```

---

# Make Commands

```bash
make setup
make lint
make format
make test
make run
```

---

# Docker

Build the image.

```bash
docker build -t ai-template-python .
```

Run using Docker Compose.

```bash
docker compose up
```

---

# Continuous Integration

GitHub Actions automatically:

* Install Python
* Install uv
* Install dependencies
* Run Ruff
* Run pytest

on every push and pull request.

---

# Roadmap

Future template repositories built from this foundation:

* FastAPI Template
* LangGraph Template
* Enterprise RAG Template
* Data Science Template
* Machine Learning Template
* Agentic AI Template

---

# Contributing

Contributions, issues, and feature requests are welcome.

Please open an issue before submitting major changes.

---

# License

This project is licensed under the MIT License.

---

## Author

**Rajesh Kanna Vaidyanathan**

Senior AI Engineer | Data Scientist

GitHub: https://github.com/vrajeshtrichy
