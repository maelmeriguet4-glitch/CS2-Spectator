from src.core.batch_processor import BatchProcessor


class MockEngine:
    def analyze_demo(self, demo_path, progress_queue):
        if "corrupt" in demo_path:
            raise ValueError("Corrupted file")
        return f"Result for {demo_path}"

def test_batch_processor():
    engine = MockEngine()
    processor = BatchProcessor(engine)
    
    # Run with one valid and one corrupted file
    processor.start_batch(["valid1.dem", "corrupt.dem", "valid2.dem"])
    
    # Wait for the manager thread to finish
    if processor._manager_thread:
        processor._manager_thread.join(timeout=5.0)
        
    messages = []
    while not processor.msg_queue.empty():
        messages.append(processor.msg_queue.get_nowait())
        
    # Analyze messages
    completions = [m for m in messages if m[0] == "BATCH_COMPLETE"]
    errors = [m for m in messages if m[0] == "BATCH_ERROR"]
    all_done = [m for m in messages if m[0] == "BATCH_ALL_DONE"]
    
    assert len(completions) == 2
    assert completions[0][1] == "valid1.dem"
    assert completions[1][1] == "valid2.dem"
    
    assert len(errors) == 1
    assert errors[0][1] == "corrupt.dem"
    assert "Corrupted file" in errors[0][2]
    
    assert len(all_done) == 1

if __name__ == "__main__":
    test_batch_processor()
    print("Tests pass!")
