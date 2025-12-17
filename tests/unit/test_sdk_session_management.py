"""
Unit tests for SAP AI Core SDK session and client management.

This module tests the caching and thread-safety of SDK session and client
initialization in proxy_server.py.
"""

import pytest
import threading
from unittest.mock import Mock, patch, MagicMock
from gen_ai_hub.proxy.native.amazon.clients import Session


class TestGetSAPAICoreSDKSession:
    """Test cases for get_sapaicore_sdk_session() function."""
    
    def test_session_initialization_on_first_call(self):
        """Test that session is initialized on first call."""
        # Import here to avoid module-level side effects
        import proxy_server
        
        # Reset the global session
        proxy_server._sdk_session = None
        
        with patch('proxy_server.Session') as mock_session_class:
            mock_session_instance = Mock(spec=Session)
            mock_session_class.return_value = mock_session_instance
            
            # First call should initialize the session
            result = proxy_server.get_sapaicore_sdk_session()
            
            # Verify Session() was called once
            mock_session_class.assert_called_once()
            assert result == mock_session_instance
            assert proxy_server._sdk_session == mock_session_instance
    
    def test_session_reuse_on_subsequent_calls(self):
        """Test that session is reused on subsequent calls."""
        import proxy_server
        
        # Reset and set up a mock session
        mock_session = Mock(spec=Session)
        proxy_server._sdk_session = mock_session
        
        with patch('proxy_server.Session') as mock_session_class:
            # Call multiple times
            result1 = proxy_server.get_sapaicore_sdk_session()
            result2 = proxy_server.get_sapaicore_sdk_session()
            result3 = proxy_server.get_sapaicore_sdk_session()
            
            # Session() should not be called since session already exists
            mock_session_class.assert_not_called()
            
            # All calls should return the same instance
            assert result1 == mock_session
            assert result2 == mock_session
            assert result3 == mock_session
    
    def test_session_thread_safety_double_checked_locking(self):
        """Test thread-safe initialization using double-checked locking pattern."""
        import proxy_server
        
        # Reset the global session
        proxy_server._sdk_session = None
        
        mock_session = Mock(spec=Session)
        call_count = 0
        
        def mock_session_constructor():
            nonlocal call_count
            call_count += 1
            return mock_session
        
        with patch('proxy_server.Session', side_effect=mock_session_constructor):
            # Simulate concurrent access from multiple threads
            results = []
            threads = []
            
            def get_session():
                result = proxy_server.get_sapaicore_sdk_session()
                results.append(result)
            
            # Create 10 threads that all try to get the session simultaneously
            for _ in range(10):
                thread = threading.Thread(target=get_session)
                threads.append(thread)
            
            # Start all threads
            for thread in threads:
                thread.start()
            
            # Wait for all threads to complete
            for thread in threads:
                thread.join()
            
            # Session should only be initialized once despite concurrent access
            assert call_count == 1
            
            # All threads should get the same session instance
            assert len(results) == 10
            assert all(r == mock_session for r in results)
    
    def test_session_initialization_logs_message(self):
        """Test that session initialization logs an info message."""
        import proxy_server
        
        proxy_server._sdk_session = None
        
        with patch('proxy_server.Session') as mock_session_class, \
             patch('proxy_server.logging.info') as mock_log_info:
            
            mock_session_class.return_value = Mock(spec=Session)
            
            proxy_server.get_sapaicore_sdk_session()
            
            # Verify logging was called with expected message
            mock_log_info.assert_called_with("Initializing global SAP AI SDK Session")


