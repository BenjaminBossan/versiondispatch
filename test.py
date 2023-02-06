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

    match = (
        "func uses incorrect version spec or package is not installed: rich==1.foo.0"
    )
    with pytest.raises(ValueError, match=match):

        @func.register("rich==1.foo.0")
        def _(bar, baz="baz"):
            return "bar"


def test_invalid_package():
    @versiondispatch
    def func():
        return "foo"

    match = (
        "func uses incorrect version spec or package is not installed: rich kid==1.0"
    )
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
    # requires to use existing functions, such as min and max; locally defined
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

        with pretend_version({"rich": "0.1"}):
            loaded = pickle.loads(pickle.dumps(func))
            assert loaded([1, 2, 3]) == 3


class TestMethodNoArgs:
    # versiondispatch should work on methods too, not only functions
    # Here: method without args
    def get_instance(self):
        class MyClass:
            @versiondispatch
            def func(self):
                return "default"

            @func.register("rich<1.0")
            def _old(self):
                return "old"

            @func.register("rich>=1000")
            def _new(self):
                return "new"

            @func.register("rich==1.2.3")
            def _exact(self):
                return "exact"

        return MyClass()

    def test_no_match(self):
        instance = self.get_instance()
        assert instance.func() == "default"

    def test_lt(self):
        with pretend_version({"rich": "0.1"}):
            instance = self.get_instance()
            assert instance.func() == "old"

    def test_gt(self):
        with pretend_version({"rich": "1001.0.0"}):
            instance = self.get_instance()
            assert instance.func() == "new"

    def test_exact(self):
        with pretend_version({"rich": "1.2.3"}):
            instance = self.get_instance()
            assert instance.func() == "exact"


class TestMethodWithArgs:
    # versiondispatch should work on methods too, not only functions
    # Here: method with args and kwargs
    def get_instance(self):
        class MyClass:
            @versiondispatch
            def func(self, bar, baz="baz"):
                return f"default {bar}-{baz}"

            @func.register("rich<1.0")
            def _old(self, bar, baz="baz"):
                return f"old {bar}-{baz}"

            @func.register("rich>=1000")
            def _new(self, bar, baz="baz"):
                return f"new {bar}-{baz}"

            @func.register("rich==1.2.3")
            def _exact(self, bar, baz="baz"):
                return f"exact {bar}-{baz}"

        return MyClass()

    def test_no_match(self):
        instance = self.get_instance()
        assert instance.func("hi", baz="there") == "default hi-there"

    def test_lt(self):
        with pretend_version({"rich": "0.1"}):
            instance = self.get_instance()
            assert instance.func("hi", baz="there") == "old hi-there"

    def test_gt(self):
        with pretend_version({"rich": "1001.0.0"}):
            instance = self.get_instance()
            assert instance.func("hi", baz="there") == "new hi-there"

    def test_exact(self):
        with pretend_version({"rich": "1.2.3"}):
            instance = self.get_instance()
            assert instance.func("hi", baz="there") == "exact hi-there"


class TestStaticMethod:
    # versiondispatch should work on methods too, not only functions
    # Here: staticmethod
    def get_instance(self):
        class MyClass:
            @versiondispatch
            @staticmethod
            def func():
                return "default"

            @func.register("rich<1.0")
            @staticmethod
            def _old():
                return "old"

            @func.register("rich>=1000")
            @staticmethod
            def _new():
                return "new"

            @func.register("rich==1.2.3")
            @staticmethod
            def _exact():
                return "exact"

        return MyClass()

    def test_no_match(self):
        instance = self.get_instance()
        assert instance.func() == "default"

    def test_lt(self):
        with pretend_version({"rich": "0.1"}):
            instance = self.get_instance()
            assert instance.func() == "old"

    def test_gt(self):
        with pretend_version({"rich": "1001.0.0"}):
            instance = self.get_instance()
            assert instance.func() == "new"

    def test_exact(self):
        with pretend_version({"rich": "1.2.3"}):
            instance = self.get_instance()
            assert instance.func() == "exact"


