from mp.core.expression import Expression as Exp


def _range_to_tuple(self):
    if self is None:
        return None
    result = self.range_to_tuple()
    return result


class Variable:

    def __init__(self, name: str = None, toward=None):
        self.name = name
        self.toward = toward

        self.num_type = None
        self.value = None
        self.op = None
        self.sub = None
        self.obj = None
        self.step = None
        self.args = None

        self.is_pointer = False
        self.is_pointer_orient = False
        self.is_constant = False
        self.is_operator = False
        self.is_indices = False
        self.is_view = False
        self.is_method = False
        self.is_method_delegate = False

        self.is_builtins = False
        # callable or constant
        self.is_data = True

    def has_attr(self, name: str):
        if self.name == name:
            return True
        if self.toward is not None:
            return self.toward.has_attr(name)
        return False

    def range_to_tuple(self):
        self.toward = _range_to_tuple(self.toward)
        return self

    def copy(self, recursive: bool = False):
        new_var = self.__class__()
        for key, value in self.__dict__.items():
            if recursive and value is not None:
                value = value.copy()
            setattr(new_var, key, value)
        return new_var

    @property
    def is_none(self):
        return (self.name is not None) and (self.toward is None)

    @property
    def is_variable(self):
        return (not self.is_constant) and (not self.is_operator) and (not self.is_method)

    @property
    def is_required(self):
        return self.is_variable and self.toward is None

    @property
    def symbol(self):
        return self.name

    def encode(self, stack_called=None):
        stack_called = self._ensure_stack_not_none(stack_called)
        toward = self._encode(self.toward, stack_called)
        if self._name_is_constant():
            return toward
        name = self.name
        # if already defined
        if name in stack_called:
            return '%s' % name
        stack_called.append(name)
        # = :=
        op = Exp.OIS[0] if self.is_pointer_orient else Exp.IS[0]
        # if pointing method
        if self.is_method:
            toward = self.toward.sub
        return '(%s%s%s)' % (name, op, toward)

    @staticmethod
    def _encode(self, stack_called):
        if self is None:
            return None
        return self.encode(stack_called)

    @staticmethod
    def _ensure_stack_not_none(stack_called):
        if stack_called is None:
            stack_called = list()
        return stack_called

    def _name_is_constant(self):
        if self.name is None:
            return True
        return self.name.startswith('/')

    def __repr__(self):
        if self.is_required:
            return Exp.REQUIRED
        if self.name is None:
            return ''
        op = ':=' if self.is_pointer_orient else '='
        return 'v[ %s %s %s ]' % (self.name, op, self.toward)


class Constant(Variable):

    def __init__(self, name: str = None, num_type=None, value=None):
        super().__init__(name, self)
        self.is_constant = True
        self.num_type = num_type
        self.value = value

    def has_attr(self, name: str):
        return False

    def range_to_tuple(self):
        return self

    @property
    def symbol(self):
        return self.value

    def encode(self, stack_called=None):
        return '%s%s' % (str(self.value), self.num_type)

    def __repr__(self):
        return 'c{ %s }' % str(self.value)


def Required():
    return Variable()


