import pytest
import os
import subprocess
import shutil
import logging
from typing import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from time import sleep

from web3 import Web3
from web3.exceptions import NameNotFound

from uniswap import Uniswap
from uniswap.constants import ETH_ADDRESS
from uniswap.exceptions import InsufficientBalance
from uniswap.util import _str_to_addr


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

ENV_UNISWAP_VERSION = os.getenv("UNISWAP_VERSION", None)
if ENV_UNISWAP_VERSION:
    UNISWAP_VERSIONS = [int(ENV_UNISWAP_VERSION)]
else:
    UNISWAP_VERSIONS = [1, 2, 3]

RECEIPT_TIMEOUT = 5


# These tests fork mainnet with anvil (https://getfoundry.sh), so they need both
# the `anvil` binary and a mainnet RPC URL in PROVIDER. Without either, the whole
# module is skipped and only the offline tests run.
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.getenv("PROVIDER"), reason="PROVIDER (mainnet RPC URL) is not set"
    ),
    pytest.mark.skipif(
        not shutil.which("anvil"), reason="anvil (Foundry) is not installed"
    ),
]


@dataclass
class AnvilInstance:
    provider: str
    eth_address: str
    eth_privkey: str


@pytest.fixture(scope="module", params=UNISWAP_VERSIONS)
def client(request, web3: Web3, anvil: AnvilInstance):
    return Uniswap(
        anvil.eth_address,
        anvil.eth_privkey,
        web3=web3,
        version=request.param,
        use_estimate_gas=False,  # see note in _build_and_send_tx
        maximum_gas=500_000,
    )


@pytest.fixture(scope="module")
def test_assets(client: Uniswap):
    """
    Buy some DAI and USDC to test with.
    """
    tokens = client._get_token_addresses()

    for token_name, amount in [("DAI", 100 * 10**18), ("USDC", 100 * 10**6)]:
        token_addr = tokens[token_name]
        price = client.get_price_output(_str_to_addr(ETH_ADDRESS), token_addr, amount)
        logger.info(f"Cost of {amount} {token_name}: {price}")
        logger.info("Buying...")

        txid = client.make_trade_output(tokens["ETH"], token_addr, amount)
        tx = client.w3.eth.wait_for_transaction_receipt(txid, timeout=RECEIPT_TIMEOUT)
        assert tx["status"] == 1, f"Transaction failed: {tx}"


@pytest.fixture(scope="module")
def web3(anvil: AnvilInstance):
    w3 = Web3(Web3.HTTPProvider(anvil.provider, request_kwargs={"timeout": 30}))
    if 1 != int(w3.net.version):
        raise Exception("PROVIDER was not a mainnet provider, which the tests require")
    return w3


@pytest.fixture(scope="module")
def anvil() -> Generator[AnvilInstance, None, None]:
    """Fixture that runs anvil forked off mainnet."""
    port = 10999
    p = subprocess.Popen(
        [
            "anvil",
            "--port",
            str(port),
            "--chain-id",
            "1",
            "--fork-url",
            os.environ["PROVIDER"],
            "--gas-price",
            str(100_000_000_000),  # 100 gwei
        ],
        stdout=subprocess.DEVNULL,
    )
    # Account #9 from anvil's default test mnemonic, starts with 10000 ETH
    eth_address = "0xa0Ee7A142d267C1f36714E4a8F75612F20a79720"
    eth_privkey = "0x2a871d0798f97d79848a013d4936a73bf4cc922c825d33c1cf7073dff6d409c6"
    provider = f"http://127.0.0.1:{port}"
    w3 = Web3(Web3.HTTPProvider(provider))
    for _ in range(60):
        if p.poll() is not None:
            raise Exception(f"anvil exited early with code {p.returncode}")
        try:
            if w3.is_connected():
                break
        except Exception:
            pass
        sleep(0.5)
    else:
        p.kill()
        raise Exception("anvil did not start within 30s")
    yield AnvilInstance(provider, eth_address, eth_privkey)
    p.kill()
    p.wait()


@contextmanager
def does_not_raise():
    yield


