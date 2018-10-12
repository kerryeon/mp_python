from mp.core.data import Builtins, Constant, Indexed, Method, Operator, Required, Tuple, Variable, View
from mp.core.error import RequiredError, SyntaxError
from mp.core.expression import Expression as Exp


class Graph:

    def __init__(self):
        super().__init__()
        # count 1 if self.alloc
        self.window = 0
        # variables
        self.vars = dict()
        # save/delete files sometime
        self.ios = dict()
        # do not make pointer
        self.lock_point = False

    # make new variable name
    def new_name(self):
        name = '%s%s' % (Exp.CODE_CONST, self.window)
        self.window += 1
        return name

    # allocate new constant
    def alloc(self, num_type, toward, name=None):
        if name is None:
            name = self.new_name()
        var = Constant(name, num_type, toward)
        self.vars[name] = var
        return var

    # allocate new variable by force
    def alloc_f(self, name, toward):
        var = Variable(name, toward)
        self.vars[name] = var
        return var

    # allocate new pointer variable
    def alloc_p(self, toward=None):
        name = self.new_name()
        return self.alloc_f(name, toward)

    # get or allocate variable
    def find(self, name):
        # name is not defined
        if name in Exp.REQUIRED:
            return Required()
        # this is a method
        if name in Exp.BUILTINS:
            return Builtins(name)

        # find in graph
        if name in self.vars.keys():
            return self.vars[name]
        # find in file sometime
        var = Variable(name)
        self.vars[name] = var
        return var

    # rename a variable
    def rename(self, name_from, name_to):
        old = self.vars[name_from]
        old.name = name_to
        self.vars[name_to] = old
        del self.vars[name_from]

    # point existing method
    def point_method(self, name, toward, repeat=None):
        self.rename(name, self.new_name())
        sub = Method(name, toward, repeat=repeat)
        sub.name = name
        self.vars[name] = sub
        return sub

    # save sometime
    def save(self, dir_from, *args, save=True):
        if dir_from is not None:
            if type(dir_from) is not Variable:
                raise SyntaxError(dir_from.symbol)
            dir_from = dir_from.symbol
        for file in args:
            if type(file) not in (Variable, Method):
                raise SyntaxError(file.symbol)
            # copy data
            if dir_from is not None:
                name = '%s%s%s' % (dir_from, Exp.DOT, file.name)
                self._inplace(self.find(name), file)
            else:
                name = file.name
            self.ios[name] = save

    # delete sometime
    def delete(self, dir_from, *args):
        for file in args:
            file.toward = None
        self.save(dir_from, *args, save=False)

    # for in-place operators
    def _inplace(self, sub, obj):
        # only variable, method, tuple in sub
        name = sub.name
        if not (sub.is_variable or sub.is_method or sub.is_operator):
            raise SyntaxError(name)
        # point method
        if obj.is_method_delegate:
            # no tuple-delegate
            if sub.is_tuple:
                raise SyntaxError(Exp.IS[0])
            # else
            self.point_method(name, obj)
            return self.vars[name]
        # var-tuple
        if not sub.is_tuple and obj.is_tuple:
            # only var-tuple
            if sub.is_variable:
                raise SyntaxError(Exp.IS[0])
        # tuple-var
        if sub.is_tuple and not obj.is_tuple:
            # only tuple-var(tuple)
            if obj.is_variable:
                if obj.toward.is_tuple:
                    obj = obj.toward
                else:
                    raise SyntaxError(Exp.IS[0])
            else:
                raise SyntaxError(Exp.IS[0])
        # tuple-tuple
        if sub.is_tuple and obj.is_tuple:
            # only same dims
            if len(sub.args) != len(obj.args):
                raise SyntaxError(Exp.IS[0])
            # in-place in order
            for arg_sub, arg_obj in zip(sub.args, obj.args):
                self._inplace(arg_sub, arg_obj)
            return sub
        # else (tuple-var, var-var)
        # rename if recursion
        if sub.is_variable:
            if obj.has_attr(name):
                self.rename(name, self.new_name())
                sub = self.alloc_f(name, obj)
                return sub
        # substitute
        sub.toward = obj
        return sub

    # for normal operators
    def operate(self, op, sub, obj=None, step=None):
        # =
        if op in Exp.IS:
            return self._inplace(sub, obj)
        # := (disposable substitute)
        if op in Exp.DIS:
            # don't use disposing while calculation
            if self.lock_point:
                return self._inplace(sub, obj)
            # else
            if sub.toward is None:
                name = sub.name
                if obj.has_attr(name):
                    raise RequiredError(sub.symbol)
                sub.toward = obj
                sub.is_pointer = True
                sub.is_pointer_orient = True
                return sub
            return sub
        # in-place operators
        if op in Exp.Tokens_Inplace:
            tmp = self.alloc_p(sub.toward)
            tmp = Operator(op, tmp, obj, step)
            return self._inplace(sub, tmp)
        # out-place operators
        tmp = self.alloc_p(sub)
        tmp = Operator(op, tmp, obj, step)
        return tmp

    # cleanup io requests
    def clean(self):
        self.ios = dict()

    # (:, :, ...)
    @classmethod
    def indices(cls, *args):
        return Indexed(*args)

    # {}
    @classmethod
    def view(cls, *args):
        return View(*args)

    # tuple
    @classmethod
    def tuple(cls, *args):
        return Tuple(*args)

    # :
    @classmethod
    def slice(cls, start, stop, step):
        op = Exp.IDX[0]
        return Operator(op, start, stop, step)
