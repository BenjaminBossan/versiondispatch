import pickle

import pytest
from importlib.metadata import version as _get_version

from src import versiondispatch, pretend_version

# sanity checks
major = int(_get_version("rich").split(".", 1)[0])
assert 1 <= major < 1000
major = int(_get_version("pytest").split(".", 1)[0])
assert 1 <= major < 1000


class TestOneCheck:
    # check a single package

    def get_func(self):
        @versiondispatch
        def func(bar, baz="baz"):
            return f"default {bar}-{baz}"

        @func.register("rich<1.0")
        def _old(bar, baz="baz"):
            return f"old {bar}-{baz}"

        @func.register("rich>=1000")
        def _new(bar, baz="baz"):
            return f"new {bar}-{baz}"

        @func.register("rich==1.2.3")
        def _exact(bar, baz="baz"):
            return f"exact {bar}-{baz}"

        return func

    def test_no_match(self):
        func = self.get_func()
        assert func("hi", baz="there") == "default hi-there"

    def test_lt(self):
        with pretend_version({"rich": "0.1"}):
            func = self.get_func()
            assert func("hi", baz="there") == "old hi-there"

    def test_gt(self):
        with pretend_version({"rich": "1001.0.0"}):
            func = self.get_func()
            assert func("hi", baz="there") == "new hi-there"

    def test_exact(self):
        with pretend_version({"rich": "1.2.3"}):
            func = self.get_func()
            assert func("hi", baz="there") == "exact hi-there"


class TestMultipleChecks:
    # check two package versions

    def get_func(self):
        @versiondispatch
        def func(bar, baz="baz"):
            return f"default default {bar}-{baz}"

        @func.register("rich<1.0, pytest<=1")
        def _old_old(bar, baz="baz"):
            return f"old old {bar}-{baz}"

        @func.register("rich<1.0;pytest>1234.5.6")
        def _old_new(bar, baz="baz"):
            return f"old new {bar}-{baz}"

        @func.register("rich>=1000 , pytest <= 1")
        def _new_old(bar, baz="baz"):
            return f"new old {bar}-{baz}"

        @func.register("rich>=1000.0 ;pytest>1234.5.6")
        def _new_new(bar, baz="baz"):
            return f"new new {bar}-{baz}"

        return func

    def test_no_match(self):
        func = self.get_func()
        assert func("hi", baz="there") == "default default hi-there"

    def test_only_first_matches(self):
        with pretend_version({"rich": "0.1", "pytest": "3.2.1"}):
            func = self.get_func()
            assert func("hi", baz="there") == "default default hi-there"

    def test_only_second_matches(self):
        with pretend_version({"rich": "3.2.1", "pytest": "0.0.1"}):
            func = self.get_func()
            assert func("hi", baz="there") == "default default hi-there"

    def test_both_match_lt_lt(self):
        with pretend_version({"rich": "0.1", "pytest": "0.0.1"}):
            func = self.get_func()
            assert func("hi", baz="there") == "old old hi-there"

    def test_both_match_lt_gt(self):
        with pretend_version({"rich": "0.1", "pytest": "9999.99.99dev"}):
            func = self.get_func()
            assert func("hi", baz="there") == "old new hi-there"

    def test_both_match_gt_lt(self):
        with pretend_version({"rich": "5555", "pytest": "0.0.1"}):
            func = self.get_func()
            assert func("hi", baz="there") == "new old hi-there"

    def test_both_match_gt_gt(self):
        with pretend_version({"rich": "5555", "pytest": "9999.99.99dev"}):
            @versiondispatch
            def func(bar, baz="baz"):
                return f"default default {bar}-{baz}"

            @func.register("rich<1.0, pytest<=1")
            def _old_old(bar, baz="baz"):
                return f"old old {bar}-{baz}"

            @func.register("rich<1.0;pytest>1234.5.6")
            def _old_new(bar, baz="baz"):
                return f"old new {bar}-{baz}"

            @func.register("rich>=1000 , pytest <= 1")
            def _new_old(bar, baz="baz"):
                return f"new old {bar}-{baz}"

            @func.register("rich>=1000.0 ;pytest>1234.5.6")
            def _new_new(bar, baz="baz"):
                return f"new new {bar}-{baz}"

            assert func("hi", baz="there") == "new new hi-there"

    def test_both_match_exact_exact(self):
        with pretend_version({"rich": "1.2.3", "pytest": "3.2.1"}):
            @versiondispatch
            def func(bar, baz="baz"):
                return f"default default {bar}-{baz}"

            @func.register("rich<1.0, pytest<=1")
            def _old_old(bar, baz="baz"):
                return f"old old {bar}-{baz}"

            @func.register("rich<1.0;pytest>1234.5.6")
            def _old_new(bar, baz="baz"):
                return f"old new {bar}-{baz}"

            @func.register("rich>=1000 , pytest <= 1")
            def _new_old(bar, baz="baz"):
                return f"new old {bar}-{baz}"

            @func.register("rich>=1000.0 ;pytest>1234.5.6")
            def _new_new(bar, baz="baz"):
                return f"new new {bar}-{baz}"

            @func.register("rich==1.2.3 ;pytest==3.2.1")
            def _exact_exact(bar, baz="baz"):
                return f"exact exact {bar}-{baz}"

            assert func("hi", baz="there") == "exact exact hi-there"