class TestClassmethod:
    # versiondispatch should work on methods too, not only functions
    # Here: classmethod
    def get_instance(self):
        class MyClass:
            @versiondispatch
            @classmethod
            def func(cls):
                return "default"

            @func.register("rich<1.0")
            @classmethod
            def _old(cls):
                return "old"

            @func.register("rich>=1000")
            @classmethod
            def _new(cls):
                return "new"

            @func.register("rich==1.2.3")
            @classmethod
            def _exact(cls):
                return "exact"

        return MyClass()

    def test_no_match(self):
        instance = self.get_instance()
        assert instance.func() == "default"

    def test_lt(self):
        with pretend_version({"rich": "0.1"}):
            instance = self.get_instance()
            assert instance.func() == "old"

    def test_gt(self):
        with pretend_version({"rich": "1001.0.0"}):
            instance = self.get_instance()
            assert instance.func() == "new"

    def test_exact(self):
        with pretend_version({"rich": "1.2.3"}):
            instance = self.get_instance()
            assert instance.func() == "exact"


class MyClass:
    @versiondispatch
    def func(self):
        return "default"

    @func.register("rich<1.0")
    def _old(self):
        return "old"

    @func.register("rich>=1000")
    def _new(self):
        return "new"

    @func.register("rich==1.2.3")
    def _exact(self):
        return "exact"


def test_decorated_method_pickleable():
    # Test that class instances with decorated methods are pickleable.
    # Unfortunately, it's not easily possible to check this with different rich
    # versions, because the class must be defined on the root level, or else it
    # cannot be pickled.
    instance = MyClass()
    assert instance.func() == "default"

    loaded = pickle.loads(pickle.dumps(instance))
    assert loaded.func() == "default"


class TestCheckPythonVersion:
    # dispatching on Python version should be possible

    def get_func(self):
        @versiondispatch
        def func():
            return "default"

        @func.register("Python<3.8")
        def _old():
            return "old"

        @func.register("Python>=4")
        def _new():
            return "new"

        @func.register("Python==3.11.12")
        def _exact():
            return "exact"

        return func

    def test_no_match(self):
        func = self.get_func()
        assert func() == "default"

    def test_lt(self):
        with pretend_version({"Python": "2.7"}):
            func = self.get_func()
            assert func() == "old"

    def test_gt(self):
        with pretend_version({"Python": "4"}):
            func = self.get_func()
            assert func() == "new"

    def test_exact(self):
        with pretend_version({"Python": "3.11.12"}):
            func = self.get_func()
            assert func() == "exact"


def test_doc_is_conserved_default():
    @versiondispatch
    def func():
        """This is a docstring"""
        return "default"

    @func.register("rich<1.0")
    def _():
        return "old"

    assert func.__doc__ == "This is a docstring"


def test_doc_is_conserved_registered():
    @versiondispatch
    def func():
        """This is a docstring"""
        return "default"

    @func.register("rich>1.0")
    def _():
        return "old"

    assert func.__doc__ == "This is a docstring"


class TestCheckOS:
    # dispatching on operating system

    def get_func(self):
        @versiondispatch
        def func():
            return "Linux"

        @func.register("os==win32")
        def _():
            return "Windows"

        @func.register("os==Darwin")
        def _():
            return "MacOS"

        return func

    def test_default(self):
        func = self.get_func()
        assert func() == "Linux"

    def test_win(self):
        with pretend_version({"os": "win32"}):
            func = self.get_func()
            assert func() == "Windows"

    def test_gt(self):
        with pretend_version({"os": "Darwin"}):
            func = self.get_func()
            assert func() == "MacOS"

    @pytest.mark.parametrize("op", ["<", "<=", ">", ">="])
    def test_operator_not_eq_raises(self, op):
        @versiondispatch
        def func():
            return "Linux"

        match = "string comparison only possible with =="
        with pytest.raises(ValueError, match=match):

            @func.register(f"os{op}win32")
            def _old():
                return "Windows"


