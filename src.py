"""versiondispatch module

This module is self-contained and can thus be vendored with other applications.

Only the 'versiondispatch' function is intended for direct usage.

"""

import collections
import itertools
import operator
import re
import sys
from contextlib import contextmanager
from functools import update_wrapper
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _get_version
from typing import Any, Callable, Dict, Generator, Optional, SupportsInt, Tuple, Union


__all__ = ["versiondispatch"]


_OP_TABLE = {
    "==": operator.eq,
    ">=": operator.ge,
    "<=": operator.le,
    ">": operator.gt,
    "<": operator.lt,
}
_OP_PAT = re.compile(r"|".join(_OP_TABLE))
BinOp = Callable[["Version", "Version"], bool]
AnyFunc = Callable[..., Any]


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
    if package.lower() == "python":
        return True

    valid = True
    try:
        _get_version(package)
    except PackageNotFoundError:
        valid = False
    return valid


def get_version(package: str) -> "Version":
    if package.lower() == "python":
        return Version(".".join(map(str, sys.version_info[:3])))

    return Version(_get_version(package))


@contextmanager
def pretend_version(version_dict: Dict[str, str]) -> Generator[None, None, None]:
    """Context manager to pretend a certain version is installed.

    Inside this context, ``get_version`` will return the indicated version
    instead of the true version of the package.

    This is for testing purposes and should not be used in any actual code.

    Examples
    --------
    >>> @versiondispatch
    ... def foo():
    ...     return "default"
    ...
    >>> @foo.register("rich>100")
    ... def _():
    ...     return "very rich"
    ...
    >>> foo()
    'default'
    ...
    >>> with pretend_version({"rich": "101"}):
    ...     @versiondispatch
    ...     def foo():
    ...         return "default"
    ...
    ...     @foo.register("rich>100")
    ...     def _():
    ...         return "very rich"
    ...
    ...     foo()
    'very rich'

    """
    global get_version

    get_version_orig = get_version

    def get_version(package: str) -> "Version":
        version = version_dict.get(package)
        # we can't do version_dict.get(package, _get_version(package)) since the
        # 2nd argument may raise an error, e.g. for 'Python'
        if version is None:
            version = _get_version(package)
        return Version(version)

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
    """Dispatch functions based on versions of installed packages

    Transforms a function into a generic function, which can have different
    behaviours depending upon the version of installed packages. The decorated
    function acts as the default implementation, and additional implementations
    can be registered using the ``register()`` attribute of the generic
    function.

    The API is similar to the builtin ``functools.singledispatch``, only,
    instead of dispatching on the type of input arguments, this decorator
    dispatches on the versions of installed packages.

    Examples
    --------
    >>> @versiondispatch
    >>> def foo():
    ...     return "default behavior"
    ...
    >>> # the name of the registered function doesn't matter
    >>> @foo.register("sklearn>1.2")
    ... def _():
    ...     return "new behavior"
    ...
    >>> @foo.register("sklearn<1.0")
    ... def _():
    ...     return "old behavior"
    ...
    >>> foo()  # output depends on installed scikit-learn version

    """
    def __init__(self, func: AnyFunc) -> None:
        self._func = func

        self._funcname = getattr(self._func, '__name__', 'versiondispatch function')
        self._impl: AnyFunc = self._func  # use initial func by default
        self._matched_version = ""  # mostly for debugging
        self._registered_funcs: list[tuple[str, AnyFunc]] = []

    def _matches_all_versions(self, package_versions: list[tuple[str, str, BinOp]]) -> bool:
        return _matches_all_versions(package_versions)

    def register(self, package_versions: str) -> Callable[[AnyFunc], AnyFunc]:
        splits = [pv.strip() for pv in package_versions.replace(";", ",").split(",")]
        return self._register(splits)

    def _register(self, package_version_list: list[str]) -> Callable[[AnyFunc], AnyFunc]:
        packages_versions = []
        for package_version in package_version_list:
            package, version, operator = _split_package_version(package_version)

            if not (_is_valid_package(package) and _is_valid_version(version)):
                raise ValueError(
                    f"{self._funcname} uses incorrect version spec or package is not "
                    f"installed: {package_version}"
                )

            packages_versions.append((package, version, operator))

        def outer(func: AnyFunc) -> AnyFunc:
            if getattr(func, "_is_versiondispatched", False) is True:
                raise ValueError(
                    "You are nesting versiondispatch, which is not supported, instead provide "
                    "multiple version, e.g. '@versiondispatch(\"foo=1.0\", \"bar=2.0\")'"
                )

            try:
                self._impl._is_versiondispatched = True  # type: ignore
            except AttributeError:
                # TODO some builtin functions are immutable
                pass

            self._registered_funcs.append((",".join(package_version_list), func))

            if self._matches_all_versions(packages_versions):
                self._impl = func
                self._matched_version = version

            return self._impl

        outer._is_versiondispatched = True  # type: ignore
        return outer

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self._impl(*args, **kwargs)

    def __getstate__(self) -> Dict[str, Any]:
        return self.__dict__.copy()

    def reset(self) -> None:
        """Re-evaluate what function to dispatch to

        Usually, the version of a package is fixed, thus it's enough to check it
        once, at function definition time, and then leave it as is. In some
        circumstances, however, the version of a package can change later on;
        most notably, when the function was defined, pickled, and later loaded
        into an environment that uses different package versions. For this
        situation, the ``reset`` method can be used to evaluate the package
        versions again.

        """
        # clear registration
        self._impl = self._func
        self._matched_version = ""
        registered_functions = self._registered_funcs[:]
        self._registered_funcs.clear()

        # replay registration process
        for package_versions, func in registered_functions:
            self.register(package_versions)(func)

    def __setstate__(self, state: Dict[str, Any]) -> None:
        self.__dict__.update(state)
        self.reset()

    def __get__(self, obj: Any, cls: Any) -> AnyFunc:
        # This method is basically copied from functools.singledispatchmethod.
        # Not exactly sure why it works but it seems to do its job.
        def _method(*args: Any, **kwargs: Any) -> Any:
            method = self._impl
            return method.__get__(obj, cls)(*args, **kwargs)

        _method.__isabstractmethod__ = self.__isabstractmethod__  # type: ignore
        _method.register = self.register  # type: ignore
        update_wrapper(_method, self._func)
        return _method

    @property
    def __isabstractmethod__(self) -> bool:
        return getattr(self._impl, '__isabstractmethod__', False)


