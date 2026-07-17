# Line 1 to 20 are here to render the help output pretty, not to be read and even less understood!! :)
GREEN  := $(shell tput -Txterm setaf 2)
WHITE  := $(shell tput -Txterm setaf 7)
YELLOW := $(shell tput -Txterm setaf 3)
RESET  := $(shell tput -Txterm sgr0)
# From https://gist.github.com/prwhite/8168133#gistcomment-1727513
# Add the following 'help' target to your Makefile
# And add help text after each target name starting with ##
# A category can be added with @category
HELP_DESCRIPTION = \
    %help; \
    while(<>) { push @{$$help{$$2 // 'options'}}, [$$1, $$3] if /^([a-zA-Z\-]+)\s*:.*\#\#(?:@([a-zA-Z\-]+))?\s(.*)$$/ }; \
    print "usage: make [target]\n\n"; \
    for (sort keys %help) { \
    print "${WHITE}$$_:${RESET}\n"; \
    for (@{$$help{$$_}}) { \
    $$sep = " " x (32 - length $$_->[0]); \
    print "  ${YELLOW}$$_->[0]${RESET}$$sep${GREEN}$$_->[1]${RESET}\n"; \
    }; \
    print "\n"; }


# Variables for local (native macOS) runs — not used by Docker targets above
VENV := .venv
PROJECT_ROOT := $(shell pwd)
# Absolute path required because LOCAL_ENV changes CWD to /tmp
PYTHON := $(PROJECT_ROOT)/$(VENV)/bin/python
# Run from /tmp so pydantic_settings does not auto-load the project .env (Docker Compose vars),
# which would cause ecodev_core.DeploymentSetting to fail with extra_forbidden errors.
LOCAL_ENV := cd /tmp && base_path=$(PROJECT_ROOT) PYTHONPATH=$(PROJECT_ROOT) environment=local

help:		## Show this help.
	@perl -e '$(HELP_DESCRIPTION)' $(MAKEFILE_LIST)

setup:		##@setup Install the pre-commit
	pip install pre-commit
	pre-commit install

jupyter-launch:            ##@docker Launch a jupyter notebook from a fresh container
	docker exec -it luxdem_backend jupyter notebook --no-browser --ip 0.0.0.0 --allow-root --port 5000

prod-launch:            ##@docker Launch production containers
	docker compose -f docker-compose.yml up -d

prod-build:            ##@docker build production image
	docker build --tag luxdem . 

dev-build:            ##@docker build development image
	docker build --tag luxdem . -f Dockerfile-dev --no-cache

all-tests:		##@tests Run all the tests
	docker exec luxdem_backend python3 -m unittest discover tests

scrape-dossiers:		##scrape-dossiers Scrape chd.lu for dossiers metadata
	docker exec luxdem_backend python3 -m app.typer_app scrape-chd-lu-for-dossier-command

insert-dossier-embedings:		##insert-dossier-embedings Insert dossier embedings into the database
	docker exec luxdem_backend python3 -m app.typer_app insert-dossier-embedings-command

insert-onh-from-dir:		##insert-dossier-embedings Insert dossier embedings into the database
	docker exec luxdem_backend python3 -m app.typer_app ingest-onh-from-dir-command

insert-coalition-doc:
	docker exec luxdem_backend python3 -m app.typer_app ingest-coalition-agreement-command
local-venv:  ##@local Create .venv with MPS PyTorch + project requirements (omits CPU-only torch index used in Dockerfile-dev)
	python3.13 -m venv $(VENV)
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install torch torchvision
	$(PYTHON) -m pip install -r requirements.txt -r requirements-dev.txt

local-verify:  ##@local Verify MPS is available and run a Docling smoke-test import (first run downloads models ~1-2 GB)
	$(LOCAL_ENV) $(PYTHON) -c "import torch; assert torch.backends.mps.is_available(), 'MPS not available'; print('MPS OK')"
	$(LOCAL_ENV) $(PYTHON) -c "from app.methodo.parsing.docling_parser import parse_with_docling; print('Docling import OK')"

local-test-parse:  ##@local Parse a single PDF with Docling on MPS (usage: make local-test-parse URL=https://example.com/file.pdf)
	cd /tmp && base_path=$(PROJECT_ROOT) PYTHONPATH=$(PROJECT_ROOT) environment=local \
	  $(PYTHON) -c "\
from app.methodo.parsing.docling_parser import parse_with_docling; \
chunks = parse_with_docling('$(URL)', {}); \
print(f'\n--- {len(chunks)} chunks ---'); \
[print(f'[{i}] {c[\"page_content\"][:200]}') for i, c in enumerate(chunks[:5])]"

local-embed-dossiers:  ##@local Run dossier embedding pipeline natively (requires Ollama on 127.0.0.1:11434 and DB reachable)
	$(LOCAL_ENV) $(PYTHON) -m app.typer_app insert-dossier-embedings-command

local-embed-onh:  ##@local Run ONH embedding pipeline natively (requires Ollama on 127.0.0.1:11434 and DB reachable)
	$(LOCAL_ENV) $(PYTHON) -m app.typer_app embed-onh-command

local-summarize-laws:  ##@local Generate dossier summaries natively via the local Ollama.app (config/local.yaml chat_model), bypassing luxdem_backend and luxdem_ollama (requires Ollama on 127.0.0.1:11434 and DB reachable; optional LIMIT=N)
	$(LOCAL_ENV) $(PYTHON) -m app.typer_app summarize-laws-command $(if $(LIMIT),--limit $(LIMIT))

local-analyze-topic:  ##@local Run topic analysis natively (usage: make local-analyze-topic TOPIC="logement abordable")
	$(LOCAL_ENV) $(PYTHON) -m app.typer_app analyze-topic-command "$(TOPIC)" --json

local-summarize-onh:  ##@local Generate ONH publication summaries natively via the local Ollama.app (config/local.yaml chat_model), bypassing luxdem_backend and luxdem_ollama (requires Ollama on 127.0.0.1:11434 and DB reachable; optional LIMIT=N)
	$(LOCAL_ENV) $(PYTHON) -m app.typer_app summarize-onh-command $(if $(LIMIT),--limit $(LIMIT))
