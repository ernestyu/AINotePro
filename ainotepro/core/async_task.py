from aqt.qt import QThread, pyqtSignal
from typing import Any, Callable, Tuple, Dict, Optional


class AsyncTask(QThread):
    finished_ok = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, target: Callable[..., Any], args: Tuple[Any, ...] = (), kwargs: Optional[Dict[str, Any]] = None):
        super().__init__()
        self._target = target
        self._args = args
        self._kwargs = kwargs or {}

    def run(self) -> None:
        try:
            result = self._target(*self._args, **self._kwargs)
            self.finished_ok.emit(result)
        except Exception as e:
            self.failed.emit(str(e))