class Operator(Variable):

    def __init__(self, op=None, sub: Variable = None, obj: Variable = None, step: Variable = None):
        super().__init__()
        self.is_operator = True
        self.op = op
        self.sub = sub
        self.obj = obj
        self.step = step
        self.args = []

    def has_attr(self, name: str):
        args = [self.sub, self.obj, self.step, *self.args]
        for arg in args:
            if arg is not None:
                if arg.has_attr(name):
                    return True
        return False

    def range_to_tuple(self):
        self.sub = _range_to_tuple(self.sub)
        self.obj = _range_to_tuple(self.obj)
        self.step = _range_to_tuple(self.step)
        self.args = [_range_to_tuple(arg) for arg in self.args]
        # ()
        if self.op in Exp.SHELL_RR:
            if self.sub.is_variable:
                if self.sub.toward.is_method:
                    args = [self.obj, self.step, *self.args]
                    args = [arg for arg in args if arg is not None]
                    self.sub.toward.args += args
                    return self.sub.toward
                else:
                    indices = Indexed(self.obj, self.step, *self.args)
                    indices.sub = self.sub.toward
                    return indices
        return self

    @property
    def symbol(self):
        return self.op

    def encode(self, stack_called=None):
        stack_called = self._ensure_stack_not_none(stack_called)
        # inplace to outplace
        op = self.op
        if op in Exp.Tokens_In2Out.keys():
            op = Exp.Tokens_In2Out[op]
        if op in Exp.Tokens_Shell:
            args = [self.sub, self.obj, self.step]
            args = [self._encode(arg, stack_called) for arg in args if arg is not None]
            shell_open = op[0]
            shell_close = op[-1]
            return '%s%s%s' % (shell_open, ','.join(args), shell_close)
        elif op in Exp.IDX:
            sub = self._encode(self.sub, stack_called)
            obj = self._encode(self.obj, stack_called)
            step = self._encode(self.step, stack_called)
            obj = '%s%s' % (op, obj) if obj is not None else '%s' % op
            step = '%s%s' % (op, step) if step is not None else ''
            return '%s%s%s' % (sub, obj, step)
        return '(%s%s%s)' % (self._encode(self.sub, stack_called), op, self._encode(self.obj, stack_called))

    def __repr__(self):
        return '%s{ %s, %s, %s }' % (self.op, self.sub, self.obj, self.step)


class Indexed(Operator):

    def __init__(self, *indices):
        super().__init__(Exp.IDX, Required())
        self.is_indices = True
        self.args = indices

    def range_to_tuple(self):
        self.args = [_range_to_tuple(arg) for arg in self.args]
        return self

    @property
    def symbol(self):
        return Exp.SHELL_RR[0]

    def encode(self, stack_called=None):
        stack_called = self._ensure_stack_not_none(stack_called)
        args = [self._encode(arg, stack_called) for arg in self.args]
        return '%s(%s)' % (self._encode(self.sub, stack_called), ','.join(args))

    def __repr__(self):
        return '%s( %s )' % (self.sub, ', '.join([repr(arg) for arg in self.args]))


class View(Operator):

    def __init__(self, *dims):
        super().__init__(Exp.IDX, Required())
        self.is_view = True
        self.args = dims

    def range_to_tuple(self):
        self.args = [_range_to_tuple(arg) for arg in self.args]
        return self

    @property
    def symbol(self):
        return self.op

    def encode(self, stack_called=None):
        stack_called = self._ensure_stack_not_none(stack_called)
        args = [self._encode(arg, stack_called) for arg in self.args]
        return '%s{%s}' % (self._encode(self.sub, stack_called), ','.join(args))

    def __repr__(self):
        return '%s{ %s }' % (self.sub, ', '.join([repr(arg) for arg in self.args]))


class Method(Variable):

    def __init__(self, sub=None, *args):
        super().__init__()
        self.is_method = True
        self.sub = sub
        self.args = args

    def has_attr(self, name: str):
        #args = [self.sub, *self.args]
        for arg in self.args:
            if arg is not None:
                if arg.has_attr(name):
                    return True
        return False

    def range_to_tuple(self):
        self.args = [_range_to_tuple(arg) for arg in self.args]
        return self

    def encode(self, stack_called=None):
        stack_called = self._ensure_stack_not_none(stack_called)
        sub = self.sub
        # if pointing method
        if self.is_method_delegate:
            # if already defined
            if sub in stack_called:
                return '%s' % sub
            # else
            stack_called.append(sub)
            if len(self.args) >= 1:
                toward = self.args[0]
                return '(%s=%s)' % (sub, toward.encode(stack_called))
            return '%s' % sub
        stack_called = self._ensure_stack_not_none(stack_called)
        args = [self._encode(arg, stack_called) for arg in self.args]
        return '%s(%s)' % (sub, ','.join(args))

    def __repr__(self):
        return '%s( %s )' % (self.sub, ', '.join([repr(arg) for arg in self.args]))


def Builtins(method: str):
    func = Method(method)
    func.is_builtins = True
    return func
