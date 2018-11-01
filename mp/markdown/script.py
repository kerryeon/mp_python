from mp.core.expression import Expression as Exp
from mp.utils import assert_filename


class ScriptWriter:
    """
        The following code relies on the 'markdown' script.
    """

    def __init__(self, filename: str = None):
        self.filename = assert_filename(filename, 'mp')
        self.buffer = ''
        self.flush()

        self.vars = list()

    def _draw_var(self, var):
        if var.symbol in self.vars:
            return

        if var.is_variable:
            if var.toward is not None:
                if not var.toward.is_placeholder:
                    self(self._encode(var))
        if var.is_method_delegate:
            self(self._encode(var))

    def _encode(self, var):
        if (var.is_variable or var.is_method_delegate) and not var.is_method_defined:
            if var.symbol in self.vars:
                return var.symbol
            self.vars.append(var.symbol)

        if var.is_variable:
            if var.toward is None:
                return var.name
            if var.toward.is_placeholder:
                return var.name
            op = ':=' if var.is_pointer_orient else '='
            return '%s %s %s' % (var.name, op, self._encode(var.toward))
        if var.is_constant:
            return '%s' % var.encode()
        if var.is_operator:
            if var.op in Exp.IDX:
                return self._index(var)
            if var.op in Exp.Tokens_Operator:
                sub = self._wrap(var.op, var.sub)
                obj = self._wrap(var.op, var.obj)
                op = var.op
                if op in Exp.Tokens_In2Out.keys():
                    op = Exp.Tokens_In2Out[op]
                return '%s %s %s' % (sub, op, obj)
        if var.is_indices or var.is_tuple:
            return self._shell(var, '(', ')')
        if var.is_view:
            return self._shell(var, '{', '}')
        if var.is_method_defined:
            sub = var.name
            args = [self._encode(arg) for arg in var.args]
            args += [self._encode(var.toward)]
            return '%s(%s)' % (sub, ', '.join(args))
        if var.is_method_delegate:
            sub = var.name
            toward = self._wrap('()', var.toward)
            if var.repeat is not None:
                toward = '%s * %s' % (toward, self._wrap('*', var.repeat))
            return '%s = %s' % (sub, toward)
        if var.is_method:
            sub = var.name
            if sub not in self.vars:
                if var.repeat is not None:
                    sub = '(%s * %s)' % (sub, self._wrap('*', var.repeat))
            args = [self._encode(arg) for arg in var.args]
            return '%s(%s)' % (sub, ', '.join(args))

    def _shell(self, var, c_open, c_close):
        sub = ''
        if var.sub is not None:
            sub = self._wrap(var.op, var.sub)
        args = [self._encode(arg) for arg in var.args]
        return '%s%s%s%s' % (sub, c_open, ', '.join(args), c_close)

    def _index(self, var):
        def _index_encode(target, default):
            if target is not None:
                default = '%s:' % self._wrap(var.op, target)
            return default

        sub = _index_encode(var.sub, ':')
        obj = _index_encode(var.obj, '')
        step = _index_encode(var.step, '')
        return '%s%s%s' % (sub, obj, step)

    def _wrap(self, var_op, target):
        code = self._encode(target)
        if target.is_operator:
            if Exp.Tokens_Order[var_op] > Exp.Tokens_Order[target.op]:
                return '(%s)' % code
        return code

    def _comment(self, msg):
        self('# %s' % msg)

    def __call__(self, msg: str = ''):
        self.buffer += '%s\n' % msg

    def save(self, flush=True):
        if self.filename is not None:
            with open(self.filename, 'w') as f:
                f.write(self.buffer)
        if flush:
            self.flush()

    def flush(self):
        self.buffer = ''
        self._comment('Auto-Generated from Mp-ScriptWriter')
        self._comment('-----------------------------------')
        self()

    @classmethod
    def draw(cls, graph, filename: str = None):
        writer = ScriptWriter(filename)
        for var in graph.vars.values():
            writer._draw_var(var)
        writer.save(flush=False)
        return writer.buffer


draw_script = ScriptWriter.draw


if __name__ == '__main__':
    from mp import PythonInterpreter
    a = PythonInterpreter()
    a('a = 3')
    a('b = 4')
    a('c = def(a, b, a + b) * ( 7+8)')
    a('d = c(a, b)')
    print(draw_script(a.plan.graph))