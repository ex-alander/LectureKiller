.PHONY: install clean run test

install:
	pip install -r requirements.txt
	cp .env.example .env || true
	@echo "Edit .env with your API key"

run:
	python -m src.cli

clean:
	rm -rf temp_images/*
	rm -rf output_markdown/*

test:
	pytest tests/ -v

setup: install
	@echo "Setup complete. Edit .env and run 'make run'"