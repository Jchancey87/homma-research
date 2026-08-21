"""
WebSocket endpoint for real-time alert streaming.
Subscribes to Redis 'screener:alerts' channel and broadcasts to connected clients.
"""
import asyncio
import json
import logging
from typing import Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import redis.asyncio as aioredis
from services.quote_schema import parse_redis_quote, serialize_ws_quote

logger = logging.getLogger(__name__)

router = APIRouter()

# Connected WebSocket clients
connected_clients: Set[WebSocket] = set()

# Redis subscriber task reference
redis_subscriber_task = None


async def redis_subscriber():
    """Subscribe to Redis screener:alerts channel and broadcast to WebSocket clients."""
    try:
        redis = aioredis.from_url(
            'redis://localhost:6379/0',
            decode_responses=True
        )
        pubsub = redis.pubsub()
        await pubsub.subscribe('screener:alerts', 'screener:quotes')
        
        logger.info("Redis subscriber started for screener:alerts and screener:quotes")
        
        async for message in pubsub.listen():
            if message['type'] == 'message':
                channel = message['channel']
                raw_data = message['data']
                
                try:
                    parsed_data = json.loads(raw_data)
                    payload = None
                    
                    if channel == 'screener:alerts':
                        if isinstance(parsed_data, dict) and parsed_data.get('type') == 'MTF_SCANNER_UPDATE':
                            try:
                                from services.market_service import set_mtf_scanner_state
                                set_mtf_scanner_state(parsed_data.get('in_play', []))
                            except Exception as mtf_err:
                                logger.warning("Failed to update MTF scanner state in market_service: %s", mtf_err)
                            payload = json.dumps(parsed_data)
                        else:
                            msg_dict = {"type": "alert", "data": parsed_data}
                            # Keep backward compatibility by embedding symbol and alert_type at root
                            if isinstance(parsed_data, dict):
                                if "symbol" in parsed_data:
                                    msg_dict["symbol"] = parsed_data["symbol"]
                                if "alert_type" in parsed_data:
                                    msg_dict["alert_type"] = parsed_data["alert_type"]
                            payload = json.dumps(msg_dict)
                        
                    elif channel == 'screener:quotes':
                        if isinstance(parsed_data, dict):
                            try:
                                tick = parse_redis_quote(parsed_data)
                                payload = json.dumps(serialize_ws_quote(tick))
                            except ValueError as e:
                                logger.warning(f"Invalid quote tick: {e}")
                            
                    if payload:
                        # Broadcast to all connected WebSocket clients
                        disconnected = set()
                        for client in connected_clients:
                            try:
                                await client.send_text(payload)
                            except Exception:
                                disconnected.add(client)
                        
                        # Remove disconnected clients
                        connected_clients.difference_update(disconnected)
                except json.JSONDecodeError:
                    logger.warning("Bad Redis message: %s", raw_data[:200])
        
        await pubsub.unsubscribe('screener:alerts', 'screener:quotes')
        await redis.close()
    except Exception as e:
        logger.error(f"Redis subscriber error: {e}")


@router.on_event("startup")
async def start_redis_subscriber():
    """Start Redis subscriber on FastAPI startup."""
    global redis_subscriber_task
    redis_subscriber_task = asyncio.create_task(redis_subscriber())
    logger.info("WebSocket alert streaming enabled")


@router.on_event("shutdown")
async def stop_redis_subscriber():
    """Stop Redis subscriber on FastAPI shutdown."""
    global redis_subscriber_task
    if redis_subscriber_task:
        redis_subscriber_task.cancel()
        try:
            await redis_subscriber_task
        except asyncio.CancelledError:
            pass
    logger.info("WebSocket alert streaming disabled")


@router.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket):
    """
    WebSocket endpoint for real-time alert streaming.
    
    Connect to: ws://localhost:5000/ws/alerts
    
    Messages are JSON objects matching the screener alert payload:
    {
        "symbol": "TICKER",
        "price": 12.34,
        "volume": 123456,
        "rvol": 2.5,
        "gap_pct": 5.2,
        "float_shares": 50000000,
        "alert_type": "ALERT_TYPE",
        "time": "2026-06-05T21:48:29.000Z"
    }
    """
    await websocket.accept()
    connected_clients.add(websocket)
    logger.info(f"WebSocket client connected. Total: {len(connected_clients)}")
    
    try:
        # Keep connection alive and handle client messages
        while True:
            # Wait for any message from client (ping/pong or commands)
            data = await websocket.receive_text()
            
            # Handle client messages if needed
            try:
                msg = json.loads(data)
                if msg.get('type') == 'ping':
                    await websocket.send_text(json.dumps({'type': 'pong'}))
            except json.JSONDecodeError:
                pass
                
    except WebSocketDisconnect:
        connected_clients.discard(websocket)
        logger.info(f"WebSocket client disconnected. Total: {len(connected_clients)}")
    except Exception as e:
        connected_clients.discard(websocket)
        logger.error(f"WebSocket error: {e}")
