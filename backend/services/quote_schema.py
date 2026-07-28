from typing import Optional
from pydantic import BaseModel

class QuoteTick(BaseModel):
    symbol: str
    price: float
    volume: int = 0
    high: float = 0.0
    low: float = 0.0
    open: float = 0.0
    bid: Optional[float] = None
    ask: Optional[float] = None
    time: float

REDIS_KEY_MAP: dict[str, str] = {
    's': 'symbol',
    'p': 'price',
    'v': 'volume',
    'h': 'high',
    'l': 'low',
    'o': 'open',
    'b': 'bid',
    'a': 'ask',
    't': 'time'
}

def parse_redis_quote(raw: dict) -> QuoteTick:
    mapped = {}
    for short_key, long_key in REDIS_KEY_MAP.items():
        if short_key in raw:
            mapped[long_key] = raw[short_key]
    
    if 'symbol' not in mapped or 'price' not in mapped or mapped['price'] is None:
        raise ValueError("Missing required fields symbol or price")
        
    return QuoteTick(**mapped)

def serialize_ws_quote(tick: QuoteTick) -> dict:
    d = tick.model_dump()
    return {"type": "price", **d}
