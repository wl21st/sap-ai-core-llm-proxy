"""
Pydantic-based configuration models for SAP AI Core LLM Proxy.

This module provides an alternative configuration system using Pydantic v2
with automatic validation, serialization, and better type checking.
"""

import threading
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict


class ServiceKeyModel(BaseModel):
    """SAP AI Core service key credentials."""
    
    model_config = ConfigDict(extra='allow')
    
    client_id: str = Field(..., alias='clientid')
    client_secret: str = Field(..., alias='clientsecret')
    auth_url: str = Field(..., alias='url')
    identity_zone_id: str = Field(..., alias='identityzoneid')


class TokenInfoModel(BaseModel):
    """Token information with caching and thread-safety."""
    
    token: Optional[str] = None
    expiry: float = 0.0


class SubAccountConfigModel(BaseModel):
    """Configuration for a single SAP AI Core subaccount."""
    
    model_config = ConfigDict(extra='forbid')
    
    resource_group: str = Field(default='default')
    service_key_json: str
    deployment_models: Dict[str, List[str]] = Field(default_factory=dict)
    
    # Optional fields for runtime use (not in JSON)
    service_key: Optional[ServiceKeyModel] = None
    token_info: TokenInfoModel = Field(default_factory=TokenInfoModel)
    normalized_models: Dict[str, List[str]] = Field(default_factory=dict)
    
    def normalize_model_names(self) -> None:
        """Normalize model names by removing prefixes like 'anthropic--'.
        
        Currently disabled - keeps original model names.
        """
        # Currently disabled - uncomment to enable normalization
        if False:
            self.normalized_models = {
                key.replace("anthropic--", ""): value
                for key, value in self.deployment_models.items()
            }
        else:
            self.normalized_models = {
                key: value
                for key, value in self.deployment_models.items()
            }


class ProxyConfigModel(BaseModel):
    """Main proxy configuration with multi-subaccount support."""
    
    model_config = ConfigDict(extra='forbid')
    
    subAccounts: Dict[str, SubAccountConfigModel] = Field(
        default_factory=dict,
        description="Mapping of subaccount names to their configurations"
    )
    secret_authentication_tokens: List[str] = Field(
        default_factory=list,
        description="List of valid authentication tokens for the proxy"
    )
    port: int = Field(default=3001, ge=1, le=65535)
    host: str = Field(default='127.0.0.1')
    
    # Global model to subaccount mapping (computed at runtime)
    model_to_subaccounts: Dict[str, List[str]] = Field(
        default_factory=dict,
        exclude=True
    )
    
    def initialize(self) -> None:
        """Initialize all subaccounts and build model mappings.
        
        This method should be called after loading the configuration
        to perform any necessary post-load processing.
        """
        for subaccount in self.subAccounts.values():
            subaccount.normalize_model_names()
        
        # Build model to subaccounts mapping for load balancing
        self.build_model_mapping()
    
    def build_model_mapping(self) -> None:
        """Build a mapping of models to the subaccounts that have them."""
        self.model_to_subaccounts = {}
        for subaccount_name, subaccount in self.subAccounts.items():
            for model in subaccount.normalized_models.keys():
                if model not in self.model_to_subaccounts:
                    self.model_to_subaccounts[model] = []
                self.model_to_subaccounts[model].append(subaccount_name)
    
    def load_service_key(self, subaccount_name: str, key_data: Dict) -> None:
        """Load service key for a specific subaccount.
        
        Args:
            subaccount_name: The name of the subaccount
            key_data: Dictionary containing the service key data
        """
        if subaccount_name in self.subAccounts:
            try:
                self.subAccounts[subaccount_name].service_key = ServiceKeyModel(
                    **key_data
                )
            except Exception as e:
                raise ValueError(
                    f"Failed to load service key for {subaccount_name}: {e}"
                )
