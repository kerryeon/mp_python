from tqdm import tqdm

from mp.core.expression import Expression as Exp


class Monitor:
    def __init__(self):
        Exp.EVENT.add('init monitor', self._init, unique=True)
        Exp.EVENT.add('begin training', self._begin, unique=True)
        Exp.EVENT.add('next step', self._next_step, unique=True)

        self._args = None
        self._name = None
        self._tqdm = None
        self._length = None

    def _get_num_epochs(self):
        if len(self._args.list) >= 2:
            return int(self._args.list[1].get_value())
        return 1

    def _update_batch_length(self):
        if self._length is None:
            self._length = self._get_batch_length()
            self._tqdm.total = self._length

    def _begin_epoch(self):
        self._tqdm = tqdm(desc=self._name, total=self._get_batch_length())
        self._tqdm.update()

    def _end_epoch(self, loss):
        self._tqdm.close()
        print('Loss:', loss)

    @classmethod
    def _get_batch_length(cls):
        minimum = None
        for length in Exp.EVENT('get batch length'):
            minimum = min(minimum, length) if minimum is not None else length
        return minimum

    # ------------ For Events -------------------------------

    def _init(self, args):
        self._args = args
        self._name = self._args.list[0].symbol

    def _begin(self):
        loss = None
        for _ in range(self._get_num_epochs()):
            self._begin_epoch()
            self._args.list[0].remove_cache()
            loss = self._args.list[0].get_value()
            self._end_epoch(loss)
        return loss

    def _next_step(self, trainer, loss):
        self._update_batch_length()
        self._tqdm.update()
