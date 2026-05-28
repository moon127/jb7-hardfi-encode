.PHONY: venv clean test run

VENV_DIR = venv
PYTHON = python3
ACTIVATE = . $(VENV_DIR)/bin/activate

venv:
	$(PYTHON) -m venv $(VENV_DIR)
	$(ACTIVATE) && pip install --upgrade pip && pip install -r requirements.txt && pip install -e ".[dev]"

clean:
	rm -rf $(VENV_DIR)
	rm -rf __pycache__
	rm -rf .pytest_cache
	rm -rf *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name '*.egg-info' -exec rm -rf {} + 2>/dev/null || true
	rm -rf .coverage htmlcov

test:
	$(ACTIVATE) && python -m pytest tests/ --cov=src/hardfi_encode --cov-report=term-missing --cov-fail-under=90 -v

test-html:
	$(ACTIVATE) && python -m pytest tests/ --cov=src/hardfi_encode --cov-report=html --cov-report=term-missing --cov-fail-under=90 -v

run:
	$(ACTIVATE) && python -m hardfi_encode
