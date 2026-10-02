.PHONY: install test test-integration typecheck lint verify build docs format-abis

install:
	python -m pip install -r requirements.txt -e ".[dev]"

test:
	pytest -ra --cov=uniswap --cov-report=term

# Needs PROVIDER (mainnet RPC URL) and anvil (https://getfoundry.sh) on PATH.
test-integration:
	pytest -ra -m integration

typecheck:
	mypy --pretty

lint:
	ruff check .

# Same checks CI runs on every push.
verify: lint typecheck test build

build:
	python -m build

docs:
	python -m pip install -e ".[docs]"
	cd docs/ && $(MAKE) html

format-abis:
	npx prettier --write --parser=json uniswap/assets/*/*.abi
