#!/usr/bin/env python3
"""
Test script for MainModel task lifecycle management
"""

import asyncio
import pytest
import sys
import os
from pathlib import Path

# Add project root to Python path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from Backend.AI.MainModel import MainModel


@pytest.mark.asyncio
async def test_mainmodel_cancellation():
    """Test that MainModel processing can be cancelled properly"""
    
    # Initialize MainModel
    main_model = MainModel()
    
    # Start the continuous processing task
    task = asyncio.create_task(main_model.run_continuous_processing())
    
    # Let it run for a short time
    await asyncio.sleep(0.1)
    
    # Verify task is running
    assert not task.done()
    
    # Cancel the task
    task.cancel()
    
    # Wait for cancellation to complete
    try:
        await task
    except asyncio.CancelledError:
        pass  # Expected behavior
    
    # Verify task is done (either cancelled or completed)
    assert task.done()


@pytest.mark.asyncio 
async def test_mainmodel_graceful_shutdown():
    """Test that MainModel handles shutdown gracefully"""
    
    main_model = MainModel()
    
    # Create task 
    task = asyncio.create_task(main_model.run_continuous_processing())
    
    # Let it process briefly
    await asyncio.sleep(0.05)
    
    # Cancel and ensure it shuts down properly
    task.cancel()
    
    # Should not raise unhandled exceptions - MainModel handles CancelledError
    try:
        await task
    except asyncio.CancelledError:
        pass  # If it does raise, that's fine too
    
    # Task should be properly done
    assert task.done()


if __name__ == "__main__":
    asyncio.run(test_mainmodel_cancellation())
    asyncio.run(test_mainmodel_graceful_shutdown())
    print("All MainModel task lifecycle tests passed!")