#################################################
# VENDERED VERSION FUNCTIONALITY FROM packaging #
#################################################

class InfinityType:  # pragma: no cover
    def __repr__(self) -> str:
        return "Infinity"

    def __hash__(self) -> int:
        return hash(repr(self))

    def __lt__(self, other: object) -> bool:
        return False

    def __le__(self, other: object) -> bool:
        return False

    def __eq__(self, other: object) -> bool:
        return isinstance(other, self.__class__)

    def __gt__(self, other: object) -> bool:
        return True

    def __ge__(self, other: object) -> bool:
        return True

    def __neg__(self: object) -> "NegativeInfinityType":
        return NegativeInfinity


Infinity = InfinityType()


class NegativeInfinityType:  # pragma: no cover
    def __repr__(self) -> str:
        return "-Infinity"

    def __hash__(self) -> int:
        return hash(repr(self))

    def __lt__(self, other: object) -> bool:
        return True

    def __le__(self, other: object) -> bool:
        return True

    def __eq__(self, other: object) -> bool:
        return isinstance(other, self.__class__)

    def __gt__(self, other: object) -> bool:
        return False

    def __ge__(self, other: object) -> bool:
        return False

    def __neg__(self: object) -> InfinityType:
        return Infinity


NegativeInfinity = NegativeInfinityType()

InfiniteTypes = Union[InfinityType, NegativeInfinityType]
PrePostDevType = Union[InfiniteTypes, Tuple[str, int]]
SubLocalType = Union[InfiniteTypes, int, str]
LocalType = Union[
    NegativeInfinityType,
    Tuple[
        Union[
            SubLocalType,
            Tuple[SubLocalType, str],
            Tuple[NegativeInfinityType, SubLocalType],
        ],
        ...,
    ],
]
CmpKey = Tuple[
    int, Tuple[int, ...], PrePostDevType, PrePostDevType, PrePostDevType, LocalType
]
LegacyCmpKey = Tuple[int, Tuple[str, ...]]

_Version = collections.namedtuple(
    "_Version", ["epoch", "release", "dev", "pre", "post", "local"]
)



def parse(version: str) -> "Version":  # pragma: no cover BB
    """
    Parse the given version string and return either a :class:`Version` object
    or a :class:`LegacyVersion` object depending on if the given version is
    a valid PEP 440 version or a legacy version.
    """
    try:
        return Version(version)
    except InvalidVersion:  # BB
        raise NotImplementedError("LegacyVersion not implemented")  # BB


class InvalidVersion(ValueError):  # pragma: no cover
    """
    An invalid version was found, users should refer to PEP 440.
    """


