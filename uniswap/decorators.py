import functools
from typing import Callable, Any, List, Dict, TYPE_CHECKING

from .constants import ETH_ADDRESS
from .util import _validate_address

if TYPE_CHECKING:
    from .uniswap import Uniswap


def check_approval(method: Callable) -> Callable:
    """Decorator to check if user is approved for a token. It approves them if they
    need to be approved."""

    @functools.wraps(method)
    def approved(self: Any, *args: Any, **kwargs: Any) -> Any:
        # Reject bad token arguments before approve() can send a transaction.
        if method.__name__ in ("make_trade", "make_trade_output"):
            _validate_address(args[0])
            _validate_address(args[1])

        # Only the input token needs an allowance; ETH needs none.
        token = args[0] if args[0] != ETH_ADDRESS else None
        if token:
            is_approved = self._is_approved(token)
            # logger.warning(f"Approved? {token}: {is_approved}")
            if not is_approved:
                self.approve(token)
        return method(self, *args, **kwargs)

    return approved


def supports(versions: List[int]) -> Callable:
    def g(f: Callable) -> Callable:
        if f.__doc__ is None:
            f.__doc__ = ""
        f.__doc__ += """\n\n
        Supports Uniswap
        """ + ", ".join(
            "v" + str(ver) for ver in versions
        )

        @functools.wraps(f)
        def check_version(self: "Uniswap", *args: List, **kwargs: Dict) -> Any:
            if self.version not in versions:
                raise Exception(
                    f"Function {f.__name__} does not support version {self.version} of Uniswap passed to constructor"
                )
            return f(self, *args, **kwargs)

        return check_version

    return g
