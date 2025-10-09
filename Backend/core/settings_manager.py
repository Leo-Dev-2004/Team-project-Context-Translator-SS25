# Backend/core/settings_manager.py

import json
import logging
import aiofiles
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class SettingsManager:
    """
    Centralized settings manager for the backend application.
    Serves as the single source of truth for all application settings.
    Supports both in-memory settings and optional file persistence.
    """
    
    def __init__(self, settings_file: Optional[str] = None):
        self._settings: Dict[str, Any] = {}
        self._settings_file = Path(settings_file) if settings_file else Path("Backend/settings.json")
        
        # Default settings
        self._default_settings = {
            "domain": "",
            "explanation_style": "detailed",
            "ai_model": "llama3.2",
            "confidence_threshold": 1,
            "cooldown_seconds": 300
        }
        
        # Initialize with defaults
        self._settings.update(self._default_settings)
        
        logger.info(f"SettingsManager initialized with settings file: {self._settings_file}")
    
    def update_settings(self, new_settings: Dict[str, Any]) -> None:
        """
        Updates the current settings with new values.
        
        Args:
            new_settings: Dictionary containing the new settings to update
        """
        if not isinstance(new_settings, dict):
            logger.warning(f"SettingsManager: ⚠️ Invalid settings type {type(new_settings)}, expected dict")
            return
            
        logger.info(f"SettingsManager: 🔧 Updating settings with keys: {list(new_settings.keys())}")
        
        # Update settings with new values
        old_values = {}
        for key, value in new_settings.items():
            if key in self._settings:
                old_values[key] = self._settings[key]
            self._settings[key] = value
            logger.debug(f"SettingsManager:   - {key}: {old_values.get(key, '<not set>')} → {value}")
            
        logger.info(f"SettingsManager: ✅ Successfully updated {len(new_settings)} setting(s)")
        logger.debug(f"SettingsManager: Settings changes: {old_values} -> {new_settings}")
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """
        Retrieves a specific setting value.
        
        Args:
            key: The setting key to retrieve
            default: Default value to return if key doesn't exist
            
        Returns:
            The setting value or default if key doesn't exist
        """
        value = self._settings.get(key, default)
        logger.debug(f"SettingsManager: Retrieved setting '{key}' = {value}")
        return value
    
    def get_all_settings(self) -> Dict[str, Any]:
        """
        Returns a copy of all current settings.
        
        Returns:
            Dictionary containing all current settings
        """
        return self._settings.copy()
    
    def reset_to_defaults(self) -> None:
        """
        Resets all settings to their default values.
        """
        logger.info("SettingsManager: Resetting all settings to defaults")
        self._settings.clear()
        self._settings.update(self._default_settings)
    
    async def load_from_file(self) -> bool:
        """
        Loads settings from the configured settings file.
        
        Returns:
            True if settings were loaded successfully, False otherwise
        """
        try:
            if not self._settings_file.exists():
                logger.info(f"SettingsManager: Settings file {self._settings_file} does not exist, using defaults")
                return False
                
            async with aiofiles.open(self._settings_file, 'r') as f:
                content = await f.read()
                file_settings = json.loads(content)
                
            if isinstance(file_settings, dict):
                # Merge with defaults, keeping file values where they exist
                merged_settings = self._default_settings.copy()
                merged_settings.update(file_settings)
                self._settings = merged_settings
                
                logger.info(f"SettingsManager: Loaded settings from {self._settings_file}")
                logger.debug(f"SettingsManager: Loaded settings: {self._settings}")
                return True
            else:
                logger.warning(f"SettingsManager: Invalid settings file format, expected dict")
                return False
                
        except json.JSONDecodeError as e:
            logger.error(f"SettingsManager: Failed to parse settings file: {e}")
            return False
        except Exception as e:
            logger.error(f"SettingsManager: Error loading settings from file: {e}")
            return False
    
    async def save_to_file(self) -> bool:
        """
        Saves current settings to the configured settings file.
        
        Returns:
            True if settings were saved successfully, False otherwise
        """
        logger.info(f"SettingsManager: 💾 Starting to save settings to file: {self._settings_file}")
        try:
            # Ensure directory exists
            self._settings_file.parent.mkdir(parents=True, exist_ok=True)
            logger.debug(f"SettingsManager: Directory verified/created: {self._settings_file.parent}")
            
            # Prepare settings for serialization
            settings_to_save = self._settings.copy()
            settings_to_save["last_updated"] = str(self._get_current_timestamp())
            logger.debug(f"SettingsManager: Prepared settings for saving: {list(settings_to_save.keys())}")
            
            async with aiofiles.open(self._settings_file, 'w') as f:
                await f.write(json.dumps(settings_to_save, indent=2))
                
            logger.info(f"SettingsManager: ✅ Successfully saved settings to {self._settings_file}")
            logger.debug(f"SettingsManager: Saved settings content: {settings_to_save}")
            return True
            
        except Exception as e:
            logger.error(f"SettingsManager: ❌ Error saving settings to file: {e}")
            return False
    
    def _get_current_timestamp(self) -> str:
        """Helper method to get current timestamp as ISO string"""
        from datetime import datetime
        return datetime.now().isoformat()
    
    def __repr__(self) -> str:
        return f"SettingsManager(file={self._settings_file}, settings_count={len(self._settings)})"