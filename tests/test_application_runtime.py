import threading
import unittest
from application_runtime import ApplicationRuntime, OverlayWindowState
from ui_dispatcher import ApplicationDispatcher

class ApplicationRuntimeTests(unittest.TestCase):
    def test_cross_thread_work_is_serial_and_cancelled_work_never_runs(self):
        loop = ApplicationRuntime()
        observed = []
        token = loop.call_later(0, lambda: observed.append('cancelled'))
        loop.cancel(token)
        def worker():
            loop.call_later(0, lambda: observed.append(threading.get_ident()))
            loop.call_later(0, loop.close)
        thread = threading.Thread(target=worker)
        thread.start(); thread.join()
        loop.run()
        self.assertEqual(observed, [threading.get_ident()])
        self.assertIsNone(loop.call_later(0, lambda: None))

    def test_window_disposal_cancels_timers_and_notifies_renderer(self):
        loop=ApplicationRuntime()
        window=OverlayWindowState(loop)
        observed=[]
        window.call_later(0,lambda:observed.append('expired'))
        window.on_destroy(lambda event:observed.append(event.widget))
        window.destroy();window.destroy()
        loop.call_later(0,loop.close);loop.run()
        self.assertEqual(observed,[window])

    def test_dispatcher_preserves_events_and_coalesces_snapshots(self):
        loop=ApplicationRuntime();dispatcher=ApplicationDispatcher(loop);observed=[]
        dispatcher.post(observed.append,'old',key='status')
        dispatcher.post(observed.append,'jump')
        dispatcher.post(observed.append,'new',key='status')
        loop.call_later(40,loop.close);loop.run()
        self.assertEqual(observed,['new','jump'])
        self.assertEqual(dispatcher.stats()['failures'],0)
