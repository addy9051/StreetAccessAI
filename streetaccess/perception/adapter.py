"""Provider-neutral perception adapter interface.

This defines the contract for extracting frame-level observations.
No runtime model API or cloud dependency is imported here.
"""

from abc import ABC, abstractmethod
from streetaccess.perception.models import PerceptionBatchRequest, PerceptionOutput


class PerceptionAdapter(ABC):
    """Abstract perception adapter interface.
    
    Future implementations (e.g., local ONNX models, edge vision models, or hosted VLMs)
    must satisfy this interface without changing downstream verification or routing logic.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the perception adapter."""
        pass

    @property
    @abstractmethod
    def is_mock(self) -> bool:
        """Indicates whether this adapter returns mock/synthetic data."""
        pass

    @abstractmethod
    def analyze(self, request: PerceptionBatchRequest) -> PerceptionOutput:
        """Analyze an input sequence and return standardized frame-level observations.
        
        Args:
            request: The batch request containing input identifier and optional frame count.
            
        Returns:
            PerceptionOutput containing standardized observations clearly marked with provider origin.
        """
        pass

