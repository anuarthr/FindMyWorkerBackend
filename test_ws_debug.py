import asyncio
import websockets
import json

async def test_conexion():
    token = input("Token JWT: ").strip()
    order_id = input("Order ID (32): ").strip() or "32"
    
    uri = f"ws://127.0.0.1:8000/ws/chat/{order_id}/?token={token}"
    
    print(f"\n🔌 Intentando conectar...")
    print(f"URI: {uri[:80]}...")
    
    try:
        async with websockets.connect(uri) as ws:
            print("✅ CONECTADO!")
            
            # Recibir primer mensaje
            msg = await asyncio.wait_for(ws.recv(), timeout=5)
            print(f"📨 Recibido: {msg}")
            
            # Enviar mensaje
            await ws.send(json.dumps({"message": "Test"}))
            print("📤 Mensaje enviado")
            
            # Recibir respuesta
            msg = await asyncio.wait_for(ws.recv(), timeout=5)
            print(f"📨 Recibido: {msg}")
            
    except websockets.exceptions.InvalidStatus as e:
        print(f"\n❌ Error HTTP Status: {e.response.status_code if hasattr(e, 'response') else 'desconocido'}")
        print(f"Detalles: {e}")
        
        # Intentar ver respuesta del servidor
        if hasattr(e, 'response'):
            print(f"\nRespuesta del servidor:")
            print(f"Headers: {e.response.headers if hasattr(e.response, 'headers') else 'N/A'}")
            body = await e.response.read() if hasattr(e.response, 'read') else None
            if body:
                print(f"Body: {body.decode()}")
    
    except asyncio.TimeoutError:
        print("\n⏱️ Timeout esperando respuesta")
    
    except ConnectionRefusedError:
        print("\n❌ Conexión rechazada - ¿Está Django corriendo?")
    
    except Exception as e:
        print(f"\n❌ Error: {type(e).__name__}")
        print(f"Detalles: {e}")
        import traceback
        traceback.print_exc()

asyncio.run(test_conexion())