class TestWarnings:
    # test that warnings are shown if the version matches

    # Note that this test requires to use existing functions, such as min and
    # max; locally defined functions are not pickleable to begin with.

    def get_func(self, warn_for=None):
        assert not isinstance(warn_for, str)
        warn_for = warn_for or ()

        @versiondispatch
        def func():
            return "default"

        # fmt: off
        if "old" in warn_for:
            @func.register("rich<1.0", warning=DeprecationWarning("warning for old"))
            def _old():
                return "old"
        else:
            @func.register("rich<1.0")
            def _old():
                return "old"

        if "new" in warn_for:
            @func.register("rich>=1000", warning=DeprecationWarning("warning for new"))
            def _new():
                return "new"
        else:
            @func.register("rich>=1000")
            def _new():
                return "new"
        # fmt: on

        return func

    def test_default_no_warning(self, recwarn):
        # no warnings registered
        func = self.get_func()
        assert func() == "default"
        assert not recwarn.list

        # warnings registerd for old and new but default called
        func = self.get_func(warn_for=["old", "new"])
        assert func() == "default"
        assert not recwarn.list

    def test_non_default_no_warning(self, recwarn):
        # no warnings registered
        with pretend_version({"rich": "0.1"}):
            func = self.get_func()
        assert func() == "old"
        assert not recwarn.list

        # warning registered for new but old called
        with pretend_version({"rich": "0.1"}):
            func = self.get_func(warn_for=["new"])
        assert func() == "old"
        assert not recwarn.list

        # warning registered for new but old called
        with pretend_version({"rich": "1234"}):
            func = self.get_func(warn_for=["old"])
        assert func() == "new"
        assert not recwarn.list

    def test_non_default_warning(self, recwarn):
        # warning registered, and shown, for old
        with pretend_version({"rich": "0.1"}):
            func = self.get_func(warn_for=["old"])

        assert func() == "old"
        assert len(recwarn.list) == 1
        assert recwarn.list[0].message.args[0] == "warning for old"

    def test_non_default_multiple_warnings_registered(self, recwarn):
        # warning registered for new and old, but warning for new should be
        # shown
        with pretend_version({"rich": "1234"}):
            func = self.get_func(warn_for=["new", "old"])

        assert func() == "new"
        assert len(recwarn.list) == 1
        assert recwarn.list[0].message.args[0] == "warning for new"

    def test_unpickle_on_different_version_shows_no_warning(self, recwarn):
        # At function definition time, the version is new, which has a warning,
        # but when unpickling, the version is old, which has no warning.
        # Therefore, there should be no warning.
        func = versiondispatch(min)

        with pretend_version({"rich": "1234"}):
            func.register("rich<1.0")(max)

            warning = DeprecationWarning("warning for new")
            func.register("rich>=1000", warning=warning)(sum)
            pickled = pickle.dumps(func)

            # sanity check that there is a registered warning
            assert func._warning

        with pretend_version({"rich": "0.1"}):
            loaded = pickle.loads(pickled)

        assert loaded([1, 2, 3]) == 3
        assert not recwarn.list

    def test_unpickle_on_different_version_shows_correct_warning(self, recwarn):
        # At function definition time, the version is old, but when unpickling,
        # the version is new. Therefore, the warning for new should be shown.
        func = versiondispatch(min)
        with pretend_version({"rich": "0.1"}):
            warning_old = DeprecationWarning("warning for old")
            func.register("rich<1.0", warning=warning_old)(max)

            warning_new = DeprecationWarning("warning for new")
            func.register("rich>=1000", warning=warning_new)(sum)

            # sanity check that the registered warning is for old
            assert func._warning.args[0] == "warning for old"

        pickled = pickle.dumps(func)
        with pretend_version({"rich": "1234"}):
            loaded = pickle.loads(pickled)

        assert loaded([1, 2, 3]) == 6
        assert len(recwarn.list) == 1
        assert recwarn.list[0].message.args[0] == "warning for new"
