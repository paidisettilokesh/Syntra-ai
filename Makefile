.PHONY: setup lint format test run clean

setup:
	pip install -r requirements.txt
	pip install -e .[dev]
	pre-commit install

lint:
	flake8 src tests main.py
	black --check src tests main.py
	isort --check src tests main.py

format:
	black src tests main.py
	isort src tests main.py

test:
	pytest tests/

run:
	python main.py

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