class TestGetSAPAICoreSDKClient:
    """Test cases for get_sapaicore_sdk_client() function."""
    
    def test_client_creation_on_first_call_for_model(self):
        """Test that client is created on first call for a specific model."""
        import proxy_server
        
        # Reset the clients cache
        proxy_server._bedrock_clients = {}
        
        mock_session = Mock(spec=Session)
        mock_client = Mock()
        mock_session.client.return_value = mock_client
        
        with patch('proxy_server.get_sapaicore_sdk_session', return_value=mock_session):
            result = proxy_server.get_sapaicore_sdk_client("claude-3-opus")

            # Verify client was created with config parameter
            mock_session.client.assert_called_once_with(
                model_name="claude-3-opus",
                config={
                    "retries": {
                        "max_attempts": 1,
                        "mode": "standard",
                    }
                }
            )
            assert result == mock_client
            assert proxy_server._bedrock_clients["claude-3-opus"] == mock_client
    
    def test_client_reuse_for_same_model(self):
        """Test that client is reused for subsequent calls with same model."""
        import proxy_server
        
        # Set up cached client
        mock_client = Mock()
        proxy_server._bedrock_clients = {"claude-3-opus": mock_client}
        
        mock_session = Mock(spec=Session)
        
        with patch('proxy_server.get_sapaicore_sdk_session', return_value=mock_session):
            result1 = proxy_server.get_sapaicore_sdk_client("claude-3-opus")
            result2 = proxy_server.get_sapaicore_sdk_client("claude-3-opus")
            
            # Session.client() should not be called since client is cached
            mock_session.client.assert_not_called()
            
            # Both calls should return the cached client
            assert result1 == mock_client
            assert result2 == mock_client
    
    def test_different_clients_for_different_models(self):
        """Test that different clients are created for different models."""
        import proxy_server
        
        proxy_server._bedrock_clients = {}
        
        mock_session = Mock(spec=Session)
        mock_client_opus = Mock()
        mock_client_sonnet = Mock()
        
        def mock_client_factory(model_name, config):
            if model_name == "claude-3-opus":
                return mock_client_opus
            elif model_name == "claude-3-sonnet":
                return mock_client_sonnet
            return Mock()
        
        mock_session.client.side_effect = mock_client_factory
        
        with patch('proxy_server.get_sapaicore_sdk_session', return_value=mock_session):
            result_opus = proxy_server.get_sapaicore_sdk_client("claude-3-opus")
            result_sonnet = proxy_server.get_sapaicore_sdk_client("claude-3-sonnet")
             
            # Verify different clients were created
            assert result_opus == mock_client_opus
            assert result_sonnet == mock_client_sonnet
            assert result_opus != result_sonnet
            
            # Verify both are cached
            assert proxy_server._bedrock_clients["claude-3-opus"] == mock_client_opus
            assert proxy_server._bedrock_clients["claude-3-sonnet"] == mock_client_sonnet
    
    def test_client_thread_safety_double_checked_locking(self):
        """Test thread-safe client creation using double-checked locking."""
        import proxy_server
        
        proxy_server._bedrock_clients = {}
        
        mock_session = Mock(spec=Session)
        mock_client = Mock()
        client_creation_count = 0
        
        def mock_client_factory(model_name, config):
            nonlocal client_creation_count
            client_creation_count += 1
            return mock_client
        
        mock_session.client.side_effect = mock_client_factory
        
        with patch('proxy_server.get_sapaicore_sdk_session', return_value=mock_session):
            results = []
            threads = []
            
            def get_client():
                result = proxy_server.get_sapaicore_sdk_client("claude-3-opus")
                results.append(result)
            
            # Create 10 threads that all try to get the same client simultaneously
            for _ in range(10):
                thread = threading.Thread(target=get_client)
                threads.append(thread)
            
            # Start all threads
            for thread in threads:
                thread.start()
            
            # Wait for all threads to complete
            for thread in threads:
                thread.join()
            
            # Client should only be created once despite concurrent access
            assert client_creation_count == 1
            
            # All threads should get the same client instance
            assert len(results) == 10
            assert all(r == mock_client for r in results)
    
    def test_client_creation_logs_message(self):
        """Test that client creation logs an info message."""
        import proxy_server
        
        proxy_server._bedrock_clients = {}
        
        mock_session = Mock(spec=Session)
        mock_client = Mock()
        mock_session.client.return_value = mock_client
        
        with patch('proxy_server.get_sapaicore_sdk_session', return_value=mock_session), \
             patch('proxy_server.logging.info') as mock_log_info:
            
            proxy_server.get_sapaicore_sdk_client("claude-3-opus")
            
            # Verify logging was called with expected message
            mock_log_info.assert_called_with(
                "Creating SAP AI SDK client for model 'claude-3-opus'"
            )
    
    def test_client_cache_returns_none_check(self):
        """Test that None check works correctly for cache lookup."""
        import proxy_server
        
        # Set up cache with None value (edge case)
        proxy_server._bedrock_clients = {"test-model": None}
        
        mock_session = Mock(spec=Session)
        mock_client = Mock()
        mock_session.client.return_value = mock_client
        
        with patch('proxy_server.get_sapaicore_sdk_session', return_value=mock_session):
            # Should create new client since cached value is None
            result = proxy_server.get_sapaicore_sdk_client("test-model")
            
            # Verify new client was created with config parameter
            mock_session.client.assert_called_once_with(
                model_name="test-model",
                config={
                    "retries": {
                        "max_attempts": 1,
                        "mode": "standard",
                    }
                }
            )
            assert result == mock_client


