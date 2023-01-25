import operator
import re
from contextlib import contextmanager
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _get_version
from typing import Callable, Dict

from packaging.version import InvalidVersion, Version, parse


__all__ = ["versiondispatch"]


_OP_TABLE = {
    "==": operator.eq,
    ">=": operator.ge,
    "<=": operator.le,
    ">": operator.gt,
    "<": operator.lt,
}
_OP_PAT = re.compile(r"|".join(_OP_TABLE))
BinOp = Callable[[Version, Version], bool]


def _split_package_version(package_version: str) -> tuple[str, str, BinOp]:
    match = _OP_PAT.search(package_version)
    if match is None:
        raise ValueError("Version not correctly specified, should be like 'foo<=1.2.3'")

    package, version = _OP_PAT.split(package_version)
    op = _OP_TABLE[match.group()]
    return package.strip(), version.strip(), op


def _is_valid_version(version: str) -> bool:
    valid = True
    try:
        Version(version)
    except InvalidVersion:
        valid = False
    return valid


def _is_valid_package(package: str) -> bool:
    valid = True
    try:
        _get_version(package)
    except PackageNotFoundError:
        valid = False
    return valid


def get_version(package: str) -> Version:
    return Version(_get_version(package))


@contextmanager
def pretend_version(version_dict: Dict[str, str]):
    """TODO"""
    global get_version

    get_version_orig = get_version

    def get_version(package: str):
        return Version(version_dict.get(package, _get_version(package)))

    yield

    get_version = get_version_orig


def _matches_version(package: str, version: str, op: BinOp) -> bool:
    v0 = get_version(package)
    v1 = parse(version)
    return op(v0, v1)


def _matches_all_versions(package_versions: list[tuple[str, str, BinOp]]) -> bool:
    all_match = all(
        _matches_version(package, version, op)
        for package, version, op in package_versions
    )
    return all_match


class versiondispatch:
    """TODO"""
    def __init__(self, func):
        self._func = func

        self._funcname = getattr(self._func, '__name__', 'versiondispatch function')
        self._impl = self._func  # use initial func by default
        self._matched_version = ""

    def register(self, package_versions: str):
        splits = [pv.strip() for pv in package_versions.replace(";", ",").split(",")]
        return self._register(splits)

    def _register(self, package_versions: list[str]):
        packages_versions = []
        for package_version in package_versions:
            package, version, operator = _split_package_version(package_version)

            if not (_is_valid_package(package) and _is_valid_version(version)):
                raise ValueError(f"{self._funcname} uses incorrect version spec: {package_version}")

            packages_versions.append((package, version, operator))

        def outer(func):
            if getattr(func, "_is_versiondispatched", False) is True:
                raise ValueError(
                    "You are nesting versiondispatch, which is not supported, instead provide "
                    "multiple version, e.g. '@versiondispatch(\"foo=1.0\", \"bar=2.0\")'"
                )

            try:
                self._impl._is_versiondispatched = True
            except AttributeError:
                # TODO some builtin functions are immutable
                pass

            if _matches_all_versions(packages_versions):
                self._impl = func
                self._matched_version = version

            return self._impl

        outer._is_versiondispatched = True
        return outer

    def __call__(self, *args, **kwargs):
        return self._impl(*args, **kwargs)
