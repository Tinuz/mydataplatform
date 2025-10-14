"""
Binance WebSocket → Kafka Producer

Connects to Binance public WebSocket streams and publishes
real-time trade events to Kafka topic 'crypto_trades'.

Symbols: BTC/USDT, ETH/USDT, BNB/USDT
Stream: wss://stream.binance.com:9443/ws/<symbol>@trade

No API key required - public data only!
"""

import asyncio
import json
import logging
import signal
import sys
from datetime import datetime
from typing import Set

import websockets
from kafka import KafkaProducer
from kafka.errors import KafkaError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
BINANCE_WS_BASE = "wss://stream.binance.com:9443/ws"
KAFKA_BOOTSTRAP_SERVERS = "kafka:9092"
KAFKA_TOPIC = "crypto_trades"

# Crypto symbols to stream
SYMBOLS = [
    'btcusdt',  # Bitcoin
    'ethusdt',  # Ethereum
    'bnbusdt',  # Binance Coin
]


class BinanceKafkaProducer:
    """Streams Binance trades to Kafka"""
    
    def __init__(self):
        self.producer = None
        self.websockets: Set[websockets.WebSocketClientProtocol] = set()
        self.running = True
        self.message_count = 0
        self.error_count = 0
        
    async def start(self):
        """Initialize Kafka producer and start WebSocket connections"""
        logger.info("🚀 Starting Binance → Kafka producer...")
        
        # Initialize Kafka producer
        try:
            self.producer = KafkaProducer(
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None,
                acks='all',  # Wait for all replicas
                retries=3,
                max_in_flight_requests_per_connection=5,
                compression_type='gzip'
            )
            logger.info(f"✅ Connected to Kafka: {KAFKA_BOOTSTRAP_SERVERS}")
        except Exception as e:
            logger.error(f"❌ Failed to connect to Kafka: {e}")
            sys.exit(1)
        
        # Start WebSocket connections for each symbol
        tasks = [self.stream_symbol(symbol) for symbol in SYMBOLS]
        
        # Add monitoring task
        tasks.append(self.monitor_stats())
        
        # Run all tasks
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def stream_symbol(self, symbol: str):
        """Stream trades for a single symbol"""
        url = f"{BINANCE_WS_BASE}/{symbol}@trade"
        
        while self.running:
            try:
                logger.info(f"📡 Connecting to {symbol.upper()} stream...")
                
                async with websockets.connect(url) as websocket:
                    self.websockets.add(websocket)
                    logger.info(f"✅ Connected to {symbol.upper()}")
                    
                    async for message in websocket:
                        if not self.running:
                            break
                        
                        await self.process_message(symbol, message)
                
            except websockets.exceptions.ConnectionClosed:
                logger.warning(f"⚠️ Connection closed for {symbol.upper()}, reconnecting...")
                await asyncio.sleep(5)
            
            except Exception as e:
                logger.error(f"❌ Error streaming {symbol.upper()}: {e}")
                self.error_count += 1
                await asyncio.sleep(10)
    
    async def process_message(self, symbol: str, message: str):
        """Process and publish trade event to Kafka"""
        try:
            # Parse Binance trade event
            data = json.loads(message)
            
            # Transform to our schema
            event = {
                'symbol': data['s'],  # BTCUSDT
                'price': float(data['p']),
                'quantity': float(data['q']),
                'event_time': datetime.fromtimestamp(data['T'] / 1000).isoformat(),
                'trade_id': data['t'],
                'is_buyer_maker': data['m'],
                'ingested_at': datetime.utcnow().isoformat()
            }
            
            # Publish to Kafka (partition by symbol)
            future = self.producer.send(
                KAFKA_TOPIC,
                key=symbol,  # Partition key
                value=event
            )
            
            # Non-blocking success callback
            future.add_callback(lambda metadata: self.on_send_success(symbol, metadata))
            future.add_errback(lambda e: self.on_send_error(symbol, e))
            
            self.message_count += 1
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ Failed to parse message: {e}")
            self.error_count += 1
        
        except Exception as e:
            logger.error(f"❌ Failed to process message: {e}")
            self.error_count += 1
    
    def on_send_success(self, symbol: str, metadata):
        """Kafka send success callback"""
        if self.message_count % 100 == 0:
            logger.debug(
                f"✅ {symbol.upper()}: partition={metadata.partition}, "
                f"offset={metadata.offset}"
            )
    
    def on_send_error(self, symbol: str, exception):
        """Kafka send error callback"""
        logger.error(f"❌ Failed to send {symbol.upper()} to Kafka: {exception}")
        self.error_count += 1
    
    async def monitor_stats(self):
        """Log statistics every 30 seconds"""
        while self.running:
            await asyncio.sleep(30)
            
            logger.info(
                f"📊 Stats: {self.message_count} messages sent, "
                f"{self.error_count} errors, "
                f"{len(self.websockets)} active connections"
            )
    
    async def stop(self):
        """Gracefully shutdown"""
        logger.info("🛑 Shutting down producer...")
        self.running = False
        
        # Close WebSocket connections
        for ws in self.websockets:
            await ws.close()
        
        # Flush and close Kafka producer
        if self.producer:
            self.producer.flush()
            self.producer.close()
        
        logger.info(f"✅ Shutdown complete. Total messages: {self.message_count}")


# Global producer instance for signal handling
producer_instance = None


def signal_handler(signum, frame):
    """Handle SIGTERM/SIGINT gracefully"""
    logger.info(f"⚠️ Received signal {signum}, shutting down...")
    if producer_instance:
        asyncio.create_task(producer_instance.stop())


async def main():
    """Main entry point"""
    global producer_instance
    
    # Register signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Start producer
    producer_instance = BinanceKafkaProducer()
    
    try:
        await producer_instance.start()
    except KeyboardInterrupt:
        logger.info("⚠️ Interrupted by user")
    finally:
        await producer_instance.stop()


if __name__ == "__main__":
    asyncio.run(main())
