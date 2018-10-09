from mp.core import attribute as _attribute
from mp.core import builtins as _builtins
from mp.core import data
from mp.core.error import BaseError, RequiredError
from mp.core.expression import Expression as Exp
from mp.core.graph import Graph
from mp.core.io import IO


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
        self.graph.lock_point = True
        try:
            for var_name, append in self.graph.ios.items():
                var = self.graph.vars[var_name]
                # save
                if append:
                    value = self._execute_recursive(var)
                    value.get_value()
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
        self.graph.lock_point = False
        self.graph.clean()

    # execute recursively along IO
    def _execute_recursive(self, toward: data.Variable):
        # echo
        if toward is None:
            return None
        # if required
        if toward.is_required:
            var = self._find_variable(toward)
            return var
        # is variable
        if type(toward) is data.Variable:
            return self._execute_variable(toward)
        # is constant
        if type(toward) is data.Constant:
            return self._execute_constant(toward)
        # is operator
        if type(toward) is data.Operator:
            return self._execute_operator(toward)
        # is slicing
        if type(toward) is data.Indexed:
            return self._execute_indexed(toward)
        # is view
        if type(toward) is data.View:
            return self._execute_view(toward)
        # is method
        if type(toward) is data.Method:
            return self._execute_method(toward)
        raise NotImplementedError

    def _execute_variable_modify(self, var, toward):
        var.toward = self._execute_recursive(toward.toward)
        var.code = toward.encode()
        return var

    def _execute_variable_point(self, var, toward):
        toward.is_pointer = False
        # find file first
        try:
            var = self._find_variable(toward)
        # file not exist
        except RequiredError:
            self._execute_variable_modify(var, toward)

    def _execute_variable(self, toward: data.Variable):
        var = self.attr[toward.name]
        # load ahead
        if toward.is_pointer:
            self._execute_variable_point(var, toward)
        # if changed or not data
        if toward.toward is not None:
            if toward.encode() != var.code or not var.is_data:
                self._execute_variable_modify(var, toward)
        return var

    def _execute_constant(self, toward: data.Constant):
        # unsupported type
        if toward.num_type not in self.ATTR.map_num_type.keys():
            raise SyntaxError(toward.num_type)
        # create new numpy object
        value = self._new_const(toward)
        const = self.ATTR.AttrConst(toward.encode(), value)
        return const

    def _execute_operator_modify(self, toward):
        var = self.attr[toward.sub]
        # reuse
        if var.reusable:
            return var
        var.value = self._execute_recursive(toward.obj)
        return var

    def _execute_operator_repeat_call(self, var, args, toward):
        toward.is_method = True
        toward.is_method_delegate = True
        toward.is_data = False
        obj = args.list[1]
        var.repeat = obj
        var.is_data = False
        return var

    def _execute_operator(self, toward: data.Operator):
        # =
        if toward.op in Exp.IS:
            return self._execute_operator_modify(toward)
        # * : if repeating calls
        args = self.ATTR.AttrList([toward.sub, toward.obj, toward.step, *toward.args], self._execute_recursive)
        sub = args.list[0]
        if sub.toward is not None:
            if sub.toward.is_method:
                if toward.op in Exp.MUL:
                    return self._execute_operator_repeat_call(sub, args, toward)
        # the others
        op = self.ATTR.AttrOP(toward.op, args)
        return op

    def _execute_indexed_delegate(self, args, toward):
        method = toward.sub
        while len(method.args) >= 1:
            method = method.args[0]
        var = method.sub
        if var in Exp.BUILTINS:
            external_method = Exp.BUILTINS[var]
        else:
            raise NotImplementedError
        method = self.ATTR.AttrMethod(var, external_method, toward, args)
        return method

    def _execute_indexed_delegate_repeat(self, args, repeat, toward):
        method = toward.sub.toward
        while len(method.args) >= 1:
            method = method.args[0]
        var = method.sub.toward.sub
        if var in Exp.BUILTINS:
            external_method = Exp.BUILTINS[var]
        else:
            raise NotImplementedError
        method = self.ATTR.AttrMethod(var, external_method, toward, args, repeat=repeat)
        return method

    def _execute_indexed(self, toward: data.Indexed):
        # if pointing method
        args = self.ATTR.AttrList(toward.args, self._execute_recursive)
        if toward.sub.is_method_delegate:
            return self._execute_indexed_delegate(args, toward)
        # if pointing repeating method
        sub = self._execute_recursive(toward.sub)
        if toward.sub.toward is not None:
            if toward.sub.toward.is_method_delegate:
                return self._execute_indexed_delegate_repeat(args, sub.toward.repeat, toward)
        # else
        op = self.ATTR.AttrIndexed(sub, args)
        return op

    def _execute_view(self, toward: data.View):
        args = self.ATTR.AttrList(toward.args, self._execute_recursive)
        sub = self._execute_recursive(toward.sub)
        op = self.ATTR.AttrView(sub, args)
        return op

    def _execute_method_delegate(self, var, args, toward):
        toward.is_data = False
        # if recursive pointing
        if len(args) >= 1:
            arg = args.list[0]
            if arg.is_method:
                if arg.args is None:
                    arg.toward = toward
                    arg.code = toward.encode()
                    return arg
        external_method = Exp.BUILTINS[var]
        method = self.ATTR.AttrMethod(var, external_method, toward, None)
        return method

    def _execute_method_external_method(self, var, args, toward):
        external_method = Exp.BUILTINS[var]
        method = self.ATTR.AttrMethod(var, external_method, toward, args)
        return method

    def _execute_method(self, toward: data.Method):
        sub = toward.sub
        args = self.ATTR.AttrList(toward.args, self._execute_recursive)
        # if pointing method
        if toward.is_method_delegate:
            return self._execute_method_delegate(sub, args, toward)
        # else
        # external methods
        if sub in Exp.BUILTINS:
            return self._execute_method_external_method(sub, args, toward)
        # user-defined methods
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
            var = self._execute_recursive(toward)
            return var
        # if binary
        elif type(value) is data.Constant:
            toward.toward = value
            var = self._execute_recursive(toward)
            return var
        raise NotImplementedError

    # return new constant
    def _new_const(self, toward):
        raise NotImplementedError

    # update graph
    def push(self, value):
        # has query
        if value is not None:
            value.update_graph(self.graph)

    @classmethod
    def get_builtin_methods(cls):
        return [t for t in dir(cls.BUILTINS) if not t.startswith('_')], cls.BUILTINS
