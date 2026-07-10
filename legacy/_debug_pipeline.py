"""Debug pipeline startup"""
import sys, traceback

try:
    print("Importing...")
    sys.path.insert(0, r"d:\AIToutiao")
    os = __import__("os")
    
    from pathlib import Path
    import json
    
    # Manual test
    state_file = Path(r"d:\AIToutiao\outputs\20260704\20260704_test_113921\pipeline_state.json")
    data = json.loads(state_file.read_text(encoding="utf-8"))
    print(f"Loaded state: {data}")
    
    from pipeline import PipelineState, PipelineMode, PipelineStage, run_pipeline
    
    state = PipelineState.load("20260704_test_113921")
    print(f"State loaded: run_id={state.run_id}, mode={state.mode}")
    print(f"Completed: {state.completed_stages}")
    
    # Determine stages
    stages = PipelineStage.stages_for_mode(state.mode)
    print(f"Stages: {stages}")
    
    for stage in stages:
        print(f"  {stage.value}: done={state.is_stage_done(stage)}")
    
    print("OK - pipeline structure is valid")
    
except Exception as e:
    print(f"ERROR: {e}")
    traceback.print_exc()
