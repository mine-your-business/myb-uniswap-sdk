"""Tests that need no Ethereum node: ABI loading, address helpers, calldata
encoding, constructor wiring and the gas-limit logic in ``_build_and_send_tx``."""

import json
from pathlib import Path
from typing import Any, Dict, List

import pytest
from web3 import Web3
from web3.exceptions import NameNotFound
from web3.providers.base import BaseProvider

from uniswap import Uniswap
from uniswap.cli import _coerce_to_checksum
from uniswap.constants import ETH_ADDRESS, WETH9_ADDRESS
from uniswap.exceptions import GasLimitExceeded
from uniswap.tokens import tokens, tokens_rinkeby
from uniswap.util import (
    _addr_to_str,
    _load_abi,
    _load_contract,
    _str_to_addr,
    is_same_address,
)

ASSETS = Path(__file__).parent.parent / "uniswap" / "assets"
FIXTURES = Path(__file__).parent / "fixtures"

DAI = "0x6B175474E89094C44Da98b954EedeAC495271d0F"
USDC = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
WALLET = "0x94e3361495bD110114ac0b6e35Ed75E77E6a6cFA"
# Address derived from SIGNER_KEY; signing rejects a mismatched "from".
SIGNER_KEY = "0x" + "11" * 32
SIGNER = "0x19E7E376E7C213B7E7e7e46cc70A5dD086DAff2A"


class FakeProvider(BaseProvider):
    """Answers the handful of RPC calls the Uniswap constructor makes."""

    def __init__(self, results: Dict[str, Any]) -> None:
        super().__init__()
        self.results = results

    def make_request(self, method: Any, params: Any) -> Any:
        if method not in self.results:
            raise AssertionError(f"unexpected RPC call {method}")
        return {"jsonrpc": "2.0", "id": 1, "result": self.results[method]}

    def is_connected(self, show_traceback: bool = False) -> bool:
        return True


def offline_web3(netid: str = "1") -> Web3:
    return Web3(
        FakeProvider(
            {"net_version": netid, "eth_getTransactionCount": "0x5", "eth_chainId": "0x1"}
        )
    )


# ------ ABIs ------------------------------------------------------------------------


ABI_NAMES = sorted(
    str(p.relative_to(ASSETS).with_suffix("")) for p in ASSETS.rglob("*.abi")
)


def test_all_abi_files_found():
    # Guards against package_data / glob regressions silently dropping ABIs.
    assert len(ABI_NAMES) >= 10


@pytest.mark.parametrize("name", ABI_NAMES)
def test_abi_loads_and_builds_contract(name: str):
    abi: Any = _load_abi(name)
    assert isinstance(abi, list) and abi
    assert all("type" in entry for entry in abi)
    contract = Web3().eth.contract(address=Web3.to_checksum_address(WETH9_ADDRESS), abi=abi)
    assert contract.address == WETH9_ADDRESS


def test_load_contract_checksums_address():
    contract = _load_contract(Web3(), "erc20", WETH9_ADDRESS.lower())
    assert contract.address == WETH9_ADDRESS


# ------ Calldata encoding -----------------------------------------------------------


def _router_calls() -> List[Dict[str, Any]]:
    return json.loads((FIXTURES / "v3_router_calldata.json").read_text())["calls"]


def _abi_word(value: Any) -> str:
    """One static ABI argument as a 32-byte big-endian word (uint or address)."""
    if isinstance(value, str):
        value = int(value, 16)
    return format(value, "064x")


@pytest.mark.parametrize("call", _router_calls(), ids=lambda c: c["fn_name"])
def test_v3_router_calldata(call: Dict[str, Any]):
    fixture = json.loads((FIXTURES / "v3_router_calldata.json").read_text())
    router = Web3().eth.contract(
        address=fixture["router_address"], abi=_load_abi("uniswap-v3/router")
    )
    args = [tuple(a) if isinstance(a, list) else a for a in call["args"]]
    flat = [v for a in call["args"] for v in (a if isinstance(a, list) else [a])]
    expected = call["selector"] + "".join(_abi_word(v) for v in flat)
    assert router.encode_abi(call["fn_name"], args=args) == expected


# ------ Address helpers -------------------------------------------------------------


def test_str_to_addr_round_trip():
    addr = _str_to_addr(DAI.lower())
    assert isinstance(addr, bytes) and len(addr) == 20
    assert _addr_to_str(addr) == DAI
    assert _str_to_addr(addr) is addr


def test_str_to_addr_rejects_names():
    with pytest.raises(NameNotFound):
        _str_to_addr("btc")
    with pytest.raises(NameNotFound):
        _addr_to_str("btc")  # type: ignore[arg-type]


def test_is_same_address_ignores_case_and_type():
    assert is_same_address(DAI, DAI.lower())
    assert is_same_address(_str_to_addr(DAI), DAI)
    assert not is_same_address(DAI, USDC)


@pytest.mark.parametrize("table", [tokens, tokens_rinkeby])
def test_token_tables_are_checksummed(table):
    for addr in table.values():
        assert Web3.is_checksum_address(addr)