class _BaseVersion:  # pragma: no cover
    _key: CmpKey  # BB

    def __hash__(self) -> int:
        return hash(self._key)

    # Please keep the duplicated `isinstance` check
    # in the six comparisons hereunder
    # unless you find a way to avoid adding overhead function calls.
    def __lt__(self, other: "_BaseVersion") -> bool:
        if not isinstance(other, _BaseVersion):
            return NotImplemented

        return self._key < other._key

    def __le__(self, other: "_BaseVersion") -> bool:
        if not isinstance(other, _BaseVersion):
            return NotImplemented

        return self._key <= other._key

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, _BaseVersion):
            return NotImplemented

        return self._key == other._key

    def __ge__(self, other: "_BaseVersion") -> bool:
        if not isinstance(other, _BaseVersion):
            return NotImplemented

        return self._key >= other._key

    def __gt__(self, other: "_BaseVersion") -> bool:
        if not isinstance(other, _BaseVersion):
            return NotImplemented

        return self._key > other._key

    def __ne__(self, other: object) -> bool:
        if not isinstance(other, _BaseVersion):
            return NotImplemented

        return self._key != other._key


# Deliberately not anchored to the start and end of the string, to make it
# easier for 3rd party code to reuse
VERSION_PATTERN = r"""
    v?
    (?:
        (?:(?P<epoch>[0-9]+)!)?                           # epoch
        (?P<release>[0-9]+(?:\.[0-9]+)*)                  # release segment
        (?P<pre>                                          # pre-release
            [-_\.]?
            (?P<pre_l>(a|b|c|rc|alpha|beta|pre|preview))
            [-_\.]?
            (?P<pre_n>[0-9]+)?
        )?
        (?P<post>                                         # post release
            (?:-(?P<post_n1>[0-9]+))
            |
            (?:
                [-_\.]?
                (?P<post_l>post|rev|r)
                [-_\.]?
                (?P<post_n2>[0-9]+)?
            )
        )?
        (?P<dev>                                          # dev release
            [-_\.]?
            (?P<dev_l>dev)
            [-_\.]?
            (?P<dev_n>[0-9]+)?
        )?
    )
    (?:\+(?P<local>[a-z0-9]+(?:[-_\.][a-z0-9]+)*))?       # local version
"""


class Version(_BaseVersion):  # pragma: no cover

    _regex = re.compile(r"^\s*" + VERSION_PATTERN + r"\s*$", re.VERBOSE | re.IGNORECASE)

    def __init__(self, version: str) -> None:

        # Validate the version and parse it into pieces
        match = self._regex.search(version)
        if not match:
            raise InvalidVersion(f"Invalid version: '{version}'")

        # Store the parsed out pieces of the version
        self._version = _Version(
            epoch=int(match.group("epoch")) if match.group("epoch") else 0,
            release=tuple(int(i) for i in match.group("release").split(".")),
            pre=_parse_letter_version(match.group("pre_l"), match.group("pre_n")),
            post=_parse_letter_version(
                match.group("post_l"), match.group("post_n1") or match.group("post_n2")
            ),
            dev=_parse_letter_version(match.group("dev_l"), match.group("dev_n")),
            local=_parse_local_version(match.group("local")),
        )

        # Generate a key which will be used for sorting
        self._key = _cmpkey(
            self._version.epoch,
            self._version.release,
            self._version.pre,
            self._version.post,
            self._version.dev,
            self._version.local,
        )

    def __repr__(self) -> str:
        return f"<Version('{self}')>"

    def __str__(self) -> str:
        parts = []

        # Epoch
        if self.epoch != 0:
            parts.append(f"{self.epoch}!")

        # Release segment
        parts.append(".".join(str(x) for x in self.release))

        # Pre-release
        if self.pre is not None:
            parts.append("".join(str(x) for x in self.pre))

        # Post-release
        if self.post is not None:
            parts.append(f".post{self.post}")

        # Development release
        if self.dev is not None:
            parts.append(f".dev{self.dev}")

        # Local version segment
        if self.local is not None:
            parts.append(f"+{self.local}")

        return "".join(parts)

    @property
    def epoch(self) -> int:
        _epoch: int = self._version.epoch
        return _epoch

    @property
    def release(self) -> Tuple[int, ...]:
        _release: Tuple[int, ...] = self._version.release
        return _release

    @property
    def pre(self) -> Optional[Tuple[str, int]]:
        _pre: Optional[Tuple[str, int]] = self._version.pre
        return _pre

    @property
    def post(self) -> Optional[int]:
        return self._version.post[1] if self._version.post else None

    @property
    def dev(self) -> Optional[int]:
        return self._version.dev[1] if self._version.dev else None

    @property
    def local(self) -> Optional[str]:
        if self._version.local:
            return ".".join(str(x) for x in self._version.local)
        else:
            return None

    @property
    def public(self) -> str:
        return str(self).split("+", 1)[0]

    @property
    def base_version(self) -> str:
        parts = []

        # Epoch
        if self.epoch != 0:
            parts.append(f"{self.epoch}!")

        # Release segment
        parts.append(".".join(str(x) for x in self.release))

        return "".join(parts)

    @property
    def is_prerelease(self) -> bool:
        return self.dev is not None or self.pre is not None

    @property
    def is_postrelease(self) -> bool:
        return self.post is not None

    @property
    def is_devrelease(self) -> bool:
        return self.dev is not None

    @property
    def major(self) -> int:
        return self.release[0] if len(self.release) >= 1 else 0

    @property
    def minor(self) -> int:
        return self.release[1] if len(self.release) >= 2 else 0

    @property
    def micro(self) -> int:
        return self.release[2] if len(self.release) >= 3 else 0


