import re

# Leer el archivo
with open('agent.py', 'r', encoding='utf-8') as f:
    contenido = f.read()

# Reemplazar el timeout de 30s a 180s (3 minutos)
# Buscar: timeout=30
# Reemplazar con: timeout=180

contenido_nuevo = re.sub(
    r'timeout=30\)',
    r'timeout=180)',
    contenido
)

# Guardar
with open('agent.py', 'w', encoding='utf-8') as f:
    f.write(contenido_nuevo)

print("✅ Timeout actualizado de 30s → 180s")
print("🔄 Reinicia el backend: python main.py")