from typing import Union

from eth_typing import Address, ChecksumAddress
from web3.contract import Contract  # noqa: F401

AddressLike = Union[Address, ChecksumAddress]
