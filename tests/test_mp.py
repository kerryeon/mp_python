from mp import PythonInterpreter
from mp import RemoteInterpreter

PATH_SCRIPT = 'script'
VARS_TEST = ['at', 'bt', ]


def _curdir():
    import os
    return os.path.abspath(os.path.join(__file__, os.path.pardir))


def _test(interpreter):
    for var_name in VARS_TEST:
        assert interpreter.plan.attr[var_name].get_value()


def test_python():
    interpreter = PythonInterpreter(_curdir())
    interpreter('save %s' % PATH_SCRIPT)
    _test(interpreter)


def test_remote():
    # not totally implemented yet
    pass


if __name__ == '__main__':
    test_python()
    test_remote()
