#this file is used to generate the data 

import pandas as pd
from faker import Faker
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
import random
import uuid
import logging

from .base_connector import base_connector
## import the error handeling file here 

logger =get_logger(__name__)

fake=Faker()

class FakeConnector(base_connector):

    def __init__(self, config:Dict[str,Any]):
        super().__init__(config)
        self.locale=config.get("locale","en_us")
        self.seed=config.get("seed",None)
        self.fake=Faker(self.locale)
        if self.seed is not None:
            Faker.seed(self.seed)
            random.seed(self.seed)

    def connect(self) -> None:
            self._connected = True
            logger.info("Faker connector initialized")
    
    def disconnect(self) -> None:
            self._connected = False
    
    def validate_connection(self) -> bool:
            return True

    def fetch_data()