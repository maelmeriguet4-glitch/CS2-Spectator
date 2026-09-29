import multiprocessing
import queue
import threading
from typing import List

from src.core.logger import setup_logger

logger = setup_logger("batch_processor")

def _batch_worker(engine, demo_path, msg_queue):
    """Worker global function for batch processing a single file."""
    try:
        msg_queue.put(("BATCH_PROGRESS", demo_path, f"Analyse en cours: {demo_path}"))
        result = engine.analyze_demo(demo_path, progress_queue=msg_queue)
        msg_queue.put(("BATCH_COMPLETE", demo_path, result))
    except Exception as e:
        logger.error(f"Erreur worker process d'analyse {demo_path}: {e}", exc_info=True)
        msg_queue.put(("BATCH_ERROR", demo_path, str(e)))

class BatchProcessor:
    def __init__(self, engine):
        self.engine = engine
        self.msg_queue = multiprocessing.Queue()
        self.total_files = 0
        self.completed_files = 0
        self.results = []
        self.errors = []
        self.state = "IDLE"  # "IDLE", "RUNNING", "COMPLETE", "CANCELLED", "ERROR"
        self.generation_id = 0
        
        self._manager_thread = None
        self._stop_event = threading.Event()
        self._current_process = None

    def start_batch(self, demo_paths: List[str]):
        """Starts batch analysis. Uses a background thread to manage processes sequentially."""
        self.stop_all()
        self.generation_id += 1
        current_gen = self.generation_id
        self.total_files = len(demo_paths)
        self.completed_files = 0
        self.results = []
        self.errors = []
        self.state = "RUNNING"
        
        self._stop_event.clear()
        
        # Clear queue
        while not self.msg_queue.empty():
            try:
                self.msg_queue.get_nowait()
            except queue.Empty:
                break
                
        self._manager_thread = threading.Thread(
            target=self._run_batch_manager, 
            args=(demo_paths, current_gen), 
            daemon=True
        )
        self._manager_thread.start()
        
    def _run_batch_manager(self, demo_paths: List[str], gen_id: int):
        """Runs in a background thread, spawning one analysis process at a time."""
        was_cancelled = False
        for demo_path in demo_paths:
            if self._stop_event.is_set() or gen_id != self.generation_id:
                was_cancelled = True
                break
                
            self._current_process = multiprocessing.Process(
                target=_batch_worker,
                args=(self.engine, demo_path, self.msg_queue),
                daemon=True
            )
            self._current_process.start()
            
            # Wait for this process to finish before starting the next
            while self._current_process.is_alive():
                if self._stop_event.is_set() or gen_id != self.generation_id:
                    self._current_process.terminate()
                    was_cancelled = True
                    break
                self._current_process.join(timeout=0.5)

            if was_cancelled:
                break

        if was_cancelled or self._stop_event.is_set() or gen_id != self.generation_id:
            if gen_id == self.generation_id:
                self.state = "CANCELLED"
                self.msg_queue.put(("BATCH_CANCELLED", None, None))
        else:
            if gen_id == self.generation_id:
                self.state = "COMPLETE"
                self.msg_queue.put(("BATCH_ALL_DONE", None, None))

    def stop_all(self):
        """Stops the batch processing completely."""
        self._stop_event.set()
        if self._current_process and self._current_process.is_alive():
            self._current_process.terminate()
        if self.state == "RUNNING":
            self.state = "CANCELLED"