def _parse_letter_version(
    letter: str, number: Union[str, bytes, SupportsInt]
) -> Optional[Tuple[str, int]]:  # pragma: no cover

    if letter:
        # We consider there to be an implicit 0 in a pre-release if there is
        # not a numeral associated with it.
        if number is None:
            number = 0

        # We normalize any letters to their lower case form
        letter = letter.lower()

        # We consider some words to be alternate spellings of other words and
        # in those cases we want to normalize the spellings to our preferred
        # spelling.
        if letter == "alpha":
            letter = "a"
        elif letter == "beta":
            letter = "b"
        elif letter in ["c", "pre", "preview"]:
            letter = "rc"
        elif letter in ["rev", "r"]:
            letter = "post"

        return letter, int(number)
    if not letter and number:
        # We assume if we are given a number, but we are not given a letter
        # then this is using the implicit post release syntax (e.g. 1.0-1)
        letter = "post"

        return letter, int(number)

    return None


_local_version_separators = re.compile(r"[\._-]")


def _parse_local_version(local: str) -> Optional[LocalType]:  # pragma: no cover
    """
    Takes a string like abc.1.twelve and turns it into ("abc", 1, "twelve").
    """
    if local is not None:
        return tuple(
            part.lower() if not part.isdigit() else int(part)
            for part in _local_version_separators.split(local)
        )
    return None


def _cmpkey(
    epoch: int,
    release: Tuple[int, ...],
    pre: Optional[Tuple[str, int]],
    post: Optional[Tuple[str, int]],
    dev: Optional[Tuple[str, int]],
    local: Optional[Tuple[SubLocalType]],
) -> CmpKey:  # pragma: no cover

    # When we compare a release version, we want to compare it with all of the
    # trailing zeros removed. So we'll use a reverse the list, drop all the now
    # leading zeros until we come to something non zero, then take the rest
    # re-reverse it back into the correct order and make it a tuple and use
    # that for our sorting key.
    _release = tuple(
        reversed(list(itertools.dropwhile(lambda x: x == 0, reversed(release))))
    )

    # We need to "trick" the sorting algorithm to put 1.0.dev0 before 1.0a0.
    # We'll do this by abusing the pre segment, but we _only_ want to do this
    # if there is not a pre or a post segment. If we have one of those then
    # the normal sorting rules will handle this case correctly.
    if pre is None and post is None and dev is not None:
        _pre: PrePostDevType = NegativeInfinity
    # Versions without a pre-release (except as noted above) should sort after
    # those with one.
    elif pre is None:
        _pre = Infinity
    else:
        _pre = pre

    # Versions without a post segment should sort before those with one.
    if post is None:
        _post: PrePostDevType = NegativeInfinity

    else:
        _post = post

    # Versions without a development segment should sort after those with one.
    if dev is None:
        _dev: PrePostDevType = Infinity

    else:
        _dev = dev

    if local is None:
        # Versions without a local segment should sort before those with one.
        _local: LocalType = NegativeInfinity
    else:
        # Versions with a local segment need that segment parsed to implement
        # the sorting rules in PEP440.
        # - Alpha numeric segments sort before numeric segments
        # - Alpha numeric segments sort lexicographically
        # - Numeric segments sort numerically
        # - Shorter versions sort before longer versions when the prefixes
        #   match exactly
        _local = tuple(
            (i, "") if isinstance(i, int) else (NegativeInfinity, i) for i in local
        )

    return epoch, _release, _pre, _post, _dev, _local
