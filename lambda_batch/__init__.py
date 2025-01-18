import json
from typing import Dict

class Response:
    url: str
    timestamp: str
    html: str
    userId: str
        
    def __init__(self, response: Dict):
        self.url = response["url"]
        self.timestamp = response["timestamp"]
        self.html = response["html"]  
        self.userId = response["userId"]
        self.json = json.dumps(self.to_dict()) 

    def to_dict(self):
        return dict(url=self.url,
                    timestamp=self.timestamp,
                    html=self.html,
                    userId=self.userId)