class TestMixedMultipleChecks:
    # partially check one or two package versions

    def get_func(self):
        @versiondispatch
        def func(bar, baz="baz"):
            return f"default default {bar}-{baz}"

        @func.register("rich<1.0")
        def _old_rich(bar, baz="baz"):
            return f"old rich {bar}-{baz}"

        @func.register("pytest<1.0")
        def _old_pytest(bar, baz="baz"):
            return f"old pytest {bar}-{baz}"

        @func.register("rich<1.0, pytest<1.0")
        def _old_old(bar, baz="baz"):
            return f"old old {bar}-{baz}"

        return func

    def test_no_match(self):
        func = self.get_func()
        assert func("hi", baz="there") == "default default hi-there"

    def test_old_rich_match(self):
        with pretend_version({"rich": "0.1.2"}):
            func = self.get_func()
            assert func("hi", baz="there") == "old rich hi-there"

    def test_old_pytest_match(self):
        with pretend_version({"pytest": "0.1.2"}):
            func = self.get_func()
            assert func("hi", baz="there") == "old pytest hi-there"

    def test_both_match(self):
        with pretend_version({"rich": "0.1.2", "pytest": "0.1.2"}):
            func = self.get_func()
            assert func("hi", baz="there") == "old old hi-there"


def test_nested_versiondispatch_raises():
    match = "You are nesting versiondispatch, which is not supported"

    @versiondispatch
    def func():
        return "func"

    with pytest.raises(ValueError, match=match):
        @func.register("rich<1.0")
        @func.register("pytest<=1")
        def _():
            return "bar"


def test_invalid_package_version_spec():
    @versiondispatch
    def func():
        return "foo"

    match = "Version not correctly specified, should be like"
    with pytest.raises(ValueError, match=match):
        @func.register("rich=1.0")
        def _(bar, baz="baz"):
            return "bar"


def test_invalid_version_spec():
    @versiondispatch
    def func():
        return "foo"

    match = "func uses incorrect version spec: rich==1.foo.0"
    with pytest.raises(ValueError, match=match):
        @func.register("rich==1.foo.0")
        def _(bar, baz="baz"):
            return "bar"


def test_invalid_package():
    @versiondispatch
    def func():
        return "foo"

    match = "func uses incorrect version spec: rich kid==1.0"
    with pytest.raises(ValueError, match=match):
        @func.register("rich kid==1.0")
        def _(bar, baz="baz"):
            return "bar"


def test_version_check_performed_only_once():
    # Test that the version check is only performed once when registering, not
    # once for each function call. This test relies on implementation details of
    # the class
    num_calls = 0

    class myversiondispatch(versiondispatch):
        def _matches_all_versions(self, package_versions):
            nonlocal num_calls
            num_calls += 1
            return super()._matches_all_versions(package_versions)

    @myversiondispatch
    def func():
        return 0

    @func.register("rich<1.0")
    def _():
        return 1

    for _ in range(10):
        func()

    assert num_calls == 1

    @func.register("rich>=1000")
    def _():
        return 2

    for _ in range(10):
        func()

    assert num_calls == 2


class TestPickle:
    # Tests centered around pickling the decorated function. Note that this test
    # requires to use defined functions, such as min and max; locally defined
    # functions are not pickleable to begin with.
    def test_pickleable_default(self):
        func = versiondispatch(min)

        func.register("rich<1.0")(max)

        loaded = pickle.loads(pickle.dumps(func))
        assert loaded([1, 2, 3]) == 1

    def test_pickleable_non_default(self):
        with pretend_version({"rich": "0.1"}):
            func = versiondispatch(min)

            func.register("rich<1.0")(max)

            loaded = pickle.loads(pickle.dumps(func))
            assert loaded([1, 2, 3]) == 3

    def test_version_changes_after_pickling(self):
        # when pickling the function on version X and unpickling it on version
        # Y, version Y should take precedence
        func = versiondispatch(min)
        func.register("rich<1.0")(max)
        pickled = pickle.dumps(func)

        with pretend_version({"rich": "0.1"}):
            loaded = pickle.loads(pickle.dumps(func))
            assert loaded([1, 2, 3]) == 3
