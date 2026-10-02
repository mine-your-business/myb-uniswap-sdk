# myb-uniswap-sdk

[![CI](https://github.com/mine-your-business/myb-uniswap-sdk/actions/workflows/ci.yml/badge.svg)](https://github.com/mine-your-business/myb-uniswap-sdk/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/myb-uniswap-sdk)](https://pypi.org/project/myb-uniswap-sdk/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Python client for [Uniswap](https://uniswap.org/) v1, v2 and v3, built on [web3.py](https://github.com/ethereum/web3.py) 8.

This is the Mine Your Business fork of [uniswap-python](https://github.com/uniswap-python/uniswap-python).
It differs from upstream in one behavior: a configurable gas limit (`maximum_gas`) that caps estimated gas
and is used as the fixed limit when gas estimation is off.
It also ships every ABI file in the package and pins known-good dependency versions in `requirements.txt`.

## Installation

Requires Python 3.11 or newer.

```sh
pip install myb-uniswap-sdk
```

The import name is `uniswap`, the same as upstream, so do not install `uniswap-python` in the same environment.

## Usage

```python
from uniswap import Uniswap

uniswap = Uniswap(
    address="0x...",           # wallet address, or None for read-only use
    private_key="0x...",       # or None for read-only use
    version=3,                 # Uniswap version: 1, 2 or 3
    provider="https://...",    # RPC URL; falls back to the PROVIDER environment variable
    maximum_gas=250_000,       # gas ceiling (default 250000)
)

dai = "0x6B175474E89094C44Da98b954EedeAC495271d0F"
eth = "0x0000000000000000000000000000000000000000"

# Price of 1 ETH in DAI (wei in, DAI base units out)
uniswap.get_price_input(eth, dai, 10**18, fee=3000)

# Swap 0.1 ETH for DAI
uniswap.make_trade(eth, dai, 10**17, fee=3000)
```

### Gas limit

| `use_estimate_gas` | Gas limit sent | When the limit is exceeded |
| --- | --- | --- |
| `True` (default) | `eth_estimateGas` result plus 20% | Raises `Exception("Gas fees too high!")` without sending if the padded estimate is above `maximum_gas` |
| `False` | `maximum_gas` | The transaction runs out of gas on chain |

### Command line

The package installs a `unipy` command that reads `PROVIDER` from the environment or a `.env` file:

```sh
export PROVIDER=https://...
unipy price eth dai
unipy token weth
```

## Upgrading from 1.x

2.0.0 moves from web3.py 5 to web3.py 8 and requires Python 3.11+.

- If you pass your own `Web3` instance, it must be a web3.py 8 instance (`Web3.to_checksum_address`, `build_transaction`, and so on).
- `make_trade` and `make_trade_output` validate both token arguments and raise `web3.exceptions.NameNotFound` for anything that is not a `0x` address.
- With `use_estimate_gas=False`, `maximum_gas` is now set before the transaction is built, so web3 no longer calls `eth_estimateGas` in that mode.
- Uniswap v2 token-to-token swaps where one side is WETH route directly instead of through WETH twice.
- The package installs the `unipy` CLI entry point.

## Development

```sh
python -m venv .venv && . .venv/bin/activate
make install    # pip install -r requirements.txt -e ".[dev]"
make verify     # ruff, mypy, offline tests and a build, as in CI
```

`requirements.txt` pins the versions CI tests against. `pyproject.toml` is the only packaging metadata and holds the version floors.

### Integration tests

Tests marked `integration` fork mainnet with [anvil](https://getfoundry.sh) and skip unless `PROVIDER` is set and `anvil` is on `PATH`:

```sh
export PROVIDER=https://...   # mainnet RPC URL
make test-integration
```

In CI they run only when the `MAINNET_PROVIDER` repository secret is set.

## Releasing

Publishing a GitHub release tagged `vX.Y.Z` builds the package and uploads it to PyPI through trusted publishing.
The tag must match `version` in `pyproject.toml`.
PyPI must list this repository, the `publish.yml` workflow and the `pypi` environment as a trusted publisher for `myb-uniswap-sdk`.

## Authors

Upstream uniswap-python is by [Shane Fontaine](https://github.com/shanefontaine), [Erik Bjäreholt](https://github.com/ErikBjare),
[@liquid-8](https://github.com/liquid-8) and [other contributors](https://github.com/uniswap-python/uniswap-python/graphs/contributors).
This fork is maintained by Mine Your Business.

## Changelog

_2.0.0_

* Upgraded web3.py 5 to 8 (snake_case web3 APIs, `encode_abi`, `build_transaction`, `raw_transaction`), following upstream's web3 6 migration
* Python 3.11+ required
* `maximum_gas` is applied before `build_transaction` when `use_estimate_gas=False`
* `make_trade` / `make_trade_output` validate token addresses up front
* v2 token-to-token swaps no longer route through WETH twice when one side is WETH (upstream #459)
* Added Görli to the network id table
* Packaging moved from `setup.py` to `pyproject.toml`; dropped the stale upstream Poetry metadata; `unipy` CLI entry point added
* License metadata corrected to MIT, matching `LICENSE`

_1.1.0_

* Configurable gas limit (`maximum_gas`)

_1.0.x_

* Forked from uniswap-python 0.5.x and published as `myb-uniswap-sdk`; all ABI files packaged; `requirements.txt` added

_Entries below are from upstream uniswap-python._

_0.5.4_

* added use of gas estimation instead of a fixed gas limit (to support Arbitrum)
* added `use_estimate_gas` constructor argument (used in testing)
* added constants/basic support for Arbitrum, Optimism, Polygon, and Fantom. (untested)
* incomplete changelog

_0.5.3_

* incomplete changelog

_0.5.2_

* incomplete changelog

_0.5.1_

* Updated dependencies
* Fixed minor typing issues

_0.5.0_

* Basic support for Uniswap V3
* Added new methods `get_price_input` and `get_price_output`
* Made a lot of previously public methods private
* Added documentation site
* Removed ENS support (which was probably broken to begin with)

_0.4.6_

* Bug fix: Update bleach package from 3.1.4 to 3.3.0

_0.4.5_
* Bug fix: Use .eth instead of .ens

_0.4.4_

* General: Add new logo for Uniswap V2
* Bug fix: Invalid balance check (#25)
* Bug fix: Fixed error when passing WETH as token

_0.4.3_

* Allow kwargs in `approved` decorator.

_0.4.2_

* Add note about Uniswap V2 support

_0.4.1_

* Update changelog for PyPi and clean up

_0.4.0_

_A huge thank you [Erik Bjäreholt](https://github.com/ErikBjare) for adding Uniswap V2 support, as well as all changes in this version!_

* Added support for Uniswap v2
* Handle arbitrary tokens (by address) using the factory contract
* Switched from setup.py to pyproject.toml/poetry
* Switched from Travis to GitHub Actions
* For CI to work in your repo, you need to set the secret MAINNET_PROVIDER. I use Infura.
* Running tests on a local fork of mainnet using ganache-cli (started as a fixture)
* Fixed tests for make_trade and make_trade_output
* Added type annotations to the entire codebase and check them with mypy in CI
* Formatted entire codebase with black
* Moved stuff around such that the basic import becomes from uniswap import Uniswap (instead of from uniswap.uniswap import UniswapWrapper)
* Fixed misc bugs

_0.3.3_
*  Provide token inputs as addresses instead of names

_0.3.2_
*  Add ability to transfer tokens after a trade
*  Add tests for this new functionality

_0.3.1_
*  Add tests for all types of trades

_0.3.0_
*  Add ability to make all types of trades
*  Add example to README

_0.2.1_
*  Add liquidity tests

_0.2.0_
*  Add liquidity and ERC20 pool methods

_0.1.1_
*  Major README update

_0.1.0_
*  Add market endpoints
*  Add tests for market endpoints
