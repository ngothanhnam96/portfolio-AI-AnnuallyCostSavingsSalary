.PHONY: install seed dev test lint docker

install:
	python -m pip install -r requirements.txt -r requirements-dev.txt

seed:
	python -m app.seed --reset

dev:
	uvicorn app.main:app --reload

test:
	python -m unittest discover -s tests -t .

lint:
	python -m ruff check app tests

docker:
	docker compose up --build
