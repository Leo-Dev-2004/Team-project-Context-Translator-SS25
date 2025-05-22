# Backend/dependencies.py
from typing import Optional
from Backend.core.simulator import SimulationManager # Absolute import for SimulationManager

# This global variable will hold the SimulationManager instance
_global_sim_manager_instance: Optional[SimulationManager] = None

def set_simulation_manager_instance(manager: SimulationManager):
    """
    Sets the global SimulationManager instance.
    This function will be called by backend.py during startup.
    """
    global _global_sim_manager_instance
    _global_sim_manager_instance = manager

def get_simulation_manager() -> SimulationManager:
    """
    FastAPI dependency function to retrieve the initialized SimulationManager.
    Raises an error if the manager has not been initialized.
    """
    if _global_sim_manager_instance is None:
        raise RuntimeError("SimulationManager not initialized. Server startup likely failed or is incomplete.")
    return _global_sim_manager_instance
