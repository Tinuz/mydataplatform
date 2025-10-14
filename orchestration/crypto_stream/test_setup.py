#!/usr/bin/env python3
"""
Test script voor crypto_stream setup

Valideert:
1. Kafka connectivity
2. Iceberg REST catalog
3. MinIO S3 connectivity
4. Producer functionality
"""

import sys
import time
import json


def test_kafka():
    """Test Kafka connection"""
    print("🔍 Testing Kafka connection...")
    
    try:
        from kafka import KafkaProducer, KafkaConsumer
        from kafka.admin import KafkaAdminClient, NewTopic
        
        # Test producer (use Docker service name when inside container)
        import os
        bootstrap_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092')
        producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        
        # Send test message
        producer.send('test_topic', {'test': 'message'})
        producer.flush()
        producer.close()
        
        print("✅ Kafka connection successful")
        return True
        
    except Exception as e:
        print(f"❌ Kafka connection failed: {e}")
        return False


def test_iceberg():
    """Test Iceberg REST catalog"""
    print("\n🔍 Testing Iceberg REST catalog...")
    
    try:
        import requests
        import os
        
        iceberg_url = os.getenv('ICEBERG_REST_URL', 'http://iceberg-rest:8181')
        response = requests.get(f'{iceberg_url}/v1/config')
        
        if response.status_code == 200:
            config = response.json()
            print(f"✅ Iceberg REST catalog accessible")
            print(f"   Config: {config}")
            return True
        else:
            print(f"❌ Iceberg returned status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Iceberg connection failed: {e}")
        return False


def test_minio():
    """Test MinIO S3 connectivity"""
    print("\n🔍 Testing MinIO S3...")
    
    try:
        import boto3
        from botocore.exceptions import ClientError
        import os
        
        minio_endpoint = os.getenv('MINIO_ENDPOINT', 'http://minio:9000')
        s3_client = boto3.client(
            's3',
            endpoint_url=minio_endpoint,
            aws_access_key_id='minio',
            aws_secret_access_key='minio12345',
            region_name='us-east-1',
            use_ssl=False
        )
        
        # List buckets
        response = s3_client.list_buckets()
        buckets = [b['Name'] for b in response['Buckets']]
        
        print(f"✅ MinIO accessible")
        print(f"   Buckets: {buckets}")
        
        # Check if 'lake' bucket exists
        if 'lake' not in buckets:
            print("   Creating 'lake' bucket...")
            s3_client.create_bucket(Bucket='lake')
            print("   ✅ Bucket created")
        
        return True
        
    except Exception as e:
        print(f"❌ MinIO connection failed: {e}")
        return False


def test_binance_websocket():
    """Test Binance WebSocket connectivity"""
    print("\n🔍 Testing Binance WebSocket...")
    
    try:
        import asyncio
        import websockets
        
        async def test_connection():
            url = "wss://stream.binance.com:9443/ws/btcusdt@trade"
            
            async with websockets.connect(url) as websocket:
                # Receive one message
                message = await asyncio.wait_for(websocket.recv(), timeout=10)
                data = json.loads(message)
                
                print(f"✅ Binance WebSocket accessible")
                print(f"   Sample trade: {data['s']} @ ${data['p']}")
                return True
        
        return asyncio.run(test_connection())
        
    except Exception as e:
        print(f"❌ Binance WebSocket failed: {e}")
        return False


def main():
    """Run all tests"""
    print("🚀 Crypto Stream Setup Validation\n")
    print("=" * 50)
    
    results = {
        'Kafka': test_kafka(),
        'Iceberg': test_iceberg(),
        'MinIO': test_minio(),
        'Binance WebSocket': test_binance_websocket(),
    }
    
    print("\n" + "=" * 50)
    print("\n📊 Test Results Summary:")
    print("-" * 50)
    
    for component, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{component:20s}: {status}")
    
    print("-" * 50)
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n🎉 All tests passed! Ready to start streaming.")
        print("\nNext steps:")
        print("1. Start the producer:")
        print("   docker-compose exec dagster python -m crypto_stream.producers.binance_producer")
        print("\n2. Materialize assets in Dagster UI:")
        print("   http://localhost:3000")
        return 0
    else:
        print("\n⚠️  Some tests failed. Check the logs above.")
        print("\nTroubleshooting:")
        
        if not results['Kafka']:
            print("- Kafka: docker-compose --profile streaming up -d kafka")
        if not results['Iceberg']:
            print("- Iceberg: docker-compose --profile streaming up -d iceberg-rest")
        if not results['MinIO']:
            print("- MinIO: docker-compose --profile standard up -d minio")
        if not results['Binance WebSocket']:
            print("- Check internet connectivity")
        
        return 1


if __name__ == "__main__":
    sys.exit(main())
