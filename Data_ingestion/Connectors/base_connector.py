#base connector file
from abc import ABC,abstractmethod
from typing import Any,Dict,List,Optional
from datetime import datetime
import logging

logger=logging.getLogger(__name__)


class base_connector(ABC):

    """Abstract base class from all the data connectors"""

    def __init__(self,config: Dict[str,Any]):
        self.config=config
        self.name=self.__class__.__name__
        self.connected=False
        logger.info(f"Initilize {self.name}")

    @abstractmethod
    def connect(self) -> None:
        """Establish connection to data source"""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Close connection to data source"""
        pass

    @abstractmethod

    def fetch_data(self,query:Optional[Dict[str,Any]]= None) -> List[dict[str,Any]]:
        """Fetch data from source.
        
        Args:
            query:Source-specific query parameters.
        
        Returns:
            List of records as dictionaries
        """

        pass

    @abstractmethod

    def validate_connection(self) -> bool:
        """Validate that the connection is healthy."""
        pass

    def get_metadata(self) -> Dict[str,Any]:
        """Return metadata about this connector instance"""
        return{
            "connector_type":self.name,
            "config":{k:v for k, v in self.config.items() if "key" not in k.lower() and "secret" not in k.lower()},
            "connected":self._connected,
            "timestamp":datetime.utcnow().isoformat(),

        }
    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
        return False




