.PHONY: demo test lint all dashboard clean

demo:
	python -m citedlog demo

dashboard:
	python -m citedlog dashboard

lint:
	ruff check .

test:
	python -m pytest -q

all: lint test demo

clean:
	rm -rf site .pytest_cache .ruff_cache
