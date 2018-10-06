from core import attribute as _attribute
from core import builtins as _builtins
from core import data
from core.error import BaseError, RequiredError
from core.expression import Expression as Exp
from core.graph import Graph
from core.io import IO


class Plan:
    ATTR = _attribute
    BUILTINS = _builtins
    CLASS_IO = IO

    def __init__(self, dir_process: str, message_to_data):
        self.code_to_data = message_to_data
        self.attr = self.ATTR.AttrDict()
        self.io = self.CLASS_IO(dir_process)
        self.graph = Graph()

    # execute along IO
    def execute(self):
        try:
            for var_name, append in self.graph.ios.items():
                var = self.graph.vars[var_name]
                # save
                if append:
                    value = self._execute_recursive(var)
                # delete
                else:
                    value = None
                    var.code = None
                    var.toward = None
                self.io.set(var_name, value)
        # if error : finish
        except BaseError as e:
            self.graph.clean()
            raise e
        self.graph.clean()

    # execute recursively along IO
    def _execute_recursive(self, toward: data.Variable):
        # echo
        if toward is None:
            return None
        # if required
        if toward.is_required:
            toward = self._find_variable(toward)
        # is variable
        if type(toward) is data.Variable:
            var = self.attr[toward.name]
            if toward.toward is not None:
                if toward.encode() != var.code:
                    var.toward = self._execute_recursive(toward.toward)
                    var.code = toward.encode()
            return var
        # is constant
        if type(toward) is data.Constant:
            # unsupported type
            if toward.num_type not in self.ATTR.map_num_type.keys():
                raise SyntaxError(toward.num_type)
            # create new numpy object
            value = self._new_const(toward)
            const = self.ATTR.AttrConst(toward.encode(), value)
            return const
        # is operator
        if type(toward) is data.Operator:
            # =
            if toward.op in Exp.IS:
                var = self.attr[toward.sub]
                # reuse
                if var.reusable:
                    return var
                var.value = self._execute_recursive(toward.obj)
                return var
            # the others
            args = self.ATTR.AttrList([toward.sub, toward.obj, toward.step, *toward.args], self._execute_recursive)
            op = self.ATTR.AttrOP(toward.op, args)
            return op
        # is slicing
        if type(toward) is data.Indexed:
            args = self.ATTR.AttrList(toward.args, self._execute_recursive)
            sub = self._execute_recursive(toward.sub)
            op = self.ATTR.AttrIndexed(sub, args)
            return op
        # is view
        if type(toward) is data.View:
            args = self.ATTR.AttrList(toward.args, self._execute_recursive)
            sub = self._execute_recursive(toward.sub)
            op = self.ATTR.AttrView(sub, args)
            return op
        # is method
        if type(toward) is data.Method:
            args = self.ATTR.AttrList(toward.args, self._execute_recursive)
            # external methods
            if toward.sub in Exp.BUILTINS:
                external_method = Exp.BUILTINS[toward.sub]
                return external_method(toward, args)
        raise NotImplementedError

    # find variable from file-system
    def _find_variable(self, toward):
        name = toward.name
        # if not variable
        if name is None:
            raise RequiredError('None')
        value = self.io.get(name)
        # not found
        if value is None:
            raise RequiredError(name)
        # if graph
        if type(value) is str:
            values = list(self.code_to_data(value))
            for value in values:
                self.push(value)
            self._execute_recursive(toward)
            return toward
        elif type(value) is data.Constant:
            toward.toward = value
            self._execute_recursive(toward)
            return toward
        raise NotImplementedError

    # return new constant
    def _new_const(self, toward):
        raise NotImplementedError

    # update graph
    def push(self, value):
        # has query
        if value is not None:
            value.update_graph(self.graph)

    def get_builtin_methods(self):
        return [t for t in dir(self.BUILTINS) if not t.startswith('_')], self.BUILTINS
