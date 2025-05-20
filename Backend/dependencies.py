from typing import Optional
from ..core.simulator import SimulationManager
from ..backend import sim_manager_instance as global_sim_manager_instance

def get_simulation_manager() -> SimulationManager:
    if global_sim_manager_instance is None:
        raise RuntimeError("SimulationManager not initialized. Server startup likely failed or is incomplete.")
    return global_sim_manager_instance
