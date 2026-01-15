import asyncio
import websockets
import json
import sys

async def test_websocket():
    print("=" * 60)
    print("🔧 Test WebSocket - FindMyWorker Chat")
    print("=" * 60)
    
    # Solicitar datos
    token = input("\n📝 Pega tu token JWT: ").strip()
    if not token:
        print("❌ Token requerido")
        return
    
    order_id = input("📝 Order ID (presiona Enter para usar 32): ").strip() or "32"
    role = input("📝 Rol (cliente/trabajador): ").strip().lower() or "cliente"
    
    uri = f"ws://127.0.0.1:8000/ws/chat/{order_id}/?token={token}"
    
    print(f"\n🔌 Conectando a: ws://127.0.0.1:8000/ws/chat/{order_id}/")
    print(f"👤 Rol: {role}")
    print(f"🔑 Token: {token[:30]}...")
    print("\n")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ ¡CONEXIÓN ESTABLECIDA!\n")
            
            # Función para recibir mensajes
            async def recibir_mensajes():
                try:
                    while True:
                        mensaje = await websocket.recv()
                        data = json.loads(mensaje)
                        
                        if data.get('type') == 'connection_established':
                            print(f"📢 {data['message']}\n")
                        
                        elif data.get('type') == 'chat_message':
                            emoji = '👤' if data.get('sender_role') == 'CLIENT' else '👷'
                            print(f"\n{emoji} {data.get('sender_name')}: {data.get('content')}")
                            print(f"   └─ Enviado: {data.get('timestamp')}")
                        
                        elif data.get('type') == 'error':
                            print(f"\n❌ Error del servidor: {data.get('message')}")
                        
                        else:
                            print(f"\n📨 Mensaje: {data}")
                            
                except websockets.exceptions.ConnectionClosed:
                    print("\n🔌 Conexión cerrada por el servidor")
            
            # Función para enviar mensajes
            async def enviar_mensajes():
                await asyncio.sleep(1)  # Esperar un momento para ver mensajes de conexión
                
                print("💬 Escribe tus mensajes (escribe 'salir' para terminar):\n")
                
                # Enviar mensaje de prueba automático
                mensaje_prueba = f"Hola, soy {role}. Este es un mensaje de prueba."
                await websocket.send(json.dumps({"message": mensaje_prueba}))
                print(f"📤 [AUTO] Mensaje enviado: '{mensaje_prueba}'\n")
                
                while True:
                    try:
                        mensaje = await asyncio.get_event_loop().run_in_executor(
                            None, 
                            input, 
                            f"\n[{role.upper()}] Escribe mensaje: "
                        )
                        
                        if mensaje.lower() in ['salir', 'exit', 'quit']:
                            print("\n👋 Cerrando conexión...")
                            break
                        
                        if mensaje.strip():
                            await websocket.send(json.dumps({"message": mensaje}))
                            print(f"✅ Mensaje enviado")
                        
                    except EOFError:
                        break
            
            # Ejecutar ambas funciones simultáneamente
            await asyncio.gather(
                recibir_mensajes(),
                enviar_mensajes()
            )
    
    except websockets.exceptions.InvalidStatusCode as e:
        print(f"\n❌ Error de conexión - Código HTTP: {e.status_code}")
        print("Posibles causas:")
        if e.status_code == 403:
            print("  - Token JWT inválido o expirado")
            print("  - Usuario sin permisos para esta orden")
        elif e.status_code == 404:
            print("  - Ruta WebSocket incorrecta")
            print("  - Orden no encontrada")
        else:
            print(f"  - Error {e.status_code}")
    
    except websockets.exceptions.InvalidURI:
        print(f"\n❌ URI inválida")
    
    except ConnectionRefusedError:
        print("\n❌ No se pudo conectar al servidor")
        print("Verifica que Django esté corriendo en http://127.0.0.1:8000")
    
    except Exception as e:
        print(f"\n❌ Error inesperado: {type(e).__name__}")
        print(f"Detalles: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(test_websocket())
    except KeyboardInterrupt:
        print("\n\n👋 Programa terminado por el usuario (Ctrl+C)")
