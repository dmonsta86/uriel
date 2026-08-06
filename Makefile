SHELL := /bin/sh
PYTHON ?= python

.PHONY: test verify portable release-check build clean

test:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -v

verify:
	$(PYTHON) -m compileall -q src tests scripts
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -v
	$(PYTHON) scripts/privacy_sweep.py

portable:
	$(PYTHON) scripts/build_portable.py

release-check:
	PYTHONPATH=src $(PYTHON) scripts/release_check.py

build: verify portable
	$(PYTHON) -m build

clean:
	rm -rf build dist .pytest_cache *.egg-info src/*.egg-info
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