class TestSDKSessionAndClientIntegration:
    """Integration tests for session and client management together."""
    
    def test_client_uses_session_correctly(self):
        """Test that client creation uses the global session."""
        import proxy_server
        
        proxy_server._sdk_session = None
        proxy_server._bedrock_clients = {}
        
        mock_session = Mock(spec=Session)
        mock_client = Mock()
        mock_session.client.return_value = mock_client
        
        with patch('proxy_server.Session', return_value=mock_session):
            # Get client should initialize session and create client
            result = proxy_server.get_sapaicore_sdk_client("claude-3-opus")
            
            # Verify session was initialized
            assert proxy_server._sdk_session == mock_session
            
            # Verify client was created using that session with config parameter
            mock_session.client.assert_called_once_with(
                model_name="claude-3-opus",
                config={
                    "retries": {
                        "max_attempts": 1,
                        "mode": "standard",
                    }
                }
            )
            assert result == mock_client
    
    def test_multiple_clients_share_same_session(self):
        """Test that multiple clients share the same session instance."""
        import proxy_server
        
        proxy_server._sdk_session = None
        proxy_server._bedrock_clients = {}
        
        mock_session = Mock(spec=Session)
        mock_client1 = Mock()
        mock_client2 = Mock()
        
        def mock_client_factory(model_name, config):
            if model_name == "model1":
                return mock_client1
            return mock_client2
        
        mock_session.client.side_effect = mock_client_factory
        
        with patch('proxy_server.Session', return_value=mock_session) as mock_session_class:
            # Create clients for different models
            client1 = proxy_server.get_sapaicore_sdk_client("model1")
            client2 = proxy_server.get_sapaicore_sdk_client("model2")
            
            # Session should only be initialized once
            mock_session_class.assert_called_once()
            
            # Both clients should use the same session
            assert mock_session.client.call_count == 2
            assert client1 == mock_client1
            assert client2 == mock_client2
    
    def test_concurrent_session_and_client_initialization(self):
        """Test concurrent initialization of session and multiple clients."""
        import proxy_server
        
        proxy_server._sdk_session = None
        proxy_server._bedrock_clients = {}
        
        mock_session = Mock(spec=Session)
        session_init_count = 0
        
        def mock_session_constructor():
            nonlocal session_init_count
            session_init_count += 1
            return mock_session
        
        client_creation_counts = {}
        
        def mock_client_factory(model_name, config):
            if model_name not in client_creation_counts:
                client_creation_counts[model_name] = 0
            client_creation_counts[model_name] += 1
            return Mock()
        
        mock_session.client.side_effect = mock_client_factory
        
        with patch('proxy_server.Session', side_effect=mock_session_constructor):
            results = []
            threads = []
            
            # Create threads that request different models
            models = ["model1", "model2", "model3"] * 5  # 15 threads total
            
            def get_client(model_name):
                result = proxy_server.get_sapaicore_sdk_client(model_name)
                results.append((model_name, result))
            
            for model in models:
                thread = threading.Thread(target=get_client, args=(model,))
                threads.append(thread)
            
            # Start all threads
            for thread in threads:
                thread.start()
            
            # Wait for all threads to complete
            for thread in threads:
                thread.join()
            
            # Session should only be initialized once
            assert session_init_count == 1
            
            # Each model should have its client created only once
            assert client_creation_counts["model1"] == 1
            assert client_creation_counts["model2"] == 1
            assert client_creation_counts["model3"] == 1
            
            # All threads should have received results
            assert len(results) == 15


class TestSDKCachePerformance:
    """Test cases for SDK caching performance characteristics."""
    
    def test_session_cache_avoids_expensive_initialization(self):
        """Test that caching avoids expensive session initialization."""
        import proxy_server
        
        proxy_server._sdk_session = None
        
        expensive_init_count = 0
        
        def expensive_session_init():
            nonlocal expensive_init_count
            expensive_init_count += 1
            # Simulate expensive initialization
            return Mock(spec=Session)
        
        with patch('proxy_server.Session', side_effect=expensive_session_init):
            # Call 100 times
            for _ in range(100):
                proxy_server.get_sapaicore_sdk_session()
            
            # Expensive initialization should only happen once
            assert expensive_init_count == 1
    
    def test_client_cache_avoids_expensive_client_creation(self):
        """Test that caching avoids expensive client creation."""
        import proxy_server
        
        proxy_server._bedrock_clients = {}
        
        mock_session = Mock(spec=Session)
        client_creation_count = 0
        
        def expensive_client_creation(model_name, config):
            nonlocal client_creation_count
            client_creation_count += 1
            # Simulate expensive client creation
            return Mock()
        
        mock_session.client.side_effect = expensive_client_creation
        
        with patch('proxy_server.get_sapaicore_sdk_session', return_value=mock_session):
            # Call 100 times for the same model
            for _ in range(100):
                proxy_server.get_sapaicore_sdk_client("claude-3-opus")
            
            # Expensive client creation should only happen once per model
            assert client_creation_count == 1