# TODO: Change pytest.param(..., mark=pytest.mark.xfail) to the expectation/raises method
@pytest.mark.usefixtures("client", "web3")
class TestUniswap(object):
    ONE_ETH = 10**18
    ONE_USDC = 10**6

    ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"

    # TODO: Detect mainnet vs rinkeby and set accordingly, like _get_token_addresses in the Uniswap class
    # For Mainnet testing (with `ganache --fork` as per the ganache fixture)
    eth = "0x0000000000000000000000000000000000000000"
    weth = Web3.to_checksum_address("0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2")
    bat = Web3.to_checksum_address("0x0D8775F648430679A709E98d2b0Cb6250d2887EF")
    dai = Web3.to_checksum_address("0x6b175474e89094c44da98b954eedeac495271d0f")
    usdc = Web3.to_checksum_address("0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48")

    # For Rinkeby
    # eth = "0x0000000000000000000000000000000000000000"
    # bat = "0xDA5B056Cfb861282B4b59d29c9B395bcC238D29B"
    # dai = "0x2448eE2641d78CC42D7AD76498917359D961A783"

    # ------ Exchange ------------------------------------------------------------------
    def test_get_fee_maker(self, client: Uniswap):
        if client.version not in [1, 2]:
            pytest.skip("Tested method not supported in this Uniswap version")
        r = client.get_fee_maker()
        assert r == 0

    def test_get_fee_taker(self, client: Uniswap):
        if client.version not in [1, 2]:
            pytest.skip("Tested method not supported in this Uniswap version")
        r = client.get_fee_taker()
        assert r == 0.003

    # ------ Market --------------------------------------------------------------------
    @pytest.mark.parametrize(
        "token0, token1, qty, kwargs",
        [
            (eth, bat, ONE_ETH, {}),
            (bat, eth, ONE_ETH, {}),
            (eth, dai, ONE_ETH, {}),
            (dai, eth, ONE_ETH, {}),
            (eth, bat, 2 * ONE_ETH, {}),
            (bat, eth, 2 * ONE_ETH, {}),
            (weth, dai, ONE_ETH, {}),
            (dai, weth, ONE_ETH, {}),
            (dai, usdc, ONE_ETH, {"fee": 500}),
            pytest.param(eth, "btc", ONE_ETH, {}, marks=pytest.mark.xfail),
            pytest.param("btc", eth, ONE_ETH, {}, marks=pytest.mark.xfail),
        ],
    )
    def test_get_price_input(self, client, token0, token1, qty, kwargs):
        if client.version == 1 and ETH_ADDRESS not in [token0, token1]:
            pytest.skip("Not supported in this version of Uniswap")
        r = client.get_price_input(token0, token1, qty, **kwargs)
        assert r

    @pytest.mark.parametrize(
        "token0, token1, qty, kwargs",
        [
            (eth, bat, ONE_ETH, {}),
            (bat, eth, ONE_ETH, {}),
            (eth, dai, ONE_ETH, {}),
            (dai, eth, ONE_ETH, {}),
            (eth, bat, 2 * ONE_ETH, {}),
            (bat, eth, ONE_ETH // 100, {}),
            (weth, dai, ONE_ETH, {}),
            (dai, weth, ONE_ETH, {}),
            (dai, usdc, ONE_USDC, {"fee": 500}),
            pytest.param(eth, "btc", ONE_ETH, {}, marks=pytest.mark.xfail),
            pytest.param("btc", eth, ONE_ETH, {}, marks=pytest.mark.xfail),
        ],
    )
    def test_get_price_output(self, client, token0, token1, qty, kwargs):
        if client.version == 1 and ETH_ADDRESS not in [token0, token1]:
            pytest.skip("Not supported in this version of Uniswap")
        r = client.get_price_output(token0, token1, qty, **kwargs)
        assert r

    # ------ ERC20 Pool ----------------------------------------------------------------
    @pytest.mark.parametrize("token", [(bat), (dai)])
    def test_get_ex_eth_balance(
        self,
        client: Uniswap,
        token,
    ):
        if not client.version == 1:
            pytest.skip("Tested method only supported on Uniswap v1")
        r = client.get_ex_eth_balance(token)
        assert r

    @pytest.mark.parametrize("token", [(bat), (dai)])
    def test_get_ex_token_balance(
        self,
        client: Uniswap,
        token,
    ):
        if not client.version == 1:
            pytest.skip("Tested method only supported on Uniswap v1")
        r = client.get_ex_token_balance(token)
        assert r

    @pytest.mark.parametrize("token", [(bat), (dai)])
    def get_exchange_rate(
        self,
        client: Uniswap,
        token,
    ):
        r = client.get_exchange_rate(token)
        assert r

    # ------ Liquidity -----------------------------------------------------------------
    @pytest.mark.skip
    @pytest.mark.parametrize(
        "token, max_eth",
        [
            (bat, 0.00001 * ONE_ETH),
            (dai, 0.00001 * ONE_ETH),
            pytest.param("btc", ONE_ETH, marks=pytest.mark.xfail),
        ],
    )
    def test_add_liquidity(self, client: Uniswap, web3: Web3, token, max_eth):
        r = client.add_liquidity(token, max_eth)
        tx = web3.eth.wait_for_transaction_receipt(r, timeout=RECEIPT_TIMEOUT)
        assert tx["status"]

    @pytest.mark.skip
    @pytest.mark.parametrize(
        "token, max_token, expectation",
        [
            (bat, 0.00001 * ONE_ETH, does_not_raise()),
            (dai, 0.00001 * ONE_ETH, does_not_raise()),
            ("btc", ONE_ETH, pytest.raises(NameNotFound)),
        ],
    )
    def test_remove_liquidity(
        self, client: Uniswap, web3: Web3, token, max_token, expectation
    ):
        with expectation:
            r = client.remove_liquidity(token, max_token)
            tx = web3.eth.wait_for_transaction_receipt(r)
            assert tx["status"]

    # ------ Make Trade ----------------------------------------------------------------
    @pytest.mark.parametrize(
        "input_token, output_token, qty, recipient, expectation",
        [
            # ETH -> Token
            (eth, dai, ONE_ETH, None, does_not_raise),
            # Token -> Token
            (dai, usdc, ONE_ETH, None, does_not_raise),
            # Token -> ETH
            (usdc, eth, 100 * ONE_USDC, None, does_not_raise),
            # (eth, bat, 0.00001 * ONE_ETH, ZERO_ADDRESS, does_not_raise),
            # (bat, eth, 0.00001 * ONE_ETH, ZERO_ADDRESS, does_not_raise),
            # (dai, bat, 0.00001 * ONE_ETH, ZERO_ADDRESS, does_not_raise),
            (dai, "btc", ONE_ETH, None, lambda: pytest.raises(NameNotFound)),
        ],
    )
    def test_make_trade(
        self,
        client: Uniswap,
        web3: Web3,
        test_assets,
        input_token,
        output_token,
        qty: int,
        recipient,
        expectation,
    ):
        if client.version == 1 and ETH_ADDRESS not in [input_token, output_token]:
            pytest.skip(
                "Not supported in this version of Uniswap, or at least no liquidity"
            )
        # Uniswap v1 token-to-ETH runs Vyper 0.1.x bytecode whose computed jumps
        # anvil's strict EVM rejects (InvalidJump); ganache tolerated them.
        if client.version == 1 and output_token == ETH_ADDRESS:
            pytest.xfail("v1 token-to-ETH: InvalidJump under anvil")
        with expectation():
            bal_in_before = client.get_token_balance(input_token)

            txid = client.make_trade(input_token, output_token, qty, recipient)
            tx = web3.eth.wait_for_transaction_receipt(txid, timeout=RECEIPT_TIMEOUT)
            assert tx["status"]

            # TODO: Checks for ETH, taking gas into account
            bal_in_after = client.get_token_balance(input_token)
            if input_token != self.eth:
                assert bal_in_before - qty == bal_in_after

    @pytest.mark.parametrize(
        "input_token, output_token, qty, recipient, expectation",
        [
            # ETH -> Token
            (eth, dai, 10**18, None, does_not_raise),
            # Token -> Token
            (dai, usdc, ONE_USDC, None, does_not_raise),
            # Token -> ETH
            (dai, eth, 10**16, None, does_not_raise),
            # FIXME: These should probably be uncommented eventually
            # (eth, bat, int(0.000001 * ONE_ETH), ZERO_ADDRESS),
            # (bat, eth, int(0.000001 * ONE_ETH), ZERO_ADDRESS),
            # (dai, bat, int(0.000001 * ONE_ETH), ZERO_ADDRESS),
            (
                dai,
                eth,
                10 * 10**18,
                None,
                lambda: pytest.raises(InsufficientBalance),
            ),
            (dai, "btc", ONE_ETH, None, lambda: pytest.raises(NameNotFound)),
        ],
    )
    def test_make_trade_output(
        self,
        client: Uniswap,
        web3: Web3,
        test_assets,
        input_token,
        output_token,
        qty: int,
        recipient,
        expectation,
    ):
        if client.version == 1 and ETH_ADDRESS not in [input_token, output_token]:
            pytest.skip(
                "Not supported in this version of Uniswap, or at least no liquidity"
            )
        # Uniswap v1 token-to-ETH runs Vyper 0.1.x bytecode whose computed jumps
        # anvil's strict EVM rejects (InvalidJump); ganache tolerated them.
        if client.version == 1 and output_token == ETH_ADDRESS:
            pytest.xfail("v1 token-to-ETH: InvalidJump under anvil")
        with expectation():
            balance_before = client.get_token_balance(output_token)

            r = client.make_trade_output(input_token, output_token, qty, recipient)
            tx = web3.eth.wait_for_transaction_receipt(r, timeout=RECEIPT_TIMEOUT)
            assert tx["status"]

            # TODO: Checks for ETH, taking gas into account
            balance_after = client.get_token_balance(output_token)
            if output_token != self.eth:
                assert balance_before + qty == balance_after