def test_cli_coerce_to_checksum():
    assert _coerce_to_checksum("dai") == DAI
    assert _coerce_to_checksum(DAI.lower()) == DAI
    with pytest.raises(ValueError):
        _coerce_to_checksum("notatoken")


# ------ Constructor -----------------------------------------------------------------


@pytest.mark.parametrize("version", [1, 2, 3])
def test_constructor_offline(version: int):
    uni = Uniswap(WALLET, None, web3=offline_web3(), version=version)
    assert uni.netname == "mainnet"
    assert uni.last_nonce == 5
    assert uni.maximum_gas == 250_000
    assert uni.factory_contract.address


def test_constructor_rejects_unknown_network():
    with pytest.raises(Exception, match="Unknown netid"):
        Uniswap(WALLET, None, web3=offline_web3("31337"), version=2)


def test_supports_decorator_rejects_wrong_version():
    uni = Uniswap(WALLET, None, web3=offline_web3(), version=3)
    with pytest.raises(Exception, match="does not support version 3"):
        uni.get_fee_maker()


@pytest.mark.parametrize("method", ["make_trade", "make_trade_output"])
@pytest.mark.parametrize(
    "token_in, token_out",
    [(ETH_ADDRESS, "btc"), (DAI, "btc"), ("btc", DAI)],
)
def test_make_trade_rejects_non_address_tokens_before_approving(
    monkeypatch, method, token_in, token_out
):
    uni = Uniswap(WALLET, None, web3=offline_web3(), version=3)
    calls: List[str] = []

    def is_approved(token: Any) -> bool:
        calls.append("check")
        return False

    def approve(token: Any) -> None:
        calls.append("approve")

    monkeypatch.setattr(uni, "_is_approved", is_approved)
    monkeypatch.setattr(uni, "approve", approve)
    with pytest.raises(NameNotFound):
        getattr(uni, method)(token_in, token_out, 1)
    assert calls == []


@pytest.mark.parametrize(
    "token_in, token_out, expected",
    [
        (DAI, USDC, [DAI, WETH9_ADDRESS, USDC]),
        (DAI, WETH9_ADDRESS, [DAI, WETH9_ADDRESS]),
        (WETH9_ADDRESS.lower(), USDC, [WETH9_ADDRESS.lower(), USDC]),
    ],
)
def test_v2_token_path_avoids_duplicate_weth(token_in, token_out, expected):
    uni = Uniswap(WALLET, None, web3=offline_web3(), version=2)
    uni.get_weth_address = lambda: WETH9_ADDRESS  # type: ignore[assignment]
    assert uni._v2_token_path(token_in, token_out) == expected


# ------ Gas limit -------------------------------------------------------------------


class FakeFunction:
    def __init__(self) -> None:
        self.built_with: Dict[str, Any] = {}

    def build_transaction(self, tx_params: Dict[str, Any]) -> Dict[str, Any]:
        self.built_with = dict(tx_params)
        return dict(tx_params)


@pytest.fixture
def gas_client(monkeypatch):
    uni = Uniswap(
        SIGNER,
        SIGNER_KEY,
        web3=offline_web3(),
        version=2,
        maximum_gas=300_000,
    )
    sent: List[Any] = []
    monkeypatch.setattr(uni.w3.eth, "estimate_gas", lambda tx: 200_000)

    def send_raw_transaction(raw: bytes) -> bytes:
        sent.append(raw)
        return b"\x01" * 32

    monkeypatch.setattr(uni.w3.eth, "send_raw_transaction", send_raw_transaction)
    uni._sent = sent  # type: ignore[attr-defined]
    return uni


def _tx_params() -> Dict[str, Any]:
    return {
        "from": SIGNER,
        "to": DAI,
        "value": 0,
        "nonce": 5,
        "gasPrice": 1,
        "chainId": 1,
    }


def test_fixed_gas_set_before_build(gas_client):
    gas_client.use_estimate_gas = False
    fn = FakeFunction()
    gas_client._build_and_send_tx(fn, _tx_params())
    # web3 would otherwise call eth_estimateGas inside build_transaction
    assert fn.built_with["gas"] == 300_000
    assert gas_client._sent
    assert gas_client.last_nonce == 6


def test_estimated_gas_has_margin(gas_client, monkeypatch):
    signed: Dict[str, Any] = {}
    real_sign = gas_client.w3.eth.account.sign_transaction

    def sign(tx, private_key):
        signed.update(tx)
        return real_sign(tx, private_key=private_key)

    monkeypatch.setattr(gas_client.w3.eth.account, "sign_transaction", sign)
    gas_client._build_and_send_tx(FakeFunction(), _tx_params())
    assert signed["gas"] == 240_000


def test_estimated_gas_over_maximum_raises(gas_client, monkeypatch):
    monkeypatch.setattr(gas_client.w3.eth, "estimate_gas", lambda tx: 260_000)
    with pytest.raises(GasLimitExceeded, match="Gas fees too high") as exc:
        gas_client._build_and_send_tx(FakeFunction(), _tx_params())
    assert (exc.value.estimated, exc.value.maximum) == (312_000, 300_000)
    assert not gas_client._sent
