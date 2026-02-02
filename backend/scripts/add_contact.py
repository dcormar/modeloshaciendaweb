#!/usr/bin/env python3
"""
Script para añadir un contacto a la tabla user_contacts
"""

import asyncio
import os
import sys
from pathlib import Path

# Añadir el directorio backend al path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv
from services.supabase_rest import SupabaseREST

# Cargar .env
env_path = backend_dir / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path, override=False)
else:
    load_dotenv(override=False)


async def add_contact():
    """Añade un contacto a la base de datos"""
    
    # Datos del contacto
    contact_data = {
        "username": "demo@demo.com",
        "nombre": "Elena Medrano",
        "email": "elenamedranocopete@gmail.com",
        "telegram_username": None,
        "tipo": "compañera departamento ventas",
        "activo": True
    }
    
    try:
        sb = SupabaseREST()
        
        print(f"Añadiendo contacto: {contact_data['nombre']} ({contact_data['email']})")
        print(f"Usuario: {contact_data['username']}")
        print(f"Tipo: {contact_data['tipo']}")
        
        result = await sb.post("user_contacts", contact_data)
        
        if result and len(result) > 0:
            contact = result[0]
            print(f"\n✅ Contacto creado exitosamente!")
            print(f"ID: {contact.get('id')}")
            print(f"Nombre: {contact.get('nombre')}")
            print(f"Email: {contact.get('email')}")
            print(f"Tipo: {contact.get('tipo')}")
            return contact
        else:
            print("\n❌ Error: No se pudo crear el contacto")
            return None
            
    except Exception as e:
        print(f"\n❌ Error creando contacto: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    asyncio.run(add_contact())
